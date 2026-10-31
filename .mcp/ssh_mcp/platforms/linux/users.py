# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Адаптер управления пользователями и группами Linux
# =============================================================================
# Description:
#   Операции управления пользователями и группами на платформе Linux
#   (user_list, user_get, user_create, user_modify, user_disable, user_delete,
#   user_groups, user_group_add, user_group_remove) с безопасной передачей
#   паролей через CredentialManager (Раздел 4.8 ТЗ).
#
# File: users.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.platforms.linux
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:56:00
# =============================================================================

import shlex
from typing import Any, Dict, List
from ...security.credentials import CredentialManager
from ...transports.base import BaseTransport
from ..base import pack_raw_result


class LinuxUserAdapter:
    """Адаптер управления пользователями и группами ОС Linux.

    Examples:
        >>> adapter = LinuxUserAdapter()
    """

    @staticmethod
    async def user_list(transport: BaseTransport) -> Dict[str, Any]:
        """Чтение списка пользователей из `/etc/passwd`.

        Args:
            transport (BaseTransport): Транспорт узла.

        Returns:
            Dict[str, Any]: Список пользователей в `users`.

        Examples:
            >>> pass
        """
        raw = await transport.execute_command("cat /etc/passwd", shell="bash")
        users: List[Dict[str, Any]] = []
        for ln in raw.stdout.splitlines():
            parts = ln.split(":")
            if len(parts) >= 7:
                users.append({"username": parts[0], "uid": int(parts[2]), "home": parts[5], "shell": parts[6]})
        return pack_raw_result(raw, {"users": users})

    @staticmethod
    async def user_get(transport: BaseTransport, username: str) -> Dict[str, Any]:
        """Получение информации о пользователе Linux (`id`).

        Args:
            transport (BaseTransport): Транспорт узла.
            username (str): Имя пользователя.

        Returns:
            Dict[str, Any]: Детали пользователя.

        Examples:
            >>> pass
        """
        q = shlex.quote(username)
        raw = await transport.execute_command(f"id {q}", shell="bash")
        return pack_raw_result(raw, {"username": username, "id_info": raw.stdout})

    @staticmethod
    async def user_create(
        transport: BaseTransport,
        cred_mgr: CredentialManager,
        username: str,
        credential_ref: str,
    ) -> Dict[str, Any]:
        """Создание пользователя Linux и установка пароля по ссылке `credential_ref`.

        Args:
            transport (BaseTransport): Транспорт узла.
            cred_mgr (CredentialManager): Менеджер секретов.
            username (str): Имя пользователя.
            credential_ref (str): Ссылка на секрет пароля.

        Returns:
            Dict[str, Any]: Статус создания без раскрытия пароля.

        Examples:
            >>> pass
        """
        pwd = cred_mgr.resolve_secret(credential_ref)
        if not pwd:
            raise ValueError(f"Не найден секрет пароля по ссылке '{credential_ref}'")
        q_u = shlex.quote(username)
        q_pair = shlex.quote(f"{username}:{pwd}")
        raw = await transport.execute_command(
            f"useradd -m {q_u} && printf '%s\\n' {q_pair} | chpasswd",
            shell="bash",
            elevate=True,
        )
        return pack_raw_result(raw, {"username": username, "created": raw.exit_code == 0})

    @staticmethod
    async def user_modify(
        transport: BaseTransport, username: str, shell_path: str = "/bin/bash"
    ) -> Dict[str, Any]:
        """Модификация параметров пользователя Linux (`usermod`)."""
        q_u = shlex.quote(username)
        q_s = shlex.quote(shell_path)
        raw = await transport.execute_command(f"usermod -s {q_s} {q_u}", shell="bash", elevate=True)
        return pack_raw_result(raw, {"username": username, "modified": raw.exit_code == 0})

    @staticmethod
    async def user_disable(transport: BaseTransport, username: str) -> Dict[str, Any]:
        """Блокировка учётной записи пользователя Linux (`usermod -L`)."""
        q_u = shlex.quote(username)
        raw = await transport.execute_command(f"usermod -L {q_u}", shell="bash", elevate=True)
        return pack_raw_result(raw, {"username": username, "disabled": raw.exit_code == 0})

    @staticmethod
    async def user_delete(transport: BaseTransport, username: str) -> Dict[str, Any]:
        """Удаление пользователя Linux (`userdel -r`)."""
        q_u = shlex.quote(username)
        raw = await transport.execute_command(f"userdel -r {q_u}", shell="bash", elevate=True)
        return pack_raw_result(raw, {"username": username, "deleted": raw.exit_code == 0})

    @staticmethod
    async def user_groups(transport: BaseTransport, username: str) -> Dict[str, Any]:
        """Получение групп пользователя Linux (`groups`)."""
        q_u = shlex.quote(username)
        raw = await transport.execute_command(f"groups {q_u}", shell="bash")
        return pack_raw_result(raw, {"username": username, "groups": raw.stdout.split()})

    @staticmethod
    async def user_group_add(
        transport: BaseTransport, username: str, group: str
    ) -> Dict[str, Any]:
        """Добавление пользователя в группу Linux (`usermod -aG`)."""
        q_u = shlex.quote(username)
        q_g = shlex.quote(group)
        raw = await transport.execute_command(f"usermod -aG {q_g} {q_u}", shell="bash", elevate=True)
        return pack_raw_result(raw, {"username": username, "group": group, "added": raw.exit_code == 0})

    @staticmethod
    async def user_group_remove(
        transport: BaseTransport, username: str, group: str
    ) -> Dict[str, Any]:
        """Удаление пользователя из группы Linux (`gpasswd -d`)."""
        q_u = shlex.quote(username)
        q_g = shlex.quote(group)
        raw = await transport.execute_command(f"gpasswd -d {q_u} {q_g}", shell="bash", elevate=True)
        return pack_raw_result(raw, {"username": username, "group": group, "removed": raw.exit_code == 0})
