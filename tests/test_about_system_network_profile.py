# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - About System Network Profile
# =============================================================================
# Description:
#   Тестирование получения сетевого профиля строго из базы данных telemetry.db
#   в составе пакетного эндпоинта /api/v1/about-system/bundle, а также проверки
#   отсутствия вызовов тяжелой диагностики при инициализации таба.
#
# File: test_about_system_network_profile.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-16 23:05:00
# =============================================================================

from pathlib import Path
import pytest
from fastapi import FastAPI, APIRouter
from fastapi.testclient import TestClient

from apps.windows.api.routers.about_system.query_diagnostics import query_network_profile_from_db
from apps.windows.api.routers.about_system.endpoints_overview import register_overview_endpoints
from apps.windows.telemetry.sqlite import TelemetryStorage


def test_storage_get_latest_network_profile():
    """Проверка метода get_latest_network_profile хранилища TelemetryStorage."""
    storage = TelemetryStorage()
    net_prof = storage.get_latest_network_profile()
    assert isinstance(net_prof, dict)
    assert "current_category" in net_prof
    assert net_prof["current_category"] in ("Public", "Private", "Domain")
    assert "is_discovery_enabled" in net_prof
    assert isinstance(net_prof["is_discovery_enabled"], bool)


def test_query_network_profile_from_db():
    """Проверка извлечения сетевого профиля строго из базы данных telemetry.db."""
    storage = TelemetryStorage()
    profile = query_network_profile_from_db(storage)
    assert isinstance(profile, dict)
    assert "current_category" in profile
    assert "primary_interface_alias" in profile
    assert "is_discovery_enabled" in profile


def test_bundle_endpoint_contains_network_profile():
    """Проверка включения сетевого профиля в /api/v1/about-system/bundle."""
    app = FastAPI()
    router = APIRouter()
    storage = TelemetryStorage()
    register_overview_endpoints(router, storage)
    app.include_router(router)

    client = TestClient(app)
    response = client.get("/api/v1/about-system/bundle")
    assert response.status_code == 200
    data = response.json()

    assert data.get("status") == "ok"
    assert "network_profile" in data
    net_prof = data["network_profile"]
    assert isinstance(net_prof, dict)
    assert "current_category" in net_prof
    assert net_prof["current_category"] in ("Public", "Private", "Domain")
    assert "is_discovery_enabled" in net_prof


def test_main_js_no_fetch_network_profile_in_init():
    """Проверка отсутствия прямого вызова fetchNetworkProfile() в функции initAboutSystemTab."""
    js_path = Path("apps/windows/api/webgui/tab_about_system/main.js")
    assert js_path.exists()
    content = js_path.read_text(encoding="utf-8")

    # Проверяем, что в теле функции initAboutSystemTab нет вызова fetchNetworkProfile()
    init_func_start = content.find("function initAboutSystemTab")
    assert init_func_start != -1
    init_func_end = content.find("window.initAboutSystemTab", init_func_start)
    assert init_func_end != -1

    init_func_body = content[init_func_start:init_func_end]
    assert "fetchNetworkProfile();" not in init_func_body, (
        "fetchNetworkProfile() не должен вызываться при инициализации вкладки!"
    )

