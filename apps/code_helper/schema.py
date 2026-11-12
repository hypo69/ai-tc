# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Code Helper - Database Schemas & DDL
# =============================================================================
# Description:
#   Декларативные схемы таблиц (DDL) для MariaDB на Hostinger и SQLite:
#   индексы кодовой базы, чанки кода, таблица символов AST и логи диагностики.
#
# File: schema.py
# Project: ai-windows-admin
# Package: apps.code_helper
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 17:10:00
# =============================================================================

from __future__ import annotations

"""Схемы таблиц базы данных для Hostinger MariaDB и SQLite."""

MARIADB_INIT_QUERIES = [
    """
    CREATE TABLE IF NOT EXISTS code_indexes (
        name VARCHAR(120) PRIMARY KEY,
        project_root TEXT,
        total_files INT NOT NULL DEFAULT 0,
        total_chunks INT NOT NULL DEFAULT 0,
        total_symbols INT NOT NULL DEFAULT 0,
        elapsed_seconds FLOAT NOT NULL DEFAULT 0.0,
        updated_at VARCHAR(40) NOT NULL,
        storage_engine VARCHAR(30) NOT NULL DEFAULT 'mariadb'
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """,
    """
    CREATE TABLE IF NOT EXISTS code_chunks (
        chunk_id VARCHAR(255) PRIMARY KEY,
        index_name VARCHAR(120) NOT NULL,
        file_path VARCHAR(500) NOT NULL,
        symbol_name VARCHAR(255) DEFAULT '',
        symbol_type VARCHAR(50) DEFAULT 'module',
        start_line INT NOT NULL DEFAULT 1,
        end_line INT NOT NULL DEFAULT 1,
        content MEDIUMTEXT NOT NULL,
        signature TEXT,
        docstring MEDIUMTEXT,
        snippet MEDIUMTEXT,
        content_hash VARCHAR(64) DEFAULT '',
        updated_at VARCHAR(40) NOT NULL,
        INDEX idx_chk_index (index_name),
        INDEX idx_chk_symbol (symbol_name),
        INDEX idx_chk_path (file_path(255))
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """,
    """
    CREATE TABLE IF NOT EXISTS code_symbols (
        symbol_id VARCHAR(255) PRIMARY KEY,
        index_name VARCHAR(120) NOT NULL,
        symbol VARCHAR(255) NOT NULL,
        short_name VARCHAR(255) NOT NULL,
        symbol_type VARCHAR(50) NOT NULL DEFAULT 'function',
        file_path VARCHAR(500) NOT NULL,
        signature TEXT,
        docstring MEDIUMTEXT,
        start_line INT NOT NULL DEFAULT 1,
        end_line INT NOT NULL DEFAULT 1,
        related_symbols_json TEXT,
        snippet MEDIUMTEXT,
        updated_at VARCHAR(40) NOT NULL,
        INDEX idx_sym_index (index_name),
        INDEX idx_sym_symbol (symbol),
        INDEX idx_sym_short (short_name)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """,
    """
    CREATE TABLE IF NOT EXISTS code_diagnostics (
        id VARCHAR(64) PRIMARY KEY,
        query TEXT,
        error_message TEXT,
        summary TEXT NOT NULL,
        root_cause TEXT NOT NULL,
        explanation MEDIUMTEXT NOT NULL,
        severity VARCHAR(30) NOT NULL DEFAULT 'error',
        confidence FLOAT NOT NULL DEFAULT 0.85,
        affected_locations_json MEDIUMTEXT,
        remediation_steps_json MEDIUMTEXT,
        created_at VARCHAR(40) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """,
]

SQLITE_INIT_SCRIPT = """
CREATE TABLE IF NOT EXISTS code_indexes (
    name TEXT PRIMARY KEY,
    project_root TEXT,
    total_files INTEGER DEFAULT 0,
    total_chunks INTEGER DEFAULT 0,
    total_symbols INTEGER DEFAULT 0,
    elapsed_seconds REAL DEFAULT 0.0,
    updated_at TEXT NOT NULL,
    storage_engine TEXT DEFAULT 'sqlite'
);
CREATE TABLE IF NOT EXISTS code_chunks (
    chunk_id TEXT PRIMARY KEY,
    index_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    symbol_name TEXT DEFAULT '',
    symbol_type TEXT DEFAULT 'module',
    start_line INTEGER DEFAULT 1,
    end_line INTEGER DEFAULT 1,
    content TEXT NOT NULL,
    signature TEXT DEFAULT '',
    docstring TEXT DEFAULT '',
    snippet TEXT DEFAULT '',
    content_hash TEXT DEFAULT '',
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chk_index ON code_chunks(index_name);
CREATE INDEX IF NOT EXISTS idx_chk_symbol ON code_chunks(symbol_name);
CREATE INDEX IF NOT EXISTS idx_chk_path ON code_chunks(file_path);

CREATE TABLE IF NOT EXISTS code_symbols (
    symbol_id TEXT PRIMARY KEY,
    index_name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    short_name TEXT NOT NULL,
    symbol_type TEXT DEFAULT 'function',
    file_path TEXT NOT NULL,
    signature TEXT DEFAULT '',
    docstring TEXT DEFAULT '',
    start_line INTEGER DEFAULT 1,
    end_line INTEGER DEFAULT 1,
    related_symbols_json TEXT DEFAULT '[]',
    snippet TEXT DEFAULT '',
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sym_index ON code_symbols(index_name);
CREATE INDEX IF NOT EXISTS idx_sym_name ON code_symbols(symbol);
CREATE INDEX IF NOT EXISTS idx_sym_short ON code_symbols(short_name);

CREATE TABLE IF NOT EXISTS code_diagnostics (
    id TEXT PRIMARY KEY,
    query TEXT DEFAULT '',
    error_message TEXT DEFAULT '',
    summary TEXT NOT NULL,
    root_cause TEXT NOT NULL,
    explanation TEXT NOT NULL,
    severity TEXT DEFAULT 'error',
    confidence REAL DEFAULT 0.85,
    affected_locations_json TEXT DEFAULT '[]',
    remediation_steps_json TEXT DEFAULT '[]',
    created_at TEXT NOT NULL
);
"""
