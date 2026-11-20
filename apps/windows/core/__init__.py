# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Apps Windows Core - Package Init
# =============================================================================
# Description:
#   Инициализация пакета базовых адаптеров и системных движков ai-tc.
#
# File: __init__.py
# Project: ai-tc
# Package: apps.windows.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 06:45:00
# =============================================================================

from __future__ import annotations
"""Базовые модули ядра и системных движков Windows."""

from apps.windows.core.engine_adapter import ElectronEngineAdapter

__all__ = ["ElectronEngineAdapter"]
