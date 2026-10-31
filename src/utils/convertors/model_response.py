# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin UTILS - Model Response Parser
# =============================================================================
# Description:
#   Универсальный парсер ответов языковых моделей (LLM).
#   Обрабатывает ответы, содержащие смесь Markdown, готового HTML, JSON-блоков
#   действий (Action blocks), цепочек рассуждений (Matrix Reasoning/ReAct)
#   и интерактивных команд PowerShell/CMD.
#
# Usage Examples:
#   Python API:
#     from src.utils.convertors.model_response import parse_model_response
#
#     result = parse_model_response(raw_text)
#     print(result["dialogue_html"])
#     print(result["actions"])
#
# File: model_response.py
# Project: ai-windows-admin
# Package: src.utils.convertors
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 19:47:00
# =============================================================================

from __future__ import annotations
"""Универсальный парсер ответов языковых моделей (LLM)."""

import json
import re
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup

from logger import logger
from src.utils.convertors.html import escape2html, html2escape
from src.utils.convertors.md import md2html


class ModelResponseParser:
    """
    Парсер структурированных ответов моделей ИИ.
    
    Поддерживает:
      - Выделение этапов рассуждения (ReAct, CoT, WikiLLM Toolbox);
      - Извлечение JSON-действий (```action ... ``` или ```tool_call ... ```);
      - Извлечение и валидацию команд Windows (PowerShell, CMD);
      - Безопасную конвертацию Markdown в HTML с сохранением существующей HTML-разметки.
    """

    # Регулярные выражения для шагов расследования
    RE_INVESTIGATION_STATUS = re.compile(
        r"^[>*\s﻿ ​]*(?:[💡⚙️🛠️✨📝🏁🔍🧠⚡]|WikiLLM Toolbox:|Запуск зонда|Шаг рассуждения|Модель синтезировала|Синтез решения|Завершение расследования)",
        re.IGNORECASE,
    )
    RE_INVESTIGATION_DATA = re.compile(
        r"^[>*\s﻿ ​]*(?:📊|Данные от|\*\*Данные|Полученные факты|Telemetry preview)",
        re.IGNORECASE,
    )

    # Регулярные выражения для команд Windows
    RE_CMD_LINE = re.compile(
        r"^(?:powershell(?:\.exe)?\s+|pwsh(?:\.exe)?\s+|(?:Stop|Get|Start|Restart|Set|New|Remove|Test|Invoke|Select|Where)-[A-Za-z]+|cmd(?:\.exe)?(?:\s+/c)?\s+|net(?:\.exe)?\s+(?:user|localgroup|start|stop|use|share|session)|taskkill\b|sc(?:\.exe)?\s+|reg(?:\.exe)?\s+|wmic\b|sfc\b|dism\b|gpupdate\b|ipconfig\b|route\b)",
        re.IGNORECASE,
    )

    @staticmethod
    def is_investigation_line(line: str) -> bool:
        """
        Проверяет, относится ли строка к статусам расследования модели.

        Args:
            line: Строка для анализа.

        Returns:
            bool: True если строка является шагом расследования.
        """
        s = (line or "").strip()
        if not s:
            return False
        return bool(ModelResponseParser.RE_INVESTIGATION_STATUS.search(s))

    @staticmethod
    def is_investigation_data(line: str) -> bool:
        """
        Проверяет, относится ли строка к заголовку данных инструмента.

        Args:
            line: Строка для анализа.

        Returns:
            bool: True если строка является заголовком блока данных.
        """
        s = (line or "").strip()
        if not s:
            return False
        return bool(ModelResponseParser.RE_INVESTIGATION_DATA.search(s))

    @staticmethod
    def clean_text(raw_text: str) -> str:
        """
        Очищает текст ответа от служебных тегов чата и голосовых разметок.

        Args:
            raw_text: Исходный текст.

        Returns:
            str: Очищенный текст.
        """
        if not raw_text:
            return ""
        text = str(raw_text)

        # Обработка тегов [VOICE] и [CHAT]
        if "[VOICE]" in text or "[CHAT]" in text:
            text = re.sub(r"\[VOICE\][\s\S]*?(?:\[/VOICE\]|(?=\[CHAT\])|$)", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\[/?CHAT\]", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\[/?VOICE\]", "", text, flags=re.IGNORECASE)

        # Очистка ритуальных приветствий в начале текста
        greetings = (
            r"^(?:Приветствую[^\.\n]*[\.\n]*|Здравствуйте[^\.\n]*[\.\n]*|"
            r"Как эксперт по[^\.\n]*[\.\n]*|Я системный инженер[^\.\n]*[\.\n]*|"
            r"Я провел анализ[^\.\n]*[\.\n]*|Я проанализировал[^\.\n]*[\.\n]*)"
        )
        text = re.sub(greetings, "", text.strip(), flags=re.IGNORECASE).strip()
        return text

    @staticmethod
    def extract_action_blocks(text: str) -> tuple[str, List[Dict[str, Any]]]:
        """
        Извлекает блоки готовых инструментов и действий (```action { ... } ```).

        Args:
            text: Исходный текст ответа.

        Returns:
            tuple: Очищенный текст с плейсхолдерами и список словарей действий.
        """
        actions: List[Dict[str, Any]] = []

        def _action_replacer(match: re.Match) -> str:
            raw_json = match.group(1).strip()
            try:
                parsed = json.loads(raw_json)
                if isinstance(parsed, dict):
                    # Приводим к стандарту структуры Action
                    action_id = str(parsed.get("action_id") or parsed.get("id") or f"action-{len(actions) + 1}")
                    title = str(parsed.get("title") or parsed.get("tool_title") or "Действие решения")
                    desc = str(parsed.get("description") or parsed.get("description_ru") or "")
                    cmd = str(parsed.get("execution_command") or parsed.get("command") or parsed.get("probe_script") or "").strip()
                    risk = str(parsed.get("risk") or "safe").lower()
                    shell = str(parsed.get("shell") or ("cmd" if cmd.startswith("cmd") or cmd.startswith("net ") else "powershell"))

                    actions.append({
                        "action_id": action_id,
                        "title": title,
                        "description": desc,
                        "execution_command": cmd,
                        "risk": risk,
                        "shell": shell,
                        "raw_json": parsed,
                    })
                    return f"###__ACTION_BLOCK_{len(actions) - 1}__###"
            except Exception as e:
                logger.debug(f"[ModelResponseParser] Не удалось распарсить JSON действия: {e}")
            return match.group(0)

        # Поиск блоков ```action { ... } ``` и ```json:action { ... } ```
        cleaned = re.sub(r"```(?:action|json:action)\s*(\{[\s\S]*?\})\s*```", _action_replacer, text, flags=re.IGNORECASE)

        # Поиск tool_call или json с create_custom_tool
        def _tool_call_replacer(match: re.Match) -> str:
            raw_json = match.group(1).strip()
            try:
                parsed = json.loads(raw_json)
                if isinstance(parsed, dict):
                    t_name = parsed.get("tool_name") or ""
                    args = parsed.get("arguments") or parsed
                    if t_name == "create_custom_tool" or args.get("execution_command") or args.get("probe_script"):
                        cmd = str(args.get("execution_command") or args.get("probe_script") or args.get("command") or "").strip()
                        if cmd:
                            actions.append({
                                "action_id": str(args.get("tool_name") or t_name or f"tool-{len(actions) + 1}"),
                                "title": str(args.get("tool_title") or args.get("title") or "Инструмент решения"),
                                "description": str(args.get("description_ru") or args.get("description") or ""),
                                "execution_command": cmd,
                                "risk": str(args.get("risk") or "safe"),
                                "shell": "powershell",
                                "raw_json": parsed,
                            })
                            return f"###__ACTION_BLOCK_{len(actions) - 1}__###"
            except Exception:
                pass
            return match.group(0)

        cleaned = re.sub(r"```(?:tool_call|json)\s*(\{[\s\S]*?(?:execution_command|probe_script|create_custom_tool)[\s\S]*?\})\s*```", _tool_call_replacer, cleaned, flags=re.IGNORECASE)
        return cleaned, actions

    @staticmethod
    def extract_investigation_steps(text: str) -> tuple[str, List[Dict[str, Any]]]:
        """
        Извлекает шаги расследования Matrix Reasoning / ReAct (> 💡, > ⚙️, > 🛠️, > 📊).

        Args:
            text: Текст с возможными строками рассуждений.

        Returns:
            tuple: Текст без шагов расследования и список шагов.
        """
        lines = text.split("\n")
        steps: List[Dict[str, Any]] = []
        dialogue_lines: List[str] = []
        in_data = False
        data_buf: List[str] = []
        data_title = ""

        for line in lines:
            trimmed = line.strip()

            if ModelResponseParser.is_investigation_data(trimmed):
                if in_data and data_buf:
                    steps.append({
                        "type": "data",
                        "title": data_title or "Данные инструмента",
                        "data": "\n".join(data_buf).strip(),
                    })
                data_title = re.sub(r"^[>*\s﻿ ​]+", "", trimmed)
                in_data = True
                data_buf = []
                continue

            if in_data:
                if trimmed.startswith("```json") or trimmed == "```":
                    if trimmed == "```" and data_buf:
                        steps.append({
                            "type": "data",
                            "title": data_title or "Данные инструмента",
                            "data": "\n".join(data_buf).strip(),
                        })
                        in_data = False
                        data_buf = []
                    continue

                if ModelResponseParser.is_investigation_line(trimmed) or ModelResponseParser.is_investigation_data(trimmed) or (not trimmed.startswith(">") and (trimmed.startswith("###") or trimmed.startswith("```"))):
                    if data_buf:
                        steps.append({
                            "type": "data",
                            "title": data_title or "Данные инструмента",
                            "data": "\n".join(data_buf).strip(),
                        })
                    in_data = False
                    data_buf = []
                else:
                    data_buf.append(re.sub(r"^[>*\s﻿ ​]+", "", line))
                    continue

            if ModelResponseParser.is_investigation_line(trimmed):
                clean_step = re.sub(r"^[>*\s﻿ ​]+", "", trimmed)
                steps.append({
                    "type": "status",
                    "text": clean_step,
                })
                continue

            dialogue_lines.append(line)

        if in_data and data_buf:
            steps.append({
                "type": "data",
                "title": data_title or "Данные инструмента",
                "data": "\n".join(data_buf).strip(),
            })

        return "\n".join(dialogue_lines).strip(), steps

    @classmethod
    def markdown_to_safe_html(cls, text: str) -> str:
        """
        Универсальное и безопасное преобразование Markdown в HTML.
        
        Корректно обрабатывает смешанный ввод (текст Markdown + фрагменты готового HTML),
        предотвращает двойное экранирование тегов и сохраняет структуру разметки.

        Args:
            text: Исходный текст.

        Returns:
            str: Результирующий валидный HTML.
        """
        if not text:
            return ""

        raw = text.strip()
        # Защита существующих блоков кода
        code_blocks: List[str] = []
        def _save_code(match: re.Match) -> str:
            lang = match.group(1) or ""
            code_content = match.group(2)
            escaped_code = html2escape(code_content.strip())
            css_lang = f" language-{lang.lower().strip()}" if lang else ""
            html_block = f'<pre class="uai-code-block p-2 rounded small font-monospace{css_lang}"><code>{escaped_code}</code></pre>'
            code_blocks.append(html_block)
            return f"\n\n@@@UAI_CODE_BLOCK_{len(code_blocks) - 1}@@@\n\n"

        protected = re.sub(r"```(\w+)?\s*([\s\S]*?)```", _save_code, raw)

        # Защита инлайн-кода
        inline_codes: List[str] = []
        def _save_inline(match: re.Match) -> str:
            code_str = match.group(1)
            escaped = html2escape(code_str.strip())
            tag = f'<code class="text-primary bg-body-secondary px-1 rounded">{escaped}</code>'
            inline_codes.append(tag)
            return f"@@@UAI_INLINE_{len(inline_codes) - 1}@@@"

        protected = re.sub(r"`([^`\n]+)`", _save_inline, protected)

        # Защита существующих валидных HTML-тегов и плейсхолдеров
        raw_html_snippets: List[str] = []
        def _save_html(match: re.Match) -> str:
            snippet = match.group(0)
            raw_html_snippets.append(snippet)
            return f"@@@UAI_RAW_HTML_{len(raw_html_snippets) - 1}@@@"

        # Защищаем существующие блочные и строчные теги, а также плейсхолдеры
        protected = re.sub(
            r"(?:###__ACTION_BLOCK_\d+__###|<\/?(?:div|span|h[1-6]|p|blockquote|code|table|thead|tbody|tr|th|td|ul|ol|li|hr|br|strong|em|a|i|button|pre)[^>]*>)",
            _save_html,
            protected,
        )

        # Экранируем оставшиеся символы & и < >, чтобы избежать внедрения некорректной разметки
        # Но сохраняем символы > в начале строк цитат
        lines = protected.split("\n")
        escaped_lines: List[str] = []
        for line in lines:
            if line.strip().startswith(">"):
                quote_part = re.match(r"^(\s*>+\s*)(.*)$", line)
                if quote_part:
                    q_prefix = quote_part.group(1)
                    q_content = html2escape(quote_part.group(2))
                    escaped_lines.append(f"{q_prefix}{q_content}")
                else:
                    escaped_lines.append(html2escape(line))
            else:
                escaped_lines.append(html2escape(line))

        working_text = "\n".join(escaped_lines)

        # Markdown заголовки (# - ######)
        working_text = re.sub(r"^[ \t]*######[ \t]+(.*$)", r'<h6 class="fw-bold text-info-emphasis mt-2 mb-1" style="font-size: 0.8rem;">\1</h6>', working_text, flags=re.MULTILINE)
        working_text = re.sub(r"^[ \t]*#####[ \t]+(.*$)", r'<h6 class="fw-bold text-info-emphasis mt-2 mb-1" style="font-size: 0.85rem;">\1</h6>', working_text, flags=re.MULTILINE)
        working_text = re.sub(r"^[ \t]*####[ \t]+(.*$)", r'<h6 class="fw-bold text-primary mt-2 mb-1" style="font-size: 0.95rem;">\1</h6>', working_text, flags=re.MULTILINE)
        working_text = re.sub(r"^[ \t]*###[ \t]+(.*$)", r'<h6 class="fw-bold text-primary mt-2 mb-1 fs-6">\1</h6>', working_text, flags=re.MULTILINE)
        working_text = re.sub(r"^[ \t]*##[ \t]+(.*$)", r'<h5 class="fw-bold text-body mt-2 mb-1">\1</h5>', working_text, flags=re.MULTILINE)
        working_text = re.sub(r"^[ \t]*#[ \t]+(.*$)", r'<h4 class="fw-bold text-body mt-2 mb-1">\1</h4>', working_text, flags=re.MULTILINE)

        # Горизонтальные разделители (---, ***, ___)
        working_text = re.sub(r"^[ \t]*(?:---|\*\*\*|___)[ \t]*$", r'<hr class="uai-divider my-2 border-secondary border-opacity-25">', working_text, flags=re.MULTILINE)

        # Ссылки [текст](url)
        working_text = re.sub(r"\[([^\]]+)\]\((https?://[^\s\)]+)\)", r'<a href="\2" target="_blank" rel="noopener noreferrer" class="text-primary text-decoration-underline">\1</a>', working_text)

        # Жирный и курсив
        working_text = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", working_text)
        working_text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", working_text)
        working_text = re.sub(r"(^|[^*])\*([^*]+?)\*([^*]|$)", r"\1<em>\2</em>\3", working_text)

        # Нумерованные списки: 1. элемент
        working_text = re.sub(
            r"^[ \t]*(\d+)\.[ \t]+(.*$)",
            r'<div class="ms-2 mb-1 d-flex align-items-start gap-1.5"><span class="badge bg-secondary font-monospace" style="font-size: 0.72rem;">\1</span><span>\2</span></div>',
            working_text,
            flags=re.MULTILINE,
        )
        # Маркированные списки: - или *
        working_text = re.sub(r"^[ \t]*[-*•][ \t]+(.*$)", r'<li class="ms-3 mb-1">\1</li>', working_text, flags=re.MULTILINE)

        # Цитаты (> цитата)
        working_text = re.sub(
            r"^[ \t]*>[ \t]+(.*$)",
            r'<div class="border-start border-primary border-3 ps-2 my-1 text-body bg-body-secondary py-1 rounded-end">\1</div>',
            working_text,
            flags=re.MULTILINE,
        )

        # Переносы строк
        working_text = working_text.replace("\n", "<br>")

        # Очистка избыточных <br> вокруг блочных элементов
        block_cleanup_regex = r"(?:<br\s*/?>\s*)*(</?(?:div|blockquote|table|thead|tbody|tr|th|td|h[1-6]|ul|ol|li|hr|pre)[^>]*>)(?:<br\s*/?>\s*)*"
        working_text = re.sub(block_cleanup_regex, r"\1", working_text, flags=re.IGNORECASE)

        # Восстановление защищенного оригинального HTML
        for i, snippet in enumerate(raw_html_snippets):
            working_text = working_text.replace(f"@@@UAI_RAW_HTML_{i}@@@", snippet)

        # Восстановление инлайн-кода
        for i, code_html in enumerate(inline_codes):
            working_text = working_text.replace(f"@@@UAI_INLINE_{i}@@@", code_html)

        # Восстановление блоков кода
        for i, block_html in enumerate(code_blocks):
            working_text = working_text.replace(f"@@@UAI_CODE_BLOCK_{i}@@@", block_html)

        return working_text

    @classmethod
    def parse(cls, raw_text: str) -> Dict[str, Any]:
        """
        Выполняет полный разбор ответа модели.

        Args:
            raw_text: Исходный текстовый ответ модели.

        Returns:
            dict: Структурированный результат с полями:
              - clean_text: очищенный текст диалога
              - html: безопасный результирующий HTML
              - actions: список обнаруженных действий
              - investigation_steps: шаги рассуждений ReAct/Matrix
              - commands: список извлеченных системных команд
        """
        cleaned = cls.clean_text(raw_text)
        text_without_actions, actions = cls.extract_action_blocks(cleaned)
        dialogue_text, steps = cls.extract_investigation_steps(text_without_actions)

        # Поиск отдельных командных блоков PowerShell / CMD в тексте
        commands: List[Dict[str, str]] = []
        for m in re.finditer(r"```(?:powershell|pwsh|ps1|cmd|bat)?\s*([\s\S]*?)```", dialogue_text, flags=re.IGNORECASE):
            cmd_code = m.group(1).strip()
            if cmd_code and (cls.RE_CMD_LINE.search(cmd_code) or "\n" in cmd_code or len(cmd_code) > 10):
                shell = "cmd" if m.group(0).lower().startswith("```cmd") else "powershell"
                commands.append({"command": cmd_code, "shell": shell})

        # Конвертация в безопасный HTML
        formatted_html = cls.markdown_to_safe_html(dialogue_text)

        return {
            "clean_text": dialogue_text,
            "html": formatted_html,
            "actions": actions,
            "investigation_steps": steps,
            "commands": commands,
        }


def parse_model_response(raw_text: str) -> Dict[str, Any]:
    """
    Универсальная функция парсинга ответа модели ИИ.

    Args:
        raw_text: Сырой ответ от модели.

    Returns:
        dict: Структурированные данные диалога, действий и HTML.
    """
    return ModelResponseParser.parse(raw_text)


def clean_model_response(raw_text: str) -> str:
    """
    Очищает ответ модели от служебных тегов и прелюдий.

    Args:
        raw_text: Исходный текст.

    Returns:
        str: Очищенный текст.
    """
    return ModelResponseParser.clean_text(raw_text)


def markdown_to_safe_html(text: str) -> str:
    """
    Преобразует Markdown в безопасный HTML без повреждения существующей разметки.

    Args:
        text: Markdown-текст или смешанный Markdown/HTML.

    Returns:
        str: HTML-разметка.
    """
    return ModelResponseParser.markdown_to_safe_html(text)
