# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Core - Safe Operations
# =============================================================================
# Description:
#   Слой безопасного выполнения, симуляции (Dry-Run) и отката действий (SafeOps).
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.core.safe_ops import SafeExecutor
#
# File: safe_ops.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 17:35:00
# =============================================================================

from __future__ import annotations
"""Слой безопасного выполнения и симуляции действий (SafeOps)."""

from apps.windows.sdk.core.safe_executor import SafeExecutor

__all__ = [
    "SafeExecutor",
]

