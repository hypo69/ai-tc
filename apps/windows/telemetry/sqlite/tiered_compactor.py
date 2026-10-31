# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry Sqlite - Tiered Compactor
# =============================================================================
# Description:
#   Каскадное многоуровневое усреднение и компактификация снимков телеметрии:
#   - 5с снимки накапливаются в течение 30 секунд.
#   - Каждые 30 секунд: пересчет средних значений в бакет '30s', удаление сырых 5с строк.
#   - Данные старше 3 минут: усреднение бакетов '30s' в '3m', удаление строк '30s'.
#   - Данные старше 10 минут: усреднение бакетов '3m' в '10m', удаление строк '3m'.
#   - Данные старше 36 часов: усреднение бакетов '10m' в '36h', удаление строк '10m'.
#   - При включенном thorough_mode (режим тщательного сбора) усреднение и удаление отключаются.
#
# Usage Examples:
#   Python API:
#     from apps.windows.telemetry.sqlite.tiered_compactor import TelemetryTieredCompactor
#
#     compactor = TelemetryTieredCompactor(connection_manager)
#     stats = compactor.run_tiered_compaction(thorough_mode=False)
#
# File: tiered_compactor.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry.sqlite
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 16:35:00
# =============================================================================

from __future__ import annotations

"""Модуль каскадного многоуровневого усреднения и компактификации снимков телеметрии."""

import json
import sqlite3
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from .connection import TelemetryConnectionManager
from .delta_tracker import SNAPSHOT_FIELDS, VOLATILE_FIELDS

try:
    from logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class TelemetryTieredCompactor:
    """Многоуровневый компактор временных рядов телеметрии (5s -> 30s -> 3m -> 10m -> 36h)."""

    def __init__(self, connection_manager: TelemetryConnectionManager) -> None:
        """Инициализирует компактор с менеджером подключений.

        Args:
            connection_manager: Менеджер соединений SQLite.
        """
        self._cm = connection_manager

    @staticmethod
    def _locf_anchor_ids(cursor: sqlite3.Cursor) -> Set[int]:
        """Возвращает ID снимков, хранящих последнее известное значение статических полей."""
        fields = [f for f in SNAPSHOT_FIELDS if f not in VOLATILE_FIELDS] + ["raw_json"]
        cols = ", ".join(f"MAX(CASE WHEN {f} IS NOT NULL AND {f} != '' THEN id END)" for f in fields)
        row = cursor.execute(f"SELECT {cols} FROM system_snapshots").fetchone()
        return {i for i in (row or []) if i is not None}

    def run_tiered_compaction(
        self,
        thorough_mode: bool = False,
        now_epoch: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Запускает полный цикл каскадного усреднения и очистки устаревших строк.

        Если thorough_mode=True, очистка и сжатие не выполняются (сохраняются все точки).

        Args:
            thorough_mode: Флаг режима тщательного сбора (True отключает усреднение).
            now_epoch: Текущая эпоха в секундах (для тестов).

        Returns:
            Dict[str, Any]: Статистика созданных бакетов и удаленных строк.
        """
        if thorough_mode:
            logger.debug("[TieredCompactor] Режим тщательного сбора активен: усреднение и удаление пропущены.")
            return {"skipped": True, "reason": "thorough_mode"}

        if self._cm.read_only:
            return {"skipped": True, "reason": "read_only"}

        now = float(now_epoch if now_epoch is not None else time.time())
        res: Dict[str, Any] = {
            "skipped": False,
            "step_30s": self.step_30s_rollup(now),
            "step_3m": self.step_3m_rollup(now),
            "step_10m": self.step_10m_rollup(now),
            "step_36h": self.step_36h_rollup(now),
        }
        return res

    def step_30s_rollup(self, now_epoch: float) -> Dict[str, int]:
        """Усредняет пятисекундные снимки старше 30 секунд в бакеты '30s' и удаляет сырые строки.

        Args:
            now_epoch: Текущее время Unix epoch.

        Returns:
            Dict[str, int]: Количество созданных бакетов и удаленных сырых снимков.
        """
        cutoff_epoch = now_epoch - 30.0
        stats = {"rollups_created": 0, "snapshots_deleted": 0, "procs_deleted": 0, "sensors_deleted": 0}

        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            anchors = self._locf_anchor_ids(cursor)

            # Выбираем завершенные 30-секундные бакеты системных снимков
            cursor.execute(
                """
                SELECT
                    CAST(created_at / 30 AS INTEGER) * 30 AS b_start,
                    COUNT(*) AS cnt,
                    AVG(cpu_total_percent) AS cpu_avg,
                    MAX(cpu_total_percent) AS cpu_max,
                    AVG(memory_percent) AS ram_avg,
                    MAX(memory_percent) AS ram_max,
                    AVG(memory_used_gb) AS ram_used_avg,
                    AVG(disk_read_bytes_sec) AS disk_r_avg,
                    AVG(disk_write_bytes_sec) AS disk_w_avg,
                    AVG(network_sent_bytes_sec) AS net_tx_avg,
                    AVG(network_recv_bytes_sec) AS net_rx_avg,
                    MIN(timestamp) AS p_start,
                    MAX(timestamp) AS p_end
                FROM system_snapshots
                WHERE created_at < ?
                GROUP BY b_start
                HAVING cnt > 0
                ORDER BY b_start ASC
                """,
                (cutoff_epoch,),
            )
            buckets = cursor.fetchall()
            if not buckets:
                return stats

            for b in buckets:
                b_start = float(b[0])
                b_end = b_start + 30.0
                cnt = int(b[1])

                cursor.execute(
                    """
                    INSERT INTO telemetry_rollups (
                        tier, sensor_id, bucket_start, bucket_end, period_start, period_end,
                        period_start_epoch, period_end_epoch, sample_count,
                        cpu_avg, cpu_max, ram_avg, ram_max, ram_used_gb_avg,
                        disk_read_bps_avg, disk_write_bps_avg, net_sent_bps_avg, net_recv_bps_avg,
                        created_at
                    ) VALUES (
                        '30s', '__system__', ?, ?, ?, ?,
                        ?, ?, ?,
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?,
                        ?
                    )
                    ON CONFLICT(tier, sensor_id, bucket_start) DO UPDATE SET
                        bucket_end = excluded.bucket_end,
                        period_end = excluded.period_end,
                        period_end_epoch = excluded.period_end_epoch,
                        sample_count = excluded.sample_count,
                        cpu_avg = excluded.cpu_avg,
                        cpu_max = excluded.cpu_max,
                        ram_avg = excluded.ram_avg,
                        ram_max = excluded.ram_max,
                        ram_used_gb_avg = excluded.ram_used_gb_avg,
                        disk_read_bps_avg = excluded.disk_read_bps_avg,
                        disk_write_bps_avg = excluded.disk_write_bps_avg,
                        net_sent_bps_avg = excluded.net_sent_bps_avg,
                        net_recv_bps_avg = excluded.net_recv_bps_avg,
                        created_at = excluded.created_at;
                    """,
                    (
                        b_start, b_end, b[11], b[12],
                        b_start, b_end, cnt,
                        round(float(b[2] or 0.0), 2), round(float(b[3] or 0.0), 2),
                        round(float(b[4] or 0.0), 2), round(float(b[5] or 0.0), 2),
                        round(float(b[6] or 0.0), 2),
                        round(float(b[7] or 0.0), 2), round(float(b[8] or 0.0), 2),
                        round(float(b[9] or 0.0), 2), round(float(b[10] or 0.0), 2),
                        b_end,
                    ),
                )
                stats["rollups_created"] += 1

                # Усреднение сенсоров sensor_polls в том же 30с окне
                cursor.execute(
                    """
                    INSERT INTO telemetry_rollups (
                        tier, sensor_id, bucket_start, bucket_end, sample_count,
                        value_min, value_max, value_avg, value_sum, created_at
                    )
                    SELECT
                        '30s' AS tier,
                        sensor_id,
                        ? AS bucket_start,
                        ? AS bucket_end,
                        COUNT(*) AS sample_count,
                        MIN(value) AS value_min,
                        MAX(value) AS value_max,
                        AVG(value) AS value_avg,
                        SUM(value) AS value_sum,
                        ? AS created_at
                    FROM sensor_polls
                    WHERE created_at >= ? AND created_at < ? AND value IS NOT NULL
                    GROUP BY sensor_id
                    ON CONFLICT(tier, sensor_id, bucket_start) DO UPDATE SET
                        bucket_end = excluded.bucket_end,
                        sample_count = excluded.sample_count,
                        value_min = excluded.value_min,
                        value_max = excluded.value_max,
                        value_avg = excluded.value_avg,
                        value_sum = excluded.value_sum,
                        created_at = excluded.created_at;
                    """,
                    (b_start, b_end, b_end, b_start, b_end),
                )

                # Удаление сырых снимков sensor_polls за этот 30с бакет
                cursor.execute(
                    "DELETE FROM sensor_polls WHERE created_at >= ? AND created_at < ?",
                    (b_start, b_end),
                )
                stats["sensors_deleted"] += cursor.rowcount

                # Находим system_snapshots для удаления (кроме якорей LOCF)
                cursor.execute(
                    "SELECT id FROM system_snapshots WHERE created_at >= ? AND created_at < ?",
                    (b_start, b_end),
                )
                cand_ids = [r[0] for r in cursor.fetchall() if r[0] not in anchors]
                if cand_ids:
                    pl = ",".join("?" for _ in cand_ids)
                    cursor.execute(
                        f"DELETE FROM process_snapshots WHERE snapshot_id IN ({pl}) AND sample_type = 'snapshot'",
                        cand_ids,
                    )
                    stats["procs_deleted"] += cursor.rowcount
                    cursor.execute(
                        f"DELETE FROM system_snapshots WHERE id IN ({pl})",
                        cand_ids,
                    )
                    stats["snapshots_deleted"] += cursor.rowcount

            conn.commit()
        return stats

    def step_3m_rollup(self, now_epoch: float) -> Dict[str, int]:
        """Усредняет 30-секундные бакеты старше 3 минут в бакеты '3m' с удалением строк '30s'.

        Args:
            now_epoch: Текущее время Unix epoch.

        Returns:
            Dict[str, int]: Статистика сворачивания в 3-минутный уровень.
        """
        cutoff_epoch = now_epoch - 180.0
        stats = {"rollups_created": 0, "rows_cleaned": 0}

        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO telemetry_rollups (
                    tier, sensor_id, bucket_start, bucket_end, sample_count,
                    cpu_avg, cpu_max, ram_avg, ram_max, ram_used_gb_avg,
                    disk_read_bps_avg, disk_write_bps_avg, net_sent_bps_avg, net_recv_bps_avg,
                    value_min, value_max, value_avg, value_sum, created_at
                )
                SELECT
                    '3m' AS tier,
                    sensor_id,
                    CAST(bucket_start / 180 AS INTEGER) * 180 AS b_start,
                    (CAST(bucket_start / 180 AS INTEGER) * 180) + 180 AS b_end,
                    SUM(sample_count) AS sample_count,
                    AVG(cpu_avg) AS cpu_avg,
                    MAX(cpu_max) AS cpu_max,
                    AVG(ram_avg) AS ram_avg,
                    MAX(ram_max) AS ram_max,
                    AVG(ram_used_gb_avg) AS ram_used_gb_avg,
                    AVG(disk_read_bps_avg) AS disk_read_bps_avg,
                    AVG(disk_write_bps_avg) AS disk_write_bps_avg,
                    AVG(net_sent_bps_avg) AS net_sent_bps_avg,
                    AVG(net_recv_bps_avg) AS net_recv_bps_avg,
                    MIN(value_min) AS value_min,
                    MAX(value_max) AS value_max,
                    AVG(value_avg) AS value_avg,
                    SUM(value_sum) AS value_sum,
                    MAX(created_at) AS created_at
                FROM telemetry_rollups
                WHERE tier = '30s' AND bucket_end <= ?
                GROUP BY sensor_id, CAST(bucket_start / 180 AS INTEGER) * 180
                ON CONFLICT(tier, sensor_id, bucket_start) DO UPDATE SET
                    bucket_end = excluded.bucket_end,
                    sample_count = excluded.sample_count,
                    cpu_avg = excluded.cpu_avg,
                    cpu_max = excluded.cpu_max,
                    ram_avg = excluded.ram_avg,
                    ram_max = excluded.ram_max,
                    ram_used_gb_avg = excluded.ram_used_gb_avg,
                    disk_read_bps_avg = excluded.disk_read_bps_avg,
                    disk_write_bps_avg = excluded.disk_write_bps_avg,
                    net_sent_bps_avg = excluded.net_sent_bps_avg,
                    net_recv_bps_avg = excluded.net_recv_bps_avg,
                    value_min = excluded.value_min,
                    value_max = excluded.value_max,
                    value_avg = excluded.value_avg,
                    value_sum = excluded.value_sum,
                    created_at = excluded.created_at;
                """,
                (cutoff_epoch,),
            )
            stats["rollups_created"] = cursor.rowcount if cursor.rowcount > 0 else 0

            # Очистка исходных строк '30s'
            cursor.execute(
                "DELETE FROM telemetry_rollups WHERE tier = '30s' AND bucket_end <= ?",
                (cutoff_epoch,),
            )
            stats["rows_cleaned"] = cursor.rowcount if cursor.rowcount > 0 else 0
            conn.commit()

        return stats

    def step_10m_rollup(self, now_epoch: float) -> Dict[str, int]:
        """Усредняет 3-минутные бакеты старше 10 минут в бакеты '10m' с удалением строк '3m'.

        Args:
            now_epoch: Текущее время Unix epoch.

        Returns:
            Dict[str, int]: Статистика сворачивания в 10-минутный уровень.
        """
        cutoff_epoch = now_epoch - 600.0
        stats = {"rollups_created": 0, "rows_cleaned": 0}

        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO telemetry_rollups (
                    tier, sensor_id, bucket_start, bucket_end, sample_count,
                    cpu_avg, cpu_max, ram_avg, ram_max, ram_used_gb_avg,
                    disk_read_bps_avg, disk_write_bps_avg, net_sent_bps_avg, net_recv_bps_avg,
                    value_min, value_max, value_avg, value_sum, created_at
                )
                SELECT
                    '10m' AS tier,
                    sensor_id,
                    CAST(bucket_start / 600 AS INTEGER) * 600 AS b_start,
                    (CAST(bucket_start / 600 AS INTEGER) * 600) + 600 AS b_end,
                    SUM(sample_count) AS sample_count,
                    AVG(cpu_avg) AS cpu_avg,
                    MAX(cpu_max) AS cpu_max,
                    AVG(ram_avg) AS ram_avg,
                    MAX(ram_max) AS ram_max,
                    AVG(ram_used_gb_avg) AS ram_used_gb_avg,
                    AVG(disk_read_bps_avg) AS disk_read_bps_avg,
                    AVG(disk_write_bps_avg) AS disk_write_bps_avg,
                    AVG(net_sent_bps_avg) AS net_sent_bps_avg,
                    AVG(net_recv_bps_avg) AS net_recv_bps_avg,
                    MIN(value_min) AS value_min,
                    MAX(value_max) AS value_max,
                    AVG(value_avg) AS value_avg,
                    SUM(value_sum) AS value_sum,
                    MAX(created_at) AS created_at
                FROM telemetry_rollups
                WHERE tier = '3m' AND bucket_end <= ?
                GROUP BY sensor_id, CAST(bucket_start / 600 AS INTEGER) * 600
                ON CONFLICT(tier, sensor_id, bucket_start) DO UPDATE SET
                    bucket_end = excluded.bucket_end,
                    sample_count = excluded.sample_count,
                    cpu_avg = excluded.cpu_avg,
                    cpu_max = excluded.cpu_max,
                    ram_avg = excluded.ram_avg,
                    ram_max = excluded.ram_max,
                    ram_used_gb_avg = excluded.ram_used_gb_avg,
                    disk_read_bps_avg = excluded.disk_read_bps_avg,
                    disk_write_bps_avg = excluded.disk_write_bps_avg,
                    net_sent_bps_avg = excluded.net_sent_bps_avg,
                    net_recv_bps_avg = excluded.net_recv_bps_avg,
                    value_min = excluded.value_min,
                    value_max = excluded.value_max,
                    value_avg = excluded.value_avg,
                    value_sum = excluded.value_sum,
                    created_at = excluded.created_at;
                """,
                (cutoff_epoch,),
            )
            stats["rollups_created"] = cursor.rowcount if cursor.rowcount > 0 else 0

            # Очистка исходных строк '3m'
            cursor.execute(
                "DELETE FROM telemetry_rollups WHERE tier = '3m' AND bucket_end <= ?",
                (cutoff_epoch,),
            )
            stats["rows_cleaned"] = cursor.rowcount if cursor.rowcount > 0 else 0
            conn.commit()

        return stats

    def step_36h_rollup(self, now_epoch: float) -> Dict[str, int]:
        """Усредняет 10-минутные бакеты старше 36 часов в бакеты '36h' с удалением строк '10m'.

        Args:
            now_epoch: Текущее время Unix epoch.

        Returns:
            Dict[str, int]: Статистика сворачивания в 36-часовой уровень.
        """
        # 36 часов = 36 * 3600 = 129600 секунд
        tier_step = 129600.0
        cutoff_epoch = now_epoch - tier_step
        stats = {"rollups_created": 0, "rows_cleaned": 0}

        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO telemetry_rollups (
                    tier, sensor_id, bucket_start, bucket_end, sample_count,
                    cpu_avg, cpu_max, ram_avg, ram_max, ram_used_gb_avg,
                    disk_read_bps_avg, disk_write_bps_avg, net_sent_bps_avg, net_recv_bps_avg,
                    value_min, value_max, value_avg, value_sum, created_at
                )
                SELECT
                    '36h' AS tier,
                    sensor_id,
                    CAST(bucket_start / 129600 AS INTEGER) * 129600 AS b_start,
                    (CAST(bucket_start / 129600 AS INTEGER) * 129600) + 129600 AS b_end,
                    SUM(sample_count) AS sample_count,
                    AVG(cpu_avg) AS cpu_avg,
                    MAX(cpu_max) AS cpu_max,
                    AVG(ram_avg) AS ram_avg,
                    MAX(ram_max) AS ram_max,
                    AVG(ram_used_gb_avg) AS ram_used_gb_avg,
                    AVG(disk_read_bps_avg) AS disk_read_bps_avg,
                    AVG(disk_write_bps_avg) AS disk_write_bps_avg,
                    AVG(net_sent_bps_avg) AS net_sent_bps_avg,
                    AVG(net_recv_bps_avg) AS net_recv_bps_avg,
                    MIN(value_min) AS value_min,
                    MAX(value_max) AS value_max,
                    AVG(value_avg) AS value_avg,
                    SUM(value_sum) AS value_sum,
                    MAX(created_at) AS created_at
                FROM telemetry_rollups
                WHERE tier = '10m' AND bucket_end <= ?
                GROUP BY sensor_id, CAST(bucket_start / 129600 AS INTEGER) * 129600
                ON CONFLICT(tier, sensor_id, bucket_start) DO UPDATE SET
                    bucket_end = excluded.bucket_end,
                    sample_count = excluded.sample_count,
                    cpu_avg = excluded.cpu_avg,
                    cpu_max = excluded.cpu_max,
                    ram_avg = excluded.ram_avg,
                    ram_max = excluded.ram_max,
                    ram_used_gb_avg = excluded.ram_used_gb_avg,
                    disk_read_bps_avg = excluded.disk_read_bps_avg,
                    disk_write_bps_avg = excluded.disk_write_bps_avg,
                    net_sent_bps_avg = excluded.net_sent_bps_avg,
                    net_recv_bps_avg = excluded.net_recv_bps_avg,
                    value_min = excluded.value_min,
                    value_max = excluded.value_max,
                    value_avg = excluded.value_avg,
                    value_sum = excluded.value_sum,
                    created_at = excluded.created_at;
                """,
                (cutoff_epoch,),
            )
            stats["rollups_created"] = cursor.rowcount if cursor.rowcount > 0 else 0

            # Очистка исходных строк '10m'
            cursor.execute(
                "DELETE FROM telemetry_rollups WHERE tier = '10m' AND bucket_end <= ?",
                (cutoff_epoch,),
            )
            stats["rows_cleaned"] = cursor.rowcount if cursor.rowcount > 0 else 0
            conn.commit()

        return stats

