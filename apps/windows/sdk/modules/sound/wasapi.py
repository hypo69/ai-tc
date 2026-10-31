# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Audio Module - WASAPI Declarations
# =============================================================================
# Description:
#   Константы, GUID, структуры и vtable сигнатуры Windows Core Audio API (WASAPI):
#   IMMDeviceEnumerator, IMMDevice, IAudioEndpointVolume, IAudioSessionManager2,
#   IAudioSessionControl2, ISimpleAudioVolume.
#
# Usage Examples:
#   from apps.windows.sdk.modules.sound.wasapi import CLSID_MMDEVICE_ENUMERATOR, parse_guid
#
# File: wasapi.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.sound
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-27 12:05:00
# =============================================================================

from __future__ import annotations
"""Низкоуровневые определения COM интерфейсов Windows Core Audio (WASAPI)."""

import ctypes
from ctypes import byref, wintypes

# Идентификаторы COM WASAPI
CLSID_MMDEVICE_ENUMERATOR = "{BCDE0395-E52F-467C-8E3D-C4579291692E}"
IID_IMMDEVICE_ENUMERATOR = "{A95664D2-9614-4F35-A746-DE8DB63617E6}"
IID_IAUDIO_ENDPOINT_VOLUME = "{5CDF2C82-841E-4546-9722-0CF74078229A}"
IID_IAUDIO_SESSION_MANAGER2 = "{77AA99A0-1BD6-484F-8BC7-2C654C9A9B6F}"
IID_IAUDIO_SESSION_CONTROL2 = "{bfb7ff88-7239-4fc9-8fa2-07c950be9c6d}"
IID_ISIMPLE_AUDIO_VOLUME = "{87CE5498-68D6-44E5-9215-6DA47EF883D8}"


class GUID(ctypes.Structure):
    """Структура Win32 GUID."""
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", wintypes.BYTE * 8),
    ]


def parse_guid(guid_str: str) -> GUID:
    """Преобразует строковый GUID в бинарную структуру GUID.

    Args:
        guid_str: Строка с представлением GUID вида {XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}.

    Returns:
        GUID: Бинарный объект структуры GUID.
    """
    g = GUID()
    ctypes.windll.ole32.CLSIDFromString(ctypes.c_wchar_p(guid_str), byref(g))
    return g

