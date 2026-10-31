# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Адаптер управления пользователями и группами Windows
# =============================================================================
# Description:
#   Операции управления локальными учётными записями и группами Windows
#   (user_list, user_get, user_create, user_modify, user_disable, user_delete,
#   user_groups, user_group_add, user_group_remove). Пароли передаются строго
#   через CredentialManager по ссылке `credential_ref` без появления в ответах
#   и журналах (Раздел 4.8 ТЗ).
#
# File: users.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.platforms.windows
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:53:45
# =============================================================================

from typing import Any, Dict
from ...security.credentials import CredentialManager
from ...transports.base import BaseTransport
from .executor import WindowsExecutor


class WindowsUserAdapter:
    """Адаптер управления локальными пользователями и группами ОС Windows.

    Examples:
        >>> adapter = WindowsUserAdapter()
    """

    @staticmethod
    def _quote(val: str) -> str:
        """Экранирование строки для PowerShell.

        Args:
            val (str): Исходная строка.

        Returns:
            str: Экранированная строка.

        Examples:
            >>> WindowsUserAdapter._quote("admin")
            'admin'
        """
        return str(val).replace("'", "''")

    @staticmethod
    async def user_list(transport: BaseTransport) -> Dict[str, Any]:
        """Получение списка локальных пользователей Windows.

        Args:
            transport (BaseTransport): Транспорт узла.

        Returns:
            Dict[str, Any]: Список пользователей в ключе `users`.

        Examples:
            >>> pass
        """
        ps = "Get-LocalUser | Select-Object Name, Enabled, Description | ConvertTo-Json -Compress"
        res = await WindowsExecutor.run_ps_json(transport, ps)
        return {"users": res.get("items", [res] if "Name" in res else [])}

    @staticmethod
    async def user_get(transport: BaseTransport, username: str) -> Dict[str, Any]:
        """Получение сведений о конкретном пользователе Windows.

        Args:
            transport (BaseTransport): Транспорт узла.
            username (str): Имя пользователя.

        Returns:
            Dict[str, Any]: Метаданные учётной записи.

        Examples:
            >>> pass
        """
        q = WindowsUserAdapter._quote(username)
        ps = f"Get-LocalUser -Name '{q}' -ErrorAction Stop | Select-Object Name, Enabled, SID, Description | ConvertTo-Json -Compress"
        return await WindowsExecutor.run_ps_json(transport, ps)

    @staticmethod
    async def user_create(
        transport: BaseTransport,
        cred_mgr: CredentialManager,
        username: str,
        credential_ref: str,
        description: str = "",
    ) -> Dict[str, Any]:
        """Создание пользователя Windows с разрешением пароля через CredentialManager.

        Args:
            transport (BaseTransport): Транспорт узла.
            cred_mgr (CredentialManager): Менеджер секретов.
            username (str): Имя создаваемого пользователя.
            credential_ref (str): Ссылка на секрет пароля.
            description (str): Описание учётной записи.

        Returns:
            Dict[str, Any]: Статус создания без возврата пароля.

        Exceptions:
            ValueError: Если секрет по `credential_ref` не найден.

        Examples:
            >>> pass
        """
        secret_pwd = cred_mgr.resolve_secret(credential_ref)
        if not secret_pwd:
            raise ValueError(f"Не удалось разрешить пароль по ссылке credential_ref='{credential_ref}'")
        q_user = WindowsUserAdapter._quote(username)
        q_desc = WindowsUserAdapter._quote(description)
        q_pwd = WindowsUserAdapter._quote(secret_pwd)
        ps = (
            f"$sec = ConvertTo-SecureString '{q_pwd}' -AsPlainText -Force; "
            f"New-LocalUser -Name '{q_user}' -Password $sec -Description '{q_desc}' -ErrorAction Stop | Out-Null; "
            f"@{{username='{q_user}'; created=$true}} | ConvertTo-Json -Compress"
        )
        return await WindowsExecutor.run_ps_json(transport, ps)

    @staticmethod
    async def user_modify(
        transport: BaseTransport, username: str, description: str = ""
    ) -> Dict[str, Any]:
        """Изменение параметров учётной записи пользователя Windows.

        Args:
            transport (BaseTransport): Транспорт узла.
            username (str): Имя пользователя.
            description (str): Новое описание.

        Returns:
            Dict[str, Any]: Статус модификации.

        Examples:
            >>> pass
        """
        q_user = WindowsUserAdapter._quote(username)
        q_desc = WindowsUserAdapter._quote(description)
        ps = f"Set-LocalUser -Name '{q_user}' -Description '{q_desc}' -ErrorAction Stop; @{{username='{q_user}'; modified=$true}} | ConvertTo-Json -Compress"
        return await WindowsExecutor.run_ps_json(transport, ps)

    @staticmethod
    async def user_disable(transport: BaseTransport, username: str) -> Dict[str, Any]:
        """Отключение учётной записи пользователя Windows.

        Args:
            transport (BaseTransport): Транспорт узла.
            username (str): Имя пользователя.

        Returns:
            Dict[str, Any]: Статус отключения.

        Examples:
            >>> pass
        """
        q = WindowsUserAdapter._quote(username)
        ps = f"Disable-LocalUser -Name '{q}' -ErrorAction Stop; @{{username='{q}'; enabled=$false}} | ConvertTo-Json -Compress"
        return await WindowsExecutor.run_ps_json(transport, ps)

    @staticmethod
    async def user_delete(transport: BaseTransport, username: str) -> Dict[str, Any]:
        """Удаление учётной записи пользователя Windows (уровень риска critical).

        Args:
            transport (BaseTransport): Транспорт узла.
            username (str): Имя удаляемого пользователя.

        Returns:
            Dict[str, Any]: Подтверждение удаления.

        Examples:
            >>> pass
        """
        q = WindowsUserAdapter._quote(username)
        ps = f"Remove-LocalUser -Name '{q}' -ErrorAction Stop; @{{username='{q}'; deleted=$true}} | ConvertTo-Json -Compress"
        return await WindowsExecutor.run_ps_json(transport, ps)

    @staticmethod
    async def user_groups(transport: BaseTransport, username: str) -> Dict[str, Any]:
        """Получение списка локальных групп, в которых состоит пользователь.

        Args:
            transport (BaseTransport): Транспорт узла.
            username (str): Имя пользователя.

        Returns:
            Dict[str, Any]: Список групп пользователя.

        Examples:
            >>> pass
        """
        q = WindowsUserAdapter._quote(username)
        ps = (
            "$g = Get-LocalGroup | Where-Object { (Get-LocalGroupMember -Group $_.Name -ErrorAction SilentlyContinue).Name -match '"
            + q
            + "' } | Select-Object -ExpandProperty Name; @{username='"
            + q
            + "'; groups=@($g)} | ConvertTo-Json -Compress"
        )
        return await WindowsExecutor.run_ps_json(transport, ps)

    @staticmethod
    async def user_group_add(
        transport: BaseTransport, username: str, group: str
    ) -> Dict[str, Any]:
        """Добавление пользователя в локальную группу Windows.

        Args:
            transport (BaseTransport): Транспорт узла.
            username (str): Имя пользователя.
            group (str): Имя группы.

        Returns:
            Dict[str, Any]: Статус добавления.

        Examples:
            >>> pass
        """
        q_u = WindowsUserAdapter._quote(username)
        q_g = WindowsUserAdapter._quote(group)
        ps = f"Add-LocalGroupMember -Group '{q_g}' -Member '{q_u}' -ErrorAction Stop; @{{username='{q_u}'; group='{q_g}'; added=$true}} | ConvertTo-Json -Compress"
        return await WindowsExecutor.run_ps_json(transport, ps)

    @staticmethod
    async def user_group_remove(
        transport: BaseTransport, username: str, group: str
    ) -> Dict[str, Any]:
        """Удаление пользователя из локальной группы Windows.

        Args:
            transport (BaseTransport): Транспорт узла.
            username (str): Имя пользователя.
            group (str): Имя группы.

        Returns:
            Dict[str, Any]: Статус удаления из группы.

        Examples:
            >>> pass
        """
        q_u = WindowsUserAdapter._quote(username)
        q_g = WindowsUserAdapter._quote(group)
        ps = f"Remove-LocalGroupMember -Group '{q_g}' -Member '{q_u}' -ErrorAction Stop; @{{username='{q_u}'; group='{q_g}'; removed=$true}} | ConvertTo-Json -Compress"
        return await WindowsExecutor.run_ps_json(transport, ps)
