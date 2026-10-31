# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Process Provenance Aggregation
# =============================================================================
# Description:
#   Тесты многоуровневой агрегации процессов с привязкой к параметрам запуска,
#   командной строке и родительской программе (тики за сутки -> суточные -> недельные -> за всё время).
#
# File: test_process_provenance_aggregation.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-16 19:47:00
# =============================================================================

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
import pytest

from apps.windows.telemetry.sqlite.connection import TelemetryConnectionManager
from apps.windows.telemetry.sqlite.schema import init_database_schema
from apps.windows.telemetry.sqlite.aggregator import TelemetrySqlAggregator
from apps.windows.telemetry.sqlite.storage import TelemetryStorage


@pytest.fixture
def test_db(tmp_path: Path) -> Path:
    """Создает временную базу данных с инициализированной схемой."""
    db_file = tmp_path / "test_telemetry.db"
    conn = sqlite3.connect(str(db_file))
    init_database_schema(conn)
    conn.close()
    return db_file


def test_process_provenance_multi_tier_aggregation(test_db: Path) -> None:
    """Проверка конвейера агрегации: 24ч тики -> суточный бакет -> недельный -> за все время."""
    cm = TelemetryConnectionManager(db_path=test_db)
    now_epoch = time.time()
    day_sec = 86400.0

    target_cmd = "python apps.windows -hidden"
    parent_app = "ai-admin.exe"

    with cm.lock, cm.get_connection() as conn:
        cursor = conn.cursor()

        # 1. Добавляем сессии запуска (3 сессии: 2 дня назад, 1 день назад, сегодня)
        sessions = [
            ("inst_day2_1", 1001, "python.exe", target_cmd, parent_app, now_epoch - 2 * day_sec, now_epoch - 2 * day_sec + 300, 300.0, 45.0),
            ("inst_day1_1", 1002, "python.exe", target_cmd, parent_app, now_epoch - 1.2 * day_sec, now_epoch - 1.2 * day_sec + 600, 600.0, 90.0),
            ("inst_today_1", 1003, "python.exe", target_cmd, parent_app, now_epoch - 3600, now_epoch - 3000, 600.0, 80.0),
        ]
        for inst_id, pid, name, cmd, parent, s_ts, e_ts, life, cpu_sec in sessions:
            cursor.execute(
                """
                INSERT INTO process_lifecycle_sessions (
                    instance_id, pid, name, cmdline, parent_name, created_ts, created_at,
                    terminated_ts, terminated_at, lifetime_sec, cpu_time_total_sec
                ) VALUES (?, ?, ?, ?, ?, ?, datetime(?, 'unixepoch'), ?, datetime(?, 'unixepoch'), ?, ?)
                """,
                (inst_id, pid, name, cmd, parent, s_ts, s_ts, e_ts, e_ts, life, cpu_sec),
            )

        # 2. Добавляем снимки системы (system_snapshots)
        for i, s_epoch in enumerate([now_epoch - 2 * day_sec, now_epoch - 1.2 * day_sec, now_epoch - 3600]):
            cursor.execute(
                "INSERT INTO system_snapshots (id, timestamp, created_at, hostname) VALUES (?, datetime(?, 'unixepoch'), ?, 'HOST-TEST')",
                (i + 1, s_epoch, s_epoch),
            )

        # 3. Добавляем детальные тики (process_snapshots)
        # Старые тики (2 дня назад) - 3 тика
        for idx in range(3):
            t_epoch = now_epoch - 2 * day_sec + idx * 60
            cursor.execute(
                """
                INSERT INTO process_snapshots (
                    snapshot_id, sample_type, instance_id, timestamp, created_at, pid, name,
                    cpu_percent, memory_mb, read_bytes_sec, write_bytes_sec
                ) VALUES (1, 'snapshot', 'inst_day2_1', datetime(?, 'unixepoch'), ?, 1001, 'python.exe', 15.0, 120.0, 1024, 512)
                """,
                (t_epoch, t_epoch),
            )

        # Старые тики (1.2 дня назад = >24 ч) - 4 тика
        for idx in range(4):
            t_epoch = now_epoch - 1.2 * day_sec + idx * 60
            cursor.execute(
                """
                INSERT INTO process_snapshots (
                    snapshot_id, sample_type, instance_id, timestamp, created_at, pid, name,
                    cpu_percent, memory_mb, read_bytes_sec, write_bytes_sec
                ) VALUES (2, 'snapshot', 'inst_day1_1', datetime(?, 'unixepoch'), ?, 1002, 'python.exe', 20.0, 150.0, 2048, 1024)
                """,
                (t_epoch, t_epoch),
            )

        # Свежие тики сегодняшнего дня (< 24 ч) - 5 тиков
        for idx in range(5):
            t_epoch = now_epoch - 3600 + idx * 60
            cursor.execute(
                """
                INSERT INTO process_snapshots (
                    snapshot_id, sample_type, instance_id, timestamp, created_at, pid, name,
                    cpu_percent, memory_mb, read_bytes_sec, write_bytes_sec
                ) VALUES (3, 'snapshot', 'inst_today_1', datetime(?, 'unixepoch'), ?, 1003, 'python.exe', 10.0, 110.0, 512, 256)
                """,
                (t_epoch, t_epoch),
            )

        conn.commit()

    # Запускаем агрегатор
    aggregator = TelemetrySqlAggregator(connection_manager=cm)
    res_daily = aggregator.aggregate_processes_daily(cutoff_seconds=day_sec)
    assert res_daily["rollups_created"] >= 1

    res_weekly = aggregator.aggregate_processes_weekly(window_days=7)
    assert res_weekly["weekly_created"] >= 1

    res_all = aggregator.aggregate_processes_all_time()
    assert res_all["all_time_created"] >= 1

    # Проверяем хранилище
    with cm.lock, cm.get_connection() as conn:
        cursor = conn.cursor()

        # 1. Проверяем, что свежие тики (<24ч) сохранились в базе для постоянной детализации!
        fresh_ticks = cursor.execute(
            "SELECT COUNT(*) FROM process_snapshots WHERE instance_id = 'inst_today_1'"
        ).fetchone()[0]
        assert fresh_ticks == 5, "Тики за последние сутки должны сохраняться с потиковой детализацией"

        # 2. Проверяем, что старые тики (>24ч) были очищены после сворачивания в суточные бакеты
        old_ticks = cursor.execute(
            "SELECT COUNT(*) FROM process_snapshots WHERE instance_id IN ('inst_day2_1', 'inst_day1_1')"
        ).fetchone()[0]
        assert old_ticks == 0, "Сырые тики старше 24ч должны быть очищены после сохранения в proc_daily"

        # 3. Проверяем наличие суточных бакетов proc_daily и расширенных статистик
        daily_rollups = cursor.execute(
            "SELECT tier, sensor_id, sample_count, cpu_avg, ram_avg, payload_json FROM telemetry_rollups WHERE tier = 'proc_daily'"
        ).fetchall()
        assert len(daily_rollups) >= 1
        pl = json.loads(daily_rollups[0][5])
        assert pl["cmdline"] == target_cmd
        assert pl["parent_name"] == parent_app
        assert pl["launch_count"] >= 1

        # Проверяем расширенный статистический профиль: перцентили, гистограмму, ввод-вывод
        assert "cpu" in pl and "p50" in pl["cpu"] and "p95" in pl["cpu"] and "p99" in pl["cpu"]
        assert "memory_mb" in pl and "p50" in pl["memory_mb"] and "p95" in pl["memory_mb"]
        assert "hourly_distribution" in pl and isinstance(pl["hourly_distribution"], dict)
        assert sum(d["samples"] for d in pl["hourly_distribution"].values()) == pl["sample_count"]
        assert "io" in pl and "total_read_mb" in pl["io"] and "total_write_mb" in pl["io"]
        assert "lifecycle" in pl and "clean_exits" in pl["lifecycle"]

        # 4. Проверяем профиль proc_all_time
        all_time = cursor.execute(
            "SELECT tier, sensor_id, sample_count, payload_json FROM telemetry_rollups WHERE tier = 'proc_all_time'"
        ).fetchall()
        assert len(all_time) >= 1
        all_pl = json.loads(all_time[0][3])
        assert all_pl["total_launches"] >= 2
        assert all_pl["cmdline"] == target_cmd

    # 5. Проверяем API чтения TelemetryStorage
    storage = TelemetryStorage(db_path=test_db)
    analytics = storage.get_process_provenance_analytics(cmdline_pattern="apps.windows")
    assert analytics["matched_processes_count"] >= 1
    target_data = analytics["processes"][0]
    assert target_data["cmdline"] == target_cmd
    assert target_data["parent_name"] == parent_app
    assert len(target_data["recent_ticks_24h"]) == 5
    assert len(target_data["daily_history"]) >= 1
    assert target_data["all_time"]["total_launches"] >= 2

    # Проверяем, что в daily_history присутствует полная статистика
    daily_first = target_data["daily_history"][0]
    assert "cpu" in daily_first and "p95" in daily_first["cpu"]
    assert "hourly_distribution" in daily_first
    assert "io" in daily_first and "total_read_mb" in daily_first["io"]
    storage.close()


