# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - state
# =============================================================================
# Description:
#   Ленивые синглтоны TC: хранилище, коллектор, диагност, контроллер сэмплирования.
#   Вынесено из router_tc.py (этап 4 оптимизации).
#
# File: state.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers.tc
# Author: hypo69
# Copyright: c 2026 hypo69
# Updated: 2026-10-13 16:25:00
# =============================================================================

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from apps.windows.analytics.diagnostic_engine import SystemDiagnosticEngine as SystemAIDiagnostician
from apps.windows.telemetry import SystemCollector
from apps.windows.telemetry.sqlite import TelemetryStorage
from apps.windows.telemetry.sampling_controller import SamplingController
from apps.windows.sdk.win32_ffi.wevtapi import WevtAPI


_collector: Optional[SystemCollector] = None
_diagnostician: Optional[SystemAIDiagnostician] = None
_storage: Optional[TelemetryStorage] = None
_sampling_controller: Optional[SamplingController] = None
_wevtapi: Optional[WevtAPI] = None


def get_storage() -> TelemetryStorage:
    """Получить или создать синглтон хранилища телеметрии SQLite в режиме read-only."""
    global _storage
    if _storage is None:
        _storage = TelemetryStorage.get_instance(read_only=True)
    return _storage


def get_sampling_controller() -> SamplingController:
    """Получить или создать синглтон контроллера сэмплирования."""
    global _sampling_controller
    if _sampling_controller is None:
        _sampling_controller = SamplingController()
    return _sampling_controller


def get_wevtapi() -> WevtAPI:
    """Получить или создать синглтон FFI интерфейса WevtAPI."""
    global _wevtapi
    if _wevtapi is None:
        _wevtapi = WevtAPI()
    return _wevtapi


class ForensicTriggerRequest(BaseModel):
    """Модель запроса активации форензик-сэмплирования (250 мс)."""
    duration_seconds: float = Field(default=30.0, description="Длительность форензик-режима в секундах")


def get_collector() -> SystemCollector:
    """Получить или создать объект синглтона сборщика телеметрии."""
    global _collector
    if _collector is None:
        _collector = SystemCollector()
    return _collector


def get_diagnostician() -> SystemAIDiagnostician:
    """Получить или создать объект синглтона AI диагностика."""
    global _diagnostician
    if _diagnostician is None:
        _diagnostician = SystemAIDiagnostician()
    return _diagnostician

