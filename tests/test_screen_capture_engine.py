# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Screen Capture Engine Test Suite
# =============================================================================
# Description:
#   Набор модульных и интеграционных тестов для подсистемы Windows.Graphics.Capture,
#   GDI fallback, Screen Diff, корреляции с ETW-телеметрией и REST API.
#
# Usage Examples:
#   pytest tests/test_screen_capture_engine.py -v
#
# File: test_screen_capture_engine.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 02:58:00
# =============================================================================

from __future__ import annotations
"""Тесты модулей экранного захвата, детектора изменений и REST API роутера."""

import time
import pytest
from PIL import Image
from fastapi.testclient import TestClient

from apps.windows.vision.screen_capture import (
    CaptureBackendType,
    CaptureEngineConfig,
    CaptureTargetType,
    CapturedFrame,
    ScreenCaptureEngine,
    ScreenDiffEngine,
    VisualIntelligenceEngine,
)
from apps.windows.vision.screen_capture.backends.wgc_backend import WgcCaptureBackend
from apps.windows.vision.screen_capture.models import WindowInfo, RectCoordinates
from apps.windows.api.routers.router_screen_capture import router


@pytest.fixture
def capture_engine() -> ScreenCaptureEngine:
    """Фикстура создания изолированного экземпляра ScreenCaptureEngine."""
    config = CaptureEngineConfig(
        backend=CaptureBackendType.GDI,
        fps_limit=15,
        image_format="jpeg",
        image_quality=75,
        diff_threshold=0.02,
        history_buffer_size=20,
    )
    engine = ScreenCaptureEngine(config=config)
    yield engine
    engine.stop_stream()


def test_list_displays(capture_engine: ScreenCaptureEngine):
    """Проверка перечисления активных дисплеев системы."""
    displays = capture_engine.list_displays()
    assert isinstance(displays, list)
    assert len(displays) > 0
    primary = displays[0]
    assert primary.width > 0
    assert primary.height > 0
    assert primary.rect.width == primary.width


def test_list_windows(capture_engine: ScreenCaptureEngine):
    """Проверка перечисления открытых окон приложений."""
    windows = capture_engine.list_windows()
    assert isinstance(windows, list)
    for w in windows[:5]:
        assert isinstance(w, WindowInfo)
        assert w.id != 0
        assert len(w.title) > 0


def test_capture_display(capture_engine: ScreenCaptureEngine):
    """Проверка моментального захвата экрана."""
    frame = capture_engine.capture_display(display_id=0)
    assert frame is not None
    assert isinstance(frame, CapturedFrame)
    assert frame.width > 0
    assert frame.height > 0
    assert frame.data_base64.startswith("data:image/jpeg;base64,")
    assert frame.size_bytes > 0


def test_capture_window_fallback(capture_engine: ScreenCaptureEngine):
    """Проверка захвата существующего окна."""
    windows = capture_engine.list_windows()
    if windows:
        target_win = windows[0]
        frame = capture_engine.capture_window(window_id=target_win.id)
        if frame:
            assert frame.target_type == CaptureTargetType.WINDOW
            assert frame.target_id == str(target_win.id)
            assert frame.data_base64.startswith("data:image/jpeg;base64,")


def test_screen_diff_engine():
    """Проверка дифференциального анализа между идентичными и измененными изображениями."""
    diff_engine = ScreenDiffEngine(threshold=0.05)

    img_black = Image.new("RGB", (200, 200), color=(0, 0, 0))
    img_black_clone = Image.new("RGB", (200, 200), color=(0, 0, 0))
    img_white = Image.new("RGB", (200, 200), color=(255, 255, 255))

    # Сравнение идентичных изображений
    ratio_same, bbox_same = diff_engine.compute_diff(img_black, img_black_clone)
    assert ratio_same == 0.0
    assert bbox_same is None
    assert not diff_engine.is_significant_change(ratio_same)

    # Сравнение кардинально разных изображений
    ratio_diff, bbox_diff = diff_engine.compute_diff(img_black, img_white)
    assert ratio_diff > 0.90
    assert bbox_diff is not None
    assert diff_engine.is_significant_change(ratio_diff)

    # RMS разность
    rms_val = diff_engine.compute_root_mean_square(img_black, img_white)
    assert rms_val > 200.0


def test_visual_intelligence_and_etw_correlation(capture_engine: ScreenCaptureEngine):
    """Проверка сопоставления кадра с системной телеметрией и ETW."""
    intel = VisualIntelligenceEngine(max_history_events=10)
    metrics = intel.sample_system_telemetry()
    assert "cpu_percent" in metrics
    assert "memory_mb" in metrics
    assert metrics["memory_mb"] > 0

    dummy_frame = CapturedFrame(
        frame_id="test_frame_1",
        target_type=CaptureTargetType.DISPLAY,
        target_id="0",
        width=1920,
        height=1080,
        diff_ratio=0.03,
    )

    dummy_window = WindowInfo(
        id=12345,
        title="Test App",
        process_name="testapp.exe",
        pid=9999,
        width=800,
        height=600,
        rect=RectCoordinates(left=0, top=0, right=800, bottom=600, width=800, height=600),
        is_hung=True,
    )

    event = intel.correlate(frame=dummy_frame, window_info=dummy_window, etw_incidents_count=2)
    assert event.frame_id == "test_frame_1"
    assert event.is_app_hung is True
    assert event.diff_detected is True
    assert "IsHungAppWindow" in event.analysis_notes
    assert len(intel.get_events_history()) == 1


def test_streaming_lifecycle(capture_engine: ScreenCaptureEngine):
    """Проверка запуска, получения кадра и остановки фонового потока."""
    started = capture_engine.start_stream(target=0)
    assert started is True

    status_start = capture_engine.get_stream_status()
    assert status_start.is_streaming is True

    # Даем фоновому потоку время захватить кадр
    time.sleep(0.3)

    latest = capture_engine.get_latest_frame()
    assert latest is not None
    assert latest.target_type == CaptureTargetType.DISPLAY

    stopped = capture_engine.stop_stream()
    assert stopped is True

    status_end = capture_engine.get_stream_status()
    assert status_end.is_streaming is False


def test_wgc_capabilities():
    """Проверка детекции возможностей Windows.Graphics.Capture API."""
    probe = WgcCaptureBackend()
    caps = probe.get_capabilities()
    assert "wgc_api_supported" in caps
    assert "namespaces" in caps
    assert "Windows.Graphics.Capture" in caps["namespaces"]


def test_screen_capture_api_endpoints():
    """Тестирование REST API эндпоинтов роутера через TestClient."""
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    # 1. Capabilities
    res_caps = client.get("/api/v1/vision/capture/capabilities")
    assert res_caps.status_code == 200
    assert res_caps.json()["status"] == "ok"

    # 2. Displays
    res_disp = client.get("/api/v1/vision/capture/displays")
    assert res_disp.status_code == 200
    displays = res_disp.json()
    assert len(displays) > 0

    # 3. Windows
    res_win = client.get("/api/v1/vision/capture/windows?limit=10")
    assert res_win.status_code == 200
    assert isinstance(res_win.json(), list)

    # 4. Config GET & POST
    res_cfg_get = client.get("/api/v1/vision/capture/config")
    assert res_cfg_get.status_code == 200
    cfg_data = res_cfg_get.json()
    assert "fps_limit" in cfg_data

    cfg_data["fps_limit"] = 12
    res_cfg_post = client.post("/api/v1/vision/capture/config", json=cfg_data)
    assert res_cfg_post.status_code == 200
    assert res_cfg_post.json()["fps_limit"] == 12

    # 5. Capture display
    res_cap = client.post("/api/v1/vision/capture/display", json={"display_id": 0})
    assert res_cap.status_code == 200
    frame = res_cap.json()
    assert frame["width"] > 0
    assert "data_base64" in frame

    # 6. Stream Status
    res_status = client.get("/api/v1/vision/capture/stream/status")
    assert res_status.status_code == 200
