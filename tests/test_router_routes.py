# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Router Routes Stability
# =============================================================================
# Description:
#   Проверяет, что набор маршрутов (метод + путь) роутеров не изменился
#   после декомпозиции модулей роутеров (этап 4 оптимизации).
#
# File: test_router_routes.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: c 2026 hypo69
# Updated: 2026-10-12 05:55:00
# =============================================================================

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.helpers.routes_snapshot import collect_routes

BASELINE = json.loads((Path(__file__).parent / 'api_baselines' / 'router_routes.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('prefix', sorted(BASELINE))
def test_routes_unchanged(prefix: str) -> None:
    """Набор маршрутов роутеров совпадает с эталоном, снятым до декомпозиции."""
    assert collect_routes(prefix) == BASELINE[prefix]

