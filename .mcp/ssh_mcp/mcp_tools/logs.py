# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: MCP-инструменты управления журналами и событиями (Event & Log)
# =============================================================================
# Description:
#   Реализация группы инструментов 4.9 ТЗ:
#   logs_list, logs_read, logs_search, logs_export, logs_recent_errors
#   для Windows Event Log и Linux journalctl / syslog / auth.log / kern.log.
#
# File: logs.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.mcp_tools
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 17:00:00
# =============================================================================

from typing import Any, Dict
from mcp.server import MCPServer
from ..bootstrap import SSHMCPRuntime
from ..platforms.linux.logs import LinuxLogsAdapter
from ..platforms.windows.events import WindowsEventsAdapter
from ..transports.base import BaseTransport


class LogsToolsModule:
    """Модуль инструментов работы с системными журналами (Раздел 4.9 ТЗ)."""

    def __init__(self, runtime: SSHMCPRuntime) -> None:
        """Инициализация модуля журналов."""
        self.rt = runtime

    async def logs_list(self, host_id: str = "localhost") -> Dict[str, Any]:
        """Список доступных системных журналов."""
        async def _h(tr: BaseTransport, plat: str, _p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxLogsAdapter.logs_list(tr)
            return await WindowsEventsAdapter.logs_list(tr)

        return await self.rt.engine.dispatch(host_id, "logs.list", {}, _h)

    async def logs_read(
        self, host_id: str, log_name: str = "System", limit: int = 25
    ) -> Dict[str, Any]:
        """Чтение последних записей из указанного журнала."""
        async def _h(tr: BaseTransport, plat: str, p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxLogsAdapter.logs_read(tr, str(p["log_name"]), int(p.get("limit", 25)))
            return await WindowsEventsAdapter.logs_read(tr, str(p["log_name"]), int(p.get("limit", 25)))

        return await self.rt.engine.dispatch(
            host_id, "logs.read", {"log_name": log_name, "limit": limit}, _h
        )

    async def logs_search(
        self, host_id: str, log_name: str, query: str, limit: int = 25
    ) -> Dict[str, Any]:
        """Поиск событий в журнале по подстроке или шаблону."""
        async def _h(tr: BaseTransport, plat: str, p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxLogsAdapter.logs_search(
                    tr, str(p["log_name"]), str(p["query"]), int(p.get("limit", 25))
                )
            return await WindowsEventsAdapter.logs_search(
                tr, str(p["log_name"]), str(p["query"]), int(p.get("limit", 25))
            )

        return await self.rt.engine.dispatch(
            host_id,
            "logs.search",
            {"log_name": log_name, "query": query, "limit": limit},
            _h,
        )

    async def logs_export(
        self, host_id: str, log_name: str = "System", limit: int = 50
    ) -> Dict[str, Any]:
        """Экспорт записей журнала в структурированный JSON-пакет."""
        async def _h(tr: BaseTransport, plat: str, p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                data = await LinuxLogsAdapter.logs_read(tr, str(p["log_name"]), int(p.get("limit", 50)))
            else:
                data = await WindowsEventsAdapter.logs_read(tr, str(p["log_name"]), int(p.get("limit", 50)))
            data["exported"] = True
            return data

        return await self.rt.engine.dispatch(
            host_id, "logs.export", {"log_name": log_name, "limit": limit}, _h
        )

    async def logs_recent_errors(
        self, host_id: str = "localhost", limit: int = 20
    ) -> Dict[str, Any]:
        """Получение последних критических ошибок из системных журналов."""
        async def _h(tr: BaseTransport, plat: str, _p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxLogsAdapter.logs_recent_errors(tr, limit)
            return await WindowsEventsAdapter.logs_recent_errors(tr, limit)

        return await self.rt.engine.dispatch(host_id, "logs.recent_errors", {"limit": limit}, _h)


def register_logs_tools(mcp: MCPServer, runtime: SSHMCPRuntime) -> LogsToolsModule:
    """Регистрация 5 инструментов работы с журналами в MCPServer."""
    mod = LogsToolsModule(runtime)

    @mcp.tool(name="logs_list", description="Список системных журналов (Event Log / journalctl)")
    async def logs_list(host_id: str = "localhost") -> Dict[str, Any]:
        return await mod.logs_list(host_id)

    @mcp.tool(name="logs_read", description="Чтение последних записей системного журнала")
    async def logs_read(host_id: str, log_name: str = "System", limit: int = 25) -> Dict[str, Any]:
        return await mod.logs_read(host_id, log_name, limit)

    @mcp.tool(name="logs_search", description="Поиск событий в журнале по ключевому слову")
    async def logs_search(
        host_id: str, log_name: str, query: str, limit: int = 25
    ) -> Dict[str, Any]:
        return await mod.logs_search(host_id, log_name, query, limit)

    @mcp.tool(name="logs_export", description="Экспорт записей системного журнала")
    async def logs_export(host_id: str, log_name: str = "System", limit: int = 50) -> Dict[str, Any]:
        return await mod.logs_export(host_id, log_name, limit)

    @mcp.tool(name="logs_recent_errors", description="Последние ошибки из системных журналов")
    async def logs_recent_errors(host_id: str = "localhost", limit: int = 20) -> Dict[str, Any]:
        return await mod.logs_recent_errors(host_id, limit)

    return mod
