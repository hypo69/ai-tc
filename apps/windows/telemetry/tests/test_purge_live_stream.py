# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry Tests - Purge Live Stream
# =============================================================================
# Description:
#   Тестирование очистки таблиц стримингового режима live stream при переходе
#   в режим Audit или вызове purge_live_stream_tables:
#   - Таблицы live stream очищаются (system_snapshots, process_snapshots, sensor_polls и т.д.).
#   - Буфер очереди в памяти сбрасывается без сохранения в БД.
#   - Таблицы аудита процессов (process_lifecycle_sessions, process_audit_samples) сохраняются.
#
# File: test_purge_live_stream.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 01:18:00
# =============================================================================

import os
import gc
import shutil
import tempfile
import pytest
from pathlib import Path

from apps.windows.telemetry.sqlite import TelemetryStorage
from apps.windows.telemetry.models import SystemSnapshot, ProcessMetrics


@pytest.fixture
def temp_storage():
    """Создает изолированную тестовую базу данных SQLite."""
    tmp_dir = tempfile.mkdtemp(prefix="test_purge_")
    db_file = Path(tmp_dir) / "test_purge_stream.db"
    storage = TelemetryStorage(db_path=db_file)
    try:
        yield storage
    finally:
        storage.close()
        del storage
        gc.collect()
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_purge_live_stream_clears_stream_and_preserves_audit(temp_storage):
    """Проверяет, что purge_live_stream_tables очищает таблицы стрима и сохраняет аудит."""
    storage = temp_storage

    # 1. Заполняем таблицы Live Stream (снапшот системы + процессы + сенсоры)
    snap = SystemSnapshot(
        timestamp="2026-10-15T01:00:00Z",
        hostname="TEST-HOST",
        cpu_total_percent=15.5,
        memory_percent=42.0,
        top_processes=[
            ProcessMetrics(pid=1001, name="test_proc.exe", cpu_percent=5.0, memory_mb=128.0)
        ]
    )
    storage.save_snapshot(snap)
    storage.save_sensor_poll({"sensor_id": "cpu_temp", "value": 45.0, "unit": "C"})
    storage.flush()

    # Проверяем, что записи live stream сохранены
    stats_before = storage.get_storage_stats()
    assert stats_before["snapshots_count"] >= 1
    assert stats_before["process_snapshots_count"] >= 1
    assert stats_before["sensor_polls_count"] >= 1

    # 2. Заполняем таблицы Audit и Lifecycle (они ДОЛЖНЫ сохраниться)
    from apps.windows.sdk.modules.process_manager import ProcessAuditor
    current_pid = os.getpid()
    auditor = ProcessAuditor()
    audit_sample = auditor.audit_process(pid=current_pid)
    assert audit_sample is not None

    storage.save_process_audit_sample(audit_sample)

    storage.upsert_process_lifecycle_session({
        "instance_id": audit_sample.instance_id or f"{current_pid}_1760000000000",
        "pid": current_pid,
        "ppid": 4,
        "name": audit_sample.name,
        "created_at": "2026-10-15T01:01:00Z",
        "created_ts": 1760000000.0,
        "is_alive": True,
        "initiator_type": "SYSTEM",
    })

    # Проверяем наличие записей аудита и сессии
    audit_samples = storage.get_process_audit_history(pid=current_pid)
    assert len(audit_samples) == 1
    sessions = storage.get_process_lifecycle_sessions(pid=current_pid)
    assert len(sessions) == 1

    # 3. Добавляем в буфер запись live stream (в памяти)
    storage.save_sensor_poll({"sensor_id": "gpu_temp", "value": 55.0, "unit": "C"})
    assert storage.get_buffered_count() > 0

    # 4. Вызываем purge_live_stream_tables
    purged = storage.purge_live_stream_tables(vacuum=True)

    # 5. Проверяем результат:
    # Буфер сброшен и очищен
    assert storage.get_buffered_count() == 0

    # Таблицы live stream очищены
    stats_after = storage.get_storage_stats()
    assert stats_after["snapshots_count"] == 0
    assert stats_after["process_snapshots_count"] == 0
    assert stats_after["sensor_polls_count"] == 0

    # Таблицы аудита и сессий ЖИВЫ и НЕ тронуты
    audit_samples_after = storage.get_process_audit_history(pid=current_pid)
    assert len(audit_samples_after) == 1
    assert audit_samples_after[0]["pid"] == current_pid

    sessions_after = storage.get_process_lifecycle_sessions(pid=current_pid)
    assert len(sessions_after) == 1
    assert sessions_after[0]["pid"] == current_pid


def test_buffer_clear_discards_queued_records(temp_storage):
    """Проверяет метод clear() у буфера телеметрии."""
    storage = temp_storage
    storage._buffer.enqueue({"type": "sensor_poll", "data": {"sensor_id": "fan_1", "value": 1500}})
    assert storage.get_buffered_count() >= 1

    discarded = storage._buffer.clear()
    assert discarded >= 1
    assert storage.get_buffered_count() == 0

    # Сброс не должен записать ничего в БД
    saved = storage.flush()
    assert saved == 0

