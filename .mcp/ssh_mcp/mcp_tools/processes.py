# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: MCP-инструменты управления процессами (Process Management)
# =============================================================================
# Description:
#   Реализация группы инструментов 4.4 ТЗ:
#   process_list, process_get, process_start, process_stop, process_tree,
#   process_resource_usage.
#
# File: processes.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.mcp_tools
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:58:45
# =============================================================================

from typing import Any, Dict, List
from mcp.server import MCPServer
from ..bootstrap import SSHMCPRuntime
from ..platforms.linux.processes import LinuxProcessAdapter
from ..platforms.windows.processes import WindowsProcessAdapter
from ..transports.base import BaseTransport


class ProcessToolsModule:
    """Модуль инструментов управления процессами (Раздел 4.4 ТЗ)."""

    def __init__(self, runtime: SSHMCPRuntime) -> None:
        """Инициализация модуля процессов."""
        self.rt = runtime

    async def process_list(self, host_id: str = "localhost", limit: int = 50) -> Dict[str, Any]:
        """Список запущенных процессов с PID, PPID, CPU и RAM."""
        async def _h(tr: BaseTransport, plat: str, _p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxProcessAdapter.process_list(tr, limit)
            return await WindowsProcessAdapter.process_list(tr, limit)

        return await self.rt.engine.dispatch(host_id, "process.list", {"limit": limit}, _h)

    async def process_get(self, host_id: str, pid: int) -> Dict[str, Any]:
        """Детальные сведения о процессе по его PID."""
        async def _h(tr: BaseTransport, plat: str, p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxProcessAdapter.process_get(tr, int(p["pid"]))
            return await WindowsProcessAdapter.process_get(tr, int(p["pid"]))

        return await self.rt.engine.dispatch(host_id, "process.get", {"pid": pid}, _h)

    async def process_start(
        self, host_id: str, executable: str, arguments: List[str] = []
    ) -> Dict[str, Any]:
        """Запуск нового процесса на целевом узле."""
        async def _h(tr: BaseTransport, plat: str, p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxProcessAdapter.process_start(tr, str(p["executable"]), list(p.get("arguments", [])))
            return await WindowsProcessAdapter.process_start(tr, str(p["executable"]), list(p.get("arguments", [])))

        return await self.rt.engine.dispatch(
            host_id, "process.start", {"executable": executable, "arguments": arguments}, _h
        )

    async def process_stop(
        self, host_id: str, pid: int, approval_id: str = ""
    ) -> Dict[str, Any]:
        """Остановка процесса по PID (требует подтверждения high-risk)."""
        async def _h(tr: BaseTransport, plat: str, p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxProcessAdapter.process_stop(tr, int(p["pid"]))
            return await WindowsProcessAdapter.process_stop(tr, int(p["pid"]))

        return await self.rt.engine.dispatch(
            host_id, "process.stop", {"pid": pid}, _h, approval_id=approval_id
        )

    async def process_tree(self, host_id: str = "localhost", limit: int = 50) -> Dict[str, Any]:
        """Дерево родительских и дочерних процессов."""
        async def _h(tr: BaseTransport, plat: str, _p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxProcessAdapter.process_tree(tr, limit)
            return await WindowsProcessAdapter.process_tree(tr, limit)

        return await self.rt.engine.dispatch(host_id, "process.tree", {"limit": limit}, _h)

    async def process_resource_usage(
        self, host_id: str = "localhost", top_n: int = 10
    ) -> Dict[str, Any]:
        """Топ процессов по потреблению ресурсов."""
        async def _h(tr: BaseTransport, plat: str, _p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxProcessAdapter.process_resource_usage(tr, top_n)
            return await WindowsProcessAdapter.process_resource_usage(tr, top_n)

        return await self.rt.engine.dispatch(host_id, "process.resource_usage", {"top_n": top_n}, _h)


def register_process_tools(mcp: MCPServer, runtime: SSHMCPRuntime) -> ProcessToolsModule:
    """Регистрация 6 инструментов управления процессами в MCPServer."""
    mod = ProcessToolsModule(runtime)

    @mcp.tool(name="process_list", description="Получение списка процессов узла")
    async def process_list(host_id: str = "localhost", limit: int = 50) -> Dict[str, Any]:
        return await mod.process_list(host_id, limit)

    @mcp.tool(name="process_get", description="Получение сведений о процессе по PID")
    async def process_get(host_id: str, pid: int) -> Dict[str, Any]:
        return await mod.process_get(host_id, pid)

    @mcp.tool(name="process_start", description="Запуск процесса на узле")
    async def process_start(host_id: str, executable: str, arguments: List[str] = []) -> Dict[str, Any]:
        return await mod.process_start(host_id, executable, arguments)

    @mcp.tool(name="process_stop", description="Принудительная остановка процесса по PID")
    async def process_stop(host_id: str, pid: int, approval_id: str = "") -> Dict[str, Any]:
        return await mod.process_stop(host_id, pid, approval_id)

    @mcp.tool(name="process_tree", description="Дерево процессов с родительскими связями PPID")
    async def process_tree(host_id: str = "localhost", limit: int = 50) -> Dict[str, Any]:
        return await mod.process_tree(host_id, limit)

    @mcp.tool(name="process_resource_usage", description="Топ процессов по потреблению памяти и CPU")
    async def process_resource_usage(host_id: str = "localhost", top_n: int = 10) -> Dict[str, Any]:
        return await mod.process_resource_usage(host_id, top_n)

    return mod
