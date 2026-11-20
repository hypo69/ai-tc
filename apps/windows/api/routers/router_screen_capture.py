# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Screen Capture Router
# =============================================================================
# Description:
#   FastAPI REST API роутер для экранного захвата (Windows.Graphics.Capture, GDI),
#   потокового видеовещания, управления окнами, дисплеями и корреляции с ETW.
#
# Usage Examples:
#   from apps.windows.api.routers.router_screen_capture import router
#
# File: router_screen_capture.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 02:54:00
# =============================================================================

from __future__ import annotations
"""Маршрутизатор API экранного захвата и визуальной аналитики."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from logger import logger
from apps.windows.vision.screen_capture import (
    CaptureBackendType,
    CaptureEngineConfig,
    CaptureTargetType,
    CapturedFrame,
    DisplayInfo,
    ScreenCaptureEngine,
    StreamStatus,
    VisualTelemetryEvent,
    WindowInfo,
)
from apps.windows.vision.screen_capture.backends.wgc_backend import WgcCaptureBackend

router = APIRouter(prefix="/api/v1/vision/capture", tags=["Vision & Screen Capture"])

# Синглтон движка захвата
_engine = ScreenCaptureEngine()
_wgc_probe = WgcCaptureBackend()


class CaptureDisplayRequest(BaseModel):
    """Запрос на захват указанного монитора."""
    display_id: int = Field(default=0, description="Идентификатор монитора")


class CaptureWindowRequest(BaseModel):
    """Запрос на захват отдельного окна по его HWND."""
    window_id: int = Field(description="Дескриптор окна (HWND)")


class StreamStartRequest(BaseModel):
    """Запрос на запуск потокового захвата."""
    target_type: CaptureTargetType = Field(default=CaptureTargetType.DISPLAY, description="Тип объекта")
    target_id: int = Field(default=0, description="ID монитора или HWND окна")


@router.get("/capabilities", summary="Возможности графической подсистемы Windows.Graphics")
async def get_capabilities() -> Dict[str, Any]:
    """Возвращает информацию о поддержке Windows.Graphics.Capture, DirectX 11 и GPU-ускорения."""
    return {
        "status": "ok",
        "capabilities": _wgc_probe.get_capabilities(),
        "active_backend": _engine.get_config().backend,
    }


@router.get("/displays", response_model=List[DisplayInfo], summary="Список доступных дисплеев")
async def list_displays() -> List[DisplayInfo]:
    """Возвращает перечень физических и виртуальных мониторов системы."""
    try:
        return _engine.list_displays()
    except Exception as exc:
        logger.error(f"[RouterScreenCapture] Ошибка перечисления дисплеев: {exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get("/windows", response_model=List[WindowInfo], summary="Список открытых окон")
async def list_windows(
    query: Optional[str] = Query(None, description="Фильтр по заголовку или процессу"),
    limit: int = Query(50, ge=1, le=200, description="Максимальное количество окон"),
) -> List[WindowInfo]:
    """Возвращает список видимых окон верхнего уровня."""
    try:
        windows = _engine.list_windows()
        if query:
            q = query.lower()
            windows = [
                w for w in windows
                if q in w.title.lower() or q in w.process_name.lower()
            ]
        return windows[:limit]
    except Exception as exc:
        logger.error(f"[RouterScreenCapture] Ошибка перечисления окон: {exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post("/display", response_model=CapturedFrame, summary="Захват монитора")
async def capture_display(req: CaptureDisplayRequest) -> CapturedFrame:
    """Выполняет моментальный снимок указанного монитора."""
    frame = _engine.capture_display(display_id=req.display_id)
    if not frame:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Не удалось захватить дисплей #{req.display_id}",
        )
    return frame


@router.post("/window", response_model=CapturedFrame, summary="Захват окна")
async def capture_window(req: CaptureWindowRequest) -> CapturedFrame:
    """Выполняет моментальный снимок окна по его HWND."""
    frame = _engine.capture_window(window_id=req.window_id)
    if not frame:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Не удалось захватить окно с HWND {req.window_id}",
        )
    return frame


@router.post("/stream/start", summary="Запуск потокового захвата")
async def start_stream(req: StreamStartRequest) -> Dict[str, Any]:
    """Запускает фоновый цикл захвата кадров с экрана или окна."""
    target_dict = {"type": req.target_type, "id": req.target_id}
    success = _engine.start_stream(target=target_dict)
    if not success:
        return {
            "status": "warning",
            "message": "Поток захвата уже запущен или произошла ошибка запуска",
            "stream_status": _engine.get_stream_status().dict(),
        }
    return {
        "status": "ok",
        "message": "Поток захвата успешно запущен",
        "stream_status": _engine.get_stream_status().dict(),
    }


@router.post("/stream/stop", summary="Остановка потокового захвата")
async def stop_stream() -> Dict[str, Any]:
    """Останавливает активный фоновый поток экранного захвата."""
    success = _engine.stop_stream()
    return {
        "status": "ok" if success else "warning",
        "message": "Поток захвата остановлен" if success else "Поток не был запущен",
        "stream_status": _engine.get_stream_status().dict(),
    }


@router.get("/stream/status", response_model=StreamStatus, summary="Состояние потока")
async def get_stream_status() -> StreamStatus:
    """Возвращает текущие метрики и состояние потокового захвата."""
    return _engine.get_stream_status()


@router.get("/stream/latest", summary="Последний полученный кадр")
async def get_latest_frame() -> Dict[str, Any]:
    """Возвращает последний кадр из потока захвата."""
    frame = _engine.get_latest_frame()
    if not frame:
        return {"status": "empty", "frame": None}
    return {"status": "ok", "frame": frame.dict()}


@router.get("/history", response_model=List[CapturedFrame], summary="История кадров")
async def get_history(limit: int = Query(20, ge=1, le=100)) -> List[CapturedFrame]:
    """Возвращает кольцевой буфер недавних снимков экрана."""
    return _engine.get_frame_history(limit=limit)


@router.get("/telemetry-events", response_model=List[VisualTelemetryEvent], summary="События корреляции с ETW")
async def get_telemetry_events(limit: int = Query(30, ge=1, le=100)) -> List[VisualTelemetryEvent]:
    """Возвращает журнал сопоставления кадров с показателями телеметрии ядра."""
    return _engine.get_telemetry_events(limit=limit)


@router.get("/config", response_model=CaptureEngineConfig, summary="Текущая конфигурация захвата")
async def get_config() -> CaptureEngineConfig:
    """Возвращает настройки параметров захвата (бэкенд, FPS, формат, ETW)."""
    return _engine.get_config()


@router.post("/config", response_model=CaptureEngineConfig, summary="Обновление конфигурации захвата")
async def update_config(config: CaptureEngineConfig) -> CaptureEngineConfig:
    """Обновляет параметры экранного захвата."""
    _engine.update_config(config)
    return _engine.get_config()
