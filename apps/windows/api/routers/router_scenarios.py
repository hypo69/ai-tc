# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Apps Windows Api Routers - Router Scenarios
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
# Project: ai-tc
# Package: apps.windows.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 05:00:00
# =============================================================================

from __future__ import annotations
"""FastAPI REST эндпоинты для запуска и мониторинга автоматизированных сценариев"""


from .scenarios.endpoints import init_router  # noqa: F401
from .scenarios.models import ScenarioRunRequest  # noqa: F401

