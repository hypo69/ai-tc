# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Shell SDK - Taskbar Config Manager
# =============================================================================
# Description:
#   Слой управления параметрами панели задач Windows (выравнивание, положение,
#   автоскрытие, поиск, значки) с глубокой интеграцией со StuckRects3,
#   Shell AppBar API и поддержкой версионных ограничений Windows 10/11.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.shell.taskbar_config import TaskbarConfigManager
#
#     mgr = TaskbarConfigManager()
#     state = mgr.get_current_state()
#     res = mgr.set_alignment("center")
#
# File: taskbar_config.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.shell
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 13:00:00
# =============================================================================

from __future__ import annotations
"""Конфигуратор параметров панели задач Windows через Shell API и реестр."""

import sys
import winreg
from typing import Any, Dict, Optional

from logger import logger
from apps.windows.sdk.modules.taskbar.core.settings_manager import (
    TaskbarSettingsManager,
    _STUCKRECTS3_KEY,
    _EXPLORER_ADVANCED_KEY,
)
from apps.windows.sdk.modules.taskbar.core.models import (
    TaskbarSettings,
    TaskbarSettingsUpdate,
)

# Позиции панели задач в StuckRects3 (байт 12)
EDGE_LEFT = 0
EDGE_TOP = 1
EDGE_RIGHT = 2
EDGE_BOTTOM = 3

POSITION_TO_EDGE = {
    "left": EDGE_LEFT,
    "top": EDGE_TOP,
    "right": EDGE_RIGHT,
    "bottom": EDGE_BOTTOM,
}

EDGE_TO_POSITION = {
    EDGE_LEFT: "left",
    EDGE_TOP: "top",
    EDGE_RIGHT: "right",
    EDGE_BOTTOM: "bottom",
}


class TaskbarConfigManager:
    """Оркестратор конфигурации панели задач Windows с поддержкой Command Registry."""

    def __init__(self) -> None:
        """Инициализация с переиспользованием системного TaskbarSettingsManager."""
        self._inner_manager = TaskbarSettingsManager()
        self.is_win11 = self._inner_manager.is_win11

    def get_position(self) -> str:
        """Считывает текущую экранную позицию панели задач (bottom, top, left, right)."""
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _STUCKRECTS3_KEY, 0, winreg.KEY_READ) as key:
                val, _ = winreg.QueryValueEx(key, "Settings")
                if isinstance(val, (bytes, bytearray)) and len(val) >= 13:
                    edge = val[12]
                    return EDGE_TO_POSITION.get(edge, "bottom")
        except Exception as exc:
            logger.debug(f"[TaskbarConfig] Ошибка чтения положения из StuckRects3: {exc}")
        return "bottom"

    def set_position(self, position: str) -> Dict[str, Any]:
        """Устанавливает позицию панели задач (bottom, top, left, right) в StuckRects3.

        Внимание: в Windows 11 (build 22000+) Microsoft зафиксировала панель задач
        снизу, поэтому позиции top/left/right имеют версионные ограничения.
        """
        pos_clean = position.lower().strip()
        if pos_clean not in POSITION_TO_EDGE:
            return {
                "success": False,
                "error": f"Недопустимая позиция '{position}'. Доступны: {list(POSITION_TO_EDGE.keys())}",
            }

        target_edge = POSITION_TO_EDGE[pos_clean]
        previous_pos = self.get_position()

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _STUCKRECTS3_KEY, 0, winreg.KEY_ALL_ACCESS) as key:
                val, val_type = winreg.QueryValueEx(key, "Settings")
                if isinstance(val, (bytes, bytearray)) and len(val) >= 13:
                    buf = bytearray(val)
                    buf[12] = target_edge
                    winreg.SetValueEx(key, "Settings", 0, val_type, bytes(buf))
                    self._inner_manager.notify_settings_changed()
                    return {
                        "success": True,
                        "position": pos_clean,
                        "previous_position": previous_pos,
                        "is_win11": self.is_win11,
                        "note": "Для полного применения может потребоваться перезапуск Explorer" if self.is_win11 else "",
                    }
        except Exception as exc:
            err_msg = f"Ошибка записи позиции в StuckRects3: {exc}"
            logger.error(f"[TaskbarConfig] {err_msg}")
            return {"success": False, "error": err_msg}

        return {"success": False, "error": "Блок данных StuckRects3 недоступен"}

    def get_alignment(self) -> str:
        """Возвращает выравнивание значков панели задач ('left' или 'center')."""
        settings = self._inner_manager.get_settings()
        return "center" if settings.alignment == 1 else "left"

    def set_alignment(self, alignment: str | int) -> Dict[str, Any]:
        """Устанавливает выравнивание значков панели задач (0/'left' или 1/'center')."""
        if isinstance(alignment, str):
            align_val = 1 if alignment.lower().strip() == "center" else 0
        else:
            align_val = 1 if alignment >= 1 else 0

        previous_align = self.get_alignment()
        res = self._inner_manager.update_settings(TaskbarSettingsUpdate(alignment=align_val))
        return {
            "success": res.get("status") == "SUCCESS",
            "alignment": "center" if align_val == 1 else "left",
            "previous_alignment": previous_align,
            "raw": res,
        }

    def get_auto_hide(self) -> bool:
        """Считывает статус автоскрытия панели задач."""
        return self._inner_manager.get_auto_hide_state()

    def set_auto_hide(self, enabled: bool) -> Dict[str, Any]:
        """Устанавливает статус автоскрытия панели задач."""
        previous_state = self.get_auto_hide()
        res = self._inner_manager.set_auto_hide_state(enabled)
        self._inner_manager.notify_settings_changed()
        return {
            "success": res,
            "auto_hide": enabled,
            "previous_auto_hide": previous_state,
        }

    def get_current_state(self) -> Dict[str, Any]:
        """Возвращает полный срез параметров панели задач для контрактов и UI."""
        base_settings = self._inner_manager.get_settings().model_dump()
        base_settings["position"] = self.get_position()
        base_settings["alignment_label"] = self.get_alignment()
        base_settings["is_win11"] = self.is_win11
        return base_settings

