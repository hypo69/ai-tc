# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin TESTS - Model Response Parser Test
# =============================================================================
# Description:
#   Тестирование универсального парсера ответов языковых моделей.
#
# File: test_model_response_parser.py
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 19:50:00
# =============================================================================

import pytest
from src.utils.convertors.model_response import (
    ModelResponseParser,
    parse_model_response,
    clean_model_response,
    markdown_to_safe_html,
)


def test_clean_model_response():
    """Проверка очистки приветствий и служебных тегов."""
    raw = "[CHAT]Здравствуйте! Я системный инженер. Вот ответ.[/CHAT][VOICE]Голос[/VOICE]"
    res = clean_model_response(raw)
    assert "Здравствуйте" not in res
    assert "[CHAT]" not in res
    assert "[VOICE]" not in res
    assert "Вот ответ." in res


def test_extract_action_blocks():
    """Проверка извлечения блоков ```action { ... } ```."""
    sample = (
        "Текст до действия\n\n"
        "```action\n"
        "{\n"
        '  "action_id": "create_david_moshe_smb_share",\n'
        '  "title": "Создать SMB-ресурс \'DavidMoshe\'",\n'
        '  "description": "Автоматическое создание каталога",\n'
        '  "execution_command": "powershell -Command \\"New-Item -Path C:\\\\Shares -Force\\""\n'
        "}\n"
        "```\n\n"
        "Текст после действия"
    )
    cleaned, actions = ModelResponseParser.extract_action_blocks(sample)
    assert len(actions) == 1
    assert actions[0]["action_id"] == "create_david_moshe_smb_share"
    assert actions[0]["title"] == "Создать SMB-ресурс 'DavidMoshe'"
    assert "###__ACTION_BLOCK_0__###" in cleaned


def test_extract_investigation_steps():
    """Проверка извлечения шагов ReAct/Matrix рассуждения."""
    sample = (
        "> 💡 *Анализ задачи и исследование ящика инструментов WikiLLM...*\n"
        "> ⚙️ **WikiLLM Toolbox**: Шаг рассуждения 1\n"
        "> 🏁 Завершение расследования.\n"
        "### Результат расследования\n"
        "Всё в порядке."
    )
    dialogue, steps = ModelResponseParser.extract_investigation_steps(sample)
    assert len(steps) == 3
    assert "### Результат расследования" in dialogue
    assert "> 💡" not in dialogue


def test_markdown_to_safe_html_with_mixed_content():
    """Проверка безопасного рендеринга смешанного Markdown и HTML."""
    sample = (
        "### 📂 Заголовок 3\n"
        "#### 1. Шаг номер один\n"
        "Текст с `кодом` и **жирным**.\n"
        "--- \n"
        "<h6>Готовый HTML заголовок</h6>\n"
        "```powershell\n"
        "Get-Process\n"
        "```\n"
    )
    html = markdown_to_safe_html(sample)
    assert "<h6" in html
    assert "Заголовок 3" in html
    assert "Шаг номер один" in html
    assert "<hr" in html
    assert "<strong>жирным</strong>" in html
    assert "<code" in html
    assert "Get-Process" in html
    # Проверяем, что готовый HTML не был повторно заэкранирован в &lt;h6&gt;
    assert "&lt;h6&gt;" not in html


def test_parse_model_response_full():
    """Комплексная проверка parse_model_response."""
    sample = (
        "> 💡 *Старт анализа*\n"
        "### 🛠️ Пошаговое руководство\n"
        "#### 1. Создание папки\n"
        "```powershell\n"
        'New-Item -Path "C:\\Shares\\דוד משה" -ItemType Directory -Force\n'
        "```\n"
        "```action\n"
        "{\n"
        '  "action_id": "create_smb",\n'
        '  "title": "Создать SMB",\n'
        '  "execution_command": "New-SmbShare"\n'
        "}\n"
        "```\n"
    )
    result = parse_model_response(sample)
    assert len(result["investigation_steps"]) == 1
    assert len(result["actions"]) == 1
    assert len(result["commands"]) == 1
    assert result["commands"][0]["command"].startswith("New-Item")
    assert "<h6" in result["html"]
