# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Apps Windows SDK WinRT Subsystems - Package Init
# =============================================================================
# Description:
#   Пакет специализированных адаптеров подсистем Windows Runtime:
#   Power, Network, Media, Graphics, Devices, AppModel.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.winrt.subsystems import WinRTPowerSubsystem
#
# File: __init__.py
# Project: ai-tc
# Package: apps.windows.sdk.winrt.subsystems
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-16 05:40:00
# =============================================================================

from __future__ import annotations
"""Экспорт подсистемных адаптеров WinRT."""

from .power import WinRTPowerSubsystem
from .network import WinRTNetworkSubsystem
from .media import WinRTMediaSubsystem
from .graphics import WinRTGraphicsSubsystem
from .devices import WinRTDevicesSubsystem
from .appmodel import WinRTAppModelSubsystem

__all__ = [
    "WinRTPowerSubsystem",
    "WinRTNetworkSubsystem",
    "WinRTMediaSubsystem",
    "WinRTGraphicsSubsystem",
    "WinRTDevicesSubsystem",
    "WinRTAppModelSubsystem",
]
