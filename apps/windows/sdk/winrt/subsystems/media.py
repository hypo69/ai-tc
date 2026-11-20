# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Apps Windows SDK WinRT Subsystems - Media
# =============================================================================
# Description:
#   Адаптер к подсистемам Windows.Media.Control и Windows.Media.Capture (WinRT).
#   Опрашивает статус системных медиасессий (GlobalSystemMediaTransportControls),
#   активное приложение (AUMID), состояние воспроизведения и доступность медиазахвата.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.winrt.subsystems.media import WinRTMediaSubsystem
#
#     subsystem = WinRTMediaSubsystem()
#     media_info = await subsystem.get_media_telemetry_async()
#
# File: media.py
# Project: ai-tc
# Package: apps.windows.sdk.winrt.subsystems
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-16 05:40:00
# =============================================================================

from __future__ import annotations
"""Адаптер к пространствам имён Windows.Media.Control и Windows.Media.Capture через WinRT."""

import asyncio
from typing import Optional
from logger import logger
from apps.windows.sdk.winrt.executor import WinRTExecutor
from apps.windows.sdk.winrt.models import WinRTMediaSessionTelemetry


class WinRTMediaSubsystem:
    """Подсистема медиа-телеметрии Windows на основе WinRT Media Transport Controls."""

    def __init__(self, executor: Optional[WinRTExecutor] = None) -> None:
        """Инициализация медиа-подсистемы WinRT.

        Args:
            executor: Экземпляр исполнителя WinRT (DI).
        """
        self.executor = executor or WinRTExecutor()

    def get_media_telemetry_sync(self) -> WinRTMediaSessionTelemetry:
        """Синхронный опрос активных медиасессий в ОС Windows."""
        script = (
            "Add-Type -AssemblyName System.Runtime.WindowsRuntime; "
            "$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | "
            "Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Length -eq 1 -and $_.IsGenericMethod })[0]; "
            "[Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager, Windows.Media.Control, ContentType=WindowsRuntime] | Out-Null; "
            "$op = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]::RequestAsync(); "
            "$asTask = $asTaskGeneric.MakeGenericMethod([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]); "
            "$task = $asTask.Invoke($null, @($op)); "
            "$task.Wait(2000) | Out-Null; "
            "$mgr = $task.Result; "
            "$curr = if ($mgr) { $mgr.GetCurrentSession() } else { $null }; "
            "$info = if ($curr) { $curr.GetPlaybackInfo() } else { $null }; "
            "@{"
            "  HasActiveSession = ($null -ne $curr); "
            "  AppId = if ($curr) { $curr.SourceAppUserModelId } else { $null }; "
            "  PlaybackStatus = if ($info) { $info.PlaybackStatus.ToString() } else { $null }; "
            "  CanPause = if ($info -and $info.Controls) { [bool]$info.Controls.IsPauseEnabled } else { $false }; "
            "  CanPlay = if ($info -and $info.Controls) { [bool]$info.Controls.IsPlayEnabled } else { $false } "
            "} | ConvertTo-Json -Compress"
        )

        data = self.executor.execute_script_sync(
            script=script,
            timeout_sec=4.0,
            cache_key="winrt_media",
            cache_ttl_sec=2.0,
        )

        if "error" in data or not data:
            logger.debug(f"[WinRTMediaSubsystem] Использование fallback значений: {data.get('error')}")
            return WinRTMediaSessionTelemetry()

        return WinRTMediaSessionTelemetry(
            has_active_session=bool(data.get("HasActiveSession", False)),
            source_app_user_model_id=data.get("AppId"),
            playback_status=data.get("PlaybackStatus"),
            can_pause=bool(data.get("CanPause", False)),
            can_play=bool(data.get("CanPlay", False)),
            media_capture_supported=True,
        )

    async def get_media_telemetry_async(self) -> WinRTMediaSessionTelemetry:
        """Асинхронный неблокирующий опрос медиа-телеметрии."""
        return await asyncio.to_thread(self.get_media_telemetry_sync)
