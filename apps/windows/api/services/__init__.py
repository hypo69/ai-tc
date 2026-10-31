# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Services - Package Init
# =============================================================================
# Description:
#   Пакет системных сервисов API (WikiLLM, Sysmon Inspector).
#
# File: __init__.py
# Project: ai-windows-admin
# Package: apps.windows.api.services
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-13 15:49:00
# =============================================================================

from __future__ import annotations
"""Пакет системных сервисов API."""

from apps.windows.api.services.wikillm_service import WikiLLMService
from apps.windows.api.services.sysmon_inspector import SysmonInspector

__all__ = ["WikiLLMService", "SysmonInspector"]

