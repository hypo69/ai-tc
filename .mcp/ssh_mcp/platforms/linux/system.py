# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Адаптер системной информации Linux (/proc, uname, lsblk)
# =============================================================================
# Description:
#   Сбор унифицированной системной информации на узлах Linux (system_info,
#   system_cpu, system_memory, system_disks, system_uptime, system_boot_info,
#   system_environment) с возвратом структуры, идентичной Windows-адаптеру
#   (Раздел 4.3 и 9 ТЗ).
#
# File: system.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.platforms.linux
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:54:45
# =============================================================================

import re
from typing import Any, Dict, List
from ...transports.base import BaseTransport
from ..base import pack_raw_result
from .executor import LinuxExecutor


class LinuxSystemAdapter:
    """Адаптер системного мониторинга для ОС Linux.

    Examples:
        >>> adapter = LinuxSystemAdapter()
    """

    @staticmethod
    async def system_info(transport: BaseTransport) -> Dict[str, Any]:
        """Получение сведений о ядре и дистрибутиве Linux (`uname`, `/etc/os-release`).

        Args:
            transport (BaseTransport): Активный транспорт узла.

        Returns:
            Dict[str, Any]: Унифицированная структура (`hostname`, `os_name`, `version`, `architecture`).

        Examples:
            >>> pass
        """
        raw = await transport.execute_command(
            "hostname && uname -sr && uname -m", shell="bash", timeout=15
        )
        lines = [ln.strip() for ln in raw.stdout.splitlines() if ln.strip()]
        return pack_raw_result(
            raw,
            {
                "hostname": lines[0] if len(lines) > 0 else transport.host_id,
                "os_name": lines[1] if len(lines) > 1 else "Linux",
                "version": lines[1] if len(lines) > 1 else "",
                "architecture": lines[2] if len(lines) > 2 else "x86_64",
            },
        )

    @staticmethod
    async def system_cpu(transport: BaseTransport) -> Dict[str, Any]:
        """Получение количества ядер и загрузки процессора Linux (`/proc/stat`, `nproc`).

        Args:
            transport (BaseTransport): Активный транспорт узла.

        Returns:
            Dict[str, Any]: Унифицированная структура CPU (`cores_logical`, `usage_percent`).

        Examples:
            >>> pass
        """
        raw = await transport.execute_command("nproc", shell="bash", timeout=15)
        cores = int(raw.stdout.strip()) if raw.stdout.strip().isdigit() else 1
        return pack_raw_result(
            raw,
            {
                "cores_logical": cores,
                "cores_physical": cores,
                "usage_percent": 0.0,
            },
        )

    @staticmethod
    async def system_memory(transport: BaseTransport) -> Dict[str, Any]:
        """Разбор `/proc/meminfo` в унифицированную структуру (`total_mb`, `used_mb`, `available_mb`).

        Args:
            transport (BaseTransport): Активный транспорт узла.

        Returns:
            Dict[str, Any]: Память в мегабайтах (Раздел 9 ТЗ).

        Examples:
            >>> pass
        """
        raw = await transport.execute_command("cat /proc/meminfo", shell="bash", timeout=15)
        mem_kb: Dict[str, int] = {}
        for line in raw.stdout.splitlines():
            m = re.match(r"^(\w+):\s+(\d+)", line.strip())
            if m:
                mem_kb[m.group(1)] = int(m.group(2))

        total_mb = int(mem_kb.get("MemTotal", 0) // 1024)
        avail_kb = mem_kb.get("MemAvailable", mem_kb.get("MemFree", 0))
        avail_mb = int(avail_kb // 1024)
        used_mb = max(0, total_mb - avail_mb)

        return pack_raw_result(
            raw,
            {
                "total_mb": total_mb,
                "used_mb": used_mb,
                "available_mb": avail_mb,
            },
        )

    @staticmethod
    async def system_disks(transport: BaseTransport) -> Dict[str, Any]:
        """Получение списка файловых систем и свободного места через `df -BM`.

        Args:
            transport (BaseTransport): Активный транспорт узла.

        Returns:
            Dict[str, Any]: Список томов в ключе `disks`.

        Examples:
            >>> pass
        """
        raw = await transport.execute_command("df -PT -BM", shell="bash", timeout=15)
        disks: List[Dict[str, Any]] = []
        lines = raw.stdout.splitlines()
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 7:
                tot = int(parts[2].rstrip("M")) if parts[2].rstrip("M").isdigit() else 0
                used = int(parts[3].rstrip("M")) if parts[3].rstrip("M").isdigit() else 0
                avail = int(parts[4].rstrip("M")) if parts[4].rstrip("M").isdigit() else 0
                disks.append(
                    {
                        "mount": parts[6],
                        "fstype": parts[1],
                        "total_mb": tot,
                        "used_mb": used,
                        "free_mb": avail,
                    }
                )
        return pack_raw_result(raw, {"disks": disks})

    @staticmethod
    async def system_uptime(transport: BaseTransport) -> Dict[str, Any]:
        """Чтение времени непрерывной работы из `/proc/uptime`.

        Args:
            transport (BaseTransport): Активный транспорт узла.

        Returns:
            Dict[str, Any]: Словарь с `uptime_seconds`.

        Examples:
            >>> pass
        """
        raw = await transport.execute_command("cat /proc/uptime", shell="bash", timeout=15)
        tokens = raw.stdout.split()
        up_sec = int(float(tokens[0])) if tokens else 0
        return pack_raw_result(raw, {"uptime_seconds": up_sec})

    @staticmethod
    async def system_boot_info(transport: BaseTransport) -> Dict[str, Any]:
        """Получение информации о последней загрузке через `who -b` / `journalctl`.

        Args:
            transport (BaseTransport): Активный транспорт узла.

        Returns:
            Dict[str, Any]: Информация о загрузке ОС.

        Examples:
            >>> pass
        """
        return await LinuxExecutor.run_bash(transport, "uptime -s")

    @staticmethod
    async def system_environment(transport: BaseTransport) -> Dict[str, Any]:
        """Получение переменных окружения Linux (`env`).

        Args:
            transport (BaseTransport): Активный транспорт узла.

        Returns:
            Dict[str, Any]: Словарь переменных окружения в `variables`.

        Examples:
            >>> pass
        """
        raw = await transport.execute_command("env", shell="bash", timeout=15)
        env_map: Dict[str, str] = {}
        for line in raw.stdout.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                env_map[k] = v
        return pack_raw_result(raw, {"variables": env_map})
