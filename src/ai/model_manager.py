# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin AI - Model Manager Module
# =============================================================================
# Description:
#   Модуль основной системы (`model_manager`).
#
# Usage Examples:
#   Python API:
#     import src.ai.model_manager as model_manager
#
# File: model_manager.py
# Project: ai-windows-admin
# Package: src.ai
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 17:35:00
# =============================================================================

"""Модуль основной системы (`model_manager`)."""

from .orchestration.model_manager import *
from .orchestration.model_manager import _CACHED_MODELS, _normalize_model_name
