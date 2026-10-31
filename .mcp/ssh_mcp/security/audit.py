# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Служба журналирования аудита (Audit Logger)
# =============================================================================
# Description:
#   Централизованный сервис записи всех административных операций в таблицу
#   `audit_log` и системный логгер проекта с обязательной очисткой секретов.
#
#   Зачем нужен этот модуль:
#     1. Гарантия 100% трассируемости действий AI-агента и администраторов.
#     2. Автоматический прогон деталей вызова через SecretRedactor до сохранения.
#
# Usage Examples:
#   Python API:
#     from ssh_mcp.security.audit import AuditLogger
#     audit.log_event(host_id="srv-01", operation="service.restart", status="success")
#
# File: audit.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.security
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:44:45
# =============================================================================

from typing import Any, Dict, List, Optional
from ..storage.repositories.audit_log_repo import AuditLogRepository
from .secret_redactor import SecretRedactor

try:
    from logger import logger
except ImportError:
    import logging

    logger = logging.getLogger("ssh_mcp.audit")


class AuditLogger:
    """Сервис аудита административных операций SSH MCP Server.

    Attributes:
        repo (AuditLogRepository): Репозиторий таблицы `audit_log`.
        redactor (SecretRedactor): Редактор секретов.
        enabled (bool): Признак активности аудита.

    Examples:
        >>> from ssh_mcp.storage.database import DatabaseManager
        >>> db = DatabaseManager(":memory:")
        >>> _ = db.initialize()
        >>> al = AuditLogger(AuditLogRepository(db), SecretRedactor())
        >>> bool(al.log_event("h1", "system.info", "low", "success", {"password": "123"}))
        True
    """

    def __init__(
        self,
        repo: AuditLogRepository,
        redactor: SecretRedactor,
        enabled: bool = True,
    ) -> None:
        """Инициализация службы аудита.

        Args:
            repo (AuditLogRepository): Репозиторий журнала аудита.
            redactor (SecretRedactor): Сервис очистки секретов.
            enabled (bool): Включено ли сохранение записей.

        Examples:
            >>> db = DatabaseManager(":memory:")
            >>> _ = db.initialize()
            >>> al = AuditLogger(AuditLogRepository(db), SecretRedactor())
        """
        self.repo = repo
        self.redactor = redactor
        self.enabled = enabled

    def log_event(
        self,
        host_id: str,
        operation: str,
        risk_level: str = "low",
        status: str = "success",
        details: Optional[Dict[str, Any]] = {},
        actor: str = "ai-agent",
    ) -> str:
        """Запись события в журнал аудита после предварительной очистки секретов.

        Args:
            host_id (str): Идентификатор целевого узла.
            operation (str): Выполняемая операция.
            risk_level (str): Уровень риска ('low', 'medium', 'high', 'critical').
            status (str): Статус выполнения ('success', 'failed', 'denied', 'approval_required').
            details (Optional[Dict[str, Any]]): Словарь параметров и результатов.
                                                Значение по умолчанию: {}.
            actor (str): Инициатор операции.

        Returns:
            str: Идентификатор созданной записи audit_id (или '', если аудит отключён).

        Examples:
            >>> db = DatabaseManager(":memory:")
            >>> _ = db.initialize()
            >>> al = AuditLogger(AuditLogRepository(db), SecretRedactor())
            >>> aid = al.log_event("srv-1", "user.create", "high", "success", {"password": "secret"})
            >>> aid.startswith("aud-")
            True
        """
        if not self.enabled:
            return ""
        safe_details = self.redactor.redact_dict(details if details else {})
        audit_id = self.repo.append_entry(
            host_id=host_id,
            actor=actor,
            operation=operation,
            risk_level=risk_level,
            status=status,
            redacted_details=safe_details,
        )
        logger.info(
            f"[SSH-MCP Audit] id={audit_id} host={host_id} op={operation} risk={risk_level} status={status}"
        )
        return audit_id

    def get_recent_logs(self, host_id: str = "", limit: int = 100) -> List[Dict[str, object]]:
        """Получение последних записей журнала аудита.

        Args:
            host_id (str): Фильтр по узлу (пустая строка — все узлы).
            limit (int): Максимальное число записей.

        Returns:
            List[Dict[str, object]]: Список записей аудита.

        Examples:
            >>> db = DatabaseManager(":memory:")
            >>> _ = db.initialize()
            >>> al = AuditLogger(AuditLogRepository(db), SecretRedactor())
            >>> al.get_recent_logs()
            []
        """
        return self.repo.list_entries(host_id=host_id, limit=limit)
