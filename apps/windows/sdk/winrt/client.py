# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Apps Windows SDK WinRT - Client Facade
# =============================================================================
# Description:
#   Фасад подсистемы WinRT для интеграции в единый WindowsSDK.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.winrt import WinRTSubsystem
#
#     winrt = WinRTSubsystem()
#     snapshot = winrt.get_snapshot()
#
# File: client.py
# Project: ai-tc
# Package: apps.windows.sdk.winrt
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-16 05:40:00
# =============================================================================

from __future__ import annotations
"""Фасад доступа к WinRT и UWP возможностям для WindowsSDK."""

from typing import Any, Dict, Optional
from apps.windows.sdk.winrt.models import (
    WinRTDeviceTelemetry,
    WinRTGraphicsTelemetry,
    WinRTMediaSessionTelemetry,
    WinRTNetworkTelemetry,
    WinRTPackageTelemetry,
    WinRTPowerTelemetry,
    WinRTProviderStatus,
    WinRTSnapshot,
)
from apps.windows.sdk.winrt.provider import WinRTProvider


class WinRTSubsystem:
    """Слой 6 Windows SDK: Современная подсистема WinRT и UWP."""

    def __init__(self, provider: Optional[WinRTProvider] = None) -> None:
        """Инициализация подсистемы WinRT в составе Windows SDK.

        Args:
            provider: Экземпляр адаптера WinRTProvider (DI).
        """
        self.provider = provider or WinRTProvider()

    def get_status(self) -> WinRTProviderStatus:
        """Получение статуса подсистемы WinRT."""
        return self.provider.get_status()

    def get_snapshot(self) -> WinRTSnapshot:
        """Получение полного снимка WinRT телеметрии (синхронно)."""
        return self.provider.probe_snapshot_sync()

    async def get_snapshot_async(self) -> WinRTSnapshot:
        """Получение полного снимка WinRT телеметрии (асинхронно)."""
        return await self.provider.probe_snapshot_async()

    def get_power(self) -> WinRTPowerTelemetry:
        """Телеметрия питания Windows.System.Power."""
        return self.provider.power.get_power_telemetry_sync()

    def get_network(self) -> WinRTNetworkTelemetry:
        """Телеметрия сети Windows.Networking.Connectivity."""
        return self.provider.network.get_network_telemetry_sync()

    def get_media(self) -> WinRTMediaSessionTelemetry:
        """Телеметрия медиасессий Windows.Media.Control."""
        return self.provider.media.get_media_telemetry_sync()

    def get_graphics(self) -> WinRTGraphicsTelemetry:
        """Телеметрия захвата и кодеков Windows.Graphics."""
        return self.provider.graphics.get_graphics_telemetry_sync()

    def get_devices(self) -> WinRTDeviceTelemetry:
        """Телеметрия устройств Windows.Devices.Enumeration."""
        return self.provider.devices.get_devices_telemetry_sync()

    def get_appmodel(self) -> WinRTPackageTelemetry:
        """Телеметрия приложений UWP и Phone Link (Windows.ApplicationModel)."""
        return self.provider.appmodel.get_appmodel_telemetry_sync()
