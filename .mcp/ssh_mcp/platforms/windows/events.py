# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Адаптер системных журналов событий Windows (Event Log)
# =============================================================================
# Description:
#   Работа с журналами Windows Event Log (System, Application, Security,
#   PowerShell Operational): logs_list, logs_read, logs_search, logs_export и
#   logs_recent_errors (Раздел 4.9 ТЗ).
#
# File: events.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.platforms.windows
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:54:00
# =============================================================================

from typing import Any, Dict
from ...transports.base import BaseTransport
from .executor import WindowsExecutor


class WindowsEventsAdapter:
    """Адаптер чтения и фильтрации журналов событий Windows Event Log.

    Examples:
        >>> adapter = WindowsEventsAdapter()
    """

    @staticmethod
    async def logs_list(transport: BaseTransport) -> Dict[str, Any]:
        """Получение списка основных каналов Windows Event Log.

        Args:
            transport (BaseTransport): Транспорт узла.

        Returns:
            Dict[str, Any]: Список журналов в ключе `logs`.

        Examples:
            >>> pass
        """
        ps = (
            "Get-WinEvent -ListLog System,Application,Security,'Microsoft-Windows-PowerShell/Operational' "
            "-ErrorAction SilentlyContinue | Select-Object LogName, RecordCount, IsEnabled | ConvertTo-Json -Compress"
        )
        res = await WindowsExecutor.run_ps_json(transport, ps)
        return {"logs": res.get("items", [res] if "LogName" in res else [])}

    @staticmethod
    async def logs_read(
        transport: BaseTransport, log_name: str = "System", limit: int = 25
    ) -> Dict[str, Any]:
        """Чтение последних записей из указанного канала журнала Windows.

        Args:
            transport (BaseTransport): Транспорт узла.
            log_name (str): Имя журнала (например, 'System' или 'Application').
            limit (int): Количество возвращаемых событий.

        Returns:
            Dict[str, Any]: События в ключе `events`.

        Examples:
            >>> pass
        """
        q = log_name.replace("'", "''")
        ps = (
            f"Get-WinEvent -LogName '{q}' -MaxEvents {int(limit)} -ErrorAction SilentlyContinue | "
            "Select-Object Id, LevelDisplayName, ProviderName, @{N='time';E={$_.TimeCreated.ToString('o')}}, Message "
            "| ConvertTo-Json -Compress"
        )
        res = await WindowsExecutor.run_ps_json(transport, ps)
        return {"log_name": log_name, "events": res.get("items", [res] if "Id" in res else [])}

    @staticmethod
    async def logs_search(
        transport: BaseTransport, log_name: str, query: str, limit: int = 25
    ) -> Dict[str, Any]:
        """Поиск событий в журнале Windows по подстроке сообщения.

        Args:
            transport (BaseTransport): Транспорт узла.
            log_name (str): Имя журнала.
            query (str): Поисковая строка.
            limit (int): Максимальное количество совпадений.

        Returns:
            Dict[str, Any]: Найденные события.

        Examples:
            >>> pass
        """
        q_log = log_name.replace("'", "''")
        q_str = query.replace("'", "''")
        ps = (
            f"Get-WinEvent -LogName '{q_log}' -MaxEvents 200 -ErrorAction SilentlyContinue | "
            f"Where-Object {{ $_.Message -match '{q_str}' }} | Select-Object -First {int(limit)} "
            "Id, LevelDisplayName, ProviderName, Message | ConvertTo-Json -Compress"
        )
        res = await WindowsExecutor.run_ps_json(transport, ps)
        return {"log_name": log_name, "query": query, "events": res.get("items", [res] if "Id" in res else [])}

    @staticmethod
    async def logs_recent_errors(
        transport: BaseTransport, limit: int = 20
    ) -> Dict[str, Any]:
        """Получение последних критических и обычных ошибок (Level 1 и 2) из System и Application.

        Args:
            transport (BaseTransport): Транспорт узла.
            limit (int): Максимальное количество ошибок.

        Returns:
            Dict[str, Any]: Список ошибок в ключе `errors`.

        Examples:
            >>> pass
        """
        ps = (
            f"Get-WinEvent -FilterHashtable @{{LogName='System','Application'; Level=1,2}} "
            f"-MaxEvents {int(limit)} -ErrorAction SilentlyContinue | "
            "Select-Object Id, LogName, ProviderName, @{N='time';E={$_.TimeCreated.ToString('o')}}, Message "
            "| ConvertTo-Json -Compress"
        )
        res = await WindowsExecutor.run_ps_json(transport, ps)
        return {"errors": res.get("items", [res] if "Id" in res else [])}
