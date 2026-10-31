# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Peripherals Diagnostics Endpoint
# =============================================================================
# Description:
#   Модульные и интеграционные тесты эндпоинта диагностики периферии
#   (/api/v1/system/diagnostics/peripherals и /api/v1/tc/peripherals).
#
# File: test_peripherals_diagnostics.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-16 23:15:00
# =============================================================================

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.windows.api.routers.router_about_system import init_router
from apps.windows.api.routers.about_system.query_diagnostics import query_peripherals_diagnostics
from apps.windows.telemetry.sqlite import TelemetryStorage


@pytest.fixture(scope="module")
def api_client() -> TestClient:
    """Фикстура тестового клиента FastAPI с подключенным роутером about_system.

    Returns:
        TestClient: Клиент для выполнения тестовых HTTP-запросов.
    """
    app = FastAPI()
    app.include_router(init_router())
    return TestClient(app)


def test_get_peripherals_diagnostics_endpoint_returns_200(api_client: TestClient) -> None:
    """Проверяет успешность выполнения GET /api/v1/system/diagnostics/peripherals (200 OK)."""
    res = api_client.get("/api/v1/system/diagnostics/peripherals")
    assert res.status_code == 200, f"Ожидался статус 200, получен {res.status_code}"
    
    data = res.json()
    assert "usb_devices" in data, "Отсутствует ключ usb_devices в ответе"
    assert "wifi_telemetry" in data, "Отсутствует ключ wifi_telemetry в ответе"
    assert "audio_endpoints" in data, "Отсутствует ключ audio_endpoints в ответе"
    assert "bluetooth_devices" in data, "Отсутствует ключ bluetooth_devices в ответе"
    assert "printers" in data, "Отсутствует ключ printers в ответе"
    assert "timestamp" in data, "Отсутствует ключ timestamp в ответе"
    assert isinstance(data["usb_devices"], list), "usb_devices должен быть списком"
    assert isinstance(data["wifi_telemetry"], dict), "wifi_telemetry должен быть словарем"
    assert isinstance(data["audio_endpoints"], list), "audio_endpoints должен быть списком"
    assert isinstance(data["bluetooth_devices"], list), "bluetooth_devices должен быть списком"
    assert isinstance(data["printers"], list), "printers должен быть списком"


def test_get_tc_peripherals_alias_returns_200(api_client: TestClient) -> None:
    """Проверяет алиас маршрута GET /api/v1/tc/peripherals."""
    res = api_client.get("/api/v1/tc/peripherals")
    assert res.status_code == 200, f"Ожидался статус 200, получен {res.status_code}"
    data = res.json()
    assert "usb_devices" in data
    assert "bluetooth_devices" in data
    assert "printers" in data


def test_post_peripherals_refresh_endpoint_returns_200(api_client: TestClient) -> None:
    """Проверяет принудительное обновление через POST /api/v1/system/diagnostics/peripherals/refresh."""
    res = api_client.post("/api/v1/system/diagnostics/peripherals/refresh")
    assert res.status_code == 200, f"Ожидался статус 200, получен {res.status_code}"
    data = res.json()
    assert data.get("status") == "ok"
    assert "usb_devices" in data
    assert "bluetooth_devices" in data
    assert "printers" in data


@pytest.mark.asyncio
async def test_query_peripherals_diagnostics_function() -> None:
    """Проверяет непосредственный вызов сервисной функции query_peripherals_diagnostics."""
    storage = TelemetryStorage.get_instance(read_only=True)
    res = await query_peripherals_diagnostics(storage, force_refresh=True)
    assert isinstance(res, dict)
    assert "usb_devices" in res
    assert "wifi_telemetry" in res
    assert "audio_endpoints" in res
    assert "bluetooth_devices" in res
    assert "printers" in res

