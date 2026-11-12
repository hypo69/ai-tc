# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Telemetry Task Scheduler API & WebGUI
# =============================================================================
# Description:
#   Тесты эндпоинтов регистрации службы телеметрии в Windows Task Scheduler
#   и наличия соответствующих элементов управления в веб-интерфейсе
#   «Внутренняя кухня» (tab_app_internals / tab_telemetry_control).
#
# File: test_telemetry_task_scheduler_api.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-11 20:38:00
# =============================================================================

from __future__ import annotations

import subprocess
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from apps.windows.api.server import create_app


@pytest.fixture(scope="module")
def api_client() -> TestClient:
    """Фикстура тестового клиента FastAPI приложения TC."""
    app = create_app()
    return TestClient(app)


def test_webgui_internals_telemetry_contains_install_task_button(api_client: TestClient) -> None:
    """Проверяет наличие кнопки установки службы в Task Scheduler в разметке и скрипте вкладки."""
    internals_html = api_client.get("/html/tab_app_internals/index.html")
    assert internals_html.status_code == 200
    assert 'id="internals-telemetry-embed-container"' in internals_html.text

    ctrl_html = api_client.get("/html/tab_telemetry_control/index.html")
    assert ctrl_html.status_code == 200
    assert 'id="tc-ctrl-btn-install-task"' in ctrl_html.text
    assert 'id="tc-ctrl-task-status-badge"' in ctrl_html.text

    ctrl_js = api_client.get("/html/tab_telemetry_control/main.js")
    assert ctrl_js.status_code == 200
    assert "/api/windows/telemetry/config/task-scheduler/status" in ctrl_js.text
    assert "/api/windows/telemetry/config/task-scheduler/install" in ctrl_js.text
    assert "installTelemetryTask" in ctrl_js.text


def test_task_scheduler_status_found_ru_and_en(api_client: TestClient) -> None:
    """Проверяет разбор статуса задачи планировщика из schtasks.exe для RU и EN локалей."""
    sample_stdout = (
        "Имя задачи:                           \\AI-Windows-Admin-Telemetry\n"
        "Состояние:                            Готово\n"
        "Состояние запланированной задачи:     Включена\n"
        "Запуск от имени:                      SYSTEM\n"
        "Тип расписания:                       При запуске системы\n"
        "Запускаемая задача:                   powershell.exe -File tlm.ps1\n"
    )
    fake_proc = SimpleNamespace(returncode=0, stdout=sample_stdout, stderr="")

    with patch("apps.windows.api.routers.router_telemetry_config.subprocess.run", return_value=fake_proc):
        res = api_client.get("/api/windows/telemetry/config/task-scheduler/status")

    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["task"]["exists"] is True
    assert data["task"]["state"] == "Готово"
    assert data["task"]["enabled"] is True
    assert data["task"]["run_as_user"] == "SYSTEM"


def test_task_scheduler_status_not_scheduled(api_client: TestClient) -> None:
    """Проверяет корректный ответ, когда задача телеметрии еще не зарегистрирована."""
    fake_proc = SimpleNamespace(returncode=1, stdout="", stderr="ERROR: The system cannot find the file specified.")

    with patch("apps.windows.api.routers.router_telemetry_config.subprocess.run", return_value=fake_proc):
        res = api_client.get("/api/windows/telemetry/config/task-scheduler/status")

    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["task"]["exists"] is False
    assert data["task"]["state"] == "NotScheduled"


def test_task_scheduler_install_success(api_client: TestClient) -> None:
    """Проверяет успешную регистрацию задачи телеметрии через Install-TelemetryTask.ps1."""
    install_proc = SimpleNamespace(returncode=0, stdout="Задача успешно зарегистрирована", stderr="")
    query_proc = SimpleNamespace(
        returncode=0,
        stdout=(
            "TaskName: \\AI-Windows-Admin-Telemetry\n"
            "Status: Ready\n"
            "Scheduled Task State: Enabled\n"
            "Run As User: SYSTEM\n"
            "Schedule Type: At system start up\n"
        ),
        stderr="",
    )

    calls: list[list[str]] = []

    def _fake_run(cmd: list[str], **kwargs) -> SimpleNamespace:
        calls.append(cmd)
        if cmd[0].lower().endswith("powershell.exe"):
            return install_proc
        return query_proc

    with patch("apps.windows.api.routers.router_telemetry_config.subprocess.run", side_effect=_fake_run):
        res = api_client.post(
            "/api/windows/telemetry/config/task-scheduler/install",
            json={"mode": "hybrid", "interval": 5.0, "top_processes": 12},
        )

    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["task"]["exists"] is True
    assert data["task"]["state"] == "Ready"
    assert len(calls) == 2
    assert any("Install-TelemetryTask.ps1" in part for part in calls[0])
    assert "-Force" in calls[0]


def test_task_scheduler_install_failure_returns_500(api_client: TestClient) -> None:
    """Проверяет возврат HTTP 500 при ошибке PowerShell-установщика."""
    fail_proc = SimpleNamespace(returncode=1, stdout="", stderr="Access denied")

    with patch("apps.windows.api.routers.router_telemetry_config.subprocess.run", return_value=fail_proc):
        res = api_client.post("/api/windows/telemetry/config/task-scheduler/install", json={"mode": "hybrid"})

    assert res.status_code == 500
    assert "Access denied" in res.json()["detail"]


def test_task_scheduler_install_missing_after_uac_cancel(api_client: TestClient) -> None:
    """Проверяет ошибку HTTP 500, если установщик завершился с 0, но задача не появилась (отмена UAC)."""
    ok_proc = SimpleNamespace(returncode=0, stdout="", stderr="")
    missing_proc = SimpleNamespace(returncode=1, stdout="", stderr="Not found")

    def _fake_run(cmd: list[str], **kwargs) -> SimpleNamespace:
        if cmd[0].lower().endswith("powershell.exe"):
            return ok_proc
        return missing_proc

    with patch("apps.windows.api.routers.router_telemetry_config.subprocess.run", side_effect=_fake_run):
        res = api_client.post("/api/windows/telemetry/config/task-scheduler/install", json={})

    assert res.status_code == 500
    assert "UAC" in res.json()["detail"]


def test_task_scheduler_install_timeout_returns_504(api_client: TestClient) -> None:
    """Проверяет возврат HTTP 504 при превышении таймаута ожидания установщика."""
    with patch(
        "apps.windows.api.routers.router_telemetry_config.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="powershell.exe", timeout=90),
    ):
        res = api_client.post("/api/windows/telemetry/config/task-scheduler/install", json={})

    assert res.status_code == 504


def test_task_scheduler_install_invalid_mode_returns_422(api_client: TestClient) -> None:
    """Проверяет валидацию параметра mode на уровне Pydantic."""
    res = api_client.post("/api/windows/telemetry/config/task-scheduler/install", json={"mode": "invalid_mode"})
    assert res.status_code == 422
