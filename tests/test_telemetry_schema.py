# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Telemetry SQLite Schema
# =============================================================================
# Description:
#   Тесты схемы SQLite телеметрии: идентичность эталону, снятому до декомпозиции
#   schema.py (этап 4 ТЗ оптимизации), и идемпотентность init_database_schema.
#
# File: test_telemetry_schema.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-16 20:45:00
# =============================================================================

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from apps.windows.telemetry.sqlite.schema import init_database_schema

BASELINE_PATH = Path(__file__).parent / 'api_baselines' / 'telemetry_schema.json'
QUERY = "SELECT type, name, tbl_name, COALESCE(sql, '') FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"


def _dump(conn: sqlite3.Connection) -> list[dict[str, str]]:
    """Снимает описание всех объектов схемы."""
    return [{'type': t, 'name': n, 'tbl': tb, 'sql': s} for t, n, tb, s in conn.execute(QUERY).fetchall()]


def test_schema_matches_baseline() -> None:
    """Схема свежей БД совпадает с эталоном: те же таблицы, индексы и их DDL."""
    conn = sqlite3.connect(':memory:')
    init_database_schema(conn)
    baseline = json.loads(BASELINE_PATH.read_text(encoding='utf-8'))
    assert _dump(conn) == baseline


def test_schema_init_is_idempotent() -> None:
    """Повторная инициализация не меняет схему и не падает."""
    conn = sqlite3.connect(':memory:')
    init_database_schema(conn)
    first = _dump(conn)
    init_database_schema(conn)
    assert _dump(conn) == first


def test_legacy_process_file_events_migration() -> None:
    """Устаревшая таблица process_file_events с битым FK на process_instance успешно мигрирует."""
    conn = sqlite3.connect(':memory:')
    # Создаем устаревшую структуру
    conn.execute('''
        CREATE TABLE process_file_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            pid INTEGER NOT NULL DEFAULT 0,
            process_name TEXT NOT NULL DEFAULT '',
            action_type TEXT NOT NULL DEFAULT '',
            target_directory TEXT NOT NULL DEFAULT '',
            file_path TEXT NOT NULL,
            bytes_affected INTEGER DEFAULT 0,
            instance_id INTEGER,
            timestamp TEXT NOT NULL DEFAULT (datetime('now')),
            created_at REAL DEFAULT 0.0,
            io_rate_bytes_sec REAL DEFAULT 0.0,
            details_json TEXT,
            FOREIGN KEY (instance_id) REFERENCES process_instance(instance_id) ON DELETE CASCADE
        );
    ''')
    conn.execute('''
        INSERT INTO process_file_events (
            pid, process_name, action_type, file_path, bytes_affected, created_at
        ) VALUES (1234, 'test.exe', 'WRITE', 'C:\\test.txt', 1024, 1700000000.0);
    ''')
    conn.commit()

    # Запускаем инициализацию / миграцию
    init_database_schema(conn)

    # Включаем FK и проверяем операции
    conn.execute('PRAGMA foreign_keys = ON;')
    rows = conn.execute('SELECT pid, process_name, operation_type, file_path, bytes_transferred FROM process_file_events').fetchall()
    assert len(rows) == 1
    assert rows[0][0] == 1234
    assert rows[0][1] == 'test.exe'
    assert rows[0][2] == 'WRITE'
    assert rows[0][3] == 'C:\\test.txt'
    assert rows[0][4] == 1024

    # Проверяем, что удаление не вызывает ошибку no such table: main.process_instance
    conn.execute('DELETE FROM process_file_events WHERE pid = 1234;')
    conn.commit()
    assert conn.execute('SELECT COUNT(*) FROM process_file_events').fetchone()[0] == 0


def test_legacy_process_snapshots_not_null_migration() -> None:
    """Таблица process_snapshots со старым ограничением NOT NULL на snapshot_id мигрирует на nullable snapshot_id."""
    conn = sqlite3.connect(':memory:')
    # Создаем устаревшую структуру с snapshot_id INTEGER NOT NULL
    conn.execute('''
        CREATE TABLE process_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            pid INTEGER NOT NULL,
            name TEXT NOT NULL
        );
    ''')
    conn.execute('''
        INSERT INTO process_snapshots (snapshot_id, timestamp, pid, name)
        VALUES (42, '2026-10-16T12:00:00', 1234, 'service.exe');
    ''')
    conn.commit()

    # Запускаем инициализацию / миграцию схемы
    init_database_schema(conn)

    # Проверяем, что существующая строка сохранилась
    rows = conn.execute("SELECT id, snapshot_id, pid, name, sample_type FROM process_snapshots WHERE pid = 1234").fetchall()
    assert len(rows) == 1
    assert rows[0][1] == 42
    assert rows[0][2] == 1234
    assert rows[0][3] == 'service.exe'
    assert rows[0][4] == 'snapshot'

    # Проверяем, что теперь можно вставлять запись с snapshot_id = NULL (например, сетевая активность)
    conn.execute('''
        INSERT INTO process_snapshots (sample_type, timestamp, pid, name)
        VALUES ('network', '2026-10-16T12:05:00', 5678, 'browser.exe');
    ''')
    conn.commit()

    net_row = conn.execute("SELECT snapshot_id, pid, name, sample_type FROM process_snapshots WHERE pid = 5678").fetchone()
    assert net_row[0] is None
    assert net_row[1] == 5678
    assert net_row[2] == 'browser.exe'
    assert net_row[3] == 'network'



