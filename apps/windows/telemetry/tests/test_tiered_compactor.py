# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Telemetry Tests - Tiered Compactor
# =============================================================================
# Description:
#   Модульные тесты для каскадного многоуровневого усреднения и компактификации:
#   - step_30s_rollup: усреднение 5с системных снимков и сенсоров в бакет 30с
#   - step_3m_rollup: усреднение 30с бакетов в 3m с очисткой 30с
#   - step_10m_rollup: усреднение 3m бакетов в 10m с очисткой 3m
#   - step_36h_rollup: усреднение 10m бакетов в 36h с очисткой 10m
#   - thorough_mode: пропуск усреднения и бессрочное сохранение сырых данных
#
# File: test_tiered_compactor.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 16:50:00
# =============================================================================

import gc
import shutil
import tempfile
import pytest
from pathlib import Path

from apps.windows.telemetry.sqlite import TelemetryStorage
from apps.windows.telemetry.sqlite.tiered_compactor import TelemetryTieredCompactor


@pytest.fixture
def temp_storage():
    """Создает изолированную тестовую базу данных SQLite."""
    tmp_dir = tempfile.mkdtemp(prefix="test_compactor_")
    db_file = Path(tmp_dir) / "test_tiered.db"
    storage = TelemetryStorage(db_path=db_file)
    try:
        yield storage
    finally:
        storage.close()
        del storage
        gc.collect()
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_thorough_mode_skips_compaction(temp_storage):
    """Проверяет, что при thorough_mode=True каскадное усреднение пропускается."""
    compactor = TelemetryTieredCompactor(temp_storage._cm)
    res = compactor.run_tiered_compaction(thorough_mode=True, now_epoch=1000.0)
    assert res.get("skipped") is True
    assert res.get("reason") == "thorough_mode"


def test_step_30s_rollup_and_raw_cleanup(temp_storage):
    """Проверяет сворачивание пятисекундных снимков в 30-секундный бакет и удаление сырых строк."""
    compactor = TelemetryTieredCompactor(temp_storage._cm)
    cm = temp_storage._cm

    # Заполняем базу двумя пятисекундными снимками в окне [60, 90)
    with cm.lock, cm.get_connection() as conn:
        cursor = conn.cursor()
        # Вставляем снимки со временем created_at = 65 и 70
        cursor.execute(
            """
            INSERT INTO system_snapshots (
                timestamp, hostname, cpu_total_percent, memory_percent,
                memory_used_gb, disk_read_bytes_sec, disk_write_bytes_sec,
                network_sent_bytes_sec, network_recv_bytes_sec, created_at
            ) VALUES
            ('2026-10-28T12:01:05Z', 'TEST-HOST', 10.0, 50.0, 8.0, 1000.0, 2000.0, 500.0, 600.0, 65.0),
            ('2026-10-28T12:01:10Z', 'TEST-HOST', 20.0, 60.0, 10.0, 3000.0, 4000.0, 700.0, 800.0, 70.0),
            -- И свежий снимок в окне [90, 120), который не должен удаляться
            ('2026-10-28T12:01:40Z', 'TEST-HOST', 30.0, 70.0, 12.0, 100.0, 200.0, 50.0, 60.0, 100.0)
            """
        )
        # Вставляем показания сенсоров в окне [60, 90)
        cursor.execute(
            """
            INSERT INTO sensor_polls (timestamp, sensor_id, sensor_name, value, unit, created_at)
            VALUES
            ('2026-10-28T12:01:05Z', 'cpu_temp', 'CPU Package', 55.0, 'C', 65.0),
            ('2026-10-28T12:01:10Z', 'cpu_temp', 'CPU Package', 65.0, 'C', 70.0)
            """
        )
        conn.commit()

    # Вызываем step_30s_rollup при now_epoch = 125 (cutoff_epoch = 95)
    # Окно [60, 90) должно свернуться, а снимок на 100.0 останется
    stats = compactor.step_30s_rollup(now_epoch=125.0)
    assert stats["rollups_created"] >= 1

    with cm.lock, cm.get_connection() as conn:
        cursor = conn.cursor()
        # Проверяем запись в telemetry_rollups для __system__
        cursor.execute("SELECT tier, sensor_id, bucket_start, bucket_end, sample_count, cpu_avg, cpu_max, ram_avg FROM telemetry_rollups WHERE tier='30s' AND sensor_id='__system__'")
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "30s"
        assert row[1] == "__system__"
        assert row[2] == 60.0
        assert row[3] == 90.0
        assert row[4] == 2
        assert row[5] == 15.0  # (10 + 20) / 2
        assert row[6] == 20.0  # max(10, 20)
        assert row[7] == 55.0  # (50 + 60) / 2

        # Проверяем запись в telemetry_rollups для сенсора
        cursor.execute("SELECT sample_count, value_min, value_max, value_avg FROM telemetry_rollups WHERE tier='30s' AND sensor_id='cpu_temp'")
        s_row = cursor.fetchone()
        assert s_row is not None
        assert s_row[0] == 2
        assert s_row[1] == 55.0
        assert s_row[2] == 65.0
        assert s_row[3] == 60.0

        # Сырые сенсоры из окна [60, 90) удалены
        cursor.execute("SELECT COUNT(*) FROM sensor_polls WHERE created_at < 90")
        assert cursor.fetchone()[0] == 0


def test_step_3m_rollup_and_30s_cleanup(temp_storage):
    """Проверяет усреднение 30-секундных бакетов в 3m и удаление строк 30s."""
    compactor = TelemetryTieredCompactor(temp_storage._cm)
    cm = temp_storage._cm

    # Создаем 30-секундные бакеты в интервале [0, 180)
    with cm.lock, cm.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO telemetry_rollups (
                tier, sensor_id, bucket_start, bucket_end, sample_count,
                cpu_avg, cpu_max, ram_avg, ram_max, created_at
            ) VALUES
            ('30s', '__system__', 0.0, 30.0, 6, 10.0, 15.0, 40.0, 45.0, 30.0),
            ('30s', '__system__', 30.0, 60.0, 6, 20.0, 25.0, 50.0, 55.0, 60.0),
            ('30s', '__system__', 60.0, 90.0, 6, 30.0, 35.0, 60.0, 65.0, 90.0)
            """
        )
        conn.commit()

    # cutoff = now - 180. Если now = 300, cutoff = 120.
    # Бакеты [0, 30), [30, 60), [60, 90) имеют bucket_end <= 90 <= 120, поэтому свернутся в [0, 180)
    stats = compactor.step_3m_rollup(now_epoch=300.0)
    assert stats["rollups_created"] >= 1
    assert stats["rows_cleaned"] == 3

    with cm.lock, cm.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT tier, bucket_start, bucket_end, sample_count, cpu_avg, cpu_max FROM telemetry_rollups WHERE tier='3m'")
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "3m"
        assert row[1] == 0.0
        assert row[2] == 180.0
        assert row[3] == 18  # 6 + 6 + 6
        assert row[4] == 20.0  # (10 + 20 + 30) / 3
        assert row[5] == 35.0  # max(15, 25, 35)

        # Проверяем, что исходные строки '30s' удалены
        cursor.execute("SELECT COUNT(*) FROM telemetry_rollups WHERE tier='30s'")
        assert cursor.fetchone()[0] == 0


def test_step_10m_rollup_and_3m_cleanup(temp_storage):
    """Проверяет усреднение 3-минутных бакетов в 10m и удаление строк 3m."""
    compactor = TelemetryTieredCompactor(temp_storage._cm)
    cm = temp_storage._cm

    with cm.lock, cm.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO telemetry_rollups (
                tier, sensor_id, bucket_start, bucket_end, sample_count,
                cpu_avg, cpu_max, ram_avg, ram_max, created_at
            ) VALUES
            ('3m', '__system__', 0.0, 180.0, 18, 10.0, 20.0, 50.0, 50.0, 180.0),
            ('3m', '__system__', 180.0, 360.0, 18, 30.0, 40.0, 50.0, 50.0, 360.0)
            """
        )
        conn.commit()

    # cutoff = now - 600. При now = 1000, cutoff = 400.
    stats = compactor.step_10m_rollup(now_epoch=1000.0)
    assert stats["rollups_created"] >= 1
    assert stats["rows_cleaned"] == 2

    with cm.lock, cm.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT tier, bucket_start, bucket_end, sample_count, cpu_avg, cpu_max FROM telemetry_rollups WHERE tier='10m'")
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "10m"
        assert row[1] == 0.0
        assert row[2] == 600.0
        assert row[3] == 36
        assert row[4] == 20.0  # (10 + 30) / 2
        assert row[5] == 40.0


def test_step_36h_rollup_and_10m_cleanup(temp_storage):
    """Проверяет усреднение 10-минутных бакетов в 36h и удаление строк 10m."""
    compactor = TelemetryTieredCompactor(temp_storage._cm)
    cm = temp_storage._cm

    with cm.lock, cm.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO telemetry_rollups (
                tier, sensor_id, bucket_start, bucket_end, sample_count,
                cpu_avg, cpu_max, ram_avg, ram_max, created_at
            ) VALUES
            ('10m', '__system__', 0.0, 600.0, 36, 15.0, 25.0, 50.0, 50.0, 600.0),
            ('10m', '__system__', 600.0, 1200.0, 36, 25.0, 35.0, 50.0, 50.0, 1200.0)
            """
        )
        conn.commit()

    # 36 часов = 129600 сек. При now = 150000, cutoff = 150000 - 129600 = 20400.
    stats = compactor.step_36h_rollup(now_epoch=150000.0)
    assert stats["rollups_created"] >= 1
    assert stats["rows_cleaned"] == 2

    with cm.lock, cm.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT tier, bucket_start, bucket_end, sample_count, cpu_avg, cpu_max FROM telemetry_rollups WHERE tier='36h'")
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "36h"
        assert row[1] == 0.0
        assert row[2] == 129600.0
        assert row[3] == 72
        assert row[4] == 20.0
        assert row[5] == 35.0

