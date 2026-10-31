# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Settings SDK - Package Init
# =============================================================================
# Description:
#   Пакет декларативного каталога настроек Windows Control Plane, резолвера
#   версий ОС и подсистемы верификации.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.settings import (
#         WINDOWS_SETTINGS,
#         get_settings_catalog,
#         SettingsResolver,
#         SettingsVerification,
#     )
#
# File: __init__.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.settings
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 13:00:00
# =============================================================================

from __future__ import annotations
"""Пакет каталога настроек, резолвера совместимости и верификации Windows."""

from apps.windows.sdk.settings.catalog import (
    WINDOWS_SETTINGS,
    SettingDefinition,
    get_settings_catalog,
)
from apps.windows.sdk.settings.resolver import (
    ResolutionResult,
    SettingsResolver,
)
from apps.windows.sdk.settings.verification import SettingsVerification

__all__ = [
    "WINDOWS_SETTINGS",
    "SettingDefinition",
    "get_settings_catalog",
    "ResolutionResult",
    "SettingsResolver",
    "SettingsVerification",
]

