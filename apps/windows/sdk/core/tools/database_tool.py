# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Core Tools - Database Instrument Tool
# =============================================================================
# Description:
#   Адаптер инструментов, сохраненных в изолированной базе данных ai_instruments
#   (Hostinger MariaDB / локальный SQLite). Позволяет загружать накопленный
#   арсенал инструментов агента в ToolRegistry и подключать его к ReAct-циклу
#   UniversalLangChainAgent с фиксацией счетчика запусков (execution_count).
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.core.tools.database_tool import register_database_instruments
#     from apps.windows.sdk.core.tools.registry import ToolRegistry
#
#     registry = ToolRegistry()
#     count = register_database_instruments(registry)
#     print(f"Загружено инструментов: {count}")
#
# File: database_tool.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.core.tools
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 18:56:00
# =============================================================================

from __future__ import annotations

"""Адаптер инструментов из базы ai_instruments для реестра ToolRegistry агента."""

import asyncio
import json
import platform
from pathlib import Path
from typing import Any, Dict, List, Optional

from header import __root__
from logger import logger
from apps.windows.sdk.core.models import RiskLevel
from apps.windows.sdk.core.tools.base import BaseTool, ToolExecutionResult
from apps.windows.sdk.core.tools.registry import ToolRegistry
from utils.command_validator import run_safe_async


class DatabaseInstrumentTool(BaseTool):
    """Инструмент агента, загруженный из изолированной базы ai_instruments."""

    is_dynamic: bool = True

    def __init__(
        self,
        tool_id: str,
        title: str,
        description: str,
        command: str,
        tool_type: str = "powershell",
        target_entity: str = "system",
        parameters_schema: Optional[Dict[str, Any]] = None,
        risk_level: RiskLevel = RiskLevel.SAFE,
        storage: Optional[Any] = None,
    ) -> None:
        """Инициализация инструмента из базы данных.

        Args:
            tool_id: Уникальный идентификатор инструмента в реестре (например, inst_process_powershell_callers).
            title: Человекочитаемое название инструмента на русском языке.
            description: Подробное описание назначения и собираемых параметров.
            command: Исполняемый скрипт или команда (PowerShell / CMD).
            tool_type: Тип среды выполнения (powershell, cmd, utility).
            target_entity: Домен/сущность Windows (process, service, network, storage, system).
            parameters_schema: OpenAPI схема входных параметров.
            risk_level: Уровень риска SafeOps.
            storage: Экземпляр AIInstrumentsStorage для фиксации счетчика вызовов.
        """
        self.tool_id = tool_id
        self.name = tool_id
        self.title = title or tool_id
        entity_tag = f"[{target_entity.upper()}] " if target_entity else ""
        self.description = f"{entity_tag}{description or title}"
        self.command = command.strip()
        self.tool_type = tool_type.lower()
        self.target_entity = target_entity
        self.parameters_schema = parameters_schema or {
            "type": "object",
            "properties": {},
            "additionalProperties": True,
        }
        self.risk_level = risk_level
        self._storage = storage

    async def execute(self, **kwargs: Any) -> ToolExecutionResult:
        """Исполнение инструмента на хосте с безопасной подстановкой параметров и фиксацией в БД.

        Args:
            **kwargs: Параметры вызова от модели.

        Returns:
            ToolExecutionResult: Результат выполнения с JSON-данными или текстом ошибки.
        """
        if platform.system() != "Windows":
            return ToolExecutionResult(
                tool_name=self.name,
                status="ok",
                data={"mock": True, "message": "Платформа не является Windows, опрос симулирован."},
                command_executed=self.command,
            )

        cmd_to_run = self.command
        # Подстановка параметров: как в формате {param}, так и в формате $param
        for k, v in kwargs.items():
            val_str = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)
            cmd_to_run = cmd_to_run.replace(f"{{{k}}}", val_str).replace(f"${k}", val_str)

        shell_type = "cmd" if self.tool_type == "cmd" else "powershell"

        try:
            res = await run_safe_async(
                command=cmd_to_run,
                dry_run=False,
                timeout_sec=25,
                shell=shell_type,
                enforce_error_visibility=True,
            )
            stdout = res.get("stdout", "").strip()
            stderr = res.get("stderr", "").strip()
            warnings = res.get("warnings", [])
            retcode = res.get("returncode", 0)

            # Инкрементируем счетчик выполнения в базе данных инструментов
            if self._storage and hasattr(self._storage, "record_execution"):
                try:
                    await asyncio.to_thread(self._storage.record_execution, self.tool_id)
                except Exception as ex_cnt:
                    logger.debug(f"[DatabaseInstrumentTool] Не удалось инкрементировать счетчик {self.tool_id}: {ex_cnt}")

            if not res.get("success") and not stdout:
                return ToolExecutionResult(
                    tool_name=self.name,
                    status="error",
                    data={"stderr": stderr, "warnings": warnings},
                    message=f"Ошибка выполнения инструмента {self.title}: {stderr or 'код ' + str(retcode)}",
                    command_executed=cmd_to_run,
                )

            try:
                parsed = json.loads(stdout) if stdout else []
            except json.JSONDecodeError:
                parsed = stdout

            msg = f"Инструмент '{self.title}' успешно выполнил сбор данных."
            if warnings:
                msg += f" Замечания: {'; '.join(warnings)}"

            return ToolExecutionResult(
                tool_name=self.name,
                status="ok" if not warnings else "warn",
                data=parsed,
                message=msg,
                command_executed=res.get("sanitized_command") or cmd_to_run,
                metadata={
                    "tool_id": self.tool_id,
                    "target_entity": self.target_entity,
                    "tool_type": self.tool_type,
                    "warnings": warnings,
                },
            )
        except Exception as e:
            logger.error(f"[DatabaseInstrumentTool] Сбой выполнения '{self.name}': {e}", exc_info=True)
            return ToolExecutionResult(
                tool_name=self.name,
                status="error",
                data=None,
                message=f"Сбой исполнения инструмента '{self.name}': {e}",
                command_executed=cmd_to_run,
            )


def register_database_instruments(
    registry: ToolRegistry,
    storage: Optional[Any] = None,
    limit: int = 150,
) -> int:
    """Загружает инструменты из базы ai_instruments и регистрирует их в ToolRegistry.

    Args:
        registry: Активный экземпляр ToolRegistry агента.
        storage: Экземпляр хранилища AIInstrumentsStorage. Если None, создается автоматически.
        limit: Максимальное количество инструментов для загрузки.

    Returns:
        int: Количество успешно зарегистрированных инструментов.
    """
    if storage is None:
        try:
            from apps.windows.ai_instruments.storage import AIInstrumentsStorage

            cfg_path = __root__ / "apps" / "windows" / "api" / "config.json"
            engine = "sqlite"
            db_path = "data/ai_instruments/ai_instruments.db"
            hostinger_cfg: Dict[str, Any] = {}

            if cfg_path.exists():
                try:
                    app_cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
                    inst_cfg = app_cfg.get("ai_instruments") or {}
                    engine = inst_cfg.get("engine", "sqlite")
                    db_path = inst_cfg.get("sqlite", {}).get("path", db_path)
                    hostinger_cfg = inst_cfg.get("hostinger", {})
                except Exception as ex_cfg:
                    logger.debug(f"[register_database_instruments] Ошибка чтения config.json: {ex_cfg}")

            storage = AIInstrumentsStorage(
                db_path=db_path,
                engine=engine,
                hostinger_config=hostinger_cfg,
            )
        except Exception as ex_st:
            logger.warning(f"[register_database_instruments] Не удалось инициализировать хранилище: {ex_st}")
            return 0

    try:
        instruments = storage.list_instruments(limit=limit)
    except Exception as ex_list:
        logger.warning(f"[register_database_instruments] Ошибка получения списка инструментов: {ex_list}")
        # Пробуем резервный опрос SQLite
        try:
            from apps.windows.ai_instruments.storage import AIInstrumentsStorage
            fallback_storage = AIInstrumentsStorage(
                db_path="data/ai_instruments/ai_instruments.db",
                engine="sqlite",
            )
            instruments = fallback_storage.list_instruments(limit=limit)
        except Exception:
            return 0

    registered_count = 0
    for inst in instruments:
        # Пропускаем, если инструмент с таким именем уже зарегистрирован в реестре
        if registry.has(inst.tool_id):
            continue

        r_level = RiskLevel.SAFE
        try:
            r_level = RiskLevel(str(inst.risk_level).lower())
        except Exception:
            pass

        tool = DatabaseInstrumentTool(
            tool_id=inst.tool_id,
            title=inst.name,
            description=inst.description,
            command=inst.command,
            tool_type=inst.tool_type,
            target_entity=inst.target_entity,
            parameters_schema=inst.parameters_schema,
            risk_level=r_level,
            storage=storage,
        )
        if registry.register(tool, overwrite=False):
            registered_count += 1

    logger.info(f"[register_database_instruments] Зарегистрировано {registered_count} инструментов из ai_instruments в ToolRegistry")
    return registered_count
