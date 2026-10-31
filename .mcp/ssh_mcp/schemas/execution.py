# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Стандартизированные схемы результатов выполнения MCP
# =============================================================================
# Description:
#   Формирование унифицированных JSON-совместимых ответов всех инструментов
#   SSH MCP Server, включая метрики времени, коды возврата, структурированные
#   данные и детализированные ошибки.
#
#   Зачем нужен этот модуль:
#     1. Гарантия единого контракта ответа (Раздел 9 ТЗ) для интеграции с RAG,
#        SQLite и аналитикой ai-tc независимо от ОС (Windows или Linux).
#     2. Строгое разделение stdout, stderr, exit_code и стандартизированных
#        кодов ошибок (ACCESS_DENIED, APPROVAL_REQUIRED, TIMEOUT и др.).
#
# Usage Examples:
#   Python API:
#     from ssh_mcp.schemas.execution import StandardMCPResponse, ExecutionMetrics
#     resp = StandardMCPResponse(success=True, host="srv-01", platform="linux",
#                                operation="system.memory", data={"total_mb": 16384})
#
# File: execution.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.schemas
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:37:00
# =============================================================================

from datetime import datetime, timezone
from typing import Any, Dict, Literal
from pydantic import BaseModel, Field


class ExecutionMetrics(BaseModel):
    """Метрики выполнения команды или транспортной операции.

    Attributes:
        duration_ms (int): Длительность выполнения в миллисекундах.
        exit_code (int): Код завершения процесса (0 — успех).
        stdout (str): Очищенный от секретов стандартный поток вывода.
        stderr (str): Очищенный от секретов поток ошибок.
        truncated (bool): Признак усечения вывода при превышении лимита размера.

    Examples:
        >>> m = ExecutionMetrics(duration_ms=42, exit_code=0)
        >>> m.exit_code
        0
    """

    duration_ms: int = Field(default=0, ge=0)
    exit_code: int = Field(default=0)
    stdout: str = Field(default="")
    stderr: str = Field(default="")
    truncated: bool = Field(default=False)


class ErrorDetail(BaseModel):
    """Детализированное описание ошибки выполнения операции.

    Attributes:
        code (str): Стандартизированный машиночитаемый код ошибки.
        message (str): Описание причины ошибки на русском или английском языке.
        approval_id (str): Идентификатор ожидающего подтверждения (если требуется Approval).

    Examples:
        >>> err = ErrorDetail(code="ACCESS_DENIED", message="Administrative privileges required")
        >>> err.code
        'ACCESS_DENIED'
    """

    code: str = Field(default="")
    message: str = Field(default="")
    approval_id: str = Field(default="")


class StandardMCPResponse(BaseModel):
    """Единый стандартизированный ответ любого инструмента SSH MCP Server.

    Attributes:
        success (bool): Флаг успешного завершения операции.
        host (str): Идентификатор целевого хоста.
        platform (str): Операционная система хоста ('windows' или 'linux').
        operation (str): Идентификатор выполненной операции из Command Registry.
        timestamp (str): Временная метка завершения в формате UTC ISO-8601.
        execution (ExecutionMetrics): Метрики времени и потоков исполнения.
        data (Dict[str, Any]): Полезная структурированная нагрузка ответа.
        error (Dict[str, Any]): Объект ошибки (пустой словарь при успехе).

    Examples:
        >>> resp = StandardMCPResponse(
        ...     success=True,
        ...     host="linux-server-01",
        ...     platform="linux",
        ...     operation="system.memory",
        ...     data={"total_mb": 16384, "used_mb": 8192, "available_mb": 8192}
        ... )
        >>> resp.success
        True
    """

    success: bool
    host: str = Field(default="localhost")
    platform: str = Field(default="windows")
    operation: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    execution: ExecutionMetrics = Field(default_factory=ExecutionMetrics)
    data: Dict[str, Any] = Field(default_factory=dict)
    error: Dict[str, Any] = Field(default_factory=dict)

    def to_contract_dict(self) -> Dict[str, Any]:
        """Преобразование ответа в словарь строго по контракту раздела 9 ТЗ.

        Returns:
            Dict[str, Any]: Словарь с данными ответа.

        Examples:
            >>> r = StandardMCPResponse(success=True, operation="system.info")
            >>> d = r.to_contract_dict()
            >>> d["success"]
            True
        """
        payload = self.model_dump()
        if self.success and not self.error:
            payload["error"] = {}
        return payload


class TaskRecord(BaseModel):
    """Модель состояния асинхронной длительной задачи.

    Attributes:
        task_id (str): Уникальный идентификатор задачи.
        host_id (str): Целевой узел выполнения.
        command_id (str): Идентификатор команды.
        status (Literal['pending', 'running', 'completed', 'failed', 'cancelled']): Статус.
        created_at (str): Время создания в UTC.
        completed_at (str): Время завершения в UTC.
        result (Dict[str, Any]): Итоговый результат выполнения.

    Examples:
        >>> t = TaskRecord(task_id="tsk-1", host_id="srv-1", command_id="ssh.execute_async")
        >>> t.status
        'pending'
    """

    task_id: str
    host_id: str
    command_id: str
    status: Literal["pending", "running", "completed", "failed", "cancelled"] = Field(default="pending")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    completed_at: str = Field(default="")
    result: Dict[str, Any] = Field(default_factory=dict)
