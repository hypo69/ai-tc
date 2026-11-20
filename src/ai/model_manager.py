# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc AI - Model Manager Module
# =============================================================================
# Description:
#   Модуль основной системы (`model_manager`).
#
# Usage Examples:
#   Python API:
#     import src.ai.model_manager as model_manager
#
# File: model_manager.py
# Project: ai-tc
# Package: src.ai
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 05:00:00
# =============================================================================

"""Модуль основной системы (`model_manager`)."""

from .orchestration.model_manager import *
from .orchestration.model_manager import _CACHED_MODELS, _normalize_model_name
