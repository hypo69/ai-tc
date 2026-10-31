# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Database Adapter Tests
# =============================================================================
# Description:
#   Модульные тесты для универсального адаптера базы данных DatabaseAdapter
#   (проверка SQLite и MariaDB режимов, адаптации параметров и fallback).
#
# File: test_db_adapter.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-13 20:39:00
# =============================================================================

from __future__ import annotations

import json
import time
import pytest
from apps.windows.db.db_adapter import DatabaseAdapter


@pytest.fixture
def sqlite_adapter() -> DatabaseAdapter:
    """Фикстура изолированного SQLite адаптера в оперативной памяти."""
    cfg = {
        "engine": "sqlite",
        "sqlite": {"path": ":memory:"},
        "mariadb": {},
    }
    adapter = DatabaseAdapter(config=cfg)
    return adapter


def test_sqlite_adapter_crud(sqlite_adapter: DatabaseAdapter):
    """Тестирование CRUD операций и адаптации параметров в SQLite."""
    assert sqlite_adapter.ping() is True

    # 1. Insert / Upsert
    sql = """
    INSERT INTO wikillm_knowledge 
        (canonical_key, title, category, description, is_verified, claims_json, remediation_json, updated_at)
    VALUES 
        (:key, :title, :category, :description, :verified, :claims, :remediation, :updated)
    ON DUPLICATE KEY UPDATE 
        title = :title, 
        category = :category, 
        description = :description, 
        is_verified = :verified, 
        claims_json = :claims, 
        remediation_json = :remediation, 
        updated_at = :updated
    """
    params = {
        "key": "win_event_test",
        "title": "Тестовое событие",
        "category": "security",
        "description": "Описание тестового события",
        "verified": 1,
        "claims": json.dumps(["Факт 1"]),
        "remediation": json.dumps(["Действие 1"]),
        "updated": time.time(),
    }
    sqlite_adapter.execute(sql, params)

    # 2. Fetch One
    row = sqlite_adapter.fetch_one(
        "SELECT * FROM wikillm_knowledge WHERE canonical_key = :key",
        {"key": "win_event_test"},
    )
    assert row is not None
    assert row["canonical_key"] == "win_event_test"
    assert row["title"] == "Тестовое событие"
    assert row["category"] == "security"

    # 3. Fetch All
    rows = sqlite_adapter.fetch_all(
        "SELECT * FROM wikillm_knowledge WHERE category = :cat",
        {"cat": "security"},
    )
    assert len(rows) == 1
    assert rows[0]["canonical_key"] == "win_event_test"

    # 4. Delete
    deleted_count = sqlite_adapter.execute(
        "DELETE FROM wikillm_knowledge WHERE canonical_key = :key",
        {"key": "win_event_test"},
    )
    assert deleted_count == 1

    row_after = sqlite_adapter.fetch_one(
        "SELECT * FROM wikillm_knowledge WHERE canonical_key = :key",
        {"key": "win_event_test"},
    )
    assert row_after is None


def test_mariadb_unreachable_fallback():
    """Тестирование штатного перехода на SQLite при недоступном сервере MariaDB."""
    cfg = {
        "engine": "mariadb",
        "sqlite": {"path": ":memory:"},
        "mariadb": {
            "host": "192.0.2.1",  # Тестовый несуществующий адрес (TEST-NET)
            "port": 3306,
            "user": "invalid",
            "password": "invalid",
            "database": "invalid",
            "connect_timeout": 1,
        },
    }
    # При сбое MariaDB адаптер автоматически переключается на SQLite
    adapter = DatabaseAdapter(config=cfg)
    assert adapter.engine == "sqlite"
    assert adapter.ping() is True


def test_global_db_adapter_import():
    """Проверка доступности глобального экземпляра db_adapter."""
    from apps.windows.db import db_adapter as global_adapter
    assert global_adapter is not None
    assert hasattr(global_adapter, "fetch_all")
    assert hasattr(global_adapter, "execute")
    assert global_adapter.ping() is True

