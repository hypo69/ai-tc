# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry Tests - History Retention
# =============================================================================
# Description:
#   Тесты хранения истории потребления ресурсов (железо и приложения):
#   - настройка history_retention (месяц, 3 мес, полгода, год, вечно);
#   - очистка истории по сроку, режим «вечно» ничего не удаляет;
#   - purge live stream не трогает историю;
#   - накопление суточного бакета приложения без перезаписи при нескольких проходах;
#   - размер тика опирается на interval_seconds.
#
# File: test_history_retention.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-30 12:50:00
# =============================================================================

import json
import sqlite3
import tempfile
import time
from pathlib import Path

import pytest

from apps.windows.telemetry.service import TelemetryLoggerService
from apps.windows.telemetry.sqlite import TelemetryStorage
from apps.windows.telemetry.sqlite.aggregator import TelemetrySqlAggregator
from apps.windows.telemetry.sqlite.connection import TelemetryConnectionManager
from apps.windows.telemetry.telemetry_config import TelemetryConfigManager

DAY = 86400.0


def _cfg(data: dict) -> Path:
    f = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8')
    json.dump(data, f)
    f.close()
    return Path(f.name)


@pytest.mark.parametrize('value,days', [
    ('1m', 30), ('3m', 90), ('6m', 180), ('1y', 365), ('forever', 0), ('мусор', 0),
])
def test_history_retention_days(value, days):
    """Срок хранения истории переводится в дни, неизвестное значение означает «вечно»."""
    mgr = TelemetryConfigManager(config_path=_cfg({'history_retention': value}))
    assert mgr.get_history_retention_days() == days


def test_history_retention_default_is_forever():
    """Без настройки история хранится вечно."""
    mgr = TelemetryConfigManager(config_path=_cfg({'interval_seconds': 5.0}))
    assert mgr.get_history_retention_days() == 0


@pytest.fixture
def storage(tmp_path):
    return TelemetryStorage(db_path=tmp_path / 't.db')


def _insert_rollup(db_path, tier, sensor_id, created_at):
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            "INSERT INTO telemetry_rollups (tier, sensor_id, bucket_start, created_at) VALUES (?, ?, ?, ?)",
            (tier, sensor_id, created_at, created_at),
        )


def _count(db_path, tier):
    with sqlite3.connect(str(db_path)) as conn:
        return conn.execute("SELECT COUNT(*) FROM telemetry_rollups WHERE tier = ?", (tier,)).fetchone()[0]


def test_purge_history_removes_only_expired(storage, tmp_path):
    """purge_history(days) удаляет историю старше срока и сохраняет свежую."""
    db = tmp_path / 't.db'
    now = time.time()
    _insert_rollup(db, 'daily', 'cpu', now - 400 * DAY)
    _insert_rollup(db, 'proc_daily', 'a.exe', now - 400 * DAY)
    _insert_rollup(db, 'proc_daily', 'b.exe', now - 10 * DAY)

    deleted = storage.purge_history(365)

    assert deleted == 2
    assert _count(db, 'daily') == 0
    assert _count(db, 'proc_daily') == 1


def test_purge_history_forever_keeps_everything(storage, tmp_path):
    """Срок 0 означает «вечно»: ничего не удаляется."""
    db = tmp_path / 't.db'
    _insert_rollup(db, 'proc_daily', 'a.exe', time.time() - 2000 * DAY)
    assert storage.purge_history(0) == 0
    assert _count(db, 'proc_daily') == 1


def test_purge_live_stream_keeps_history_tiers(storage, tmp_path):
    """Очистка live stream не удаляет накопленную историю железа и приложений."""
    db = tmp_path / 't.db'
    now = time.time()
    _insert_rollup(db, 'hourly', 'cpu', now)
    _insert_rollup(db, 'proc_daily', 'a.exe', now)
    _insert_rollup(db, 'proc_all_time', 'a.exe', now)
    _insert_rollup(db, '30s', '__system__', now)

    storage.purge_live_stream_tables(vacuum=False)

    assert _count(db, 'hourly') == 1
    assert _count(db, 'proc_daily') == 1
    assert _count(db, 'proc_all_time') == 1
    assert _count(db, '30s') == 0


def _insert_ticks(cm, epoch, count, cpu):
    with cm.lock, cm.get_connection() as conn:
        for i in range(count):
            t = epoch + i * 5
            conn.execute(
                "INSERT INTO process_snapshots (sample_type, timestamp, created_at, pid, name, cpu_percent, memory_mb, "
                "read_bytes_sec, write_bytes_sec) VALUES ('snapshot', datetime(?, 'unixepoch'), ?, 10, 'app.exe', ?, 100.0, 0, 0)",
                (t, t, cpu),
            )
        conn.commit()


def test_daily_bucket_accumulates_across_runs(tmp_path):
    """Повторная агрегация того же дня дополняет суточный бакет, а не перезаписывает его."""
    db = tmp_path / 't.db'
    storage = TelemetryStorage(db_path=db)
    cm = TelemetryConnectionManager(db_path=db)
    agg = TelemetrySqlAggregator(connection_manager=cm)
    day_start = (int(time.time() // DAY) - 3) * DAY
    base = day_start + 3600

    _insert_ticks(cm, base, 3, 10.0)
    agg.aggregate_processes_daily(cutoff_seconds=DAY)
    _insert_ticks(cm, base + 600, 2, 30.0)
    agg.aggregate_processes_daily(cutoff_seconds=DAY)

    with sqlite3.connect(str(db)) as conn:
        rows = conn.execute("SELECT sample_count, cpu_avg, cpu_max FROM telemetry_rollups WHERE tier = 'proc_daily'").fetchall()
    assert len(rows) == 1
    assert rows[0][0] == 5
    assert rows[0][1] == pytest.approx((3 * 10.0 + 2 * 30.0) / 5)
    assert rows[0][2] == 30.0
    storage.close() if hasattr(storage, 'close') else None


def test_tick_uses_interval_seconds_in_audit_mode():
    """Тик опирается на interval_seconds; ускорение аудита работает только при целевом PID."""
    cfg = _cfg({'mode': 'audit', 'interval_seconds': 5.0, 'audit_interval_sec': 1.0})
    tmp = tempfile.mkdtemp(prefix='tick_')
    svc = TelemetryLoggerService(
        storage=TelemetryStorage(db_path=Path(tmp) / 't.db'),
        config_manager=TelemetryConfigManager(config_path=cfg),
    )
    assert svc.config_manager.get_audit_target_pid() is None
    assert svc.get_tick_interval() == 5.0

    svc.config_manager.get_audit_target_pid = lambda: 123
    assert svc.get_tick_interval() == 1.0
