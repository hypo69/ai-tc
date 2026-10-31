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
# Package: src.ai.providers.ollama
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 17:35:00
# =============================================================================

"""Модуль основной системы (`__init__`)."""

from .client import OllamaClient
from .chat import OllamaChatBase
__all__ = ['OllamaClient', 'OllamaChatBase']
