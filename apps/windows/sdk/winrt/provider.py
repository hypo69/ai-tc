# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Apps Windows SDK WinRT - Provider
# =============================================================================
# Description:
#   Адаптер WinRTProvider — системный источник телеметрии и управления Windows.
#   Входит в триаду системных провайдеров AI-TC (Win32 / WinRT / WMI-CIM)
#   и поставляет высокоуровневые метаданные и снимки в Telemetry Bus.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.winrt.provider import WinRTProvider
#
#     provider = WinRTProvider()
#     snapshot = await provider.probe_snapshot_async()
#
# File: provider.py
# Project: ai-tc
# Package: apps.windows.sdk.winrt
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-16 05:40:00
# =============================================================================

from __future__ import annotations
"""Системный провайдер WinRTProvider для архитектуры сбора данных AI-TC."""

import asyncio
import os
import platform
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from logger import logger

from apps.windows.sdk.winrt.executor import WinRTExecutor
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
from apps.windows.sdk.winrt.subsystems.appmodel import WinRTAppModelSubsystem
from apps.windows.sdk.winrt.subsystems.devices import WinRTDevicesSubsystem
from apps.windows.sdk.winrt.subsystems.graphics import WinRTGraphicsSubsystem
from apps.windows.sdk.winrt.subsystems.media import WinRTMediaSubsystem
from apps.windows.sdk.winrt.subsystems.network import WinRTNetworkSubsystem
from apps.windows.sdk.winrt.subsystems.power import WinRTPowerSubsystem


class WinRTProvider:
    """Адаптер системного уровня WinRTProvider (Windows Runtime / UWP).

    Реализует концепцию конспекта: предоставление данных из современного уровня
    Windows API (Windows.Graphics, Windows.Media, Windows.Devices, Windows.Networking,
    Windows.System.Power, Windows.ApplicationModel) без жесткой привязки
    диагностической системы исключительно к Win32 или WMI.
    """

    SUPPORTED_NAMESPACES: List[str] = [
        "Windows.System.Power",
        "Windows.Networking.Connectivity",
        "Windows.Media.Control",
        "Windows.Media.Capture",
        "Windows.Graphics.Capture",
        "Windows.Graphics.Imaging",
        "Windows.Devices.Enumeration",
        "Windows.ApplicationModel",
    ]

    def __init__(self, executor: Optional[WinRTExecutor] = None) -> None:
        """Инициализация провайдера WinRT и его дочерних подсистем.

        Args:
            executor: Экземпляр исполнителя WinRT (DI).
        """
        self.executor = executor or WinRTExecutor()
        self.power = WinRTPowerSubsystem(self.executor)
        self.network = WinRTNetworkSubsystem(self.executor)
        self.media = WinRTMediaSubsystem(self.executor)
        self.graphics = WinRTGraphicsSubsystem(self.executor)
        self.devices = WinRTDevicesSubsystem(self.executor)
        self.appmodel = WinRTAppModelSubsystem(self.executor)
        self._last_error: Optional[str] = None

    def is_available(self) -> bool:
        """Проверка доступности среды WinRT на хосте."""
        return os.name == "nt"

    def get_status(self) -> WinRTProviderStatus:
        """Получение текущего статуса провайдера WinRT."""
        is_avail = self.is_available()
        return WinRTProviderStatus(
            is_available=is_avail,
            os_version=f"{platform.system()} {platform.release()} ({platform.version()})",
            runtime_engine="PowerShell / WinRT System Runtime Bridge",
            supported_namespaces=self.SUPPORTED_NAMESPACES,
            last_error=self._last_error,
        )

    def probe_snapshot_sync(self) -> WinRTSnapshot:
        """Синхронный сбор полного снимка всех WinRT подсистем."""
        status = self.get_status()
        if not status.is_available:
            return WinRTSnapshot(status=status)

        try:
            power_data = self.power.get_power_telemetry_sync()
            network_data = self.network.get_network_telemetry_sync()
            media_data = self.media.get_media_telemetry_sync()
            graphics_data = self.graphics.get_graphics_telemetry_sync()
            devices_data = self.devices.get_devices_telemetry_sync()
            appmodel_data = self.appmodel.get_appmodel_telemetry_sync()

            return WinRTSnapshot(
                timestamp=datetime.now(timezone.utc),
                status=status,
                power=power_data,
                network=network_data,
                media=media_data,
                graphics=graphics_data,
                devices=devices_data,
                appmodel=appmodel_data,
            )
        except Exception as e:
            self._last_error = str(e)
            logger.error(f"[WinRTProvider] Ошибка формирования снимка WinRT: {e}")
            status.last_error = str(e)
            return WinRTSnapshot(status=status)

    async def probe_snapshot_async(self) -> WinRTSnapshot:
        """Асинхронный параллельный сбор полного снимка WinRT подсистем."""
        status = self.get_status()
        if not status.is_available:
            return WinRTSnapshot(status=status)

        try:
            power_task = self.power.get_power_telemetry_async()
            network_task = self.network.get_network_telemetry_async()
            media_task = self.media.get_media_telemetry_async()
            graphics_task = self.graphics.get_graphics_telemetry_async()
            devices_task = self.devices.get_devices_telemetry_async()
            appmodel_task = self.appmodel.get_appmodel_telemetry_async()

            results = await asyncio.gather(
                power_task,
                network_task,
                media_task,
                graphics_task,
                devices_task,
                appmodel_task,
                return_exceptions=True,
            )

            p_res = results[0] if isinstance(results[0], WinRTPowerTelemetry) else WinRTPowerTelemetry()
            n_res = results[1] if isinstance(results[1], WinRTNetworkTelemetry) else WinRTNetworkTelemetry()
            m_res = results[2] if isinstance(results[2], WinRTMediaSessionTelemetry) else WinRTMediaSessionTelemetry()
            g_res = results[3] if isinstance(results[3], WinRTGraphicsTelemetry) else WinRTGraphicsTelemetry()
            d_res = results[4] if isinstance(results[4], WinRTDeviceTelemetry) else WinRTDeviceTelemetry()
            a_res = results[5] if isinstance(results[5], WinRTPackageTelemetry) else WinRTPackageTelemetry()

            return WinRTSnapshot(
                timestamp=datetime.now(timezone.utc),
                status=status,
                power=p_res,
                network=n_res,
                media=m_res,
                graphics=g_res,
                devices=d_res,
                appmodel=a_res,
            )
        except Exception as e:
            self._last_error = str(e)
            logger.error(f"[WinRTProvider] Ошибка асинхронного сбора снимка WinRT: {e}")
            status.last_error = str(e)
            return WinRTSnapshot(status=status)

    def to_telemetry_dict(self, snapshot: Optional[WinRTSnapshot] = None) -> Dict[str, Any]:
        """Преобразование снимка в структурированный словарь для Telemetry Bus."""
        snap = snapshot or self.probe_snapshot_sync()
        return snap.model_dump(mode="json")
