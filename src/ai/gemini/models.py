# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc AI - Models Module
# =============================================================================
# Description:
#   Модуль основной системы (`models`).
#
# Usage Examples:
#   Python API:
#     import src.ai.gemini.models as models
#
# File: models.py
# Project: ai-tc
# Package: src.ai.gemini
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 05:00:00
# =============================================================================

"""Модуль основной системы (`models`)."""

from .core import load_unsupported_models, add_unsupported_model, GoogleGenerativeAICore
__all__ = ['load_unsupported_models', 'add_unsupported_model', 'GoogleGenerativeAICore']
