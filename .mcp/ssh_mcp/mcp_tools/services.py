# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: MCP-инструменты управления службами (Service Management)
# =============================================================================
# Description:
#   Реализация группы инструментов 4.5 ТЗ:
#   service_list, service_status, service_start, service_stop, service_restart,
#   service_enable, service_disable для Windows (SCM) и Linux (systemd/init).
#
# File: services.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.mcp_tools
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:59:00
# =============================================================================

from typing import Any, Dict
from mcp.server import MCPServer
from ..bootstrap import SSHMCPRuntime
from ..platforms.linux.services import LinuxServiceAdapter
from ..platforms.windows.services import WindowsServiceAdapter
from ..transports.base import BaseTransport


class ServiceToolsModule:
    """Модуль инструментов управления службами Windows и Linux (Раздел 4.5 ТЗ)."""

    def __init__(self, runtime: SSHMCPRuntime) -> None:
        """Инициализация модуля служб."""
        self.rt = runtime

    async def service_list(self, host_id: str = "localhost", limit: int = 50) -> Dict[str, Any]:
        """Список системных служб узла."""
        async def _h(tr: BaseTransport, plat: str, _p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxServiceAdapter.service_list(tr, limit)
            return await WindowsServiceAdapter.service_list(tr, limit)

        return await self.rt.engine.dispatch(host_id, "service.list", {"limit": limit}, _h)

    async def service_status(self, host_id: str, service_name: str) -> Dict[str, Any]:
        """Состояние конкретной службы."""
        async def _h(tr: BaseTransport, plat: str, p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxServiceAdapter.service_status(tr, str(p["service_name"]))
            return await WindowsServiceAdapter.service_status(tr, str(p["service_name"]))

        return await self.rt.engine.dispatch(
            host_id, "service.status", {"service_name": service_name}, _h
        )

    async def service_start(self, host_id: str, service_name: str) -> Dict[str, Any]:
        """Запуск службы."""
        async def _h(tr: BaseTransport, plat: str, p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxServiceAdapter.service_start(tr, str(p["service_name"]))
            return await WindowsServiceAdapter.service_start(tr, str(p["service_name"]))

        return await self.rt.engine.dispatch(
            host_id, "service.start", {"service_name": service_name}, _h
        )

    async def service_stop(
        self, host_id: str, service_name: str, approval_id: str = ""
    ) -> Dict[str, Any]:
        """Остановка службы (требует подтверждения high-risk)."""
        async def _h(tr: BaseTransport, plat: str, p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxServiceAdapter.service_stop(tr, str(p["service_name"]))
            return await WindowsServiceAdapter.service_stop(tr, str(p["service_name"]))

        return await self.rt.engine.dispatch(
            host_id, "service.stop", {"service_name": service_name}, _h, approval_id=approval_id
        )

    async def service_restart(
        self, host_id: str, service_name: str, approval_id: str = ""
    ) -> Dict[str, Any]:
        """Перезапуск службы (требует подтверждения high-risk)."""
        async def _h(tr: BaseTransport, plat: str, p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxServiceAdapter.service_restart(tr, str(p["service_name"]))
            return await WindowsServiceAdapter.service_restart(tr, str(p["service_name"]))

        return await self.rt.engine.dispatch(
            host_id, "service.restart", {"service_name": service_name}, _h, approval_id=approval_id
        )

    async def service_enable(
        self, host_id: str, service_name: str, approval_id: str = ""
    ) -> Dict[str, Any]:
        """Включение автозапуска службы."""
        async def _h(tr: BaseTransport, plat: str, p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxServiceAdapter.service_enable(tr, str(p["service_name"]))
            return await WindowsServiceAdapter.service_enable(tr, str(p["service_name"]))

        return await self.rt.engine.dispatch(
            host_id, "service.enable", {"service_name": service_name}, _h, approval_id=approval_id
        )

    async def service_disable(
        self, host_id: str, service_name: str, approval_id: str = ""
    ) -> Dict[str, Any]:
        """Отключение автозапуска службы."""
        async def _h(tr: BaseTransport, plat: str, p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxServiceAdapter.service_disable(tr, str(p["service_name"]))
            return await WindowsServiceAdapter.service_disable(tr, str(p["service_name"]))

        return await self.rt.engine.dispatch(
            host_id, "service.disable", {"service_name": service_name}, _h, approval_id=approval_id
        )


def register_service_tools(mcp: MCPServer, runtime: SSHMCPRuntime) -> ServiceToolsModule:
    """Регистрация 7 инструментов управления службами в MCPServer."""
    mod = ServiceToolsModule(runtime)

    @mcp.tool(name="service_list", description="Список системных служб узла")
    async def service_list(host_id: str = "localhost", limit: int = 50) -> Dict[str, Any]:
        return await mod.service_list(host_id, limit)

    @mcp.tool(name="service_status", description="Проверка состояния службы")
    async def service_status(host_id: str, service_name: str) -> Dict[str, Any]:
        return await mod.service_status(host_id, service_name)

    @mcp.tool(name="service_start", description="Запуск системной службы")
    async def service_start(host_id: str, service_name: str) -> Dict[str, Any]:
        return await mod.service_start(host_id, service_name)

    @mcp.tool(name="service_stop", description="Остановка системной службы (требует подтверждения)")
    async def service_stop(host_id: str, service_name: str, approval_id: str = "") -> Dict[str, Any]:
        return await mod.service_stop(host_id, service_name, approval_id)

    @mcp.tool(name="service_restart", description="Перезапуск системной службы (требует подтверждения)")
    async def service_restart(host_id: str, service_name: str, approval_id: str = "") -> Dict[str, Any]:
        return await mod.service_restart(host_id, service_name, approval_id)

    @mcp.tool(name="service_enable", description="Включение автозапуска службы")
    async def service_enable(host_id: str, service_name: str, approval_id: str = "") -> Dict[str, Any]:
        return await mod.service_enable(host_id, service_name, approval_id)

    @mcp.tool(name="service_disable", description="Отключение автозапуска службы")
    async def service_disable(host_id: str, service_name: str, approval_id: str = "") -> Dict[str, Any]:
        return await mod.service_disable(host_id, service_name, approval_id)

    return mod
