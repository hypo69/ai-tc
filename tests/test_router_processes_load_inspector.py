# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Tests - Router Processes Load Inspector
# =============================================================================
# Description:
#   Модульные тесты для проверки REST API эндпоинтов вкладки
#   «Инспектор нагрузки процессов» (/api/v1/tab-processes-load-inspector/*).
#   Проверяет топ процессов, категоризированный диспетчер задач, сетевую и файловую
#   активность, аудит утечек, Deep Dive инстансы и расследование PowerShell.
#
# Usage Examples:
#   pytest tests/test_router_processes_load_inspector.py
#
# File: test_router_processes_load_inspector.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 18:59:00
# =============================================================================

from __future__ import annotations
"""Тесты эндпоинтов вкладки tab-processes-load-inspector."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.windows.api.routers.router_processes_load_inspector import init_router


@pytest.fixture
def client() -> TestClient:
    """Фикстура тестового клиента с подключенным роутером вкладки."""
    app = FastAPI()
    app.include_router(init_router())
    return TestClient(app)


def test_top_processes_endpoint(client: TestClient):
    """Проверка эндпоинта /panel-top-processes."""
    resp = client.get("/api/v1/tab-processes-load-inspector/panel-top-processes?limit=10")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_process_manager_endpoints(client: TestClient):
    """Проверка эндпоинтов панели диспетчера процессов /panel-process-manager."""
    # 1. Categorized report
    resp_cat = client.get("/api/v1/tab-processes-load-inspector/panel-process-manager")
    assert resp_cat.status_code == 200
    data_cat = resp_cat.json()
    assert "apps" in data_cat
    assert "background_processes" in data_cat
    assert "windows_processes" in data_cat

    # 2. Summary report
    resp_sum = client.get("/api/v1/tab-processes-load-inspector/panel-process-manager/summary")
    assert resp_sum.status_code == 200
    data_sum = resp_sum.json()
    assert "total_processes" in data_sum

    # 3. Action simulation (dry-run)
    payload = {
        "pid": 999999,
        "kill_tree": True,
        "dry_run": True,
        "confirmed_by_user": False
    }
    resp_act = client.post("/api/v1/tab-processes-load-inspector/panel-process-manager/action", json=payload)
    assert resp_act.status_code == 200
    assert resp_act.json().get("status") == "DRY_RUN_SUCCESS"


def test_network_and_files_endpoints(client: TestClient):
    """Проверка эндпоинтов сетевой активности и мониторинга файлов."""
    resp_net = client.get("/api/v1/tab-processes-load-inspector/panel-network-activity?limit=20")
    assert resp_net.status_code == 200
    assert isinstance(resp_net.json(), list)

    resp_files = client.get("/api/v1/tab-processes-load-inspector/panel-file-watcher/events?limit=20")
    assert resp_files.status_code == 200
    assert isinstance(resp_files.json(), list)


def test_leak_hunter_endpoints(client: TestClient):
    """Проверка эндпоинтов аудита утечек ресурсов."""
    resp = client.get("/api/v1/tab-processes-load-inspector/panel-leak-hunter?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)

    resp_ref = client.post("/api/v1/tab-processes-load-inspector/panel-leak-hunter/refresh?limit=10")
    assert resp_ref.status_code == 200


def test_deep_dive_endpoints(client: TestClient):
    """Проверка эндпоинтов углубленного анализа инстансов процессов."""
    resp_act = client.get("/api/v1/tab-processes-load-inspector/panel-deep-dive/active?limit=10")
    assert resp_act.status_code == 200
    assert isinstance(resp_act.json(), list)

    resp_hist = client.get("/api/v1/tab-processes-load-inspector/panel-deep-dive/history?limit=10")
    assert resp_hist.status_code == 200
    assert isinstance(resp_hist.json(), list)

    resp_file_act = client.get("/api/v1/tab-processes-load-inspector/panel-deep-dive/21276_1792474028651/file-activity?limit=50")
    assert resp_file_act.status_code == 200
    assert isinstance(resp_file_act.json(), list)

    resp_sockets = client.get("/api/v1/tab-processes-load-inspector/panel-deep-dive/21276_1792474028651/sockets")
    assert resp_sockets.status_code == 200
    assert isinstance(resp_sockets.json(), list)

    resp_samples = client.get("/api/v1/tab-processes-load-inspector/panel-deep-dive/18252_1793465254783/samples?limit=60")
    assert resp_samples.status_code == 200
    assert isinstance(resp_samples.json(), list)

    resp_samples_pid = client.get("/api/v1/tab-processes-load-inspector/panel-deep-dive/18252/samples?limit=10")
    assert resp_samples_pid.status_code == 200
    assert isinstance(resp_samples_pid.json(), list)


def test_ai_audit_powershell_endpoint(client: TestClient):
    """Проверка эндпоинта ИИ-расследования вызовов PowerShell."""
    resp = client.get("/api/v1/tab-processes-load-inspector/panel-ai-audit/powershell")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "verdict" in data

