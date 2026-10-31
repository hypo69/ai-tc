# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Core - Universal LangChain Agent
# =============================================================================
# Description:
#   Универсальный агент на базе LangChain и LangGraph для решения абстрактных
#   и ранее неизвестных задач администрирования Windows.
#   Использует WikiLLM и ToolRegistry как динамический ящик с инструментами,
#   а при отсутствии готового инструмента синтезирует его на лету
#   через мета-инструмент create_custom_tool с потоковым выводом (SSE).
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.core.universal_langchain_agent import UniversalLangChainAgent
#
#     agent = UniversalLangChainAgent()
#     async for event in agent.stream_solve("Кто-то постоянно запускает PowerShell"):
#         print(event)
#
# File: universal_langchain_agent.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 18:57:00
# =============================================================================

from __future__ import annotations

"""Универсальный агент на базе LangChain и LangGraph для решения абстрактных задач Windows."""

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional

from header import __root__
from logger import logger

from apps.windows.sdk.core.tools.registry import ToolRegistry
from apps.windows.sdk.core.tools.system_tools import register_system_tools
from apps.windows.sdk.core.tools.database_tool import register_database_instruments
from apps.windows.sdk.core.tools.dynamic_factory import DynamicToolFactory, CreateCustomToolMetaTool
from apps.windows.sdk.core.agent_loop import extract_json_block


def _extract_chunk_text(chunk: Any) -> str:
    """Извлекает строковый текст из чанка LangChain (который может быть str, list или dict).

    Args:
        chunk: Объект ответа модели (AIMessageChunk или строка).

    Returns:
        str: Извлеченный текстовый фрагмент.
    """
    if hasattr(chunk, "content"):
        c = chunk.content
        if isinstance(c, str):
            return c
        if isinstance(c, list):
            res = []
            for item in c:
                if isinstance(item, dict):
                    res.append(str(item.get("text") or item.get("content") or ""))
                else:
                    res.append(str(item))
            return "".join(res)
        return str(c)
    return str(chunk)


class UniversalLangChainAgent:
    """Универсальный ReAct-агент с динамическим ящиком инструментов WikiLLM."""

    def __init__(self, model_name: Optional[str] = None) -> None:
        """Инициализация агента, реестра инструментов и мета-фабрики.

        Args:
            model_name: Опциональное переопределение модели.
        """
        resolved_model = model_name
        if not resolved_model:
            try:
                cfg_path = __root__ / "config.json"
                if cfg_path.exists():
                    with open(cfg_path, "r", encoding="utf-8") as f:
                        c_data = json.load(f)
                    resolved_model = (
                        c_data.get("ai_providers_and_models_configuration", {}).get("default_model")
                        or c_data.get("ai", {}).get("gemini", {}).get("model")
                    )
            except Exception:
                pass
        self.model_name = resolved_model or "gemini-2.5-flash"
        self.registry = ToolRegistry()
        register_system_tools(self.registry)
        try:
            # Загружаем инструменты из базы ai_instruments (Hostinger MariaDB / SQLite)
            register_database_instruments(self.registry)
        except Exception as ex_db:
            logger.warning(f"[UniversalLangChainAgent] Не удалось подгрузить базу ai_instruments: {ex_db}")
        self.factory = DynamicToolFactory(self.registry)
        self.meta_tool = CreateCustomToolMetaTool(self.factory)
        self.registry.register(self.meta_tool)
        self._llm = None

    def _get_api_key(self) -> str:
        """Извлечение рабочего ключа GEMINI_API_KEY из окружения или файла ключей."""
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            try:
                from src.ai.gemini.gemini_api_key_state import load_api_keys
                loaded, _, _ = load_api_keys()
                aiza_keys = [k for k in loaded if k.startswith("AIzaSy")]
                if aiza_keys:
                    api_key = aiza_keys[0]
                elif loaded:
                    api_key = loaded[0]
            except Exception as ex:
                logger.debug(f"[UniversalLangChainAgent] Не удалось считать ключи через state: {ex}")
        return api_key

    def _init_llm(self) -> Any:
        """Ленивая инициализация ChatGoogleGenerativeAI из LangChain."""
        if self._llm is not None:
            return self._llm

        api_key = self._get_api_key()
        if not api_key:
            logger.warning("[UniversalLangChainAgent] GEMINI_API_KEY не обнаружен, fallback на локальную модель/нативный клиент")

        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            self._llm = ChatGoogleGenerativeAI(
                model=self.model_name,
                google_api_key=api_key,
                temperature=0.1,
                streaming=True,
            )
        except Exception as e:
            logger.warning(f"[UniversalLangChainAgent] Ошибка инициализации ChatGoogleGenerativeAI: {e}")
            self._llm = None

        return self._llm

    def _build_tools_description(self) -> str:
        """Формирует структурированное текстовое описание доступных инструментов для промпта."""
        system_tools = []
        db_tools = []
        meta_tools = []

        for t in self.registry.list_tools():
            if t.name == "create_custom_tool":
                meta_tools.append(f"- **{t.name}**: {t.description}")
            elif getattr(t, "is_dynamic", False):
                db_tools.append(f"- **{t.name}**: {t.description}")
            else:
                system_tools.append(f"- **{t.name}**: {t.description}")

        sections = []
        if system_tools:
            sections.append("#### Встроенные системные коллекторы:\n" + "\n".join(system_tools))
        if db_tools:
            sections.append("#### Специализированный арсенал инструментов (ai_instruments):\n" + "\n".join(db_tools))
        if meta_tools:
            sections.append("#### Мета-инструменты синтеза на лету:\n" + "\n".join(meta_tools))

        return "\n\n".join(sections)

    def _build_system_prompt(self) -> str:
        """Создает системную инструкцию с описанием WikiLLM ящика инструментов и мета-инструмента."""
        tools_block = self._build_tools_description()
        return (
            "Ты — автономный инженерный AI-ассистент платформы AI Windows Admin для ОС Windows.\n"
            "Твоя задача — расследовать и решать ЛЮБЫЕ, в том числе абстрактные и ранее неизвестные задачи администрирования.\n\n"
            f"### 🧰 ДОСТУПНЫЙ ЯЩИК ИНСТРУМЕНТОВ (WIKILLM TOOLBOX):\n{tools_block}\n\n"
            "### ⚙️ ПРАВИЛА ВЫБОРА И СИНТЕЗА ИНСТРУМЕНТОВ:\n"
            "1. Сначала проверь: есть ли в ящике подходящий инструмент для сбора фактов.\n"
            "2. ЕСЛИ ИНСТРУМЕНТА НЕ ХВАТАЕТ для решения абстрактной задачи (например, требуется специфический опрос "
            "Bluetooth, Wi-Fi, PnP, планировщика задач, процессов, дескрипторов, сетевых портов или реестра):\n"
            "   ВЫЗОВИ мета-инструмент `create_custom_tool`! Сформируй валидный, безопасный read-only PowerShell скрипт "
            "с обязательной конвертацией вывода в JSON (`| ConvertTo-Json -Compress`).\n"
            "3. Для вызова инструмента верни СТРОГО блок JSON:\n"
            "```tool_call\n"
            '{"tool_name": "имя_инструмента", "arguments": { ... }}\n'
            "```\n"
            "4. Опирайся СТРОГО на фактические данные, возвращенные инструментами.\n"
            "5. ТОЧНОСТЬ ПУТЕЙ К ФАЙЛАМ В SafeOps execution_command:\n"
            "   - КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО сокращать или выдумывать пути 'по памяти'. В Windows многие современные программы "
            "(Google Drive File Stream, Chrome, Teams, Edge, Discord, Slack) хранят исполняемый файл в версионированных подкаталогах "
            "(например: `C:\\Program Files\\Google\\Drive File Stream\\132.0.0.0\\GoogleDriveFS.exe`).\n"
            "   - Если в телеметрии или результатах инструмента получен точный путь `Path` процесса, в `Start-Process` подставляй СТРОГО этот точный путь.\n"
            "   - Для безопасного перезапуска процессов используй шаблон, сохраняющий исходный путь:\n"
            "     `$p = (Get-Process <Name> | Select-Object -ExpandProperty Path -First 1); Stop-Process -Name <Name>; Start-Sleep -Seconds 3; if ($p -and (Test-Path $p)) { Start-Process $p }`\n"
            "   - Для Google Drive в корне каталога также всегда доступен официальный скрипт запуска: `Start-Process \"$env:ProgramFiles\\Google\\Drive File Stream\\launch.bat\"`.\n"
            "6. При формулировании итогового ответа используй понятный Markdown на русском языке с заголовками, списками и эмодзи.\n"
            "7. Если предлагаешь исправление или команду настройки, добавь в конце ответа блок SafeOps-действия:\n"
            "```action\n"
            "{\n"
            '  "action_id": "action_id",\n'
            '  "title": "Название действия",\n'
            '  "description": "Описание эффекта",\n'
            '  "execution_command": "powershell_команда"\n'
            "}\n"
            "```\n"
            "8. ГОТОВЫЕ КОМАНДНЫЕ СТРОКИ POWERSHELL ДЛЯ СЛУЖБ И КОМПОНЕНТОВ:\n"
            "   - Если в ответе рассматриваются службы (services), процессы, сетевые подключения или драйверы, ОБЯЗАТЕЛЬНО "
            "для каждого рассматриваемого компонента выводи точную команду PowerShell в отдельном блоке кода ```powershell "
            "(например: `Get-Service -Name <ServiceName>`). WebGUI автоматически превратит каждый такой блок кода в интерактивный терминал с кнопкой «Run»!\n"
            "   - СТРОЖАЙШЕЕ ПРАВИЛО: КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО использовать флаг `-ErrorAction SilentlyContinue` (или `-EA 0`)! "
            "Ошибки выполнения никогда нельзя глушить или замалчивать — оператор и модель всегда должны видеть реальный текст ошибки в stderr!\n"
            "   - Если службы или процессы могут отсутствовать, используй честный опрос по точной маске (*vmswitch*, *hyperv*, *hns*) "
            "или системные командлеты Get-NetAdapter, Get-VMSwitch:\n"
            "     ```powershell\n"
            "     Get-Service -Name hns, *vmswitch* | Select-Object Name, DisplayName, Status, StartType\n"
            "     ```\n"
            "9. УПРАВЛЕНИЕ ЛОКАЛЬНЫМИ ПОЛЬЗОВАТЕЛЯМИ И УЧЕТНЫМИ ЗАПИСЯМИ (NET USER):\n"
            "   - Для любых задач аудита, проверки паролей, флагов PasswordRequired/Active, блокировки или удаления "
            "локальных учетных записей ОБЯЗАТЕЛЬНО используй специализированный инструмент `net_user` "
            "и выдавай нативные быстрые команды Windows `net user <пользователь> ...` или `net localgroup ...`!\n"
            "   - КАТЕГОРИЧЕСКИ НЕ ИСПОЛЬЗУЙ тяжеловесные скрипты ADSI (`[ADSI]'WinNT://...'`) или WMI/CIM, если задачу "
            "можно решить через стандартный `net user`.\n"
            "   - НЕ СТЕСНЯЙСЯ предлагать опасные и радикальные действия (например, полное безвозвратное удаление учетной записи: "
            "`net user <username> /delete` или мгновенную блокировку: `net user <username> /active:no`).\n"
            "   - На запрос «как удалить пользователя?» или при расследовании несанкционированных учетных записей прямо приводи "
            "команду `net user <имя_пользователя> /delete` (с кратким предупреждением о деструктивном характере операции) "
            "и генерируй SafeOps action с `execution_command`: `cmd /c net user <имя_пользователя> /delete`.\n"
        )

    async def stream_solve(self, query: str) -> AsyncIterator[Dict[str, Any]]:
        """Потоковое решение абстрактной задачи с выбором или синтезом инструментов.

        Args:
            query: Задача или вопрос оператора на естественном языке.

        Yields:
            Dict[str, Any]: События SSE (status, tool_call, tool_created, tool_result, token, action).
        """
        yield {"type": "status", "text": "🧠 Анализ задачи и исследование ящика инструментов WikiLLM..."}

        # 1. Загрузка модели
        llm = self._init_llm()
        system_prompt = self._build_system_prompt()

        # 2. Попытка нативного ReAct через LangGraph (если доступен)
        use_native_langgraph = False
        try:
            from langgraph.prebuilt import create_react_agent
            from langchain_core.tools import tool

            # Оборачиваем инструменты реестра в LangChain Tools
            langchain_tools = []
            for t in self.registry.list_tools():
                tool_name = t.name
                tool_desc = t.description

                # Создаем замыкание для инструмента
                def make_runner(target_tool):
                    async def _runner(**kwargs):
                        res = await target_tool.execute(**kwargs)
                        return res.data if res.status == 'ok' else {'error': res.message}
                    return _runner

                func = make_runner(t)
                func.__name__ = tool_name.replace('-', '_')
                func.__doc__ = tool_desc
                langchain_tools.append(tool(func))

            if llm and langchain_tools:
                use_native_langgraph = True
        except Exception as ex:
            logger.debug(f"[UniversalLangChainAgent] LangGraph адаптер не активирован, запуск прямого ReAct: {ex}")

        # 3. Агентный цикл рассуждений (ReAct Loop)
        max_turns = 4
        current_context = f"Вопрос пользователя: «{query}»"
        conversation_log: List[str] = [current_context]

        for turn in range(max_turns):
            prompt = (
                f"{system_prompt}\n\n"
                f"--- ХОД РАССЛЕДОВАНИЯ ---\n"
                f"{''.join(conversation_log)}\n\n"
                "Сделай следующий шаг: вызови нужный инструмент (`tool_call`), создай новый через `create_custom_tool` "
                "или сформируй итоговый ответ пользователю."
            )

            yield {"type": "status", "text": f"⚙️ Шаг рассуждения {turn + 1}: выбор инструмента или синтез решения..."}

            # Запрос к LLM
            response_text = ""
            try:
                if llm and hasattr(llm, "astream"):
                    async for chunk in llm.astream(prompt):
                        chunk_str = _extract_chunk_text(chunk)
                        response_text += chunk_str
                else:
                    # Fallback на системный API Gemini
                    from src.ai.gemini.generative_ai import GoogleGenerativeAI
                    ai = GoogleGenerativeAI(model_name=self.model_name, system_instruction=system_prompt)
                    async for chunk in ai.chat_stream(prompt):
                        response_text += chunk
            except Exception as req_err:
                logger.error(f"[UniversalLangChainAgent] Ошибка обращения к модели: {req_err}")
                yield {"type": "status", "text": f"⚠️ Запрос к модели: {req_err}. Запуск эвристического зонда..."}
                response_text = '```tool_call\n{"tool_name": "windows_collector", "arguments": {"collector_name": "services"}}\n```'

            # Проверяем, есть ли вызов инструмента
            tool_match = re.search(r'```(?:tool_call|json)?\s*({[\s\S]*?"tool_name"[\s\S]*?})\s*```', response_text)
            tool_data = None
            if tool_match:
                tool_data = extract_json_block(tool_match.group(1))

            if not tool_data and '{"tool_name"' in response_text:
                tool_data = extract_json_block(response_text)

            if tool_data and "tool_name" in tool_data:
                called_tool = str(tool_data["tool_name"]).strip()
                args = tool_data.get("arguments", {})
                if not isinstance(args, dict) or not args:
                    # Если модель передала аргументы на верхнем уровне JSON
                    args = {k: v for k, v in tool_data.items() if k != "tool_name"}

                # Если это мета-инструмент создания нового инструмента
                if called_tool == "create_custom_tool":
                    new_tname = args.get("tool_name") or args.get("name") or f"probe-{turn}"
                    new_ttitle = args.get("tool_title") or args.get("title") or new_tname
                    new_desc = args.get("description_ru") or args.get("description") or f"Динамический зонд: {new_ttitle}"
                    new_script = (
                        args.get("probe_script")
                        or args.get("powershell_script")
                        or args.get("ps_script")
                        or args.get("code")
                        or args.get("script")
                        or args.get("command")
                        or "Get-Process | ConvertTo-Json"
                    )
                    new_instr = args.get("instructions") or args.get("instruction") or "Выполнить системный опрос и вернуть JSON."

                    yield {
                        "type": "tool_created",
                        "tool_name": new_tname,
                        "title": new_ttitle,
                        "script": new_script
                    }
                    yield {
                        "type": "status",
                        "text": f"✨ Модель синтезировала новый инструмент в WikiLLM: «{new_ttitle}» (`{new_tname}`). Выполняю на хосте..."
                    }

                    # Исполняем мета-инструмент с гарантированными параметрами
                    exec_res = await self.meta_tool.execute(
                        tool_name=new_tname,
                        tool_title=new_ttitle,
                        description_ru=new_desc,
                        probe_script=new_script,
                        instructions=new_instr
                    )
                    result_data = exec_res.data
                else:
                    yield {
                        "type": "tool_call",
                        "name": called_tool,
                        "arguments": args
                    }
                    yield {
                        "type": "status",
                        "text": f"🔍 Выполнение инструмента из ящика WikiLLM: `{called_tool}`..."
                    }
                    tool_obj = self.registry.get(called_tool)
                    if tool_obj:
                        if called_tool == "windows_collector" and "collector_name" not in args:
                            args["collector_name"] = args.get("domain") or args.get("collector") or args.get("name") or "processes"
                        try:
                            exec_res = await tool_obj.execute(**args)
                            result_data = exec_res.data if hasattr(exec_res, "data") else exec_res
                        except Exception as ex:
                            result_data = {"error": f"Ошибка вызова {called_tool}: {ex}"}
                    else:
                        result_data = {"error": f"Инструмент {called_tool} не найден в реестре"}

                # Записываем наблюдение в журнал диалога
                res_json = json.dumps(result_data, ensure_ascii=False, indent=2)[:3500]
                conversation_log.append(f"\n[Вызов инструмента {called_tool}]: {json.dumps(args, ensure_ascii=False)}\n")
                conversation_log.append(f"[Результат инструмента {called_tool}]:\n{res_json}\n")
                if hasattr(exec_res, "message") and exec_res.message and ("Замечание:" in exec_res.message or "Предупреждение:" in exec_res.message):
                    conversation_log.append(f"[Самопроверка системы]: {exec_res.message}\n")

                yield {
                    "type": "tool_result",
                    "name": called_tool,
                    "data_preview": str(res_json)[:600]
                }
            else:
                # Модель решила, что собрала достаточно информации и не вызывает инструмент
                clean_reply = re.sub(r'```(?:tool_call|json)?\s*{[\s\S]*?}\s*```', '', response_text).strip()
                if clean_reply and len(clean_reply) > 60 and not clean_reply.startswith("{"):
                    yield {"type": "status", "text": "📝 Формирование итогового экспертного заключения..."}
                    for line in clean_reply.split("\n"):
                        yield {"type": "token", "chunk": line + "\n"}
                        await asyncio.sleep(0.01)

                    action_match = re.search(r'```action\s*({[\s\S]*?})\s*```', response_text)
                    if action_match:
                        act_data = extract_json_block(action_match.group(1))
                        if act_data:
                            yield {"type": "action", "action": act_data}
                    return
                # Иначе переходим к финальному синтезу
                break

        # 4. Финальный синтез экспертного заключения на основе всех собранных улик
        yield {"type": "status", "text": "📝 Формирование итогового отчета на основе собранных фактов..."}

        synthesis_prompt = (
            f"{system_prompt}\n\n"
            f"--- ЖУРНАЛ РАССЛЕДОВАНИЯ И СОБРАННЫЕ ДАННЫЕ С ХОСТА ---\n"
            f"{''.join(conversation_log)}\n\n"
            f"ЗАДАЧА: Фаза сбора данных завершена. На основе собранных фактов сформируй подробный, исчерпывающий и структурированный ответ "
            f"для пользователя на его исходный вопрос: «{query}».\n"
            "СТРОГИЙ ЗАПРЕТ: НЕ вызывай инструменты! Не пиши блоки ```tool_call или JSON. Отвечай связным человеческим текстом на русском языке.\n"
            "ТРЕБОВАНИЯ К ОТВЕТУ:\n"
            "1. Укажи точные факты, события (Event ID 41, 1074, 6008 и др.), точное время, коды ошибок или процессы, если они зафиксированы в собранных логах.\n"
            "2. Дай понятное техническое объяснение первопричины случившегося.\n"
            "3. Приведи четкие рекомендации системного администратора по устранению или предотвращению инцидента.\n"
            "4. Если предлагаешь команду в блоке ```action, используй ТОЧНЫЙ путь к исполняемому файлу из собранных данных (учитывай папки версий, например 132.0.0.0, или скрипт launch.bat), либо шаблон с предварительным сохранением Path.\n"
            "5. Для каждой упомянутой службы или компонента Windows выведи готовую командную строку PowerShell в блоке ```powershell (например: Get-Service -Name <ServiceName>), а также общую сводную команду.\n"
            "Форматируй ответ в Markdown со списками и акцентами. Пиши строго по существу, без шаблонных вводных фраз."
        )

        full_synthesis_text = ""
        try:
            if llm and hasattr(llm, "astream"):
                async for chunk in llm.astream(synthesis_prompt):
                    chunk_str = _extract_chunk_text(chunk)
                    if "```tool_call" not in chunk_str and "tool_name" not in chunk_str:
                        full_synthesis_text += chunk_str
                        yield {"type": "token", "chunk": chunk_str}
            else:
                from src.ai.gemini.generative_ai import GoogleGenerativeAI
                ai = GoogleGenerativeAI(model_name=self.model_name, system_instruction=system_prompt)
                async for chunk in ai.chat_stream(synthesis_prompt):
                    if "```tool_call" not in chunk and "tool_name" not in chunk:
                        full_synthesis_text += chunk
                        yield {"type": "token", "chunk": chunk}

            action_match = re.search(r'```action\s*({[\s\S]*?})\s*```', full_synthesis_text)
            if action_match:
                act_data = extract_json_block(action_match.group(1))
                if act_data:
                    yield {"type": "action", "action": act_data}
        except Exception as synth_err:
            logger.error(f"[UniversalLangChainAgent] Ошибка финального синтеза: {synth_err}")
            yield {"type": "token", "chunk": f"\n\n**Результаты расследования:**\n{conversation_log[-1]}"}

        yield {"type": "status", "text": "🏁 Расследование завершено."}


__all__ = ["UniversalLangChainAgent"]

