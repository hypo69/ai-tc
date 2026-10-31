# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api - Internal App
# =============================================================================
# Description:
#   Главный FastAPI сервер управления подсистемой Windows AI-Windows-Admin.
#
# Usage Examples:
#   Python API:
#     from apps.windows.api.internal_app import load_config, create_internal_app
#
#     app = create_internal_app()
#
# File: internal_app.py
# Project: ai-windows-admin
# Package: apps.windows.api
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 17:35:00
# =============================================================================

from __future__ import annotations
"""Главный FastAPI сервер управления подсистемой Windows AI-Windows-Admin."""

from apps.windows.api.server import (
    create_app,
    create_internal_app,
    discover_and_register_routers,
    load_config,
    load_tc_config,
)

__all__ = [
    'create_app',
    'create_internal_app',
    'discover_and_register_routers',
    'load_config',
    'load_tc_config',
]


