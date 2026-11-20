# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Apps Windows SDK WinRT Subsystems - Network
# =============================================================================
# Description:
#   Адаптер к подсистеме Windows.Networking.Connectivity (WinRT).
#   Опрашивает текущий активный профиль сети, уровень связности с интернетом,
#   статус корпоративного домена, тип интерфейса (Ethernet/WLAN/WWAN) и уровень сигнала.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.winrt.subsystems.network import WinRTNetworkSubsystem
#
#     subsystem = WinRTNetworkSubsystem()
#     net_info = await subsystem.get_network_telemetry_async()
#
# File: network.py
# Project: ai-tc
# Package: apps.windows.sdk.winrt.subsystems
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-16 05:40:00
# =============================================================================

from __future__ import annotations
"""Адаптер к пространству имён Windows.Networking.Connectivity через WinRT."""

import asyncio
from typing import Optional
from logger import logger
from apps.windows.sdk.winrt.executor import WinRTExecutor
from apps.windows.sdk.winrt.models import WinRTNetworkTelemetry


class WinRTNetworkSubsystem:
    """Подсистема сетевой телеметрии Windows на основе WinRT NetworkInformation."""

    def __init__(self, executor: Optional[WinRTExecutor] = None) -> None:
        """Инициализация подсистемы сети WinRT.

        Args:
            executor: Экземпляр исполнителя WinRT (DI).
        """
        self.executor = executor or WinRTExecutor()

    def get_network_telemetry_sync(self) -> WinRTNetworkTelemetry:
        """Синхронный опрос состояния сетевых подключений через WinRT."""
        script = (
            "[Windows.Networking.Connectivity.NetworkInformation, Windows.Networking.Connectivity, ContentType=WindowsRuntime] | Out-Null; "
            "$p = [Windows.Networking.Connectivity.NetworkInformation]::GetInternetConnectionProfile(); "
            "if ($null -eq $p) { "
            "  @{ ConnectivityLevel = 'None'; DomainConnectivity = 'None' } | ConvertTo-Json -Compress "
            "} else { "
            "  @{ "
            "    ProfileName = $p.ProfileName; "
            "    ConnectivityLevel = $p.GetNetworkConnectivityLevel().ToString(); "
            "    DomainConnectivity = $p.GetDomainConnectivityLevel().ToString(); "
            "    IsWlan = $p.IsWlanConnectionProfile; "
            "    IsWwan = $p.IsWwanConnectionProfile; "
            "    SignalBars = if ($p.GetSignalBars()) { $p.GetSignalBars() } else { $null }; "
            "    InterfaceType = if ($p.NetworkAdapter) { $p.NetworkAdapter.IanaInterfaceType } else { 0 } "
            "  } | ConvertTo-Json -Compress "
            "}"
        )
        data = self.executor.execute_script_sync(
            script=script,
            timeout_sec=4.0,
            cache_key="winrt_network",
            cache_ttl_sec=3.0,
        )

        if "error" in data or not data:
            logger.debug(f"[WinRTNetworkSubsystem] Использование fallback значений сети: {data.get('error')}")
            return WinRTNetworkTelemetry()

        return WinRTNetworkTelemetry(
            profile_name=data.get("ProfileName"),
            connectivity_level=str(data.get("ConnectivityLevel", "None")),
            domain_connectivity=str(data.get("DomainConnectivity", "None")),
            is_wlan=bool(data.get("IsWlan", False)),
            is_wwan=bool(data.get("IsWwan", False)),
            signal_bars=data.get("SignalBars"),
            iana_interface_type=int(data.get("InterfaceType") or 0),
        )

    async def get_network_telemetry_async(self) -> WinRTNetworkTelemetry:
        """Асинхронный неблокирующий опрос состояния сетевых подключений через WinRT."""
        return await asyncio.to_thread(self.get_network_telemetry_sync)
