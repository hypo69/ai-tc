# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - WikiLLM MariaDB Management
# =============================================================================
# Description:
#   Тестирование API эндпоинтов управления базой данных WikiLLM:
#   конфигурация, проверка доступности MariaDB, инициализация таблиц и импорт SQLite.
#
# File: test_wikillm_mariadb_management.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 17:25:00
# =============================================================================

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.windows.api.routers.router_wikillm_editor import router


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Инициализация тестового клиента FastAPI с роутером WikiLLM Editor."""
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_get_db_configuration(client: TestClient) -> None:
    """Проверка получения конфигурации базы данных."""
    response = client.get("/api/v1/wikillm/db/config")
    assert response.status_code == 200
    data = response.json()
    assert "engine" in data
    assert "mariadb" in data
    assert "sqlite" in data
    mariadb = data["mariadb"]
    assert "connection_type" in mariadb
    assert "php_api_url" in mariadb


def test_save_db_configuration_php_api(client: TestClient) -> None:
    """Проверка сохранения настроек с методом php_api."""
    cfg_payload = {
        "engine": "mariadb",
        "mariadb": {
            "connection_type": "php_api",
            "host": "srv1502.hstgr.io",
            "port": 3306,
            "database": "u177424397_comp_knowledge",
            "user": "u177424397_davidka",
            "password": "@Davidka#1969",
            "ip_fallback": "77.37.35.16",
            "connect_timeout": 10,
            "php_api_url": "https://srv1502.hstgr.io/wikillm_hostinger.php",
            "php_api_key": "test_token_123"
        },
        "sqlite_path": "data/windows_wikillm/knowledge.db"
    }
    save_res = client.post("/api/v1/wikillm/db/config", json=cfg_payload)
    assert save_res.status_code == 200
    save_data = save_res.json()
    assert save_data.get("ok") is True

    # Проверка считывания
    get_res = client.get("/api/v1/wikillm/db/config")
    assert get_res.status_code == 200
    saved_cfg = get_res.json()
    assert saved_cfg["mariadb"]["connection_type"] == "php_api"
    assert saved_cfg["mariadb"]["php_api_key"] == "test_token_123"

    # Возвращаем активный движок обратно на локальный SQLite после теста
    cfg_payload["engine"] = "sqlite"
    client.post("/api/v1/wikillm/db/config", json=cfg_payload)


def test_check_sqlite_db_connection_and_init(client: TestClient) -> None:
    """Проверка локальной базы подсказок SQLite без обращения к PHP API."""
    check_res = client.post(
        "/api/v1/wikillm/db/check",
        json={"engine": "sqlite", "sqlite_path": "data/windows_wikillm/knowledge.db"},
    )
    assert check_res.status_code == 200
    data = check_res.json()
    assert data.get("ok") is True
    assert data.get("connected") is True
    assert data.get("engine") == "sqlite"
    assert "Ошибка сети при обращении к PHP API" not in data.get("message", "")

    init_res = client.post(
        "/api/v1/wikillm/db/init-tables",
        json={"engine": "sqlite", "sqlite_path": "data/windows_wikillm/knowledge.db"},
    )
    assert init_res.status_code == 200
    init_data = init_res.json()
    assert init_data.get("ok") is True
    assert init_data.get("engine") == "sqlite"


def test_check_db_connection_flow(client: TestClient) -> None:
    """Проверка подключения к MariaDB и аудита таблиц."""
    # Тестируем проверку при прямом подключении
    response = client.post("/api/v1/wikillm/db/check", json={"connection_type": "direct"})
    assert response.status_code == 200
    data = response.json()
    assert "ok" in data
    assert "stage" in data
    assert "database_exists" in data


def test_init_tables_and_import(client: TestClient) -> None:
    """Проверка инициализации пустых таблиц и импорта из SQLite."""
    # 1. Инициализация таблиц
    init_res = client.post("/api/v1/wikillm/db/init-tables", json={"connection_type": "direct"})
    assert init_res.status_code == 200
    init_data = init_res.json()
    assert init_data.get("ok") is True

    # 2. Импорт из локальной SQLite
    import_res = client.post("/api/v1/wikillm/db/import-sqlite", json={"connection_type": "direct"})
    assert import_res.status_code == 200
    import_data = import_res.json()
    assert import_data.get("ok") is True
    assert "imported_knowledge" in import_data

