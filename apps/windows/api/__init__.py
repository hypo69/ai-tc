# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows API - Package Root
# =============================================================================
# Description:
#   Слой 7: Внутренний FastAPI-сервис подсистемы Windows и Auto-Discovery роутеров.
#   Использует ленивый экспорт серверных фабрик для предотвращения сайд-эффектов.
#
# Usage Examples:
#   Python API:
#     from apps.windows.api import create_app, discover_and_register_routers
#
# File: __init__.py
# Project: ai-windows-admin
# Package: apps.windows.api
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-13 07:54:00
# =============================================================================

from __future__ import annotations
"""Внутренний FastAPI-сервис подсистемы Windows (Слой 7)."""

from typing import Any


def __getattr__(name: str) -> Any:
    """Ленивый импорт серверных компонентов без сайд-эффектов при импорте подпакетов."""
    if name in ("create_app", "create_internal_app", "discover_and_register_routers", "load_config", "app", "get_app"):
        from apps.windows.api.server import (
            create_app,
            create_internal_app,
            discover_and_register_routers,
            load_config,
            get_app,
        )
        mapping = {
            "create_app": create_app,
            "create_internal_app": create_internal_app,
            "discover_and_register_routers": discover_and_register_routers,
            "load_config": load_config,
            "get_app": get_app,
            "app": get_app(),
        }
        return mapping[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "create_app",
    "create_internal_app",
    "discover_and_register_routers",
    "load_config",
    "get_app",
]
