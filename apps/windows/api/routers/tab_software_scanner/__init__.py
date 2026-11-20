# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Routers - Tab Software Scanner Package
# =============================================================================
# Description:
#   Пакет специализированных REST API роутеров для вкладки tab-software-scanner.
#
# File: __init__.py
# Project: ai-tc
# Package: apps.windows.api.routers.tab_software_scanner
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 05:00:00
# =============================================================================

from __future__ import annotations

from .router_software_ai import router, init_router

__all__ = ["router", "init_router"]

