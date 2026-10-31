# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - Router About System
# =============================================================================
# Description:
#   FastAPI REST эндпоинты для панели "О Системе" (About System Panel)
#   с прямыми SQL-запросами к SQLite базе данных telemetry.db.
#
# Usage Examples:
#   Python API:
#     from apps.windows.api.routers.router_about_system import AboutSystemPanelOverviewResponse
#
#     service = AboutSystemPanelOverviewResponse()
#
# File: router_about_system.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 17:35:00
# =============================================================================

from __future__ import annotations
"""FastAPI REST эндпоинты для панели 'О Системе' из базы данных telemetry.db."""


from fastapi import APIRouter

from apps.windows.telemetry.sqlite import TelemetryStorage

from .about_system.endpoints_overview import register_overview_endpoints
from .about_system.endpoints_panels import register_panel_endpoints
from .about_system.endpoints_system import register_system_action_endpoints


def init_router() -> APIRouter:
    """Инициализирует FastAPI роутер панели 'О системе'.

    Returns:
        APIRouter: Роутер с эндпойнтами /api/v1/about-system/* и /api/v1/system/*.
    """
    router = APIRouter(tags=["About System Panel"])
    storage = TelemetryStorage.get_instance(read_only=True)
    register_overview_endpoints(router, storage)
    register_panel_endpoints(router, storage)
    register_system_action_endpoints(router, storage)
    return router

