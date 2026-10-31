# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - AI Assistant Bridge Test
# =============================================================================
# Description:
#   Тестирование моста между FastAPI приложениями apps/windows и apps/ai_assistant.
#   Проверяет эндпоинты статуса моста, маршруты WebGUI и делегирование Panel API.
#
# Usage Examples:
#   pytest tests/test_ai_assistant_bridge.py -v
#
# File: test_ai_assistant_bridge.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-20 13:35:00
# =============================================================================

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from apps.windows.api.server import create_app


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Создаёт тестовый клиент FastAPI приложения с подключенным мостом."""
    app = create_app()
    return TestClient(app)


def test_bridge_status_endpoint(client: TestClient) -> None:
    """Проверка доступности эндпоинта статуса моста."""
    response = client.get("/api/v1/bridge/status")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "ok"
    assert "windows" in data.get("apps", {})
    assert "ai_assistant" in data.get("apps", {})
    assert data["apps"]["ai_assistant"]["webgui_exists"] is True


def test_ai_assistant_webgui_routes(client: TestClient) -> None:
    """Проверка отдачи HTML интерфейса Умной истории файлов."""
    for path in ("/ai_assistant", "/ai-assistant", "/smart-history"):
        response = client.get(path)
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "AI Assistant" in response.text or "Smart Version History" in response.text


def test_ai_assistant_api_history_route(client: TestClient) -> None:
    """Проверка доступности истории Git через объединенный сервер."""
    response = client.get("/api/v1/history?limit=2")
    assert response.status_code == 200
    commits = response.json()
    assert isinstance(commits, list)


def test_ai_assistant_panel_delegation(client: TestClient) -> None:
    """Проверка делегирования запросов Panel API для панелей истории Git."""
    response = client.get("/api/v1/panel/panel-timeline?limit=2")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "ok"
    assert data.get("panel_id") == "panel-timeline"
    assert "data" in data

