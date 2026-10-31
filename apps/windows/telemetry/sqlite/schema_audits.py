# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry Sqlite - Schema Audits
# =============================================================================
# Description:
#   DDL-определения жизненного цикла процессов, инцидентов и Change-Only
#   инвентаризации ОС (4 из 12 таблиц):
#   process_lifecycle_sessions, incidents, inventory_state, inventory_changes.
#
# File: schema_audits.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry.sqlite
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-16 12:55:00
# =============================================================================

from __future__ import annotations

"""DDL-определения сессий жизненного цикла процессов, инцидентов и Change-Only состояния ОС."""

from typing import Tuple

from .delta_inventory import DELTA_INVENTORY_DDL, DELTA_INVENTORY_INDEX_DDL

AUDITS_SCHEMA_DDL: Tuple[str, ...] = (
    # 7. Жизненный цикл, генеалогия (lineage), provenance и ресурсные пики процессов
    '''
    CREATE TABLE IF NOT EXISTS process_lifecycle_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        instance_id TEXT NOT NULL UNIQUE,
        definition_id INTEGER DEFAULT 1,
        parent_instance_id INTEGER,
        pid INTEGER NOT NULL,
        ppid INTEGER,
        name TEXT NOT NULL,
        friendly_name TEXT,
        exe_path TEXT,
        binary_hash TEXT,
        icon_base64 TEXT,
        cmdline TEXT,
        username TEXT,
        sid TEXT,
        session_id INTEGER DEFAULT 1,
        integrity_level TEXT,
        parent_name TEXT,
        parent_exe TEXT,
        parent_guid TEXT,
        initiator_type TEXT,
        status TEXT DEFAULT 'RUNNING',
        created_at TEXT NOT NULL,
        created_ts REAL NOT NULL,
        terminated_at TEXT,
        terminated_ts REAL,
        is_alive INTEGER NOT NULL DEFAULT 1,
        lifetime_sec REAL DEFAULT 0.0,
        exit_code INTEGER,
        cpu_time_user_sec REAL DEFAULT 0.0,
        cpu_time_kernel_sec REAL DEFAULT 0.0,
        cpu_time_total_sec REAL DEFAULT 0.0,
        cpu_cycles INTEGER,
        peak_working_set_mb REAL DEFAULT 0.0,
        peak_private_mb REAL DEFAULT 0.0,
        io_read_bytes INTEGER DEFAULT 0,
        io_write_bytes INTEGER DEFAULT 0,
        io_read_ops INTEGER DEFAULT 0,
        io_write_ops INTEGER DEFAULT 0,
        files_accessed_json TEXT,
        remote_endpoints_json TEXT,
        raw_json TEXT
    );
    ''',
    # 9. Единый журнал инцидентов, сбоев, аномалий, всплесков и событий безопасности/ОС
    '''
    CREATE TABLE IF NOT EXISTS incidents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        incident_id TEXT UNIQUE,
        timestamp TEXT NOT NULL,
        created_at REAL NOT NULL,
        domain TEXT NOT NULL DEFAULT 'incident',
        trigger_type TEXT NOT NULL DEFAULT 'event',
        severity TEXT NOT NULL DEFAULT 'INFO',
        title TEXT NOT NULL DEFAULT '',
        channel TEXT,
        event_id INTEGER,
        event_record_id INTEGER,
        provider_name TEXT,
        sensor_id TEXT,
        device_id TEXT,
        app_name TEXT,
        value REAL,
        baseline_mean REAL,
        baseline_sigma REAL,
        deviation_factor REAL,
        unit TEXT,
        window_start TEXT,
        window_end TEXT,
        duration_sec REAL DEFAULT 0.0,
        trigger_metrics_json TEXT,
        suspect_processes_json TEXT,
        related_events_json TEXT,
        metrics_summary_json TEXT,
        raw_window_json TEXT,
        message TEXT,
        details_json TEXT,
        raw_xml TEXT,
        resolved INTEGER DEFAULT 0
    );
    ''',
    # 11 & 12. Change-Only инвентаризация состояния и дельт ОС (inventory_state, inventory_changes)
    *DELTA_INVENTORY_DDL,
)

AUDITS_INDEX_DDL: Tuple[str, ...] = (
    'CREATE INDEX IF NOT EXISTS idx_pls_name_ts ON process_lifecycle_sessions(name, created_ts DESC);',
    'CREATE INDEX IF NOT EXISTS idx_pls_user_ts ON process_lifecycle_sessions(username, created_ts DESC);',
    'CREATE INDEX IF NOT EXISTS idx_pls_parent_ts ON process_lifecycle_sessions(parent_name, created_ts DESC);',
    'CREATE INDEX IF NOT EXISTS idx_pls_pid_ts ON process_lifecycle_sessions(pid, created_ts DESC);',
    'CREATE INDEX IF NOT EXISTS idx_pls_alive ON process_lifecycle_sessions(is_alive, created_ts DESC);',
    'CREATE INDEX IF NOT EXISTS idx_incidents_created ON incidents(created_at DESC);',
    'CREATE INDEX IF NOT EXISTS idx_incidents_domain ON incidents(domain, created_at DESC);',
    'CREATE INDEX IF NOT EXISTS idx_incidents_trigger ON incidents(trigger_type, severity);',
    'CREATE INDEX IF NOT EXISTS idx_incidents_channel ON incidents(channel, created_at DESC);',
    *DELTA_INVENTORY_INDEX_DDL,
)

