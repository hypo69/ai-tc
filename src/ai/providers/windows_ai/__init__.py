# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin AI -   Init   Module
# =============================================================================
# Description:
#   Модуль основной системы (`__init__`).
#
# Usage Examples:
#
#
# File: __init__.py
# Project: ai-windows-admin
# Package: src.ai.providers.windows_ai
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 17:35:00
# =============================================================================

"""Модуль основной системы (`__init__`)."""

from .probe import probe_windows_ai_components, is_windows_os
from .chat import WindowsAIChatBase
__all__ = ['probe_windows_ai_components', 'is_windows_os', 'WindowsAIChatBase']
