# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry Tests - Process Lifecycle & Initiators
# =============================================================================
# Description:
#   Модульные и интеграционные тесты отслеживания жизненного цикла процессов:
#   уникальные сессии (instance_id), время рождения и завершения, атрибуция
#   инициаторов (родительских процессов), пользователей и ресурсного следа.
#
# File: test_process_lifecycle_tracker.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 01:04:00
# =============================================================================

import gc
import os
import shutil
import tempfile
import pytest
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.windows.sdk.modules.process_manager import (
    ProcessLifecycleTracker,
    ProcessSessionRecord,
    ProcessLifecycleDelta,
)
from apps.windows.telemetry.sqlite import TelemetryStorage
from apps.windows.telemetry.service import TelemetryLoggerService
from apps.windows.telemetry.telemetry_config import TelemetryConfigManager
from apps.windows.router import router as windows_router


@pytest.fixture
def temp_telemetry_storage():
    """Создает изолированное временное хранилище SQLite для тестов жизненного цикла."""
    tmp_dir = tempfile.mkdtemp(prefix="test_life_")
    db_file = Path(tmp_dir) / "test_lifecycle.db"
    storage = TelemetryStorage(db_path=db_file)
    try:
        yield storage
    finally:
        storage.close()
        del storage
        gc.collect()
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_process_lifecycle_tracker_scan():
    """Проверяет сканирование текущих процессов, формирование instance_id и инициаторов."""
    tracker = ProcessLifecycleTracker()
    delta = tracker.scan_processes_delta()

    assert delta is not None
    assert delta.active_count > 0
    assert len(delta.created_sessions) > 0

    current_pid = os.getpid()
    cur_session = next((s for s in delta.created_sessions if s.pid == current_pid), None)
    assert cur_session is not None
    assert cur_session.pid == current_pid
    assert cur_session.is_alive is True
    assert "_" in cur_session.instance_id
    assert cur_session.created_ts > 0.0
    assert cur_session.name.lower().endswith(('.exe', 'python')) or 'python' in cur_session.name.lower()
    assert cur_session.initiator_type in (
        "user_interactive",
        "system_service",
        "task_scheduler",
        "script_runner",
        "system_kernel",
        "application_child",
        "unknown",
    )


def test_storage_lifecycle_session_crud(temp_telemetry_storage):
    """Проверяет сохранение, обновление и выборку сессий процессов в SQLite."""
    current_pid = os.getpid()
    inst_id = f"{current_pid}_1728950000000"

    record = ProcessSessionRecord(
        instance_id=inst_id,
        pid=current_pid,
        ppid=1000,
        name="test_runner.exe",
        friendly_name="Test Runner",
        exe_path=r"C:\Windows\System32\test_runner.exe",
        binary_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        cmdline="test_runner.exe --verbose",
        username=r"DELL-VOSTRO\onela",
        parent_name="cmd.exe",
        parent_exe=r"C:\Windows\System32\cmd.exe",
        initiator_type="user_interactive",
        created_at="2026-10-15T00:00:00Z",
        created_ts=1728950000.0,
        is_alive=True,
        lifetime_sec=12.5,
        cpu_time_total_sec=1.23,
        peak_working_set_mb=45.6,
        io_read_bytes=1048576,
        io_write_bytes=2097152,
    )

    # 1. Сохранение новой сессии
    saved = temp_telemetry_storage.upsert_process_lifecycle_session(record)
    assert saved is True

    # 2. Выборка по instance_id
    loaded = temp_telemetry_storage.get_process_lifecycle_by_instance_id(inst_id)
    assert loaded is not None
    assert loaded["instance_id"] == inst_id
    assert loaded["name"] == "test_runner.exe"
    assert loaded["parent_name"] == "cmd.exe"
    assert loaded["initiator_type"] == "user_interactive"
    assert loaded["username"] == r"DELL-VOSTRO\onela"
    assert loaded["is_alive"] == 1

    # 3. Обновление статуса: процесс завершился
    record.is_alive = False
    record.terminated_at = "2026-10-15T00:00:30Z"
    record.terminated_ts = 1728950030.0
    record.lifetime_sec = 30.0
    record.exit_code = 0
    record.cpu_time_total_sec = 2.45
    temp_telemetry_storage.upsert_process_lifecycle_session(record)

    updated = temp_telemetry_storage.get_process_lifecycle_by_instance_id(inst_id)
    assert updated is not None
    assert updated["is_alive"] == 0
    assert updated["lifetime_sec"] == 30.0
    assert updated["exit_code"] == 0
    assert updated["cpu_time_total_sec"] == 2.45

    # 4. Выборка с фильтрацией по имени и пользователю
    by_app = temp_telemetry_storage.get_process_lifecycle_sessions(app_name="test_runner")
    assert len(by_app) == 1

    by_user = temp_telemetry_storage.get_process_lifecycle_sessions(username="onela")
    assert len(by_user) == 1

    # 5. Сводный аналитический отчет
    summary = temp_telemetry_storage.get_app_summary_report(app_name="test_runner")
    assert summary["total_launches"] == 1
    assert summary["active_now"] == 0
    assert summary["total_lifetime_sec"] == 30.0
    assert "cmd.exe" in summary["initiators"]


def test_service_track_lifecycle_delta(temp_telemetry_storage):
    """Проверяет интеграцию вызова track_lifecycle_delta сервисом телеметрии."""
    service = TelemetryLoggerService(storage=temp_telemetry_storage)
    delta = service.track_lifecycle_delta()

    assert delta is not None
    assert delta.active_count > 0

    # Проверяем, что запущенные процессы попали в SQLite
    current_pid = os.getpid()
    sessions = temp_telemetry_storage.get_process_lifecycle_sessions(pid=current_pid)
    assert len(sessions) >= 1
    assert sessions[0]["pid"] == current_pid


def test_api_lifecycle_endpoints():
    """Проверяет работу FastAPI эндпоинтов жизненного цикла процессов."""
    app = FastAPI()
    app.include_router(windows_router)
    client = TestClient(app)

    # 1. GET /api/windows/telemetry/lifecycle/sessions
    resp = client.get("/api/windows/telemetry/lifecycle/sessions?limit=5")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

    # 2. GET /api/windows/telemetry/lifecycle/summary
    resp = client.get("/api/windows/telemetry/lifecycle/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_launches" in data
    assert "initiators" in data
    assert "users" in data


def test_incident_timeline_builder_correlates_spike():
    """Проверяет корреляцию цепочки инцидента: старт -> всплеск CPU -> рост RAM -> запись на диск -> сеть."""
    from apps.windows.sdk.modules.process_manager import IncidentTimelineBuilder

    samples = [
        {
            "instance_id": "4812_1728950000000",
            "pid": 4812,
            "name": "python.exe",
            "timestamp": "2026-10-15T12:00:00+00:00",
            "created_at": 1728950000.0,
            "cpu_percent": 5.0,
            "working_set_mb": 50.0,
            "private_mb": 40.0,
            "write_bytes_sec": 0.0,
            "write_operations": 10,
            "open_files": [],
            "tcp_connections_count": 0,
            "is_alive": True,
            "initiator_type": "user_interactive",
            "parent_name": "cmd.exe",
            "username": r"DELL-VOSTRO\onela",
        },
        {
            "instance_id": "4812_1728950000000",
            "pid": 4812,
            "name": "python.exe",
            "timestamp": "2026-10-15T12:00:01+00:00",
            "created_at": 1728950001.0,
            "cpu_percent": 85.0,  # Всплеск CPU
            "working_set_mb": 60.0,
            "private_mb": 50.0,
            "write_bytes_sec": 0.0,
            "write_operations": 15,
            "open_files": [],
            "tcp_connections_count": 0,
            "is_alive": True,
        },
        {
            "instance_id": "4812_1728950000000",
            "pid": 4812,
            "name": "python.exe",
            "timestamp": "2026-10-15T12:00:02+00:00",
            "created_at": 1728950002.0,
            "cpu_percent": 80.0,
            "working_set_mb": 360.0,  # Скачок RAM на +300 МБ
            "private_mb": 350.0,
            "write_bytes_sec": 0.0,
            "write_operations": 20,
            "open_files": [],
            "tcp_connections_count": 0,
            "is_alive": True,
        },
        {
            "instance_id": "4812_1728950000000",
            "pid": 4812,
            "name": "python.exe",
            "timestamp": "2026-10-15T12:00:03+00:00",
            "created_at": 1728950003.0,
            "cpu_percent": 60.0,
            "working_set_mb": 370.0,
            "private_mb": 360.0,
            "write_bytes_sec": 12.5 * 1024 * 1024,  # Интенсивная запись 12.5 МБ/с
            "write_operations": 300,
            "open_files": [r"C:\AppData\cache.tmp"],
            "tcp_connections_count": 0,
            "is_alive": True,
        },
        {
            "instance_id": "4812_1728950000000",
            "pid": 4812,
            "name": "python.exe",
            "timestamp": "2026-10-15T12:00:04+00:00",
            "created_at": 1728950004.0,
            "cpu_percent": 20.0,
            "working_set_mb": 370.0,
            "private_mb": 360.0,
            "write_bytes_sec": 0.0,
            "write_operations": 305,
            "open_files": [r"C:\AppData\cache.tmp"],
            "tcp_connections_count": 2,  # Сетевые соединения
            "connections": [{"remote_address": "93.184.216.34", "remote_port": 443}],
            "is_alive": True,
        },
    ]

    builder = IncidentTimelineBuilder()
    timeline = builder.build_timeline_from_samples(samples)

    assert timeline is not None
    assert timeline.pid == 4812
    assert timeline.process_name == "python.exe"
    assert timeline.max_cpu_percent == 85.0
    assert timeline.peak_memory_mb == 370.0
    assert len(timeline.touched_files) >= 1
    assert any("93.184.216.34:443" in h for h in timeline.active_network_hosts)

    # Проверяем последовательность событий
    resources = [ev.resource for ev in timeline.events]
    assert "Процесс" in resources
    assert "CPU" in resources
    assert "RAM" in resources
    assert "Диск" in resources
    assert "Сеть" in resources


def test_storage_and_api_incident_timeline(temp_telemetry_storage):
    """Проверяет извлечение хроники инцидента через TelemetryStorage и FastAPI эндпоинт."""
    current_pid = os.getpid()

    # 1. Делаем аудит текущего процесса
    from apps.windows.sdk.modules.process_manager import ProcessAuditor
    auditor = ProcessAuditor()
    sample = auditor.audit_process(pid=current_pid)
    temp_telemetry_storage.save_process_audit_sample(sample)

    # 2. Запрос хроники через хранилище
    timeline = temp_telemetry_storage.get_process_incident_timeline(pid=current_pid)
    assert timeline is not None
    assert timeline["pid"] == current_pid
    assert len(timeline["events"]) >= 1

    # 3. Запрос через FastAPI
    app = FastAPI()
    app.include_router(windows_router)
    client = TestClient(app)

    resp = client.get(f"/api/windows/telemetry/incident/{current_pid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["pid"] == current_pid
    assert "events" in data

