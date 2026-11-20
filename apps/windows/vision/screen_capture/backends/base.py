# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Screen Capture - Base Backend
# =============================================================================
# Description:
#   Абстрактный интерфейс для бэкендов экранного захвата (Windows.Graphics.Capture,
#   DirectX DXGI Desktop Duplication, Win32 GDI).
#
# Usage Examples:
#   class MyBackend(BaseCaptureBackend): ...
#
# File: base.py
# Project: ai-windows-admin
# Package: apps.windows.vision.screen_capture.backends
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 02:46:00
# =============================================================================

from __future__ import annotations
"""Базовый абстрактный класс для бэкендов экранного захвата."""

from abc import ABC, abstractmethod
from typing import List, Optional
from PIL import Image

from apps.windows.vision.screen_capture.models import DisplayInfo, WindowInfo


class BaseCaptureBackend(ABC):
    """Абстрактный класс бэкенда графического захвата."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Возвращает уникальное имя бэкенда (например, 'wgc', 'dxgi', 'gdi')."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Проверяет доступность бэкенда в текущей операционной системе."""
        pass

    @abstractmethod
    def list_displays(self) -> List[DisplayInfo]:
        """Возвращает список обнаруженных физических и виртуальных дисплеев."""
        pass

    @abstractmethod
    def list_windows(self) -> List[WindowInfo]:
        """Возвращает список видимых окон верхнего уровня."""
        pass

    @abstractmethod
    def capture_display(self, display_id: int) -> Optional[Image.Image]:
        """Выполняет захват указанного монитора и возвращает PIL Image."""
        pass

    @abstractmethod
    def capture_window(self, window_id: int) -> Optional[Image.Image]:
        """Выполняет захват указанного окна (по HWND) и возвращает PIL Image."""
        pass
