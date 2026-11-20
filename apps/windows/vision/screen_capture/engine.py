# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Screen Capture - Main Engine
# =============================================================================
# Description:
#   Центральный координатор захвата экранов и окон Windows.Graphics.Capture & GDI,
#   потокового вещания, дифференциального анализа и корреляции с телеметрией.
#
# Usage Examples:
#   from apps.windows.vision.screen_capture import ScreenCaptureEngine
#   engine = ScreenCaptureEngine()
#   displays = engine.list_displays()
#   frame = engine.capture_display(0)
#
# File: engine.py
# Project: ai-windows-admin
# Package: apps.windows.vision.screen_capture
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 02:52:00
# =============================================================================

from __future__ import annotations
"""Основной движок ScreenCaptureEngine для захвата экранов, окон и видеопотока."""

import base64
from datetime import datetime, timezone
import io
import threading
import time
from typing import Any, Dict, List, Optional, Union
import uuid
from PIL import Image

from logger import logger
from apps.windows.vision.screen_capture.backends.base import BaseCaptureBackend
from apps.windows.vision.screen_capture.backends.gdi_backend import GdiCaptureBackend
from apps.windows.vision.screen_capture.backends.wgc_backend import WgcCaptureBackend
from apps.windows.vision.screen_capture.models import (
    CaptureBackendType,
    CaptureEngineConfig,
    CaptureTargetType,
    CapturedFrame,
    DisplayInfo,
    StreamStatus,
    VisualTelemetryEvent,
    WindowInfo,
)
from apps.windows.vision.screen_capture.screen_diff import ScreenDiffEngine
from apps.windows.vision.screen_capture.visual_intelligence import VisualIntelligenceEngine


class ScreenCaptureEngine:
    """
    Единый API-движок экранного захвата для AI-TC:
    - Захват дисплеев и отдельных окон приложений
    - Интеграция с Windows.Graphics.Capture, DXGI и Win32 GDI
    - Потоковый захват с контролем FPS
    - Детектирование визуальных изменений (Screen Diff)
    - Корреляция с системной ETW-телеметрией
    """

    def __init__(self, config: Optional[CaptureEngineConfig] = None) -> None:
        """Инициализация движка, бэкендов и фоновых служб."""
        self._config = config or CaptureEngineConfig()
        self._gdi_backend = GdiCaptureBackend()
        self._wgc_backend = WgcCaptureBackend(fallback_backend=self._gdi_backend)
        self._diff_engine = ScreenDiffEngine(threshold=self._config.diff_threshold)
        self._intel_engine = VisualIntelligenceEngine(max_history_events=self._config.history_buffer_size)

        # Состояние потокового захвата
        self._stream_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._stream_lock = threading.Lock()
        self._stream_target: Optional[Dict[str, Any]] = None
        self._latest_frame: Optional[CapturedFrame] = None
        self._previous_pil_image: Optional[Image.Image] = None

        # Статистика потока
        self._stream_start_time: float = 0.0
        self._frames_counter: int = 0
        self._actual_fps: float = 0.0

    def _select_backend(self) -> BaseCaptureBackend:
        """Выбирает активный бэкенд на основании конфигурации и возможностей системы."""
        if self._config.backend == CaptureBackendType.WGC:
            return self._wgc_backend
        if self._config.backend == CaptureBackendType.GDI:
            return self._gdi_backend
        # Режим AUTO: проверяем WGC, иначе GDI
        return self._wgc_backend if self._wgc_backend.is_available() else self._gdi_backend

    def list_displays(self) -> List[DisplayInfo]:
        """Возвращает список доступных экранов и мониторов."""
        backend = self._select_backend()
        return backend.list_displays()

    def list_windows(self) -> List[WindowInfo]:
        """Возвращает список видимых окон верхнего уровня."""
        backend = self._select_backend()
        return backend.list_windows()

    def capture_display(self, display_id: int = 0) -> Optional[CapturedFrame]:
        """Захватывает указанный монитор целиком."""
        backend = self._select_backend()
        pil_img = backend.capture_display(display_id)
        if not pil_img:
            return None

        displays = backend.list_displays()
        disp_title = next((d.name for d in displays if d.id == display_id), f"Display #{display_id}")
        return self._process_captured_image(
            pil_img=pil_img,
            target_type=CaptureTargetType.DISPLAY,
            target_id=str(display_id),
            target_title=disp_title,
            backend_name=backend.name,
        )

    def capture_window(self, window_id: int) -> Optional[CapturedFrame]:
        """Захватывает отдельное окно по его дескриптору (HWND)."""
        backend = self._select_backend()
        pil_img = backend.capture_window(window_id)
        if not pil_img:
            return None

        windows = backend.list_windows()
        wnd_info = next((w for w in windows if w.id == window_id), None)
        wnd_title = wnd_info.title if wnd_info else f"Window HWND {window_id}"

        frame = self._process_captured_image(
            pil_img=pil_img,
            target_type=CaptureTargetType.WINDOW,
            target_id=str(window_id),
            target_title=wnd_title,
            backend_name=backend.name,
            window_info=wnd_info,
        )
        return frame

    def start_stream(self, target: Union[int, Dict[str, Any], str] = 0) -> bool:
        """
        Запускает фоновый поток захвата для монитора или окна.

        Args:
            target: ID монитора (int), HWND окна (int) или словарь конфигурации цели:
                    {'type': 'display'|'window', 'id': int}.

        Returns:
            bool: True если стрим успешно запущен, False если уже активен или ошибка.
        """
        with self._stream_lock:
            if self._stream_thread and self._stream_thread.is_alive():
                logger.warning("[ScreenCaptureEngine] Поток захвата уже запущен")
                return False

            parsed_target: Dict[str, Any] = {}
            if isinstance(target, dict):
                parsed_target = target
            elif isinstance(target, int):
                # Если число больше 10000, скорее всего это HWND окна, иначе индекс дисплея
                if target >= 10000:
                    parsed_target = {"type": CaptureTargetType.WINDOW, "id": target}
                else:
                    parsed_target = {"type": CaptureTargetType.DISPLAY, "id": target}
            else:
                parsed_target = {"type": CaptureTargetType.DISPLAY, "id": 0}

            self._stream_target = parsed_target
            self._stop_event.clear()
            self._stream_start_time = time.time()
            self._frames_counter = 0
            self._actual_fps = 0.0

            self._stream_thread = threading.Thread(
                target=self._stream_worker,
                daemon=True,
                name="ScreenCaptureStreamWorker",
            )
            self._stream_thread.start()
            logger.console(f"[ScreenCaptureEngine] Запущен стрим для цели: {parsed_target}", text_color="green")
            return True

    def stop_stream(self) -> bool:
        """Останавливает активный фоновый поток захвата."""
        with self._stream_lock:
            if not self._stream_thread or not self._stream_thread.is_alive():
                return False

            self._stop_event.set()
            self._stream_thread.join(timeout=2.0)
            self._stream_thread = None
            logger.console("[ScreenCaptureEngine] Поток экранного захвата остановлен", text_color="yellow")
            return True

    def get_latest_frame(self) -> Optional[CapturedFrame]:
        """Возвращает самый свежий полученный кадр из потока захвата."""
        with self._stream_lock:
            return self._latest_frame

    def get_stream_status(self) -> StreamStatus:
        """Возвращает текущие метрики и состояние потокового захвата."""
        with self._stream_lock:
            is_active = self._stream_thread is not None and self._stream_thread.is_alive()
            target_type = self._stream_target.get("type") if self._stream_target else None
            target_id = str(self._stream_target.get("id")) if self._stream_target else None
            latest_ts = self._latest_frame.timestamp_utc if self._latest_frame else None
            active_be = self._select_backend().name

            return StreamStatus(
                is_streaming=is_active,
                target_type=target_type,
                target_id=target_id,
                target_title=self._latest_frame.target_title if self._latest_frame else None,
                fps_actual=round(self._actual_fps, 1),
                total_frames_captured=self._frames_counter,
                backend_active=active_be,
                last_frame_timestamp=latest_ts,
            )

    def get_config(self) -> CaptureEngineConfig:
        """Возвращает текущие параметры конфигурации."""
        return self._config

    def update_config(self, new_config: CaptureEngineConfig) -> None:
        """Обновляет параметры захвата и применяет изменения."""
        self._config = new_config
        self._diff_engine.threshold = new_config.diff_threshold
        logger.console(f"[ScreenCaptureEngine] Конфигурация обновлена: backend={new_config.backend}, fps={new_config.fps_limit}", text_color="cyan")

    def get_frame_history(self, limit: int = 20) -> List[CapturedFrame]:
        """Возвращает визуальную историю кадров."""
        return self._intel_engine.get_frame_history(limit)

    def get_telemetry_events(self, limit: int = 50) -> List[VisualTelemetryEvent]:
        """Возвращает историю событий корреляции кадра с телеметрией/ETW."""
        return self._intel_engine.get_events_history(limit)

    def _stream_worker(self) -> None:
        """Фоновый цикл захвата кадров с соблюдением частоты FPS."""
        fps_target = max(1, self._config.fps_limit)
        frame_delay = 1.0 / fps_target
        fps_check_time = time.time()
        fps_frames = 0

        while not self._stop_event.is_set():
            t_start = time.perf_counter()

            target_type = self._stream_target.get("type", CaptureTargetType.DISPLAY)
            target_id = int(self._stream_target.get("id", 0))

            frame: Optional[CapturedFrame] = None
            if target_type == CaptureTargetType.WINDOW:
                frame = self.capture_window(target_id)
            else:
                frame = self.capture_display(target_id)

            if frame:
                with self._stream_lock:
                    self._latest_frame = frame
                    self._frames_counter += 1
                fps_frames += 1

            # Расчет фактического FPS раз в секунду
            now = time.time()
            if now - fps_check_time >= 1.0:
                self._actual_fps = fps_frames / (now - fps_check_time)
                fps_check_time = now
                fps_frames = 0

            # Пауза до следующего кадра
            elapsed = time.perf_counter() - t_start
            sleep_time = max(0.001, frame_delay - elapsed)
            time.sleep(sleep_time)

    def _process_captured_image(
        self,
        pil_img: Image.Image,
        target_type: CaptureTargetType,
        target_id: str,
        target_title: str,
        backend_name: str,
        window_info: Optional[WindowInfo] = None,
    ) -> CapturedFrame:
        """Сжимает изображение, вычисляет diff ratio и корреляцию с телеметрией."""
        orig_w, orig_h = pil_img.size

        # Расчет разницы со снимком предыдущего кадра
        diff_ratio, _ = self._diff_engine.compute_diff(self._previous_pil_image, pil_img)
        self._previous_pil_image = pil_img.copy()

        # Масштабирование при необходимости
        img_to_encode = pil_img
        if orig_w > self._config.max_resolution_width:
            scale = self._config.max_resolution_width / float(orig_w)
            new_h = int(orig_h * scale)
            img_to_encode = pil_img.resize((self._config.max_resolution_width, new_h), Image.Resampling.BILINEAR)

        # Кодирование в Base64
        buf = io.BytesIO()
        fmt = self._config.image_format.upper()
        if fmt == "JPG":
            fmt = "JPEG"
        if fmt == "JPEG":
            img_to_encode.convert("RGB").save(buf, format="JPEG", quality=self._config.image_quality, optimize=True)
            mime = "image/jpeg"
        else:
            img_to_encode.save(buf, format="PNG", optimize=False)
            mime = "image/png"

        raw_bytes = buf.getvalue()
        b64_data = f"data:{mime};base64," + base64.b64encode(raw_bytes).decode("ascii")

        frame = CapturedFrame(
            frame_id=f"frame_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}",
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            target_type=target_type,
            target_id=target_id,
            target_title=target_title,
            width=orig_w,
            height=orig_h,
            format=self._config.image_format,
            data_base64=b64_data,
            size_bytes=len(raw_bytes),
            backend_used=backend_name,
            diff_ratio=diff_ratio,
            metadata={
                "encoded_width": img_to_encode.width,
                "encoded_height": img_to_encode.height,
            },
        )

        # Корреляция с телеметрией и ETW
        if self._config.enable_etw_correlation:
            self._intel_engine.correlate(frame=frame, window_info=window_info)

        return frame
