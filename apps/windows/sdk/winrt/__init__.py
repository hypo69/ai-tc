# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Apps Windows SDK WinRT - Package Root
# =============================================================================
# Description:
#   Пакет WinRT (Windows Runtime) и UWP (Universal Windows Platform) для AI-TC.
#   Предоставляет системный адаптер WinRTProvider, подсистемы захвата графики,
#   медиасессий, управления питанием, сетевых подключений и манифестов UWP.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.winrt import WinRTProvider, WinRTSubsystem, WinRTSnapshot
#
# File: __init__.py
# Project: ai-tc
# Package: apps.windows.sdk.winrt
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-16 05:40:00
# =============================================================================

from __future__ import annotations
"""Корневой модуль пакета WinRT Windows SDK."""

from .models import (
    WinRTDeviceTelemetry,
    WinRTGraphicsTelemetry,
    WinRTMediaSessionTelemetry,
    WinRTNetworkTelemetry,
    WinRTPackageTelemetry,
    WinRTPowerTelemetry,
    WinRTProviderStatus,
    WinRTSnapshot,
)
from .executor import WinRTExecutor
from .provider import WinRTProvider
from .client import WinRTSubsystem

__all__ = [
    "WinRTProvider",
    "WinRTSubsystem",
    "WinRTExecutor",
    "WinRTSnapshot",
    "WinRTPowerTelemetry",
    "WinRTNetworkTelemetry",
    "WinRTMediaSessionTelemetry",
    "WinRTGraphicsTelemetry",
    "WinRTDeviceTelemetry",
    "WinRTPackageTelemetry",
    "WinRTProviderStatus",
]
