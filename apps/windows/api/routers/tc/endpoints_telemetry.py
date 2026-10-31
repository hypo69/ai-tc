# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - endpoints_telemetry
# =============================================================================
# Description:
#   Эндпойнты телеметрии, сэмплирования и God Mode.
#   Вынесено из router_tc.py (этап 4 оптимизации).
#
# File: endpoints_telemetry.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers.tc
# Author: hypo69
# Copyright: c 2026 hypo69
# Updated: 2026-10-12 06:20:00
# =============================================================================

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request

from header import __root__
from logger import logger
from apps.windows.telemetry.models import SamplingMode
from .state import ForensicTriggerRequest
from .state import get_sampling_controller
from .state import get_storage
from .state import get_wevtapi


def register_telemetry_endpoints(router: APIRouter) -> None:
    """Регистрирует эндпойнты телеметрии на роутере."""
    # =========================================================================
    # 5. Расширенные эндпоинты телеметрии, роллапов, БД и форензики
    # =========================================================================

    @router.get("/telemetry/rollups")
    async def get_telemetry_rollups(
        request: Request,
        level: str = "hourly",
        limit: int = 100,
        sensor_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Получение агрегированных роллапов телеметрии по уровням (hourly, daily, weekly, monthly, yearly)."""
        storage = get_storage()
        rows = storage.get_telemetry_rollups(level=level, limit=limit, sensor_id=sensor_id)
        return {
            "status": "ok",
            "level": level,
            "count": len(rows),
            "rollups": rows,
        }

    @router.get("/telemetry/db-stats")
    async def get_telemetry_db_stats(request: Request) -> Dict[str, Any]:
        """Получение метрик производительности и состояния базы данных SQLite (telemetry.db)."""
        storage = get_storage()
        db_path = storage.db_path
        db_size_bytes = 0
        wal_size_bytes = 0
        shm_size_bytes = 0

        p = Path(db_path)
        if p.is_file():
            db_size_bytes = p.stat().st_size
        wal_p = Path(str(db_path) + "-wal")
        if wal_p.is_file():
            wal_size_bytes = wal_p.stat().st_size
        shm_p = Path(str(db_path) + "-shm")
        if shm_p.is_file():
            shm_size_bytes = shm_p.stat().st_size

        counts: Dict[str, int] = {}
        try:
            with storage.connection() as conn:
                cursor = conn.cursor()
                for table in ["system_snapshots", "process_snapshots", "incidents", "telemetry_hourly", "telemetry_daily"]:
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        row = cursor.fetchone()
                        counts[table] = row[0] if row else 0
                    except Exception:
                        counts[table] = 0
        except Exception as ex:
            logger.debug(f"[router_tc] Ошибка при сборе статистики таблиц: {ex}")

        return {
            "status": "ok",
            "db_path": db_path,
            "db_size_bytes": db_size_bytes,
            "db_size_mb": round(db_size_bytes / (1024 * 1024), 2),
            "wal_size_bytes": wal_size_bytes,
            "wal_size_mb": round(wal_size_bytes / (1024 * 1024), 2),
            "shm_size_bytes": shm_size_bytes,
            "table_counts": counts,
            "pragmas": {
                "journal_mode": "WAL",
                "synchronous": "NORMAL",
                "mmap_size_mb": 256,
                "cache_size_mb": 64,
                "busy_timeout_ms": 15000,
            },
            "buffer_ram_limit_mb": 32,
        }

    @router.get("/telemetry/incidents")
    async def get_telemetry_incidents(
        request: Request,
        limit: int = 50,
        trigger_type: Optional[str] = None,
        severity: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Получение списка зафиксированных инцидентов и аномалий телеметрии."""
        storage = get_storage()
        incidents = storage.get_incidents(limit=limit, trigger_type=trigger_type, severity=severity)
        return {
            "status": "ok",
            "count": len(incidents),
            "incidents": incidents,
        }

    @router.get("/telemetry/sysmon")
    async def get_telemetry_sysmon_events(
        request: Request,
        limit: int = 50,
        event_ids: Optional[str] = None,
        filter_process: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Получение событий Sysmon (Event ID 1, 7, 10, 11, 23, 26) через WevtAPI FFI."""
        wevt = get_wevtapi()
        ids_list = None
        if event_ids:
            try:
                ids_list = [int(x.strip()) for x in event_ids.split(",") if x.strip().isdigit()]
            except Exception:
                pass
        events = wevt.query_sysmon_events(limit=limit, event_ids=ids_list, filter_process=filter_process)
        return {
            "status": "ok",
            "count": len(events),
            "events": events,
        }

    @router.get("/telemetry/powershell-scripts")
    async def get_powershell_script_blocks(
        request: Request,
        limit: int = 50,
        filter_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Получение блоков скриптов PowerShell (Event ID 4104) через WevtAPI FFI."""
        wevt = get_wevtapi()
        blocks = wevt.query_powershell_script_blocks(limit=limit, filter_text=filter_text)
        return {
            "status": "ok",
            "count": len(blocks),
            "script_blocks": blocks,
        }

    @router.get("/sampling/status")
    async def get_sampling_status(request: Request) -> Dict[str, Any]:
        """Получение текущего режима сэмплирования и интервала телеметрии."""
        ctrl = get_sampling_controller()
        status_info = ctrl.get_status()
        current_mode = ctrl.mode
        return {
            "status": "ok",
            "mode": current_mode.value,
            "interval_seconds": ctrl.get_current_interval(),
            "is_forensic": current_mode == SamplingMode.FORENSIC,
            "is_incident": current_mode == SamplingMode.INCIDENT,
            "details": status_info,
        }

    @router.post("/sampling/trigger-forensic")
    async def trigger_sampling_forensic(payload: ForensicTriggerRequest, request: Request) -> Dict[str, Any]:
        """Активация высокочастотного форензик-сэмплирования (250 мс) на заданную длительность."""
        ctrl = get_sampling_controller()
        duration = float(payload.duration_seconds or 30.0)
        ctrl.trigger_forensic_mode(duration_seconds=duration)
        return {
            "status": "ok",
            "message": f"Форензик-сэмплинг (250 мс) активирован на {duration} сек.",
            "duration_seconds": duration,
            "mode": ctrl.mode.value,
            "interval_seconds": ctrl.get_current_interval(),
        }

    @router.post("/godmode/open")
    @router.get("/godmode/open")
    async def open_god_mode() -> Dict[str, Any]:
        """Открывает виртуальную папку Windows God Mode (All Tasks) или переводит фокус на уже открытое окно."""
        god_mode_guid = "ED7BA470-8E54-465E-825C-99712043E01C"
        hwnd = None

        # 1. Попытка найти уже открытое окно проводника через Shell.Application COM
        try:
            import win32com.client
            shell = win32com.client.Dispatch("Shell.Application")
            for w in shell.Windows():
                url = getattr(w, "LocationURL", "") or ""
                name = getattr(w, "LocationName", "") or ""
                if god_mode_guid in url.upper() or god_mode_guid in name.upper():
                    hwnd = getattr(w, "HWND", None)
                    if hwnd:
                        break
        except Exception as exc:
            logger.debug(f"[router_tc] Поиск окна God Mode через Shell.Application: {exc}")

        # 2. Fallback: поиск через EnumWindows Win32
        if not hwnd:
            try:
                import ctypes
                from ctypes import wintypes
                found = []
                WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

                def _enum_cb(h, _):
                    if ctypes.windll.user32.IsWindowVisible(h):
                        length = ctypes.windll.user32.GetWindowTextLengthW(h)
                        if length > 0:
                            buff = ctypes.create_unicode_buffer(length + 1)
                            ctypes.windll.user32.GetWindowTextW(h, buff, length + 1)
                            title = buff.value
                            if god_mode_guid.lower() in title.lower() or any(k in title.lower() for k in ["все задачи", "all tasks", "god mode"]):
                                found.append(h)
                    return True

                ctypes.windll.user32.EnumWindows(WNDENUMPROC(_enum_cb), 0)
                if found:
                    hwnd = found[0]
            except Exception as exc:
                logger.debug(f"[router_tc] Поиск окна через EnumWindows: {exc}")

        # 3. Если окно найдено — восстанавливаем и переводим на него фокус
        if hwnd:
            try:
                import ctypes
                user32 = ctypes.windll.user32
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                user32.AllowSetForegroundWindow(-1)
                user32.BringWindowToTop(hwnd)
                user32.SetForegroundWindow(hwnd)
                user32.SwitchToThisWindow(hwnd, True)
                logger.info(f"[router_tc] Переведён фокус на существующее окно God Mode (HWND {hwnd})")
                return {
                    "status": "ok",
                    "action": "focused",
                    "hwnd": hwnd,
                    "message": "Фокус переведён на открытое окно God Mode",
                }
            except Exception as exc:
                logger.warning(f"[router_tc] Не удалось активировать окно HWND {hwnd}: {exc}")

        # 4. Если окно не было открыто — запускаем
        try:
            bin_godmode = __root__ / "bin" / f".{{{god_mode_guid}}}"
            if bin_godmode.exists():
                target = str(bin_godmode.resolve())
            else:
                target = f"shell:::{{{god_mode_guid}}}"

            subprocess.Popen(["explorer.exe", target])
            logger.info(f"[router_tc] Открыт God Mode: {target}")
            return {
                "status": "ok",
                "action": "opened",
                "message": "Папка God Mode успешно открыта в Проводнике Windows",
            }
        except Exception as exc:
            logger.error(f"[router_tc] Ошибка открытия God Mode: {exc}")
            return {"status": "error", "message": str(exc)}

