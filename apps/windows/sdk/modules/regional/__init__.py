# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Modules Regional - Package Root
# =============================================================================
# Description:
#   Модуль управления региональными параметрами, языковыми пакетами Windows,
#   часовыми поясами, локалями и системными свойствами хоста.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.regional import RegionalManager
#
# File: __init__.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.regional
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 14:25:00
# =============================================================================

from __future__ import annotations

from apps.windows.sdk.modules.regional.models import (
    KeyboardLayoutModel,
    LanguagePackModel,
    TimezoneModel,
    LocaleModel,
    UserAccountModel,
)
from apps.windows.sdk.modules.regional.manager import RegionalManager

__all__ = [
    "RegionalManager",
    "KeyboardLayoutModel",
    "LanguagePackModel",
    "TimezoneModel",
    "LocaleModel",
    "UserAccountModel",
]

