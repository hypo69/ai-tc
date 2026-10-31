# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry Sqlite - Schema Security
# =============================================================================
# Description:
#   DDL-определения сессий питания, перезагрузок, BSOD и простоев (1 из 12 таблиц):
#   power_sessions.
#
# File: schema_security.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry.sqlite
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-16 12:55:00
# =============================================================================

from __future__ import annotations

"""DDL-определение единой таблицы сессий питания, перезагрузок и сбоев ядра."""

from typing import Tuple

SECURITY_SCHEMA_DDL: Tuple[str, ...] = (
    # 10. Единая таблица сессий питания, перезагрузок, BSOD, событий питания и разрывов
    '''
    CREATE TABLE IF NOT EXISTS power_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL UNIQUE,
        record_type TEXT NOT NULL DEFAULT 'session',
        boot_time TEXT NOT NULL,
        boot_timestamp REAL NOT NULL,
        shutdown_time TEXT,
        shutdown_timestamp REAL,
        uptime_seconds REAL DEFAULT 0.0,
        uptime_human TEXT,
        shutdown_type TEXT NOT NULL,
        classification TEXT,
        confidence TEXT,
        initiator TEXT,
        user TEXT,
        domain TEXT,
        process TEXT,
        process_id INTEGER,
        reason TEXT,
        reason_code TEXT,
        comment TEXT,
        summary TEXT,
        clean_shutdown INTEGER DEFAULT 1,
        unexpected_shutdown INTEGER DEFAULT 0,
        bugcheck TEXT,
        bugcheck_code TEXT,
        bugcheck_params_json TEXT,
        dump_file TEXT,
        boot_event_id INTEGER DEFAULT 12,
        shutdown_event_id INTEGER,
        event_id INTEGER,
        provider TEXT,
        channel TEXT,
        initiator_chain_json TEXT,
        events_json TEXT,
        evidence_json TEXT,
        details_json TEXT,
        raw_xml TEXT,
        created_at REAL NOT NULL
    );
    ''',
)

SECURITY_INDEX_DDL: Tuple[str, ...] = (
    'CREATE INDEX IF NOT EXISTS idx_psess_boot_ts ON power_sessions(boot_timestamp DESC);',
    'CREATE INDEX IF NOT EXISTS idx_psess_type ON power_sessions(record_type, created_at DESC);',
    'CREATE INDEX IF NOT EXISTS idx_psess_shutdown_type ON power_sessions(shutdown_type);',
)

