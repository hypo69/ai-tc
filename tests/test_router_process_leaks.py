# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Router Process Leaks Test
# =============================================================================
# Description:
#   Модульные тесты для проверки API диагностики утечек ресурсов процессов
#   (/api/v1/system/diagnostics/leaks и refresh). Проверяет чтение срезов
#   из локальной базы данных SQLite без внешних накладных расходов.
#
# Usage Examples:
#   pytest tests/test_router_process_leaks.py
#
# File: test_router_process_leaks.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-17 02:56:00
# =============================================================================

"""Тесты эндпоинтов диагностики утечек процессов (GET/POST /api/v1/system/diagnostics/leaks)."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.windows.api.routers.router_about_system import init_router


@pytest.fixture
def client():
    """Фикстура тестового клиента FastAPI с подключенным роутером панели О системе."""
    app = FastAPI()
    app.include_router(init_router())
    return TestClient(app)


def test_get_process_leaks_endpoint(client):
    """Проверка возврата среза утечек процессов из SQLite через GET запрос."""
    response = client.get("/api/v1/system/diagnostics/leaks?limit=50")
    assert response.status_code == 200
    data = response.json()
    assert "total_processes" in data
    assert "suspicious_count" in data
    assert "all_processes" in data
    assert "top_handle_hogs" in data
    assert "top_gdi_hogs" in data
    assert "top_page_fault_hogs" in data
    assert isinstance(data["all_processes"], list)


def test_refresh_process_leaks_endpoint_reads_from_db(client):
    """Проверка, что POST запрос обновления утечек процессов возвращает данные из SQLite."""
    response = client.post("/api/v1/system/diagnostics/leaks/refresh?limit=50")
    assert response.status_code == 200
    data = response.json()
    assert "total_processes" in data
    assert "suspicious_count" in data
    assert "all_processes" in data
    assert isinstance(data["all_processes"], list)


def test_tc_process_leaks_alias_endpoints(client):
    """Проверка работы альтернативных алиасов /api/v1/tc/process-leaks."""
    get_res = client.get("/api/v1/tc/process-leaks?limit=10")
    assert get_res.status_code == 200
    assert "all_processes" in get_res.json()

    post_res = client.post("/api/v1/tc/process-leaks/refresh?limit=10")
    assert post_res.status_code == 200
    assert "all_processes" in post_res.json()

