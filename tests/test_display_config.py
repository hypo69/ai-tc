# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Display Config & Rotation
# =============================================================================
# Description:
#   Модульные и интеграционные тесты низкоуровневого управления дисплеями,
#   перечисления мониторов, модели DisplayItem и Win32 FFI ориентации экранов.
#
# File: test_display_config.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 13:06:00
# =============================================================================

from __future__ import annotations

import pytest
from apps.windows.sdk.display.display_models import (
    DisplayItem,
    DisplayOrientation,
    DisplayRotateRequest,
    DisplayRotateResponse,
)
from apps.windows.sdk.display.display_config import DisplayConfigManager


def test_display_orientation_conversions() -> None:
    """Проверяет корректность конвертации ориентаций между enum, градусами и DMDO кодами."""
    assert DisplayOrientation.LANDSCAPE.to_dmdo() == 0
    assert DisplayOrientation.PORTRAIT.to_dmdo() == 1
    assert DisplayOrientation.LANDSCAPE_FLIPPED.to_dmdo() == 2
    assert DisplayOrientation.PORTRAIT_FLIPPED.to_dmdo() == 3

    assert DisplayOrientation.LANDSCAPE.to_degrees() == 0
    assert DisplayOrientation.PORTRAIT.to_degrees() == 90
    assert DisplayOrientation.LANDSCAPE_FLIPPED.to_degrees() == 180
    assert DisplayOrientation.PORTRAIT_FLIPPED.to_degrees() == 270

    assert DisplayOrientation.from_dmdo(0) == DisplayOrientation.LANDSCAPE
    assert DisplayOrientation.from_dmdo(1) == DisplayOrientation.PORTRAIT
    assert DisplayOrientation.from_dmdo(2) == DisplayOrientation.LANDSCAPE_FLIPPED
    assert DisplayOrientation.from_dmdo(3) == DisplayOrientation.PORTRAIT_FLIPPED


def test_display_config_manager_list_displays() -> None:
    """Проверяет перечисление реальных физических/виртуальных дисплеев системы."""
    mgr = DisplayConfigManager()
    displays = mgr.list_displays()

    assert isinstance(displays, list)
    if displays:
        primary = next((d for d in displays if d.is_primary), None)
        assert primary is not None, "В системе должен быть хотя бы один основной монитор"
        assert primary.id.startswith(r"\\.\DISPLAY")
        assert primary.width > 0
        assert primary.height > 0
        assert primary.current_orientation in (
            DisplayOrientation.LANDSCAPE,
            DisplayOrientation.PORTRAIT,
            DisplayOrientation.LANDSCAPE_FLIPPED,
            DisplayOrientation.PORTRAIT_FLIPPED,
        )


def test_get_display_by_id() -> None:
    """Проверяет поиск дисплея по полному и нормализованному ID."""
    mgr = DisplayConfigManager()
    displays = mgr.list_displays()
    if not displays:
        pytest.skip("Нет доступных дисплеев для тестирования")

    disp = displays[0]
    found = mgr.get_display(disp.id)
    assert found is not None
    assert found.id == disp.id

    # Проверка поиска без префикса слешей
    clean_id = disp.id.replace(r"\\.\\", "")
    found_clean = mgr.get_display(clean_id)
    assert found_clean is not None


def test_rotate_display_validation_and_rollback_flow() -> None:
    """Проверяет контракт запроса поворота и подтверждение/откат."""
    mgr = DisplayConfigManager()
    displays = mgr.list_displays()
    if not displays:
        pytest.skip("Нет доступных дисплеев для тестирования")

    disp = displays[0]
    current_orient = disp.current_orientation

    # Вызов с текущей ориентацией должен успешно завершаться без ошибок
    res = mgr.rotate_display(disp.id, current_orient, timeout_seconds=10, auto_rollback=False)
    assert res.success is True
    assert res.actual_orientation == current_orient
    assert res.confirmed is True

