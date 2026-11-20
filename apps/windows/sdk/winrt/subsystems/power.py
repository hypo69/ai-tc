# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Apps Windows SDK WinRT Subsystems - Power
# =============================================================================
# Description:
#   Адаптер к подсистеме Windows.System.Power (WinRT).
#   Считывает статус аккумулятора, состояние энергосбережения, источник питания
#   и расчётный процент заряда без обращения к устаревшим Win32 API.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.winrt.subsystems.power import WinRTPowerSubsystem
#
#     subsystem = WinRTPowerSubsystem()
#     power_info = await subsystem.get_power_telemetry_async()
#
# File: power.py
# Project: ai-tc
# Package: apps.windows.sdk.winrt.subsystems
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-16 05:40:00
# =============================================================================

from __future__ import annotations
"""Адаптер к пространству имён Windows.System.Power через WinRT."""

from typing import Optional
from logger import logger
from apps.windows.sdk.winrt.executor import WinRTExecutor
from apps.windows.sdk.winrt.models import WinRTPowerTelemetry


class WinRTPowerSubsystem:
    """Подсистема телеметрии питания Windows на основе WinRT PowerManager."""

    def __init__(self, executor: Optional[WinRTExecutor] = None) -> None:
        """Инициализация подсистемы питания WinRT.

        Args:
            executor: Экземпляр исполнителя WinRT (DI).
        """
        self.executor = executor or WinRTExecutor()

    def get_power_telemetry_sync(self) -> WinRTPowerTelemetry:
        """Синхронный сбор телеметрии питания WinRT."""
        script = (
            "[Windows.System.Power.PowerManager, Windows.System.Power, ContentType=WindowsRuntime] | Out-Null; "
            "@{"
            "BatteryStatus = [Windows.System.Power.PowerManager]::BatteryStatus.ToString(); "
            "EnergySaverStatus = [Windows.System.Power.PowerManager]::EnergySaverStatus.ToString(); "
            "PowerSupplyStatus = [Windows.System.Power.PowerManager]::PowerSupplyStatus.ToString(); "
            "RemainingChargePercent = [Windows.System.Power.PowerManager]::RemainingChargePercent"
            "} | ConvertTo-Json -Compress"
        )
        data = self.executor.execute_script_sync(
            script=script,
            timeout_sec=4.0,
            cache_key="winrt_power",
            cache_ttl_sec=2.0,
        )

        if "error" in data or not data:
            logger.debug(f"[WinRTPowerSubsystem] Использование fallback значений: {data.get('error')}")
            return WinRTPowerTelemetry()

        battery_status = str(data.get("BatteryStatus", "NotPresent"))
        energy_saver = str(data.get("EnergySaverStatus", "Disabled"))
        power_supply = str(data.get("PowerSupplyStatus", "Adequate"))
        remaining_pct = data.get("RemainingChargePercent")
        if remaining_pct is not None:
            try:
                remaining_pct = int(remaining_pct)
            except (ValueError, TypeError):
                remaining_pct = None

        return WinRTPowerTelemetry(
            battery_status=battery_status,
            energy_saver_status=energy_saver,
            power_supply_status=power_supply,
            remaining_charge_percent=remaining_pct,
            is_battery_present=(battery_status != "NotPresent"),
        )

    async def get_power_telemetry_async(self) -> WinRTPowerTelemetry:
        """Асинхронный неблокирующий сбор телеметрии питания WinRT."""
        import asyncio
        return await asyncio.to_thread(self.get_power_telemetry_sync)
