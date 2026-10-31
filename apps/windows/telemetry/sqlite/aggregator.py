# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry Sqlite - Aggregator
# =============================================================================
# Description:
#   Многоуровневый SQL-агрегатор временных рядов телеметрии (raw -> hourly ->
#   daily -> weekly -> monthly -> yearly) в единой таблице telemetry_rollups
#   и фиксация всплесков в таблице incidents.
#
# Usage Examples:
#   Python API:
#     from apps.windows.telemetry.sqlite.aggregator import TelemetrySqlAggregator
#
#     agg = TelemetrySqlAggregator(connection_manager)
#     agg.run_pipeline()
#
# File: aggregator.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry.sqlite
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-30 13:05:00
# =============================================================================

from __future__ import annotations

"""Многоуровневый SQL-агрегатор временных рядов телеметрии и процессов в единую таблицу telemetry_rollups."""

import hashlib
import json
import sqlite3
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from .connection import TelemetryConnectionManager

try:
    from logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class AggregationLevel(str, Enum):
    """Уровни иерархической агрегации временных рядов телеметрии и процессов."""

    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    PROC_DAILY = "proc_daily"
    PROC_WEEKLY = "proc_weekly"
    PROC_ALL_TIME = "proc_all_time"


def sensors_aggregate(
    conn: sqlite3.Connection,
    level: Union[AggregationLevel, str],
    start_epoch: Optional[float] = None,
    end_epoch: Optional[float] = None,
    detect_spikes: bool = True,
) -> Dict[str, Any]:
    """Выполняет единую SQL-агрегацию сенсоров для указанного уровня иерархии в таблицу telemetry_rollups.

    Args:
        conn: Активное подключение к базе данных SQLite.
        level: Уровень агрегации ('hourly', 'daily', 'weekly', 'monthly', 'yearly').
        start_epoch: Начальная граница выборки в секундах epoch (опционально).
        end_epoch: Конечная граница выборки в секундах epoch (опционально).
        detect_spikes: Флаг сохранения статистических всплесков/аномалий в incidents.

    Returns:
        Dict[str, Any]: Словарь с количеством обработанных бакетов и сохраненных аномалий.
    """
    lvl_str = str(level.value if isinstance(level, AggregationLevel) else level).lower()
    cursor = conn.cursor()
    now_epoch = time.time()
    res: Dict[str, Any] = {"level": lvl_str, "buckets_aggregated": 0, "spikes_recorded": 0}

    if lvl_str == AggregationLevel.HOURLY.value:
        s_epoch = float(start_epoch) if start_epoch is not None else 0.0
        e_epoch = float(end_epoch) if end_epoch is not None else (int(now_epoch // 3600) * 3600.0)

        cursor.execute(
            """
            INSERT INTO telemetry_rollups (
                tier,
                sensor_id,
                bucket_start,
                bucket_end,
                sample_count,
                value_min,
                value_max,
                value_avg,
                value_sum,
                value_sum_sq,
                value_stddev,
                value_first,
                value_last,
                min_val,
                max_val,
                avg_val,
                sum_val,
                last_val,
                created_at
            )
            WITH raw_window AS (
                SELECT
                    sensor_id,
                    CAST(created_at / 3600 AS INTEGER) * 3600 AS b_start,
                    created_at,
                    value,
                    FIRST_VALUE(value) OVER (
                        PARTITION BY sensor_id, CAST(created_at / 3600 AS INTEGER) * 3600
                        ORDER BY created_at ASC
                    ) AS f_val,
                    FIRST_VALUE(value) OVER (
                        PARTITION BY sensor_id, CAST(created_at / 3600 AS INTEGER) * 3600
                        ORDER BY created_at DESC
                    ) AS l_val
                FROM sensor_polls
                WHERE created_at >= ? AND created_at < ? AND value IS NOT NULL
            )
            SELECT
                'hourly' AS tier,
                sensor_id,
                b_start AS bucket_start,
                b_start + 3600 AS bucket_end,
                COUNT(*) AS sample_count,
                MIN(value) AS value_min,
                MAX(value) AS value_max,
                AVG(value) AS value_avg,
                SUM(value) AS value_sum,
                SUM(value * value) AS value_sum_sq,
                SQRT(MAX(0.0, (SUM(value * value) - (SUM(value) * SUM(value)) / COUNT(*)) / COUNT(*))) AS value_stddev,
                MIN(f_val) AS value_first,
                MAX(l_val) AS value_last,
                MIN(value) AS min_val,
                MAX(value) AS max_val,
                AVG(value) AS avg_val,
                SUM(value) AS sum_val,
                MAX(l_val) AS last_val,
                b_start AS created_at
            FROM raw_window
            GROUP BY sensor_id, b_start
            ON CONFLICT(tier, sensor_id, bucket_start) DO UPDATE SET
                bucket_end = excluded.bucket_end,
                sample_count = excluded.sample_count,
                value_min = excluded.value_min,
                value_max = excluded.value_max,
                value_avg = excluded.value_avg,
                value_sum = excluded.value_sum,
                value_sum_sq = excluded.value_sum_sq,
                value_stddev = excluded.value_stddev,
                value_first = excluded.value_first,
                value_last = excluded.value_last,
                min_val = excluded.min_val,
                max_val = excluded.max_val,
                avg_val = excluded.avg_val,
                sum_val = excluded.sum_val,
                last_val = excluded.last_val;
            """,
            (s_epoch, e_epoch),
        )
        res["buckets_aggregated"] = cursor.rowcount if cursor.rowcount > 0 else 0

        if detect_spikes:
            cursor.execute(
                """
                INSERT OR IGNORE INTO incidents (
                    incident_id, timestamp, created_at, domain, trigger_type, severity,
                    title, sensor_id, value, baseline_mean, baseline_sigma, details_json
                )
                SELECT
                    'spike_' || p.sensor_id || '_' || p.id,
                    p.timestamp,
                    p.created_at,
                    'spike',
                    CASE WHEN p.value >= h.value_avg THEN 'high' ELSE 'low' END,
                    'WARNING',
                    'Spike: ' || p.sensor_id,
                    p.sensor_id,
                    p.value,
                    h.value_avg,
                    h.value_stddev,
                    'Всплеск: знач=' || ROUND(p.value, 2) || ', avg=' || ROUND(h.value_avg, 2) || ', std=' || ROUND(h.value_stddev, 2)
                FROM sensor_polls p
                JOIN telemetry_rollups h
                  ON h.tier = 'hourly'
                 AND p.sensor_id = h.sensor_id
                 AND (CAST(p.created_at / 3600 AS INTEGER) * 3600) = h.bucket_start
                WHERE h.value_stddev > 0.01
                  AND ABS(p.value - h.value_avg) >= 2.5 * h.value_stddev
                  AND p.created_at >= ? AND p.created_at < ?
                  AND NOT EXISTS (
                      SELECT 1 FROM incidents s
                      WHERE s.domain = 'spike' AND s.sensor_id = p.sensor_id AND s.created_at = p.created_at
                  );
                """,
                (s_epoch, e_epoch),
            )
            res["spikes_recorded"] = cursor.rowcount if cursor.rowcount > 0 else 0

    elif lvl_str == AggregationLevel.DAILY.value:
        s_epoch = float(start_epoch) if start_epoch is not None else 0.0
        e_epoch = float(end_epoch) if end_epoch is not None else (int(now_epoch // 86400) * 86400.0)

        cursor.execute(
            """
            INSERT INTO telemetry_rollups (
                tier, sensor_id, bucket_start, bucket_end, sample_count,
                value_min, value_max, value_avg, value_sum, value_sum_sq,
                value_stddev, value_first, value_last,
                min_val, max_val, avg_val, sum_val, last_val, created_at
            )
            WITH hourly_window AS (
                SELECT
                    sensor_id,
                    CAST(bucket_start / 86400 AS INTEGER) * 86400 AS b_start,
                    bucket_start,
                    sample_count,
                    value_min,
                    value_max,
                    value_sum,
                    value_sum_sq,
                    value_first,
                    value_last,
                    FIRST_VALUE(value_first) OVER (
                        PARTITION BY sensor_id, CAST(bucket_start / 86400 AS INTEGER) * 86400
                        ORDER BY bucket_start ASC
                    ) AS f_val,
                    FIRST_VALUE(value_last) OVER (
                        PARTITION BY sensor_id, CAST(bucket_start / 86400 AS INTEGER) * 86400
                        ORDER BY bucket_start DESC
                    ) AS l_val
                FROM telemetry_rollups
                WHERE tier = 'hourly' AND bucket_start >= ? AND bucket_start < ?
            )
            SELECT
                'daily' AS tier,
                sensor_id,
                b_start AS bucket_start,
                b_start + 86400 AS bucket_end,
                SUM(sample_count) AS sample_count,
                MIN(value_min) AS value_min,
                MAX(value_max) AS value_max,
                SUM(value_sum) / SUM(sample_count) AS value_avg,
                SUM(value_sum) AS value_sum,
                SUM(value_sum_sq) AS value_sum_sq,
                SQRT(MAX(0.0, (SUM(value_sum_sq) - (SUM(value_sum) * SUM(value_sum)) / SUM(sample_count)) / SUM(sample_count))) AS value_stddev,
                MIN(f_val) AS value_first,
                MAX(l_val) AS value_last,
                MIN(value_min) AS min_val,
                MAX(value_max) AS max_val,
                SUM(value_sum) / SUM(sample_count) AS avg_val,
                SUM(value_sum) AS sum_val,
                MAX(l_val) AS last_val,
                b_start AS created_at
            FROM hourly_window
            GROUP BY sensor_id, b_start
            ON CONFLICT(tier, sensor_id, bucket_start) DO UPDATE SET
                bucket_end = excluded.bucket_end,
                sample_count = excluded.sample_count,
                value_min = excluded.value_min,
                value_max = excluded.value_max,
                value_avg = excluded.value_avg,
                value_sum = excluded.value_sum,
                value_sum_sq = excluded.value_sum_sq,
                value_stddev = excluded.value_stddev,
                value_first = excluded.value_first,
                value_last = excluded.value_last,
                min_val = excluded.min_val,
                max_val = excluded.max_val,
                avg_val = excluded.avg_val,
                sum_val = excluded.sum_val,
                last_val = excluded.last_val;
            """,
            (s_epoch, e_epoch),
        )
        res["buckets_aggregated"] = cursor.rowcount if cursor.rowcount > 0 else 0

    elif lvl_str == AggregationLevel.WEEKLY.value:
        s_epoch = float(start_epoch) if start_epoch is not None else 0.0
        e_epoch = float(end_epoch) if end_epoch is not None else (int(now_epoch // 604800) * 604800.0)

        cursor.execute(
            """
            INSERT INTO telemetry_rollups (
                tier, sensor_id, bucket_start, bucket_end, sample_count,
                value_min, value_max, value_avg, value_sum, value_sum_sq,
                value_stddev, value_first, value_last,
                min_val, max_val, avg_val, sum_val, last_val, created_at
            )
            WITH daily_window AS (
                SELECT
                    sensor_id,
                    CAST(bucket_start / 604800 AS INTEGER) * 604800 AS b_start,
                    bucket_start,
                    sample_count,
                    value_min,
                    value_max,
                    value_sum,
                    value_sum_sq,
                    value_first,
                    value_last,
                    FIRST_VALUE(value_first) OVER (
                        PARTITION BY sensor_id, CAST(bucket_start / 604800 AS INTEGER) * 604800
                        ORDER BY bucket_start ASC
                    ) AS f_val,
                    FIRST_VALUE(value_last) OVER (
                        PARTITION BY sensor_id, CAST(bucket_start / 604800 AS INTEGER) * 604800
                        ORDER BY bucket_start DESC
                    ) AS l_val
                FROM telemetry_rollups
                WHERE tier = 'daily' AND bucket_start >= ? AND bucket_start < ?
            )
            SELECT
                'weekly' AS tier,
                sensor_id,
                b_start AS bucket_start,
                b_start + 604800 AS bucket_end,
                SUM(sample_count) AS sample_count,
                MIN(value_min) AS value_min,
                MAX(value_max) AS value_max,
                SUM(value_sum) / SUM(sample_count) AS value_avg,
                SUM(value_sum) AS value_sum,
                SUM(value_sum_sq) AS value_sum_sq,
                SQRT(MAX(0.0, (SUM(value_sum_sq) - (SUM(value_sum) * SUM(value_sum)) / SUM(sample_count)) / SUM(sample_count))) AS value_stddev,
                MIN(f_val) AS value_first,
                MAX(l_val) AS value_last,
                MIN(value_min) AS min_val,
                MAX(value_max) AS max_val,
                SUM(value_sum) / SUM(sample_count) AS avg_val,
                SUM(value_sum) AS sum_val,
                MAX(l_val) AS last_val,
                b_start AS created_at
            FROM daily_window
            GROUP BY sensor_id, b_start
            ON CONFLICT(tier, sensor_id, bucket_start) DO UPDATE SET
                bucket_end = excluded.bucket_end,
                sample_count = excluded.sample_count,
                value_min = excluded.value_min,
                value_max = excluded.value_max,
                value_avg = excluded.value_avg,
                value_sum = excluded.value_sum,
                value_sum_sq = excluded.value_sum_sq,
                value_stddev = excluded.value_stddev,
                value_first = excluded.value_first,
                value_last = excluded.value_last,
                min_val = excluded.min_val,
                max_val = excluded.max_val,
                avg_val = excluded.avg_val,
                sum_val = excluded.sum_val,
                last_val = excluded.last_val;
            """,
            (s_epoch, e_epoch),
        )
        res["buckets_aggregated"] = cursor.rowcount if cursor.rowcount > 0 else 0

    elif lvl_str == AggregationLevel.MONTHLY.value:
        s_epoch = float(start_epoch) if start_epoch is not None else 0.0
        e_epoch = float(end_epoch) if end_epoch is not None else now_epoch

        cursor.execute(
            """
            INSERT INTO telemetry_rollups (
                tier, sensor_id, bucket_start, bucket_end, sample_count,
                value_min, value_max, value_avg, value_sum, value_sum_sq,
                value_stddev, value_first, value_last,
                min_val, max_val, avg_val, sum_val, last_val, created_at
            )
            WITH daily_window AS (
                SELECT
                    sensor_id,
                    CAST(strftime('%s', datetime(bucket_start, 'unixepoch', 'start of month')) AS INTEGER) AS b_start,
                    CAST(strftime('%s', datetime(bucket_start, 'unixepoch', 'start of month', '+1 month')) AS INTEGER) AS b_end,
                    bucket_start,
                    sample_count,
                    value_min,
                    value_max,
                    value_sum,
                    value_sum_sq,
                    value_first,
                    value_last,
                    FIRST_VALUE(value_first) OVER (
                        PARTITION BY sensor_id, strftime('%Y-%m', datetime(bucket_start, 'unixepoch'))
                        ORDER BY bucket_start ASC
                    ) AS f_val,
                    FIRST_VALUE(value_last) OVER (
                        PARTITION BY sensor_id, strftime('%Y-%m', datetime(bucket_start, 'unixepoch'))
                        ORDER BY bucket_start DESC
                    ) AS l_val
                FROM telemetry_rollups
                WHERE tier = 'daily' AND bucket_start >= ? AND bucket_start < ?
            )
            SELECT
                'monthly' AS tier,
                sensor_id,
                b_start AS bucket_start,
                MAX(b_end) AS bucket_end,
                SUM(sample_count) AS sample_count,
                MIN(value_min) AS value_min,
                MAX(value_max) AS value_max,
                SUM(value_sum) / SUM(sample_count) AS value_avg,
                SUM(value_sum) AS value_sum,
                SUM(value_sum_sq) AS value_sum_sq,
                SQRT(MAX(0.0, (SUM(value_sum_sq) - (SUM(value_sum) * SUM(value_sum)) / SUM(sample_count)) / SUM(sample_count))) AS value_stddev,
                MIN(f_val) AS value_first,
                MAX(l_val) AS value_last,
                MIN(value_min) AS min_val,
                MAX(value_max) AS max_val,
                SUM(value_sum) / SUM(sample_count) AS avg_val,
                SUM(value_sum) AS sum_val,
                MAX(l_val) AS last_val,
                b_start AS created_at
            FROM daily_window
            GROUP BY sensor_id, b_start
            ON CONFLICT(tier, sensor_id, bucket_start) DO UPDATE SET
                bucket_end = excluded.bucket_end,
                sample_count = excluded.sample_count,
                value_min = excluded.value_min,
                value_max = excluded.value_max,
                value_avg = excluded.value_avg,
                value_sum = excluded.value_sum,
                value_sum_sq = excluded.value_sum_sq,
                value_stddev = excluded.value_stddev,
                value_first = excluded.value_first,
                value_last = excluded.value_last,
                min_val = excluded.min_val,
                max_val = excluded.max_val,
                avg_val = excluded.avg_val,
                sum_val = excluded.sum_val,
                last_val = excluded.last_val;
            """,
            (s_epoch, e_epoch),
        )
        res["buckets_aggregated"] = cursor.rowcount if cursor.rowcount > 0 else 0

    elif lvl_str == AggregationLevel.YEARLY.value:
        s_epoch = float(start_epoch) if start_epoch is not None else 0.0
        e_epoch = float(end_epoch) if end_epoch is not None else now_epoch

        cursor.execute(
            """
            INSERT INTO telemetry_rollups (
                tier, sensor_id, bucket_start, bucket_end, sample_count,
                value_min, value_max, value_avg, value_sum, value_sum_sq,
                value_stddev, value_first, value_last,
                min_val, max_val, avg_val, sum_val, last_val, created_at
            )
            WITH monthly_window AS (
                SELECT
                    sensor_id,
                    CAST(strftime('%s', datetime(bucket_start, 'unixepoch', 'start of year')) AS INTEGER) AS b_start,
                    CAST(strftime('%s', datetime(bucket_start, 'unixepoch', 'start of year', '+1 year')) AS INTEGER) AS b_end,
                    bucket_start,
                    sample_count,
                    value_min,
                    value_max,
                    value_sum,
                    value_sum_sq,
                    value_first,
                    value_last,
                    FIRST_VALUE(value_first) OVER (
                        PARTITION BY sensor_id, strftime('%Y', datetime(bucket_start, 'unixepoch'))
                        ORDER BY bucket_start ASC
                    ) AS f_val,
                    FIRST_VALUE(value_last) OVER (
                        PARTITION BY sensor_id, strftime('%Y', datetime(bucket_start, 'unixepoch'))
                        ORDER BY bucket_start DESC
                    ) AS l_val
                FROM telemetry_rollups
                WHERE tier = 'monthly' AND bucket_start >= ? AND bucket_start < ?
            )
            SELECT
                'yearly' AS tier,
                sensor_id,
                b_start AS bucket_start,
                MAX(b_end) AS bucket_end,
                SUM(sample_count) AS sample_count,
                MIN(value_min) AS value_min,
                MAX(value_max) AS value_max,
                SUM(value_sum) / SUM(sample_count) AS value_avg,
                SUM(value_sum) AS value_sum,
                SUM(value_sum_sq) AS value_sum_sq,
                SQRT(MAX(0.0, (SUM(value_sum_sq) - (SUM(value_sum) * SUM(value_sum)) / SUM(sample_count)) / SUM(sample_count))) AS value_stddev,
                MIN(f_val) AS value_first,
                MAX(l_val) AS value_last,
                MIN(value_min) AS min_val,
                MAX(value_max) AS max_val,
                SUM(value_sum) / SUM(sample_count) AS avg_val,
                SUM(value_sum) AS sum_val,
                MAX(l_val) AS last_val,
                b_start AS created_at
            FROM monthly_window
            GROUP BY sensor_id, b_start
            ON CONFLICT(tier, sensor_id, bucket_start) DO UPDATE SET
                bucket_end = excluded.bucket_end,
                sample_count = excluded.sample_count,
                value_min = excluded.value_min,
                value_max = excluded.value_max,
                value_avg = excluded.value_avg,
                value_sum = excluded.value_sum,
                value_sum_sq = excluded.value_sum_sq,
                value_stddev = excluded.value_stddev,
                value_first = excluded.value_first,
                value_last = excluded.value_last,
                min_val = excluded.min_val,
                max_val = excluded.max_val,
                avg_val = excluded.avg_val,
                sum_val = excluded.sum_val,
                last_val = excluded.last_val;
            """,
            (s_epoch, e_epoch),
        )
        res["buckets_aggregated"] = cursor.rowcount if cursor.rowcount > 0 else 0

    else:
        raise ValueError(f"Неизвестный уровень агрегации: {lvl_str}")

    return res


def _calc_percentiles(values: List[float]) -> Dict[str, float]:
    """Вычисляет статистические перцентили (P50/медиана, P90, P95, P99) для числового ряда."""
    if not values:
        return {"p50": 0.0, "p90": 0.0, "p95": 0.0, "p99": 0.0}
    s = sorted(values)
    n = len(s)
    def _pct(p: float) -> float:
        idx = min(int(n * p), n - 1)
        return round(s[idx], 2)
    return {
        "p50": _pct(0.50),
        "p90": _pct(0.90),
        "p95": _pct(0.95),
        "p99": _pct(0.99),
    }


def _wavg(old_val: float, old_n: int, new_val: float, new_n: int) -> float:
    """Взвешенное по числу замеров среднее двух значений."""
    return round((float(old_val or 0.0) * old_n + float(new_val or 0.0) * new_n) / max(1, old_n + new_n), 2)


def _merge_daily_payload(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """Сливает уже сохранённый суточный профиль приложения с новой порцией тиков того же дня.

    Средние и p50/p90 взвешиваются по числу замеров, максимумы и p95/p99 берутся как максимум
    (приближение: точные перцентили по свёрнутым данным восстановить нельзя). Запуски
    дедуплицируются по instance_id, чтобы повторный проход не удваивал счётчики.

    Args:
        old: Сохранённый payload суточного бакета.
        new: Payload, посчитанный по новой порции тиков.

    Returns:
        Dict[str, Any]: Объединённый payload.
    """
    n_o, n_n = int(old.get("sample_count") or 0), int(new.get("sample_count") or 0)
    merged = dict(new)
    merged["sample_count"] = n_o + n_n
    merged["period_start"] = old.get("period_start") or new.get("period_start")

    for key, avg_keys, max_keys in (("cpu", ("avg", "p50", "p90"), ("max", "p95", "p99")),
                                    ("memory_mb", ("avg", "p50", "p90"), ("max", "p95"))):
        o, n = old.get(key) or {}, new.get(key) or {}
        m = {"min": min(o.get("min", n.get("min", 0.0)), n.get("min", 0.0))}
        m.update({k: _wavg(o.get(k, 0.0), n_o, n.get(k, 0.0), n_n) for k in avg_keys})
        m.update({k: max(o.get(k, 0.0), n.get(k, 0.0)) for k in max_keys})
        merged[key] = m

    o_io, n_io = old.get("io") or {}, new.get("io") or {}
    merged["io"] = {
        "total_read_mb": round(float(o_io.get("total_read_mb") or 0.0) + float(n_io.get("total_read_mb") or 0.0), 2),
        "total_write_mb": round(float(o_io.get("total_write_mb") or 0.0) + float(n_io.get("total_write_mb") or 0.0), 2),
        "peak_read_kb_sec": max(o_io.get("peak_read_kb_sec", 0.0), n_io.get("peak_read_kb_sec", 0.0)),
        "peak_write_kb_sec": max(o_io.get("peak_write_kb_sec", 0.0), n_io.get("peak_write_kb_sec", 0.0)),
    }

    hours: Dict[str, Dict[str, Any]] = {}
    for src in (old.get("hourly_distribution") or {}, new.get("hourly_distribution") or {}):
        for hr, d in src.items():
            cur = hours.get(hr)
            if cur is None:
                hours[hr] = dict(d)
            else:
                cur["avg_cpu_percent"] = _wavg(cur["avg_cpu_percent"], cur["samples"], d["avg_cpu_percent"], d["samples"])
                cur["avg_memory_mb"] = _wavg(cur["avg_memory_mb"], cur["samples"], d["avg_memory_mb"], d["samples"])
                cur["samples"] += d["samples"]
    merged["hourly_distribution"] = dict(sorted(hours.items()))

    instances = {**(old.get("instances") or {}), **(new.get("instances") or {})}
    merged["instances"] = instances
    o_lc, n_lc = old.get("lifecycle") or {}, new.get("lifecycle") or {}
    overlap = bool(set(old.get("instances") or {}) & set(new.get("instances") or {}))
    cpu_time = max if overlap else (lambda a, b: a + b)
    merged["launch_count"] = max(1, len(instances)) if instances else max(old.get("launch_count", 1), new.get("launch_count", 1))
    merged["lifecycle"] = {
        "clean_exits": sum(1 for code in instances.values() if code == 0),
        "crashes": sum(1 for code in instances.values() if code is not None and code != 0),
        "avg_lifetime_sec": _wavg(o_lc.get("avg_lifetime_sec", 0.0), n_o, n_lc.get("avg_lifetime_sec", 0.0), n_n),
        "total_cpu_time_sec": round(cpu_time(float(o_lc.get("total_cpu_time_sec") or 0.0), float(n_lc.get("total_cpu_time_sec") or 0.0)), 2),
    }

    merged["avg_cpu_percent"] = merged["cpu"]["avg"]
    merged["max_cpu_percent"] = merged["cpu"]["max"]
    merged["avg_memory_mb"] = merged["memory_mb"]["avg"]
    merged["max_memory_mb"] = merged["memory_mb"]["max"]
    return merged


def aggregate_processes_daily(
    conn: sqlite3.Connection,
    cutoff_seconds: float = 86400.0,
    outlier_cpu_threshold: float = 30.0,
    tick_seconds: float = 5.0,
) -> Dict[str, int]:
    """Сворачивает детальные сэмплы процессов старше суток (24ч) в суточную статистику proc_daily с расширенным профилем (перцентили, почасовая гистограмма, ввод-вывод, аварии)."""
    cursor = conn.cursor()
    now_epoch = time.time()
    cutoff_epoch = now_epoch - float(cutoff_seconds)

    query = """
    SELECT
        p.id,
        p.snapshot_id,
        p.created_at,
        p.timestamp,
        p.pid,
        p.name,
        p.cpu_percent,
        p.memory_mb,
        p.read_bytes_sec,
        p.write_bytes_sec,
        p.instance_id,
        COALESCE(l.cmdline, p.cmdline, p.name) as cmdline,
        COALESCE(l.parent_name, p.parent_name, 'Unknown') as parent_name,
        COALESCE(l.initiator_type, 'background') as initiator_type,
        l.exit_code,
        l.lifetime_sec,
        l.cpu_time_total_sec,
        l.io_read_bytes,
        l.io_write_bytes
    FROM process_snapshots p
    LEFT JOIN process_lifecycle_sessions l ON p.instance_id = l.instance_id
    WHERE p.sample_type = 'snapshot' AND p.created_at < ?
    ORDER BY p.name, p.created_at ASC
    """
    cursor.execute(query, (cutoff_epoch,))
    raw_rows = cursor.fetchall()
    if not raw_rows:
        return {"rollups_created": 0, "outliers_saved": 0, "raw_deleted": 0}

    grouped = defaultdict(list)
    raw_ids = []
    outlier_rows = []

    for r in raw_rows:
        raw_ids.append(r["id"])
        cpu_val = float(r["cpu_percent"] or 0.0)
        if cpu_val >= outlier_cpu_threshold:
            outlier_rows.append((
                r["snapshot_id"],
                r["timestamp"],
                r["created_at"],
                r["pid"],
                r["name"],
                cpu_val,
                float(r["memory_mb"] or 0.0),
                r["instance_id"],
                json.dumps({"details": f"Outlier CPU={cpu_val:.1f}%", "cmdline": r["cmdline"]}, ensure_ascii=False),
            ))

        ts_str = str(r["timestamp"] or "")
        day_str = ts_str[:10] if len(ts_str) >= 10 else datetime.fromtimestamp(float(r["created_at"]), tz=timezone.utc).strftime("%Y-%m-%d")
        key = (day_str, r["name"], r["cmdline"], r["parent_name"])
        grouped[key].append(r)

    if outlier_rows:
        cursor.executemany(
            """
            INSERT INTO process_snapshots (
                snapshot_id, timestamp, created_at, pid, name,
                cpu_percent, memory_mb, instance_id, sample_type, is_outlier, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'outlier', 1, ?)
            """,
            outlier_rows,
        )

    rollup_rows = []
    for (day_str, p_name, cmdline, parent_name), procs in grouped.items():
        cnt = len(procs)
        cpus = [float(p["cpu_percent"] or 0.0) for p in procs]
        mems = [float(p["memory_mb"] or 0.0) for p in procs]
        read_rates = [float(p["read_bytes_sec"] or 0.0) for p in procs]
        write_rates = [float(p["write_bytes_sec"] or 0.0) for p in procs]

        # 1. Перцентили CPU и RAM
        cpu_pcts = _calc_percentiles(cpus)
        ram_pcts = _calc_percentiles(mems)

        # 2. Почасовая гистограмма активности (Time-of-day hourly distribution, 00..23)
        hourly_acc = defaultdict(lambda: {"samples": 0, "cpu_sum": 0.0, "ram_sum": 0.0})
        for p in procs:
            ts_val = str(p["timestamp"] or "")
            hr_k = ts_val[11:13] if len(ts_val) >= 13 and ts_val[11:13].isdigit() else datetime.fromtimestamp(float(p["created_at"]), tz=timezone.utc).strftime("%H")
            acc = hourly_acc[hr_k]
            acc["samples"] += 1
            acc["cpu_sum"] += float(p["cpu_percent"] or 0.0)
            acc["ram_sum"] += float(p["memory_mb"] or 0.0)

        hourly_distribution = {
            hr: {
                "samples": d["samples"],
                "avg_cpu_percent": round(d["cpu_sum"] / max(1, d["samples"]), 2),
                "avg_memory_mb": round(d["ram_sum"] / max(1, d["samples"]), 2),
            }
            for hr, d in sorted(hourly_acc.items())
        }

        # 3. Ввод-вывод (диск/сеть)
        peak_read_bps = max(read_rates) if read_rates else 0.0
        avg_read_bps = sum(read_rates) / cnt if cnt > 0 else 0.0
        peak_write_bps = max(write_rates) if write_rates else 0.0
        avg_write_bps = sum(write_rates) / cnt if cnt > 0 else 0.0
        total_read_mb = round(sum(read_rates) * tick_seconds / (1024.0 * 1024.0), 2)
        total_write_mb = round(sum(write_rates) * tick_seconds / (1024.0 * 1024.0), 2)

        # 4. Анализ сессий, запусков, кодов возврата и аварий
        inst_map = {}
        for p in procs:
            iid = p["instance_id"]
            if iid and iid not in inst_map:
                inst_map[iid] = p

        clean_exits = sum(1 for inst in inst_map.values() if inst["exit_code"] == 0)
        crashes = sum(1 for inst in inst_map.values() if inst["exit_code"] is not None and inst["exit_code"] != 0)
        durations = [float(inst["lifetime_sec"]) for inst in inst_map.values() if inst["lifetime_sec"] is not None and float(inst["lifetime_sec"]) > 0]
        avg_lifetime = round(sum(durations) / len(durations), 1) if durations else 0.0
        total_cpu_time = round(sum(float(inst["cpu_time_total_sec"] or 0.0) for inst in inst_map.values()), 2)

        try:
            b_start = datetime.strptime(day_str, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()
        except Exception:
            b_start = float(procs[0]["created_at"])
        b_end = b_start + 86400.0

        p_start_ts = str(procs[0]["timestamp"])
        p_end_ts = str(procs[-1]["timestamp"])
        p_start_epoch = float(procs[0]["created_at"])
        p_end_epoch = float(procs[-1]["created_at"])

        sig_hash = hashlib.sha256(f"{cmdline}|{parent_name}".encode("utf-8", "ignore")).hexdigest()[:16]
        sensor_id = f"proc:{p_name}:{sig_hash}"

        payload = {
            "name": p_name,
            "cmdline": cmdline,
            "parent_name": parent_name,
            "date": day_str,
            "launch_count": max(1, len(inst_map) if inst_map else 1),
            "instances": {str(iid): inst["exit_code"] for iid, inst in inst_map.items()},
            "sample_count": cnt,
            "cpu": {
                "min": round(min(cpus), 2),
                "avg": round(sum(cpus) / cnt, 2),
                "max": round(max(cpus), 2),
                "p50": cpu_pcts["p50"],
                "p90": cpu_pcts["p90"],
                "p95": cpu_pcts["p95"],
                "p99": cpu_pcts["p99"],
            },
            "memory_mb": {
                "min": round(min(mems), 2),
                "avg": round(sum(mems) / cnt, 2),
                "max": round(max(mems), 2),
                "p50": ram_pcts["p50"],
                "p90": ram_pcts["p90"],
                "p95": ram_pcts["p95"],
            },
            "io": {
                "total_read_mb": total_read_mb,
                "total_write_mb": total_write_mb,
                "peak_read_kb_sec": round(peak_read_bps / 1024.0, 1),
                "peak_write_kb_sec": round(peak_write_bps / 1024.0, 1),
            },
            "lifecycle": {
                "clean_exits": clean_exits,
                "crashes": crashes,
                "avg_lifetime_sec": avg_lifetime,
                "total_cpu_time_sec": total_cpu_time,
            },
            "hourly_distribution": hourly_distribution,
            "avg_cpu_percent": round(sum(cpus) / cnt, 2),
            "max_cpu_percent": round(max(cpus), 2),
            "avg_memory_mb": round(sum(mems) / cnt, 2),
            "max_memory_mb": round(max(mems), 2),
            "period_start": p_start_ts,
            "period_end": p_end_ts,
        }

        prev = cursor.execute(
            "SELECT payload_json, period_start, period_start_epoch, disk_read_bps_avg, disk_read_bps_max, "
            "disk_write_bps_avg, disk_write_bps_max, cpu_p95, sample_count FROM telemetry_rollups "
            "WHERE tier = 'proc_daily' AND sensor_id = ? AND bucket_start = ?",
            (sensor_id, b_start),
        ).fetchone()
        if prev and prev["payload_json"]:
            n_old = int(prev["sample_count"] or 0)
            payload = _merge_daily_payload(json.loads(prev["payload_json"]), payload)
            avg_read_bps = _wavg(prev["disk_read_bps_avg"], n_old, avg_read_bps, cnt)
            avg_write_bps = _wavg(prev["disk_write_bps_avg"], n_old, avg_write_bps, cnt)
            peak_read_bps = max(float(prev["disk_read_bps_max"] or 0.0), peak_read_bps)
            peak_write_bps = max(float(prev["disk_write_bps_max"] or 0.0), peak_write_bps)
            cpu_pcts["p95"] = max(float(prev["cpu_p95"] or 0.0), cpu_pcts["p95"])
            p_start_ts = prev["period_start"] or p_start_ts
            p_start_epoch = float(prev["period_start_epoch"] or p_start_epoch)
            cnt = payload["sample_count"]

        rollup_rows.append((
            sensor_id,
            b_start,
            b_end,
            p_start_ts,
            p_end_ts,
            p_start_epoch,
            p_end_epoch,
            cnt,
            payload["avg_cpu_percent"],
            payload["max_cpu_percent"],
            cpu_pcts["p95"],
            payload["avg_memory_mb"],
            payload["max_memory_mb"],
            round(avg_read_bps, 1),
            round(peak_read_bps, 1),
            round(avg_write_bps, 1),
            round(peak_write_bps, 1),
            json.dumps(payload, ensure_ascii=False),
            now_epoch,
        ))

    if rollup_rows:
        cursor.executemany(
            """
            INSERT OR REPLACE INTO telemetry_rollups (
                tier, sensor_id, bucket_start, bucket_end, period_start, period_end,
                period_start_epoch, period_end_epoch, sample_count,
                cpu_avg, cpu_max, cpu_p95, ram_avg, ram_max,
                disk_read_bps_avg, disk_read_bps_max, disk_write_bps_avg, disk_write_bps_max,
                payload_json, created_at
            ) VALUES ('proc_daily', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rollup_rows,
        )

    cursor.execute(
        f"DELETE FROM process_snapshots WHERE id IN ({','.join(['?'] * len(raw_ids))})",
        raw_ids,
    )

    return {
        "rollups_created": len(rollup_rows),
        "outliers_saved": len(outlier_rows),
        "raw_deleted": len(raw_ids),
    }


def aggregate_processes_weekly(conn: sqlite3.Connection, window_days: int = 7) -> Dict[str, int]:
    """Агрегирует суточные бакеты proc_daily за последние window_days дней в tier='proc_weekly'."""
    cursor = conn.cursor()
    now_epoch = time.time()
    min_epoch = now_epoch - (float(window_days) * 86400.0)

    cursor.execute(
        """
        SELECT sensor_id, bucket_start, sample_count, cpu_avg, cpu_max, ram_avg, ram_max, payload_json
        FROM telemetry_rollups
        WHERE tier = 'proc_daily' AND bucket_start >= ?
        ORDER BY sensor_id, bucket_start ASC
        """,
        (min_epoch,),
    )
    rows = cursor.fetchall()
    if not rows:
        return {"weekly_created": 0}

    grouped = defaultdict(list)
    for r in rows:
        grouped[r["sensor_id"]].append(r)

    weekly_rows = []
    for sensor_id, items in grouped.items():
        total_samples = sum(int(it["sample_count"] or 1) for it in items)
        if total_samples <= 0:
            continue
        weighted_cpu = sum(float(it["cpu_avg"] or 0.0) * int(it["sample_count"] or 1) for it in items) / total_samples
        weighted_mem = sum(float(it["ram_avg"] or 0.0) * int(it["sample_count"] or 1) for it in items) / total_samples
        max_cpu = max(float(it["cpu_max"] or 0.0) for it in items)
        max_mem = max(float(it["ram_max"] or 0.0) for it in items)
        total_launches = 0
        total_clean_exits = 0
        total_crashes = 0
        total_read_mb = 0.0
        total_write_mb = 0.0
        total_cpu_sec = 0.0
        cmdline = ""
        p_name = ""
        parent_name = ""
        days_history = []
        p95_list = []
        for it in items:
            pl = json.loads(it["payload_json"]) if it["payload_json"] else {}
            total_launches += int(pl.get("launch_count") or 1)
            cmdline = pl.get("cmdline") or cmdline
            p_name = pl.get("name") or p_name
            parent_name = pl.get("parent_name") or parent_name

            io_info = pl.get("io") or {}
            total_read_mb += float(io_info.get("total_read_mb") or 0.0)
            total_write_mb += float(io_info.get("total_write_mb") or 0.0)

            lc = pl.get("lifecycle") or {}
            total_clean_exits += int(lc.get("clean_exits") or 0)
            total_crashes += int(lc.get("crashes") or 0)
            total_cpu_sec += float(lc.get("total_cpu_time_sec") or 0.0)

            cpu_info = pl.get("cpu") or {}
            if "p95" in cpu_info:
                p95_list.append(float(cpu_info["p95"]))

            days_history.append({
                "date": pl.get("date"),
                "launches": pl.get("launch_count", 1),
                "avg_cpu": pl.get("avg_cpu_percent"),
                "max_cpu": pl.get("max_cpu_percent"),
                "p95_cpu": cpu_info.get("p95"),
                "avg_ram": pl.get("avg_memory_mb"),
                "read_mb": io_info.get("total_read_mb", 0.0),
                "write_mb": io_info.get("total_write_mb", 0.0),
                "crashes": lc.get("crashes", 0),
                "hourly_distribution": pl.get("hourly_distribution", {}),
            })

        b_start = int(now_epoch // 604800) * 604800.0
        b_end = b_start + 604800.0
        overall_p95 = max(p95_list) if p95_list else round(weighted_cpu * 1.5, 2)

        payload = {
            "name": p_name,
            "cmdline": cmdline,
            "parent_name": parent_name,
            "total_launches": total_launches,
            "days_active": len(items),
            "sample_count": total_samples,
            "avg_cpu_percent": round(weighted_cpu, 2),
            "max_cpu_percent": round(max_cpu, 2),
            "p95_cpu_percent": round(overall_p95, 2),
            "avg_memory_mb": round(weighted_mem, 2),
            "max_memory_mb": round(max_mem, 2),
            "io": {
                "total_read_mb": round(total_read_mb, 2),
                "total_write_mb": round(total_write_mb, 2),
            },
            "lifecycle": {
                "clean_exits": total_clean_exits,
                "crashes": total_crashes,
                "total_cpu_time_sec": round(total_cpu_sec, 2),
            },
            "daily_history": days_history,
        }

        weekly_rows.append((
            sensor_id,
            b_start,
            b_end,
            total_samples,
            payload["avg_cpu_percent"],
            payload["max_cpu_percent"],
            round(overall_p95, 2),
            payload["avg_memory_mb"],
            payload["max_memory_mb"],
            json.dumps(payload, ensure_ascii=False),
            now_epoch,
        ))

    if weekly_rows:
        cursor.executemany(
            """
            INSERT OR REPLACE INTO telemetry_rollups (
                tier, sensor_id, bucket_start, bucket_end, sample_count,
                cpu_avg, cpu_max, cpu_p95, ram_avg, ram_max, payload_json, created_at
            ) VALUES ('proc_weekly', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            weekly_rows,
        )

    return {"weekly_created": len(weekly_rows)}


def aggregate_processes_all_time(conn: sqlite3.Connection) -> Dict[str, int]:
    """Обновляет накопительную пожизненную статистику программы за всё время наблюдений (tier='proc_all_time')."""
    cursor = conn.cursor()
    now_epoch = time.time()

    # Профиль производный от proc_daily: удаляем, чтобы после очистки по сроку хранения не оставались «хвосты»
    cursor.execute("DELETE FROM telemetry_rollups WHERE tier = 'proc_all_time'")
    cursor.execute(
        """
        SELECT sensor_id, sample_count, cpu_avg, cpu_max, ram_avg, ram_max, payload_json
        FROM telemetry_rollups
        WHERE tier = 'proc_daily'
        ORDER BY sensor_id, bucket_start ASC
        """
    )
    rows = cursor.fetchall()
    if not rows:
        return {"all_time_created": 0}

    grouped = defaultdict(list)
    for r in rows:
        grouped[r["sensor_id"]].append(r)

    all_rows = []
    for sensor_id, items in grouped.items():
        total_samples = sum(int(it["sample_count"] or 1) for it in items)
        if total_samples <= 0:
            continue
        weighted_cpu = sum(float(it["cpu_avg"] or 0.0) * int(it["sample_count"] or 1) for it in items) / total_samples
        weighted_mem = sum(float(it["ram_avg"] or 0.0) * int(it["sample_count"] or 1) for it in items) / total_samples
        max_cpu = max(float(it["cpu_max"] or 0.0) for it in items)
        max_mem = max(float(it["ram_max"] or 0.0) for it in items)
        total_launches = 0
        total_clean_exits = 0
        total_crashes = 0
        total_read_mb = 0.0
        total_write_mb = 0.0
        total_cpu_sec = 0.0
        cmdline = ""
        p_name = ""
        parent_name = ""
        dates = []
        p95_list = []
        for it in items:
            pl = json.loads(it["payload_json"]) if it["payload_json"] else {}
            total_launches += int(pl.get("launch_count") or 1)
            cmdline = pl.get("cmdline") or cmdline
            p_name = pl.get("name") or p_name
            parent_name = pl.get("parent_name") or parent_name

            io_info = pl.get("io") or {}
            total_read_mb += float(io_info.get("total_read_mb") or 0.0)
            total_write_mb += float(io_info.get("total_write_mb") or 0.0)

            lc = pl.get("lifecycle") or {}
            total_clean_exits += int(lc.get("clean_exits") or 0)
            total_crashes += int(lc.get("crashes") or 0)
            total_cpu_sec += float(lc.get("total_cpu_time_sec") or 0.0)

            cpu_info = pl.get("cpu") or {}
            if "p95" in cpu_info:
                p95_list.append(float(cpu_info["p95"]))

            if pl.get("date"):
                dates.append(pl["date"])

        overall_p95 = max(p95_list) if p95_list else round(weighted_cpu * 1.5, 2)

        payload = {
            "name": p_name,
            "cmdline": cmdline,
            "parent_name": parent_name,
            "total_launches": total_launches,
            "total_clean_exits": total_clean_exits,
            "total_crashes": total_crashes,
            "total_days_observed": len(set(dates)),
            "first_observed": min(dates) if dates else "unknown",
            "last_observed": max(dates) if dates else "unknown",
            "sample_count": total_samples,
            "avg_cpu_percent": round(weighted_cpu, 2),
            "record_max_cpu_percent": round(max_cpu, 2),
            "p95_cpu_percent": round(overall_p95, 2),
            "avg_memory_mb": round(weighted_mem, 2),
            "record_max_memory_mb": round(max_mem, 2),
            "io": {
                "total_read_mb": round(total_read_mb, 2),
                "total_write_mb": round(total_write_mb, 2),
            },
            "lifecycle": {
                "total_cpu_time_hours": round(total_cpu_sec / 3600.0, 3),
                "total_cpu_time_sec": round(total_cpu_sec, 2),
            },
        }

        all_rows.append((
            sensor_id,
            0.0,
            total_samples,
            payload["avg_cpu_percent"],
            payload["record_max_cpu_percent"],
            round(overall_p95, 2),
            payload["avg_memory_mb"],
            payload["record_max_memory_mb"],
            json.dumps(payload, ensure_ascii=False),
            now_epoch,
        ))

    if all_rows:
        cursor.executemany(
            """
            INSERT OR REPLACE INTO telemetry_rollups (
                tier, sensor_id, bucket_start, sample_count,
                cpu_avg, cpu_max, cpu_p95, ram_avg, ram_max, payload_json, created_at
            ) VALUES ('proc_all_time', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            all_rows,
        )

    return {"all_time_created": len(all_rows)}


class TelemetrySqlAggregator:
    """Управляет вызовами SQL-агрегации и каскадным выполнением цепочки агрегаторов."""

    def __init__(self, connection_manager: TelemetryConnectionManager) -> None:
        """Инициализирует SQL-агрегатор телеметрии.

        Args:
            connection_manager: Менеджер подключений SQLite.
        """
        self._cm = connection_manager
        self._scheduler_timer: Optional[threading.Timer] = None
        self._scheduler_interval: float = 300.0
        self._scheduler_running: bool = False

    def start_background_scheduler(self, interval_seconds: float = 300.0) -> None:
        """Запускает фоновый регламентный планировщик агрегации."""
        if self._cm.read_only:
            return
        self.stop_background_scheduler()
        self._scheduler_interval = max(10.0, float(interval_seconds))
        self._scheduler_running = True
        self._schedule_next_run()
        logger.info(f"Запущен фоновый регламентный планировщик агрегации (квант: {self._scheduler_interval}с)")

    def stop_background_scheduler(self) -> None:
        """Останавливает фоновый регламентный планировщик агрегации."""
        self._scheduler_running = False
        if self._scheduler_timer:
            try:
                self._scheduler_timer.cancel()
            except Exception:
                pass
            self._scheduler_timer = None

    def _schedule_next_run(self) -> None:
        if not self._scheduler_running or self._cm.read_only:
            return
        self._scheduler_timer = threading.Timer(self._scheduler_interval, self._on_scheduler_tick)
        self._scheduler_timer.daemon = True
        self._scheduler_timer.start()

    def _on_scheduler_tick(self) -> None:
        if not self._scheduler_running or self._cm.read_only:
            return
        try:
            self.run_pipeline()
        except Exception as ex:
            logger.debug(f"Ошибка регламентной фоновой агрегации: {ex}")
        finally:
            self._schedule_next_run()

    def aggregate(
        self,
        level: Union[AggregationLevel, str],
        start_epoch: Optional[float] = None,
        end_epoch: Optional[float] = None,
        detect_spikes: bool = True,
    ) -> Dict[str, Any]:
        """Запускает агрегацию указанного уровня в транзакции."""
        if self._cm.read_only:
            return {"level": str(level), "buckets_aggregated": 0, "spikes_recorded": 0, "read_only": True}

        with self._cm.lock, self._cm.get_connection() as conn:
            result = sensors_aggregate(
                conn=conn,
                level=level,
                start_epoch=start_epoch,
                end_epoch=end_epoch,
                detect_spikes=detect_spikes,
            )
            conn.commit()
            return result

    def aggregate_hourly(self, start_epoch: Optional[float] = None, end_epoch: Optional[float] = None, detect_spikes: bool = True) -> Dict[str, Any]:
        """Выполняет почасовую агрегацию сырых замеров."""
        return self.aggregate(AggregationLevel.HOURLY, start_epoch=start_epoch, end_epoch=end_epoch, detect_spikes=detect_spikes)

    def aggregate_daily(self, start_epoch: Optional[float] = None, end_epoch: Optional[float] = None) -> Dict[str, Any]:
        """Выполняет суточную агрегацию из почасовых бакетов."""
        return self.aggregate(AggregationLevel.DAILY, start_epoch=start_epoch, end_epoch=end_epoch)

    def aggregate_weekly(self, start_epoch: Optional[float] = None, end_epoch: Optional[float] = None) -> Dict[str, Any]:
        """Выполняет недельную агрегацию из суточных бакетов."""
        return self.aggregate(AggregationLevel.WEEKLY, start_epoch=start_epoch, end_epoch=end_epoch)

    def aggregate_monthly(self, start_epoch: Optional[float] = None, end_epoch: Optional[float] = None) -> Dict[str, Any]:
        """Выполняет месячную агрегацию из суточных бакетов."""
        return self.aggregate(AggregationLevel.MONTHLY, start_epoch=start_epoch, end_epoch=end_epoch)

    def aggregate_yearly(self, start_epoch: Optional[float] = None, end_epoch: Optional[float] = None) -> Dict[str, Any]:
        """Выполняет годовую агрегацию из месячных бакетов."""
        return self.aggregate(AggregationLevel.YEARLY, start_epoch=start_epoch, end_epoch=end_epoch)

    def aggregate_processes_daily(self, cutoff_seconds: float = 86400.0, outlier_cpu_threshold: float = 30.0) -> Dict[str, int]:
        """Сворачивает детальные сэмплы процессов старше суток (24ч) в суточную статистику proc_daily."""
        if self._cm.read_only:
            return {"rollups_created": 0, "outliers_saved": 0, "raw_deleted": 0}
        with self._cm.lock, self._cm.get_connection() as conn:
            res = aggregate_processes_daily(conn, cutoff_seconds=cutoff_seconds, outlier_cpu_threshold=outlier_cpu_threshold)
            conn.commit()
            return res

    def aggregate_processes_weekly(self, window_days: int = 7) -> Dict[str, int]:
        """Агрегирует суточные бакеты proc_daily за последние window_days дней в tier='proc_weekly'."""
        if self._cm.read_only:
            return {"weekly_created": 0}
        with self._cm.lock, self._cm.get_connection() as conn:
            res = aggregate_processes_weekly(conn, window_days=window_days)
            conn.commit()
            return res

    def aggregate_processes_all_time(self) -> Dict[str, int]:
        """Обновляет накопительную пожизненную статистику программы за всё время наблюдений (tier='proc_all_time')."""
        if self._cm.read_only:
            return {"all_time_created": 0}
        with self._cm.lock, self._cm.get_connection() as conn:
            res = aggregate_processes_all_time(conn)
            conn.commit()
            return res

    def run_pipeline(
        self,
        start_epoch: Optional[float] = None,
        end_epoch: Optional[float] = None,
        detect_spikes: bool = True,
        cutoff_process_seconds: float = 86400.0,
        tick_seconds: float = 5.0,
    ) -> Dict[str, Any]:
        """Выполняет полный каскад агрегации: сенсоры (raw -> hourly -> daily -> weekly -> monthly -> yearly) и процессы (тики 24ч -> proc_daily -> proc_weekly -> proc_all_time) в одной транзакции."""
        if self._cm.read_only:
            return {"read_only": True}

        with self._cm.lock, self._cm.get_connection() as conn:
            h_res = sensors_aggregate(conn, AggregationLevel.HOURLY, start_epoch, end_epoch, detect_spikes)
            d_res = sensors_aggregate(conn, AggregationLevel.DAILY, start_epoch, end_epoch, False)
            w_res = sensors_aggregate(conn, AggregationLevel.WEEKLY, start_epoch, end_epoch, False)
            m_res = sensors_aggregate(conn, AggregationLevel.MONTHLY, start_epoch, end_epoch, False)
            y_res = sensors_aggregate(conn, AggregationLevel.YEARLY, start_epoch, end_epoch, False)

            # Агрегация процессов: тики старше 24ч сворачиваются в суточные, недельные и бессрочные профили
            proc_d_res = aggregate_processes_daily(conn, cutoff_seconds=cutoff_process_seconds, tick_seconds=tick_seconds)
            proc_w_res = aggregate_processes_weekly(conn, window_days=7)
            proc_all_res = aggregate_processes_all_time(conn)

            conn.commit()

            return {
                "hourly": h_res,
                "daily": d_res,
                "weekly": w_res,
                "monthly": m_res,
                "yearly": y_res,
                "proc_daily": proc_d_res,
                "proc_weekly": proc_w_res,
                "proc_all_time": proc_all_res,
            }

