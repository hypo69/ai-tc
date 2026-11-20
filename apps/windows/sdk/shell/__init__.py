# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Shell SDK - Package Init
# =============================================================================
# Description:
#   Пакет управления элементами оболочки Windows (Taskbar, Start Menu, Explorer).
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.shell import TaskbarConfigManager
#
# File: __init__.py
# Project: ai-tc
# Package: apps.windows.sdk.shell
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 05:00:00
# =============================================================================

from __future__ import annotations
"""Пакет управления оболочкой Windows Shell."""

from apps.windows.sdk.shell.taskbar_config import TaskbarConfigManager

__all__ = ["TaskbarConfigManager"]

