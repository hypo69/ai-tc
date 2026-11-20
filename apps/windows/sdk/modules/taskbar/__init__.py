# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Apps Windows Modules Taskbar - Init
# =============================================================================
# Description:
#   Инициализация пакета управления панелью задач и окнами Windows.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.taskbar import TaskbarController, init_router
#
# File: __init__.py
# Project: ai-tc
# Package: apps.windows.sdk.modules.taskbar
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 05:00:00
# =============================================================================

from __future__ import annotations
"""Модуль управления панелью задач (TaskbarController) и окнами Windows."""

from apps.windows.sdk.modules.taskbar.core.manager import TaskbarController
from apps.windows.sdk.modules.taskbar.router import init_router, router

__all__ = [
    "TaskbarController",
    "router",
    "init_router",
]


