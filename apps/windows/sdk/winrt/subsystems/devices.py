# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Apps Windows SDK WinRT Subsystems - Devices
# =============================================================================
# Description:
#   Адаптер к подсистеме Windows.Devices.Enumeration (WinRT).
#   Опрашивает зарегистрированные в Windows устройства по классам DeviceClass:
#   аудиовыход (AudioRender), захват звука (AudioCapture), видеокамеры (VideoCapture)
#   и общее количество подключённой периферии.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.winrt.subsystems.devices import WinRTDevicesSubsystem
#
#     subsystem = WinRTDevicesSubsystem()
#     dev_info = await subsystem.get_devices_telemetry_async()
#
# File: devices.py
# Project: ai-tc
# Package: apps.windows.sdk.winrt.subsystems
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-16 05:40:00
# =============================================================================

from __future__ import annotations
"""Адаптер к пространству имён Windows.Devices.Enumeration через WinRT."""

import asyncio
from typing import Optional
from logger import logger
from apps.windows.sdk.winrt.executor import WinRTExecutor
from apps.windows.sdk.winrt.models import WinRTDeviceTelemetry


class WinRTDevicesSubsystem:
    """Подсистема инвентаризации устройств Windows на основе WinRT DeviceInformation."""

    def __init__(self, executor: Optional[WinRTExecutor] = None) -> None:
        """Инициализация подсистемы устройств WinRT.

        Args:
            executor: Экземпляр исполнителя WinRT (DI).
        """
        self.executor = executor or WinRTExecutor()

    def get_devices_telemetry_sync(self) -> WinRTDeviceTelemetry:
        """Синхронный сбор телеметрии устройств по классам WinRT."""
        script = (
            "Add-Type -AssemblyName System.Runtime.WindowsRuntime; "
            "$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | "
            "Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Length -eq 1 -and $_.IsGenericMethod })[0]; "
            "[Windows.Devices.Enumeration.DeviceInformation, Windows.Devices.Enumeration, ContentType=WindowsRuntime] | Out-Null; "
            "$queryClass = { param($cls) "
            "  try { "
            "    $op = [Windows.Devices.Enumeration.DeviceInformation]::FindAllAsync($cls); "
            "    $asTask = $asTaskGeneric.MakeGenericMethod([Windows.Devices.Enumeration.DeviceInformationCollection]); "
            "    $t = $asTask.Invoke($null, @($op)); "
            "    if ($t.Wait(1500)) { $t.Result.Count } else { 0 } "
            "  } catch { 0 } "
            "}; "
            "@{"
            "  AudioCapture = & $queryClass ([Windows.Devices.Enumeration.DeviceClass]::AudioCapture); "
            "  AudioRender = & $queryClass ([Windows.Devices.Enumeration.DeviceClass]::AudioRender); "
            "  VideoCapture = & $queryClass ([Windows.Devices.Enumeration.DeviceClass]::VideoCapture) "
            "} | ConvertTo-Json -Compress"
        )

        data = self.executor.execute_script_sync(
            script=script,
            timeout_sec=5.0,
            cache_key="winrt_devices",
            cache_ttl_sec=30.0,
        )

        if "error" in data or not data:
            logger.debug(f"[WinRTDevicesSubsystem] Использование fallback значений: {data.get('error')}")
            return WinRTDeviceTelemetry()

        audio_capture = int(data.get("AudioCapture") or 0)
        audio_render = int(data.get("AudioRender") or 0)
        video_capture = int(data.get("VideoCapture") or 0)
        total = audio_capture + audio_render + video_capture

        return WinRTDeviceTelemetry(
            total_devices_count=total,
            cameras_count=video_capture,
            audio_render_count=audio_render,
            audio_capture_count=audio_capture,
        )

    async def get_devices_telemetry_async(self) -> WinRTDeviceTelemetry:
        """Асинхронный неблокирующий сбор телеметрии устройств."""
        return await asyncio.to_thread(self.get_devices_telemetry_sync)
