# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows DB - Database Adapter
# =============================================================================
# Description:
#   Универсальный адаптер базы данных (MariaDB / SQLite) для централизованного
#   и локального хранения данных телеметрии и базы знаний WikiLLM.
#
# File: db_adapter.py
# Project: ai-windows-admin
# Package: apps.windows.db
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 17:25:00
# =============================================================================

from __future__ import annotations

import json
import os
import re
import sqlite3
import ssl
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from logger import logger
except ImportError:
    import logging
    logger = logging.getLogger("db_adapter")

try:
    import pymysql
    import pymysql.cursors
    HAS_PYMYSQL = True
except ImportError:
    HAS_PYMYSQL = False


class DatabaseAdapter:
    """Универсальный адаптер базы данных с поддержкой MariaDB и SQLite."""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        config_path: Optional[Union[str, Path]] = None,
    ) -> None:
        """Инициализирует адаптер базы данных, считывая настройки конфигурации.

        Args:
            config: Готовый словарь конфигурации базы данных (опционально).
            config_path: Путь к файлу конфигурации (опционально).
        """
        self._lock = threading.RLock()
        self._mariadb_conn: Optional[Any] = None
        self._sqlite_conn: Optional[sqlite3.Connection] = None
        self.config = config or self._load_db_config(config_path)
        self.engine = str(self.config.get("engine", "mariadb")).lower()
        self._ensure_tables()

    def _load_db_config(self, config_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
        """Считывает секцию database из конфигурационных файлов приложения.

        Args:
            config_path: Явный путь к файлу конфигурации.

        Returns:
            Словарь параметров базы данных.
        """
        candidate_paths = []
        if config_path:
            candidate_paths.append(Path(config_path))
        candidate_paths.extend([
            Path("apps/windows/api/config.json"),
            Path("config.json"),
        ])

        for path in candidate_paths:
            if path.is_file():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if "database" in data and isinstance(data["database"], dict):
                            return data["database"]
                except Exception as err:
                    logger.debug(f"[DatabaseAdapter] Ошибка чтения конфига {path}: {err}")

        # Стандартные параметры по умолчанию
        return {
            "engine": "sqlite",
            "sqlite": {"path": "data/wikillm.db"},
            "mariadb": {},
        }

    def _get_mariadb_conn(self) -> Any:
        """Создает или возвращает существующее соединение с MariaDB.

        Returns:
            Объект соединения PyMySQL.

        Raises:
            RuntimeError: Если pymysql не установлен или соединение не удалось.
        """
        if not HAS_PYMYSQL:
            raise RuntimeError("Библиотека 'pymysql' не установлена для работы с MariaDB.")

        with self._lock:
            if self._mariadb_conn is not None:
                try:
                    self._mariadb_conn.ping()
                    return self._mariadb_conn
                except Exception:
                    self._mariadb_conn = None

            cfg = self.config.get("mariadb", {})
            host = cfg.get("host", "127.0.0.1")
            port = int(cfg.get("port", 3306))
            user = cfg.get("user", "")
            password = cfg.get("password", "")
            database = cfg.get("database", "")
            charset = cfg.get("charset", "utf8mb4")
            timeout = int(cfg.get("connect_timeout", 5))

            try:
                self._mariadb_conn = pymysql.connect(
                    host=host,
                    port=port,
                    user=user,
                    password=password,
                    database=database,
                    charset=charset,
                    connect_timeout=timeout,
                    cursorclass=pymysql.cursors.DictCursor,
                    autocommit=True,
                )
                logger.info(f"[DatabaseAdapter] Подключение к MariaDB ({host}:{port}/{database}) успешно.")
                return self._mariadb_conn
            except Exception as conn_err:
                ip_fallback = cfg.get("ip_fallback")
                if ip_fallback and ip_fallback != host:
                    try:
                        logger.warning(f"[DatabaseAdapter] Ошибка {host}, пробуем ip_fallback {ip_fallback}...")
                        self._mariadb_conn = pymysql.connect(
                            host=ip_fallback,
                            port=port,
                            user=user,
                            password=password,
                            database=database,
                            charset=charset,
                            connect_timeout=timeout,
                            cursorclass=pymysql.cursors.DictCursor,
                            autocommit=True,
                        )
                        logger.info(f"[DatabaseAdapter] Подключение к MariaDB по ip_fallback ({ip_fallback}) успешно.")
                        return self._mariadb_conn
                    except Exception as fallback_err:
                        raise RuntimeError(f"Не удалось подключиться к MariaDB ({host} и {ip_fallback}): {fallback_err}")
                raise RuntimeError(f"Не удалось подключиться к MariaDB ({host}): {conn_err}")

    def _get_sqlite_conn(self) -> sqlite3.Connection:
        """Создает или возвращает соединение со SQLite.

        Returns:
            Объект соединения sqlite3.Connection.
        """
        with self._lock:
            if self._sqlite_conn is not None:
                return self._sqlite_conn

            cfg = self.config.get("sqlite", {})
            raw_path = cfg.get("path")
            if raw_path == ":memory:":
                db_path = ":memory:"
            else:
                from apps.windows.db.paths import resolve_system_knowledge_db_path
                db_path_obj = resolve_system_knowledge_db_path(raw_path)
                db_path_obj.parent.mkdir(parents=True, exist_ok=True)
                db_path = str(db_path_obj)

            conn = sqlite3.connect(db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA foreign_keys = ON;")
            self._sqlite_conn = conn
            self._ensure_sqlite_tables(conn)
            return conn

    def _ensure_sqlite_tables(self, conn: Optional[sqlite3.Connection] = None) -> None:
        """Создает необходимые локальные таблицы SQLite и мигрирует данные при необходимости."""
        c = conn or self._sqlite_conn
        if c is None:
            c = self._get_sqlite_conn()

        try:
            with self._lock:
                cur = c.cursor()
                cur.execute("""
                CREATE TABLE IF NOT EXISTS wikillm_knowledge (
                    canonical_key TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'general',
                    description TEXT,
                    is_verified INTEGER NOT NULL DEFAULT 1,
                    claims_json TEXT,
                    remediation_json TEXT,
                    updated_at REAL NOT NULL
                );
                """)
                cur.execute("""
                CREATE TABLE IF NOT EXISTS wikillm_procedural_tools (
                    tool_id TEXT PRIMARY KEY,
                    canonical_key TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    script_type TEXT NOT NULL DEFAULT 'powershell',
                    script_content TEXT NOT NULL,
                    parameters_schema_json TEXT,
                    risk_level TEXT NOT NULL DEFAULT 'safe',
                    is_automated INTEGER NOT NULL DEFAULT 0,
                    tags_json TEXT,
                    status TEXT NOT NULL DEFAULT 'active',
                    version TEXT NOT NULL DEFAULT '1.0.0',
                    compatibility_json TEXT,
                    execution_metrics_json TEXT,
                    execution_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """)
                cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_proc_tools_canon ON wikillm_procedural_tools (canonical_key);
                """)
                cur.execute("""
                CREATE TABLE IF NOT EXISTS wiki_llm_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_name TEXT NOT NULL UNIQUE,
                    top_k INTEGER NOT NULL DEFAULT 5,
                    fetch_k INTEGER NOT NULL DEFAULT 20,
                    score_threshold REAL NOT NULL DEFAULT 0.70,
                    reranker_enabled INTEGER NOT NULL DEFAULT 1,
                    rerank_top_n INTEGER NOT NULL DEFAULT 5,
                    temperature REAL NOT NULL DEFAULT 0.2,
                    max_context_tokens INTEGER NOT NULL DEFAULT 4096,
                    grounding_required INTEGER NOT NULL DEFAULT 1,
                    data TEXT,
                    updated_at REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """)

                # Проверяем, есть ли записи в wikillm_knowledge
                cur.execute("SELECT COUNT(*) FROM wikillm_knowledge;")
                knowledge_count = cur.fetchone()[0]

                # Если wikillm_knowledge пуста, проверяем наличие legacy-таблицы entities
                if knowledge_count == 0:
                    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
                    existing_tables = [r[0] for r in cur.fetchall()]
                    if "entities" in existing_tables:
                        claims_map: Dict[str, List[str]] = {}
                        if "claims" in existing_tables:
                            try:
                                cur.execute("SELECT canonical_key, statement FROM claims;")
                                for row in cur.fetchall():
                                    claims_map.setdefault(row[0], []).append(row[1])
                            except Exception:
                                pass

                        resolutions_map: Dict[str, List[str]] = {}
                        if "resolutions" in existing_tables:
                            try:
                                cur.execute("SELECT canonical_key, title, description FROM resolutions;")
                                for row in cur.fetchall():
                                    desc = f": {row[2]}" if row[2] else ""
                                    resolutions_map.setdefault(row[0], []).append(f"{row[1]}{desc}")
                            except Exception:
                                pass

                        try:
                            cur.execute("SELECT * FROM entities;")
                            for ent in cur.fetchall():
                                d = dict(ent)
                                ckey = d.get("canonical_key", "")
                                if not ckey:
                                    continue
                                title = d.get("name") or d.get("title") or ckey
                                desc = d.get("summary") or d.get("description") or ""
                                cat = d.get("category") or "general"
                                updated_val = d.get("updated_at")
                                ts = time.time()
                                if updated_val is not None:
                                    try:
                                        ts = float(updated_val)
                                    except (ValueError, TypeError):
                                        try:
                                            from datetime import datetime
                                            ts = datetime.fromisoformat(str(updated_val)).timestamp()
                                        except Exception:
                                            ts = time.time()

                                cur.execute("""
                                INSERT OR IGNORE INTO wikillm_knowledge 
                                    (canonical_key, title, category, description, is_verified, claims_json, remediation_json, updated_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                """, (
                                    ckey,
                                    title,
                                    cat,
                                    desc,
                                    1 if d.get("is_verified", 1) else 0,
                                    json.dumps(claims_map.get(ckey, []), ensure_ascii=False),
                                    json.dumps(resolutions_map.get(ckey, []), ensure_ascii=False),
                                    ts
                                ))
                        except Exception as ent_err:
                            logger.debug(f"[DatabaseAdapter] Ошибка автомиграции из entities: {ent_err}")

                    # Если записей по-прежнему 0 (в entities ничего не было), вставляем базовую запись
                    cur.execute("SELECT COUNT(*) FROM wikillm_knowledge;")
                    if cur.fetchone()[0] == 0:
                        cur.execute("""
                        INSERT OR IGNORE INTO wikillm_knowledge
                            (canonical_key, title, category, description, is_verified, claims_json, remediation_json, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            "win_event_4624",
                            "Успешный вход в систему (Event 4624)",
                            "security_audit",
                            "Событие успешного входа пользователя в систему. Фиксирует тип входа (Logon Type) и SID.",
                            1,
                            json.dumps(["Вход выполнен успешно", "Фиксирует учетные данные субъекта"], ensure_ascii=False),
                            json.dumps(["Проверить IP-адрес источника при сетевом входе", "Сверить рабочие часы"], ensure_ascii=False),
                            time.time()
                        ))

                # Проверяем наличие профилей по умолчанию
                cur.execute("SELECT COUNT(*) FROM wiki_llm_profiles;")
                profiles_count = cur.fetchone()[0]
                if profiles_count == 0:
                    default_profiles = [
                        ("fast", 3, 10, 0.60, 0, 3, 0.1, 2048, 0, json.dumps({"top_k": 3, "fetch_k": 10, "score_threshold": 0.60, "reranker_enabled": False, "rerank_top_n": 3, "temperature": 0.1, "max_context_tokens": 2048, "grounding_required": False})),
                        ("balanced", 5, 20, 0.70, 1, 5, 0.2, 4096, 1, json.dumps({"top_k": 5, "fetch_k": 20, "score_threshold": 0.70, "reranker_enabled": True, "rerank_top_n": 5, "temperature": 0.2, "max_context_tokens": 4096, "grounding_required": True})),
                        ("precise", 8, 30, 0.85, 1, 5, 0.0, 8192, 1, json.dumps({"top_k": 8, "fetch_k": 30, "score_threshold": 0.85, "reranker_enabled": True, "rerank_top_n": 5, "temperature": 0.0, "max_context_tokens": 8192, "grounding_required": True}))
                    ]
                    now_ts = time.time()
                    for prof in default_profiles:
                        cur.execute("""
                        INSERT OR IGNORE INTO wiki_llm_profiles 
                            (profile_name, top_k, fetch_k, score_threshold, reranker_enabled, rerank_top_n, temperature, max_context_tokens, grounding_required, data, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (*prof, now_ts))

                c.commit()
        except Exception as sqlite_err:
            logger.error(f"[DatabaseAdapter] Ошибка инициализации таблиц SQLite: {sqlite_err}")

    def _ensure_tables(self) -> None:
        """Создает необходимые таблицы базы данных, если они отсутствуют."""
        # 1. Всегда гарантируем наличие локальных таблиц SQLite
        self._ensure_sqlite_tables()

        create_sql_mariadb = """
        CREATE TABLE IF NOT EXISTS wikillm_knowledge (
            canonical_key VARCHAR(255) PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            category VARCHAR(100) NOT NULL DEFAULT 'general',
            description MEDIUMTEXT,
            is_verified TINYINT(1) NOT NULL DEFAULT 1,
            claims_json LONGTEXT,
            remediation_json LONGTEXT,
            updated_at DOUBLE NOT NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """

        if self.engine == "mariadb":
            conn_type = str(self.config.get("mariadb", {}).get("connection_type", "direct")).lower()
            if conn_type == "php_api":
                try:
                    res = self.init_empty_tables()
                    if not res.get("ok"):
                        raise RuntimeError(res.get("error") or res.get("message") or "Сбой вызова PHP API")
                    return
                except Exception as err:
                    logger.warning(
                        f"[DatabaseAdapter] Сбой инициализации MariaDB через PHP API: {err}. Переключение на SQLite."
                    )
                    self.engine = "sqlite"
            else:
                try:
                    conn = self._get_mariadb_conn()
                    with conn.cursor() as cur:
                        cur.execute(create_sql_mariadb)
                    return
                except Exception as err:
                    logger.warning(
                        f"[DatabaseAdapter] Сбой инициализации MariaDB: {err}. Переключение на локальный SQLite."
                    )
                    self.engine = "sqlite"

    def _prepare_sql_and_params(
        self,
        sql: str,
        params: Optional[Dict[str, Any]],
        target_engine: str,
    ) -> Tuple[str, Any]:
        """Адаптирует синтаксис SQL-запроса и параметров под целевую СУБД.

        Args:
            sql: Исходный SQL-запрос с именованными параметрами (:param).
            params: Словарь параметров.
            target_engine: 'mariadb' или 'sqlite'.

        Returns:
            Кортеж (адаптированный SQL, адаптированные параметры).
        """
        p = dict(params) if params else {}

        if target_engine == "mariadb":
            # Заменяем :param_name на %(param_name)s для PyMySQL
            adapted_sql = re.sub(r":([a-zA-Z0-9_]+)", r"%(\1)s", sql)
            return adapted_sql, p

        # Для SQLite синтаксис :param поддерживается нативно
        adapted_sql = sql
        # Адаптация конструкции ON DUPLICATE KEY UPDATE для SQLite 3.24+
        if "ON DUPLICATE KEY UPDATE" in adapted_sql.upper():
            conflict_col = "canonical_key"
            sql_lower = adapted_sql.lower()
            if "wiki_llm_profiles" in sql_lower:
                conflict_col = "profile_name"
            elif "wikillm_procedural_tools" in sql_lower:
                conflict_col = "tool_id"

            adapted_sql = re.sub(
                r"ON DUPLICATE KEY UPDATE",
                f"ON CONFLICT({conflict_col}) DO UPDATE SET",
                adapted_sql,
                flags=re.IGNORECASE,
            )

        return adapted_sql, p

    def execute(self, sql: str, params: Optional[Dict[str, Any]] = None) -> int:
        """Выполняет команду изменения данных (INSERT, UPDATE, DELETE).

        Args:
            sql: SQL-запрос.
            params: Словарь параметров запроса.

        Returns:
            Число затронутых строк.
        """
        if self.engine == "mariadb":
            conn_type = str(self.config.get("mariadb", {}).get("connection_type", "direct")).lower()
            if conn_type == "php_api":
                try:
                    php_url = self.config.get("mariadb", {}).get("php_api_url", "")
                    api_key = self.config.get("mariadb", {}).get("php_api_key", "")
                    timeout = int(self.config.get("mariadb", {}).get("connect_timeout", 15))
                    res = self._call_php_api(
                        php_url, "execute", {"sql": sql, "params": params or {}}, timeout=timeout, api_key=api_key
                    )
                    if res.get("ok"):
                        return int(res.get("affected_rows", 0))
                    raise RuntimeError(res.get("error") or res.get("message") or "Ошибка запроса PHP API")
                except Exception as err:
                    logger.warning(f"[DatabaseAdapter] Ошибка PHP API в execute: {err}. Запасной путь SQLite.")
                    self.engine = "sqlite"
            else:
                try:
                    conn = self._get_mariadb_conn()
                    adapted_sql, adapted_params = self._prepare_sql_and_params(sql, params, "mariadb")
                    with conn.cursor() as cur:
                        count = cur.execute(adapted_sql, adapted_params)
                        return count
                except Exception as err:
                    logger.warning(f"[DatabaseAdapter] Ошибка MariaDB в execute: {err}. Запасной путь SQLite.")
                    self.engine = "sqlite"

        conn = self._get_sqlite_conn()
        adapted_sql, adapted_params = self._prepare_sql_and_params(sql, params, "sqlite")
        with self._lock:
            cur = conn.execute(adapted_sql, adapted_params)
            conn.commit()
            return cur.rowcount

    def fetch_all(self, sql: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Выполняет запрос на выборку и возвращает список строк-словарей.

        Args:
            sql: SQL-запрос.
            params: Словарь параметров.

        Returns:
            Список словарей с результатами.
        """
        if self.engine == "mariadb":
            conn_type = str(self.config.get("mariadb", {}).get("connection_type", "direct")).lower()
            if conn_type == "php_api":
                try:
                    php_url = self.config.get("mariadb", {}).get("php_api_url", "")
                    api_key = self.config.get("mariadb", {}).get("php_api_key", "")
                    timeout = int(self.config.get("mariadb", {}).get("connect_timeout", 15))
                    res = self._call_php_api(
                        php_url, "query", {"sql": sql, "params": params or {}}, timeout=timeout, api_key=api_key
                    )
                    if res.get("ok") and "rows" in res:
                        return list(res["rows"])
                    raise RuntimeError(res.get("error") or res.get("message") or "Ошибка запроса PHP API")
                except Exception as err:
                    logger.warning(f"[DatabaseAdapter] Ошибка PHP API в fetch_all: {err}. Запасной путь SQLite.")
                    self.engine = "sqlite"
            else:
                try:
                    conn = self._get_mariadb_conn()
                    adapted_sql, adapted_params = self._prepare_sql_and_params(sql, params, "mariadb")
                    with conn.cursor() as cur:
                        cur.execute(adapted_sql, adapted_params)
                        rows = cur.fetchall()
                        return list(rows) if rows else []
                except Exception as err:
                    logger.warning(f"[DatabaseAdapter] Ошибка MariaDB в fetch_all: {err}. Запасной путь SQLite.")
                    self.engine = "sqlite"

        conn = self._get_sqlite_conn()
        adapted_sql, adapted_params = self._prepare_sql_and_params(sql, params, "sqlite")
        with self._lock:
            cur = conn.execute(adapted_sql, adapted_params)
            rows = cur.fetchall()
            return [dict(r) for r in rows]

    def fetch_one(self, sql: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Выполняет запрос на выборку одной строки.

        Args:
            sql: SQL-запрос.
            params: Словарь параметров.

        Returns:
            Словарь с данными строки или None.
        """
        rows = self.fetch_all(sql, params)
        return rows[0] if rows else None

    def ping(self) -> bool:
        """Проверяет доступность текущего подключения к базе данных.

        Returns:
            True при успешном ответе, иначе False.
        """
        try:
            res = self.fetch_one("SELECT 1 AS alive")
            return res is not None and (res.get("alive") == 1 or res.get("1") == 1)
        except Exception:
            return False

    def _get_sqlite_source_info(self, sqlite_path: Optional[str] = None) -> Dict[str, Any]:
        """Возвращает информацию о локальной базе данных SQLite для миграции."""
        from apps.windows.db.paths import resolve_system_knowledge_db_path
        src_path = resolve_system_knowledge_db_path(sqlite_path)

        if not src_path.is_file():
            return {"exists": False, "path": str(src_path), "entities_count": 0, "tools_count": 0}

        try:
            conn = sqlite3.connect(str(src_path))
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [r[0] for r in cur.fetchall()]
            ent_cnt = 0
            if "entities" in tables:
                cur.execute("SELECT COUNT(*) FROM entities;")
                ent_cnt = max(ent_cnt, cur.fetchone()[0])
            if "wikillm_knowledge" in tables:
                cur.execute("SELECT COUNT(*) FROM wikillm_knowledge;")
                ent_cnt = max(ent_cnt, cur.fetchone()[0])

            tool_cnt = 0
            if "wikillm_procedural_tools" in tables:
                cur.execute("SELECT COUNT(*) FROM wikillm_procedural_tools;")
                tool_cnt = cur.fetchone()[0]

            conn.close()
            return {
                "exists": True,
                "path": str(src_path),
                "entities_count": ent_cnt,
                "tools_count": tool_cnt,
                "total_records": ent_cnt + tool_cnt,
            }
        except Exception as exc:
            return {"exists": False, "path": str(src_path), "error": str(exc), "entities_count": 0, "tools_count": 0}

    def _call_php_api(
        self,
        url: str,
        action: str,
        payload: Optional[Dict[str, Any]] = None,
        timeout: int = 15,
        api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Отправляет HTTP запрос к удаленному PHP REST API мосту (wikillm_hostinger.php).

        Args:
            url: URL скрипта на сервере.
            action: Название действия (check, create_db, init_tables, batch_import, status).
            payload: Тело запроса JSON.
            timeout: Таймаут в секундах.
            api_key: Секретный ключ (опционально).

        Returns:
            Словарь с результатом ответа от PHP скрипта.
        """
        import urllib.request
        import urllib.error

        clean_url = (url or "").strip()
        if not clean_url:
            return {
                "ok": False,
                "connected": False,
                "stage": "connection_failed",
                "error": "URL PHP API не указан в настройках.",
                "message": "URL PHP API не указан в настройках.",
            }

        sep = "&" if "?" in clean_url else "?"
        full_url = f"{clean_url}{sep}action={action}"
        body_data = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")

        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "AI-Windows-Admin-DB-Adapter/1.0",
        }
        if api_key:
            headers["X-API-Key"] = str(api_key).strip()

        req = urllib.request.Request(full_url, data=body_data, headers=headers, method="POST")
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ssl_ctx) as response:
                resp_bytes = response.read()
                return json.loads(resp_bytes.decode("utf-8"))
        except urllib.error.HTTPError as http_err:
            try:
                err_data = json.loads(http_err.read().decode("utf-8"))
                return err_data
            except Exception:
                return {
                    "ok": False,
                    "connected": False,
                    "stage": "connection_failed",
                    "error": f"HTTP {http_err.code}: {http_err.reason}",
                    "message": f"Ошибка PHP API (HTTP {http_err.code}): {http_err.reason}",
                }
        except Exception as exc:
            return {
                "ok": False,
                "connected": False,
                "stage": "connection_failed",
                "error": str(exc),
                "message": f"Ошибка сети при обращении к PHP API: {exc}",
            }

    def check_connection(self, cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Проверяет подключение к серверу MariaDB (напрямую или через PHP API), наличие базы данных и таблиц."""
        c = cfg or self.config.get("mariadb", {})
        conn_type = str(c.get("connection_type", "direct")).lower()
        timeout = int(c.get("connect_timeout", 10))
        database = c.get("database", "")

        # Режим 0: Проверка локальной базы данных SQLite
        is_sqlite_mode = (
            conn_type == "sqlite"
            or str(c.get("engine", "")).lower() == "sqlite"
            or (cfg is None and self.engine == "sqlite")
            or database.endswith(".db")
        )
        if is_sqlite_mode:
            from apps.windows.db.paths import resolve_system_knowledge_db_path
            sq_path = c.get("sqlite_path") or c.get("path") or self.config.get("sqlite", {}).get("path")
            resolved_path = resolve_system_knowledge_db_path(sq_path)
            sq_info = self._get_sqlite_source_info(str(resolved_path))
            exists = sq_info.get("exists", False)
            total = sq_info.get("total_records", 0)
            return {
                "ok": exists,
                "connected": exists,
                "engine": "sqlite",
                "stage": "ready" if exists else "database_missing",
                "database_exists": exists,
                "tables_exist": exists,
                "total_records": total,
                "sqlite_info": sq_info,
                "path": str(resolved_path),
                "template": sq_path,
                "message": f"Локальная база данных SQLite доступна: {sq_info.get('path')} ({total} подсказок/записей)." if exists else f"Файл базы SQLite не найден: {sq_path}",
            }

        # Режим 1: Подключение через PHP REST API скрипт
        if conn_type == "php_api":
            php_url = c.get("php_api_url", "")
            api_key = c.get("php_api_key", "")
            res = self._call_php_api(
                php_url, "check", {"database": database}, timeout=timeout, api_key=api_key
            )
            sqlite_info = self._get_sqlite_source_info()
            res["sqlite_info"] = sqlite_info
            if "total_records" not in res and "tables" in res and isinstance(res["tables"], dict):
                res["total_records"] = sum(t.get("count", 0) for t in res["tables"].values())
            return res

        # Режим 2: Прямое TCP подключение к MariaDB (порт 3306)
        host = c.get("host", "127.0.0.1")
        port = int(c.get("port", 3306))
        user = c.get("user", "")
        password = c.get("password", "")
        ip_fallback = c.get("ip_fallback")

        if not HAS_PYMYSQL:
            return {
                "ok": False,
                "stage": "driver_missing",
                "error": "Модуль pymysql не установлен в окружении Python.",
                "message": "Модуль pymysql не установлен.",
            }

        server_conn = None
        active_host = host
        try:
            # 1. Проверяем связь с сервером MariaDB (без выбора базы данных)
            try:
                server_conn = pymysql.connect(
                    host=host,
                    port=port,
                    user=user,
                    password=password,
                    connect_timeout=timeout,
                    charset="utf8mb4",
                )
            except Exception as e1:
                if ip_fallback and ip_fallback != host:
                    active_host = ip_fallback
                    server_conn = pymysql.connect(
                        host=ip_fallback,
                        port=port,
                        user=user,
                        password=password,
                        connect_timeout=timeout,
                        charset="utf8mb4",
                    )
                else:
                    raise e1

            # Получаем версию сервера MariaDB
            with server_conn.cursor() as cur:
                cur.execute("SELECT VERSION();")
                version_row = cur.fetchone()
                server_version = version_row[0] if version_row else "Unknown"

                # 2. Проверяем существование базы данных
                cur.execute("SHOW DATABASES;")
                databases = [d[0].lower() for d in cur.fetchall()]

            db_exists = bool(database and database.lower() in databases)
            sqlite_info = self._get_sqlite_source_info()

            if not db_exists:
                return {
                    "ok": True,
                    "connected": True,
                    "server_version": server_version,
                    "active_host": active_host,
                    "database_exists": False,
                    "database": database,
                    "stage": "database_missing",
                    "sqlite_info": sqlite_info,
                    "message": f"Сервер MariaDB доступен, но база данных '{database}' не существует.",
                }

            # 3. База данных существует, проверяем таблицы и количество строк
            db_conn = pymysql.connect(
                host=active_host,
                port=port,
                user=user,
                password=password,
                database=database,
                connect_timeout=timeout,
                charset="utf8mb4",
            )
            tables_info = {}
            target_tables = ["wikillm_knowledge", "wikillm_procedural_tools", "wiki_llm_profiles"]
            with db_conn.cursor() as cur:
                cur.execute("SHOW TABLES;")
                existing_tables = [t[0].lower() for t in cur.fetchall()]
                for tbl in target_tables:
                    if tbl.lower() in existing_tables:
                        try:
                            cur.execute(f"SELECT COUNT(*) FROM `{tbl}`;")
                            row_cnt = cur.fetchone()[0]
                            tables_info[tbl] = {"exists": True, "count": row_cnt}
                        except Exception:
                            tables_info[tbl] = {"exists": True, "count": 0}
                    else:
                        tables_info[tbl] = {"exists": False, "count": 0}
            db_conn.close()

            all_ready = all(t.get("exists", False) for t in tables_info.values())
            total_records = sum(t.get("count", 0) for t in tables_info.values())
            is_empty = (total_records == 0)

            return {
                "ok": True,
                "connected": True,
                "server_version": server_version,
                "active_host": active_host,
                "database_exists": True,
                "database": database,
                "tables": tables_info,
                "all_tables_ready": all_ready,
                "is_empty": is_empty,
                "total_records": total_records,
                "stage": "ready" if (all_ready and not is_empty) else "tables_setup_needed",
                "sqlite_info": sqlite_info,
                "message": "База данных доступна и готова к работе." if (all_ready and not is_empty) else "База данных найдена, требуется настройка таблиц или импорт данных.",
            }
        except Exception as exc:
            return {
                "ok": False,
                "connected": False,
                "stage": "connection_failed",
                "error": str(exc),
                "message": f"Не удалось подключиться к серверу MariaDB: {exc}",
            }
        finally:
            if server_conn:
                try:
                    server_conn.close()
                except Exception:
                    pass

    def create_database(self, cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Создает базу данных на сервере MariaDB (напрямую или через PHP API)."""
        c = cfg or self.config.get("mariadb", {})
        conn_type = str(c.get("connection_type", "direct")).lower()
        database = c.get("database", "")
        timeout = int(c.get("connect_timeout", 10))

        if not database:
            return {"ok": False, "error": "Имя базы данных не указано.", "message": "Имя базы данных не указано."}

        if conn_type == "php_api":
            php_url = c.get("php_api_url", "")
            api_key = c.get("php_api_key", "")
            return self._call_php_api(
                php_url, "create_db", {"database": database}, timeout=timeout, api_key=api_key
            )

        host = c.get("host", "127.0.0.1")
        port = int(c.get("port", 3306))
        user = c.get("user", "")
        password = c.get("password", "")
        ip_fallback = c.get("ip_fallback")

        conn = None
        try:
            try:
                conn = pymysql.connect(
                    host=host, port=port, user=user, password=password, connect_timeout=timeout, charset="utf8mb4"
                )
            except Exception as e1:
                if ip_fallback and ip_fallback != host:
                    conn = pymysql.connect(
                        host=ip_fallback, port=port, user=user, password=password, connect_timeout=timeout, charset="utf8mb4"
                    )
                else:
                    raise e1

            with conn.cursor() as cur:
                clean_db = re.sub(r"[^a-zA-Z0-9_]", "", database)
                cur.execute(f"CREATE DATABASE IF NOT EXISTS `{clean_db}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")

            logger.console(f"[DatabaseAdapter] База данных '{clean_db}' успешно создана на сервере MariaDB.")
            return {"ok": True, "database": clean_db, "message": f"База данных '{clean_db}' успешно создана."}
        except Exception as exc:
            logger.console(f"[DatabaseAdapter] Ошибка создания базы '{database}': {exc}")
            return {"ok": False, "error": str(exc), "message": f"Ошибка создания базы данных: {exc}"}
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def init_empty_tables(self, cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Создает пустые таблицы WikiLLM в локальной SQLite или MariaDB (напрямую или через PHP API)."""
        target_cfg = cfg or self.config.get("mariadb", {})
        conn_type = str(target_cfg.get("connection_type", "direct")).lower()
        database = target_cfg.get("database", "")
        timeout = int(target_cfg.get("connect_timeout", 10))

        is_sqlite_mode = (
            conn_type == "sqlite"
            or str(target_cfg.get("engine", "")).lower() == "sqlite"
            or (cfg is None and self.engine == "sqlite")
            or database.endswith(".db")
        )
        if is_sqlite_mode:
            from apps.windows.db.paths import resolve_system_knowledge_db_path
            sq_path = target_cfg.get("sqlite_path") or target_cfg.get("path") or self.config.get("sqlite", {}).get("path")
            resolved_path = resolve_system_knowledge_db_path(sq_path)
            try:
                resolved_path.parent.mkdir(parents=True, exist_ok=True)
                sq_conn = sqlite3.connect(str(resolved_path))
                sq_conn.row_factory = sqlite3.Row
                self._ensure_sqlite_tables(sq_conn)
                sq_conn.close()
                return {
                    "ok": True,
                    "engine": "sqlite",
                    "path": str(resolved_path),
                    "tables_created": ["wikillm_knowledge", "wikillm_procedural_tools", "wiki_llm_profiles"],
                    "message": f"Таблицы локальной базы SQLite успешно инициализированы: {resolved_path}",
                }
            except Exception as exc:
                return {
                    "ok": False,
                    "engine": "sqlite",
                    "error": str(exc),
                    "message": f"Ошибка инициализации таблиц SQLite: {exc}",
                }

        if conn_type == "php_api":
            php_url = target_cfg.get("php_api_url", "")
            api_key = target_cfg.get("php_api_key", "")
            return self._call_php_api(
                php_url, "init_tables", {"database": database}, timeout=timeout, api_key=api_key
            )

        host = target_cfg.get("host", "127.0.0.1")
        port = int(target_cfg.get("port", 3306))
        user = target_cfg.get("user", "")
        password = target_cfg.get("password", "")
        ip_fallback = target_cfg.get("ip_fallback")

        create_knowledge = """
        CREATE TABLE IF NOT EXISTS wikillm_knowledge (
            canonical_key VARCHAR(255) PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            category VARCHAR(100) NOT NULL DEFAULT 'general',
            description MEDIUMTEXT,
            is_verified TINYINT(1) NOT NULL DEFAULT 1,
            claims_json LONGTEXT,
            remediation_json LONGTEXT,
            updated_at DOUBLE NOT NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """

        create_procedural = """
        CREATE TABLE IF NOT EXISTS wikillm_procedural_tools (
            tool_id VARCHAR(255) PRIMARY KEY,
            canonical_key VARCHAR(255) NOT NULL,
            title VARCHAR(255) NOT NULL,
            description MEDIUMTEXT,
            script_type VARCHAR(50) NOT NULL DEFAULT 'powershell',
            script_content LONGTEXT NOT NULL,
            parameters_schema_json LONGTEXT,
            risk_level VARCHAR(50) NOT NULL DEFAULT 'safe',
            is_automated TINYINT(1) NOT NULL DEFAULT 0,
            tags_json LONGTEXT,
            status VARCHAR(50) NOT NULL DEFAULT 'active',
            version VARCHAR(50) NOT NULL DEFAULT '1.0.0',
            compatibility_json LONGTEXT,
            execution_metrics_json LONGTEXT,
            execution_count INT NOT NULL DEFAULT 0,
            created_at VARCHAR(100) NOT NULL,
            updated_at VARCHAR(100) NOT NULL,
            INDEX idx_proc_tools_canon (canonical_key)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """

        create_profiles = """
        CREATE TABLE IF NOT EXISTS wiki_llm_profiles (
            id INT PRIMARY KEY AUTO_INCREMENT,
            profile_name VARCHAR(255) NOT NULL UNIQUE,
            top_k INT NOT NULL DEFAULT 5,
            fetch_k INT NOT NULL DEFAULT 20,
            score_threshold DOUBLE NOT NULL DEFAULT 0.70,
            reranker_enabled TINYINT(1) NOT NULL DEFAULT 1,
            rerank_top_n INT NOT NULL DEFAULT 5,
            temperature DOUBLE NOT NULL DEFAULT 0.2,
            max_context_tokens INT NOT NULL DEFAULT 4096,
            grounding_required TINYINT(1) NOT NULL DEFAULT 1,
            data LONGTEXT,
            updated_at DOUBLE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """

        default_profiles = [
            ("fast", 3, 10, 0.60, 0, 3, 0.1, 2048, 0, json.dumps({"top_k": 3, "fetch_k": 10, "score_threshold": 0.60, "reranker_enabled": False, "rerank_top_n": 3, "temperature": 0.1, "max_context_tokens": 2048, "grounding_required": False})),
            ("balanced", 5, 20, 0.70, 1, 5, 0.2, 4096, 1, json.dumps({"top_k": 5, "fetch_k": 20, "score_threshold": 0.70, "reranker_enabled": True, "rerank_top_n": 5, "temperature": 0.2, "max_context_tokens": 4096, "grounding_required": True})),
            ("precise", 8, 30, 0.85, 1, 5, 0.0, 8192, 1, json.dumps({"top_k": 8, "fetch_k": 30, "score_threshold": 0.85, "reranker_enabled": True, "rerank_top_n": 5, "temperature": 0.0, "max_context_tokens": 8192, "grounding_required": True}))
        ]

        conn = None
        created_tables = []
        try:
            try:
                conn = pymysql.connect(
                    host=host, port=port, user=user, password=password, database=database, connect_timeout=timeout, charset="utf8mb4"
                )
            except Exception as e1:
                if ip_fallback and ip_fallback != host:
                    conn = pymysql.connect(
                        host=ip_fallback, port=port, user=user, password=password, database=database, connect_timeout=timeout, charset="utf8mb4"
                    )
                else:
                    raise e1

            with conn.cursor() as cur:
                cur.execute(create_knowledge)
                created_tables.append("wikillm_knowledge")
                cur.execute(create_procedural)
                created_tables.append("wikillm_procedural_tools")
                cur.execute(create_profiles)
                created_tables.append("wiki_llm_profiles")

                for prof in default_profiles:
                    cur.execute(
                        """
                        INSERT INTO wiki_llm_profiles 
                            (profile_name, top_k, fetch_k, score_threshold, reranker_enabled, rerank_top_n, temperature, max_context_tokens, grounding_required, data, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, UNIX_TIMESTAMP())
                        ON DUPLICATE KEY UPDATE updated_at = UNIX_TIMESTAMP();
                        """,
                        prof
                    )
            conn.commit()
            logger.console("[DatabaseAdapter] Пустые таблицы WikiLLM успешно инициализированы в MariaDB.")
            return {"ok": True, "tables_created": created_tables, "message": "Пустые таблицы WikiLLM успешно инициализированы."}
        except Exception as exc:
            logger.console(f"[DatabaseAdapter] Ошибка инициализации таблиц MariaDB: {exc}")
            return {"ok": False, "error": str(exc), "message": f"Ошибка инициализации таблиц: {exc}"}
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def import_from_sqlite(self, sqlite_path: Optional[str] = None, cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Импортирует сущности, знания и процедурные инструменты из SQLite в MariaDB."""
        init_res = self.init_empty_tables(cfg)
        if not init_res.get("ok"):
            return init_res

        target_cfg = cfg or self.config.get("mariadb", {})
        host = target_cfg.get("host", "127.0.0.1")
        port = int(target_cfg.get("port", 3306))
        user = target_cfg.get("user", "")
        password = target_cfg.get("password", "")
        database = target_cfg.get("database", "")
        ip_fallback = target_cfg.get("ip_fallback")
        timeout = int(target_cfg.get("connect_timeout", 5))

        src_path = Path(sqlite_path) if sqlite_path else Path("data/windows_wikillm/knowledge.db")
        if not src_path.is_file():
            for alt in [Path("data/wikillm.db"), Path("wiki_llm.db")]:
                if alt.is_file():
                    src_path = alt
                    break

        if not src_path.is_file():
            return {"ok": False, "error": f"Файл SQLite базы данных не найден: {src_path}", "message": f"Файл SQLite не найден: {src_path}"}

        imported_knowledge = 0
        imported_tools = 0

        src_conn = sqlite3.connect(str(src_path))
        src_conn.row_factory = sqlite3.Row
        src_cur = src_conn.cursor()

        src_cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        sqlite_tables = [r[0] for r in src_cur.fetchall()]

        knowledge_rows = []
        knowledge_dicts = []
        if "wikillm_knowledge" in sqlite_tables:
            src_cur.execute("SELECT * FROM wikillm_knowledge;")
            for r in src_cur.fetchall():
                d = dict(r)
                item = {
                    "canonical_key": d.get("canonical_key", ""),
                    "title": d.get("title", ""),
                    "category": d.get("category", "general"),
                    "description": d.get("description", ""),
                    "is_verified": int(d.get("is_verified", 1)),
                    "claims_json": d.get("claims_json", "[]"),
                    "remediation_json": d.get("remediation_json", "[]"),
                    "updated_at": float(d.get("updated_at") or 0.0),
                }
                knowledge_dicts.append(item)
                knowledge_rows.append((
                    item["canonical_key"],
                    item["title"],
                    item["category"],
                    item["description"],
                    item["is_verified"],
                    item["claims_json"],
                    item["remediation_json"],
                    item["updated_at"],
                ))

        if not knowledge_rows and "entities" in sqlite_tables:
            claims_map = {}
            if "claims" in sqlite_tables:
                try:
                    src_cur.execute("SELECT canonical_key, statement FROM claims;")
                    for c_row in src_cur.fetchall():
                        k = c_row["canonical_key"]
                        claims_map.setdefault(k, []).append(c_row["statement"])
                except Exception:
                    pass

            resolutions_map = {}
            if "resolutions" in sqlite_tables:
                try:
                    src_cur.execute("SELECT canonical_key, title, description FROM resolutions;")
                    for r_row in src_cur.fetchall():
                        k = r_row["canonical_key"]
                        res_text = r_row["title"] + (f": {r_row['description']}" if r_row["description"] else "")
                        resolutions_map.setdefault(k, []).append(res_text)
                except Exception:
                    pass

            src_cur.execute("SELECT canonical_key, name, category, summary, updated_at FROM entities;")
            import time
            for e_row in src_cur.fetchall():
                k = e_row["canonical_key"]
                title = e_row["name"] or k
                cat = e_row["category"] or "system"
                desc = e_row["summary"] or ""
                clms = json.dumps(claims_map.get(k, []), ensure_ascii=False)
                remed = json.dumps(resolutions_map.get(k, []), ensure_ascii=False)
                ts = time.time()
                item = {
                    "canonical_key": k,
                    "title": title,
                    "category": cat,
                    "description": desc,
                    "is_verified": 1,
                    "claims_json": clms,
                    "remediation_json": remed,
                    "updated_at": ts,
                }
                knowledge_dicts.append(item)
                knowledge_rows.append((k, title, cat, desc, 1, clms, remed, ts))

        tool_rows = []
        tool_dicts = []
        if "wikillm_procedural_tools" in sqlite_tables:
            try:
                src_cur.execute("SELECT * FROM wikillm_procedural_tools;")
                for t in src_cur.fetchall():
                    td = dict(t)
                    t_item = {
                        "tool_id": td.get("tool_id"),
                        "canonical_key": td.get("canonical_key"),
                        "title": td.get("title"),
                        "description": td.get("description"),
                        "script_type": td.get("script_type", "powershell"),
                        "script_content": td.get("script_content", ""),
                        "parameters_schema_json": td.get("parameters_schema_json", "{}"),
                        "risk_level": td.get("risk_level", "safe"),
                        "is_automated": int(td.get("is_automated", 0)),
                        "tags_json": td.get("tags_json", "[]"),
                        "status": td.get("status", "active"),
                        "version": td.get("version", "1.0.0"),
                        "compatibility_json": td.get("compatibility_json", "{}"),
                        "execution_metrics_json": td.get("execution_metrics_json", "{}"),
                        "execution_count": int(td.get("execution_count", 0)),
                        "created_at": td.get("created_at", ""),
                        "updated_at": td.get("updated_at", ""),
                    }
                    tool_dicts.append(t_item)
                    tool_rows.append(tuple(t_item.values()))
            except Exception as e_tool:
                logger.warning(f"[DatabaseAdapter] Ошибка чтения процедурных инструментов: {e_tool}")

        src_conn.close()

        # Если выбран режим PHP API – отправляем данные через HTTP
        conn_type = str(target_cfg.get("connection_type", "direct")).lower()
        if conn_type == "php_api":
            php_url = target_cfg.get("php_api_url", "")
            api_key = target_cfg.get("php_api_key", "")
            payload = {"knowledge": knowledge_dicts, "tools": tool_dicts, "database": database}
            res = self._call_php_api(php_url, "batch_import", payload, timeout=timeout * 3, api_key=api_key)
            res["source"] = str(src_path)
            return res

        conn = None
        try:
            try:
                conn = pymysql.connect(
                    host=host, port=port, user=user, password=password, database=database, connect_timeout=timeout, charset="utf8mb4"
                )
            except Exception as e1:
                if ip_fallback and ip_fallback != host:
                    conn = pymysql.connect(
                        host=ip_fallback, port=port, user=user, password=password, database=database, connect_timeout=timeout, charset="utf8mb4"
                    )
                else:
                    raise e1

            with conn.cursor() as cur:
                if knowledge_rows:
                    insert_kb_sql = """
                    INSERT INTO wikillm_knowledge 
                        (canonical_key, title, category, description, is_verified, claims_json, remediation_json, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE 
                        title = VALUES(title),
                        category = VALUES(category),
                        description = VALUES(description),
                        is_verified = VALUES(is_verified),
                        claims_json = VALUES(claims_json),
                        remediation_json = VALUES(remediation_json),
                        updated_at = VALUES(updated_at);
                    """
                    cur.executemany(insert_kb_sql, knowledge_rows)
                    imported_knowledge = len(knowledge_rows)

                if tool_rows:
                    insert_tool_sql = """
                    INSERT INTO wikillm_procedural_tools
                        (tool_id, canonical_key, title, description, script_type, script_content, parameters_schema_json,
                         risk_level, is_automated, tags_json, status, version, compatibility_json, execution_metrics_json,
                         execution_count, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        title = VALUES(title),
                        description = VALUES(description),
                        script_content = VALUES(script_content),
                        status = VALUES(status),
                        updated_at = VALUES(updated_at);
                    """
                    cur.executemany(insert_tool_sql, tool_rows)
                    imported_tools = len(tool_rows)

            conn.commit()
            logger.console(f"[DatabaseAdapter] Импорт успешно завершен: {imported_knowledge} записей знаний, {imported_tools} процедурных инструментов в MariaDB.")
            return {
                "ok": True,
                "imported_knowledge": imported_knowledge,
                "imported_tools": imported_tools,
                "source": str(src_path),
                "message": f"Успешно импортировано {imported_knowledge} записей знаний и {imported_tools} инструментов из SQLite.",
            }
        except Exception as exc:
            logger.console(f"[DatabaseAdapter] Ошибка импорта в MariaDB: {exc}")
            return {"ok": False, "error": str(exc), "message": f"Ошибка импорта данных в MariaDB: {exc}"}
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def close(self) -> None:
        """Закрывает активные подключения к MariaDB и SQLite."""
        with self._lock:
            if self._mariadb_conn is not None:
                try:
                    self._mariadb_conn.close()
                except Exception:
                    pass
                self._mariadb_conn = None

            if self._sqlite_conn is not None:
                try:
                    self._sqlite_conn.close()
                except Exception:
                    pass
                self._sqlite_conn = None

    def update_config(self, new_config: Dict[str, Any], save_to_disk: bool = True) -> None:
        """Обновляет конфигурацию базы данных и сбрасывает активные соединения."""
        self.close()
        self.config = new_config
        self.engine = str(new_config.get("engine", "mariadb")).lower()

        if save_to_disk:
            cfg_path = Path("apps/windows/api/config.json")
            if cfg_path.is_file():
                try:
                    with open(cfg_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    data["database"] = self.config
                    with open(cfg_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    logger.console(f"[DatabaseAdapter] Конфигурация базы данных обновлена в {cfg_path}")
                except Exception as exc:
                    logger.warning(f"[DatabaseAdapter] Не удалось сохранить конфигурацию: {exc}")

        self._ensure_tables()


# Глобальный экземпляр адаптера для использования в роутерах
db_adapter = DatabaseAdapter()

