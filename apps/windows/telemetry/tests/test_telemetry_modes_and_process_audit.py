# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry Tests - Modes & Process Audit
# =============================================================================
# Description:
#   Тесты двух режимов телеметрии (live stream и audit) и глубокого аудита
#   процесса по PID через Windows SDK (CPU, RAM, Private Bytes, I/O, Network).
#
# File: test_telemetry_modes_and_process_audit.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 07:20:00
# =============================================================================

import os
import gc
import shutil
import tempfile
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from fastapi import FastAPI

from apps.windows.sdk.modules.process_manager import ProcessAuditor, ProcessAuditSample
from apps.windows.telemetry.telemetry_config import TelemetryConfigManager
from apps.windows.telemetry.service import TelemetryLoggerService
from apps.windows.telemetry.sqlite import TelemetryStorage
from apps.windows.router import router as windows_router


@pytest.fixture
def temp_telemetry_storage():
    """Создает изолированное временное хранилище SQLite для тестов."""
    tmp_dir = tempfile.mkdtemp(prefix="test_tel_")
    db_file = Path(tmp_dir) / "test_audit_telemetry.db"
    storage = TelemetryStorage(db_path=db_file)
    try:
        yield storage
    finally:
        storage.close()
        del storage
        gc.collect()
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_process_auditor_collects_process_metrics():
    """Проверяет сбор метрик процессора, памяти (Private Bytes), I/O и сети для текущего процесса."""
    current_pid = os.getpid()
    auditor = ProcessAuditor()
    sample = auditor.audit_process(pid=current_pid)

    assert sample is not None
    assert sample.pid == current_pid
    assert sample.is_alive is True
    assert sample.name.lower().endswith(('.exe', 'python')) or 'python' in sample.name.lower()

    # 1. CPU
    assert sample.cpu.total_cpu_time_sec >= 0.0
    assert sample.cpu.num_threads >= 1
    assert sample.cpu.total_context_switches >= 0

    # 2. Память и Private Bytes
    assert sample.memory.working_set_mb > 0.0
    assert sample.memory.private_mb >= 0.0
    assert sample.memory.commit_size_mb >= 0.0

    # 3. Дисковый ввод-вывод
    assert sample.io.total_operations >= 0
    assert sample.io.read_operations >= 0

    # 4. Сеть
    assert sample.network.total_connections_count >= 0


def test_telemetry_config_mode_switching():
    """Проверяет переключение режимов: Audit работает на старте в любом случае, стриминг отключается отдельно или оба работают."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg_file = Path(tmp_dir) / "config.json"
        cfg_mgr = TelemetryConfigManager(config_path=cfg_file)

        # 1. По умолчанию на старте телеметрии Audit активен в любом случае
        assert cfg_mgr.is_audit_mode() is True
        assert cfg_mgr.is_audit_enabled() is True
        assert cfg_mgr.is_streaming_enabled() is False
        assert cfg_mgr.is_live_stream_mode() is False

        # 2. Активация режима аудита для конкретного целевого PID
        pid = os.getpid()
        cfg_mgr.activate_audit_mode(pid=pid, interval_sec=0.5)

        assert cfg_mgr.is_audit_mode() is True
        assert cfg_mgr.is_streaming_enabled() is False
        assert cfg_mgr.get_audit_target_pid() == pid
        assert cfg_mgr.get_audit_interval_sec() == 0.5

        # 3. Активация стриминга: стриминг включается, а аудит также продолжает работать!
        cfg_mgr.activate_streaming_mode()
        assert cfg_mgr.is_live_stream_mode() is True
        assert cfg_mgr.is_streaming_enabled() is True
        assert cfg_mgr.is_audit_mode() is True
        assert cfg_mgr.get_telemetry_mode() == 'both'

        # 4. Стриминг можно отключать отдельно от аудита
        cfg_mgr.deactivate_streaming_mode()
        assert cfg_mgr.is_streaming_enabled() is False
        assert cfg_mgr.is_live_stream_mode() is False
        assert cfg_mgr.is_audit_mode() is True
        assert cfg_mgr.get_telemetry_mode() == 'audit'

        # 5. Можно запускать оба процесса одновременно
        cfg_mgr.activate_both_mode(pid=pid, interval_sec=1.0)
        assert cfg_mgr.is_streaming_enabled() is True
        assert cfg_mgr.is_audit_mode() is True
        assert cfg_mgr.get_telemetry_mode() == 'both'


def test_storage_save_and_read_process_audit(temp_telemetry_storage):
    """Проверяет сохранение и извлечение срезов глубокого аудита в таблицу process_audit_samples."""
    current_pid = os.getpid()
    auditor = ProcessAuditor()
    sample = auditor.audit_process(pid=current_pid)
    assert sample is not None

    # Сохранение в базу данных
    row_id = temp_telemetry_storage.save_process_audit_sample(sample)
    assert row_id is not None
    assert row_id > 0

    # Чтение истории аудита из базы
    history = temp_telemetry_storage.get_process_audit_history(pid=current_pid, limit=10)
    assert len(history) == 1
    record = history[0]
    assert record['pid'] == current_pid
    assert record['name'] == sample.name
    assert record['working_set_mb'] == sample.memory.working_set_mb
    assert record['private_mb'] == sample.memory.private_mb
    assert record['total_context_switches'] == sample.cpu.total_context_switches


def test_telemetry_service_audit_cycle(temp_telemetry_storage):
    """Проверяет вызов audit_process_once сервисом TelemetryLoggerService."""
    current_pid = os.getpid()
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg_file = Path(tmp_dir) / "config.json"
        cfg_mgr = TelemetryConfigManager(config_path=cfg_file)
        service = TelemetryLoggerService(storage=temp_telemetry_storage, config_manager=cfg_mgr)

        sample = service.audit_process_once(current_pid)
        assert sample is not None
        assert service.last_process_audit_sample is not None
        assert service.last_process_audit_sample.pid == current_pid

        # Проверяем, что замер попал в хранилище
        history = temp_telemetry_storage.get_process_audit_history(pid=current_pid, limit=5)
        assert len(history) >= 1


def test_telemetry_service_separate_audit_and_streaming(temp_telemetry_storage):
    """Проверяет независимость аудита и стриминга: аудит активен всегда, стриминг отключается отдельно."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg_file = Path(tmp_dir) / "config.json"
        cfg_mgr = TelemetryConfigManager(config_path=cfg_file)
        service = TelemetryLoggerService(storage=temp_telemetry_storage, config_manager=cfg_mgr)

        # 1. На старте телеметрии аудит активен в любом случае
        assert service.is_audit_active() is True
        assert service.is_streaming_active() is False

        # 2. Активация стриминга: стриминг включается, аудит не прекращается
        service.activate_streaming_mode(interval_sec=2.0)
        assert service.is_streaming_active() is True
        assert service.is_audit_active() is True

        # 3. Отключение стриминга отдельно от аудита
        service.deactivate_streaming_mode()
        assert service.is_streaming_active() is False
        assert service.is_audit_active() is True  # Аудит продолжает работать!

        # 4. Активация обоих процессов одновременно
        service.activate_both_mode()
        assert service.is_streaming_active() is True
        assert service.is_audit_active() is True


def test_telemetry_api_endpoints():
    """Проверяет FastAPI эндпоинты режимов телеметрии, стриминга и аудита процесса."""
    app = FastAPI()
    app.include_router(windows_router)
    client = TestClient(app)

    current_pid = os.getpid()

    # 1. GET /api/windows/telemetry/mode
    resp = client.get("/api/windows/telemetry/mode")
    assert resp.status_code == 200
    data = resp.json()
    assert "mode" in data
    assert "is_audit_mode" in data
    assert "audit_enabled" in data
    assert "streaming_enabled" in data

    # 2. POST /api/windows/telemetry/mode (активация audit)
    resp = client.post("/api/windows/telemetry/mode", json={"mode": "audit", "pid": current_pid, "interval_sec": 1.0})
    assert resp.status_code == 200
    assert resp.json()["mode"] == "audit"
    assert resp.json()["target_pid"] == current_pid
    assert resp.json()["audit_enabled"] is True
    assert resp.json()["streaming_enabled"] is False

    # 3. GET /api/windows/telemetry/audit/{pid}
    resp = client.get(f"/api/windows/telemetry/audit/{current_pid}")
    assert resp.status_code == 200
    sample_data = resp.json()
    assert sample_data["pid"] == current_pid
    assert "cpu" in sample_data
    assert "memory" in sample_data
    assert "io" in sample_data
    assert "network" in sample_data

    # 4. POST /api/windows/telemetry/mode (активация обоих процессов: both)
    resp = client.post("/api/windows/telemetry/mode", json={"mode": "both"})
    assert resp.status_code == 200
    assert resp.json()["mode"] == "both"
    assert resp.json()["audit_enabled"] is True
    assert resp.json()["streaming_enabled"] is True

    # 5. POST /api/windows/telemetry/streaming/stop (остановка стриминга отдельно от аудита)
    resp = client.post("/api/windows/telemetry/streaming/stop")
    assert resp.status_code == 200
    assert resp.json()["streaming_enabled"] is False
    assert resp.json()["audit_enabled"] is True

    # 6. POST /api/windows/telemetry/streaming/start (запуск стриминга отдельно)
    resp = client.post("/api/windows/telemetry/streaming/start")
    assert resp.status_code == 200
    assert resp.json()["streaming_enabled"] is True
    assert resp.json()["audit_enabled"] is True

