# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Telemetry SQLite API Stability
# =============================================================================
# Description:
#   Тесты стабильности публичного API TelemetryWriter и TelemetryReader при
#   декомпозиции на миксины (этап 4 ТЗ оптимизации) и поведенческий дымовой тест
#   записи на временной БД.
#
# File: test_telemetry_sqlite_api.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-16 17:15:00
# =============================================================================

from __future__ import annotations

import gc
import inspect
import json
import shutil
import tempfile
from pathlib import Path

import pytest

from apps.windows.telemetry.sqlite import TelemetryStorage
from apps.windows.telemetry.sqlite.reader import TelemetryReader
from apps.windows.telemetry.sqlite.writer import TelemetryWriter

BASELINE_PATH = Path(__file__).parent / 'api_baselines' / 'telemetry_sqlite_api.json'


def _api(cls: type) -> dict[str, str]:
    """Собирает публичный API класса: имена и сигнатуры методов, свойства."""
    out: dict[str, str] = {}
    for name, member in inspect.getmembers(cls):
        if name.startswith('__') and name != '__init__':
            continue
        if isinstance(member, property):
            out[name] = 'property'
        elif callable(member):
            out[name] = str(inspect.signature(member))
    return out


@pytest.mark.parametrize('cls', [TelemetryWriter, TelemetryReader, TelemetryStorage], ids=lambda c: c.__name__)
def test_public_api_unchanged(cls: type) -> None:
    """Набор методов и их сигнатуры совпадают с эталоном, снятым до декомпозиции."""
    baseline = json.loads(BASELINE_PATH.read_text(encoding='utf-8'))[cls.__name__]
    assert _api(cls) == baseline


@pytest.fixture
def storage():
    """Хранилище на временной БД в режиме прямой записи."""
    tmpdir = tempfile.mkdtemp()
    st = TelemetryStorage(db_path=Path(tmpdir) / 'api_stability.db', buffer_mode='direct')
    try:
        yield st
    finally:
        st.close()
        del st
        gc.collect()
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_writer_domains_write_rows(storage: TelemetryStorage) -> None:
    """По одному методу из каждой группы записи реально пишут строки в БД."""
    writer = storage.writer
    with storage.get_connection() as conn:
        cur = conn.cursor()
        writer.insert_cpu_telemetry_sample(cur, {'total_percent': 12.5})
        writer.insert_disk_io_event(cur, {'device': 'C:', 'event_type': 'test'})
        conn.commit()
        cpu_rows = conn.execute('SELECT COUNT(*) FROM sensor_polls').fetchone()[0]
        io_rows = conn.execute('SELECT COUNT(*) FROM process_file_events').fetchone()[0]
    assert cpu_rows == 1 and io_rows == 1
    assert writer.save_services_snapshot('snap-1', []) == 0

def test_reader_domains_read_empty_db(storage: TelemetryStorage) -> None:
    """По одному методу из каждой группы чтения отрабатывают на пустой БД и возвращают пустые списки."""
    reader = storage.reader
    assert reader.get_snapshots() == []
    assert reader.get_disk_inventory() == []
    assert reader.get_reboot_history() == []
    assert reader.get_security_events() == []


def test_incidents_insert_and_aggregation_spike_incident_id(storage: TelemetryStorage) -> None:
    """Проверка генерации incident_id при фиксации всплесков агрегации и прямых вставках."""
    writer = storage.writer
    with storage.get_connection() as conn:
        cur = conn.cursor()
        writer.insert_event_row(cur, {"message": "test tel"})
        writer.insert_app_event(cur, {"app": "test_app", "event_type": "crash"})
        writer.insert_app_poll(cur, {"app": "test_app", "metric_name": "cpu", "value": 50.0})
        writer.insert_telemetry_spike(
            cur,
            {
                "sensor_id": "cpu_temp",
                "value": 95.0,
                "baseline_mean": 50.0,
                "baseline_sigma": 5.0,
                "deviation_factor": 9.0,
            },
        )
        conn.commit()

        rows = conn.execute("SELECT incident_id, domain FROM incidents").fetchall()
        assert len(rows) == 4
        for inc_id, _ in rows:
            assert inc_id is not None and inc_id != ""

    res = storage.run_aggregation_pipeline()
    assert isinstance(res, dict)


