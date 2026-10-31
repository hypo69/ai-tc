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
# Package: src.ai.providers.gemini_cli
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 17:35:00
# =============================================================================

"""Модуль основной системы (`__init__`)."""

from .client import GeminiCliProvider, GeminiCliResponse
from .chat import GeminiCliChatBase
__all__ = ['GeminiCliProvider', 'GeminiCliResponse', 'GeminiCliChatBase']
