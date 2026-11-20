# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Apps Windows Telemetry - WinRT Collector
# =============================================================================
# Description:
#   Коллектор телеметрии Windows Runtime (WinRT) и Universal Windows Platform (UWP).
#   Служит адаптером системного уровня (System Providers: WinRT) для отправки
#   метрик в Telemetry Bus, сохранения в telemetry.db и передачи в Analysis Engine.
#
# Usage Examples:
#   Python API:
#     from apps.windows.telemetry.winrt_collector import WinRTCollector
#
#     collector = WinRTCollector()
#     snapshot = collector.get_winrt_snapshot()
#
# File: winrt_collector.py
# Project: ai-tc
# Package: apps.windows.telemetry
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-16 05:40:00
# =============================================================================

from __future__ import annotations
"""Коллектор телеметрии WinRT/UWP для включения в общую шину сбора метрик AI-TC."""

import asyncio
from typing import Any, Dict, Optional
from logger import logger

from apps.windows.sdk.winrt import (
    WinRTDeviceTelemetry,
    WinRTGraphicsTelemetry,
    WinRTMediaSessionTelemetry,
    WinRTNetworkTelemetry,
    WinRTPackageTelemetry,
    WinRTPowerTelemetry,
    WinRTProvider,
    WinRTProviderStatus,
    WinRTSnapshot,
)


class WinRTCollector:
    """Сборщик метрик и телеметрии Windows Runtime (WinRT) для Telemetry Bus."""

    def __init__(self, provider: Optional[WinRTProvider] = None) -> None:
        """Инициализация коллектора WinRT.

        Args:
            provider: Экземпляр адаптера WinRTProvider (DI).
        """
        self.provider = provider or WinRTProvider()
        self._last_snapshot: Optional[WinRTSnapshot] = None

    def is_available(self) -> bool:
        """Проверка доступности WinRT на текущей платформе."""
        return self.provider.is_available()

    def get_status(self) -> WinRTProviderStatus:
        """Получение статуса WinRT провайдера."""
        return self.provider.get_status()

    def get_winrt_snapshot(self, force_refresh: bool = False) -> WinRTSnapshot:
        """Получение комплексного снимка метрик WinRT (Power, Network, Media, Graphics, Devices, UWP).

        Args:
            force_refresh: Принудительный опрос без использования кэша.

        Returns:
            Экземпляр WinRTSnapshot.
        """
        if not force_refresh and self._last_snapshot is not None:
            return self._last_snapshot
        snapshot = self.provider.probe_snapshot_sync()
        self._last_snapshot = snapshot
        return snapshot

    async def get_winrt_snapshot_async(self, force_refresh: bool = False) -> WinRTSnapshot:
        """Асинхронный неблокирующий сбор снимка метрик WinRT для Event Loop."""
        if not force_refresh and self._last_snapshot is not None:
            return self._last_snapshot
        snapshot = await self.provider.probe_snapshot_async()
        self._last_snapshot = snapshot
        return snapshot

    def get_power_metrics(self) -> WinRTPowerTelemetry:
        """Сбор метрик питания через Windows.System.Power."""
        return self.provider.power.get_power_telemetry_sync()

    def get_network_connectivity(self) -> WinRTNetworkTelemetry:
        """Сбор сетевых метрик через Windows.Networking.Connectivity."""
        return self.provider.network.get_network_telemetry_sync()

    def get_active_media_session(self) -> WinRTMediaSessionTelemetry:
        """Сбор состояния медиасессий через Windows.Media.Control."""
        return self.provider.media.get_media_telemetry_sync()

    def get_graphics_capture_capabilities(self) -> WinRTGraphicsTelemetry:
        """Сбор данных о поддержке захвата экрана через Windows.Graphics.Capture."""
        return self.provider.graphics.get_graphics_telemetry_sync()

    def get_device_counts(self) -> WinRTDeviceTelemetry:
        """Сбор количества устройств через Windows.Devices.Enumeration."""
        return self.provider.devices.get_devices_telemetry_sync()

    def get_uwp_applications(self) -> WinRTPackageTelemetry:
        """Сбор сведений о пакетах UWP и приложении Phone Link через Windows.ApplicationModel."""
        return self.provider.appmodel.get_appmodel_telemetry_sync()

    def to_telemetry_payload(self, snapshot: Optional[WinRTSnapshot] = None) -> Dict[str, Any]:
        """Форматирование данных WinRT для публикации в Telemetry Bus и сохранения в telemetry.db.

        Args:
            snapshot: Опциональный готовый снимок. Если не передан, выполняется сбор.

        Returns:
            Словарь с сериализованными метриками для Telemetry Bus.
        """
        snap = snapshot or self.get_winrt_snapshot()
        return {
            "source": "WinRTProvider",
            "tier": "Tier_Modern_WinRT",
            "timestamp": snap.timestamp.isoformat(),
            "power": snap.power.model_dump(),
            "network": snap.network.model_dump(),
            "media": snap.media.model_dump(),
            "graphics": snap.graphics.model_dump(),
            "devices": snap.devices.model_dump(),
            "appmodel": snap.appmodel.model_dump(),
            "status": snap.status.model_dump(),
        }
