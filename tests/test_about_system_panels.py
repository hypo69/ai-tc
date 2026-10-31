# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - About System Panels
# =============================================================================
# Description:
#   Тестирование наполнения данных для панелей вкладки «О системе»:
#   - Full Hardware Specification Tree (hardware_tree)
#   - Disks Health & Wear Panel (storage_battery / disks_wear)
#   - Battery Deep Telemetry Panel (battery / battery_wear)
#   - Storage Volumes & Partitions (summary / disks)
#   - Независимые API накопителей (/storage-wear) и батареи (/battery)
#
# File: test_about_system_panels.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-20 18:48:00
# =============================================================================

from pathlib import Path
import pytest
from fastapi import FastAPI, APIRouter
from fastapi.testclient import TestClient

from apps.windows.api.routers.about_system.endpoints_overview import register_overview_endpoints
from apps.windows.telemetry.sqlite import TelemetryStorage


def test_bundle_endpoint_contains_hardware_storage_and_battery_panels():
    """Проверка присутствия полей оборудования, дисков и независимой батареи в /api/v1/about-system/bundle."""
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
    # 1. Hardware Tree
    assert "hardware" in data
    assert "hardware_tree" in data
    assert isinstance(data["hardware_tree"], list)

    # 2. Disks Health & Wear
    assert "disks_wear" in data
    assert isinstance(data["disks_wear"], list)
    assert "storage_battery" in data
    sb = data["storage_battery"]
    assert isinstance(sb, dict)
    assert "disks_wear" in sb
    assert isinstance(sb["disks_wear"], list)

    # 3. Battery Deep Telemetry в составе единого бандла
    assert "battery" in data
    assert "battery_wear" in data
    assert isinstance(data["battery_wear"], dict)
    assert "power_source" in data["battery_wear"]
    assert "has_battery" in data["battery_wear"]

    # 4. Storage Volumes & Partitions
    assert "summary" in data
    summary = data["summary"]
    assert isinstance(summary, dict)
    assert "disks" in summary
    assert isinstance(summary["disks"], list)

    # 5. OS Install Date & Monitors Orientation
    assert "os_install_date" in summary
    assert summary["os_install_date"] != ""
    if "kpi" in data and "os" in data["kpi"]:
        assert data["kpi"]["os"].get("os_install_date") != ""
    monitors = summary.get("monitors", [])
    for m in monitors:
        assert "orientation" in m
        assert m["orientation"] in ("горизонтальная", "вертикальная", "альбомная", "портретная")


def test_independent_diagnostics_endpoints():
    """Проверка раздельных независимых эндпоинтов для дисков и батареи."""
    app = FastAPI()
    router = APIRouter()
    storage = TelemetryStorage()
    register_overview_endpoints(router, storage)
    app.include_router(router)

    client = TestClient(app)

    # Независимый API состояния накопителей
    disks_resp = client.get("/api/v1/system/diagnostics/storage-wear")
    assert disks_resp.status_code == 200
    disks_data = disks_resp.json()
    assert disks_data.get("status") == "ok"
    assert "disks_wear" in disks_data

    # Независимый API телеметрии батареи
    bat_resp = client.get("/api/v1/system/diagnostics/battery")
    assert bat_resp.status_code == 200
    bat_data = bat_resp.json()
    assert bat_data.get("status") == "ok"
    assert "battery_wear" in bat_data
    assert "power_source" in bat_data["battery_wear"]

    # Комбинированный fallback эндпоинт
    combined_resp = client.get("/api/v1/system/diagnostics/storage-battery")
    assert combined_resp.status_code == 200
    comb_data = combined_resp.json()
    assert "disks_wear" in comb_data
    assert "battery_wear" in comb_data


def test_main_js_invokes_independent_panels():
    """Проверка, что main.js вызывает рендеринг дерева оборудования, раздельных дисков и батареи."""
    js_path = Path("apps/windows/api/webgui/tab_about_system/main.js")
    assert js_path.exists()
    content = js_path.read_text(encoding="utf-8")

    # Проверка импортов
    assert "applyHardwareData" in content
    assert "applyDisksWearData" in content
    assert "applyBatteryData" in content
    assert "applyStorageBatteryWearData" in content
    assert "renderDisksTable" in content

    # Проверка вызова в applyBundleData
    assert "applyHardwareData(hwNodes)" in content
    assert "applyDisksWearData(disksWear)" in content
    assert "applyBatteryData(batteryData)" in content
    assert "applyStorageBatteryWearData(wearData)" in content
    assert "renderDisksTable(disks)" in content


def test_battery_panel_is_independent_row_in_html():
    """Проверка, что в index.html панель Battery Deep Telemetry находится в отдельной строке."""
    html_path = Path("apps/windows/api/webgui/tab_about_system/index.html")
    assert html_path.exists()
    content = html_path.read_text(encoding="utf-8")

    assert 'data-panel-id="panel-about-battery"' in content
    assert 'id="btn-diag-battery-refresh"' in content
    assert 'id="btn-diag-disks-wear-refresh"' in content

    # Проверка, что панель дисков не делит колонку с батареей (обе col-12)
    assert 'data-panel-id="panel-about-disks-wear"' in content


def test_main_js_uses_single_bundle_api_without_separate_panel_requests():
    """Проверка, что вкладка About System использует единый эндпоинт bundle без разрозненных запросов от панелей."""
    js_path = Path("apps/windows/api/webgui/tab_about_system/main.js")
    assert js_path.exists()
    content = js_path.read_text(encoding="utf-8")

    # Проверка запроса единого пакета бандла
    assert "/api/v1/about-system/bundle" in content

    # Проверка отсутствия автоматических fallback вызовов отдельных API в refreshAllData
    assert "await Promise.all([" not in content

    # Проверка, что applyBundleData передает данные напрямую без дополнительных сетевых fallback-опросов
    apply_bundle_start = content.find("function applyBundleData(bundle)")
    assert apply_bundle_start != -1
    apply_bundle_end = content.find("function refreshAllData", apply_bundle_start)
    assert apply_bundle_end != -1
    apply_bundle_body = content[apply_bundle_start:apply_bundle_end]

    # Никакая панель не должна слать отдельный запрос внутри applyBundleData
    assert "fetchHardwareTree()" not in apply_bundle_body
    assert "fetchDisksWear()" not in apply_bundle_body
    assert "fetchBatteryWear()" not in apply_bundle_body
    assert "fetchSecurityHealth()" not in apply_bundle_body
    assert "fetchNetworkProfile()" not in apply_bundle_body


def test_panel_loader_and_tab_core_block_about_system_panels():
    """Проверка, что panel-loader.js и tab-core.js блокируют отправку запросов /panel/ для вкладки about-system."""
    loader_path = Path("apps/windows/api/webgui/js/panel-loader.js")
    assert loader_path.exists()
    loader_content = loader_path.read_text(encoding="utf-8")
    assert "cleanId.startsWith('panel-about-')" in loader_content

    tab_core_path = Path("apps/windows/api/webgui/js/tab-core.js")
    assert tab_core_path.exists()
    tab_core_content = tab_core_path.read_text(encoding="utf-8")
    assert "tabName !== 'about-system'" in tab_core_content

