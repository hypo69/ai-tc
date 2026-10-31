# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - Router Forensics
# =============================================================================
# Description:
#   Роутер, предоставляющий данные о форензике для фронтенда вкладки Forensics.
#   Возвращает JSON со сведениями о текущем активном окне, времени бездействия
#   пользователя, приложениях, использующих камеру/микрофон, хронологической
#   истории активности (таймлайн переключения окон) и данных UserAssist.
#
# Usage Examples:
#   Python API:
#     from apps.windows.api.routers.router_forensics import init_router
#
#     router = init_router()
#
# File: router_forensics.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-16 20:57:00
# =============================================================================

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from logger import logger
from apps.windows.telemetry.sqlite import TelemetryStorage


class ForegroundWindow(BaseModel):
    """Информация о текущем активном окне."""
    title: str = Field(default="Рабочий стол Windows", description="Заголовок окна")
    process_name: str = Field(default="explorer.exe", description="Имя процесса")
    pid: int = Field(default=0, description="PID процесса")

class AppAccessInfo(BaseModel):
    """Приложение, имеющее доступ к камере или микрофону."""
    app_name: str = Field(..., description="Имя приложения")
    is_active_now: bool = Field(False, description="Активно в данный момент")

class UserAssistApp(BaseModel):
    """Запись UserAssist из реестра."""
    name: str = Field(..., description="Имя программы")
    run_count: int = Field(..., description="Количество запусков")
    focus_formatted: str = Field(..., description="Время фокуса (чч:мм:сс)")
    path: str = Field(..., description="Путь к исполняемому файлу")

class ForensicsHistoryItem(BaseModel):
    """Элемент хронологической истории активности (таймлайн)."""
    id: Optional[int] = Field(None, description="ID записи в SQLite")
    snapshot_id: str = Field(..., description="Идентификатор снимка")
    timestamp: str = Field(..., description="Время фиксации ISO-8601")
    foreground_window: ForegroundWindow = Field(..., description="Окно в фокусе")
    user_idle_seconds: float = Field(0.0, description="Время простоя в секундах")
    camera_active_apps: list[AppAccessInfo] = Field(default_factory=list, description="Использование камеры")
    microphone_active_apps: list[AppAccessInfo] = Field(default_factory=list, description="Использование микрофона")

class ForensicsResponse(BaseModel):
    """Ответ, ожидаемый фронтендом Forensics‑вкладки."""
    status: str = Field(default="ok", description="Статус ответа")
    foreground_window: ForegroundWindow = Field(..., description="Текущее активное окно")
    user_idle_seconds: float = Field(..., description="Время бездействия пользователя в секундах")
    camera_active_apps: list[AppAccessInfo] = Field(default_factory=list, description="Приложения, использующие камеру")
    microphone_active_apps: list[AppAccessInfo] = Field(default_factory=list, description="Приложения, использующие микрофон")
    userassist_top_apps: list[UserAssistApp] = Field(default_factory=list, description="Топ‑приложения UserAssist")
    history: list[ForensicsHistoryItem] = Field(default_factory=list, description="Хронологическая история активности")


def _convert_history_row(d: Dict[str, Any]) -> ForensicsHistoryItem:
    """Преобразует строку снимка SQLite в элемент истории ForensicsHistoryItem."""
    fg = ForegroundWindow(
        title=d.get("foreground_window_title") or "Рабочий стол Windows",
        process_name=d.get("foreground_process_name") or "explorer.exe",
        pid=int(d.get("foreground_pid") or 0),
    )
    cam = [AppAccessInfo(**a) if isinstance(a, dict) else a for a in (d.get("camera_active_apps") or [])]
    mic = [AppAccessInfo(**a) if isinstance(a, dict) else a for a in (d.get("microphone_active_apps") or [])]
    return ForensicsHistoryItem(
        id=d.get("id"),
        snapshot_id=str(d.get("snapshot_id") or ""),
        timestamp=str(d.get("timestamp") or ""),
        foreground_window=fg,
        user_idle_seconds=float(d.get("user_idle_seconds") or 0.0),
        camera_active_apps=cam,
        microphone_active_apps=mic,
    )


def _convert_snapshot_to_response(d: Dict[str, Any], history: Optional[List[Dict[str, Any]]] = None) -> ForensicsResponse:
    """Преобразует сырые данные снимка SQLite в модель ответа ForensicsResponse."""
    fg = ForegroundWindow(
        title=d.get("foreground_window_title") or "Рабочий стол Windows",
        process_name=d.get("foreground_process_name") or "explorer.exe",
        pid=int(d.get("foreground_pid") or 0),
    )
    cam = [AppAccessInfo(**a) if isinstance(a, dict) else a for a in (d.get("camera_active_apps") or [])]
    mic = [AppAccessInfo(**a) if isinstance(a, dict) else a for a in (d.get("microphone_active_apps") or [])]
    ua = [UserAssistApp(**a) if isinstance(a, dict) else a for a in (d.get("userassist_top_apps") or [])]
    hist_items = [_convert_history_row(h) for h in (history or [])]
    return ForensicsResponse(
        status="ok",
        foreground_window=fg,
        user_idle_seconds=float(d.get("user_idle_seconds") or 0.0),
        camera_active_apps=cam,
        microphone_active_apps=mic,
        userassist_top_apps=ua,
        history=hist_items,
    )


def _perform_forensics_scan(storage: TelemetryStorage) -> ForensicsResponse:
    """Выполняет живой сбор форензики и сохраняет снимок в SQLite."""
    try:
        from apps.windows.telemetry.deep_diagnostics import DeepDiagnosticsEngine
        engine = DeepDiagnosticsEngine()
        rep = engine.collect_forensics_activity()
        snap_id = f"snap_forensics_{int(datetime.now(timezone.utc).timestamp())}"
        try:
            write_store = TelemetryStorage.get_instance(read_only=False)
            write_store.save_forensics_snapshot(snap_id, {
                "foreground_window_title": rep.foreground_window.get("title", ""),
                "foreground_process_name": rep.foreground_window.get("process_name", ""),
                "foreground_pid": rep.foreground_window.get("pid", 0),
                "user_idle_seconds": int(rep.user_idle_seconds),
                "camera_active_apps": rep.camera_active_apps,
                "microphone_active_apps": rep.microphone_active_apps,
                "userassist_top_apps": rep.userassist_top_apps,
            })
        except Exception as write_err:
            logger.debug(f"Не удалось записать снимок форензики в SQLite: {write_err}")

        d = storage.get_latest_forensics_snapshot()
        hist = storage.get_forensics_history(limit=50)
        if d:
            return _convert_snapshot_to_response(d, hist)
        return ForensicsResponse(
            status="ok",
            foreground_window=ForegroundWindow(**rep.foreground_window),
            user_idle_seconds=rep.user_idle_seconds,
            camera_active_apps=[AppAccessInfo(**a) for a in rep.camera_active_apps],
            microphone_active_apps=[AppAccessInfo(**a) for a in rep.microphone_active_apps],
            userassist_top_apps=[UserAssistApp(**a) for a in rep.userassist_top_apps],
            history=[_convert_history_row(h) for h in hist],
        )
    except Exception as ex:
        logger.debug(f"Ошибка сбора форензики: {ex}")
        return ForensicsResponse(
            status="ok",
            foreground_window=ForegroundWindow(),
            user_idle_seconds=0.0,
            camera_active_apps=[],
            microphone_active_apps=[],
            userassist_top_apps=[],
            history=[],
        )


def init_router(storage: Optional[TelemetryStorage] = None) -> APIRouter:
    """Инициализирует роутер Forensics с чтением из SQLite (< 5 мс).

    Путь: `/api/v1/system/diagnostics/forensics`
    """
    router = APIRouter(prefix="/api/v1/system/diagnostics", tags=["Forensics"])
    store = storage or TelemetryStorage.get_instance(read_only=True)

    @router.get("/forensics", response_model=ForensicsResponse)
    async def get_forensics(refresh: bool = Query(False, description="Принудительное живое сканирование")) -> ForensicsResponse:
        """Возвращает срез активности пользователя и форензики с историей из SQLite (< 5 мс)."""
        if refresh:
            return await asyncio.to_thread(_perform_forensics_scan, store)
        d = store.get_latest_forensics_snapshot()
        if not d or not d.get("userassist_top_apps"):
            return await asyncio.to_thread(_perform_forensics_scan, store)
        hist = store.get_forensics_history(limit=50)
        return _convert_snapshot_to_response(d, hist)

    @router.get("/forensics/history", response_model=List[ForensicsHistoryItem])
    async def get_forensics_history(
        limit: int = Query(50, ge=1, le=500, description="Лимит записей"),
        hours: float = Query(24.0, ge=0.1, le=720.0, description="Период в часах"),
    ) -> List[ForensicsHistoryItem]:
        """Возвращает хронологическую историю переключения окон и активности пользователя."""
        hist = store.get_forensics_history(limit=limit, hours=hours)
        return [_convert_history_row(h) for h in hist]

    @router.post("/forensics/refresh", response_model=ForensicsResponse)
    @router.post("/forensics/rescan", response_model=ForensicsResponse)
    async def refresh_forensics() -> ForensicsResponse:
        """Принудительно пересканирует форензик-активность и обновляет срез в SQLite."""
        return await asyncio.to_thread(_perform_forensics_scan, store)

    @router.get("/privacy-status")
    @router.get("/forensics/privacy-status")
    async def get_privacy_status():
        """Возвращает текущий статус активности камеры и микрофона (Privacy Radar)."""
        d = store.get_latest_forensics_snapshot()
        if not d:
            res = await asyncio.to_thread(_perform_forensics_scan, store)
            return {
                "camera_active_apps": [a.app_name for a in res.camera_active_apps],
                "microphone_active_apps": [a.app_name for a in res.microphone_active_apps],
                "user_idle_seconds": res.user_idle_seconds,
            }
        cam_apps = [a.get("app_name", "") for a in (d.get("camera_active_apps") or []) if a.get("app_name")]
        mic_apps = [a.get("app_name", "") for a in (d.get("microphone_active_apps") or []) if a.get("app_name")]
        return {
            "camera_active_apps": cam_apps,
            "microphone_active_apps": mic_apps,
            "user_idle_seconds": d.get("user_idle_seconds", 0),
        }

    return router


