# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin AI Instruments - Storage
# =============================================================================
# Description:
#   Хранилище инструментов ИИ-агента (ai_instruments.db).
#   Поддерживает три режима работы:
#     1. Локальный SQLite файл ai_instruments.db
#     2. Прямое TCP-подключение к MariaDB на сервере Hostinger (PyMySQL)
#     3. Удалённый REST API мост на сервере Hostinger (PHP API bridge)
#
# Usage Examples:
#   Python API:
#     from apps.windows.ai_instruments.storage import AIInstrumentsStorage
#
#     storage = AIInstrumentsStorage("data/ai_instruments/ai_instruments.db")
#     tool = storage.save_instrument(inst)
#
# File: storage.py
# Project: ai-windows-admin
# Package: apps.windows.ai_instruments
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 17:31:00
# =============================================================================

from __future__ import annotations

"""Хранилище базы инструментов ИИ-агента (ai_instruments.db) для SQLite и Hostinger MariaDB."""

import json
import os
import random
import sqlite3
import ssl
import threading
import time
import urllib.parse
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from logger import logger
from .models import AIInstrument, get_current_iso_time

try:
    import pymysql
    import pymysql.cursors

    HAS_PYMYSQL = True
except ImportError:
    HAS_PYMYSQL = False


class AIInstrumentsStorage:
    """Хранилище инструментов агента с поддержкой SQLite и Hostinger (Direct TCP / PHP API)."""

    def __init__(
        self,
        db_path: str | Path = "data/ai_instruments/ai_instruments.db",
        engine: str = "sqlite",
        hostinger_config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Инициализирует подключение к хранилищу ai_instruments.

        Args:
            db_path: Путь к SQLite файлу ai_instruments.db или ':memory:'.
            engine: Тип движка: 'sqlite', 'mariadb' или 'hostinger'.
            hostinger_config: Параметры удаленного подключения к Hostinger.
        """
        self._lock = threading.RLock()
        self.engine = engine.lower()
        self.hostinger_config = dict(hostinger_config or {})
        self.db_path = Path(db_path) if str(db_path) != ":memory:" else ":memory:"
        self._mem_conn: Optional[sqlite3.Connection] = None
        self._mariadb_conn: Optional[Any] = None

        if self.db_path == ":memory:":
            self._mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._mem_conn.row_factory = sqlite3.Row
        elif isinstance(self.db_path, Path):
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Всегда инициализируем локальную SQLite базу (основную или резервную)
        self._init_sqlite_db()

        if self.engine in ("mariadb", "hostinger"):
            self._init_remote_db()

    @property
    def _is_remote(self) -> bool:
        """Возвращает True, если активно удаленное хранилище Hostinger/MariaDB."""
        return self.engine in ("mariadb", "hostinger")

    @property
    def _conn_type(self) -> str:
        """Возвращает тип удаленного подключения ('direct' или 'php_api')."""
        return str(self.hostinger_config.get("connection_type", "direct")).lower()

    @contextmanager
    def _connect_sqlite(self) -> Generator[sqlite3.Connection, None, None]:
        """Контекстный менеджер соединения с локальной базой SQLite."""
        if self._mem_conn is not None:
            with self._lock:
                try:
                    yield self._mem_conn
                    self._mem_conn.commit()
                except Exception:
                    self._mem_conn.rollback()
                    raise
        else:
            conn = sqlite3.connect(str(self.db_path), timeout=15.0, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.execute("PRAGMA busy_timeout = 15000")
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def _get_mariadb_conn(self) -> Any:
        """Создает или возвращает прямое TCP-соединение с MariaDB на Hostinger.

        Returns:
            Объект соединения PyMySQL.

        Raises:
            RuntimeError: Если pymysql не установлен или не удалось подключиться.
        """
        if not HAS_PYMYSQL:
            raise RuntimeError("Модуль 'pymysql' не установлен для прямого подключения к MariaDB.")

        with self._lock:
            if self._mariadb_conn is not None:
                try:
                    self._mariadb_conn.ping(reconnect=True)
                    return self._mariadb_conn
                except Exception:
                    self._mariadb_conn = None

            cfg = self.hostinger_config
            host = cfg.get("host") or os.environ.get("HOSTINGER_DB_HOST", "")
            port = int(cfg.get("port") or os.environ.get("HOSTINGER_DB_PORT", 3306))
            user = cfg.get("user") or os.environ.get("HOSTINGER_DB_USER", "")
            password = cfg.get("password") or os.environ.get("HOSTINGER_DB_PASSWORD", "")
            database = cfg.get("database") or os.environ.get("HOSTINGER_DB_NAME", "")
            timeout = int(cfg.get("connect_timeout", 10))
            read_timeout = int(cfg.get("read_timeout", 15))
            write_timeout = int(cfg.get("write_timeout", 15))
            ip_fallback = cfg.get("ip_fallback") or os.environ.get("HOSTINGER_DB_IP_FALLBACK", "")

            try:
                self._mariadb_conn = pymysql.connect(
                    host=host,
                    port=port,
                    user=user,
                    password=password,
                    database=database,
                    charset="utf8mb4",
                    connect_timeout=timeout,
                    read_timeout=read_timeout,
                    write_timeout=write_timeout,
                    cursorclass=pymysql.cursors.DictCursor,
                    autocommit=True,
                )
                return self._mariadb_conn
            except Exception as conn_err:
                if ip_fallback and ip_fallback != host:
                    try:
                        self._mariadb_conn = pymysql.connect(
                            host=ip_fallback,
                            port=port,
                            user=user,
                            password=password,
                            database=database,
                            charset="utf8mb4",
                            connect_timeout=timeout,
                            read_timeout=read_timeout,
                            write_timeout=write_timeout,
                            cursorclass=pymysql.cursors.DictCursor,
                            autocommit=True,
                        )
                        return self._mariadb_conn
                    except Exception as fb_err:
                        raise RuntimeError(f"Ошибка подключения к MariaDB ({host} / {ip_fallback}): {fb_err}") from fb_err
                raise RuntimeError(f"Ошибка подключения к MariaDB ({host}:{port}): {conn_err}") from conn_err

    def _execute_remote(self, action: str, sql: str, params: Optional[List[Any]] = None) -> Dict[str, Any]:
        """Выполняет SQL-запрос на удаленном сервере Hostinger (через Direct TCP или PHP API).

        Args:
            action: Тип операции ('query' для SELECT, 'execute' для DDL/DML).
            sql: SQL-запрос с позиционными маркерами '?'.
            params: Список позиционных параметров.

        Returns:
            Dict[str, Any]: Результат с ключами 'rows' или 'affected_rows'.
        """
        if self._conn_type == "php_api" and self.hostinger_config.get("php_api_url"):
            try:
                return self._call_hostinger_api(action, {"sql": sql, "params": params or []})
            except Exception as api_err:
                # Если указан хост БД и учетные данные, пробуем переключиться на прямой TCP (Direct MariaDB)
                if HAS_PYMYSQL and self.hostinger_config.get("host") and self.hostinger_config.get("user"):
                    logger.info(
                        f"[AIInstrumentsStorage] PHP API недоступен ({api_err}), переключение на прямой TCP MariaDB."
                    )
                    self.hostinger_config["connection_type"] = "direct"
                else:
                    raise

        conn = self._get_mariadb_conn()
        mysql_sql = sql.replace("?", "%s")
        with self._lock:
            with conn.cursor() as cur:
                affected = cur.execute(mysql_sql, tuple(params or []))
                if action == "query":
                    rows = cur.fetchall()
                    return {"ok": True, "rows": list(rows) if rows else []}
                return {"ok": True, "affected_rows": int(affected or 0)}

    def _init_sqlite_db(self) -> None:
        """Создает таблицы и индексы в SQLite базе ai_instruments.db."""
        with self._connect_sqlite() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_instruments (
                    tool_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    tool_type TEXT NOT NULL DEFAULT 'powershell',
                    command TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    target_entity TEXT DEFAULT '',
                    parameters_schema TEXT DEFAULT '{}',
                    risk_level TEXT DEFAULT 'safe',
                    author_agent TEXT DEFAULT 'reasoning_chain',
                    tags TEXT DEFAULT '["#agent_tool"]',
                    execution_count INTEGER DEFAULT 0,
                    last_executed_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_inst_target ON ai_instruments(target_entity)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_inst_type ON ai_instruments(tool_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_inst_name ON ai_instruments(name)")

    def _init_remote_db(self) -> None:
        """Инициализирует таблицу ai_instruments на удаленном сервере Hostinger."""
        sql_init = """
        CREATE TABLE IF NOT EXISTS ai_instruments (
            tool_id VARCHAR(255) PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            tool_type VARCHAR(50) NOT NULL DEFAULT 'powershell',
            command LONGTEXT NOT NULL,
            description MEDIUMTEXT,
            target_entity VARCHAR(255) DEFAULT '',
            parameters_schema_json LONGTEXT,
            risk_level VARCHAR(50) NOT NULL DEFAULT 'safe',
            author_agent VARCHAR(100) NOT NULL DEFAULT 'reasoning_chain',
            tags_json LONGTEXT,
            execution_count INT NOT NULL DEFAULT 0,
            last_executed_at VARCHAR(100),
            created_at VARCHAR(100) NOT NULL,
            updated_at VARCHAR(100) NOT NULL,
            INDEX idx_ai_inst_target (target_entity),
            INDEX idx_ai_inst_type (tool_type)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
        try:
            self._execute_remote("execute", sql_init)
            logger.info(
                f"[AIInstrumentsStorage] Таблица ai_instruments на сервере Hostinger ({self._conn_type}) проверена"
            )
        except Exception as ex:
            logger.warning(
                f"[AIInstrumentsStorage] Предупреждение при инициализации на Hostinger: {ex}. "
                "Используется резервная база SQLite."
            )
            self.engine = "sqlite"

    def _call_hostinger_api(self, action: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Отправляет запрос к REST API мосту на сервере Hostinger.

        Args:
            action: Действие ('query', 'execute', 'status').
            data: Данные запроса.

        Returns:
            Dict[str, Any]: Ответ сервера.
        """
        php_api_url = (self.hostinger_config.get("php_api_url") or "").strip()
        if not php_api_url:
            raise ValueError("php_api_url не настроен для Hostinger")

        sep = "&" if "?" in php_api_url else "?"
        url = f"{php_api_url}{sep}action={action}"
        encoded_data = json.dumps(data, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=encoded_data,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "AI-Windows-Admin-Instruments/1.0",
                "X-API-Key": str(self.hostinger_config.get("php_api_key", "")).strip(),
            },
            method="POST",
        )
        timeout = int(self.hostinger_config.get("connect_timeout", 10))
        ssl_ctx = ssl.create_default_context()
        if not bool(self.hostinger_config.get("verify_ssl", True)):
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE

        max_retries = 3
        last_err: Optional[Exception] = None
        for attempt in range(max_retries):
            try:
                with urllib.request.urlopen(req, timeout=timeout, context=ssl_ctx) as resp:
                    resp_body = resp.read().decode("utf-8")
                    return json.loads(resp_body)
            except Exception as err:
                last_err = err
                if attempt < max_retries - 1:
                    backoff = (0.5 * (2 ** attempt)) + random.uniform(0.05, 0.25)
                    time.sleep(backoff)
        raise RuntimeError(f"Сбой обращения к PHP API Hostinger после {max_retries} попыток: {last_err}") from last_err

    def check_remote_connection(self) -> Dict[str, Any]:
        """Проверяет доступность удаленной базы на Hostinger и возвращает статистику таблицы ai_instruments."""
        res = self._execute_remote("query", "SELECT COUNT(*) AS cnt FROM ai_instruments", [])
        rows = res.get("rows", [])
        count = int(rows[0].get("cnt", 0)) if rows else 0
        return {
            "ok": True,
            "connected": True,
            "engine": "hostinger",
            "connection_type": self._conn_type,
            "host": self.hostinger_config.get("host", "srv1502.hstgr.io"),
            "database": self.hostinger_config.get("database", "u177424397_comp_knowledge"),
            "table": "ai_instruments",
            "count": count,
            "message": (
                f"Сервер Hostinger ({self._conn_type}) доступен: "
                f"таблица ai_instruments содержит {count} инструментов."
            ),
        }

    def _row_to_instrument(self, row: sqlite3.Row | Dict[str, Any]) -> AIInstrument:
        """Преобразует строку базы данных в объект AIInstrument."""
        d = dict(row)

        schema_raw = d.get("parameters_schema") or d.get("parameters_schema_json") or "{}"
        if isinstance(schema_raw, str):
            try:
                schema_dict = json.loads(schema_raw)
            except Exception:
                schema_dict = {}
        else:
            schema_dict = schema_raw or {}

        tags_raw = d.get("tags") or d.get("tags_json") or "[]"
        if isinstance(tags_raw, str):
            try:
                tags_list = json.loads(tags_raw)
            except Exception:
                tags_list = ["#agent_tool"]
        else:
            tags_list = tags_raw or ["#agent_tool"]

        return AIInstrument(
            tool_id=d["tool_id"],
            name=d["name"],
            tool_type=d.get("tool_type", "powershell"),
            command=d["command"],
            description=d.get("description") or "",
            target_entity=d.get("target_entity") or "",
            parameters_schema=schema_dict,
            risk_level=d.get("risk_level") or "safe",
            author_agent=d.get("author_agent") or "reasoning_chain",
            tags=tags_list,
            execution_count=int(d.get("execution_count") or 0),
            last_executed_at=d.get("last_executed_at"),
            created_at=d.get("created_at") or get_current_iso_time(),
            updated_at=d.get("updated_at") or get_current_iso_time(),
        )

    def save_instrument(self, inst: AIInstrument) -> AIInstrument:
        """Сохраняет или обновляет инструмент в базе ai_instruments.db или Hostinger.

        Args:
            inst: Экземпляр инструмента.

        Returns:
            AIInstrument: Сохраненный инструмент.
        """
        inst.updated_at = get_current_iso_time()
        if self._is_remote:
            sql = """
            INSERT INTO ai_instruments 
                (tool_id, name, tool_type, command, description, target_entity, parameters_schema_json,
                 risk_level, author_agent, tags_json, execution_count, last_executed_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON DUPLICATE KEY UPDATE
                name = VALUES(name),
                tool_type = VALUES(tool_type),
                command = VALUES(command),
                description = VALUES(description),
                target_entity = VALUES(target_entity),
                parameters_schema_json = VALUES(parameters_schema_json),
                risk_level = VALUES(risk_level),
                tags_json = VALUES(tags_json),
                updated_at = VALUES(updated_at);
            """
            params = [
                inst.tool_id,
                inst.name,
                inst.tool_type,
                inst.command,
                inst.description,
                inst.target_entity,
                json.dumps(inst.parameters_schema, ensure_ascii=False),
                inst.risk_level,
                inst.author_agent,
                json.dumps(inst.tags, ensure_ascii=False),
                inst.execution_count,
                inst.last_executed_at,
                inst.created_at,
                inst.updated_at,
            ]
            self._execute_remote("execute", sql, params)
            return inst

        with self._connect_sqlite() as conn:
            conn.execute(
                """
                INSERT INTO ai_instruments 
                    (tool_id, name, tool_type, command, description, target_entity, parameters_schema,
                     risk_level, author_agent, tags, execution_count, last_executed_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tool_id) DO UPDATE SET
                    name = excluded.name,
                    tool_type = excluded.tool_type,
                    command = excluded.command,
                    description = excluded.description,
                    target_entity = excluded.target_entity,
                    parameters_schema = excluded.parameters_schema,
                    risk_level = excluded.risk_level,
                    tags = excluded.tags,
                    updated_at = excluded.updated_at
                """,
                (
                    inst.tool_id,
                    inst.name,
                    inst.tool_type,
                    inst.command,
                    inst.description,
                    inst.target_entity,
                    json.dumps(inst.parameters_schema, ensure_ascii=False),
                    inst.risk_level,
                    inst.author_agent,
                    json.dumps(inst.tags, ensure_ascii=False),
                    inst.execution_count,
                    inst.last_executed_at,
                    inst.created_at,
                    inst.updated_at,
                ),
            )
        return inst

    def get_instrument(self, tool_id: str) -> Optional[AIInstrument]:
        """Возвращает инструмент по уникальному ID."""
        if self._is_remote:
            sql = "SELECT * FROM ai_instruments WHERE tool_id = ? LIMIT 1"
            res = self._execute_remote("query", sql, [tool_id])
            rows = res.get("rows", [])
            return self._row_to_instrument(rows[0]) if rows else None

        with self._connect_sqlite() as conn:
            row = conn.execute("SELECT * FROM ai_instruments WHERE tool_id = ?", (tool_id,)).fetchone()
            return self._row_to_instrument(row) if row else None

    def list_instruments(
        self,
        limit: int = 50,
        offset: int = 0,
        tool_type: Optional[str] = None,
        target_entity: Optional[str] = None,
    ) -> List[AIInstrument]:
        """Возвращает список инструментов с фильтрацией по типу и сущности."""
        query = "SELECT * FROM ai_instruments WHERE 1=1"
        params: List[Any] = []
        if tool_type:
            query += " AND tool_type = ?"
            params.append(tool_type)
        if target_entity:
            query += " AND target_entity = ?"
            params.append(target_entity)
        query += " ORDER BY execution_count DESC, updated_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        if self._is_remote:
            res = self._execute_remote("query", query, params)
            rows = res.get("rows", [])
            return [self._row_to_instrument(r) for r in rows]

        with self._connect_sqlite() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_instrument(r) for r in rows]

    def search_instruments(self, query_str: str, limit: int = 20) -> List[AIInstrument]:
        """Выполняет поиск инструментов по названию, описанию и коду команды."""
        q = f"%{query_str.strip()}%"
        sql = """
        SELECT * FROM ai_instruments 
        WHERE name LIKE ? OR description LIKE ? OR command LIKE ? OR target_entity LIKE ?
        ORDER BY execution_count DESC, updated_at DESC LIMIT ?
        """
        params = [q, q, q, q, limit]

        if self._is_remote:
            res = self._execute_remote("query", sql, params)
            rows = res.get("rows", [])
            return [self._row_to_instrument(r) for r in rows]

        with self._connect_sqlite() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_instrument(r) for r in rows]

    def delete_instrument(self, tool_id: str) -> bool:
        """Удаляет инструмент из базы ai_instruments.db."""
        if self._is_remote:
            sql = "DELETE FROM ai_instruments WHERE tool_id = ?"
            res = self._execute_remote("execute", sql, [tool_id])
            return bool(res.get("affected_rows", 0) > 0)

        with self._connect_sqlite() as conn:
            cur = conn.execute("DELETE FROM ai_instruments WHERE tool_id = ?", (tool_id,))
            return cur.rowcount > 0

    def record_execution(self, tool_id: str) -> bool:
        """Инкрементирует счётчик выполнения и фиксирует временную метку."""
        now = get_current_iso_time()
        if self._is_remote:
            sql = "UPDATE ai_instruments SET execution_count = execution_count + 1, last_executed_at = ?, updated_at = ? WHERE tool_id = ?"
            res = self._execute_remote("execute", sql, [now, now, tool_id])
            return bool(res.get("affected_rows", 0) > 0)

        with self._connect_sqlite() as conn:
            cur = conn.execute(
                "UPDATE ai_instruments SET execution_count = execution_count + 1, last_executed_at = ?, updated_at = ? WHERE tool_id = ?",
                (now, now, tool_id),
            )
            return cur.rowcount > 0

    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику базы данных инструментов агента."""
        count = 0
        if self._is_remote:
            sql = "SELECT COUNT(*) AS cnt FROM ai_instruments"
            res = self._execute_remote("query", sql, [])
            rows = res.get("rows", [])
            if rows:
                count = int(rows[0].get("cnt", 0))
            return {
                "engine": "hostinger_mariadb",
                "connection_type": self._conn_type,
                "total_instruments": count,
                "host": self.hostinger_config.get("host", "srv1502.hstgr.io"),
                "database": self.hostinger_config.get("database", "u177424397_comp_knowledge"),
                "table": "ai_instruments",
            }

        with self._connect_sqlite() as conn:
            row = conn.execute("SELECT COUNT(*) AS cnt FROM ai_instruments").fetchone()
            if row:
                count = int(row["cnt"])
        return {
            "engine": "sqlite",
            "total_instruments": count,
            "database_path": str(self.db_path),
            "table": "ai_instruments",
        }
