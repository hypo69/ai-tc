# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Display SDK - Package Init
# =============================================================================
# Description:
#   Пакет низкоуровневого управления дисплеями, ориентацией экранов и мульти-мониторной
#   подсистемой Windows.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.display import DisplayConfigManager, DisplayItem, DisplayOrientation
#
# File: __init__.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.display
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 13:00:00
# =============================================================================

from __future__ import annotations
"""Пакет управления мониторами и ориентацией экранов Windows."""

from apps.windows.sdk.display.display_config import DisplayConfigManager
from apps.windows.sdk.display.display_models import (
    DisplayItem,
    DisplayOrientation,
    DisplayRotateRequest,
    DisplayRotateResponse,
)

__all__ = [
    "DisplayConfigManager",
    "DisplayItem",
    "DisplayOrientation",
    "DisplayRotateRequest",
    "DisplayRotateResponse",
]

