# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Taskbar Config
# =============================================================================
# Description:
#   Модульные тесты конфигурации панели задач Windows (выравнивание, автоскрытие,
#   позиционирование через StuckRects3 и срез состояния).
#
# File: test_taskbar_config.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 13:06:00
# =============================================================================

from __future__ import annotations

import pytest
from apps.windows.sdk.shell.taskbar_config import TaskbarConfigManager


def test_taskbar_config_manager_initialization() -> None:
    """Проверяет инициализацию менеджера и определение Windows 11."""
    mgr = TaskbarConfigManager()
    assert hasattr(mgr, "is_win11")
    assert isinstance(mgr.is_win11, bool)


def test_taskbar_get_current_state() -> None:
    """Проверяет получение полного среза параметров панели задач."""
    mgr = TaskbarConfigManager()
    state = mgr.get_current_state()

    assert isinstance(state, dict)
    assert "alignment" in state
    assert "alignment_label" in state
    assert state["alignment_label"] in ("left", "center")
    assert "position" in state
    assert state["position"] in ("bottom", "top", "left", "right")
    assert "auto_hide" in state
    assert isinstance(state["auto_hide"], bool)
    assert "is_win11" in state


def test_taskbar_alignment_reading_and_validation() -> None:
    """Проверяет чтение выравнивания значков панели задач."""
    mgr = TaskbarConfigManager()
    align = mgr.get_alignment()
    assert align in ("left", "center")


def test_taskbar_position_reading() -> None:
    """Проверяет чтение текущей экранной позиции панели задач."""
    mgr = TaskbarConfigManager()
    pos = mgr.get_position()
    assert pos in ("bottom", "top", "left", "right")


def test_taskbar_auto_hide_reading() -> None:
    """Проверяет считывание флага автоскрытия панели задач."""
    mgr = TaskbarConfigManager()
    auto_hide = mgr.get_auto_hide()
    assert isinstance(auto_hide, bool)

