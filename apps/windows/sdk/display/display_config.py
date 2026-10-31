# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Display SDK - Display Config Manager
# =============================================================================
# Description:
#   Win32 FFI реализация низкоуровневого управления дисплеями Windows:
#   перечисление мониторов, чтение текущих параметров, безопасный поворот экрана
#   (MONITOR.ROTATE) с таймером подтверждения и возможностью автоматического отката.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.display.display_config import DisplayConfigManager
#
#     mgr = DisplayConfigManager()
#     displays = mgr.list_displays()
#     res = mgr.rotate_display(displays[0].id, "portrait", timeout_seconds=15)
#
# File: display_config.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.display
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 13:00:00
# =============================================================================

from __future__ import annotations
"""Менеджер конфигурации и поворота мониторов Windows через Win32 User32 API."""

import asyncio
import ctypes
import ctypes.wintypes
import threading
import time
from typing import Any, Dict, List, Optional

from logger import logger
from apps.windows.sdk.display.display_models import (
    DisplayItem,
    DisplayOrientation,
    DisplayRotateResponse,
)

# Win32 Константы
CCHDEVICENAME = 32
CCHFORMNAME = 32

ENUM_CURRENT_SETTINGS = -1

# Флаги полей DEVMODE (dmFields)
DM_ORIENTATION = 0x00000001
DM_PELSWIDTH = 0x00080000
DM_PELSHEIGHT = 0x00100000
DM_DISPLAYFLAGS = 0x00200000
DM_DISPLAYFREQUENCY = 0x00400000
DM_DISPLAYORIENTATION = 0x00800000

# Флаги ChangeDisplaySettingsEx
CDS_UPDATEREGISTRY = 0x00000001
CDS_TEST = 0x00000002
CDS_FULLSCREEN = 0x00000004
CDS_GLOBAL = 0x00000008
CDS_SET_PRIMARY = 0x00000010
CDS_RESET = 0x40000000

# Коды возврата ChangeDisplaySettingsEx
DISP_CHANGE_SUCCESSFUL = 0
DISP_CHANGE_RESTART = 1
DISP_CHANGE_FAILED = -1
DISP_CHANGE_BADMODE = -2
DISP_CHANGE_NOTUPDATED = -3
DISP_CHANGE_BADFLAGS = -4
DISP_CHANGE_BADPARAM = -5

# Флаги состояния DISPLAY_DEVICE
DISPLAY_DEVICE_ATTACHED_TO_DESKTOP = 0x00000001
DISPLAY_DEVICE_PRIMARY_DEVICE = 0x00000004


class POINTL(ctypes.Structure):
    """Win32 точка с координатами X и Y."""
    _fields_ = [
        ("x", ctypes.c_long),
        ("y", ctypes.c_long),
    ]


class DISPLAY_DEVICEW(ctypes.Structure):
    """Win32 структура описания графического устройства."""
    _fields_ = [
        ("cb", ctypes.wintypes.DWORD),
        ("DeviceName", ctypes.wintypes.WCHAR * 32),
        ("DeviceString", ctypes.wintypes.WCHAR * 128),
        ("StateFlags", ctypes.wintypes.DWORD),
        ("DeviceID", ctypes.wintypes.WCHAR * 128),
        ("DeviceKey", ctypes.wintypes.WCHAR * 128),
    ]


class DEVMODE_DISPLAY(ctypes.Structure):
    """Win32 структура DEVMODEW для графического режима дисплея."""
    _fields_ = [
        ("dmDeviceName", ctypes.wintypes.WCHAR * 32),
        ("dmSpecVersion", ctypes.wintypes.WORD),
        ("dmDriverVersion", ctypes.wintypes.WORD),
        ("dmSize", ctypes.wintypes.WORD),
        ("dmDriverExtra", ctypes.wintypes.WORD),
        ("dmFields", ctypes.wintypes.DWORD),
        ("dmPosition", POINTL),
        ("dmDisplayOrientation", ctypes.wintypes.DWORD),
        ("dmDisplayFixedOutput", ctypes.wintypes.DWORD),
        ("dmColor", ctypes.c_short),
        ("dmDuplex", ctypes.c_short),
        ("dmYResolution", ctypes.c_short),
        ("dmTTOption", ctypes.c_short),
        ("dmCollate", ctypes.c_short),
        ("dmFormName", ctypes.wintypes.WCHAR * 32),
        ("dmLogPixels", ctypes.wintypes.WORD),
        ("dmBitsPerPel", ctypes.wintypes.DWORD),
        ("dmPelsWidth", ctypes.wintypes.DWORD),
        ("dmPelsHeight", ctypes.wintypes.DWORD),
        ("dmDisplayFlags", ctypes.wintypes.DWORD),
        ("dmDisplayFrequency", ctypes.wintypes.DWORD),
        ("dmICMMethod", ctypes.wintypes.DWORD),
        ("dmICMIntent", ctypes.wintypes.DWORD),
        ("dmMediaType", ctypes.wintypes.DWORD),
        ("dmDitherType", ctypes.wintypes.DWORD),
        ("dmReserved1", ctypes.wintypes.DWORD),
        ("dmReserved2", ctypes.wintypes.DWORD),
        ("dmPanningWidth", ctypes.wintypes.DWORD),
        ("dmPanningHeight", ctypes.wintypes.DWORD),
    ]


class DisplayConfigManager:
    """Менеджер перечисления мониторов, чтения режимов и ориентации дисплеев Windows."""

    def __init__(self) -> None:
        """Инициализация менеджера дисплеев и отслеживания таймеров отката."""
        self._user32 = ctypes.windll.user32 if hasattr(ctypes, "windll") else None
        # Сохранение активных сессий поворота для автоматического отката
        # display_id -> dict(previous_orientation, timer_thread, confirmed)
        self._pending_rollbacks: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def _get_devmode(self, device_name: str) -> Optional[DEVMODE_DISPLAY]:
        """Считывает текущие настройки DEVMODE для указанного дисплея."""
        if not self._user32:
            return None
        dm = DEVMODE_DISPLAY()
        dm.dmSize = ctypes.sizeof(DEVMODE_DISPLAY)
        res = self._user32.EnumDisplaySettingsW(device_name, ENUM_CURRENT_SETTINGS, ctypes.byref(dm))
        if res:
            return dm
        return None

    def list_displays(self) -> List[DisplayItem]:
        """Возвращает список всех подключенных дисплеев с текущими параметрами и ориентацией."""
        displays: List[DisplayItem] = []
        if not self._user32:
            return displays

        dev = DISPLAY_DEVICEW()
        dev.cb = ctypes.sizeof(DISPLAY_DEVICEW)
        i = 0

        while self._user32.EnumDisplayDevicesW(None, i, ctypes.byref(dev), 0):
            state = dev.StateFlags
            is_attached = bool(state & DISPLAY_DEVICE_ATTACHED_TO_DESKTOP)
            is_primary = bool(state & DISPLAY_DEVICE_PRIMARY_DEVICE)
            dev_name = dev.DeviceName

            if is_attached:
                dm = self._get_devmode(dev_name)
                orientation = DisplayOrientation.LANDSCAPE
                width = 0
                height = 0
                freq = 0

                if dm:
                    orientation = DisplayOrientation.from_dmdo(dm.dmDisplayOrientation)
                    width = dm.dmPelsWidth
                    height = dm.dmPelsHeight
                    freq = dm.dmDisplayFrequency

                displays.append(
                    DisplayItem(
                        id=dev_name,
                        name=dev_name,
                        adapter_string=dev.DeviceString,
                        is_primary=is_primary,
                        is_attached=is_attached,
                        current_orientation=orientation,
                        width=width,
                        height=height,
                        frequency_hz=freq,
                    )
                )
            i += 1

        return displays

    def get_display(self, display_id: str) -> Optional[DisplayItem]:
        """Получает информацию о конкретном мониторе по ID."""
        clean_id = display_id.strip()
        for d in self.list_displays():
            if d.id.lower() == clean_id.lower() or d.id.replace(r"\\.\\", "").lower() == clean_id.lower():
                return d
        return None

    def get_current_orientation(self, display_id: str) -> DisplayOrientation:
        """Считывает текущую ориентацию дисплея."""
        disp = self.get_display(display_id)
        if disp:
            return disp.current_orientation
        return DisplayOrientation.LANDSCAPE

    def rotate_display(
        self,
        display_id: str,
        target_orientation: DisplayOrientation | str,
        timeout_seconds: int = 15,
        auto_rollback: bool = True,
    ) -> DisplayRotateResponse:
        """Поворачивает дисплей в указанную ориентацию с поддержкой таймера отката."""
        if isinstance(target_orientation, str):
            target_orientation = DisplayOrientation(target_orientation)

        target_disp = self.get_display(display_id)
        if not target_disp:
            return DisplayRotateResponse(
                success=False,
                display_id=display_id,
                requested_orientation=target_orientation,
                actual_orientation=DisplayOrientation.LANDSCAPE,
                error=f"Дисплей '{display_id}' не обнаружен",
            )

        current_dm = self._get_devmode(target_disp.id)
        if not current_dm:
            return DisplayRotateResponse(
                success=False,
                display_id=target_disp.id,
                requested_orientation=target_orientation,
                actual_orientation=target_disp.current_orientation,
                error="Не удалось считать структуру DEVMODE дисплея",
            )

        orig_orientation = DisplayOrientation.from_dmdo(current_dm.dmDisplayOrientation)
        if orig_orientation == target_orientation:
            return DisplayRotateResponse(
                success=True,
                display_id=target_disp.id,
                requested_orientation=target_orientation,
                actual_orientation=orig_orientation,
                confirmed=True,
            )

        new_dm = DEVMODE_DISPLAY()
        ctypes.memmove(ctypes.byref(new_dm), ctypes.byref(current_dm), ctypes.sizeof(DEVMODE_DISPLAY))

        # Вычисляем, меняется ли ориентация между горизонтальной и вертикальной
        current_is_portrait = orig_orientation in (DisplayOrientation.PORTRAIT, DisplayOrientation.PORTRAIT_FLIPPED)
        target_is_portrait = target_orientation in (DisplayOrientation.PORTRAIT, DisplayOrientation.PORTRAIT_FLIPPED)

        if current_is_portrait != target_is_portrait:
            # Смена габаритов местами
            new_dm.dmPelsWidth, new_dm.dmPelsHeight = new_dm.dmPelsHeight, new_dm.dmPelsWidth

        new_dm.dmDisplayOrientation = target_orientation.to_dmdo()
        new_dm.dmFields |= (DM_DISPLAYORIENTATION | DM_PELSWIDTH | DM_PELSHEIGHT)

        # Выполняем изменение режима экрана
        ret = self._user32.ChangeDisplaySettingsExW(
            target_disp.id,
            ctypes.byref(new_dm),
            None,
            CDS_UPDATEREGISTRY,
            None,
        )

        if ret != DISP_CHANGE_SUCCESSFUL:
            err_msg = f"ChangeDisplaySettingsExW завершился с кодом ошибки {ret}"
            logger.error(f"[DisplayConfig] {err_msg} для {target_disp.id}")
            return DisplayRotateResponse(
                success=False,
                display_id=target_disp.id,
                requested_orientation=target_orientation,
                actual_orientation=orig_orientation,
                error=err_msg,
            )

        logger.info(
            f"[DisplayConfig] Экран {target_disp.id} повернут: {orig_orientation.value} -> {target_orientation.value}"
        )

        # Если включен авто-откат, запускаем таймер ожидания подтверждения
        pending_rollback = False
        if auto_rollback and timeout_seconds > 0:
            with self._lock:
                self._cancel_existing_timer(target_disp.id)
                session = {
                    "display_id": target_disp.id,
                    "previous_orientation": orig_orientation,
                    "target_orientation": target_orientation,
                    "confirmed": False,
                    "deadline": time.time() + timeout_seconds,
                }
                timer = threading.Thread(
                    target=self._rollback_worker,
                    args=(target_disp.id, orig_orientation, timeout_seconds),
                    daemon=True,
                )
                session["timer"] = timer
                self._pending_rollbacks[target_disp.id] = session
                timer.start()
                pending_rollback = True

        return DisplayRotateResponse(
            success=True,
            display_id=target_disp.id,
            requested_orientation=target_orientation,
            actual_orientation=target_orientation,
            confirmed=not auto_rollback,
            pending_rollback=pending_rollback,
            timeout_seconds=timeout_seconds if pending_rollback else 0,
        )

    def _cancel_existing_timer(self, display_id: str) -> None:
        """Отменяет существующий таймер отката для дисплея."""
        if display_id in self._pending_rollbacks:
            self._pending_rollbacks[display_id]["confirmed"] = True
            del self._pending_rollbacks[display_id]

    def _rollback_worker(self, display_id: str, orig_orientation: DisplayOrientation, timeout_seconds: int) -> None:
        """Фоновый рабочий поток обратного отсчета для отката ориентации."""
        time.sleep(timeout_seconds)
        with self._lock:
            session = self._pending_rollbacks.get(display_id)
            if not session or session.get("confirmed"):
                return
            logger.warning(
                f"[DisplayConfig] Таймаут ({timeout_seconds}с) истек без подтверждения. Откат экрана {display_id} к {orig_orientation.value}"
            )
            del self._pending_rollbacks[display_id]

        # Выполняем возврат к прежней ориентации
        self._apply_rotation_direct(display_id, orig_orientation)

    def _apply_rotation_direct(self, display_id: str, target_orientation: DisplayOrientation) -> bool:
        """Прямой вызов смены ориентации без создания таймеров."""
        current_disp = self.get_display(display_id)
        if not current_disp:
            return False
        current_dm = self._get_devmode(current_disp.id)
        if not current_dm:
            return False

        orig_orientation = DisplayOrientation.from_dmdo(current_dm.dmDisplayOrientation)
        if orig_orientation == target_orientation:
            return True

        new_dm = DEVMODE_DISPLAY()
        ctypes.memmove(ctypes.byref(new_dm), ctypes.byref(current_dm), ctypes.sizeof(DEVMODE_DISPLAY))

        current_is_portrait = orig_orientation in (DisplayOrientation.PORTRAIT, DisplayOrientation.PORTRAIT_FLIPPED)
        target_is_portrait = target_orientation in (DisplayOrientation.PORTRAIT, DisplayOrientation.PORTRAIT_FLIPPED)

        if current_is_portrait != target_is_portrait:
            new_dm.dmPelsWidth, new_dm.dmPelsHeight = new_dm.dmPelsHeight, new_dm.dmPelsWidth

        new_dm.dmDisplayOrientation = target_orientation.to_dmdo()
        new_dm.dmFields |= (DM_DISPLAYORIENTATION | DM_PELSWIDTH | DM_PELSHEIGHT)

        ret = self._user32.ChangeDisplaySettingsExW(
            current_disp.id,
            ctypes.byref(new_dm),
            None,
            CDS_UPDATEREGISTRY,
            None,
        )
        return ret == DISP_CHANGE_SUCCESSFUL

    def confirm_rotation(self, display_id: str) -> bool:
        """Пользователь подтверждает, что новый режим экрана устраивает (отменяет таймер отката)."""
        clean_id = display_id.strip()
        with self._lock:
            for d_id, session in list(self._pending_rollbacks.items()):
                if d_id.lower() == clean_id.lower() or d_id.replace(r"\\.\\", "").lower() == clean_id.lower():
                    session["confirmed"] = True
                    del self._pending_rollbacks[d_id]
                    logger.info(f"[DisplayConfig] Смена ориентации для {d_id} подтверждена пользователем")
                    return True
        return False

    def rollback_rotation(self, display_id: str) -> bool:
        """Немедленный откат ориентации экрана к исходному состоянию."""
        clean_id = display_id.strip()
        orig_orientation = None
        with self._lock:
            for d_id, session in list(self._pending_rollbacks.items()):
                if d_id.lower() == clean_id.lower() or d_id.replace(r"\\.\\", "").lower() == clean_id.lower():
                    orig_orientation = session.get("previous_orientation")
                    session["confirmed"] = True
                    del self._pending_rollbacks[d_id]
                    break

        if orig_orientation:
            logger.info(f"[DisplayConfig] Пользовательский откат экрана {clean_id} к {orig_orientation.value}")
            return self._apply_rotation_direct(clean_id, orig_orientation)
        return False

