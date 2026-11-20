# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Test Router DB Manager
# =============================================================================
# Description:
#   Инженерные TDD тесты для сервиса и REST API управления базами данных:
#   - Обзор параметров, метрик и таблиц (SQLite и Hostinger MariaDB);
#   - Прямой ввод и выполнение команд SQL (SELECT, INSERT, UPDATE, DELETE);
#   - Инструменты сжатия и оптимизации (SQLite VACUUM, wal_checkpoint);
#   - Экспорт таблиц в форматы SQL, JSON и CSV;
#   - Создание бэкапов с ZIP-сжатием, скачивание, восстановление и удаление.
#
# File: test_router_db_manager.py
# Project: ai-tc
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-19 17:25:00
# =============================================================================

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.windows.db.db_manager_service import DBManagerService
from apps.windows.api.routers.router_db_manager import init_router


@pytest.fixture
def temp_db_env(tmp_path: Path):
    """Создает изолированную тестовую среду с тестовой базой SQLite."""
    base_dir = tmp_path
    backups_dir = tmp_path / "backups"
    exports_dir = tmp_path / "exports"
    db_file = tmp_path / "test_sample.db"

    # Инициализация тестовой таблицы
    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, role TEXT, score REAL);")
    conn.execute("INSERT INTO users (name, role, score) VALUES ('Alice', 'admin', 98.5);")
    conn.execute("INSERT INTO users (name, role, score) VALUES ('Bob', 'engineer', 84.0);")
    conn.commit()
    conn.close()

    service = DBManagerService(base_dir=base_dir, backups_dir=backups_dir, exports_dir=exports_dir)
    return {
        "service": service,
        "db_file": db_file,
        "backups_dir": backups_dir,
        "exports_dir": exports_dir,
    }


def test_service_overview_and_parameters(temp_db_env):
    """Проверяет получение обзора и параметров баз данных."""
    service: DBManagerService = temp_db_env["service"]
    overview = service.get_overview()

    assert "targets" in overview
    assert "server_time" in overview
    targets = overview["targets"]
    assert len(targets) >= 3

    # Проверяем наличие ключевых полей
    for t in targets:
        assert "id" in t
        assert "type" in t
        assert "status" in t


def test_service_query_select_and_dml(temp_db_env):
    """Проверяет прямое выполнение команд SELECT, INSERT, UPDATE, DELETE."""
    service: DBManagerService = temp_db_env["service"]
    db_path = str(temp_db_env["db_file"])

    # 1. SELECT
    sel_res = service.execute_query(db_path, "SELECT * FROM users ORDER BY id;")
    assert sel_res["success"] is True
    assert sel_res["is_query"] is True
    assert sel_res["row_count"] == 2
    assert "Alice" in [r["name"] for r in sel_res["rows"]]
    assert "Bob" in [r["name"] for r in sel_res["rows"]]

    # 2. INSERT
    ins_res = service.execute_query(db_path, "INSERT INTO users (name, role, score) VALUES ('Charlie', 'tester', 76.0);")
    assert ins_res["success"] is True
    assert ins_res["affected_rows"] == 1

    # 3. UPDATE
    upd_res = service.execute_query(db_path, "UPDATE users SET score = 100.0 WHERE name = 'Charlie';")
    assert upd_res["success"] is True
    assert upd_res["affected_rows"] == 1

    # Проверка обновленного значения
    check_res = service.execute_query(db_path, "SELECT score FROM users WHERE name = 'Charlie';")
    assert check_res["rows"][0]["score"] == 100.0

    # 4. DELETE
    del_res = service.execute_query(db_path, "DELETE FROM users WHERE name = 'Bob';")
    assert del_res["success"] is True
    assert del_res["affected_rows"] == 1

    # Проверка финального количества
    fin_res = service.execute_query(db_path, "SELECT COUNT(*) AS total FROM users;")
    assert fin_res["rows"][0]["total"] == 2


def test_service_compress_vacuum(temp_db_env):
    """Проверяет сжатие базы через VACUUM."""
    service: DBManagerService = temp_db_env["service"]
    db_path = str(temp_db_env["db_file"])

    comp_res = service.compress_database(db_path, action="vacuum")
    assert comp_res["success"] is True
    assert comp_res["action"] == "vacuum"
    assert "before_bytes" in comp_res
    assert "after_bytes" in comp_res
    assert comp_res["after_bytes"] > 0


def test_service_export_sql_json_csv(temp_db_env):
    """Проверяет экспорт базы в форматы SQL Dump, JSON и CSV."""
    service: DBManagerService = temp_db_env["service"]
    db_path = str(temp_db_env["db_file"])

    # 1. SQL Dump
    exp_sql = service.export_database(db_path, table_name="all", export_format="sql")
    assert exp_sql["success"] is True
    assert exp_sql["format"] == "sql"
    sql_file = Path(exp_sql["filepath"])
    assert sql_file.exists()
    content = sql_file.read_text(encoding="utf-8")
    assert "INSERT INTO `users`" in content
    assert "Alice" in content

    # 2. JSON
    exp_json = service.export_database(db_path, table_name="all", export_format="json")
    assert exp_json["success"] is True
    assert exp_json["format"] == "json"
    json_file = Path(exp_json["filepath"])
    assert json_file.exists()
    data = json.loads(json_file.read_text(encoding="utf-8"))
    assert data["total_records"] >= 2

    # 3. CSV
    exp_csv = service.export_database(db_path, table_name="all", export_format="csv")
    assert exp_csv["success"] is True
    assert exp_csv["format"] == "csv"
    csv_file = Path(exp_csv["filepath"])
    assert csv_file.exists()
    csv_content = csv_file.read_text(encoding="utf-8")
    assert "Alice" in csv_content


def test_service_backup_restore_and_delete(temp_db_env):
    """Проверяет создание бэкапа с ZIP-сжатием, листинг, удаление и восстановление."""
    service: DBManagerService = temp_db_env["service"]
    db_path = str(temp_db_env["db_file"])

    # 1. Создание бэкапа с ZIP
    b_res = service.create_backup(db_path, compress_zip=True)
    assert b_res["success"] is True
    assert b_res["is_compressed"] is True
    assert b_res["filename"].endswith(".zip")
    b_file = Path(b_res["filepath"])
    assert b_file.exists()

    # 2. Список бэкапов
    b_list = service.list_backups()
    assert len(b_list) >= 1
    assert any(b["filename"] == b_res["filename"] for b in b_list)

    # 3. Восстановление
    # Сначала удалим данные в базе
    service.execute_query(db_path, "DELETE FROM users;")
    empty_chk = service.execute_query(db_path, "SELECT COUNT(*) AS total FROM users;")
    assert empty_chk["rows"][0]["total"] == 0

    # Восстанавливаем из бэкапа
    rest_res = service.restore_backup(b_res["filename"], target_id=db_path)
    assert rest_res["success"] is True

    # Проверяем, что данные восстановились
    rest_chk = service.execute_query(db_path, "SELECT COUNT(*) AS total FROM users;")
    assert rest_chk["rows"][0]["total"] == 2

    # 4. Удаление бэкапа
    del_res = service.delete_backup(b_res["filename"])
    assert del_res["success"] is True
    assert not b_file.exists()


def test_fastapi_router_endpoints(temp_db_env):
    """Проверяет REST API эндпоинты через FastAPI TestClient."""
    service: DBManagerService = temp_db_env["service"]
    db_path = str(temp_db_env["db_file"])

    app = FastAPI()
    router = init_router(service)
    app.include_router(router)
    client = TestClient(app)

    # 1. GET /api/v1/db-manager/overview
    ov_resp = client.get("/api/v1/db-manager/overview")
    assert ov_resp.status_code == 200
    assert "targets" in ov_resp.json()

    # 2. POST /api/v1/db-manager/query
    q_resp = client.post("/api/v1/db-manager/query", json={
        "target_id": db_path,
        "sql": "SELECT id, name FROM users;",
    })
    assert q_resp.status_code == 200
    data = q_resp.json()
    assert data["success"] is True
    assert data["row_count"] == 2

    # 3. POST /api/v1/db-manager/compress
    c_resp = client.post("/api/v1/db-manager/compress", json={
        "target_id": db_path,
        "action": "vacuum",
    })
    assert c_resp.status_code == 200
    assert c_resp.json()["success"] is True

    # 4. POST /api/v1/db-manager/export
    e_resp = client.post("/api/v1/db-manager/export", json={
        "target_id": db_path,
        "table_name": "all",
        "export_format": "sql",
    })
    assert e_resp.status_code == 200
    exp_fn = e_resp.json()["filename"]

    # 5. GET /api/v1/db-manager/download/{filename}
    dl_resp = client.get(f"/api/v1/db-manager/download/{exp_fn}")
    assert dl_resp.status_code == 200
    assert "INSERT INTO `users`" in dl_resp.text

    # 6. POST /api/v1/db-manager/backup
    bk_resp = client.post("/api/v1/db-manager/backup", json={
        "target_id": db_path,
        "compress_zip": True,
    })
    assert bk_resp.status_code == 200
    bk_fn = bk_resp.json()["filename"]

    # 7. GET /api/v1/db-manager/backups
    bks_resp = client.get("/api/v1/db-manager/backups")
    assert bks_resp.status_code == 200
    assert bks_resp.json()["count"] >= 1

    # 8. DELETE /api/v1/db-manager/backups/{filename}
    del_resp = client.delete(f"/api/v1/db-manager/backups/{bk_fn}")
    assert del_resp.status_code == 200
    assert del_resp.json()["success"] is True
