# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - Admin Package
# =============================================================================
# Description:
#   Подпакет эндпойнтов администрирования.
#
# File: __init__.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers.admin
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-30 13:25:00
# =============================================================================

"""Подпакет эндпойнтов администрирования (вынесен из router_admin.py)."""

from . import (  # noqa: F401
    apps,
    google_accounts,
    instructions,
    mcp,
    plugins,
    rag_search,
    schedulers,
    skills,
)

__all__ = [
    "apps",
    "google_accounts",
    "instructions",
    "mcp",
    "plugins",
    "rag_search",
    "schedulers",
    "skills",
]

