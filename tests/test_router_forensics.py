# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Router Forensics Test
# =============================================================================
# Description:
#   Модульные тесты для проверки API роутера поведенческой форензики
#   (/api/v1/system/diagnostics/forensics) и корректности получения срезов из SQLite.
#
# Usage Examples:
#   pytest tests/test_router_forensics.py
#
# File: test_router_forensics.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-16 20:58:00
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
    """Проверка эндпоинта радара приватности камеры и микрофона."""
    response = client.get("/api/v1/system/diagnostics/privacy-status")
    assert response.status_code == 200
    data = response.json()
    assert "camera_active_apps" in data
    assert "microphone_active_apps" in data
    assert "user_idle_seconds" in data

