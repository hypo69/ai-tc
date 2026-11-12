# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Tests - Software AI and Hardening Standards
# =============================================================================
# Description:
#   Модульные и интеграционные тесты для роутера ИИ-диагностики ПО,
#   завершения процессов, изоляции в брандмауэре и интервалов телеметрии.
#
# File: test_software_ai_and_hardening.py
# Project: ai-windows-admin
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 18:03:00
# =============================================================================

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from apps.windows.api.routers.tab_software_scanner.router_software_ai import (
    router as software_ai_router,
    prune_metadata_for_prompt,
    safe_run_command,
)
from apps.windows.telemetry.telemetry_config import TelemetryConfigManager


@pytest.fixture
def api_client():
    app = FastAPI()
    app.include_router(software_ai_router)
    return TestClient(app)


def test_token_pruning():
    """Тест очистки избыточных и дефолтных значений метрик для экономии токенов."""
    raw = {
        "pid": 1234,
        "name": "test.exe",
        "cpu_percent": "0.0%",
        "memory_mb": 0,
        "ports": "null",
        "active_threads": 5,
        "empty_field": "",
        "none_field": None,
    }
    pruned = prune_metadata_for_prompt(raw)
    assert "pid" in pruned
    assert "name" in pruned
    assert "active_threads" in pruned
    assert "cpu_percent" not in pruned
    assert "memory_mb" not in pruned
    assert "ports" not in pruned
    assert "empty_field" not in pruned
    assert "none_field" not in pruned


def test_software_explain_endpoint_json(api_client):
    """Тест эндпоинта /api/v1/chat/software-explain с возвратом структурированного JSON."""
    payload = {
        "program": {
            "name": "chrome.exe",
            "path": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
            "pid": 4512,
            "cpu_percent": "1.2%",
            "memory_mb": "128.5 MB",
        },
        "stream": False,
    }
    response = api_client.post("/api/v1/chat/software-explain", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    assert "security_verdict" in data
    assert "risk_level" in data
    assert data["risk_level"] in ("Low", "Medium", "High", "Critical")


def test_software_explain_endpoint_streaming(api_client):
    """Тест эндпоинта /api/v1/chat/software-explain в режиме Server-Sent Events."""
    payload = {
        "name": "svchost.exe",
        "pid": 890,
        "path": "C:\\Windows\\System32\\svchost.exe",
        "stream": True,
    }
    response = api_client.post("/api/v1/chat/software-explain", json=payload)
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")
    assert "data:" in response.text
    assert "[DONE]" in response.text


def test_process_kill_safety_check(api_client):
    """Тест защиты от завершения системных процессов (PID <= 4)."""
    response = api_client.post("/api/v1/processes/kill", json={"pid": 4, "force": True})
    assert response.status_code == 400
    assert "критических системных процессов" in response.json()["detail"]


def test_firewall_block_dry_run(api_client):
    """Тест блокировки исполняемого файла в брандмауэре в режиме симуляции (dry_run)."""
    payload = {
        "path": "C:\\malware\\miner.exe",
        "name": "Test-Miner-Rule",
        "direction": "Out",
        "dry_run": True,
    }
    response = api_client.post("/api/v1/security/firewall/block", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "dry_run"
    assert data["rule_name"] == "Test-Miner-Rule"
    assert data["action"] == "Block"


def test_telemetry_collector_intervals():
    """Тест 4 независимых интервалов опроса коллекторов телеметрии."""
    cfg = TelemetryConfigManager()
    assert cfg.get_wmi_interval_seconds() == 120.0
    assert cfg.get_smart_interval_seconds() == 300.0
    assert cfg.get_handles_interval_seconds() == 60.0
    assert cfg.get_network_ports_interval_seconds() == 30.0


def test_storage_analyzer_clean_aliases():
    """Тест очистки версий, разрядности и формирования алиасов в StorageAnalyzer."""
    from apps.windows.sdk.core.software_transparency import StorageAnalyzer, SoftwareItem

    analyzer = StorageAnalyzer()
    app = SoftwareItem(
        id="py-test",
        name="Python 3.14.7 (64-bit)",
        executable_path="C:\\Users\\test\\AppData\\Local\\Python\\pythoncore-3.14-64\\python.exe"
    )
    aliases = analyzer._get_search_aliases(app)
    assert "python 3.14.7 (64-bit)" in aliases
    assert "python 3.14.7" in aliases
    assert "python" in aliases


def test_storage_analyzer_nested_matching(tmp_path):
    """Тест двухуровневого сопоставления папок вендоров в _find_matching_folder."""
    from apps.windows.sdk.core.software_transparency import StorageAnalyzer

    analyzer = StorageAnalyzer()
    base_dir = tmp_path / "LocalAppData"
    vendor_dir = base_dir / "Google"
    app_dir = vendor_dir / "Chrome"
    app_dir.mkdir(parents=True)

    matched = analyzer._find_matching_folder(str(base_dir), ["радио поток", "chrome"])
    assert matched is not None
    assert matched == str(app_dir)


def test_network_tracker_filters_archives_and_extracts_publisher_domain():
    """Тест фильтрации ложных доменов (.zip/.exe) и извлечения URL из поля издателя."""
    from apps.windows.sdk.core.software_transparency import ConfigFile, NetworkTracker, SoftwareItem

    tracker = NetworkTracker()
    app = SoftwareItem(
        id="wireshark-4-6",
        name="Wireshark 4.6.8",
        publisher="The Wireshark developer community, https://www.wireshark.org/",
    )
    cfgs = [
        ConfigFile(
            path="C:\\test\\__install__.json",
            display_path="C:\\test\\__install__.json",
            filename="__install__.json",
            sample_content='{"archive": "python-3.14.6-amd64.zip", "docs": "https://docs.python.org/3.14/"}',
        )
    ]
    endpoints = tracker.track_app_network(app, cfgs)
    domains = [ep.domain_or_ip for ep in endpoints]
    assert "python-3.14.6-amd64.zip" not in domains
    assert "docs.python.org" in domains
    assert "www.wireshark.org" in domains


def test_infer_install_location_from_display_icon_and_uninstall(tmp_path):
    """Тест вычисления директории установки из DisplayIcon или UninstallString при пустом InstallLocation."""
    from apps.windows.sdk.core.software_audit import SoftwareAuditEngine

    app_dir = tmp_path / "SampleVendor" / "SampleApp"
    app_dir.mkdir(parents=True)
    exe_file = app_dir / "sample.exe"
    exe_file.write_text("bin")

    loc1 = SoftwareAuditEngine._infer_install_location(f'"{exe_file}",0', "", "")
    assert loc1 == str(app_dir)

    loc2 = SoftwareAuditEngine._infer_install_location("", f'"{app_dir / "unins000.exe"}" /SILENT', "")
    assert loc2 == str(app_dir)


def test_transparency_frontend_renders_all_parameters():
    """Проверка отображения всех параметров SoftwareItem в шаблоне и скрипте tab_software_transparency."""
    from pathlib import Path

    js_path = Path("apps/windows/api/webgui/tab_software_transparency/main.js")
    js_content = js_path.read_text(encoding="utf-8")

    for required_field in (
        "n.domain_or_ip",
        "app.category",
        "app.purpose_description",
        "app.executable_path",
        "app.architecture",
        "app.install_date",
        "app.size_bytes",
        "app.run_count",
        "app.registry_key",
        "app.uninstall_string",
        "app.windows_services",
    ):
        assert required_field in js_content, f"Поле {required_field} должно отображаться в таблице прозрачности ПО"



