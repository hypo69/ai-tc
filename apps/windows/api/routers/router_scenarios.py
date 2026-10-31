# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - Router Scenarios
# =============================================================================
# Description:
#   FastAPI REST эндпоинты для запуска и мониторинга автоматизированных сценариев
#
# Usage Examples:
#   Python API:
#     from apps.windows.api.routers.router_scenarios import ScenarioQuestionsConfig
#
#     service = ScenarioQuestionsConfig()
#
# File: router_scenarios.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 17:35:00
# =============================================================================

from __future__ import annotations
"""FastAPI REST эндпоинты для запуска и мониторинга автоматизированных сценариев"""


from .scenarios.endpoints import init_router  # noqa: F401
from .scenarios.models import ScenarioRunRequest  # noqa: F401

