# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: MCP-инструменты сетевой диагностики (Network Management)
# =============================================================================
# Description:
#   Реализация группы инструментов 4.7 ТЗ:
#   network_interfaces, network_routes, network_connections, network_dns,
#   network_ping, network_port_check, network_firewall_status.
#
# File: network.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.mcp_tools
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:59:30
# =============================================================================

from typing import Any, Dict
from mcp.server import MCPServer
from ..bootstrap import SSHMCPRuntime
from ..platforms.linux.network import LinuxNetworkAdapter
from ..platforms.windows.network import WindowsNetworkAdapter
from ..transports.base import BaseTransport


class NetworkToolsModule:
    """Модуль сетевого управления и диагностики (Раздел 4.7 ТЗ)."""

    def __init__(self, runtime: SSHMCPRuntime) -> None:
        """Инициализация сетевого модуля."""
        self.rt = runtime

    async def network_interfaces(self, host_id: str = "localhost") -> Dict[str, Any]:
        """Сетевые интерфейсы и назначенные IP-адреса."""
        async def _h(tr: BaseTransport, plat: str, _p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxNetworkAdapter.network_interfaces(tr)
            return await WindowsNetworkAdapter.network_interfaces(tr)

        return await self.rt.engine.dispatch(host_id, "network.interfaces", {}, _h)

    async def network_routes(self, host_id: str = "localhost") -> Dict[str, Any]:
        """Таблица сетевой маршрутизации узла."""
        async def _h(tr: BaseTransport, plat: str, _p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxNetworkAdapter.network_routes(tr)
            return await WindowsNetworkAdapter.network_routes(tr)

        return await self.rt.engine.dispatch(host_id, "network.routes", {}, _h)

    async def network_connections(
        self, host_id: str = "localhost", limit: int = 50
    ) -> Dict[str, Any]:
        """Активные сетевые соединения и открытые порты."""
        async def _h(tr: BaseTransport, plat: str, _p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxNetworkAdapter.network_connections(tr, limit)
            return await WindowsNetworkAdapter.network_connections(tr, limit)

        return await self.rt.engine.dispatch(host_id, "network.connections", {"limit": limit}, _h)

    async def network_dns(self, host_id: str = "localhost") -> Dict[str, Any]:
        """Настройки DNS-серверов узла."""
        async def _h(tr: BaseTransport, plat: str, _p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxNetworkAdapter.network_dns(tr)
            return await WindowsNetworkAdapter.network_dns(tr)

        return await self.rt.engine.dispatch(host_id, "network.dns", {}, _h)

    async def network_ping(self, host_id: str, target: str) -> Dict[str, Any]:
        """Проверка доступности удалённого адреса (ICMP Ping)."""
        async def _h(tr: BaseTransport, plat: str, p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxNetworkAdapter.network_ping(tr, str(p["target"]))
            return await WindowsNetworkAdapter.network_ping(tr, str(p["target"]))

        return await self.rt.engine.dispatch(host_id, "network.ping", {"target": target}, _h)

    async def network_port_check(
        self, host_id: str, target: str, port: int
    ) -> Dict[str, Any]:
        """Проверка открытия TCP-порта."""
        async def _h(tr: BaseTransport, plat: str, p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxNetworkAdapter.network_port_check(tr, str(p["target"]), int(p["port"]))
            return await WindowsNetworkAdapter.network_port_check(tr, str(p["target"]), int(p["port"]))

        return await self.rt.engine.dispatch(
            host_id, "network.port_check", {"target": target, "port": port}, _h
        )

    async def network_firewall_status(self, host_id: str = "localhost") -> Dict[str, Any]:
        """Состояние межсетевого экрана (Windows Firewall / nftables / iptables)."""
        async def _h(tr: BaseTransport, plat: str, _p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxNetworkAdapter.network_firewall_status(tr)
            return await WindowsNetworkAdapter.network_firewall_status(tr)

        return await self.rt.engine.dispatch(host_id, "network.firewall_status", {}, _h)


def register_network_tools(mcp: MCPServer, runtime: SSHMCPRuntime) -> NetworkToolsModule:
    """Регистрация 7 сетевых инструментов в MCPServer."""
    mod = NetworkToolsModule(runtime)

    @mcp.tool(name="network_interfaces", description="Список сетевых адаптеров и IP-адресов")
    async def network_interfaces(host_id: str = "localhost") -> Dict[str, Any]:
        return await mod.network_interfaces(host_id)

    @mcp.tool(name="network_routes", description="Таблица маршрутизации узла")
    async def network_routes(host_id: str = "localhost") -> Dict[str, Any]:
        return await mod.network_routes(host_id)

    @mcp.tool(name="network_connections", description="Активные TCP/UDP соединения и открытые сокеты")
    async def network_connections(host_id: str = "localhost", limit: int = 50) -> Dict[str, Any]:
        return await mod.network_connections(host_id, limit)

    @mcp.tool(name="network_dns", description="Конфигурация DNS-серверов")
    async def network_dns(host_id: str = "localhost") -> Dict[str, Any]:
        return await mod.network_dns(host_id)

    @mcp.tool(name="network_ping", description="Проверка сетевой доступности хоста (ICMP)")
    async def network_ping(host_id: str, target: str) -> Dict[str, Any]:
        return await mod.network_ping(host_id, target)

    @mcp.tool(name="network_port_check", description="Проверка доступности TCP-порта")
    async def network_port_check(host_id: str, target: str, port: int) -> Dict[str, Any]:
        return await mod.network_port_check(host_id, target, port)

    @mcp.tool(name="network_firewall_status", description="Статус профилей и правил межсетевого экрана")
    async def network_firewall_status(host_id: str = "localhost") -> Dict[str, Any]:
        return await mod.network_firewall_status(host_id)

    return mod
