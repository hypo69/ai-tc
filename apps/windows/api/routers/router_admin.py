# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - Router Admin
# =============================================================================
# Description:
#   Агрегатор административных роутеров: эндпойнты администрирования,
#   агентов, навыков (Skills), плагинов и серверов MCP.
#
# Usage Examples:
#   Python API:
#     from apps.windows.api.routers.router_admin import init_router, init_skills_router
#
#     admin_router = init_router()
#     skills_router = init_skills_router()
#
# File: router_admin.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-03 15:45:00
# =============================================================================

from __future__ import annotations

"""Агрегатор административных роутеров: эндпойнты вынесены в подпакет ``admin`` (регистрация — через импорт)."""

from fastapi import APIRouter

from .admin import (  # noqa: F401 - импорт регистрирует эндпойнты на общих роутерах
    apps,
    google_accounts,
    instructions,
    mcp,
    plugins,
    rag_search,
    schedulers,
    skills,
)
from .admin.mcp import admin_mcp_router, mcp_router  # noqa: F401
from .admin.routers import plugins_router, router, router_v1, router_apps, skills_router  # noqa: F401


def init_router() -> APIRouter:
    """Возвращает основной административный роутер (/api/admin)."""
    return router


def init_agents_router() -> APIRouter:
    """Возвращает роутер агентов (/api/agents)."""
    from .router_agents import init_router as agents_init
    return agents_init()


def init_apps_router() -> APIRouter:
    """Возвращает роутер публичного статуса и конфигурации приложений (/api/v1/apps)."""
    return router_apps


def init_skills_router() -> APIRouter:
    """Возвращает роутер навыков агента (/api/skills)."""
    return skills_router


def init_plugins_router() -> APIRouter:
    """Возвращает роутер пользовательских плагинов (/api/plugins)."""
    return plugins_router


def init_mcp_router() -> APIRouter:
    """Возвращает роутер серверов MCP (/api/mcp)."""
    return mcp_router
