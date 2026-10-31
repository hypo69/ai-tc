# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api - Router WikiLLM Editor
# =============================================================================
# Description:
#   Реализует эндпоинты для работы с БД WikiLLM: проверка соединения, инициализация,
#   миграция данных из SQLite и получение списка профилей.
#
# File: router_wikillm_editor.py
# Project: ai-windows-admin
# Package: apps.windows.api
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 02:58:00
# =============================================================================

"""Router, предоставляющий API для управления базой WikiLLM.

Эндпоинты (префикс ``/api/v1/wikillm``):
- ``POST /db/test``   – проверка соединения с MariaDB (или fallback к SQLite).
- ``POST /db/init``   – создание таблицы ``wiki_llm_profiles`` при необходимости.
- ``POST /db/migrate`` – миграция профилей из локального ``wiki_llm.db`` (SQLite) в MariaDB.
- ``GET  /profiles`` – получение всех профилей; при отсутствии таблицы возвращает пустой список.

Все сообщения выводятся в консоль через ``logger.console``.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, List, Dict

from fastapi import APIRouter, HTTPException, status
from logger import logger
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, ProgrammingError

router = APIRouter(prefix="/api/v1/wikillm", tags=["WikiLLM DB Editor"])

# ---------------------------------------------------------------------------
# Вспомогательные функции для доступа к конфигурации БД
# ---------------------------------------------------------------------------

def _load_db_config() -> Dict[str, Any]:
    """Читает конфигурацию БД из ``apps/windows/api/config.json``.

    Возвращает словарь с параметрами MariaDB и SQLite. При ошибке выводит
    сообщение в консоль и возвращает пустой словарь.
    """
    cfg_path = Path(__file__).parent / "config.json"
    if not cfg_path.is_file():
        cfg_path = Path(__file__).parents[1] / "api" / "config.json"
    if not cfg_path.is_file():
        logger.console(f"Конфиг БД не найден: {cfg_path}")
        return {}
    with cfg_path.open("r", encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg.get("database", {})

def _engine_mariadb() -> Any:
    """Создаёт SQLAlchemy engine для MariaDB согласно конфигу.

    Если параметры недоступны, бросает ``HTTPException``.
    """
    db_cfg = _load_db_config()
    mariadb_cfg = db_cfg.get("mariadb")
    if not mariadb_cfg:
        raise HTTPException(status_code=500, detail="MariaDB config missing")
    user = mariadb_cfg.get("user")
    password = mariadb_cfg.get("password")
    host = mariadb_cfg.get("host")
    port = mariadb_cfg.get("port", 3306)
    database = mariadb_cfg.get("database")
    dsn = f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"
    try:
        engine = create_engine(dsn, pool_pre_ping=True, future=True)
        return engine
    except Exception as exc:
        logger.console(f"Не удалось создать engine для MariaDB: {exc}")
        raise HTTPException(status_code=500, detail="Engine creation failed")

def _engine_sqlite() -> Any:
    """Engine для локальной SQLite базы (telemetry.db)."""
    db_cfg = _load_db_config()
    sqlite_cfg = db_cfg.get("sqlite", {})
    path = sqlite_cfg.get("path", "telemetry.db")
    dsn = f"sqlite+pysqlite:///{path}"
    return create_engine(dsn, future=True)

# ---------------------------------------------------------------------------
# Эндпоинты
# ---------------------------------------------------------------------------

@router.post("/db/test")
async def test_connection() -> Dict[str, Any]:
    """Проверка соединения с MariaDB.

    Возвращает JSON ``{"ok": true}`` при успешном подключении, иначе ``{"ok": false, "error": "..."}``.
    """
    try:
        engine = _engine_mariadb()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.console("Успешное соединение с MariaDB")
        return {"ok": True}
    except OperationalError as exc:
        logger.console(f"Ошибка соединения MariaDB: {exc}")
        return {"ok": False, "error": str(exc)}

@router.post("/db/init")
async def init_wikillm_table() -> Dict[str, Any]:
    """Создаёт таблицу ``wiki_llm_profiles`` при её отсутствии.

    Таблица имеет простую схему: ``id`` (INT PK AUTO_INCREMENT), ``profile_name``
    (VARCHAR), ``data`` (JSON), ``created_at`` (TIMESTAMP).
    """
    sql = """
    CREATE TABLE IF NOT EXISTS wiki_llm_profiles (
        id INT PRIMARY KEY AUTO_INCREMENT,
        profile_name VARCHAR(255) NOT NULL,
        data JSON NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    try:
        engine = _engine_mariadb()
        with engine.begin() as conn:
            conn.execute(text(sql))
        logger.console("Таблица wiki_llm_profiles инициализирована")
        return {"status": "initialized"}
    except Exception as exc:
        logger.console(f"Ошибка инициализации таблицы: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

@router.post("/db/migrate")
async def migrate_profiles() -> Dict[str, Any]:
    """Перенос профилей из локального SQLite ``wiki_llm.db`` в MariaDB.

    При отсутствии SQLite‑файла возвращает статус ``no_source``.
    """
    sqlite_path = Path(__file__).parents[2] / "wiki_llm.db"
    if not sqlite_path.is_file():
        logger.console(f"SQLite файл {sqlite_path} не найден, миграция пропущена")
        return {"status": "no_source"}

    src_conn = sqlite3.connect(sqlite_path)
    src_cur = src_conn.cursor()
    try:
        src_cur.execute("SELECT profile_name, data FROM wiki_llm_profiles")
        rows = src_cur.fetchall()
    except sqlite3.OperationalError:
        logger.console("Таблица wiki_llm_profiles в SQLite отсутствует")
        src_conn.close()
        return {"status": "no_table"}
    src_conn.close()

    if not rows:
        logger.console("Нет профилей для миграции")
        return {"status": "empty"}

    engine = _engine_mariadb()
    insert_sql = text(
        "INSERT INTO wiki_llm_profiles (profile_name, data) VALUES (:name, :data) "
        "ON DUPLICATE KEY UPDATE data = VALUES(data)"
    )
    with engine.begin() as conn:
        for name, data in rows:
            json_data = json.dumps(json.loads(data) if isinstance(data, str) else data)
            conn.execute(insert_sql, {"name": name, "data": json_data})
    logger.console(f"Мигрировано {len(rows)} профилей в MariaDB")
    return {"status": "migrated", "count": len(rows)}

@router.get("/profiles")
async def list_profiles() -> List[Dict[str, Any]]:
    """Возвращает список всех профилей WikiLLM.

    Если таблица отсутствует или база данных недоступна – возвращает список по умолчанию.
    """
    default_profiles = [
        {"profile_name": "fast", "data": {"top_k": 3, "fetch_k": 10, "score_threshold": 0.60, "reranker_enabled": False, "rerank_top_n": 3, "temperature": 0.1, "max_context_tokens": 2048, "grounding_required": False}},
        {"profile_name": "balanced", "data": {"top_k": 5, "fetch_k": 20, "score_threshold": 0.70, "reranker_enabled": True, "rerank_top_n": 5, "temperature": 0.2, "max_context_tokens": 4096, "grounding_required": True}},
        {"profile_name": "precise", "data": {"top_k": 8, "fetch_k": 30, "score_threshold": 0.85, "reranker_enabled": True, "rerank_top_n": 5, "temperature": 0.0, "max_context_tokens": 8192, "grounding_required": True}},
    ]
    try:
        engine = _engine_mariadb()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT profile_name, data FROM wiki_llm_profiles"))
            profiles = [{"profile_name": row[0], "data": json.loads(row[1]) if isinstance(row[1], str) else row[1]} for row in result]
        return profiles if profiles else default_profiles
    except ProgrammingError as exc:
        logger.console(f"Таблица wiki_llm_profiles отсутствует: {exc}")
        return default_profiles
    except Exception as exc:
        logger.console(f"MariaDB недоступна, возврат стандартных профилей WikiLLM: {exc}")
        return default_profiles

def init_router() -> APIRouter:
    """Возвращает инициализированный роутер для подключения к FastAPI.
    """
    return router

__all__ = ["router", "init_router"]

