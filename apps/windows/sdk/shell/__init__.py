# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Shell SDK - Package Init
# =============================================================================
# Description:
#   Пакет управления элементами оболочки Windows (Taskbar, Start Menu, Explorer).
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.shell import TaskbarConfigManager
#
# File: __init__.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.shell
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 13:00:00
# =============================================================================

from __future__ import annotations
"""Пакет управления оболочкой Windows Shell."""

from apps.windows.sdk.shell.taskbar_config import TaskbarConfigManager

__all__ = ["TaskbarConfigManager"]

