# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Screen Capture - Data Models
# =============================================================================
# Description:
#   Модели данных и структуры контрактов для подсистемы экранного захвата
#   (Windows.Graphics.Capture, DXGI, GDI) и визуальной диагностики.
#
# Usage Examples:
#   from apps.windows.vision.screen_capture.models import DisplayInfo, WindowInfo, CapturedFrame
#
# File: models.py
# Project: ai-windows-admin
# Package: apps.windows.vision.screen_capture
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 02:45:00
# =============================================================================

from __future__ import annotations
"""Модели данных для экранного захвата и корреляции с системной телеметрией."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CaptureBackendType(str, Enum):
    """Доступные бэкенды графического захвата."""
    WGC = "wgc"             # Windows.Graphics.Capture (основной WinRT API)
    DXGI = "dxgi"           # DirectX Desktop Duplication API
    GDI = "gdi"             # Win32 GDI / BitBlt / PrintWindow (универсальный резервный)
    AUTO = "auto"           # Автовыбор наиболее быстрого доступного механизма


class CaptureTargetType(str, Enum):
    """Тип объекта захвата."""
    DISPLAY = "display"     # Рабочий стол / монитор целиком
    WINDOW = "window"       # Отдельное окно приложения


class RectCoordinates(BaseModel):
    """Координаты прямоугольной области на экране."""
    left: int = 0
    top: int = 0
    right: int = 0
    bottom: int = 0
    width: int = 0
    height: int = 0


class DisplayInfo(BaseModel):
    """Информация о физическом или виртуальном мониторе."""
    id: int = Field(description="Порядковый номер дисплея")
    name: str = Field(description="Системное имя устройства (например, \\\\.\\DISPLAY1)")
    width: int = Field(description="Ширина экрана в пикселях")
    height: int = Field(description="Высота экрана в пикселях")
    is_primary: bool = Field(default=False, description="Является ли монитор основным")
    scale_factor: float = Field(default=1.0, description="DPI масштаб монитора")
    rect: RectCoordinates = Field(description="Глобальные экранные координаты")


class WindowInfo(BaseModel):
    """Информация об открытом окне приложения."""
    id: int = Field(description="Дескриптор окна (HWND)")
    title: str = Field(description="Заголовок окна")
    process_name: str = Field(default="", description="Имя исполняемого файла процесса")
    pid: int = Field(default=0, description="Идентификатор процесса (PID)")
    width: int = Field(default=0, description="Ширина клиентской области")
    height: int = Field(default=0, description="Высота клиентской области")
    rect: RectCoordinates = Field(description="Экранные координаты окна")
    is_minimized: bool = Field(default=False, description="Свернуто ли окно")
    is_visible: bool = Field(default=True, description="Видимо ли окно на экране")
    is_hung: bool = Field(default=False, description="Признак зависания (IsHungAppWindow)")


class CapturedFrame(BaseModel):
    """Снимок экрана или отдельного окна."""
    frame_id: str = Field(description="Уникальный идентификатор кадра (UUID/штамп)")
    timestamp_utc: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Время создания кадра в формате UTC ISO 8601"
    )
    target_type: CaptureTargetType = Field(description="Тип цели захвата")
    target_id: str = Field(description="Идентификатор цели (ID монитора или HWND окна)")
    target_title: str = Field(default="", description="Название цели (имя монитора или заголовок окна)")
    width: int = Field(description="Фактическая ширина кадра")
    height: int = Field(description="Фактическая высота кадра")
    format: str = Field(default="png", description="Формат сжатия изображения (png/jpeg/webp)")
    data_base64: str = Field(default="", description="Base64 Data URL (data:image/png;base64,...)")
    size_bytes: int = Field(default=0, description="Размер сжатого изображения в байтах")
    backend_used: str = Field(default="gdi", description="Бэкенд, использованный для захвата")
    diff_ratio: float = Field(default=0.0, description="Доля изменившихся пикселей по сравнению с предыдущим кадром (0.0..1.0)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Дополнительные метаданные (DPI, GPU, процесс)")


class VisualTelemetryEvent(BaseModel):
    """Событие корреляции визуального кадра с системной телеметрией и ETW."""
    timestamp_utc: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    frame_id: str = Field(description="ID снимка экрана")
    target_name: str = Field(description="Имя монитора или окна")
    cpu_percent: float = Field(default=0.0, description="Загрузка CPU в момент кадра")
    memory_mb: float = Field(default=0.0, description="Использование памяти")
    disk_active_percent: float = Field(default=0.0, description="Активность накопителя")
    etw_incident_count: int = Field(default=0, description="Количество связанных ETW-инцидентов")
    is_app_hung: bool = Field(default=False, description="Признак визуального зависания приложения")
    diff_detected: bool = Field(default=True, description="Обнаружены ли визуальные изменения")
    diff_ratio: float = Field(default=0.0, description="Величина изменения экрана")
    analysis_notes: str = Field(default="", description="Заключение аналитического движка")


class CaptureEngineConfig(BaseModel):
    """Конфигурация параметров экранного захвата."""
    backend: CaptureBackendType = Field(default=CaptureBackendType.AUTO, description="Предпочитаемый бэкенд захвата")
    fps_limit: int = Field(default=10, ge=1, le=60, description="Лимит частоты кадров при потоковом захвате")
    image_format: str = Field(default="jpeg", description="Формат передачи кадров (jpeg, png, webp)")
    image_quality: int = Field(default=80, ge=10, le=100, description="Качество сжатия JPEG (10-100)")
    max_resolution_width: int = Field(default=1920, description="Максимальная ширина кадра для превью (масштабирование)")
    diff_threshold: float = Field(default=0.02, description="Порог существенного изменения экрана для фиксации событий (2%)")
    enable_etw_correlation: bool = Field(default=True, description="Включить сопоставление кадров с ETW-телеметрией")
    history_buffer_size: int = Field(default=30, ge=5, le=120, description="Размер кольцевого буфера истории кадров")


class StreamStatus(BaseModel):
    """Текущее состояние потокового захвата."""
    is_streaming: bool = Field(default=False, description="Активен ли поток захвата")
    target_type: Optional[CaptureTargetType] = None
    target_id: Optional[str] = None
    target_title: Optional[str] = None
    fps_actual: float = Field(default=0.0, description="Фактическая частота кадров в секунду")
    total_frames_captured: int = Field(default=0, description="Всего захвачено кадров за текущую сессию")
    backend_active: str = Field(default="gdi", description="Активный бэкенд захвата")
    last_frame_timestamp: Optional[str] = None
