# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Адаптер системных журналов Linux (journalctl / syslog / auth.log)
# =============================================================================
# Description:
#   Чтение, поиск и экспорт журналов событий на платформе Linux (journalctl,
#   syslog, auth.log, kern.log) согласно разделу 4.9 ТЗ.
#
# File: logs.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.platforms.linux
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:56:15
# =============================================================================

import shlex
from typing import Any, Dict
from ...transports.base import BaseTransport
from ..base import pack_raw_result


class LinuxLogsAdapter:
    """Адаптер чтения системных журналов ОС Linux.

    Examples:
        >>> adapter = LinuxLogsAdapter()
    """

    @staticmethod
    async def logs_list(transport: BaseTransport) -> Dict[str, Any]:
        """Получение списка доступных журналов в `/var/log` и `journalctl`.

        Args:
            transport (BaseTransport): Транспорт узла.

        Returns:
            Dict[str, Any]: Список журналов в `logs`.

        Examples:
            >>> pass
        """
        raw = await transport.execute_command("ls -1 /var/log 2>/dev/null | head -n 30", shell="bash")
        files = [ln.strip() for ln in raw.stdout.splitlines() if ln.strip()]
        return pack_raw_result(raw, {"logs": ["journalctl"] + files})

    @staticmethod
    async def logs_read(
        transport: BaseTransport, log_name: str = "journalctl", limit: int = 25
    ) -> Dict[str, Any]:
        """Чтение последних записей из `journalctl` или файла `/var/log/<log_name>`.

        Args:
            transport (BaseTransport): Транспорт узла.
            log_name (str): Имя журнала ('journalctl', 'syslog', 'auth.log', 'kern.log').
            limit (int): Количество строк.

        Returns:
            Dict[str, Any]: События в ключе `events`.

        Examples:
            >>> pass
        """
        if log_name in ("journalctl", "System", "Application"):
            cmd = f"journalctl -n {int(limit)} --no-pager"
        else:
            safe_file = shlex.quote(f"/var/log/{log_name.lstrip('/')}")
            cmd = f"tail -n {int(limit)} {safe_file}"
        raw = await transport.execute_command(cmd, shell="bash")
        return pack_raw_result(raw, {"log_name": log_name, "events": raw.stdout.splitlines()})

    @staticmethod
    async def logs_search(
        transport: BaseTransport, log_name: str, query: str, limit: int = 25
    ) -> Dict[str, Any]:
        """Поиск строк в журнале Linux по шаблону.

        Args:
            transport (BaseTransport): Транспорт узла.
            log_name (str): Имя журнала.
            query (str): Поисковый запрос.
            limit (int): Лимит совпадений.

        Returns:
            Dict[str, Any]: Найденные записи в `events`.

        Examples:
            >>> pass
        """
        q_str = shlex.quote(query)
        cmd = f"journalctl --no-pager | grep -i {q_str} | tail -n {int(limit)}"
        raw = await transport.execute_command(cmd, shell="bash")
        return pack_raw_result(raw, {"log_name": log_name, "query": query, "events": raw.stdout.splitlines()})

    @staticmethod
    async def logs_recent_errors(
        transport: BaseTransport, limit: int = 20
    ) -> Dict[str, Any]:
        """Получение последних ошибок (`journalctl -p err`).

        Args:
            transport (BaseTransport): Транспорт узла.
            limit (int): Максимальное количество записей.

        Returns:
            Dict[str, Any]: Ошибки в ключе `errors`.

        Examples:
            >>> pass
        """
        raw = await transport.execute_command(
            f"journalctl -p err -n {int(limit)} --no-pager", shell="bash"
        )
        return pack_raw_result(raw, {"errors": raw.stdout.splitlines()})
