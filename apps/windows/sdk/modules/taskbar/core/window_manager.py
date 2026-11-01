# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Modules Taskbar - Window Manager
# =============================================================================
# Description:
#   Управление окнами Windows рабочего стола и панели задач через Win32 API.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.taskbar.core.window_manager import WindowManager
#
#     mgr = WindowManager()
#     windows = mgr.list_windows()
#
# File: window_manager.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.taskbar.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 11:57:30
# =============================================================================

from __future__ import annotations
"""Управление окнами рабочего стола через Win32 User32 и DWM API."""

import ctypes
from ctypes import wintypes
import os
from typing import Any, Callable, Dict, List, Optional, Tuple
import psutil

from logger import logger
from apps.windows.sdk.modules.taskbar.core.models import (
    WindowBatchActionRequest,
    WindowItem,
    WindowMoveRequest,
    WindowRect,
)

# Win32 константы управления показом окон
SW_HIDE = 0
SW_SHOWNORMAL = 1
SW_SHOWMINIMIZED = 2
SW_MAXIMIZE = 3
SW_SHOW = 5
SW_MINIMIZE = 6
SW_RESTORE = 9

WM_CLOSE = 0x0010
GW_OWNER = 4

# Стили окон GWL_STYLE и GWL_EXSTYLE
GWL_STYLE = -16
GWL_EXSTYLE = -20

WS_POPUP = 0x80000000
WS_CHILD = 0x40000000
WS_MINIMIZE = 0x20000000
WS_VISIBLE = 0x10000000
WS_DISABLED = 0x08000000
WS_CLIPSIBLINGS = 0x04000000
WS_CLIPCHILDREN = 0x02000000
WS_MAXIMIZE = 0x01000000
WS_CAPTION = 0x00C00000
WS_BORDER = 0x00800000
WS_SYSMENU = 0x00080000
WS_THICKFRAME = 0x00040000

WS_EX_TOPMOST = 0x00000008
WS_EX_ACCEPTFILES = 0x00000010
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_WINDOWEDGE = 0x00000100
WS_EX_CLIENTEDGE = 0x00000200
WS_EX_APPWINDOW = 0x00040000
WS_EX_LAYERED = 0x00080000
WS_EX_COMPOSITED = 0x02000000
WS_EX_NOACTIVATE = 0x08000000

# Callback prototype для EnumWindows
WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)


class RECT(ctypes.Structure):
    """Структура прямоугольника Win32 RECT."""
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class WindowManager:
    """Управление окнами верхнего уровня операционной системы Windows."""

    def __init__(self) -> None:
        """Инициализация менеджера окон."""
        self._user32 = ctypes.windll.user32
        self._kernel32 = ctypes.windll.kernel32

    def _get_process_name(self, pid: int) -> str:
        """Получение имени процесса по PID."""
        if pid <= 0:
            return ""
        try:
            return psutil.Process(pid).name()
        except Exception:
            return ""

    def _get_process_telemetry(
        self,
        pid: int,
        proc_cache: Optional[Dict[int, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Сбор расширенной телеметрии процесса по PID с поддержкой кэширования."""
        default_data: Dict[str, Any] = {
            "process_name": "",
            "parent_pid": 0,
            "parent_process_name": "",
            "exe_path": "",
            "cmdline": "",
            "username": "",
            "process_status": "",
            "memory_mb": 0.0,
            "threads_count": 0,
        }
        if pid <= 0:
            return default_data
        if proc_cache is not None and pid in proc_cache:
            return proc_cache[pid]

        data = dict(default_data)
        try:
            proc = psutil.Process(pid)
            with proc.oneshot():
                data["process_name"] = proc.name() or ""
                try:
                    data["parent_pid"] = proc.ppid() or 0
                except Exception:
                    pass
                try:
                    data["exe_path"] = proc.exe() or ""
                except Exception:
                    pass
                try:
                    cmd_parts = proc.cmdline()
                    data["cmdline"] = " ".join(cmd_parts) if cmd_parts else data["exe_path"]
                except Exception:
                    data["cmdline"] = data["exe_path"]
                try:
                    data["username"] = proc.username() or ""
                except Exception:
                    pass
                try:
                    data["process_status"] = proc.status() or ""
                except Exception:
                    pass
                try:
                    mem = proc.memory_info()
                    data["memory_mb"] = round(mem.rss / (1024 * 1024), 1)
                except Exception:
                    pass
                try:
                    data["threads_count"] = proc.num_threads() or 0
                except Exception:
                    pass

            ppid = data["parent_pid"]
            if ppid > 0:
                try:
                    data["parent_process_name"] = psutil.Process(ppid).name() or ""
                except Exception:
                    pass
        except Exception:
            pass

        if proc_cache is not None:
            proc_cache[pid] = data
        return data

    @staticmethod
    def _decode_window_styles(style: int, ex_style: int) -> List[str]:
        """Декодирование битовых масок GWL_STYLE и GWL_EXSTYLE в список флагов Win32."""
        flags: List[str] = []
        style_u = style & 0xFFFFFFFF
        ex_u = ex_style & 0xFFFFFFFF

        if style_u & WS_VISIBLE:
            flags.append("WS_VISIBLE")
        if style_u & WS_POPUP:
            flags.append("WS_POPUP")
        if style_u & WS_CHILD:
            flags.append("WS_CHILD")
        if style_u & WS_MINIMIZE:
            flags.append("WS_MINIMIZE")
        if style_u & WS_MAXIMIZE:
            flags.append("WS_MAXIMIZE")
        if style_u & WS_DISABLED:
            flags.append("WS_DISABLED")
        if (style_u & WS_CAPTION) == WS_CAPTION:
            flags.append("WS_CAPTION")
        if style_u & WS_SYSMENU:
            flags.append("WS_SYSMENU")
        if style_u & WS_THICKFRAME:
            flags.append("WS_THICKFRAME")

        if ex_u & WS_EX_TOPMOST:
            flags.append("WS_EX_TOPMOST")
        if ex_u & WS_EX_TOOLWINDOW:
            flags.append("WS_EX_TOOLWINDOW")
        if ex_u & WS_EX_APPWINDOW:
            flags.append("WS_EX_APPWINDOW")
        if ex_u & WS_EX_LAYERED:
            flags.append("WS_EX_LAYERED")
        if ex_u & WS_EX_TRANSPARENT:
            flags.append("WS_EX_TRANSPARENT")
        if ex_u & WS_EX_NOACTIVATE:
            flags.append("WS_EX_NOACTIVATE")
        if ex_u & WS_EX_ACCEPTFILES:
            flags.append("WS_EX_ACCEPTFILES")
        if ex_u & WS_EX_COMPOSITED:
            flags.append("WS_EX_COMPOSITED")

        return flags

    @staticmethod
    def _classify_window_role(
        rect: WindowRect,
        is_minimized: bool,
        is_topmost: bool,
        is_tool_window: bool,
        is_layered: bool,
        is_no_activate: bool,
        owner_hwnd: int,
        style_flags: List[str],
    ) -> str:
        """Эвристическая классификация назначения окна по его габаритам и стилям Win32."""
        w, h = rect.width, rect.height
        if not is_minimized and (w <= 64 and h <= 64):
            return f"Фоновое техническое микро-окно ({w}×{h} пикс., перехват событий/хоткеев/IPC)"
        if not is_minimized and (rect.right <= 0 or rect.bottom <= 0 or rect.left < -10000 or rect.top < -10000):
            return "Скрытое закадровое окно (Off-screen координатная область)"
        if is_topmost and is_layered and ("WS_EX_TRANSPARENT" in style_flags or is_no_activate):
            return "Прозрачный экранный оверлей поверх всех окон (Topmost Layered Overlay)"
        if is_topmost and is_tool_window:
            return "Всплывающая системная/инструментальная панель поверх окон (Topmost ToolWindow)"
        if is_tool_window:
            return "Вспомогательное инструментальное окно (ToolWindow)"
        if is_topmost:
            return "Окно с приоритетом поверх остальных (Topmost Window)"
        if "WS_POPUP" in style_flags and "WS_CAPTION" not in style_flags:
            return "Безрамочное всплывающее окно / Flyout-панель (Popup Window)"
        if owner_hwnd > 0:
            return "Дочернее / диалоговое окно приложения (Owned Window)"
        return "Стандартное прикладное окно рабочего стола (Top-Level Application Window)"

    def _get_window_rect(self, hwnd: int) -> WindowRect:
        """Получение координат и размеров окна по его HWND."""
        r = RECT()
        try:
            if self._user32.GetWindowRect(hwnd, ctypes.byref(r)):
                w = max(0, r.right - r.left)
                h = max(0, r.bottom - r.top)
                return WindowRect(
                    left=r.left,
                    top=r.top,
                    right=r.right,
                    bottom=r.bottom,
                    width=w,
                    height=h,
                )
        except Exception:
            pass
        return WindowRect()

    def get_taskbar_rect(self) -> WindowRect:
        """Возвращает координаты и габариты главной панели задач Windows (Shell_TrayWnd)."""
        try:
            hwnd = self._user32.FindWindowW("Shell_TrayWnd", None)
            if hwnd:
                return self._get_window_rect(hwnd)
        except Exception as exc:
            logger.debug(f"[WindowManager] Ошибка определения габаритов Taskbar: {exc}")
        return WindowRect()

    def get_foreground_window(self) -> Optional[WindowItem]:
        """Возвращает информацию о текущем активном окне переднего плана."""
        try:
            hwnd = self._user32.GetForegroundWindow()
            if hwnd:
                return self.get_window_by_hwnd(hwnd)
        except Exception as exc:
            logger.debug(f"[WindowManager] Ошибка GetForegroundWindow: {exc}")
        return None

    def get_window_by_hwnd(
        self,
        hwnd: int,
        proc_cache: Optional[Dict[int, Dict[str, Any]]] = None,
    ) -> Optional[WindowItem]:
        """Получение детальной информации об окне и его процессе по HWND."""
        if not self._user32.IsWindow(hwnd):
            return None

        # Заголовок окна
        length = self._user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        self._user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value

        # Имя класса
        class_buf = ctypes.create_unicode_buffer(256)
        self._user32.GetClassNameW(hwnd, class_buf, 256)
        class_name = class_buf.value

        # PID и TID
        pid = wintypes.DWORD()
        tid = int(self._user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid)) or 0)
        process_id = pid.value
        proc_info = self._get_process_telemetry(process_id, proc_cache=proc_cache)
        process_name = proc_info["process_name"] or self._get_process_name(process_id)

        # Состояния окна
        is_visible = bool(self._user32.IsWindowVisible(hwnd))
        is_minimized = bool(self._user32.IsIconic(hwnd))
        is_maximized = bool(self._user32.IsZoomed(hwnd))
        fg_hwnd = self._user32.GetForegroundWindow()
        is_foreground = (hwnd == fg_hwnd)

        # Проверка зависания и владельца
        is_hung = False
        try:
            is_hung = bool(self._user32.IsHungAppWindow(hwnd))
        except Exception:
            pass

        owner_hwnd = 0
        try:
            owner_hwnd = int(self._user32.GetWindow(hwnd, GW_OWNER) or 0)
        except Exception:
            pass

        # Стили окна Win32
        style = 0
        ex_style = 0
        try:
            style = int(self._user32.GetWindowLongW(hwnd, GWL_STYLE) or 0)
            ex_style = int(self._user32.GetWindowLongW(hwnd, GWL_EXSTYLE) or 0)
        except Exception:
            pass

        ex_u = ex_style & 0xFFFFFFFF
        style_u = style & 0xFFFFFFFF
        is_topmost = bool(ex_u & WS_EX_TOPMOST)
        is_tool_window = bool(ex_u & WS_EX_TOOLWINDOW)
        is_app_window = bool(ex_u & WS_EX_APPWINDOW)
        is_layered = bool(ex_u & WS_EX_LAYERED)
        is_no_activate = bool(ex_u & WS_EX_NOACTIVATE)

        style_flags = self._decode_window_styles(style_u, ex_u)
        rect = self._get_window_rect(hwnd)
        role_hint = self._classify_window_role(
            rect=rect,
            is_minimized=is_minimized,
            is_topmost=is_topmost,
            is_tool_window=is_tool_window,
            is_layered=is_layered,
            is_no_activate=is_no_activate,
            owner_hwnd=owner_hwnd,
            style_flags=style_flags,
        )

        return WindowItem(
            hwnd=hwnd,
            title=title,
            process_id=process_id,
            process_name=process_name,
            class_name=class_name,
            is_visible=is_visible,
            is_minimized=is_minimized,
            is_maximized=is_maximized,
            is_foreground=is_foreground,
            rect=rect,
            thread_id=tid,
            parent_pid=proc_info["parent_pid"],
            parent_process_name=proc_info["parent_process_name"],
            exe_path=proc_info["exe_path"],
            cmdline=proc_info["cmdline"],
            username=proc_info["username"],
            process_status=proc_info["process_status"],
            memory_mb=proc_info["memory_mb"],
            threads_count=proc_info["threads_count"],
            owner_hwnd=owner_hwnd,
            is_hung=is_hung,
            is_topmost=is_topmost,
            is_tool_window=is_tool_window,
            is_app_window=is_app_window,
            is_layered=is_layered,
            is_no_activate=is_no_activate,
            style_hex=f"0x{style_u:08X}",
            ex_style_hex=f"0x{ex_u:08X}",
            style_flags=style_flags,
            window_role_hint=role_hint,
        )

    def list_windows(
        self,
        only_visible: bool = True,
        only_taskbar: bool = True,
        title_filter: Optional[str] = None,
        process_filter: Optional[str] = None,
    ) -> List[WindowItem]:
        """Перечисляет все окна рабочего стола с опциональной фильтрацией."""
        result: List[WindowItem] = []
        proc_cache: Dict[int, Dict[str, Any]] = {}

        def enum_windows_proc(hwnd: int, lparam: int) -> bool:
            if not self._user32.IsWindow(hwnd):
                return True

            is_vis = bool(self._user32.IsWindowVisible(hwnd))
            if only_visible and not is_vis:
                return True

            length = self._user32.GetWindowTextLengthW(hwnd)
            # Если требуется фильтрация по панели задач, пропускаем безымянные окна
            if only_taskbar and length == 0:
                return True

            # Проверка стилей окна (отсечение tool window без явного app window)
            if only_taskbar:
                ex_style = self._user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                if (ex_style & WS_EX_TOOLWINDOW) and not (ex_style & WS_EX_APPWINDOW):
                    return True

            win_info = self.get_window_by_hwnd(hwnd, proc_cache=proc_cache)
            if win_info:
                # Фильтр по названию
                if title_filter and title_filter.lower() not in win_info.title.lower():
                    return True
                # Фильтр по процессу
                if process_filter and process_filter.lower() not in win_info.process_name.lower():
                    return True
                result.append(win_info)

            return True

        cb = WNDENUMPROC(enum_windows_proc)
        self._user32.EnumWindows(cb, 0)
        return result

    def activate_window(self, hwnd: int) -> bool:
        """Активирует окно, восстанавливает из свернутого состояния и выводит на передний план."""
        if not self._user32.IsWindow(hwnd):
            return False
        try:
            if self._user32.IsIconic(hwnd):
                self._user32.ShowWindow(hwnd, SW_RESTORE)
            else:
                self._user32.ShowWindow(hwnd, SW_SHOW)
            self._user32.BringWindowToTop(hwnd)
            return bool(self._user32.SetForegroundWindow(hwnd))
        except Exception as exc:
            logger.error(f"[WindowManager] Ошибка активации окна HWND {hwnd}: {exc}")
            return False

    def minimize_window(self, hwnd: int) -> bool:
        """Сворачивает окно на панель задач."""
        if not self._user32.IsWindow(hwnd):
            return False
        return bool(self._user32.ShowWindow(hwnd, SW_MINIMIZE))

    def maximize_window(self, hwnd: int) -> bool:
        """Разворачивает окно на весь экран."""
        if not self._user32.IsWindow(hwnd):
            return False
        return bool(self._user32.ShowWindow(hwnd, SW_MAXIMIZE))

    def restore_window(self, hwnd: int) -> bool:
        """Восстанавливает нормальный размер окна."""
        if not self._user32.IsWindow(hwnd):
            return False
        return bool(self._user32.ShowWindow(hwnd, SW_RESTORE))

    def move_window(self, hwnd: int, req: WindowMoveRequest) -> bool:
        """Изменяет положение и размеры окна."""
        if not self._user32.IsWindow(hwnd):
            return False
        return bool(self._user32.MoveWindow(hwnd, req.x, req.y, req.width, req.height, True))

    def close_window(self, hwnd: int) -> bool:
        """Корректно закрывает окно через отправку сообщения WM_CLOSE."""
        if not self._user32.IsWindow(hwnd):
            return False
        return bool(self._user32.PostMessageW(hwnd, WM_CLOSE, 0, 0))

    def batch_action(self, req: WindowBatchActionRequest) -> Dict[str, Any]:
        """Выполняет пакетные действия над окнами рабочего стола."""
        action = req.action.lower()
        windows = self.list_windows(only_visible=True, only_taskbar=True)
        affected = 0

        if action == "minimize_all":
            for w in windows:
                if not w.is_minimized:
                    self.minimize_window(w.hwnd)
                    affected += 1
        elif action == "restore_all":
            for w in windows:
                if w.is_minimized:
                    self.restore_window(w.hwnd)
                    affected += 1
        elif action == "minimize_all_except":
            target = req.target_hwnd
            for w in windows:
                if w.hwnd != target and not w.is_minimized:
                    self.minimize_window(w.hwnd)
                    affected += 1
            if target:
                self.activate_window(target)
        elif action == "close_by_process":
            proc_target = (req.process_name or "").lower()
            for w in windows:
                if proc_target and proc_target in w.process_name.lower():
                    self.close_window(w.hwnd)
                    affected += 1
        else:
            return {"status": "ERROR", "message": f"Неизвестное действие: {req.action}"}

        return {
            "status": "SUCCESS",
            "action": req.action,
            "affected_windows_count": affected,
        }

