# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Native - SetupAPI
# =============================================================================
# Description:
#   Низкоуровневый интерфейс к SetupAPI и Configuration Manager PnP.
#   Единый реэкспорт из apps.windows.sdk.win32_ffi.setupapi для предотвращения
#   конфликтов типов структур ctypes (SP_DEVINFO_DATA).
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.native.setupapi import SetupAPI, SP_DEVINFO_DATA
#
# File: setupapi.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.native
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-16 19:11:00
# =============================================================================

from __future__ import annotations
"""Низкоуровневый интерфейс к SetupAPI и Configuration Manager PnP (реэкспорт из win32_ffi)."""

from apps.windows.sdk.win32_ffi.setupapi import (
    DIGCF_ALLCLASSES,
    DIGCF_DEFAULT,
    DIGCF_DEVICEINTERFACE,
    DIGCF_PRESENT,
    DIGCF_PROFILE,
    DN_HAS_PROBLEM,
    CR_SUCCESS,
    SPDRP_CLASS,
    SPDRP_CLASSGUID,
    SPDRP_DEVICEDESC,
    SPDRP_DRIVER,
    SPDRP_FRIENDLYNAME,
    SPDRP_HARDWAREID,
    SPDRP_MFG,
    GUID,
    SP_DEVINFO_DATA,
    PnPDeviceInfo,
    SetupAPI,
)

__all__ = [
    "DIGCF_ALLCLASSES",
    "DIGCF_DEFAULT",
    "DIGCF_DEVICEINTERFACE",
    "DIGCF_PRESENT",
    "DIGCF_PROFILE",
    "DN_HAS_PROBLEM",
    "CR_SUCCESS",
    "SPDRP_CLASS",
    "SPDRP_CLASSGUID",
    "SPDRP_DEVICEDESC",
    "SPDRP_DRIVER",
    "SPDRP_FRIENDLYNAME",
    "SPDRP_HARDWAREID",
    "SPDRP_MFG",
    "GUID",
    "SP_DEVINFO_DATA",
    "PnPDeviceInfo",
    "SetupAPI",
]
