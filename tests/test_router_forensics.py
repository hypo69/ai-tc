# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Tests - Router Forensics Test
# =============================================================================
# Description:
#   Модульные тесты для проверки API роутера поведенческой форензики
#   (/api/v1/system/diagnostics/forensics) и корректности получения срезов из SQLite.
#
# Usage Examples:
#   pytest tests/test_router_forensics.py
#
# File: test_router_forensics.py
# Project: ai-tc
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 12:35:00
# =============================================================================

"""Тесты роутера поведенческой форензики и сбора телеметрии активности."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.windows.api.routers.router_forensics import init_router
from apps.windows.telemetry.sqlite import TelemetryStorage


@pytest.fixture
def client():
    """Фикстура тестового клиента FastAPI с подключенным роутером форензики."""
    app = FastAPI()
    storage = TelemetryStorage.get_instance(read_only=True)
    app.include_router(init_router(storage=storage))
    return TestClient(app)


def test_forensics_endpoint_returns_data(client):
    """Проверка возврата валидного среза форензики из базы данных."""
    response = client.get("/api/v1/system/diagnostics/forensics")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "foreground_window" in data
    assert "user_idle_seconds" in data
    assert "userassist_top_apps" in data
    assert "history" in data
    assert isinstance(data["history"], list)
    assert isinstance(data["userassist_top_apps"], list)


def test_forensics_history_endpoint(client):
    """Проверка эндпоинта истории таймлайна активности."""
    response = client.get("/api/v1/system/diagnostics/forensics/history?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if len(data) > 0:
        item = data[0]
        assert "snapshot_id" in item
        assert "timestamp" in item
        assert "foreground_window" in item


def test_privacy_status_endpoint(client):
    """Проверка эндпоинта радара приватности камеры, микрофона и звука."""
    response = client.get("/api/v1/system/diagnostics/privacy-status")
    assert response.status_code == 200
    data = response.json()
    assert "camera_active_apps" in data
    assert "microphone_active_apps" in data
    assert "audio_playback_apps" in data
    assert "audio_capture_apps" in data
    assert "user_idle_seconds" in data


def test_forensics_audio_sessions_endpoint(client):
    """Проверка эндпоинта оперативного опроса аудиосессий WASAPI."""
    response = client.get("/api/v1/system/diagnostics/forensics/audio-sessions")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if len(data) > 0:
        session = data[0]
        assert "name" in session
        assert "pid" in session
        assert "device_flow" in session
        assert "is_active_now" in session


def test_forensics_super_timeline_endpoint(client):
    """Проверка эндпоинта супер-таймлайна цифровых доказательств."""
    response = client.get("/api/v1/system/diagnostics/forensics/super-timeline?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if len(data) > 0:
        item = data[0]
        assert "timestamp" in item
        assert "category" in item
        assert "source" in item
        assert "action" in item


def test_forensics_usb_artifacts_endpoint(client):
    """Проверка эндпоинта аппаратных доказательств USBSTOR."""
    response = client.get("/api/v1/system/diagnostics/forensics/artifacts/usb")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_forensics_reboots_endpoint(client):
    """Проверка эндпоинта событий выключения и сбоев ОС."""
    response = client.get("/api/v1/system/diagnostics/forensics/artifacts/reboots?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_forensics_investigate_endpoint(client):
    """Проверка интеллектуальной реконструкции инцидента."""
    payload = {"scenario_type": "reboot_crash", "window_minutes": 30}
    response = client.post("/api/v1/system/diagnostics/forensics/investigate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "investigation_id" in data
    assert "scenario_type" in data
    assert "root_cause_analysis" in data
    assert "confidence_score" in data
    assert "chain_of_custody" in data


def test_forensics_chain_of_custody_endpoint(client):
    """Проверка цепочки сохранности доказательств и SHA-256."""
    response = client.get("/api/v1/system/diagnostics/forensics/chain-of-custody")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert "sha256_hash" in data[0]
    assert "verified" in data[0]



