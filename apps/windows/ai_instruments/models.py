# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin AI Instruments - Data Models
# =============================================================================
# Description:
#   Модели данных для изолированной базы данных инструментов ИИ-агента
#   (ai_instruments.db). Хранит ТОЛЬКО исполняемые скрипты, утилиты и команды,
#   синтезированные моделью в цепочке рассуждений или переданные из советов.
#
# Usage Examples:
#   Python API:
#     from apps.windows.ai_instruments.models import AIInstrument, AIInstrumentCreate
#
#     inst = AIInstrument(
#         tool_id="inst_spooler_restart",
#         name="Перезапуск диспетчера печати",
#         tool_type="powershell",
#         command="Restart-Service -Name Spooler -Force",
#         description="Перезапускает зависшую службу печати",
#         target_entity="service:spooler"
#     )
#
# File: models.py
# Project: ai-windows-admin
# Package: apps.windows.ai_instruments
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-20 12:35:00
# =============================================================================

from __future__ import annotations

"""Модели данных для базы инструментов ИИ-агента (ai_instruments.db)."""

import datetime
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def get_current_iso_time() -> str:
    """Возвращает текущую дату и время в формате ISO 8601."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class AIInstrument(BaseModel):
    """Сущность инструмента ИИ-агента для базы данных ai_instruments.db."""

    tool_id: str = Field(
        default_factory=lambda: f"inst_{uuid.uuid4().hex[:12]}",
        description="Уникальный идентификатор инструмента",
    )
    name: str = Field(
        ...,
        description="Понятное название инструмента или скрипта",
    )
    tool_type: str = Field(
        default="powershell",
        description="Тип инструмента: powershell, utility, cmd, python",
    )
    command: str = Field(
        ...,
        description="Исполняемая команда или текст скрипта автоматизации",
    )
    description: str = Field(
        default="",
        description="Назначение инструмента и рекомендации агенту по использованию",
    )
    target_entity: str = Field(
        default="",
        description="Сущность Windows или канонический ключ (например, service:spooler, process:lsass.exe)",
    )
    parameters_schema: Dict[str, Any] = Field(
        default_factory=dict,
        description="JSON-схема аргументов и параметров запуска инструмента",
    )
    risk_level: str = Field(
        default="safe",
        description="Уровень риска операции: safe, caution, danger",
    )
    author_agent: str = Field(
        default="reasoning_chain",
        description="Источник/агент создания инструмента: reasoning_chain, gemini, admin",
    )
    tags: List[str] = Field(
        default_factory=lambda: ["#agent_tool"],
        description="Теги для семантической фильтрации и группировки",
    )
    execution_count: int = Field(
        default=0,
        description="Счётчик успешных запусков инструмента агентом",
    )
    last_executed_at: Optional[str] = Field(
        default=None,
        description="Временная метка последнего запуска в формате ISO 8601",
    )
    created_at: str = Field(
        default_factory=get_current_iso_time,
        description="Временная метка создания инструмента",
    )
    updated_at: str = Field(
        default_factory=get_current_iso_time,
        description="Временная метка последнего обновления инструмента",
    )


class AIInstrumentCreate(BaseModel):
    """Схема запроса на сохранение нового инструмента в ai_instruments.db."""

    tool_id: Optional[str] = Field(
        default=None,
        description="Опциональный пользовательский идентификатор инструмента",
    )
    name: str = Field(
        ...,
        description="Название инструмента или скрипта",
    )
    tool_type: str = Field(
        default="powershell",
        description="Тип инструмента: powershell, utility, cmd, python",
    )
    command: str = Field(
        ...,
        description="Исполняемая команда или тело скрипта",
    )
    description: Optional[str] = Field(
        default="",
        description="Описание назначения инструмента",
    )
    target_entity: Optional[str] = Field(
        default="",
        description="Связанная сущность системы (process, service, etc.)",
    )
    parameters_schema: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Схема параметров",
    )
    risk_level: Optional[str] = Field(
        default="safe",
        description="Уровень риска: safe, caution, danger",
    )
    author_agent: Optional[str] = Field(
        default="reasoning_chain",
        description="Агент или источник создания",
    )
    tags: Optional[List[str]] = Field(
        default_factory=lambda: ["#agent_tool"],
        description="Теги для каталогизации",
    )


class AIInstrumentExecuteRequest(BaseModel):
    """Схема запроса на запуск инструмента."""

    tool_id: str = Field(
        ...,
        description="Идентификатор инструмента в ai_instruments.db",
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Параметры подстановки в команду",
    )
    timeout_sec: int = Field(
        default=35,
        ge=5,
        le=300,
        description="Таймаут выполнения команды в секундах",
    )
    as_admin: bool = Field(
        default=False,
        description="Запуск с повышенными привилегиями Администратора (RunAs)",
    )

