# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Settings SDK - Settings Catalog
# =============================================================================
# Description:
#   Декларативный каталог параметров Windows Control Catalog: описание настроек,
#   допустимых типов, ограничений, бэкендов, областей действия и уровней риска.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.settings.catalog import WINDOWS_SETTINGS, get_settings_catalog
#
#     catalog = get_settings_catalog()
#
# File: catalog.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.settings
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 13:00:00
# =============================================================================

from __future__ import annotations
"""Декларативный каталог настроек Windows Control Catalog."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SettingDefinition(BaseModel):
    """Метаданные отдельного настраиваемого параметра Windows."""
    id: str = Field(..., description="Уникальный идентификатор команды (например, MONITOR.ROTATE)")
    title: str = Field(..., description="Человекочитаемое название параметра на русском языке")
    category: str = Field(..., description="Категория: Display, Taskbar, Window, Focus, Shell")
    backend: str = Field(..., description="Основной адаптер: display_config, shell, win32, registry, powershell")
    scope: str = Field("user", description="Область действия: user, monitor, system")
    requires_admin: bool = Field(False, description="Требуются ли повышенные права администратора (Elevation)")
    capability: str = Field("safe", description="Класс возможности: safe, compat, version_dependent, admin")
    values: List[Any] = Field(default_factory=list, description="Список допустимых значений или схема типов")
    default_value: Optional[Any] = Field(None, description="Значение по умолчанию")
    description: str = Field("", description="Подробное назначение параметра")
    icon: str = Field("bi-sliders", description="Иконка Bootstrap Icons для UI")


# Единый декларативный каталог настроек системы Windows
WINDOWS_SETTINGS: Dict[str, Dict[str, Any]] = {
    "MONITOR.ROTATE": {
        "id": "MONITOR.ROTATE",
        "title": "Ориентация экрана",
        "category": "Display",
        "backend": "display_config",
        "scope": "monitor",
        "requires_admin": False,
        "capability": "compat",
        "values": [
            "landscape",
            "portrait",
            "landscape_flipped",
            "portrait_flipped",
        ],
        "default_value": "landscape",
        "description": "Поворот ориентации экрана дисплея с подтверждением и авто-откатом.",
        "icon": "bi-display",
    },
    "TASKBAR.SET_ALIGNMENT": {
        "id": "TASKBAR.SET_ALIGNMENT",
        "title": "Выравнивание значков панели задач",
        "category": "Taskbar",
        "backend": "shell",
        "scope": "user",
        "requires_admin": False,
        "capability": "safe",
        "values": ["left", "center"],
        "default_value": "center",
        "description": "Выравнивание значков приложений на панели задач Windows 11 (слева или по центру).",
        "icon": "bi-text-center",
    },
    "TASKBAR.SET_POSITION": {
        "id": "TASKBAR.SET_POSITION",
        "title": "Расположение панели задач",
        "category": "Taskbar",
        "backend": "shell",
        "scope": "user",
        "requires_admin": False,
        "capability": "version_dependent",
        "values": ["bottom", "top", "left", "right"],
        "default_value": "bottom",
        "description": "Размещение панели задач у края экрана (снизу, сверху, слева или справа).",
        "icon": "bi-layout-sidebar-inset",
    },
    "TASKBAR.SET_AUTOHIDE": {
        "id": "TASKBAR.SET_AUTOHIDE",
        "title": "Автоматическое скрытие панели задач",
        "category": "Taskbar",
        "backend": "shell",
        "scope": "user",
        "requires_admin": False,
        "capability": "safe",
        "values": [True, False],
        "default_value": False,
        "description": "Автоматически скрывать панель задач при отсутствии наведения курсора мыши.",
        "icon": "bi-eye-slash",
    },
    "WINDOW.FOCUS_TRACKING": {
        "id": "WINDOW.FOCUS_TRACKING",
        "title": "Фокус за курсором (X-Mouse)",
        "category": "Focus",
        "backend": "win32",
        "scope": "user",
        "requires_admin": False,
        "capability": "safe",
        "values": [True, False],
        "default_value": False,
        "description": "Автоматическая передача активного фокуса окну под указателем мыши (Active Window Tracking).",
        "icon": "bi-cursor-fill",
    },
}


def get_settings_catalog() -> Dict[str, SettingDefinition]:
    """Возвращает типизированный словарь определений каталога настроек."""
    return {k: SettingDefinition(**v) for k, v in WINDOWS_SETTINGS.items()}

