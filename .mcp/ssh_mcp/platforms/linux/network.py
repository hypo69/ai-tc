# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Адаптер сетевого управления Linux (iproute2 / ss / nftables)
# =============================================================================
# Description:
#   Сетевые операции на платформе Linux: network_interfaces, network_routes,
#   network_connections, network_dns, network_ping, network_port_check и
#   network_firewall_status через iproute2 (`ip -j`), `ss`, `nft` / `iptables`
#   (Раздел 4.7 ТЗ).
#
# File: network.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.platforms.linux
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:55:45
# =============================================================================

import shlex
from typing import Any, Dict
from ...transports.base import BaseTransport
from ..base import pack_raw_result, safe_parse_json


class LinuxNetworkAdapter:
    """Адаптер сетевой диагностики для ОС Linux.

    Examples:
        >>> adapter = LinuxNetworkAdapter()
    """

    @staticmethod
    async def network_interfaces(transport: BaseTransport) -> Dict[str, Any]:
        """Получение списка сетевых интерфейсов через `ip -j addr`.

        Args:
            transport (BaseTransport): Транспорт узла.

        Returns:
            Dict[str, Any]: Список интерфейсов в `interfaces`.

        Examples:
            >>> pass
        """
        raw = await transport.execute_command("ip -j addr 2>/dev/null || ip addr", shell="bash")
        parsed = safe_parse_json(raw.stdout)
        return pack_raw_result(raw, {"interfaces": parsed.get("items", parsed)})

    @staticmethod
    async def network_routes(transport: BaseTransport) -> Dict[str, Any]:
        """Получение таблицы маршрутизации Linux через `ip -j route`.

        Args:
            transport (BaseTransport): Транспорт узла.

        Returns:
            Dict[str, Any]: Список маршрутов в `routes`.

        Examples:
            >>> pass
        """
        raw = await transport.execute_command("ip -j route 2>/dev/null || ip route", shell="bash")
        parsed = safe_parse_json(raw.stdout)
        return pack_raw_result(raw, {"routes": parsed.get("items", parsed)})

    @staticmethod
    async def network_connections(transport: BaseTransport, limit: int = 50) -> Dict[str, Any]:
        """Получение активных сокетов через `ss -tunap`.

        Args:
            transport (BaseTransport): Транспорт узла.
            limit (int): Максимальное количество строк.

        Returns:
            Dict[str, Any]: Соединения в `connections`.

        Examples:
            >>> pass
        """
        raw = await transport.execute_command(f"ss -tuna | head -n {int(limit)}", shell="bash")
        lines = [ln.strip() for ln in raw.stdout.splitlines()[1:] if ln.strip()]
        return pack_raw_result(raw, {"connections": lines})

    @staticmethod
    async def network_dns(transport: BaseTransport) -> Dict[str, Any]:
        """Чтение настроек DNS из `/etc/resolv.conf`.

        Args:
            transport (BaseTransport): Транспорт узла.

        Returns:
            Dict[str, Any]: Список DNS-серверов.

        Examples:
            >>> pass
        """
        raw = await transport.execute_command("cat /etc/resolv.conf", shell="bash")
        servers = [
            ln.split()[1]
            for ln in raw.stdout.splitlines()
            if ln.strip().startswith("nameserver") and len(ln.split()) >= 2
        ]
        return pack_raw_result(raw, {"dns_servers": servers})

    @staticmethod
    async def network_ping(transport: BaseTransport, target: str) -> Dict[str, Any]:
        """Проверка доступности узла через `ping -c 1`.

        Args:
            transport (BaseTransport): Транспорт узла.
            target (str): Целевой адрес.

        Returns:
            Dict[str, Any]: Статус доступности (`reachable`).

        Examples:
            >>> pass
        """
        q = shlex.quote(target)
        raw = await transport.execute_command(f"ping -c 1 -W 2 {q}", shell="bash")
        return pack_raw_result(raw, {"target": target, "reachable": raw.exit_code == 0})

    @staticmethod
    async def network_port_check(
        transport: BaseTransport, target: str, port: int
    ) -> Dict[str, Any]:
        """Проверка открытия TCP-порта с узла Linux.

        Args:
            transport (BaseTransport): Транспорт узла.
            target (str): Целевой хост.
            port (int): Порт.

        Returns:
            Dict[str, Any]: Статус порта (`open`).

        Examples:
            >>> pass
        """
        q_t = shlex.quote(target)
        raw = await transport.execute_command(
            f"timeout 3 bash -c '</dev/tcp/{q_t}/{int(port)}' >/dev/null 2>&1", shell="bash"
        )
        return pack_raw_result(raw, {"target": target, "port": int(port), "open": raw.exit_code == 0})

    @staticmethod
    async def network_firewall_status(transport: BaseTransport) -> Dict[str, Any]:
        """Проверка состояния межсетевого экрана Linux (`nftables` / `iptables` / `ufw`).

        Args:
            transport (BaseTransport): Транспорт узла.

        Returns:
            Dict[str, Any]: Сведения о правилах межсетевого экрана.

        Examples:
            >>> pass
        """
        cmd = "if command -v nft >/dev/null 2>&1; then nft list ruleset; else iptables -L -n; fi"
        raw = await transport.execute_command(cmd, shell="bash", elevate=True)
        return pack_raw_result(raw, {"firewall_output": raw.stdout})
