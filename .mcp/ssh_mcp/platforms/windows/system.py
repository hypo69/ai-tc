# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Адаптер системной информации Windows (CIM / WMI / SDK)
# =============================================================================
# Description:
#   Сбор унифицированной системной информации на платформе Windows:
#   system_info, system_cpu, system_memory, system_disks, system_uptime,
#   system_boot_info и system_environment. При локальном выполнении
#   переиспользует стек ai-tc / psutil для мгновенного ответа без оверхеда.
#
# File: system.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.platforms.windows
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:52:30
# =============================================================================

import os
import platform as py_platform
import time
from typing import Any, Dict
import psutil

from ...transports.base import BaseTransport
from ...transports.local_transport import LocalTransport
from .executor import WindowsExecutor


class WindowsSystemAdapter:
    """Адаптер системного мониторинга и инвентаризации для ОС Windows.

    Возвращает данные в единой кроссплатформенной структуре (совместимой с Linux).

    Examples:
        >>> adapter = WindowsSystemAdapter()
    """

    @staticmethod
    async def system_info(transport: BaseTransport) -> Dict[str, Any]:
        """Получение сведений об ОС Windows (CIM Win32_OperatingSystem).

        Args:
            transport (BaseTransport): Активный транспорт узла.

        Returns:
            Dict[str, Any]: Унифицированная структура (`hostname`, `os_name`, `version`, `arch`).

        Examples:
            >>> pass
        """
        if isinstance(transport, LocalTransport):
            uname = py_platform.uname()
            return {
                "hostname": uname.node,
                "os_name": f"{uname.system} {uname.release}",
                "version": uname.version,
                "architecture": uname.machine,
            }
        ps = (
            "$os = Get-CimInstance Win32_OperatingSystem; "
            "@{hostname=$env:COMPUTERNAME; os_name=$os.Caption; version=$os.Version; architecture=$os.OSArchitecture} "
            "| ConvertTo-Json -Compress"
        )
        return await WindowsExecutor.run_ps_json(transport, ps)

    @staticmethod
    async def system_cpu(transport: BaseTransport) -> Dict[str, Any]:
        """Получение загрузки CPU и количества ядер Windows.

        Args:
            transport (BaseTransport): Активный транспорт узла.

        Returns:
            Dict[str, Any]: Словарь с `cores_logical`, `cores_physical`, `usage_percent`.

        Examples:
            >>> pass
        """
        if isinstance(transport, LocalTransport):
            return {
                "cores_logical": int(psutil.cpu_count(logical=True) or 1),
                "cores_physical": int(psutil.cpu_count(logical=False) or 1),
                "usage_percent": float(psutil.cpu_percent(interval=0.05)),
            }
        ps = (
            "$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1; "
            "@{cores_logical=[int]$cpu.NumberOfLogicalProcessors; cores_physical=[int]$cpu.NumberOfCores; "
            "usage_percent=[float]$cpu.LoadPercentage} | ConvertTo-Json -Compress"
        )
        return await WindowsExecutor.run_ps_json(transport, ps)

    @staticmethod
    async def system_memory(transport: BaseTransport) -> Dict[str, Any]:
        """Получение состояния оперативной памяти в МБ (`total_mb`, `used_mb`, `available_mb`).

        Args:
            transport (BaseTransport): Активный транспорт узла.

        Returns:
            Dict[str, Any]: Унифицированная структура памяти в МБ (Раздел 9 ТЗ).

        Examples:
            >>> pass
        """
        if isinstance(transport, LocalTransport):
            vm = psutil.virtual_memory()
            total_mb = int(vm.total // (1024 * 1024))
            avail_mb = int(vm.available // (1024 * 1024))
            return {
                "total_mb": total_mb,
                "used_mb": max(0, total_mb - avail_mb),
                "available_mb": avail_mb,
            }
        ps = (
            "$os = Get-CimInstance Win32_OperatingSystem; "
            "$tot = [int][math]::Round($os.TotalVisibleMemorySize / 1024); "
            "$av = [int][math]::Round($os.FreePhysicalMemory / 1024); "
            "@{total_mb=$tot; used_mb=($tot - $av); available_mb=$av} | ConvertTo-Json -Compress"
        )
        return await WindowsExecutor.run_ps_json(transport, ps)

    @staticmethod
    async def system_disks(transport: BaseTransport) -> Dict[str, Any]:
        """Получение списка логических дисков и свободного места в МБ.

        Args:
            transport (BaseTransport): Активный транспорт узла.

        Returns:
            Dict[str, Any]: Список томов в ключе `disks`.

        Examples:
            >>> pass
        """
        if isinstance(transport, LocalTransport):
            disks = []
            for part in psutil.disk_partitions(all=False):
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    disks.append(
                        {
                            "mount": part.mountpoint,
                            "fstype": part.fstype,
                            "total_mb": int(usage.total // (1024 * 1024)),
                            "used_mb": int(usage.used // (1024 * 1024)),
                            "free_mb": int(usage.free // (1024 * 1024)),
                        }
                    )
                except OSError:
                    continue
            return {"disks": disks}
        ps = (
            "$d = Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | ForEach-Object { "
            "@{mount=$_.DeviceID; fstype=$_.FileSystem; total_mb=[int]($_.Size/1MB); "
            "free_mb=[int]($_.FreeSpace/1MB); used_mb=[int](($_.Size - $_.FreeSpace)/1MB)} }; "
            "@{disks=@($d)} | ConvertTo-Json -Compress"
        )
        return await WindowsExecutor.run_ps_json(transport, ps)

    @staticmethod
    async def system_uptime(transport: BaseTransport) -> Dict[str, Any]:
        """Получение времени непрерывной работы ОС в секундах.

        Args:
            transport (BaseTransport): Активный транспорт узла.

        Returns:
            Dict[str, Any]: Словарь с `uptime_seconds` и `boot_timestamp`.

        Examples:
            >>> pass
        """
        if isinstance(transport, LocalTransport):
            boot_ts = int(psutil.boot_time())
            return {
                "uptime_seconds": max(0, int(time.time()) - boot_ts),
                "boot_timestamp": boot_ts,
            }
        ps = (
            "$os = Get-CimInstance Win32_OperatingSystem; "
            "$up = [int]((Get-Date) - $os.LastBootUpTime).TotalSeconds; "
            "@{uptime_seconds=$up} | ConvertTo-Json -Compress"
        )
        return await WindowsExecutor.run_ps_json(transport, ps)

    @staticmethod
    async def system_boot_info(transport: BaseTransport) -> Dict[str, Any]:
        """Получение сведений о последней загрузке ОС Windows.

        Args:
            transport (BaseTransport): Активный транспорт узла.

        Returns:
            Dict[str, Any]: Информация о загрузке системы.

        Examples:
            >>> pass
        """
        ps = (
            "$os = Get-CimInstance Win32_OperatingSystem; "
            "@{last_boot=$os.LastBootUpTime.ToString('o'); system_directory=$os.SystemDirectory} "
            "| ConvertTo-Json -Compress"
        )
        return await WindowsExecutor.run_ps_json(transport, ps)

    @staticmethod
    async def system_environment(transport: BaseTransport) -> Dict[str, Any]:
        """Получение переменных окружения процесса/системы (с последующей очисткой секретов).

        Args:
            transport (BaseTransport): Активный транспорт узла.

        Returns:
            Dict[str, Any]: Словарь переменных окружения в `variables`.

        Examples:
            >>> pass
        """
        if isinstance(transport, LocalTransport):
            return {"variables": dict(os.environ)}
        ps = (
            "$e = @{}; Get-ChildItem Env: | ForEach-Object { $e[$_.Name] = $_.Value }; "
            "@{variables=$e} | ConvertTo-Json -Compress"
        )
        return await WindowsExecutor.run_ps_json(transport, ps)
