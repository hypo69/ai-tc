# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Apps Windows SDK WinRT Subsystems - Graphics
# =============================================================================
# Description:
#   Адаптер к подсистемам Windows.Graphics.Capture и Windows.Graphics.Imaging (WinRT).
#   Проверяет поддержку современного аппаратно-ускоренного захвата окон/экранов
#   и считывает перечень зарегистрированных в ОС кодеков декодирования и кодирования WIC.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.winrt.subsystems.graphics import WinRTGraphicsSubsystem
#
#     subsystem = WinRTGraphicsSubsystem()
#     graphics_info = await subsystem.get_graphics_telemetry_async()
#
# File: graphics.py
# Project: ai-tc
# Package: apps.windows.sdk.winrt.subsystems
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-16 05:40:00
# =============================================================================

from __future__ import annotations
"""Адаптер к пространствам имён Windows.Graphics.Capture и Windows.Graphics.Imaging через WinRT."""

import asyncio
from typing import Optional
from logger import logger
from apps.windows.sdk.winrt.executor import WinRTExecutor
from apps.windows.sdk.winrt.models import WinRTGraphicsTelemetry


class WinRTGraphicsSubsystem:
    """Подсистема графической телеметрии и возможностей захвата Windows на основе WinRT."""

    def __init__(self, executor: Optional[WinRTExecutor] = None) -> None:
        """Инициализация подсистемы графики WinRT.

        Args:
            executor: Экземпляр исполнителя WinRT (DI).
        """
        self.executor = executor or WinRTExecutor()

    def get_graphics_telemetry_sync(self) -> WinRTGraphicsTelemetry:
        """Синхронный сбор графической телеметрии WinRT."""
        script = (
            "[Windows.Graphics.Capture.GraphicsCaptureSession, Windows.Graphics.Capture, ContentType=WindowsRuntime] | Out-Null; "
            "[Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType=WindowsRuntime] | Out-Null; "
            "[Windows.Graphics.Imaging.BitmapEncoder, Windows.Graphics.Imaging, ContentType=WindowsRuntime] | Out-Null; "
            "$isSupported = [Windows.Graphics.Capture.GraphicsCaptureSession]::IsSupported(); "
            "$dec = @([Windows.Graphics.Imaging.BitmapDecoder]::GetDecoderInformationEnumerator() | ForEach-Object { $_.FriendlyName }); "
            "$enc = @([Windows.Graphics.Imaging.BitmapEncoder]::GetEncoderInformationEnumerator() | ForEach-Object { $_.FriendlyName }); "
            "@{"
            "  CaptureSupported = $isSupported; "
            "  Decoders = $dec; "
            "  Encoders = $enc "
            "} | ConvertTo-Json -Compress"
        )

        data = self.executor.execute_script_sync(
            script=script,
            timeout_sec=4.0,
            cache_key="winrt_graphics",
            cache_ttl_sec=300.0,  # список кодеков статичен, кэшируем на 5 минут
        )

        if "error" in data or not data:
            logger.debug(f"[WinRTGraphicsSubsystem] Использование fallback значений: {data.get('error')}")
            return WinRTGraphicsTelemetry()

        decoders = data.get("Decoders", [])
        if isinstance(decoders, str):
            decoders = [decoders]

        encoders = data.get("Encoders", [])
        if isinstance(encoders, str):
            encoders = [encoders]

        return WinRTGraphicsTelemetry(
            capture_supported=bool(data.get("CaptureSupported", True)),
            supported_imaging_decoders=decoders,
            supported_imaging_encoders=encoders,
            gpu_d3d_device_accessible=True,
        )

    async def get_graphics_telemetry_async(self) -> WinRTGraphicsTelemetry:
        """Асинхронный неблокирующий сбор графической телеметрии."""
        return await asyncio.to_thread(self.get_graphics_telemetry_sync)
