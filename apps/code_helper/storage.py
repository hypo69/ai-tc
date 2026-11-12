# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Code Helper - Hostinger MariaDB & Local Storage Manager
# =============================================================================
# Description:
#   Автономный менеджер хранения базы знаний исходного кода.
#   Обеспечивает подключение к MariaDB на Hostinger (u177424397_code_helper)
#   с автоматическим fallback в локальную базу SQLite при недоступности сети
#   или неразрешенном Remote IP в панели Hostinger.
#
# File: storage.py
# Project: ai-windows-admin
# Package: apps.code_helper
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 14:25:00
# =============================================================================

from __future__ import annotations

"""Модуль хранения базы знаний кода в Hostinger MariaDB и SQLite."""

import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

try:
    import pymysql
    import pymysql.cursors
    HAS_PYMYSQL = True
except ImportError:
    HAS_PYMYSQL = False

from logger import logger
from .models import CodeChunk, CodeSymbol, DiagnosticConclusion, IndexStats
from .schema import MARIADB_INIT_QUERIES, SQLITE_INIT_SCRIPT


class CodeHelperStorage:
    """Универсальное хранилище базы знаний кода с поддержкой Hostinger MariaDB и SQLite."""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        config_path: Optional[Path | str] = None,
    ) -> None:
        """Инициализация хранилища базы знаний.

        Args:
            config: Словарь настроек приложения или секция storage.
            config_path: Путь к файлу конфигурации.
        """
        self._lock = threading.RLock()
        self.config: Dict[str, Any] = self._resolve_config(config, config_path)
        storage_cfg = self.config.get("storage", self.config)

        self.engine_preference: str = str(storage_cfg.get("engine", "mariadb")).lower()
        self.hostinger_cfg: Dict[str, Any] = dict(storage_cfg.get("hostinger", {}))
        
        sqlite_cfg = storage_cfg.get("sqlite", {})
        raw_sqlite_path = sqlite_cfg.get("path", "data/code_helper/code_helper.db")
        self.sqlite_path = Path(raw_sqlite_path) if str(raw_sqlite_path) != ":memory:" else ":memory:"

        self._mariadb_conn: Optional[Any] = None
        self._is_mariadb_active: bool = False
        self._last_mariadb_error: str = ""

        if isinstance(self.sqlite_path, Path):
            self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_sqlite_schema()
        if self.engine_preference in ("mariadb", "hostinger"):
            self._try_init_mariadb()

    def _resolve_config(
        self, config: Optional[Dict[str, Any]], config_path: Optional[Path | str]
    ) -> Dict[str, Any]:
        """Загрузка конфигурации из переданного словаря или файла config.json."""
        if config:
            return config
        target_path = Path(config_path) if config_path else Path(__file__).parent / "config.json"
        if target_path.exists():
            try:
                with open(target_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as exc:
                logger.warning(f"[CodeHelperStorage] Не удалось прочитать {target_path}: {exc}")
        return {}

    @property
    def active_engine(self) -> str:
        """Возвращает текущий активный движок хранилища ('mariadb' или 'sqlite')."""
        return "mariadb" if self._is_mariadb_active else "sqlite"

    def _get_mariadb_connection(self) -> Any:
        """Устанавливает или возвращает существующее TCP соединение с Hostinger MariaDB."""
        if not HAS_PYMYSQL:
            raise RuntimeError("Пакет 'pymysql' не установлен в окружении.")

        with self._lock:
            if self._mariadb_conn is not None:
                try:
                    self._mariadb_conn.ping(reconnect=True)
                    return self._mariadb_conn
                except Exception:
                    self._mariadb_conn = None

            cfg = self.hostinger_cfg
            host = cfg.get("host") or os.getenv("CODE_HELPER_DB_HOST", "srv1502.hstgr.io")
            ip_fallback = cfg.get("ip_fallback") or os.getenv("CODE_HELPER_DB_IP_FALLBACK", "")
            port = int(cfg.get("port") or os.getenv("CODE_HELPER_DB_PORT", "3306"))
            user = cfg.get("user") or os.getenv("CODE_HELPER_DB_USER", "u177424397_code_help_adm")
            password = cfg.get("password") or os.getenv("CODE_HELPER_DB_PASSWORD", "")
            database = cfg.get("database") or os.getenv("CODE_HELPER_DB_NAME", "u177424397_code_helper")
            timeout = int(cfg.get("connect_timeout", 10))
            read_timeout = int(cfg.get("read_timeout", timeout))
            write_timeout = int(cfg.get("write_timeout", timeout))

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
            except Exception as err:
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
                        raise RuntimeError(f"Сбой подключения к Hostinger MariaDB: {fb_err}") from fb_err
                raise RuntimeError(f"Сбой подключения к Hostinger MariaDB: {err}") from err

    def _try_init_mariadb(self) -> bool:
        """Попытка инициализации MariaDB на Hostinger с созданием необходимых таблиц."""
        try:
            conn = self._get_mariadb_connection()
            with conn.cursor() as cur:
                for query in MARIADB_INIT_QUERIES:
                    cur.execute(query)
            self._is_mariadb_active = True
            logger.info("[CodeHelperStorage] Успешное подключение к MariaDB на Hostinger (u177424397_code_helper).")
            return True
        except Exception as exc:
            self._is_mariadb_active = False
            self._last_mariadb_error = str(exc)
            logger.warning(
                f"[CodeHelperStorage] MariaDB на Hostinger недоступна ({exc}). "
                f"Используется локальный SQLite кэш: {self.sqlite_path}"
            )
            return False

    @contextmanager
    def _connect_sqlite(self) -> Generator[sqlite3.Connection, None, None]:
        """Контекстный менеджер соединения с локальной SQLite базой (режим WAL + busy_timeout)."""
        conn = sqlite3.connect(str(self.sqlite_path), timeout=15.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_sqlite_schema(self) -> None:
        """Инициализация схемы таблиц в SQLite."""
        with self._connect_sqlite() as conn:
            conn.executescript(SQLITE_INIT_SCRIPT)

    def test_connection(self) -> Dict[str, Any]:
        """Тестирует прямое соединение с Hostinger MariaDB и возвращает диагностику."""
        start_t = time.perf_counter()
        cfg = self.hostinger_cfg
        res: Dict[str, Any] = {
            "target": f"{cfg.get('host', 'srv1502.hstgr.io')}:{cfg.get('port', 3306)}",
            "database": cfg.get("database", "u177424397_code_helper"),
            "user": cfg.get("user", "u177424397_code_help_adm"),
            "active_engine": self.active_engine,
            "sqlite_path": str(self.sqlite_path),
        }
        try:
            conn = self._get_mariadb_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT VERSION() AS ver, DATABASE() AS cur_db, NOW() AS srv_time;")
                row = cur.fetchone()
            elapsed_ms = round((time.perf_counter() - start_t) * 1000, 2)
            self._is_mariadb_active = True
            res.update({
                "status": "connected",
                "server_version": row.get("ver") if row else "unknown",
                "current_database": row.get("cur_db") if row else cfg.get("database"),
                "server_time": str(row.get("srv_time")) if row else "",
                "latency_ms": elapsed_ms,
                "message": "Успешное соединение с Hostinger MariaDB.",
            })
            return res
        except Exception as exc:
            self._is_mariadb_active = False
            self._last_mariadb_error = str(exc)
            elapsed_ms = round((time.perf_counter() - start_t) * 1000, 2)
            help_msg = (
                "Если ошибка 'Access denied': перейдите в панель управления Hostinger (hPanel) -> "
                "'Базы данных' -> 'Удаленный MySQL' (Remote MySQL) и добавьте IP '%' (любой хост) "
                "или текущий IP клиента для доступа к базе u177424397_code_helper."
            )
            res.update({
                "status": "error",
                "error": str(exc),
                "latency_ms": elapsed_ms,
                "hostinger_instruction": help_msg,
                "fallback_active": True,
            })
            return res

    def save_index(
        self,
        stats: IndexStats,
        chunks: List[CodeChunk],
        symbols: List[CodeSymbol],
    ) -> None:
        """Сохраняет метаданные индекса, чанки и символы в активное хранилище."""
        # 1. Сохраняем в локальный SQLite (надежный кэш)
        with self._connect_sqlite() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO code_indexes 
                   (name, project_root, total_files, total_chunks, total_symbols, elapsed_seconds, updated_at, storage_engine)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    stats.name, stats.project_root, stats.total_files,
                    stats.total_chunks, stats.total_symbols, stats.elapsed_seconds,
                    stats.updated_at, "sqlite",
                ),
            )
            conn.execute("DELETE FROM code_chunks WHERE index_name = ?", (stats.name,))
            conn.execute("DELETE FROM code_symbols WHERE index_name = ?", (stats.name,))

            chunk_records = [
                (
                    c.chunk_id, c.index_name, c.file_path, c.symbol_name, c.symbol_type,
                    c.start_line, c.end_line, c.content, c.signature, c.docstring,
                    c.snippet, c.content_hash, c.updated_at,
                )
                for c in chunks
            ]
            conn.executemany(
                """INSERT INTO code_chunks 
                   (chunk_id, index_name, file_path, symbol_name, symbol_type, start_line, end_line,
                    content, signature, docstring, snippet, content_hash, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                chunk_records,
            )

            symbol_records = [
                (
                    s.symbol_id, s.index_name, s.symbol, s.short_name, s.symbol_type,
                    s.file_path, s.signature, s.docstring, s.start_line, s.end_line,
                    json.dumps(s.related_symbols, ensure_ascii=False), s.snippet, s.updated_at,
                )
                for s in symbols
            ]
            conn.executemany(
                """INSERT INTO code_symbols 
                   (symbol_id, index_name, symbol, short_name, symbol_type, file_path,
                    signature, docstring, start_line, end_line, related_symbols_json, snippet, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                symbol_records,
            )

        # 2. Если MariaDB активна, сохраняем в Hostinger MariaDB
        if self._is_mariadb_active or self.engine_preference in ("mariadb", "hostinger"):
            try:
                conn_mdb = self._get_mariadb_connection()
                with conn_mdb.cursor() as cur:
                    cur.execute(
                        """REPLACE INTO code_indexes 
                           (name, project_root, total_files, total_chunks, total_symbols, elapsed_seconds, updated_at, storage_engine)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                        (
                            stats.name, stats.project_root, stats.total_files,
                            stats.total_chunks, stats.total_symbols, stats.elapsed_seconds,
                            stats.updated_at, "mariadb",
                        ),
                    )
                    cur.execute("DELETE FROM code_chunks WHERE index_name = %s", (stats.name,))
                    cur.execute("DELETE FROM code_symbols WHERE index_name = %s", (stats.name,))

                    if chunk_records:
                        cur.executemany(
                            """INSERT INTO code_chunks 
                               (chunk_id, index_name, file_path, symbol_name, symbol_type, start_line, end_line,
                                content, signature, docstring, snippet, content_hash, updated_at)
                               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                            chunk_records,
                        )
                    if symbol_records:
                        cur.executemany(
                            """INSERT INTO code_symbols 
                               (symbol_id, index_name, symbol, short_name, symbol_type, file_path,
                                signature, docstring, start_line, end_line, related_symbols_json, snippet, updated_at)
                               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                            symbol_records,
                        )
                self._is_mariadb_active = True
            except Exception as exc:
                self._is_mariadb_active = False
                logger.warning(f"[CodeHelperStorage] Синхронизация с Hostinger MariaDB завершилась с ошибкой: {exc}")

    def list_indexes(self) -> List[Dict[str, Any]]:
        """Возвращает список всех сохраненных индексов."""
        if self._is_mariadb_active:
            try:
                conn = self._get_mariadb_connection()
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM code_indexes ORDER BY updated_at DESC")
                    return cur.fetchall() or []
            except Exception:
                self._is_mariadb_active = False

        with self._connect_sqlite() as conn:
            rows = conn.execute("SELECT * FROM code_indexes ORDER BY updated_at DESC").fetchall()
            return [dict(r) for r in rows]

    def search_chunks(self, query: str, index_name: str = "codebase", top_k: int = 5) -> List[Dict[str, Any]]:
        """Выполняет текстовый и символьный поиск чанков в индексе."""
        pattern = f"%{query.strip()}%"
        if self._is_mariadb_active:
            try:
                conn = self._get_mariadb_connection()
                with conn.cursor() as cur:
                    sql = """
                        SELECT chunk_id, file_path, symbol_name, symbol_type, start_line, end_line,
                               signature, snippet, content
                        FROM code_chunks
                        WHERE index_name = %s AND (symbol_name LIKE %s OR content LIKE %s OR file_path LIKE %s)
                        LIMIT %s
                    """
                    cur.execute(sql, (index_name, pattern, pattern, pattern, top_k))
                    return cur.fetchall() or []
            except Exception:
                self._is_mariadb_active = False

        with self._connect_sqlite() as conn:
            sql = """
                SELECT chunk_id, file_path, symbol_name, symbol_type, start_line, end_line,
                       signature, snippet, content
                FROM code_chunks
                WHERE index_name = ? AND (symbol_name LIKE ? OR content LIKE ? OR file_path LIKE ?)
                LIMIT ?
            """
            rows = conn.execute(sql, (index_name, pattern, pattern, pattern, top_k)).fetchall()
            return [dict(r) for r in rows]

    def search_symbols(self, query: str, index_name: str = "codebase", limit: int = 15) -> List[Dict[str, Any]]:
        """Поиск AST-символов по имени или префиксу."""
        pattern = f"%{query.strip()}%"
        if self._is_mariadb_active:
            try:
                conn = self._get_mariadb_connection()
                with conn.cursor() as cur:
                    sql = """
                        SELECT symbol_id, symbol, short_name, symbol_type, file_path,
                               signature, docstring, start_line, end_line, snippet
                        FROM code_symbols
                        WHERE index_name = %s AND (symbol LIKE %s OR short_name LIKE %s)
                        LIMIT %s
                    """
                    cur.execute(sql, (index_name, pattern, pattern, limit))
                    return cur.fetchall() or []
            except Exception:
                self._is_mariadb_active = False

        with self._connect_sqlite() as conn:
            sql = """
                SELECT symbol_id, symbol, short_name, symbol_type, file_path,
                       signature, docstring, start_line, end_line, snippet
                FROM code_symbols
                WHERE index_name = ? AND (symbol LIKE ? OR short_name LIKE ?)
                LIMIT ?
            """
            rows = conn.execute(sql, (index_name, pattern, pattern, limit)).fetchall()
            return [dict(r) for r in rows]

    def save_diagnostic(self, conclusion: DiagnosticConclusion, query: str = "", error_message: str = "") -> None:
        """Сохраняет диагностическое заключение в базу данных."""
        diag_id = f"diag_{int(time.time() * 1000)}"
        aff_json = json.dumps([loc.model_dump() for loc in conclusion.affected_locations], ensure_ascii=False)
        rem_json = json.dumps([stp.model_dump() for stp in conclusion.remediation_steps], ensure_ascii=False)
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        with self._connect_sqlite() as conn:
            conn.execute(
                """INSERT INTO code_diagnostics 
                   (id, query, error_message, summary, root_cause, explanation, severity, confidence,
                    affected_locations_json, remediation_steps_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    diag_id, query, error_message, conclusion.summary, conclusion.root_cause,
                    conclusion.explanation, conclusion.severity, conclusion.confidence,
                    aff_json, rem_json, now_str,
                ),
            )
