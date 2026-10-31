# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Audio Module - Init
# =============================================================================
# Description:
#   Пакет управления звуком и системной громкостью Windows.
#
# Usage Examples:
#   from apps.windows.sdk.modules.sound import SoundManager, SoundSettingsDTO
#
# File: __init__.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.sound
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-27 12:05:00
# =============================================================================

from __future__ import annotations
"""Модуль управления звуком Windows."""

from .manager import SoundManager
from .models import (
    AudioDeviceDTO,
    LaunchToolRequest,
    MuteChangeRequest,
    SessionMuteRequest,
    SessionVolumeRequest,
    SoundSchemeDTO,
    SoundSessionDTO,
    SoundSettingsDTO,
    TestSoundRequest,
    VolumeChangeRequest,
)

__all__ = [
    "SoundManager",
    "AudioDeviceDTO",
    "SoundSessionDTO",
    "SoundSchemeDTO",
    "SoundSettingsDTO",
    "VolumeChangeRequest",
    "MuteChangeRequest",
    "SessionVolumeRequest",
    "SessionMuteRequest",
    "TestSoundRequest",
    "LaunchToolRequest",
]

