# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Менеджер подтверждения опасных операций (Approval Manager)
# =============================================================================
# Description:
#   Контроль выполнения команд с высоким (`high`) и критическим (`critical`)
#   уровнем риска. Привязывает подтверждение (Approval) строго к конкретному
#   узлу `host_id`, идентификатору команды `command_id` и SHA-256 хэшу
#   канонических параметров (Раздел 5 ТЗ).
#
#   Зачем нужен этот модуль:
#     1. Гарантия того, что общее разрешение "Full Admin" не позволяет ИИ
#        самостоятельно перезапускать службы, удалять пользователей или
#        менять правила межсетевого экрана без явного подтверждения.
#     2. Защита от подмены аргументов после получения подтверждения.
#
# Usage Examples:
#   Python API:
#     from ssh_mcp.core.approval_manager import ApprovalManager
#     am = ApprovalManager(approvals_repo)
#     req = am.require_or_verify("srv-1", cmd_def, {"service_name": "sshd"})
#
# File: approval_manager.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:49:30
# =============================================================================

import hashlib
import json
from typing import Any, Dict, List
import uuid

from ..schemas.command import CommandDefinition
from ..storage.repositories.approvals_repo import ApprovalsRepository


class ApprovalRequiredException(PermissionError):
    """Исключение, сигнализирующее о необходимости подтверждения операции администратором.

    Attributes:
        approval_id (str): Идентификатор созданного или ожидающего запроса.
        host_id (str): Целевой узел.
        command_id (str): Команда.
        risk_level (str): Уровень риска.
    """

    def __init__(self, approval_id: str, host_id: str, command_id: str, risk_level: str, message: str) -> None:
        """Инициализация исключения подтверждения.

        Args:
            approval_id (str): Идентификатор запроса подтверждения.
            host_id (str): Идентификатор хоста.
            command_id (str): Идентификатор команды.
            risk_level (str): Уровень риска.
            message (str): Текст пояснения.

        Examples:
            >>> ex = ApprovalRequiredException("app-1", "h1", "cmd", "high", "Needs approval")
            >>> ex.approval_id
            'app-1'
        """
        super().__init__(message)
        self.approval_id = approval_id
        self.host_id = host_id
        self.command_id = command_id
        self.risk_level = risk_level


class ApprovalManager:
    """Менеджер запросов и проверки подтверждений для опасных административных операций.

    Attributes:
        repo (ApprovalsRepository): Репозиторий таблицы `approvals`.
        require_for_high (bool): Требовать ли подтверждение для уровня `high`.
        require_for_critical (bool): Требовать ли подтверждение для уровня `critical`.

    Examples:
        >>> from ssh_mcp.storage.database import DatabaseManager
        >>> db = DatabaseManager(":memory:")
        >>> _ = db.initialize()
        >>> am = ApprovalManager(ApprovalsRepository(db))
        >>> h = am.compute_params_hash({"service_name": "nginx"})
        >>> len(h) == 64
        True
    """

    def __init__(
        self,
        repo: ApprovalsRepository,
        require_for_high: bool = True,
        require_for_critical: bool = True,
    ) -> None:
        """Инициализация менеджера подтверждений.

        Args:
            repo (ApprovalsRepository): Репозиторий таблицы `approvals`.
            require_for_high (bool): Обязательность подтверждения для `high`.
            require_for_critical (bool): Обязательность подтверждения для `critical`.

        Examples:
            >>> db = DatabaseManager(":memory:")
            >>> _ = db.initialize()
            >>> am = ApprovalManager(ApprovalsRepository(db))
        """
        self.repo = repo
        self.require_for_high = require_for_high
        self.require_for_critical = require_for_critical

    @staticmethod
    def compute_params_hash(parameters: Dict[str, Any]) -> str:
        """Вычисление детерминированного SHA-256 хэша словаря параметров (без поля approval_id).

        Args:
            parameters (Dict[str, Any]): Словарь аргументов команды.

        Returns:
            str: Hex-строка SHA-256.

        Examples:
            >>> ApprovalManager.compute_params_hash({"b": 2, "a": 1}) == ApprovalManager.compute_params_hash({"a": 1, "b": 2})
            True
        """
        clean_params = {
            k: v for k, v in (parameters or {}).items() if k not in ("approval_id", "password", "secret")
        }
        canonical = json.dumps(clean_params, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def needs_approval(self, command: CommandDefinition) -> bool:
        """Определение, требует ли команда явного подтверждения по политике риска.

        Args:
            command (CommandDefinition): Определение команды.

        Returns:
            bool: True, если требуется подтверждение.

        Examples:
            >>> db = DatabaseManager(":memory:")
            >>> _ = db.initialize()
            >>> am = ApprovalManager(ApprovalsRepository(db))
            >>> c = CommandDefinition(id="win.restart", name="Restart", risk_level="high")
            >>> am.needs_approval(c)
            True
        """
        if command.requires_confirmation:
            return True
        if command.risk_level == "critical" and self.require_for_critical:
            return True
        if command.risk_level == "high" and self.require_for_high:
            return True
        return False

    def verify_or_request(
        self,
        host_id: str,
        command: CommandDefinition,
        parameters: Dict[str, Any],
        approval_id: str = "",
        actor: str = "ai-agent",
    ) -> bool:
        """Проверка наличия одобренного подтверждения либо создание нового запроса.

        Если подтверждение привязано к другому хосту, другой команде или другим
        параметрам, выбрасывается `ApprovalRequiredException`.

        Args:
            host_id (str): Идентификатор целевого хоста.
            command (CommandDefinition): Определение команды.
            parameters (Dict[str, Any]): Параметры вызова.
            approval_id (str): Переданный идентификатор подтверждения (если уже получен).
            actor (str): Инициатор запроса.

        Returns:
            bool: True, если подтверждение не требуется или успешно верифицировано.

        Exceptions:
            ApprovalRequiredException: Если требуется подтверждение или оно было отклонено.

        Examples:
            >>> db = DatabaseManager(":memory:")
            >>> _ = db.initialize()
            >>> am = ApprovalManager(ApprovalsRepository(db))
            >>> cmd = CommandDefinition(id="system.info", name="Info", risk_level="low")
            >>> am.verify_or_request("h1", cmd, {})
            True
        """
        if not self.needs_approval(command):
            return True

        params_hash = self.compute_params_hash(parameters)

        if approval_id:
            record = self.repo.get_approval(approval_id)
            if not record:
                raise ApprovalRequiredException(
                    approval_id=approval_id,
                    host_id=host_id,
                    command_id=command.id,
                    risk_level=command.risk_level,
                    message=f"Указанное подтверждение '{approval_id}' не найдено в реестре",
                )
            if (
                str(record.get("host_id")) != host_id
                or str(record.get("command_id")) != command.id
                or str(record.get("parameters_hash")) != params_hash
            ):
                raise ApprovalRequiredException(
                    approval_id=approval_id,
                    host_id=host_id,
                    command_id=command.id,
                    risk_level=command.risk_level,
                    message=(
                        f"Подтверждение '{approval_id}' привязано к другим параметрам/хосту "
                        f"и не может быть использовано для '{command.id}' на '{host_id}'"
                    ),
                )
            status = str(record.get("status", "pending"))
            if status == "approved":
                return True
            if status == "rejected":
                raise ApprovalRequiredException(
                    approval_id=approval_id,
                    host_id=host_id,
                    command_id=command.id,
                    risk_level=command.risk_level,
                    message=f"Выполнение операции '{command.id}' отклонено администратором (approval_id={approval_id})",
                )
            raise ApprovalRequiredException(
                approval_id=approval_id,
                host_id=host_id,
                command_id=command.id,
                risk_level=command.risk_level,
                message=f"Запрос подтверждения '{approval_id}' находится в статусе ожидания ('pending')",
            )

        existing = self.repo.find_matching_approval(host_id, command.id, params_hash)
        if existing and str(existing.get("status")) == "approved":
            return True

        new_id = f"apr-{uuid.uuid4().hex[:10]}"
        safe_params = {k: v for k, v in parameters.items() if k not in ("password", "secret", "token")}
        self.repo.create_approval(
            approval_id=new_id,
            host_id=host_id,
            command_id=command.id,
            parameters_hash=params_hash,
            parameters=safe_params,
            risk_level=command.risk_level,
            requested_by=actor,
        )
        raise ApprovalRequiredException(
            approval_id=new_id,
            host_id=host_id,
            command_id=command.id,
            risk_level=command.risk_level,
            message=(
                f"Операция '{command.id}' на узле '{host_id}' имеет уровень риска '{command.risk_level}' "
                f"и требует явного подтверждения администратора (approval_id='{new_id}')"
            ),
        )

    def approve(self, approval_id: str, decided_by: str = "administrator") -> bool:
        """Одобрение ожидающего запроса администратором.

        Args:
            approval_id (str): Идентификатор запроса.
            decided_by (str): Имя администратора.

        Returns:
            bool: True при успешном одобрении.

        Examples:
            >>> db = DatabaseManager(":memory:")
            >>> _ = db.initialize()
            >>> am = ApprovalManager(ApprovalsRepository(db))
            >>> am.approve("nonexistent")
            False
        """
        return self.repo.update_status(approval_id, "approved", decided_by)

    def reject(self, approval_id: str, decided_by: str = "administrator") -> bool:
        """Отклонение ожидающего запроса администратором.

        Args:
            approval_id (str): Идентификатор запроса.
            decided_by (str): Имя администратора.

        Returns:
            bool: True при успешном отклонении.

        Examples:
            >>> db = DatabaseManager(":memory:")
            >>> _ = db.initialize()
            >>> am = ApprovalManager(ApprovalsRepository(db))
            >>> am.reject("nonexistent")
            False
        """
        return self.repo.update_status(approval_id, "rejected", decided_by)

    def list_pending_approvals(self) -> List[Dict[str, object]]:
        """Получение всех запросов, ожидающих подтверждения.

        Returns:
            List[Dict[str, object]]: Список записей со статусом 'pending'.

        Examples:
            >>> db = DatabaseManager(":memory:")
            >>> _ = db.initialize()
            >>> am = ApprovalManager(ApprovalsRepository(db))
            >>> am.list_pending_approvals()
            []
        """
        return self.repo.list_pending()
