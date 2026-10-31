# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry Sqlite - Schema
# =============================================================================
# Description:
#   Определение консолидированной схемы SQLite (12 таблиц), индексов и миграций
#   для телеметрии Windows.
#
# Usage Examples:
#   Python API:
#     from apps.windows.telemetry.sqlite.schema import TelemetrySchemaManager
#
#     TelemetrySchemaManager.initialize_schema(conn)
#
# File: schema.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry.sqlite
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 15:58:30
# =============================================================================

from __future__ import annotations

"""Управление консолидированной схемой базы данных SQLite телеметрии Windows (12 таблиц)."""

import sqlite3
from typing import Dict, FrozenSet, List, Tuple

from .schema_audits import AUDITS_INDEX_DDL, AUDITS_SCHEMA_DDL
from .schema_core import CORE_INDEX_DDL, CORE_SCHEMA_DDL
from .schema_inventory import INVENTORY_INDEX_DDL, INVENTORY_SCHEMA_DDL
from .schema_security import SECURITY_INDEX_DDL, SECURITY_SCHEMA_DDL
from .schema_storage import STORAGE_INDEX_DDL, STORAGE_SCHEMA_DDL

try:
    from logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


ALLOWED_TABLES: FrozenSet[str] = frozenset({
    # Базовые 12 таблиц телеметрии Windows
    "system_snapshots",
    "sensor_polls",
    "telemetry_rollups",
    "hardware_components",
    "hardware_component_history",
    "process_snapshots",
    "process_lifecycle_sessions",
    "process_file_events",
    "incidents",
    "power_sessions",
    "inventory_state",
    "inventory_changes",
    # Системные таблицы SQLite
    "sqlite_sequence",
    # Персистентные таблицы модулей Windows SDK в telemetry.db
    "taskbar_action_history",
    "window_management_history",
    "personalization_snapshots",
    "personalization_change_history",
    "file_versions",
    "file_version_blobs",
    "focus_profiles",
    "suppressed_notifications",
    "focus_session_logs",
})

SCHEMA_DDL: Tuple[str, ...] = (
    *CORE_SCHEMA_DDL,
    *INVENTORY_SCHEMA_DDL,
    *AUDITS_SCHEMA_DDL,
    *SECURITY_SCHEMA_DDL,
    *STORAGE_SCHEMA_DDL,
)

INDEX_DDL: Tuple[str, ...] = (
    *CORE_INDEX_DDL,
    *INVENTORY_INDEX_DDL,
    *AUDITS_INDEX_DDL,
    *SECURITY_INDEX_DDL,
    *STORAGE_INDEX_DDL,
)


class TelemetrySchemaManager:
    """Менеджер инициализации и миграции консолидированной схемы базы данных SQLite (12 таблиц)."""

    @classmethod
    def initialize_schema(cls, conn: sqlite3.Connection) -> None:
        """Создает 12 базовых таблиц, индексы и удаляет устаревшие таблицы в рамках транзакции.

        Args:
            conn: Активное соединение с базой данных SQLite.
        """
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = OFF;")
        try:
            cls._prepare_legacy_tables(cursor)
            for ddl in SCHEMA_DDL:
                cursor.execute(ddl)
            cls._run_migrations(cursor)
            for idx_ddl in INDEX_DDL:
                cursor.execute(idx_ddl)
            conn.commit()
        finally:
            cursor.execute("PRAGMA foreign_keys = ON;")

    @staticmethod
    def _prepare_legacy_tables(cursor: sqlite3.Cursor) -> None:
        """Проверяет старую структуру таблиц перед выполнением CREATE TABLE IF NOT EXISTS."""
        cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name='telemetry_rollups';")
        row = cursor.fetchone()
        if row and row[1] and ("sensor_id" not in row[1] or "value_min" not in row[1]):
            cursor.execute("DROP TABLE IF EXISTS telemetry_rollups;")

        cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name='hardware_component_history';")
        row_hch = cursor.fetchone()
        if row_hch and row_hch[1] and "component_type" not in row_hch[1]:
            cursor.execute("DROP TABLE IF EXISTS hardware_component_history;")

        cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name='hardware_components';")
        row_hc = cursor.fetchone()
        if row_hc and row_hc[1] and ("first_seen" not in row_hc[1] or "specs_json" not in row_hc[1]):
            cursor.execute("DROP TABLE IF EXISTS hardware_components;")

        cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name='incidents';")
        row_inc = cursor.fetchone()
        if row_inc and row_inc[1] and (("NOT NULL" in row_inc[1] and "incident_id" in row_inc[1]) or "window_start" not in row_inc[1]):
            cursor.execute("SELECT COUNT(*) FROM incidents;")
            cnt = cursor.fetchone()[0] or 0
            if cnt == 0:
                cursor.execute("DROP TABLE IF EXISTS incidents;")
            else:
                cursor.execute("ALTER TABLE incidents RENAME TO _legacy_incidents;")

        cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name='process_file_events';")
        row_pfe = cursor.fetchone()
        if row_pfe and row_pfe[1] and ("process_instance" in row_pfe[1] or "operation_type" not in row_pfe[1]):
            cursor.execute("SELECT COUNT(*) FROM process_file_events;")
            cnt_pfe = cursor.fetchone()[0] or 0
            if cnt_pfe == 0:
                cursor.execute("DROP TABLE IF EXISTS process_file_events;")
            else:
                cursor.execute("ALTER TABLE process_file_events RENAME TO _legacy_process_file_events;")

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='process_snapshots';")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(process_snapshots);")
            ps_info = cursor.fetchall()
            if any(r[1] == "snapshot_id" and r[3] == 1 for r in ps_info):
                proc_ddl = next((ddl for ddl in SCHEMA_DDL if "CREATE TABLE IF NOT EXISTS process_snapshots" in ddl), None)
                if proc_ddl:
                    temp_ddl = proc_ddl.replace(
                        "CREATE TABLE IF NOT EXISTS process_snapshots",
                        "CREATE TABLE _migrating_process_snapshots",
                    )
                    cursor.execute(temp_ddl)
                    cursor.execute("PRAGMA table_info(_migrating_process_snapshots);")
                    new_cols = {r[1] for r in cursor.fetchall()}
                    old_cols = [r[1] for r in ps_info]
                    common_cols = [c for c in old_cols if c in new_cols]
                    cols_str = ", ".join(common_cols)
                    cursor.execute(f"INSERT INTO _migrating_process_snapshots ({cols_str}) SELECT {cols_str} FROM process_snapshots;")
                    cursor.execute("DROP TABLE process_snapshots;")
                    cursor.execute("ALTER TABLE _migrating_process_snapshots RENAME TO process_snapshots;")

    @staticmethod
    def _run_migrations(cursor: sqlite3.Cursor) -> None:
        """Выполняет миграцию колонок 12 основных таблиц и удаляет все устаревшие таблицы."""
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
        )
        existing_tables = {row[0] for row in cursor.fetchall()}

        # 0. Перенос данных из устаревшей таблицы _legacy_process_file_events
        if "_legacy_process_file_events" in existing_tables and "process_file_events" in existing_tables:
            try:
                cursor.execute("PRAGMA table_info(_legacy_process_file_events);")
                old_cols = {r[1] for r in cursor.fetchall()}
                op_col = "action_type" if "action_type" in old_cols else ("operation_type" if "operation_type" in old_cols else "'IO'")
                bytes_col = "bytes_affected" if "bytes_affected" in old_cols else ("bytes_transferred" if "bytes_transferred" in old_cols else "0")
                cursor.execute(f'''
                    INSERT OR IGNORE INTO process_file_events (
                        instance_id, pid, process_name, timestamp, created_at,
                        operation_type, file_path, target_directory, bytes_transferred,
                        io_rate_bytes_sec, details_json
                    )
                    SELECT
                        instance_id, pid, process_name, timestamp, created_at,
                        {op_col}, file_path, target_directory, {bytes_col},
                        io_rate_bytes_sec, details_json
                    FROM _legacy_process_file_events;
                ''')
                cursor.execute("DROP TABLE IF EXISTS _legacy_process_file_events;")
            except Exception as mig_err:
                logger.debug(f"[TelemetrySchemaManager] Миграция _legacy_process_file_events: {mig_err}")

        # 0.1 Перенос данных из устаревшей таблицы _legacy_incidents
        if "_legacy_incidents" in existing_tables and "incidents" in existing_tables:
            try:
                cursor.execute("PRAGMA table_info(_legacy_incidents);")
                old_cols = {r[1] for r in cursor.fetchall()}
                cursor.execute("PRAGMA table_info(incidents);")
                new_cols = {r[1] for r in cursor.fetchall()}
                common = list(old_cols & new_cols)
                if common:
                    cols_str = ", ".join(common)
                    cursor.execute(f"INSERT OR IGNORE INTO incidents ({cols_str}) SELECT {cols_str} FROM _legacy_incidents;")
                cursor.execute("DROP TABLE IF EXISTS _legacy_incidents;")
            except Exception as mig_err:
                logger.debug(f"[TelemetrySchemaManager] Миграция _legacy_incidents: {mig_err}")

        # 1. Перенос истории апгрейдов железа из старой таблицы hardware_config_changes
        if "hardware_config_changes" in existing_tables and "hardware_component_history" in existing_tables:
            try:
                cursor.execute("SELECT COUNT(*) FROM hardware_component_history;")
                if (cursor.fetchone()[0] or 0) == 0:
                    cursor.execute('''
                        INSERT INTO hardware_component_history (
                            timestamp, created_at, component_type, change_type,
                            component_name, old_config_json, new_config_json, summary
                        )
                        SELECT
                            timestamp, created_at, component_type, change_type,
                            component_name, old_config_json, new_config_json, summary
                        FROM hardware_config_changes;
                    ''')
            except sqlite3.OperationalError:
                pass

        # 2. Добавление недостающих колонок в существующие таблицы из 12 базовых
        required_columns: Dict[str, List[Tuple[str, str]]] = {
            "system_snapshots": [
                ("cpu_temp_c", "REAL"),
                ("cpu_power_w", "REAL"),
                ("gpu_vram_used_mb", "REAL"),
                ("throttling_json", "TEXT"),
                ("vss_snapshots_count", "INTEGER DEFAULT 0"),
                ("hardware_audit", "TEXT"),
            ],
            "sensor_polls": [
                ("value_numeric", "REAL"),
                ("status", "TEXT DEFAULT 'OK'"),
            ],
            "process_snapshots": [
                ("sample_type", "TEXT NOT NULL DEFAULT 'snapshot'"),
                ("instance_id", "TEXT"),
                ("created_at", "REAL"),
                ("working_set_mb", "REAL"),
                ("private_mb", "REAL"),
                ("peak_working_set_mb", "REAL"),
                ("commit_size_mb", "REAL"),
                ("page_faults", "INTEGER"),
                ("gdi_objects", "INTEGER DEFAULT 0"),
                ("user_objects", "INTEGER DEFAULT 0"),
                ("read_bytes", "INTEGER"),
                ("write_bytes", "INTEGER"),
                ("read_operations", "INTEGER"),
                ("write_operations", "INTEGER"),
                ("exit_time", "REAL"),
                ("is_alive", "INTEGER DEFAULT 1"),
                ("user_time_sec", "REAL"),
                ("kernel_time_sec", "REAL"),
                ("total_cpu_time_sec", "REAL"),
                ("total_context_switches", "INTEGER"),
                ("cpu_cycles", "INTEGER"),
                ("open_files_count", "INTEGER DEFAULT 0"),
                ("tcp_connections_count", "INTEGER DEFAULT 0"),
                ("udp_sockets_count", "INTEGER DEFAULT 0"),
                ("sockets_json", "TEXT"),
                ("open_files_json", "TEXT"),
                ("leak_risk_score", "TEXT"),
                ("is_outlier", "INTEGER DEFAULT 0"),
                ("raw_json", "TEXT"),
            ],
            "process_lifecycle_sessions": [
                ("definition_id", "INTEGER DEFAULT 1"),
                ("parent_instance_id", "INTEGER"),
                ("icon_base64", "TEXT"),
                ("sid", "TEXT"),
                ("session_id", "INTEGER DEFAULT 1"),
                ("integrity_level", "TEXT"),
                ("parent_guid", "TEXT"),
                ("status", "TEXT DEFAULT 'RUNNING'"),
            ],
            "process_file_events": [
                ("process_name", "TEXT"),
                ("io_rate_bytes_sec", "REAL DEFAULT 0.0"),
                ("details_json", "TEXT"),
            ],
            "incidents": [
                ("window_start", "TEXT"),
                ("window_end", "TEXT"),
                ("duration_sec", "REAL DEFAULT 0.0"),
                ("resolved", "INTEGER DEFAULT 0"),
                ("domain", "TEXT NOT NULL DEFAULT 'incident'"),
                ("channel", "TEXT"),
                ("event_id", "INTEGER"),
                ("event_record_id", "INTEGER"),
                ("provider_name", "TEXT"),
                ("sensor_id", "TEXT"),
                ("device_id", "TEXT"),
                ("app_name", "TEXT"),
                ("value", "REAL"),
                ("baseline_mean", "REAL"),
                ("baseline_sigma", "REAL"),
                ("deviation_factor", "REAL"),
                ("unit", "TEXT"),
                ("message", "TEXT"),
                ("details_json", "TEXT"),
                ("raw_xml", "TEXT"),
            ],
            "power_sessions": [
                ("record_type", "TEXT NOT NULL DEFAULT 'session'"),
                ("classification", "TEXT"),
                ("confidence", "TEXT"),
                ("user", "TEXT"),
                ("domain", "TEXT"),
                ("process_id", "INTEGER"),
                ("summary", "TEXT"),
                ("bugcheck_code", "TEXT"),
                ("bugcheck_params_json", "TEXT"),
                ("dump_file", "TEXT"),
                ("event_id", "INTEGER"),
                ("provider", "TEXT"),
                ("channel", "TEXT"),
                ("evidence_json", "TEXT"),
                ("details_json", "TEXT"),
                ("raw_xml", "TEXT"),
            ],
            "inventory_state": [
                ("state_json", "TEXT"),
                ("updated_at", "REAL DEFAULT 0.0"),
            ],
            "inventory_changes": [
                ("timestamp", "TEXT"),
                ("created_at", "REAL DEFAULT 0.0"),
                ("diff_json", "TEXT"),
            ],
        }

        for table_name, cols in required_columns.items():
            if table_name not in existing_tables:
                continue
            cursor.execute(f"PRAGMA table_info({table_name});")
            present_cols = {row[1] for row in cursor.fetchall()}
            for col_name, col_type in cols:
                if col_name not in present_cols:
                    try:
                        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type};")
                    except sqlite3.OperationalError:
                        pass

        # 3. Удаление всех избыточных и устаревших таблиц, не входящих в разрешенные
        for tbl in sorted(existing_tables - ALLOWED_TABLES):
            if tbl.startswith("sqlite_"):
                continue
            try:
                cursor.execute(f"DROP TABLE IF EXISTS [{tbl}];")
            except sqlite3.OperationalError as err:
                logger.debug(f"[TelemetrySchemaManager] Не удалось удалить устаревшую таблицу {tbl}: {err}")


init_database_schema = TelemetrySchemaManager.initialize_schema


