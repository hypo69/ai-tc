# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Screen Capture - Win32 GDI Backend
# =============================================================================
# Description:
#   Высокопроизводительный нативный бэкенд экранного захвата на базе Win32 GDI,
#   BitBlt, PrintWindow (PW_RENDERFULLCONTENT) и ctypes.
#
# Usage Examples:
#   from apps.windows.vision.screen_capture.backends.gdi_backend import GdiCaptureBackend
#   backend = GdiCaptureBackend()
#   image = backend.capture_display(0)
#
# File: gdi_backend.py
# Project: ai-windows-admin
# Package: apps.windows.vision.screen_capture.backends
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 02:47:00
# =============================================================================

from __future__ import annotations
"""Win32 GDI и Desktop DC бэкенд захвата экранов и окон."""

import ctypes
from ctypes import wintypes
import os
import sys
from typing import Any, List, Optional
from PIL import Image

from logger import logger
from apps.windows.vision.screen_capture.backends.base import BaseCaptureBackend
from apps.windows.vision.screen_capture.models import (
    DisplayInfo,
    RectCoordinates,
    WindowInfo,
)

# Константы Win32 API
SRCCOPY = 0x00CC0020
PW_RENDERFULLCONTENT = 0x00000002
DIB_RGB_COLORS = 0
BI_RGB = 0


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", BITMAPINFOHEADER),
        ("bmiColors", wintypes.DWORD * 3),
    ]


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class MONITORINFOEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", wintypes.DWORD),
        ("szDevice", wintypes.WCHAR * 32),
    ]


class GdiCaptureBackend(BaseCaptureBackend):
    """Бэкенд экранного захвата через Win32 GDI и WinUser API."""

    def __init__(self) -> None:
        """Инициализирует структуры Win32 API и DPI-осведомленность."""
        self._user32 = ctypes.windll.user32 if sys.platform == "win32" else None
        self._gdi32 = ctypes.windll.gdi32 if sys.platform == "win32" else None
        self._setup_dpi_awareness()

    @property
    def name(self) -> str:
        """Уникальное наименование бэкенда."""
        return "gdi"

    def is_available(self) -> bool:
        """Проверяет платформу и доступность Win32 графических библиотек."""
        return sys.platform == "win32" and self._user32 is not None and self._gdi32 is not None

    def _setup_dpi_awareness(self) -> None:
        """Включает попиксельную DPI-осведомленность для точного масштабирования."""
        if not self._user32:
            return
        try:
            # Per-Monitor V2 DPI awareness
            ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except Exception:
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
            except Exception:
                try:
                    self._user32.SetProcessDPIAware()
                except Exception:
                    pass

    def list_displays(self) -> List[DisplayInfo]:
        """Возвращает список обнаруженных мониторов системы."""
        displays: List[DisplayInfo] = []
        if not self.is_available():
            return displays

        MonitorEnumProc = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HMONITOR,
            wintypes.HDC,
            ctypes.POINTER(RECT),
            wintypes.LPARAM,
        )

        display_index = 0

        def _enum_proc(hmonitor: Any, hdc: Any, lprect: Any, lparam: Any) -> bool:
            nonlocal display_index
            info = MONITORINFOEXW()
            info.cbSize = ctypes.sizeof(MONITORINFOEXW)
            if self._user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
                r = info.rcMonitor
                w = max(0, r.right - r.left)
                h = max(0, r.bottom - r.top)
                is_primary = bool(info.dwFlags & 1)
                dev_name = str(info.szDevice).strip() or f"\\\\.\\DISPLAY{display_index + 1}"
                displays.append(
                    DisplayInfo(
                        id=display_index,
                        name=dev_name,
                        width=w,
                        height=h,
                        is_primary=is_primary,
                        scale_factor=1.0,
                        rect=RectCoordinates(
                            left=r.left,
                            top=r.top,
                            right=r.right,
                            bottom=r.bottom,
                            width=w,
                            height=h,
                        ),
                    )
                )
                display_index += 1
            return True

        cb = MonitorEnumProc(_enum_proc)
        self._user32.EnumDisplayMonitors(None, None, cb, 0)

        # Fallback если перечисление не вернуло результатов
        if not displays:
            vx = self._user32.GetSystemMetrics(0)
            vy = self._user32.GetSystemMetrics(1)
            displays.append(
                DisplayInfo(
                    id=0,
                    name=r"\\.\DISPLAY1",
                    width=vx,
                    height=vy,
                    is_primary=True,
                    scale_factor=1.0,
                    rect=RectCoordinates(left=0, top=0, right=vx, bottom=vy, width=vx, height=vy),
                )
            )

        return displays

    def list_windows(self) -> List[WindowInfo]:
        """Возвращает список активных окон с заголовками и координатами."""
        windows: List[WindowInfo] = []
        if not self.is_available():
            return windows

        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def _enum_windows_proc(hwnd: int, lparam: Any) -> bool:
            if not self._user32.IsWindowVisible(hwnd):
                return True

            length = self._user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True

            buffer = ctypes.create_unicode_buffer(length + 1)
            self._user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value.strip()

            if not title:
                return True

            # Получаем координаты
            rect = RECT()
            self._user32.GetWindowRect(hwnd, ctypes.byref(rect))
            w = max(0, rect.right - rect.left)
            h = max(0, rect.bottom - rect.top)

            # Пропуск скрытых или микроскопических окон
            if w <= 10 or h <= 10:
                return True

            # PID и имя процесса
            pid = wintypes.DWORD()
            self._user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            proc_id = pid.value
            proc_name = self._resolve_process_name(proc_id)

            # Проверка зависания
            is_hung = bool(self._user32.IsHungAppWindow(hwnd))
            is_minimized = bool(self._user32.IsIconic(hwnd))

            windows.append(
                WindowInfo(
                    id=int(hwnd),
                    title=title,
                    process_name=proc_name,
                    pid=proc_id,
                    width=w,
                    height=h,
                    rect=RectCoordinates(
                        left=rect.left,
                        top=rect.top,
                        right=rect.right,
                        bottom=rect.bottom,
                        width=w,
                        height=h,
                    ),
                    is_minimized=is_minimized,
                    is_visible=True,
                    is_hung=is_hung,
                )
            )
            return True

        cb = WNDENUMPROC(_enum_windows_proc)
        self._user32.EnumWindows(cb, 0)
        return windows

    def _resolve_process_name(self, pid: int) -> str:
        """Определяет имя исполняемого файла процесса по его PID."""
        if pid <= 0:
            return ""
        try:
            import psutil
            return psutil.Process(pid).name()
        except Exception:
            return ""

    def capture_display(self, display_id: int) -> Optional[Image.Image]:
        """Захватывает указанный монитор через Desktop DC и BitBlt."""
        displays = self.list_displays()
        target_display = next((d for d in displays if d.id == display_id), None)
        if not target_display and displays:
            target_display = displays[0]
        if not target_display:
            return None

        r = target_display.rect
        return self._capture_screen_rect(r.left, r.top, r.width, r.height)

    def capture_window(self, window_id: int) -> Optional[Image.Image]:
        """Захватывает окно по его HWND, используя PrintWindow с fallback на BitBlt."""
        if not self.is_available():
            return None

        hwnd = wintypes.HWND(window_id)
        if not self._user32.IsWindow(hwnd):
            logger.warning(f"[GdiCaptureBackend] Некорректный HWND окна: {window_id}")
            return None

        rect = RECT()
        self._user32.GetWindowRect(hwnd, ctypes.byref(rect))
        w = max(0, rect.right - rect.left)
        h = max(0, rect.bottom - rect.top)
        if w == 0 or h == 0:
            return None

        hdc_screen = self._user32.GetWindowDC(hwnd)
        if not hdc_screen:
            return None

        hdc_mem = self._gdi32.CreateCompatibleDC(hdc_screen)
        hbmp = self._gdi32.CreateCompatibleBitmap(hdc_screen, w, h)
        h_old_bmp = self._gdi32.SelectObject(hdc_mem, hbmp)

        img: Optional[Image.Image] = None
        try:
            # 1. Попытка через PrintWindow (PW_RENDERFULLCONTENT)
            pw_success = self._user32.PrintWindow(hwnd, hdc_mem, PW_RENDERFULLCONTENT)
            if not pw_success:
                # 2. Fallback на прямой BitBlt из DC окна
                self._gdi32.BitBlt(hdc_mem, 0, 0, w, h, hdc_screen, 0, 0, SRCCOPY)

            img = self._hbitmap_to_pil(hdc_mem, hbmp, w, h)
        except Exception as exc:
            logger.error(f"[GdiCaptureBackend] Ошибка захвата окна {window_id}: {exc}")
        finally:
            self._gdi32.SelectObject(hdc_mem, h_old_bmp)
            self._gdi32.DeleteObject(hbmp)
            self._gdi32.DeleteDC(hdc_mem)
            self._user32.ReleaseDC(hwnd, hdc_screen)

        return img

    def _capture_screen_rect(self, x: int, y: int, width: int, height: int) -> Optional[Image.Image]:
        """Захватывает произвольный прямоугольный фрагмент виртуального экрана."""
        if width <= 0 or height <= 0 or not self.is_available():
            return None

        hdc_screen = self._user32.GetDC(None)
        if not hdc_screen:
            return None

        hdc_mem = self._gdi32.CreateCompatibleDC(hdc_screen)
        hbmp = self._gdi32.CreateCompatibleBitmap(hdc_screen, width, height)
        h_old_bmp = self._gdi32.SelectObject(hdc_mem, hbmp)

        img: Optional[Image.Image] = None
        try:
            self._gdi32.BitBlt(hdc_mem, 0, 0, width, height, hdc_screen, x, y, SRCCOPY)
            img = self._hbitmap_to_pil(hdc_mem, hbmp, width, height)
        except Exception as exc:
            logger.error(f"[GdiCaptureBackend] Ошибка BitBlt экрана: {exc}")
        finally:
            self._gdi32.SelectObject(hdc_mem, h_old_bmp)
            self._gdi32.DeleteObject(hbmp)
            self._gdi32.DeleteDC(hdc_mem)
            self._user32.ReleaseDC(None, hdc_screen)

        return img

    def _hbitmap_to_pil(self, hdc: Any, hbmp: Any, width: int, height: int) -> Optional[Image.Image]:
        """Конвертирует Win32 HBITMAP в объект PIL Image без утечек памяти."""
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = width
        # Отрицательная высота указывает формат top-down DIB
        bmi.bmiHeader.biHeight = -height
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = BI_RGB

        buffer_len = width * height * 4
        buffer = ctypes.create_string_buffer(buffer_len)

        lines = self._gdi32.GetDIBits(
            hdc,
            hbmp,
            0,
            height,
            buffer,
            ctypes.byref(bmi),
            DIB_RGB_COLORS,
        )

        if lines == 0:
            return None

        # Формат буфера BGRA, конвертируем в RGB
        image = Image.frombuffer("RGBA", (width, height), buffer, "raw", "BGRA", 0, 1)
        return image.convert("RGB")
