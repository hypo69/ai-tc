# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Settings SDK - Settings Verification
# =============================================================================
# Description:
#   Модуль верификации и аудита применения параметров Windows:
#   проверка фактического состояния реестра и Win32 подсистемы после команды,
#   валидация ожидаемых значений и контроль возможностей отката.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.settings.verification import SettingsVerification
#
#     verifier = SettingsVerification()
#     state = verifier.get_current_state("TASKBAR.SET_ALIGNMENT")
#     is_ok = verifier.verify("TASKBAR.SET_ALIGNMENT", "center")
#
# File: verification.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.settings
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 13:00:00
# =============================================================================

from __future__ import annotations
"""Верификатор фактического применения настроек Windows."""

from typing import Any, Dict, Optional

from apps.windows.sdk.display.display_config import DisplayConfigManager
from apps.windows.sdk.shell.taskbar_config import TaskbarConfigManager


class SettingsVerification:
    """Проверка и чтение фактического состояния настроек системы."""

    def __init__(self) -> None:
        """Инициализация модулей чтения состояния."""
        self._display_mgr = DisplayConfigManager()
        self._taskbar_mgr = TaskbarConfigManager()

    def get_current_state(self, command_id: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Считывает фактическое значение указанной настройки из операционной системы."""
        p = params or {}

        if command_id == "MONITOR.ROTATE":
            disp_id = p.get("display_id")
            if not disp_id:
                displays = self._display_mgr.list_displays()
                disp_id = displays[0].id if displays else r"\\.\DISPLAY1"
            return self._display_mgr.get_current_orientation(disp_id).value

        if command_id == "TASKBAR.SET_ALIGNMENT":
            return self._taskbar_mgr.get_alignment()

        if command_id == "TASKBAR.SET_POSITION":
            return self._taskbar_mgr.get_position()

        if command_id == "TASKBAR.SET_AUTOHIDE":
            return self._taskbar_mgr.get_auto_hide()

        return None

    def verify(self, command_id: str, expected_value: Any, params: Optional[Dict[str, Any]] = None) -> bool:
        """Сравнивает фактическое состояние в системе с ожидаемым после применения."""
        actual = self.get_current_state(command_id, params)
        if isinstance(expected_value, str) and isinstance(actual, str):
            return expected_value.lower().strip() == actual.lower().strip()
        return actual == expected_value

    def supports_rollback(self, command_id: str) -> bool:
        """Проверяет, поддерживает ли команда автоматический или ручной откат состояния."""
        rollbackable = {
            "MONITOR.ROTATE": True,
            "TASKBAR.SET_ALIGNMENT": True,
            "TASKBAR.SET_POSITION": True,
            "TASKBAR.SET_AUTOHIDE": True,
            "WINDOW.FOCUS_TRACKING": True,
        }
        return rollbackable.get(command_id, False)

