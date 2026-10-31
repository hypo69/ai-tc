# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - Router Tc
# =============================================================================
# Description:
#   FastAPI REST эндпоинты для управления активной AI-моделью, провайдером
#
# Usage Examples:
#   Python API:
#     from apps.windows.api.routers.router_tc import TcModelInstructionPayload
#
#     service = TcModelInstructionPayload()
#
# File: router_tc.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 17:35:00
# =============================================================================

from __future__ import annotations
"""FastAPI REST эндпоинты для управления активной AI-моделью, провайдером и расширенной телеметрией."""


from fastapi import APIRouter

from apps.windows.api.routers.tc.endpoints_ai import register_ai_endpoints
from apps.windows.api.routers.tc.endpoints_system import register_system_endpoints
from apps.windows.api.routers.tc.endpoints_telemetry import register_telemetry_endpoints
from apps.windows.api.routers.tc.state import get_collector, get_diagnostician  # noqa: F401


def init_router() -> APIRouter:
    """Инициализация FastAPI роутера Test Computer (TC).

    Returns:
        APIRouter: Роутер с эндпойнтами управления TC.
    """
    router = APIRouter(prefix="/api/v1/tc", tags=["Test Computer (TC)"])
    register_ai_endpoints(router)
    register_system_endpoints(router)
    register_telemetry_endpoints(router)
    return router

