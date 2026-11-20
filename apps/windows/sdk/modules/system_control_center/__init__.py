# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Apps Windows Modules System_Control_Center -   Init  
# =============================================================================
# Description:
#   Пакет микросервиса Центра управления системой Windows.
#
# Usage Examples:
#
#
# File: __init__.py
# Project: ai-tc
# Package: apps.windows.sdk.modules.system_control_center
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 05:00:00
# =============================================================================

"""Пакет микросервиса Центра управления системой Windows."""

from .router import init_router, router
__all__ = ['init_router', 'router']
