# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Router Power Lifecycle Test
# =============================================================================
# Description:
#   Модульные тесты для проверки API роутера жизненного цикла питания
#   (/api/v1/power/*) и корректности получения сессий и сводки питания.
#
# Usage Examples:
#   pytest tests/test_router_power_lifecycle.py
#
# File: test_router_power_lifecycle.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-20 13:44:00
# =============================================================================

"""Тесты роутера жизненного цикла питания и аптайма системы."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.windows.api.routers.router_power_lifecycle import init_router


@pytest.fixture
def client():
    """Фикстура тестового клиента FastAPI с подключенным роутером питания."""
    app = FastAPI()
    app.include_router(init_router())
    return TestClient(app)


def test_power_summary_endpoint(client):
    """Проверка эндпоинта сводки жизненного цикла питания."""
    response = client.get("/api/v1/power/summary")
    assert response.status_code == 200
    data = response.json()
    assert "current_uptime_seconds" in data
    assert "total_sessions_count" in data
    assert "clean_shutdowns_count" in data
    assert "unexpected_shutdowns_count" in data
    assert isinstance(data["current_uptime_seconds"], (int, float))


def test_power_sessions_endpoint(client):
    """Проверка эндпоинта списка сессий питания."""
    response = client.get("/api/v1/power/sessions?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if data:
        first = data[0]
        assert "session_id" in first
        assert "boot_time" in first
        assert "shutdown_type" in first


def test_power_events_endpoint(client):
    """Проверка эндпоинта журнала событий питания."""
    response = client.get("/api/v1/power/events?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if data:
        first = data[0]
        assert "event_id" in first
        assert "timestamp" in first
        assert "provider" in first

