# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Apps Windows Modules Regional - Package Root
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
# Project: ai-tc
# Package: apps.windows.sdk.modules.regional
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 05:00:00
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

