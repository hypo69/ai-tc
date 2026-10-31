# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Адаптер сетевого управления Windows (NetTCPIP / NetSecurity)
# =============================================================================
# Description:
#   Реализация сетевых инструментов Windows: network_interfaces, network_routes,
#   network_connections, network_dns, network_ping, network_port_check и
#   network_firewall_status (Раздел 4.7 ТЗ).
#
# File: network.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.platforms.windows
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:53:30
# =============================================================================

import asyncio
import socket
import time
from typing import Any, Dict, List
import psutil

from ...transports.base import BaseTransport
from ...transports.local_transport import LocalTransport
from .executor import WindowsExecutor


class WindowsNetworkAdapter:
    """Адаптер диагностики и мониторинга сети ОС Windows.

    Examples:
        >>> adapter = WindowsNetworkAdapter()
    """

    @staticmethod
    async def network_interfaces(transport: BaseTransport) -> Dict[str, Any]:
        """Получение списка сетевых интерфейсов и их IP-адресов.

        Args:
            transport (BaseTransport): Транспорт узла.

        Returns:
            Dict[str, Any]: Список интерфейсов в ключе `interfaces`.

        Examples:
            >>> pass
        """
        if isinstance(transport, LocalTransport):
            addrs = psutil.net_if_addrs()
            interfaces: List[Dict[str, Any]] = []
            for iface_name, snic_list in addrs.items():
                ips = [s.address for s in snic_list if s.family in (socket.AF_INET, socket.AF_INET6)]
                interfaces.append({"name": iface_name, "addresses": ips})
            return {"interfaces": interfaces}

        ps = (
            "Get-NetIPAddress | Select-Object @{N='name';E={$_.InterfaceAlias}}, "
            "@{N='address';E={$_.IPAddress}} | ConvertTo-Json -Compress"
        )
        res = await WindowsExecutor.run_ps_json(transport, ps)
        return {"interfaces": res.get("items", [res] if "name" in res else [])}

    @staticmethod
    async def network_routes(transport: BaseTransport) -> Dict[str, Any]:
        """Получение таблицы маршрутизации Windows (Get-NetRoute).

        Args:
            transport (BaseTransport): Транспорт узла.

        Returns:
            Dict[str, Any]: Список маршрутов в `routes`.

        Examples:
            >>> pass
        """
        ps = (
            "Get-NetRoute -AddressFamily IPv4 | Select-Object -First 30 "
            "DestinationPrefix, NextHop, RouteMetric | ConvertTo-Json -Compress"
        )
        res = await WindowsExecutor.run_ps_json(transport, ps)
        return {"routes": res.get("items", [res] if "DestinationPrefix" in res else [])}

    @staticmethod
    async def network_connections(transport: BaseTransport, limit: int = 50) -> Dict[str, Any]:
        """Получение активных TCP-соединений и прослушиваемых портов.

        Args:
            transport (BaseTransport): Транспорт узла.
            limit (int): Лимит возвращаемых сокетов.

        Returns:
            Dict[str, Any]: Список соединений в `connections`.

        Examples:
            >>> pass
        """
        if isinstance(transport, LocalTransport):
            conns: List[Dict[str, Any]] = []
            for c in psutil.net_connections(kind="inet")[:limit]:
                laddr = f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else ""
                raddr = f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else ""
                conns.append({"local": laddr, "remote": raddr, "status": c.status, "pid": int(c.pid or 0)})
            return {"connections": conns}

        ps = (
            f"Get-NetTCPConnection | Select-Object -First {int(limit)} "
            "LocalAddress, LocalPort, RemoteAddress, RemotePort, State, OwningProcess | ConvertTo-Json -Compress"
        )
        res = await WindowsExecutor.run_ps_json(transport, ps)
        return {"connections": res.get("items", [res] if "LocalPort" in res else [])}

    @staticmethod
    async def network_dns(transport: BaseTransport) -> Dict[str, Any]:
        """Получение настроек DNS-клиента Windows.

        Args:
            transport (BaseTransport): Транспорт узла.

        Returns:
            Dict[str, Any]: Конфигурация DNS-серверов.

        Examples:
            >>> pass
        """
        ps = "Get-DnsClientServerAddress -AddressFamily IPv4 | Select-Object InterfaceAlias, ServerAddresses | ConvertTo-Json -Compress"
        res = await WindowsExecutor.run_ps_json(transport, ps)
        return {"dns_servers": res.get("items", [res] if "InterfaceAlias" in res else [])}

    @staticmethod
    async def network_ping(transport: BaseTransport, target: str) -> Dict[str, Any]:
        """Проверка сетевой доступности узла (Test-Connection).

        Args:
            transport (BaseTransport): Транспорт узла.
            target (str): Проверяемый хост или IP.

        Returns:
            Dict[str, Any]: Результат проверки (`reachable`, `target`).

        Examples:
            >>> pass
        """
        q = target.replace("'", "''")
        ps = f"$ok = Test-Connection -ComputerName '{q}' -Count 1 -Quiet; @{{target='{q}'; reachable=[bool]$ok}} | ConvertTo-Json -Compress"
        return await WindowsExecutor.run_ps_json(transport, ps)

    @staticmethod
    async def network_port_check(
        transport: BaseTransport, target: str, port: int, timeout: float = 3.0
    ) -> Dict[str, Any]:
        """Проверка доступности TCP-порта на целевом адресе.

        Args:
            transport (BaseTransport): Транспорт узла.
            target (str): Целевой IP или хост.
            port (int): Номер TCP-порта.
            timeout (float): Таймаут подключения в секундах.

        Returns:
            Dict[str, Any]: Статус открытия порта (`open`, `latency_ms`).

        Examples:
            >>> pass
        """
        if isinstance(transport, LocalTransport):
            started = time.perf_counter()
            try:
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(target, int(port)), timeout=timeout
                )
                writer.close()
                await writer.wait_closed()
                return {
                    "target": target,
                    "port": int(port),
                    "open": True,
                    "latency_ms": int((time.perf_counter() - started) * 1000),
                }
            except Exception:
                return {"target": target, "port": int(port), "open": False, "latency_ms": 0}

        q = target.replace("'", "''")
        ps = (
            f"$r = Test-NetConnection -ComputerName '{q}' -Port {int(port)} -WarningAction SilentlyContinue; "
            f"@{{target='{q}'; port={int(port)}; open=[bool]$r.TcpTestSucceeded}} | ConvertTo-Json -Compress"
        )
        return await WindowsExecutor.run_ps_json(transport, ps)

    @staticmethod
    async def network_firewall_status(transport: BaseTransport) -> Dict[str, Any]:
        """Получение статуса профилей брандмауэра Windows (NetSecurity).

        Args:
            transport (BaseTransport): Транспорт узла.

        Returns:
            Dict[str, Any]: Состояние профилей Domain, Private, Public.

        Examples:
            >>> pass
        """
        ps = "Get-NetFirewallProfile | Select-Object Name, Enabled | ConvertTo-Json -Compress"
        res = await WindowsExecutor.run_ps_json(transport, ps)
        return {"profiles": res.get("items", [res] if "Name" in res else [])}
