# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Core Tools - Dynamic Factory
# =============================================================================
# Description:
#   Фабрика динамических инструментов и мета-инструмент create_custom_tool.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.core.tools.dynamic_factory import DynamicSynthesizedTool
#
#     service = DynamicSynthesizedTool()
#
# File: dynamic_factory.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.core.tools
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 17:33:00
# =============================================================================

from __future__ import annotations
"""Фабрика динамических инструментов и мета-инструмент create_custom_tool."""

import asyncio
import json
import platform
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional
from header import __root__
from logger import logger
from apps.windows.sdk.core.models import RiskLevel
from apps.windows.sdk.core.tools.base import BaseTool, ToolExecutionResult
from apps.windows.sdk.core.tools.registry import ToolRegistry
from utils.command_validator import run_safe_async, validate_powershell_syntax

def to_ascii_slug(text: str) -> str:
    """Преобразует строку в безопасный ASCII-слаг для имени инструмента."""
    translit_map = {'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo', 'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch', 'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya', ' ': '-'}
    res = []
    for char in text.lower():
        if char in translit_map:
            res.append(translit_map[char])
        elif char.isalnum() or char in ('-', '_'):
            res.append(char)
        else:
            res.append('-')
    slug = ''.join(res)
    slug = re.sub('-+', '-', slug).strip('-_')
    return slug or 'custom-tool'

class DynamicSynthesizedTool(BaseTool):
    """Инструмент, синтезированный моделью на лету в процессе диалога."""
    is_dynamic = True

    def __init__(self, name: str, title: str, description: str, probe_script: str, parameters_schema: Optional[Dict[str, Any]]=None, instructions: str='', risk_level: RiskLevel=RiskLevel.SAFE) -> None:
        """Инициализация динамического инструмента."""
        self.name = to_ascii_slug(name)
        self.title = title or self.name
        self.description = description or f'Динамический инструмент {self.title}'
        self.probe_script = probe_script.strip()
        self.instructions = instructions or 'Выполнить системный зонд и вернуть структурированные данные.'
        self.parameters_schema = parameters_schema or {'type': 'object', 'properties': {}, 'additionalProperties': True}
        self.risk_level = risk_level

    async def execute(self, **kwargs: Any) -> ToolExecutionResult:
        """Исполнение динамического PowerShell скрипта с подстановкой параметров и самопроверкой."""
        if platform.system() != 'Windows':
            return ToolExecutionResult(tool_name=self.name, status='ok', data={'mock': True, 'message': 'Платформа не является Windows, зонд симулирован.'}, command_executed=self.probe_script)
        exec_script = self.probe_script
        for k, v in kwargs.items():
            val_str = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)
            exec_script = exec_script.replace(f'${k}', val_str)
        try:
            # Выполняем через модуль самопроверки run_safe_async с автоисправлением и UTF-8
            res = await run_safe_async(
                command=exec_script,
                dry_run=False,
                timeout_sec=15,
                shell='powershell',
                enforce_error_visibility=True
            )
            stdout = res.get('stdout', '').strip()
            stderr = res.get('stderr', '').strip()
            warnings = res.get('warnings', [])
            retcode = res.get('returncode', 0)

            if not res.get('success') and not stdout:
                return ToolExecutionResult(
                    tool_name=self.name,
                    status='error',
                    data={'stderr': stderr, 'warnings': warnings},
                    message=f"Ошибка выполнения динамического инструмента: {stderr or 'код ' + str(retcode)}",
                    command_executed=exec_script
                )

            try:
                parsed = json.loads(stdout) if stdout else []
            except json.JSONDecodeError:
                parsed = stdout

            msg = f"Инструмент '{self.title}' успешно выполнил сбор данных."
            if warnings:
                msg += f" Замечание: {'; '.join(warnings)}"

            return ToolExecutionResult(
                tool_name=self.name,
                status='ok' if not warnings else 'warn',
                data=parsed,
                message=msg,
                command_executed=res.get('sanitized_command') or exec_script,
                metadata={
                    'is_dynamic': True,
                    'instructions': self.instructions,
                    'description_ru': self.description,
                    'warnings': warnings
                }
            )
        except Exception as e:
            return ToolExecutionResult(tool_name=self.name, status='error', data=None, message=f'Сбой исполнения динамического инструмента: {e}', command_executed=exec_script)

class DynamicToolFactory:
    """Фабрика создания, регистрации и сохранения динамических инструментов."""

    def __init__(self, registry: ToolRegistry) -> None:
        """Инициализация фабрики."""
        self.registry = registry

    def create_and_register(self, tool_name: str, tool_title: str, description_ru: str, probe_script: str, parameters_schema: Optional[Dict[str, Any]]=None, instructions: str='', risk_level: str='safe') -> DynamicSynthesizedTool:
        """Создает динамический инструмент и немедленно регистрирует его в активном реестре."""
        r_level = RiskLevel.SAFE
        try:
            r_level = RiskLevel(risk_level.lower())
        except Exception:
            pass
        tool = DynamicSynthesizedTool(name=tool_name, title=tool_title, description=description_ru, probe_script=probe_script, parameters_schema=parameters_schema, instructions=instructions, risk_level=r_level)
        self.registry.register(tool, overwrite=True)
        self._persist_to_ai_instruments(tool)
        return tool

    def _persist_to_ai_instruments(self, tool: DynamicSynthesizedTool) -> None:
        """Сохраняет синтезированный в цепочке рассуждений инструмент в изолированную БД ai_instruments."""
        try:
            from apps.windows.ai_instruments.models import AIInstrumentCreate
            from apps.windows.ai_instruments.service import AIInstrumentsService
            from apps.windows.ai_instruments.storage import AIInstrumentsStorage

            cfg_path = __root__ / "apps" / "windows" / "api" / "config.json"
            engine = "sqlite"
            db_path = "data/ai_instruments/ai_instruments.db"
            hostinger_cfg: Dict[str, Any] = {}
            auto_extract = True
            title_prefix = ""

            if cfg_path.exists():
                try:
                    app_cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
                    inst_cfg = app_cfg.get("ai_instruments") or {}
                    engine = inst_cfg.get("engine", "sqlite")
                    db_path = inst_cfg.get("sqlite", {}).get("path", db_path)
                    hostinger_cfg = inst_cfg.get("hostinger", {})
                    runtime_cfg = inst_cfg.get("runtime") or {}
                    auto_extract = bool(runtime_cfg.get("auto_extract_from_reasoning", True))
                    title_prefix = str(runtime_cfg.get("title_prefix", "")).strip()
                except Exception:
                    pass

            if not auto_extract:
                return

            storage = AIInstrumentsStorage(db_path=db_path, engine=engine, hostinger_config=hostinger_cfg)
            srv = AIInstrumentsService(storage=storage)
            display_name = f"{title_prefix}: {tool.title}" if (title_prefix and not tool.title.startswith(title_prefix)) else tool.title
            srv.save_instrument(
                AIInstrumentCreate(
                    tool_id=f"inst_{tool.name.replace('-', '_')}",
                    name=display_name,
                    tool_type="powershell",
                    command=tool.probe_script,
                    description=tool.description,
                    target_entity="system",
                    parameters_schema=tool.parameters_schema,
                    risk_level=tool.risk_level.value if hasattr(tool.risk_level, "value") else str(tool.risk_level),
                    author_agent="dynamic_tool_factory",
                    tags=["#dynamic_synthesized", "#reasoning_chain"],
                )
            )
        except Exception as ex:
            logger.debug(f"[DynamicToolFactory] Не удалось синхронизировать инструмент '{tool.name}' в ai_instruments: {ex}")

    def save_as_skill(self, tool: DynamicSynthesizedTool) -> Dict[str, Any]:
        """Сохраняет динамический инструмент как постоянный навык в .agents/skills/."""
        safe_name = tool.name
        target_dir = __root__ / '.agents' / 'skills' / safe_name
        already_existed = (target_dir / 'SKILL.md').exists()
        skill_md_content = f'---\nname: {safe_name}\ndescription: Automated assistant skill for: {tool.description}\n---\n\n# {tool.title}\n\n## 🎯 Назначение (Purpose)\n{tool.description}\n\n## 🚀 Триггеры и применение (When to Use & Triggers)\nИспользуется при запросах пользователя о конфигурации хоста, экспресс-диагностике и аудите в интерфейсе Test Computer (/tc).\n\n## ⚙️ Протокол выполнения (Execution Protocol)\n{tool.instructions}\n'
        created_path = ''
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            skill_file = target_dir / 'SKILL.md'
            skill_file.write_text(skill_md_content, encoding='utf-8')
            if tool.probe_script and (not tool.probe_script.startswith('apps.windows')):
                scripts_dir = target_dir / 'scripts'
                scripts_dir.mkdir(parents=True, exist_ok=True)
                (scripts_dir / 'probe.ps1').write_text(tool.probe_script, encoding='utf-8')
            created_path = str(skill_file.relative_to(__root__))
        except Exception as e:
            logger.warning(f'[DynamicToolFactory] Не удалось записать навык в {target_dir}: {e}')
        if not created_path:
            created_path = f'.agents/skills/{safe_name}/SKILL.md'
        return {'name': safe_name, 'title': tool.title, 'path': created_path, 'description_ru': tool.description, 'is_new': not already_existed}

class CreateCustomToolMetaTool(BaseTool):
    """Системный мета-инструмент для создания новых инструментов моделью на лету."""
    name = 'create_custom_tool'
    title = 'Создание инструмента на лету'
    description = 'Создает, валидирует и регистрирует новый специализированный инструмент в памяти системы. Используй этот инструмент, когда встроенных инструментов недостаточно для точного ответа на вопрос пользователя (например: опрос специфических мышей, принтеров, Bluetooth, сетевых папок SMB, реестра или PnP устройств).'
    parameters_schema = {'type': 'object', 'properties': {'tool_name': {'type': 'string', 'description': "Краткий идентификатор инструмента в kebab-case (например: 'mouse-history-inspector', 'usb-device-auditor')"}, 'tool_title': {'type': 'string', 'description': 'Человекочитаемое название инструмента на русском языке'}, 'description_ru': {'type': 'string', 'description': 'Подробное описание назначения инструмента на русском языке'}, 'probe_script': {'type': 'string', 'description': 'PowerShell скрипт опроса с выводом в JSON (| ConvertTo-Json). Должен быть безопасным и read-only.'}, 'instructions': {'type': 'string', 'description': 'Пошаговый протокол выполнения инструмента'}}, 'required': ['tool_name', 'tool_title', 'description_ru', 'probe_script']}
    risk_level = RiskLevel.SAFE

    def __init__(self, factory: DynamicToolFactory) -> None:
        """Инициализация мета-инструмента."""
        self.factory = factory

    async def execute(self, tool_name: str, tool_title: str, description_ru: str, probe_script: str, instructions: str='', **kwargs: Any) -> ToolExecutionResult:
        """Регистрация нового инструмента и немедленный пробный запуск с синтаксической самопроверкой."""
        try:
            # 1. Предварительная синтаксическая самопроверка (AST-валидация)
            is_valid, errs = validate_powershell_syntax(probe_script)
            if not is_valid:
                err_msg = f"Ошибка синтаксиса PowerShell при создании инструмента '{tool_name}': {'; '.join(errs)}"
                logger.warning(f"[CreateCustomToolMetaTool] {err_msg}")
                return ToolExecutionResult(
                    tool_name=self.name,
                    status='error',
                    data={'syntax_errors': errs},
                    message=err_msg,
                    command_executed=probe_script
                )

            tool = self.factory.create_and_register(tool_name=tool_name, tool_title=tool_title, description_ru=description_ru, probe_script=probe_script, instructions=instructions)
            exec_res = await tool.execute()
            return ToolExecutionResult(tool_name=self.name, status='ok' if exec_res.status == 'ok' else 'warn', data=exec_res.data, message=f"Инструмент '{tool.title}' успешно создан, зарегистрирован в рантайме и выполнен.", command_executed=tool.probe_script, metadata={'created_tool_name': tool.name, 'created_tool_title': tool.title, 'created_tool_description': tool.description, 'is_new_tool': True, 'instructions': tool.instructions})
        except Exception as e:
            logger.error(f"[CreateCustomToolMetaTool] Сбой создания инструмента '{tool_name}': {e}", exc_info=True)
            return ToolExecutionResult(tool_name=self.name, status='error', data=None, message=f"Ошибка создания инструмента '{tool_name}': {e}")
