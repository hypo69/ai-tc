# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Apps Windows Api Routers - routers
# =============================================================================
# Description:
#   Единые объекты APIRouter администрирования.
#   Вынесено из router_admin.py (этап 4 оптимизации).
#
# File: routers.py
# Project: ai-tc
# Package: apps.windows.api.routers.admin
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20 16:45:00
# =============================================================================

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
router_v1 = APIRouter(prefix="/api/v1/admin", tags=["admin"])
router_apps = APIRouter(prefix="/api/v1/apps", tags=["apps"])
skills_router = APIRouter(prefix="/api/v1/skills", tags=["skills"])
plugins_router = APIRouter(prefix="/api/v1/plugins", tags=["plugins"])
