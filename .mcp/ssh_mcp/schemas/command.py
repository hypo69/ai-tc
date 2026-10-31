# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Схемы каталога команд и политик привилегий (Command Registry)
# =============================================================================
# Description:
#   Определение моделей команд, входных параметров, уровней риска и политик
#   доступа для централизованного реестра Command Registry.
#
#   Зачем нужен этот модуль:
#     1. Исключение прямых бесконтрольных вызовов shell из MCP-инструментов.
#     2. Декларативная валидация аргументов, уровня привилегий (standard /
#        administrator) и уровня риска (low, medium, high, critical).
#
# Usage Examples:
#   Python API:
#     from ssh_mcp.schemas.command import CommandDefinition
#     cmd = CommandDefinition(id="linux.service.restart", name="Restart Service",
#                             platform="linux", category="services")
#
# File: command.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.schemas
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:36:30
# =============================================================================

from typing import Any, Dict, Literal
from pydantic import BaseModel, Field


class ParameterSpec(BaseModel):
    """Спецификация параметра команды в реестре.

    Attributes:
        type (Literal['string', 'integer', 'boolean', 'float', 'list', 'dict']): Тип параметра.
        required (bool): Обязательность передачи параметра.
        default (Any): Значение по умолчанию (если параметр не передан).
        description (str): Описание назначения параметра на русском языке.
        pattern (str): Регулярное выражение для валидации строковых значений.

    Examples:
        >>> spec = ParameterSpec(type="string", required=True)
        >>> spec.required
        True
    """

    type: Literal["string", "integer", "boolean", "float", "list", "dict"] = Field(default="string")
    required: bool = Field(default=True)
    default: Any = Field(default="")
    description: str = Field(default="")
    pattern: str = Field(default="")


class CommandDefinition(BaseModel):
    """Описание административной команды в Command Registry.

    Attributes:
        id (str): Уникальный идентификатор команды (например, windows.service.restart).
        name (str): Человекочитаемое название операции.
        platform (Literal['windows', 'linux', 'any']): Целевая платформа.
        category (str): Функциональная категория (system, processes, services и др.).
        executor (Literal['powershell', 'pwsh', 'cmd', 'bash', 'sh', 'internal']): Исполнитель.
        privilege (Literal['standard', 'administrator']): Требуемый уровень привилегий.
        risk_level (Literal['low', 'medium', 'high', 'critical']): Уровень риска операции.
        parameters (Dict[str, ParameterSpec]): Словарь спецификаций параметров.
        timeout (int): Максимальное время выполнения в секундах.
        requires_confirmation (bool): Признак обязательного подтверждения (Approval).
        audit (bool): Обязательность записи операции в журнал аудита.
        template (str): Безопасный шаблон команды или идентификатор адаптера.

    Examples:
        >>> cmd = CommandDefinition(
        ...     id="windows.service.restart",
        ...     name="Restart Windows Service",
        ...     platform="windows",
        ...     category="services",
        ...     executor="powershell",
        ...     privilege="administrator",
        ...     risk_level="high",
        ...     requires_confirmation=True
        ... )
        >>> cmd.risk_level
        'high'
    """

    id: str
    name: str
    platform: Literal["windows", "linux", "any"] = Field(default="any")
    category: str = Field(default="general")
    executor: Literal["powershell", "pwsh", "cmd", "bash", "sh", "internal"] = Field(default="internal")
    privilege: Literal["standard", "administrator"] = Field(default="standard")
    risk_level: Literal["low", "medium", "high", "critical"] = Field(default="low")
    parameters: Dict[str, ParameterSpec] = Field(default_factory=dict)
    timeout: int = Field(default=30, ge=1, le=3600)
    requires_confirmation: bool = Field(default=False)
    audit: bool = Field(default=True)
    template: str = Field(default="")
