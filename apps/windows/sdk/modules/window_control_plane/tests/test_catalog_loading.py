# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Window Control Plane Catalog
# =============================================================================
# Description:
#   Тесты загрузки каталога параметров Window Control Plane из JSON.
#
# File: test_catalog_loading.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.window_control_plane.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-11 04:21:00
# =============================================================================

from __future__ import annotations

from apps.windows.sdk.modules.window_control_plane.catalog import (
    CATALOG_DATA_PATH,
    WindowControlPlaneCatalog,
)


def test_catalog_data_file_exists() -> None:
    """JSON-файл данных каталога присутствует рядом с модулем."""
    assert CATALOG_DATA_PATH.is_file()


def test_catalog_loads_295_unique_items() -> None:
    """Каталог содержит 295 параметров с уникальными id и индексами 1..295."""
    catalog = WindowControlPlaneCatalog()
    items = catalog.get_all()
    assert len(items) == 295
    assert len({i.id for i in items}) == 295
    assert sorted(i.index for i in items) == list(range(1, 296))


def test_catalog_lookup_by_id_and_index() -> None:
    """Поиск по id и по индексу возвращает один и тот же объект."""
    catalog = WindowControlPlaneCatalog()
    first = catalog.get_by_index(1)
    assert first is not None
    assert catalog.get_by_id(first.id) is first


def test_catalog_search_by_query() -> None:
    """Текстовый поиск находит параметры отслеживания активного окна."""
    catalog = WindowControlPlaneCatalog()
    found = catalog.search(query='active_window_tracking')
    assert any(i.id == 'window.focus.active_window_tracking' for i in found)

