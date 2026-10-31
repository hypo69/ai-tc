# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Telemetry Win32_FFI Compatibility Bridge
# =============================================================================
# Description:
#   Мост обратной совместимости для импорта win32_ffi из apps.windows.telemetry.win32_ffi.
#   Перенаправляет вызовы на apps.windows.sdk.win32_ffi.
#
# File: __init__.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry.win32_ffi
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-13 17:39:00
# =============================================================================

"""Мост обратной совместимости win32_ffi."""

from apps.windows.sdk.win32_ffi import (
    Kernel32API,
    PsapiAPI,
    Advapi32API,
    NtdllAPI,
    EtwAPI,
    WevtAPI,
    ChannelMetadata,
    CHANNEL_DESCRIPTIONS,
    ServiceControlManager,
    ServiceInfo,
    TaskSchedulerAPI,
    IPHelperAPI,
    NetworkSocketInfo,
    SetupAPI,
    PnPDeviceInfo,
    WindowsErrorDecoder,
    format_system_error,
    decode_bugcheck_code,
)
from apps.windows.sdk.win32_ffi import (
    advapi32,
    error_decoder,
    etw,
    kernel32,
    nethelper,
    ntdll,
    psapi,
    scm,
    setupapi,
    tasksched,
    wevtapi,
)

__all__ = [
    'Kernel32API',
    'PsapiAPI',
    'Advapi32API',
    'NtdllAPI',
    'EtwAPI',
    'WevtAPI',
    'ChannelMetadata',
    'CHANNEL_DESCRIPTIONS',
    'ServiceControlManager',
    'ServiceInfo',
    'TaskSchedulerAPI',
    'IPHelperAPI',
    'NetworkSocketInfo',
    'SetupAPI',
    'PnPDeviceInfo',
    'WindowsErrorDecoder',
    'format_system_error',
    'decode_bugcheck_code',
    'advapi32',
    'error_decoder',
    'etw',
    'kernel32',
    'nethelper',
    'ntdll',
    'psapi',
    'scm',
    'setupapi',
    'tasksched',
    'wevtapi',
]

