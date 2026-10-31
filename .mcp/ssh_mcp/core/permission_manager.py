# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Менеджер прав доступа и привилегий (Permission Manager)
# =============================================================================
# Description:
#   Проверка разрешений на выполнение команд для конкретного хоста, контроль
#   категорий операций, предельного уровня риска и политики повышения
#   привилегий (standard vs administrator).
#
#   Зачем нужен этот модуль:
#     1. Реализация ступени "Check Host Permissions & Check Privilege Level"
#        жизненного цикла команды (Раздел 5 и 6 ТЗ).
#     2. Загрузка профилей `default.yaml` и `admin.yaml` в БД.
#
# Usage Examples:
#   Python API:
#     from ssh_mcp.core.permission_manager import PermissionManager
#     pm = PermissionManager(permissions_repo, default_privilege="administrator")
#     pm.check_access("srv-01", cmd_def)
#
# File: permission_manager.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:49:00
# =============================================================================

from typing import Dict
from ..schemas.command import CommandDefinition
from ..security.authorization import AuthorizationError
from ..storage.repositories.permissions_repo import PermissionsRepository

RISK_WEIGHTS: Dict[str, int] = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


class PermissionManager:
    """Контроллер проверки прав доступа к хостам и повышения привилегий.

    Attributes:
        repo (PermissionsRepository): Репозиторий политик доступа в БД.
        default_privilege (str): Уровень привилегий по умолчанию ('standard' или 'administrator').

    Examples:
        >>> from ssh_mcp.storage.database import DatabaseManager
        >>> db = DatabaseManager(":memory:")
        >>> _ = db.initialize()
        >>> pm = PermissionManager(PermissionsRepository(db), default_privilege="administrator")
        >>> cmd = CommandDefinition(id="system.info", name="Info", category="system", risk_level="low")
        >>> pm.check_access("srv-1", cmd)
        True
    """

    def __init__(
        self, repo: PermissionsRepository, default_privilege: str = "administrator"
    ) -> None:
        """Инициализация менеджера разрешений.

        Args:
            repo (PermissionsRepository): Репозиторий таблицы `permissions`.
            default_privilege (str): Глобальный уровень привилегий по умолчанию.

        Examples:
            >>> db = DatabaseManager(":memory:")
            >>> _ = db.initialize()
            >>> pm = PermissionManager(PermissionsRepository(db))
        """
        self.repo = repo
        self.default_privilege = default_privilege

    def check_access(
        self, host_id: str, command: CommandDefinition, requested_privilege: str = ""
    ) -> bool:
        """Проверка прав на выполнение команды на целевом хосте.

        Args:
            host_id (str): Идентификатор целевого узла.
            command (CommandDefinition): Определение команды из Command Registry.
            requested_privilege (str): Запрошенный уровень привилегий (пустая строка — из конфига).

        Returns:
            bool: True, если выполнение разрешено политикой.

        Exceptions:
            AuthorizationError: При запрете категории, превышении уровня риска или нехватке привилегий.

        Examples:
            >>> db = DatabaseManager(":memory:")
            >>> _ = db.initialize()
            >>> pm = PermissionManager(PermissionsRepository(db), default_privilege="standard")
            >>> cmd = CommandDefinition(id="win.stop", name="Stop", category="services", privilege="administrator", risk_level="high")
            >>> try:
            ...     pm.check_access("h1", cmd)
            ... except AuthorizationError:
            ...     print("denied")
            denied
        """
        effective_priv = requested_privilege or self.default_privilege
        policy = self.repo.get_host_policy(host_id)

        if policy:
            allowed_cats = policy.get("allowed_categories", ["*"])
            if isinstance(allowed_cats, list) and "*" not in allowed_cats:
                if command.category not in allowed_cats:
                    raise AuthorizationError(
                        f"Категория '{command.category}' запрещена политикой доступа для узла '{host_id}'"
                    )

            max_risk = str(policy.get("max_risk_level", "critical"))
            if RISK_WEIGHTS.get(command.risk_level, 4) > RISK_WEIGHTS.get(max_risk, 4):
                raise AuthorizationError(
                    f"Уровень риска команды '{command.id}' ({command.risk_level}) превышает "
                    f"максимально разрешённый политикой ({max_risk}) для узла '{host_id}'"
                )

            allow_elevation = bool(policy.get("allow_privilege_elevation", False))
            if command.privilege == "administrator" and not allow_elevation and effective_priv != "administrator":
                raise AuthorizationError(
                    f"Команда '{command.id}' требует привилегий administrator, но повышение привилегий отключено для '{host_id}'"
                )

        if command.privilege == "administrator" and effective_priv != "administrator":
            raise AuthorizationError(
                f"Недостаточно привилегий: команда '{command.id}' требует уровня 'administrator' (текущий: '{effective_priv}')"
            )

        return True
