# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Commands - Package Init
# =============================================================================
# Description:
#   Пакет централизованных исполнителей команд Windows Control Plane.
#
# Usage Examples:
#   Python API:
#     from apps.windows.commands import WindowsSettingsExecutor, CommandExecutionRequest
#
# File: __init__.py
# Project: ai-windows-admin
# Package: apps.windows.commands
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 13:00:00
# =============================================================================

from __future__ import annotations
"""Пакет исполнителей команд управления Windows."""

from apps.windows.commands.windows_settings import (
    CommandExecutionRequest,
    CommandExecutionResult,
    WindowsSettingsExecutor,
)

__all__ = [
    "CommandExecutionRequest",
    "CommandExecutionResult",
    "WindowsSettingsExecutor",
]

