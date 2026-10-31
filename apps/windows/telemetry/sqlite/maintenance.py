# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry Sqlite - Maintenance
# =============================================================================
# Description:
#   Обслуживание, очистка, агрегация и контроль размера базы данных SQLite
#   в архитектуре 12 базовых таблиц.
#
# Usage Examples:
#   Python API:
#     from apps.windows.telemetry.sqlite.maintenance import TelemetryMaintenance
#
#     maint = TelemetryMaintenance(connection_manager)
#     stats = maint.get_storage_stats()
#
# File: maintenance.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry.sqlite
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-30 12:55:00
# =============================================================================

from __future__ import annotations
"""Методы обслуживания, очистки старых записей, дефрагментации и агрегации телеметрии в SQLite (12 таблиц)."""

import json
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .connection import TelemetryConnectionManager
from .delta_tracker import SNAPSHOT_FIELDS, VOLATILE_FIELDS
from .tiered_compactor import TelemetryTieredCompactor

try:
    from logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


# Уровни агрегатов долгосрочной истории потребления железа и приложений
HISTORY_TIERS = ('36h', 'hourly', 'daily', 'weekly', 'monthly', 'yearly', 'proc_daily', 'proc_weekly', 'proc_all_time')


class TelemetryMaintenance:
    """Выполняет регламентные операции: очистка, контроль размера, вакуумирование и агрегации."""

    def __init__(
        self,
        connection_manager: TelemetryConnectionManager,
        max_db_size_mb: float = 50.0,
        retention_days: int = 7,
        auto_vacuum_enabled: bool = True,
        buffer_file_path: Optional[Path] = None,
    ) -> None:
        """Инициализирует менеджер обслуживания базы данных.

        Args:
            connection_manager: Менеджер соединений SQLite.
            max_db_size_mb: Максимальный размер файлов БД в МБ.
            retention_days: Срок хранения сырых записей в днях.
            auto_vacuum_enabled: Флаг автоматического запуска VACUUM.
            buffer_file_path: Путь к файлу буфера.
        """
        self._cm = connection_manager
        self.max_db_size_mb = max(1.0, float(max_db_size_mb))
        self.retention_days = max(1, int(retention_days))
        self.auto_vacuum_enabled = bool(auto_vacuum_enabled)
        self.buffer_file_path = buffer_file_path or (self._cm.db_path.parent / "telemetry_buffer.jsonl")
        self._tiered_compactor = TelemetryTieredCompactor(self._cm)

    def run_tiered_compaction(
        self,
        thorough_mode: bool = False,
        now_epoch: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Запускает каскадное многоуровневое усреднение снимков (5с -> 30с -> 3м -> 10м -> 36ч).

        Args:
            thorough_mode: Флаг режима тщательного сбора (при True усреднение и удаление отключаются).
            now_epoch: Текущее время Unix epoch (опционально, для тестов).

        Returns:
            Dict[str, Any]: Отчет о количестве созданных бакетов и удаленных строк.
        """
        return self._tiered_compactor.run_tiered_compaction(thorough_mode=thorough_mode, now_epoch=now_epoch)

    def get_db_file_sizes(self) -> Dict[str, int]:
        """Возвращает физические размеры файлов БД на диске (DB, WAL, SHM) в байтах."""
        db_path = self._cm.db_path
        db_bytes = db_path.stat().st_size if db_path.exists() else 0
        wal_path = db_path.with_name(db_path.name + "-wal")
        shm_path = db_path.with_name(db_path.name + "-shm")
        wal_bytes = wal_path.stat().st_size if wal_path.exists() else 0
        shm_bytes = shm_path.stat().st_size if shm_path.exists() else 0
        return {
            "db_bytes": db_bytes,
            "wal_bytes": wal_bytes,
            "shm_bytes": shm_bytes,
            "total_bytes": db_bytes + wal_bytes + shm_bytes,
        }

    def get_total_db_size_mb(self) -> float:
        """Возвращает совокупный физический размер файлов БД в МБ."""
        sizes = self.get_db_file_sizes()
        return round(sizes["total_bytes"] / (1024.0 * 1024.0), 3)

    def checkpoint_wal(self) -> bool:
        """Сбрасывает WAL-журнал в основной файл базы данных."""
        if self._cm.read_only:
            return False
        with self._cm.lock:
            try:
                with self._cm.get_connection() as conn:
                    conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                return True
            except Exception as e:
                logger.debug(f"Ошибка сброса WAL-журнала: {e}")
                return False

    def vacuum(self) -> bool:
        """Выполняет сжатие и дефрагментацию базы данных."""
        if self._cm.read_only:
            return False
        with self._cm.lock:
            self.checkpoint_wal()
            try:
                conn = sqlite3.connect(str(self._cm.db_path), timeout=30.0, isolation_level=None)
                try:
                    conn.execute("PRAGMA incremental_vacuum(2000);")
                    conn.execute("VACUUM;")
                finally:
                    conn.close()
                self.checkpoint_wal()
                logger.info(f"Выполнен VACUUM для базы данных телеметрии ({self._cm.db_path})")
                return True
            except Exception as e:
                logger.warning(f"Ошибка при выполнении VACUUM: {e}")
                return False

    def get_storage_stats(
        self,
        buffered_count: int = 0,
        buffer_mode: str = "memory",
        buffer_size: int = 50,
        flush_interval_seconds: float = 30.0,
    ) -> Dict[str, Any]:
        """Возвращает агрегированную статистику 12 базовых таблиц, размера и параметров."""
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()

            def _q_int(sql: str, params: tuple = ()) -> int:
                try:
                    cursor.execute(sql, params)
                    r = cursor.fetchone()
                    return int(r[0] or 0) if r else 0
                except Exception:
                    return 0

            snap_count = _q_int("SELECT COUNT(*) FROM system_snapshots;")
            proc_count = _q_int("SELECT COUNT(*) FROM process_snapshots WHERE sample_type = 'snapshot';")
            outliers_count = _q_int("SELECT COUNT(*) FROM process_snapshots WHERE sample_type = 'outlier' OR is_outlier = 1;")
            sensors_count = _q_int("SELECT COUNT(*) FROM sensor_polls;")
            rollups_count = _q_int("SELECT COUNT(*) FROM telemetry_rollups;")
            rollups_2min_count = _q_int("SELECT COUNT(*) FROM telemetry_rollups WHERE tier = 'proc_2min';")
            rollups_daily_count = _q_int("SELECT COUNT(*) FROM telemetry_rollups WHERE tier = 'proc_daily';")
            telemetry_hourly_count = _q_int("SELECT COUNT(*) FROM telemetry_rollups WHERE tier = 'hourly';")
            telemetry_daily_count = _q_int("SELECT COUNT(*) FROM telemetry_rollups WHERE tier = 'daily';")
            telemetry_weekly_count = _q_int("SELECT COUNT(*) FROM telemetry_rollups WHERE tier = 'weekly';")
            telemetry_monthly_count = _q_int("SELECT COUNT(*) FROM telemetry_rollups WHERE tier = 'monthly';")
            telemetry_yearly_count = _q_int("SELECT COUNT(*) FROM telemetry_rollups WHERE tier = 'yearly';")

            incidents_count = _q_int("SELECT COUNT(*) FROM incidents WHERE domain = 'incident';")
            events_count = _q_int("SELECT COUNT(*) FROM incidents WHERE domain = 'telemetry_event';")
            app_polls_count = _q_int("SELECT COUNT(*) FROM incidents WHERE domain = 'app_poll';")
            app_events_count = _q_int("SELECT COUNT(*) FROM incidents WHERE domain = 'app_event';")
            device_events_count = _q_int("SELECT COUNT(*) FROM incidents WHERE domain = 'device_event';")
            telemetry_spikes_count = _q_int("SELECT COUNT(*) FROM incidents WHERE domain = 'spike';")

            app_params_count = _q_int("SELECT COUNT(*) FROM inventory_changes WHERE domain LIKE 'app_params:%';")
            w64_events_count = _q_int("SELECT COUNT(*) FROM process_file_events WHERE details_json LIKE '%etw%' OR details_json LIKE '%w64%' OR operation_type LIKE 'w64:%';")
            disk_io_count = _q_int("SELECT COUNT(*) FROM process_file_events WHERE operation_type LIKE 'disk_%';")

            audits_count = _q_int("SELECT COUNT(*) FROM hardware_components WHERE category = 'hardware_audit';")
            device_inventory_count = _q_int("SELECT COUNT(*) FROM hardware_components WHERE category = 'pnp_device';")
            disk_inventory_count = _q_int("SELECT COUNT(*) FROM hardware_components WHERE category = 'disk';")
            volume_inventory_count = _q_int("SELECT COUNT(*) FROM hardware_components WHERE category = 'volume';")
            cpu_inventory_count = _q_int("SELECT COUNT(*) FROM hardware_components WHERE category = 'cpu';")
            ram_module_inventory_count = _q_int("SELECT COUNT(*) FROM hardware_components WHERE category = 'ram';")
            gpu_inventory_count = _q_int("SELECT COUNT(*) FROM hardware_components WHERE category = 'gpu';")
            network_adapter_inventory_count = _q_int("SELECT COUNT(*) FROM hardware_components WHERE category = 'network';")

            disk_health_count = _q_int("SELECT COUNT(*) FROM sensor_polls WHERE sensor_category = 'disk_health';")
            disk_perf_count = _q_int("SELECT COUNT(*) FROM sensor_polls WHERE sensor_category = 'disk_perf';")
            cpu_samples_count = _q_int("SELECT COUNT(*) FROM sensor_polls WHERE sensor_category = 'cpu_sample';")
            ram_samples_count = _q_int("SELECT COUNT(*) FROM sensor_polls WHERE sensor_category = 'ram_sample';")
            gpu_samples_count = _q_int("SELECT COUNT(*) FROM sensor_polls WHERE sensor_category = 'gpu_sample';")
            network_samples_count = _q_int("SELECT COUNT(*) FROM sensor_polls WHERE sensor_category = 'net_sample';")

            file_sizes = self.get_db_file_sizes()
            size_mb = round(file_sizes["db_bytes"] / (1024 * 1024), 2)
            wal_size_mb = round(file_sizes["wal_bytes"] / (1024 * 1024), 2)
            total_size_mb = round(file_sizes["total_bytes"] / (1024 * 1024), 2)
            buffer_file_size = self.buffer_file_path.stat().st_size if self.buffer_file_path.exists() else 0

            return {
                "db_path": str(self._cm.db_path),
                "snapshots_count": snap_count,
                "process_snapshots_count": proc_count,
                "process_outliers_count": outliers_count,
                "process_rollups_2min_count": rollups_2min_count,
                "process_rollups_daily_count": rollups_daily_count,
                "incidents_count": incidents_count,
                "telemetry_rollups_count": rollups_count,
                "telemetry_hourly_count": telemetry_hourly_count,
                "telemetry_daily_count": telemetry_daily_count,
                "telemetry_weekly_count": telemetry_weekly_count,
                "telemetry_monthly_count": telemetry_monthly_count,
                "telemetry_yearly_count": telemetry_yearly_count,
                "telemetry_spikes_count": telemetry_spikes_count,
                "disk_inventory_count": disk_inventory_count,
                "volume_inventory_count": volume_inventory_count,
                "disk_health_count": disk_health_count,
                "disk_perf_count": disk_perf_count,
                "disk_io_count": disk_io_count,
                "cpu_inventory_count": cpu_inventory_count,
                "ram_module_inventory_count": ram_module_inventory_count,
                "gpu_inventory_count": gpu_inventory_count,
                "network_adapter_inventory_count": network_adapter_inventory_count,
                "cpu_samples_count": cpu_samples_count,
                "ram_samples_count": ram_samples_count,
                "gpu_samples_count": gpu_samples_count,
                "network_samples_count": network_samples_count,
                "sensor_polls_count": sensors_count,
                "events_count": events_count,
                "hardware_audits_count": audits_count,
                "app_polls_count": app_polls_count,
                "app_events_count": app_events_count,
                "app_param_changes_count": app_params_count,
                "custom_records_count": 0,
                "device_events_count": device_events_count,
                "device_inventory_count": device_inventory_count,
                "w64_events_count": w64_events_count,
                "file_size_mb": size_mb,
                "wal_size_mb": wal_size_mb,
                "total_size_mb": total_size_mb,
                "max_db_size_mb": self.max_db_size_mb,
                "retention_days": self.retention_days,
                "size_limit_exceeded": total_size_mb > self.max_db_size_mb,
                "buffer_mode": buffer_mode,
                "buffered_count": buffered_count,
                "buffer_size": buffer_size,
                "flush_interval_seconds": flush_interval_seconds,
                "buffer_file_path": str(self.buffer_file_path),
                "buffer_file_size_bytes": buffer_file_size,
            }

    @staticmethod
    def _locf_anchor_ids(cursor: sqlite3.Cursor) -> List[int]:
        """Возвращает id снимков, хранящих последнее известное значение статических полей."""
        fields = [f for f in SNAPSHOT_FIELDS if f not in VOLATILE_FIELDS] + ["raw_json"]
        cols = ", ".join(f"MAX(CASE WHEN {f} IS NOT NULL AND {f} != '' THEN id END)" for f in fields)
        row = cursor.execute(f"SELECT {cols} FROM system_snapshots").fetchone()
        return sorted({i for i in (row or []) if i is not None})

    def cleanup_old_records(self, retention_days: Optional[int] = None, vacuum_after: bool = False) -> int:
        """Удаляет устаревшие записи телеметрии из 12 базовых таблиц (LOCF-якоря статических полей сохраняются)."""
        if self._cm.read_only:
            return 0
        days = retention_days if retention_days is not None else self.retention_days
        threshold_epoch = datetime.now(timezone.utc).timestamp() - (float(days) * 86400.0 if days > 0 else -1.0)
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            anchors = set(self._locf_anchor_ids(cursor))
            cursor.execute("SELECT id FROM system_snapshots WHERE created_at < ?", (threshold_epoch,))
            old_ids = [row[0] for row in cursor.fetchall() if row[0] not in anchors]
            if old_ids:
                cursor.execute(
                    "DELETE FROM process_snapshots WHERE snapshot_id IN (SELECT id FROM system_snapshots WHERE created_at < ?)",
                    (threshold_epoch,),
                )
                placeholders = ",".join("?" for _ in anchors) or "NULL"
                cursor.execute(
                    f"DELETE FROM system_snapshots WHERE created_at < ? AND id NOT IN ({placeholders})",
                    (threshold_epoch, *anchors),
                )
            cursor.execute("DELETE FROM process_snapshots WHERE created_at < ? AND sample_type != 'audit'", (threshold_epoch,))
            cursor.execute("DELETE FROM sensor_polls WHERE created_at < ?", (threshold_epoch,))
            cursor.execute("DELETE FROM incidents WHERE created_at < ?", (threshold_epoch,))
            cursor.execute("DELETE FROM inventory_changes WHERE created_at < ?", (threshold_epoch,))

            pid_snap_threshold_str = (datetime.now(timezone.utc) - timedelta(days=min(days, 1))).isoformat()
            cursor.execute("DELETE FROM process_file_events WHERE timestamp < ? OR created_at < ?", (pid_snap_threshold_str, threshold_epoch))

            conn.commit()
            deleted_count = len(old_ids)
            logger.info(f"Очищено {deleted_count} устаревших снимков телеметрии (старше {days} дн.)")

        if vacuum_after and self.auto_vacuum_enabled:
            self.vacuum()

        return deleted_count

    def purge_log_tables(self, vacuum: bool = True) -> Dict[str, int]:
        """Очистка записей журналов событий Windows (domain='security_event' в таблице incidents)."""
        if self._cm.read_only:
            return {}

        stats: Dict[str, int] = {}
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT COUNT(*) FROM incidents WHERE domain = 'security_event';")
                count = cursor.fetchone()[0]
                if count > 0:
                    cursor.execute("DELETE FROM incidents WHERE domain = 'security_event';")
                    stats["security_events"] = count
                    stats["incidents(security_event)"] = count
            except Exception as ex:
                logger.debug(f"Пропуск очистки событий безопасности: {ex}")
            conn.commit()

        if stats:
            logger.info(f"Очищены записи журналов телеметрии: {stats}")
        else:
            logger.debug("Очищены записи журналов телеметрии: устаревших событий безопасности не обнаружено (0)")
        if vacuum:
            self.vacuum()
        return stats

    def purge_live_stream_tables(self, vacuum: bool = True) -> Dict[str, int]:
        """Полная очистка потоковых данных режима live stream при переходе или работе в режиме аудита.

        Данные глубокого аудита процессов (process_lifecycle_sessions и process_snapshots с sample_type='audit')
        сохраняются без изменений.
        """
        if self._cm.read_only:
            return {}

        stats: Dict[str, int] = {}
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Снимки процессов (сохраняем sample_type = 'audit')
            cursor.execute("SELECT COUNT(*) FROM process_snapshots WHERE sample_type != 'audit';")
            ps_cnt = cursor.fetchone()[0]
            if ps_cnt > 0:
                cursor.execute("DELETE FROM process_snapshots WHERE sample_type != 'audit';")
                stats["process_snapshots"] = ps_cnt

            # 2. Снимки системы, сенсоры, агрегаты и файловые события
            # Агрегаты истории железа и приложений (HISTORY_TIERS) живут вечно, удаляется только транзитное
            marks = ",".join("?" for _ in HISTORY_TIERS)
            cursor.execute(f"SELECT COUNT(*) FROM telemetry_rollups WHERE tier NOT IN ({marks});", HISTORY_TIERS)
            rollups_cnt = cursor.fetchone()[0]
            if rollups_cnt > 0:
                cursor.execute(f"DELETE FROM telemetry_rollups WHERE tier NOT IN ({marks});", HISTORY_TIERS)
                stats["telemetry_rollups"] = rollups_cnt

            for tbl in ("system_snapshots", "sensor_polls", "process_file_events"):
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {tbl};")
                    count = cursor.fetchone()[0]
                    if count > 0:
                        cursor.execute(f"DELETE FROM {tbl};")
                        stats[tbl] = count
                except Exception as ex:
                    logger.debug(f"Пропуск очистки таблицы {tbl}: {ex}")

            # 3. Потоковые события и всплески в incidents
            cursor.execute(
                "SELECT COUNT(*) FROM incidents WHERE domain IN ('spike', 'app_poll', 'app_event', 'device_event', 'telemetry_event');"
            )
            inc_cnt = cursor.fetchone()[0]
            if inc_cnt > 0:
                cursor.execute(
                    "DELETE FROM incidents WHERE domain IN ('spike', 'app_poll', 'app_event', 'device_event', 'telemetry_event');"
                )
                stats["incidents"] = inc_cnt

            conn.commit()

        total_purged = sum(stats.values())
        logger.info(f"Таблицы live stream очищены ({total_purged} записей удалено): {stats}")

        if vacuum:
            self.vacuum()
        else:
            self.checkpoint_wal()

        return stats

    def enforce_size_limit(self, max_size_mb: Optional[float] = None, target_ratio: float = 0.85) -> Dict[str, Any]:
        """Ограничивает совокупный размер БД телеметрии."""
        if self._cm.read_only:
            return {"pruned": False, "read_only": True}
        limit_mb = max_size_mb if max_size_mb is not None else self.max_db_size_mb
        initial_sizes = self.get_db_file_sizes()
        initial_size_mb = round(initial_sizes["total_bytes"] / (1024.0 * 1024.0), 3)

        if initial_size_mb <= limit_mb:
            return {
                "pruned": False,
                "initial_size_mb": initial_size_mb,
                "final_size_mb": initial_size_mb,
                "max_size_mb": limit_mb,
                "deleted_snapshots": 0,
                "deleted_records": 0,
            }

        target_mb = max(0.5, limit_mb * target_ratio)
        logger.warning(f"⚠️ Превышен лимит размера базы данных: {initial_size_mb:.2f} МБ > {limit_mb:.2f} МБ.")

        self.purge_log_tables(vacuum=False)
        total_deleted_snaps = self.cleanup_old_records(retention_days=self.retention_days, vacuum_after=False)
        self.checkpoint_wal()

        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "DELETE FROM process_snapshots WHERE id NOT IN (SELECT id FROM process_snapshots ORDER BY id DESC LIMIT 5000);"
                )
                cursor.execute(
                    "DELETE FROM process_lifecycle_sessions WHERE instance_id NOT IN (SELECT instance_id FROM process_lifecycle_sessions ORDER BY created_ts DESC LIMIT 5000);"
                )
                conn.commit()
            except Exception as e:
                logger.debug(f"Усечение сэмплов: {e}")

            while True:
                cursor.execute("SELECT COUNT(*) FROM system_snapshots;")
                snap_count = cursor.fetchone()[0]
                if not snap_count or snap_count <= 5:
                    break
                batch_size = max(5, int(snap_count * 0.25))
                anchors = set(self._locf_anchor_ids(cursor))
                cursor.execute("SELECT id, created_at FROM system_snapshots ORDER BY created_at ASC LIMIT ?", (batch_size,))
                rows = [r for r in cursor.fetchall() if r[0] not in anchors]
                if not rows:
                    break
                ids_to_del = [r[0] for r in rows]
                cutoff_t = rows[-1][1]
                placeholders = ",".join("?" for _ in ids_to_del)
                cursor.execute(f"DELETE FROM process_snapshots WHERE snapshot_id IN ({placeholders})", ids_to_del)
                cursor.execute(f"DELETE FROM system_snapshots WHERE id IN ({placeholders})", ids_to_del)
                cursor.execute("DELETE FROM sensor_polls WHERE created_at <= ?", (cutoff_t,))
                cursor.execute("DELETE FROM process_file_events WHERE created_at <= ?", (cutoff_t,))
                cursor.execute("DELETE FROM incidents WHERE created_at <= ? AND domain != 'incident'", (cutoff_t,))
                conn.commit()
                total_deleted_snaps += len(ids_to_del)
                if snap_count - len(ids_to_del) <= 5:
                    break

        if self.auto_vacuum_enabled:
            self.vacuum()
        else:
            self.checkpoint_wal()

        final_sizes = self.get_db_file_sizes()
        final_size_mb = round(final_sizes["total_bytes"] / (1024.0 * 1024.0), 3)

        return {
            "pruned": True,
            "initial_size_mb": initial_size_mb,
            "final_size_mb": final_size_mb,
            "max_size_mb": limit_mb,
            "target_size_mb": target_mb,
            "deleted_snapshots": total_deleted_snaps,
        }

    def purge_history(self, retention_days: int) -> int:
        """Удаляет историю железа и приложений (агрегаты telemetry_rollups) старше срока хранения.

        Args:
            retention_days: Срок хранения в днях, 0 и меньше означает «хранить вечно».

        Returns:
            int: Количество удалённых строк истории.
        """
        if self._cm.read_only or retention_days <= 0:
            return 0
        threshold_epoch = datetime.now(timezone.utc).timestamp() - float(retention_days) * 86400.0
        marks = ','.join('?' for _ in HISTORY_TIERS)
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.execute(
                f"DELETE FROM telemetry_rollups WHERE tier IN ({marks}) AND created_at < ?",
                (*HISTORY_TIERS, threshold_epoch),
            )
            conn.commit()
            deleted = cursor.rowcount
        if deleted:
            logger.info(f"История старше {retention_days} дн. очищена: {deleted} строк")
        return deleted
