# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Window Control Plane Router
# =============================================================================
# Description:
#   Модульные тесты REST API эндпоинта настроек пользовательского окружения
#   (User Environment Settings, /api/v1/user-environment-settings).
#
# File: test_router.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.window_control_plane.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 20:50:00
# =============================================================================

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.windows.sdk.modules.window_control_plane.router import init_router, router


@pytest.fixture
def test_client() -> TestClient:
    """Фикстура для создания тестового приложения FastAPI и клиента."""
    app = FastAPI()
    app.include_router(init_router())
    return TestClient(app)


def test_get_user_environment_settings_endpoint(test_client: TestClient) -> None:
    """Эндпоинт GET /api/v1/user-environment-settings возвращает 15 категорий настроек."""
    response = test_client.get("/api/v1/user-environment-settings")
    assert response.status_code == 200
    data = response.json()
    assert "total_categories" in data
    assert data["total_categories"] == 15
    assert "categories" in data
    assert len(data["categories"]) == 15
    first_cat = data["categories"][0]
    assert "category_id" in first_cat
    assert "items" in first_cat


def test_openapi_schema_user_environment_settings() -> None:
    """Проверка наличия эндпоинта, summary и docstring в схеме OpenAPI."""
    app = FastAPI()
    app.include_router(init_router())
    schema = app.openapi()
    paths = schema.get("paths", {})
    assert "/api/v1/user-environment-settings" in paths
    endpoint_spec = paths["/api/v1/user-environment-settings"].get("get", {})
    assert endpoint_spec.get("summary") == "Get User Environment Settings"
    assert "Список всех настроек пользовательского окружения" in endpoint_spec.get("description", "")


def test_windows_router_does_not_contain_broken_nested_route() -> None:
    """Проверка, что apps.windows.router не содержит вложенный сломанный путь."""
    from apps.windows.router import router as windows_router
    app = FastAPI()
    app.include_router(windows_router)
    schema = app.openapi()
    paths = list(schema.get("paths", {}).keys())
    assert not any("window-management/api/v1" in p for p in paths)

