# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry Tests - Live Stream Report & HW Compare
# =============================================================================
# Description:
#   Тестирование новой архитектуры телеметрии:
#   1. Audit работает постоянно (непрерывный аудит процессов и инициаторов).
#   2. Live stream активируется по запросу (on-demand), при завершении НЕ вытирает таблицы,
#      а формирует детальный компактный отчет ресурсопотребления (чем и насколько было загружено железо).
#   3. Компактификация сырых тиков с минимальным ростом БД.
#   4. Изменения конфигурации оборудования («было / стало») сохраняются ВСЕГДА.
#   5. Сравнительный отчет производительности до и после модернизации железа («Было / Стало»).
#
# File: test_live_stream_report_and_hardware_compare.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 02:02:00
# =============================================================================

import os
import gc
import json
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.windows.telemetry.sqlite import TelemetryStorage
from apps.windows.telemetry.telemetry_config import TelemetryConfigManager
from apps.windows.telemetry.service import TelemetryLoggerService
from apps.windows.telemetry.models import SystemSnapshot, ProcessMetrics, CpuMetrics, MemoryMetrics
from apps.windows.router import router as windows_router


@pytest.fixture
def temp_storage():
    """Создает изолированную тестовую базу данных SQLite."""
    tmp_dir = tempfile.mkdtemp(prefix="test_live_report_")
    db_file = Path(tmp_dir) / "test_live_report.db"
    storage = TelemetryStorage(db_path=db_file)
    try:
        yield storage
    finally:
        storage.close()
        del storage
        gc.collect()
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_hardware_config_changes_saved_always(temp_storage):
    """Проверяет, что изменения конфигурации оборудования («было / стало») сохраняются навсегда."""
    storage = temp_storage

    # 1. Записываем факт замены процессора
    old_cpu = {"name": "Intel Core i5-8400", "cores": 6, "base_freq_mhz": 2800.0}
    new_cpu = {"name": "AMD Ryzen 7 7800X3D", "cores": 8, "base_freq_mhz": 4200.0}
    ch1_id = storage.save_hardware_config_change(
        component_type="CPU",
        change_type="REPLACED",
        component_name="AMD Ryzen 7 7800X3D",
        old_config=old_cpu,
        new_config=new_cpu,
        summary="Замена процессора: Intel Core i5-8400 -> AMD Ryzen 7 7800X3D",
    )
    assert ch1_id > 0

    # 2. Записываем факт добавления RAM
    old_ram = {"total_gb": 16.0, "modules_count": 2}
    new_ram = {"total_gb": 32.0, "modules_count": 4}
    ch2_id = storage.save_hardware_config_change(
        component_type="RAM",
        change_type="MODIFIED",
        component_name="RAM Memory",
        old_config=old_ram,
        new_config=new_ram,
        summary="Апгрейд оперативной памяти: 16GB -> 32GB",
    )
    assert ch2_id > ch1_id

    # 3. Извлекаем изменения
    changes = storage.get_hardware_config_changes()
    assert len(changes) == 2
    assert changes[0]["id"] == ch2_id
    assert changes[0]["component_type"] == "RAM"
    assert changes[0]["old_config"] == old_ram
    assert changes[0]["new_config"] == new_ram

    assert changes[1]["id"] == ch1_id
    assert changes[1]["component_type"] == "CPU"

    # 4. Проверяем, что очистка live stream НЕ удаляет записи изменений железа
    storage.purge_live_stream_tables(vacuum=False)
    changes_after_purge = storage.get_hardware_config_changes()
    assert len(changes_after_purge) == 2, "hardware_config_changes должны храниться ВСЕГДА"


def test_live_stream_report_generation_and_compaction(temp_storage):
    """Проверяет генерацию отчета сессии live stream и компактификацию вместо слепого удаления."""
    storage = temp_storage

    now = time.time()
    t1 = now - 5.0

    iso_now = datetime.now(timezone.utc).isoformat()

    # 1. Записываем сэмплы системного снапшота во время сессии live stream
    snap1 = SystemSnapshot(
        timestamp=iso_now,
        hostname="WORKSTATION",
        cpu=CpuMetrics(total_percent=65.0, temperature_celsius=58.0),
        memory=MemoryMetrics(percent=75.0, used_gb=12.0, total_gb=16.0),
        top_processes=[
            ProcessMetrics(pid=101, name="heavy_rendering.exe", cpu_percent=55.0, memory_mb=4096.0),
            ProcessMetrics(pid=102, name="chrome.exe", cpu_percent=8.0, memory_mb=2048.0),
        ]
    )
    storage.save_snapshot(snap1)

    snap2 = SystemSnapshot(
        timestamp=iso_now,
        hostname="WORKSTATION",
        cpu=CpuMetrics(total_percent=75.0, temperature_celsius=64.0),
        memory=MemoryMetrics(percent=80.0, used_gb=12.8, total_gb=16.0),
        top_processes=[
            ProcessMetrics(pid=101, name="heavy_rendering.exe", cpu_percent=68.0, memory_mb=4200.0),
        ]
    )
    storage.save_snapshot(snap2)
    storage.flush()
    t2 = time.time() + 2.0

    # 2. Финализируем сессию live stream в отчет ресурсопотребления
    session_id = "test-live-stream-001"
    report = storage.finalize_live_stream_session(
        session_id=session_id,
        started_ts=t1,
        ended_ts=t2,
        trigger_source="manual",
    )

    assert report is not None
    assert report["session_id"] == session_id
    assert report["cpu_max_percent"] >= 70.0
    assert report["ram_avg_used_gb"] >= 12.0
    assert "top_cpu_consumers" in report
    assert any(p["name"] == "heavy_rendering.exe" for p in report["top_cpu_consumers"])

    # 3. Проверяем наличие отчета в истории сессий
    saved_sessions = storage.get_live_stream_sessions()
    assert len(saved_sessions) == 1
    assert saved_sessions[0]["session_id"] == session_id

    # 4. Проверяем компактификацию: тики сжимаются, а сессионный профиль сохраняется
    compaction_res = storage.compact_live_stream_data(keep_last_snapshots=1)
    sessions_after_compact = storage.get_live_stream_sessions()
    assert len(sessions_after_compact) == 1, "Сессионный отчет должен сохраниться навсегда"


def test_hardware_upgrade_comparison_report(temp_storage):
    """Проверяет построение сравнительного отчета «Было / Стало» при модернизации железа."""
    storage = temp_storage
    now = time.time()

    # Сессия 1: ДО апгрейда (Intel Core i5)
    t_before_start = now - 3600.0
    t_before_end = now - 3000.0
    before_session = {
        "session_id": "session-before-upgrade",
        "started_at": "2026-10-15T01:00:00Z",
        "ended_at": "2026-10-15T01:10:00Z",
        "started_ts": t_before_start,
        "ended_ts": t_before_end,
        "duration_seconds": 600.0,
        "cpu_model": "Intel Core i5-8400",
        "cpu_avg_percent": 74.5,
        "cpu_max_percent": 98.0,
        "cpu_avg_temp_c": 78.5,
        "cpu_max_temp_c": 86.0,
        "ram_total_gb": 16.0,
        "ram_avg_used_gb": 13.5,
        "ram_avg_percent": 84.0,
        "disk_read_mbs": 45.0,
        "disk_write_mbs": 30.0,
    }
    storage.save_live_stream_session(before_session)

    # Факт апгрейда: замена процессора и памяти
    change_time = now - 1800.0
    ch_id = storage.save_hardware_config_change(
        component_type="CPU",
        change_type="REPLACED",
        component_name="AMD Ryzen 7 7800X3D",
        old_config={"name": "Intel Core i5-8400", "cores": 6},
        new_config={"name": "AMD Ryzen 7 7800X3D", "cores": 8},
        summary="Апгрейд: Intel Core i5-8400 -> AMD Ryzen 7 7800X3D",
        created_at=change_time,
    )

    # Сессия 2: ПОСЛЕ апгрейда (AMD Ryzen 7)
    t_after_start = now - 600.0
    t_after_end = now - 60.0
    after_session = {
        "session_id": "session-after-upgrade",
        "started_at": "2026-10-15T01:50:00Z",
        "ended_at": "2026-10-15T01:59:00Z",
        "started_ts": t_after_start,
        "ended_ts": t_after_end,
        "duration_seconds": 540.0,
        "cpu_model": "AMD Ryzen 7 7800X3D",
        "cpu_avg_percent": 24.0,
        "cpu_max_percent": 48.0,
        "cpu_avg_temp_c": 56.0,
        "cpu_max_temp_c": 64.0,
        "ram_total_gb": 32.0,
        "ram_avg_used_gb": 13.2,
        "ram_avg_percent": 41.2,
        "disk_read_mbs": 120.0,
        "disk_write_mbs": 95.0,
    }
    storage.save_live_stream_session(after_session)

    # Формируем сравнительный отчет
    rep = storage.get_hardware_comparison_report(change_id=ch_id)
    assert rep is not None
    assert rep["has_before_after_sessions"] is True
    assert rep["change_info"]["summary"] == "Апгрейд: Intel Core i5-8400 -> AMD Ryzen 7 7800X3D"

    deltas = rep["metrics_comparison"]
    assert deltas["cpu_avg_percent_diff"] < 0, "Загрузка CPU должна снизиться"
    assert deltas["cpu_avg_temp_diff_c"] < 0, "Температура CPU должна упасть"
    assert "снизилась" in rep["conclusion"] or "упала" in rep["conclusion"]


def test_service_live_stream_workflow_and_api(temp_storage):
    """Проверяет управление live stream через сервис и FastAPI эндпоинты."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg_file = Path(tmp_dir) / "config.json"
        cfg_mgr = TelemetryConfigManager(config_path=cfg_file)
        service = TelemetryLoggerService(storage=temp_storage, config_manager=cfg_mgr)

        # 1. По умолчанию режим Audit активен
        assert cfg_mgr.is_audit_mode() is True

        # 2. Запуск live stream по запросу
        sess_id = service.start_live_stream(duration_seconds=300.0)
        assert sess_id.startswith("live-")
        assert service.is_live_stream_active() is True

        # 3. Остановка live stream и получение отчета
        report = service.stop_live_stream()
        assert report is not None
        assert report["session_id"] == sess_id
        assert service.is_live_stream_active() is False

        # 4. Проверка FastAPI роутера
        app = FastAPI()
        app.include_router(windows_router)
        client = TestClient(app)

        # Start live stream
        resp_start = client.post("/api/windows/telemetry/live-stream/start", json={"duration_seconds": 60.0})
        assert resp_start.status_code == 200
        assert resp_start.json()["status"] == "started"

        # Stop live stream
        resp_stop = client.post("/api/windows/telemetry/live-stream/stop")
        assert resp_stop.status_code == 200
        assert resp_stop.json()["status"] == "stopped"

        # Sessions list
        resp_sessions = client.get("/api/windows/telemetry/live-stream/sessions")
        assert resp_sessions.status_code == 200
        assert isinstance(resp_sessions.json(), list)

        # Hardware changes
        resp_hw = client.get("/api/windows/telemetry/hardware/changes")
        assert resp_hw.status_code == 200
        assert isinstance(resp_hw.json(), list)

