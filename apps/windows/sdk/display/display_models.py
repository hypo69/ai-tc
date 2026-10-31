# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Display SDK - Display Models
# =============================================================================
# Description:
#   Pydantic-модели данных для мониторов, геометрии экранов, параметров ориентации
#   и контрактов команд управления дисплеями Windows.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.display.display_models import DisplayItem, DisplayOrientation
#
# File: display_models.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.display
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 13:00:00
# =============================================================================

from __future__ import annotations
"""Модели данных мониторов и ориентации дисплеев Windows."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DisplayOrientation(str, Enum):
    """Ориентация экрана дисплея."""
    LANDSCAPE = "landscape"                     # Альбомная (0 градусов)
    PORTRAIT = "portrait"                       # Портретная (90 градусов)
    LANDSCAPE_FLIPPED = "landscape_flipped"     # Альбомная перевёрнутая (180 градусов)
    PORTRAIT_FLIPPED = "portrait_flipped"       # Портретная перевёрнутая (270 градусов)

    @classmethod
    def from_dmdo(cls, dmdo_value: int) -> DisplayOrientation:
        """Преобразует числовое значение Win32 DMDO_* в DisplayOrientation."""
        mapping = {
            0: cls.LANDSCAPE,
            1: cls.PORTRAIT,
            2: cls.LANDSCAPE_FLIPPED,
            3: cls.PORTRAIT_FLIPPED,
        }
        return mapping.get(dmdo_value, cls.LANDSCAPE)

    def to_dmdo(self) -> int:
        """Преобразует ориентацию в числовой код Win32 DMDO_*."""
        mapping = {
            self.LANDSCAPE: 0,
            self.PORTRAIT: 1,
            self.LANDSCAPE_FLIPPED: 2,
            self.PORTRAIT_FLIPPED: 3,
        }
        return mapping.get(self, 0)

    def to_degrees(self) -> int:
        """Возвращает угол поворота в градусах."""
        mapping = {
            self.LANDSCAPE: 0,
            self.PORTRAIT: 90,
            self.LANDSCAPE_FLIPPED: 180,
            self.PORTRAIT_FLIPPED: 270,
        }
        return mapping.get(self, 0)


class DisplayItem(BaseModel):
    """Информация о физическом или виртуальном мониторе Windows."""
    id: str = Field(..., description="Системный идентификатор адаптера (например, \\\\.\\DISPLAY1)")
    name: str = Field("", description="Имя видеоадаптера или монитора")
    adapter_string: str = Field("", description="Название графического ускорителя (GPU)")
    is_primary: bool = Field(False, description="Признак основного дисплея")
    is_attached: bool = Field(True, description="Подключен ли дисплей к рабочему столу")
    current_orientation: DisplayOrientation = Field(
        DisplayOrientation.LANDSCAPE, description="Текущая ориентация экрана"
    )
    width: int = Field(0, description="Текущая ширина в пикселях")
    height: int = Field(0, description="Текущая высота в пикселях")
    frequency_hz: int = Field(0, description="Частота обновления в Гц")
    supported_orientations: List[DisplayOrientation] = Field(
        default_factory=lambda: [
            DisplayOrientation.LANDSCAPE,
            DisplayOrientation.PORTRAIT,
            DisplayOrientation.LANDSCAPE_FLIPPED,
            DisplayOrientation.PORTRAIT_FLIPPED,
        ],
        description="Поддерживаемые режимы ориентации"
    )


class DisplayRotateRequest(BaseModel):
    """Запрос на поворот ориентации дисплея."""
    display_id: str = Field(..., description="Идентификатор дисплея (например, \\\\.\\DISPLAY1 или DISPLAY1)")
    orientation: DisplayOrientation = Field(..., description="Желаемая ориентация экрана")
    timeout_seconds: int = Field(15, description="Таймаут ожидания подтверждения перед автоматическим откатом")
    auto_rollback: bool = Field(True, description="Автоматически восстанавливать прежний режим при отсутствии подтверждения")


class DisplayRotateResponse(BaseModel):
    """Результат выполнения поворота экрана."""
    success: bool = Field(..., description="Статус успешности операции")
    display_id: str = Field(..., description="Идентификатор целевого дисплея")
    requested_orientation: DisplayOrientation = Field(..., description="Запрошенная ориентация")
    actual_orientation: DisplayOrientation = Field(..., description="Фактическая ориентация после вызова API")
    confirmed: bool = Field(False, description="Подтверждена ли смена ориентации пользователем")
    pending_rollback: bool = Field(False, description="Ожидает ли таймер авто-отката подтверждения")
    timeout_seconds: int = Field(0, description="Оставшееся время таймаута")
    error: Optional[str] = Field(None, description="Текст ошибки при сбое")

