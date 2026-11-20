# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Apps Windows DB - Database Manager Service
# =============================================================================
# Description:
#   Сервисный слой управления базами данных:
#   - Обзор параметров и структуры баз данных (Hostinger MariaDB и локальные SQLite);
#   - Прямое выполнение SQL команд (SELECT, INSERT, UPDATE, DELETE);
#   - Сжатие и оптимизация (SQLite VACUUM, MariaDB OPTIMIZE TABLE, очистка WAL);
#   - Экспорт таблиц и данных в форматы SQL Dump, JSON, CSV;
#   - Создание, скачивание, восстановление и удаление резервных копий (бэкапов) с ZIP-сжатием.
#
# File: db_manager_service.py
# Project: ai-tc
# Package: apps.windows.db
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-19 17:25:00
# =============================================================================

from __future__ import annotations

import csv
import io
import json
import os
import shutil
import sqlite3
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

try:
    import pymysql
    import pymysql.cursors
    HAS_PYMYSQL = True
except ImportError:
    HAS_PYMYSQL = False

from apps.windows.db.paths import resolve_system_knowledge_db_path, load_merged_system_config


class DBManagerService:
    """Сервис управления локальными и удаленными базами данных."""

    def __init__(
        self,
        base_dir: Optional[Path] = None,
        backups_dir: Optional[Path] = None,
        exports_dir: Optional[Path] = None,
    ) -> None:
        """Инициализирует сервис управления базами данных.

        Args:
            base_dir: Базовая директория проекта.
            backups_dir: Директория хранения резервных копий.
            exports_dir: Директория хранения файлов экспорта.
        """
        self.base_dir = base_dir or Path.cwd()
        self.backups_dir = backups_dir or (self.base_dir / "data" / "backups")
        self.exports_dir = exports_dir or (self.base_dir / "data" / "exports")
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        self.exports_dir.mkdir(parents=True, exist_ok=True)

    def _get_system_config(self) -> Dict[str, Any]:
        """Возвращает актуальную объединенную системную конфигурацию."""
        return load_merged_system_config()

    def get_configured_targets(self) -> List[Dict[str, Any]]:
        """Возвращает список доступных баз данных (SQLite и Hostinger MariaDB).

        Returns:
            List[Dict[str, Any]]: Метаданные доступных источников БД.
        """
        cfg = self._get_system_config()
        targets: List[Dict[str, Any]] = []

        # 1. Системные подсказки SQLite
        sq_path_raw = cfg.get("database", {}).get("sqlite", {}).get("path") or "data/windows_wikillm/knowledge.db"
        resolved_sq = resolve_system_knowledge_db_path(sq_path_raw)
        targets.append({
            "id": "sqlite:knowledge",
            "name": "WikiLLM Подсказки (SQLite)",
            "type": "sqlite",
            "path": str(resolved_sq),
            "description": "Локальная база общих подсказок и системных знаний Windows",
            "is_default": True,
        })

        # 2. Инструменты ИИ-агента SQLite
        inst_sq = self.base_dir / "data" / "ai_instruments" / "ai_instruments.db"
        targets.append({
            "id": "sqlite:instruments",
            "name": "Инструменты агента (SQLite)",
            "type": "sqlite",
            "path": str(inst_sq),
            "description": "Локальное хранилище каталога процедурных инструментов ИИ",
            "is_default": False,
        })

        # 3. Телеметрия SQLite
        telem_sq = self.base_dir / "data" / "telemetry.db"
        targets.append({
            "id": "sqlite:telemetry",
            "name": "Телеметрия (SQLite)",
            "type": "sqlite",
            "path": str(telem_sq),
            "description": "Журнал системных метрик CPU, памяти и накопителей",
            "is_default": False,
        })

        # 4. Hostinger MariaDB: База инструментов (u177424397_tool_chains)
        h_inst = cfg.get("ai_instruments", {}).get("hostinger", {})
        targets.append({
            "id": "hostinger:tool_chains",
            "name": "Hostinger: Tool Chains (MariaDB)",
            "type": "mariadb",
            "host": h_inst.get("host", "srv1373.hstgr.io"),
            "port": int(h_inst.get("port", 3306)),
            "database": h_inst.get("database", "u177424397_tool_chains"),
            "user": h_inst.get("user", "u177424397_ai_tc_admin"),
            "password": h_inst.get("password", "@Davidka#1969"),
            "connection_type": h_inst.get("connection_type", "direct"),
            "php_api_url": h_inst.get("php_api_url", "https://srv1502.hstgr.io/wikillm_hostinger.php"),
            "description": "Удаленная база инструментов и цепочек рассуждений на Hostinger",
            "is_default": False,
        })

        # 5. Hostinger MariaDB: База знаний (u177424397_comp_knowledge)
        h_wiki = cfg.get("database", {}).get("mariadb", {})
        targets.append({
            "id": "hostinger:comp_knowledge",
            "name": "Hostinger: Comp Knowledge (MariaDB)",
            "type": "mariadb",
            "host": h_wiki.get("host", "srv1502.hstgr.io"),
            "port": int(h_wiki.get("port", 3306)),
            "database": h_wiki.get("database", "u177424397_comp_knowledge"),
            "user": h_wiki.get("user", "u177424397_davidka"),
            "password": h_wiki.get("password", "@Davidka#1969"),
            "connection_type": h_wiki.get("connection_type", "php_api"),
            "php_api_url": h_wiki.get("php_api_url", "https://srv1502.hstgr.io/wikillm_hostinger.php"),
            "description": "Удаленная база знаний WikiLLM на сервере Hostinger",
            "is_default": False,
        })

        return targets

    def resolve_target(self, target_id: str) -> Dict[str, Any]:
        """Находит параметры базы по ее идентификатору.

        Args:
            target_id: ID целевой базы (например 'sqlite:knowledge' или прямой путь).

        Returns:
            Dict[str, Any]: Конфигурация выбранной базы.
        """
        targets = self.get_configured_targets()
        for t in targets:
            if t["id"].lower() == target_id.lower():
                return t

        # Если передан прямой путь к .db файлу
        p = Path(target_id)
        if not p.is_absolute():
            p = self.base_dir / p
        return {
            "id": f"sqlite:{p.stem}",
            "name": f"Пользовательская SQLite ({p.name})",
            "type": "sqlite",
            "path": str(p),
            "description": "Локальная пользовательская база данных SQLite",
            "is_default": False,
        }

    # --------------------------------------------------------------------------
    # 1. Обзор параметров и структуры (Overview)
    # --------------------------------------------------------------------------

    def get_overview(self) -> Dict[str, Any]:
        """Формирует полную сводку параметров, статусов и таблиц всех баз данных."""
        targets = self.get_configured_targets()
        overview_list: List[Dict[str, Any]] = []

        for target in targets:
            t_type = target.get("type")
            t_id = target.get("id")
            info: Dict[str, Any] = {
                "id": t_id,
                "name": target.get("name"),
                "type": t_type,
                "description": target.get("description"),
                "status": "unknown",
                "connected": False,
                "size_bytes": 0,
                "size_human": "0 B",
                "tables_count": 0,
                "tables": [],
            }

            if t_type == "sqlite":
                p = Path(target["path"])
                info["location"] = str(p)
                if p.exists() and p.is_file():
                    try:
                        sz = p.stat().st_size
                        info["size_bytes"] = sz
                        info["size_human"] = self._format_bytes(sz)
                        info["status"] = "online"
                        info["connected"] = True

                        conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
                        conn.row_factory = sqlite3.Row
                        try:
                            # Читаем параметры SQLite
                            page_sz = conn.execute("PRAGMA page_size;").fetchone()[0]
                            page_cnt = conn.execute("PRAGMA page_count;").fetchone()[0]
                            journal = conn.execute("PRAGMA journal_mode;").fetchone()[0]
                            info["parameters"] = {
                                "page_size": page_sz,
                                "page_count": page_cnt,
                                "journal_mode": str(journal).upper(),
                                "encoding": "UTF-8",
                                "engine": f"SQLite {sqlite3.sqlite_version}",
                            }

                            # Список таблиц
                            tables_cur = conn.execute(
                                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;"
                            )
                            t_names = [r[0] for r in tables_cur.fetchall()]
                            info["tables_count"] = len(t_names)
                            t_details = []
                            for tname in t_names:
                                cnt_cur = conn.execute(f'SELECT COUNT(*) FROM "{tname}";')
                                r_cnt = cnt_cur.fetchone()[0]
                                cols_cur = conn.execute(f'PRAGMA table_info("{tname}");')
                                cols = [{"cid": c[0], "name": c[1], "type": c[2], "notnull": c[3], "pk": c[5]} for c in cols_cur.fetchall()]
                                t_details.append({
                                    "name": tname,
                                    "rows": r_cnt,
                                    "columns": cols,
                                })
                            info["tables"] = t_details
                        finally:
                            conn.close()
                    except Exception as sq_err:
                        info["status"] = "error"
                        info["error"] = str(sq_err)
                else:
                    info["status"] = "not_found"
                    info["size_human"] = "Файл отсутствует"

            elif t_type == "mariadb":
                host = target.get("host", "")
                port = target.get("port", 3306)
                db_name = target.get("database", "")
                user = target.get("user", "")
                info["location"] = f"{host}:{port}/{db_name} ({user})"
                info["parameters"] = {
                    "host": host,
                    "port": port,
                    "database": db_name,
                    "user": user,
                    "engine": "MariaDB / MySQL (Hostinger)",
                    "connection_type": target.get("connection_type", "direct"),
                }
                # Пробуем проверить подключение
                if HAS_PYMYSQL:
                    t0 = time.perf_counter()
                    try:
                        conn = pymysql.connect(
                            host=host,
                            port=port,
                            user=user,
                            password=target.get("password", ""),
                            database=db_name,
                            connect_timeout=3,
                            read_timeout=3,
                            charset="utf8mb4",
                            cursorclass=pymysql.cursors.DictCursor,
                        )
                        latency_ms = round((time.perf_counter() - t0) * 1000, 1)
                        try:
                            with conn.cursor() as cur:
                                cur.execute("SELECT VERSION() AS ver;")
                                ver = cur.fetchone()["ver"]
                                info["parameters"]["server_version"] = ver
                                info["parameters"]["latency_ms"] = latency_ms

                                cur.execute("""
                                    SELECT table_name AS name, table_rows AS rows,
                                           (data_length + index_length) AS size_bytes,
                                           engine, table_collation
                                    FROM information_schema.tables
                                    WHERE table_schema = %s
                                    ORDER BY table_name;
                                """, (db_name,))
                                t_rows = cur.fetchall()
                                info["tables_count"] = len(t_rows)
                                total_sz = sum(int(r.get("size_bytes") or 0) for r in t_rows)
                                info["size_bytes"] = total_sz
                                info["size_human"] = self._format_bytes(total_sz)
                                info["tables"] = [{
                                    "name": r["name"],
                                    "rows": int(r.get("rows") or 0),
                                    "size_bytes": int(r.get("size_bytes") or 0),
                                    "size_human": self._format_bytes(int(r.get("size_bytes") or 0)),
                                    "engine": r.get("engine", "InnoDB"),
                                } for r in t_rows]
                                info["status"] = "online"
                                info["connected"] = True
                        finally:
                            conn.close()
                    except Exception as m_err:
                        info["status"] = "offline"
                        info["error"] = str(m_err)
                else:
                    info["status"] = "no_driver"
                    info["error"] = "Драйвер pymysql не установлен"

            overview_list.append(info)

        return {
            "targets": overview_list,
            "server_time": datetime.now(timezone.utc).isoformat(),
        }

    # --------------------------------------------------------------------------
    # 2. Прямое выполнение SQL команд (Query Console)
    # --------------------------------------------------------------------------

    def execute_query(
        self,
        target_id: str,
        sql: str,
        params: Optional[Dict[str, Any]] = None,
        max_rows: int = 200,
    ) -> Dict[str, Any]:
        """Выполняет произвольный SQL запрос (SELECT, INSERT, UPDATE, DELETE, DDL).

        Args:
            target_id: Идентификатор базы.
            sql: SQL запрос.
            params: Параметры запроса (опционально).
            max_rows: Максимальное количество строк в ответе.

        Returns:
            Dict[str, Any]: Результат выполнения запроса.
        """
        clean_sql = (sql or "").strip()
        if not clean_sql:
            return {"success": False, "error": "Пустой SQL запрос.", "execution_time_ms": 0.0}

        target = self.resolve_target(target_id)
        t_type = target.get("type")
        first_token = clean_sql.split()[0].upper()
        is_select = first_token in ("SELECT", "SHOW", "PRAGMA", "DESCRIBE", "DESC", "EXPLAIN")

        t0 = time.perf_counter()
        if t_type == "sqlite":
            p = Path(target.get("path", ""))
            p.parent.mkdir(parents=True, exist_ok=True)
            try:
                conn = sqlite3.connect(str(p), timeout=10.0)
                conn.row_factory = sqlite3.Row
                try:
                    cursor = conn.cursor()
                    if params:
                        cursor.execute(clean_sql, params)
                    else:
                        cursor.execute(clean_sql)

                    exec_time = round((time.perf_counter() - t0) * 1000, 2)
                    if is_select:
                        cols = [d[0] for d in cursor.description] if cursor.description else []
                        rows = [dict(r) for r in cursor.fetchmany(max_rows)]
                        return {
                            "success": True,
                            "target": target["id"],
                            "is_query": True,
                            "columns": cols,
                            "rows": rows,
                            "row_count": len(rows),
                            "affected_rows": 0,
                            "execution_time_ms": exec_time,
                        }
                    else:
                        conn.commit()
                        aff = cursor.rowcount
                        return {
                            "success": True,
                            "target": target["id"],
                            "is_query": False,
                            "columns": [],
                            "rows": [],
                            "row_count": 0,
                            "affected_rows": aff if aff >= 0 else 0,
                            "execution_time_ms": exec_time,
                        }
                finally:
                    conn.close()
            except Exception as ex:
                return {
                    "success": False,
                    "target": target["id"],
                    "error": f"Ошибка SQLite: {ex}",
                    "execution_time_ms": round((time.perf_counter() - t0) * 1000, 2),
                }

        elif t_type == "mariadb":
            if not HAS_PYMYSQL:
                return {"success": False, "error": "PyMySQL не установлен", "execution_time_ms": 0.0}
            try:
                conn = pymysql.connect(
                    host=target.get("host", ""),
                    port=int(target.get("port", 3306)),
                    user=target.get("user", ""),
                    password=target.get("password", ""),
                    database=target.get("database", ""),
                    connect_timeout=5,
                    charset="utf8mb4",
                    cursorclass=pymysql.cursors.DictCursor,
                    autocommit=True,
                )
                try:
                    with conn.cursor() as cur:
                        if params:
                            cur.execute(clean_sql, params)
                        else:
                            cur.execute(clean_sql)
                        exec_time = round((time.perf_counter() - t0) * 1000, 2)
                        if is_select:
                            rows = list(cur.fetchmany(max_rows))
                            cols = [col[0] for col in cur.description] if cur.description else []
                            return {
                                "success": True,
                                "target": target["id"],
                                "is_query": True,
                                "columns": cols,
                                "rows": rows,
                                "row_count": len(rows),
                                "affected_rows": 0,
                                "execution_time_ms": exec_time,
                            }
                        else:
                            aff = cur.rowcount
                            return {
                                "success": True,
                                "target": target["id"],
                                "is_query": False,
                                "columns": [],
                                "rows": [],
                                "row_count": 0,
                                "affected_rows": aff if aff >= 0 else 0,
                                "execution_time_ms": exec_time,
                            }
                finally:
                    conn.close()
            except Exception as ex:
                return {
                    "success": False,
                    "target": target["id"],
                    "error": f"Ошибка MariaDB: {ex}",
                    "execution_time_ms": round((time.perf_counter() - t0) * 1000, 2),
                }

        return {"success": False, "error": f"Неизвестный тип базы: {t_type}", "execution_time_ms": 0.0}

    # --------------------------------------------------------------------------
    # 3. Инструменты для сжатия и оптимизации (Compression Tools)
    # --------------------------------------------------------------------------

    def compress_database(
        self,
        target_id: str,
        action: str = "vacuum",
        table_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Сжимает и оптимизирует базу данных.

        Для SQLite: VACUUM + PRAGMA wal_checkpoint(TRUNCATE).
        Для MariaDB: OPTIMIZE TABLE / ANALYZE TABLE.
        """
        target = self.resolve_target(target_id)
        t_type = target.get("type")

        if t_type == "sqlite":
            p = Path(target.get("path", ""))
            if not p.exists():
                return {"success": False, "error": f"Файл базы не найден: {p}"}

            before_bytes = p.stat().st_size
            try:
                conn = sqlite3.connect(str(p), timeout=20.0)
                try:
                    conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                    conn.execute("VACUUM;")
                    conn.commit()
                finally:
                    conn.close()

                after_bytes = p.stat().st_size
                saved = max(0, before_bytes - after_bytes)
                pct = round((saved / before_bytes * 100), 1) if before_bytes > 0 else 0.0

                return {
                    "success": True,
                    "target": target["id"],
                    "action": "vacuum",
                    "before_bytes": before_bytes,
                    "after_bytes": after_bytes,
                    "saved_bytes": saved,
                    "saved_percent": pct,
                    "before_human": self._format_bytes(before_bytes),
                    "after_human": self._format_bytes(after_bytes),
                    "saved_human": self._format_bytes(saved),
                    "message": f"SQLite база успешно сжата (VACUUM): освобождено {self._format_bytes(saved)} ({pct}%).",
                }
            except Exception as ex:
                return {"success": False, "error": f"Ошибка сжатия SQLite: {ex}"}

        elif t_type == "mariadb":
            if not HAS_PYMYSQL:
                return {"success": False, "error": "PyMySQL не установлен"}
            try:
                conn = pymysql.connect(
                    host=target.get("host", ""),
                    port=int(target.get("port", 3306)),
                    user=target.get("user", ""),
                    password=target.get("password", ""),
                    database=target.get("database", ""),
                    connect_timeout=10,
                    cursorclass=pymysql.cursors.DictCursor,
                    autocommit=True,
                )
                try:
                    with conn.cursor() as cur:
                        if table_name and table_name.strip():
                            target_tables = [table_name.strip()]
                        else:
                            cur.execute("""
                                SELECT table_name AS name
                                FROM information_schema.tables
                                WHERE table_schema = %s;
                            """, (target.get("database"),))
                            target_tables = [r["name"] for r in cur.fetchall()]

                        results = []
                        for t in target_tables:
                            cur.execute(f"OPTIMIZE TABLE `{t}`;")
                            res = cur.fetchall()
                            results.extend(res)

                    return {
                        "success": True,
                        "target": target["id"],
                        "action": "optimize",
                        "tables_optimized": target_tables,
                        "details": results,
                        "message": f"Оптимизация таблиц MariaDB завершена: {', '.join(target_tables)}.",
                    }
                finally:
                    conn.close()
            except Exception as ex:
                return {"success": False, "error": f"Ошибка оптимизации MariaDB: {ex}"}

        return {"success": False, "error": f"Неподдерживаемый тип базы: {t_type}"}

    # --------------------------------------------------------------------------
    # 4. Экспорт из баз (включая базы на хостинге) (Export)
    # --------------------------------------------------------------------------

    def export_database(
        self,
        target_id: str,
        table_name: Optional[str] = "all",
        export_format: str = "sql",
    ) -> Dict[str, Any]:
        """Экспортирует таблицы и данные в форматы SQL Dump, JSON или CSV.

        Args:
            target_id: Идентификатор базы (Hostinger или SQLite).
            table_name: Имя таблицы или 'all'.
            export_format: 'sql', 'json', 'csv'.

        Returns:
            Dict[str, Any]: Метаданные созданного файла экспорта.
        """
        target = self.resolve_target(target_id)
        fmt = (export_format or "sql").lower().strip()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_tid = target["id"].replace(":", "_").replace("/", "_")
        filename = f"export_{safe_tid}_{stamp}.{fmt}"
        out_path = self.exports_dir / filename

        tables_data = self._dump_tables_raw(target, table_name)
        if not tables_data:
            return {"success": False, "error": "Нет данных или таблиц для экспорта"}

        total_records = sum(len(t["rows"]) for t in tables_data)

        if fmt == "json":
            export_payload = {
                "database_target": target["id"],
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "tables_count": len(tables_data),
                "total_records": total_records,
                "tables": tables_data,
            }
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(export_payload, f, ensure_ascii=False, indent=2)

        elif fmt == "csv":
            # Если одна таблица — чистый CSV, если несколько — конкатенация или первая
            with open(out_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                for t in tables_data:
                    writer.writerow([f"# TABLE: {t['name']}"])
                    if t["columns"]:
                        writer.writerow(t["columns"])
                    for row in t["rows"]:
                        writer.writerow([row.get(c, "") for c in t["columns"]])
                    writer.writerow([])

        else:  # SQL dump
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(f"-- =========================================================\n")
                f.write(f"-- AI-TC Database Export Dump\n")
                f.write(f"-- Target: {target['id']} ({target.get('name')})\n")
                f.write(f"-- Date: {datetime.now(timezone.utc).isoformat()}\n")
                f.write(f"-- =========================================================\n\n")

                for t in tables_data:
                    tname = t["name"]
                    cols = t["columns"]
                    f.write(f"-- Таблица: {tname} ({len(t['rows'])} записей)\n")
                    if t.get("create_sql"):
                        f.write(f"{t['create_sql']};\n\n")
                    for row in t["rows"]:
                        col_names_str = ", ".join(f"`{c}`" for c in cols)
                        vals = []
                        for c in cols:
                            v = row.get(c)
                            if v is None:
                                vals.append("NULL")
                            elif isinstance(v, (int, float)):
                                vals.append(str(v))
                            else:
                                esc = str(v).replace("'", "''").replace("\\", "\\\\")
                                vals.append(f"'{esc}'")
                        vals_str = ", ".join(vals)
                        f.write(f"INSERT INTO `{tname}` ({col_names_str}) VALUES ({vals_str});\n")
                    f.write("\n")

        file_sz = out_path.stat().st_size
        return {
            "success": True,
            "filename": filename,
            "filepath": str(out_path),
            "download_url": f"/api/v1/db-manager/download/{filename}",
            "format": fmt,
            "size_bytes": file_sz,
            "size_human": self._format_bytes(file_sz),
            "records_count": total_records,
            "tables_count": len(tables_data),
            "message": f"Экспорт успешно сформирован: {filename} ({self._format_bytes(file_sz)}, {total_records} записей).",
        }

    def _dump_tables_raw(self, target: Dict[str, Any], table_name: Optional[str]) -> List[Dict[str, Any]]:
        """Извлекает структуру и строки таблиц для экспорта."""
        t_type = target.get("type")
        tables_res: List[Dict[str, Any]] = []

        if t_type == "sqlite":
            p = Path(target.get("path", ""))
            if not p.exists():
                return []
            conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            try:
                cur = conn.cursor()
                if table_name and table_name != "all":
                    cur.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name = ?;", (table_name,))
                else:
                    cur.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;")
                t_list = cur.fetchall()

                for row in t_list:
                    tname = row["name"]
                    c_sql = row["sql"]
                    # Строки
                    r_cur = conn.execute(f'SELECT * FROM "{tname}";')
                    cols = [d[0] for d in r_cur.description] if r_cur.description else []
                    rows = [dict(r) for r in r_cur.fetchall()]
                    tables_res.append({
                        "name": tname,
                        "create_sql": c_sql,
                        "columns": cols,
                        "rows": rows,
                    })
            finally:
                conn.close()

        elif t_type == "mariadb":
            if not HAS_PYMYSQL:
                return []
            conn = pymysql.connect(
                host=target.get("host", ""),
                port=int(target.get("port", 3306)),
                user=target.get("user", ""),
                password=target.get("password", ""),
                database=target.get("database", ""),
                connect_timeout=10,
                cursorclass=pymysql.cursors.DictCursor,
            )
            try:
                with conn.cursor() as cur:
                    if table_name and table_name != "all":
                        t_names = [table_name]
                    else:
                        cur.execute("SHOW TABLES;")
                        t_names = [list(r.values())[0] for r in cur.fetchall()]

                    for tname in t_names:
                        cur.execute(f"SHOW CREATE TABLE `{tname}`;")
                        cr_row = cur.fetchone()
                        c_sql = list(cr_row.values())[1] if cr_row else ""
                        cur.execute(f"SELECT * FROM `{tname}`;")
                        rows = cur.fetchall()
                        cols = [d[0] for d in cur.description] if cur.description else []
                        tables_res.append({
                            "name": tname,
                            "create_sql": c_sql,
                            "columns": cols,
                            "rows": list(rows),
                        })
            finally:
                conn.close()

        return tables_res

    # --------------------------------------------------------------------------
    # 5. Управление резервными копиями (Backups)
    # --------------------------------------------------------------------------

    def create_backup(self, target_id: str, compress_zip: bool = True) -> Dict[str, Any]:
        """Создает резервную копию базы данных (с опциональным ZIP сжатием).

        Args:
            target_id: Идентификатор базы.
            compress_zip: Сжимать ли в zip-архив.

        Returns:
            Dict[str, Any]: Метаданные созданной копии.
        """
        target = self.resolve_target(target_id)
        t_type = target.get("type")
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_tid = target["id"].replace(":", "_").replace("/", "_")

        if t_type == "sqlite":
            src_p = Path(target.get("path", ""))
            if not src_p.exists():
                return {"success": False, "error": f"Файл базы не найден: {src_p}"}

            raw_filename = f"backup_{safe_tid}_{stamp}.db"
            raw_path = self.backups_dir / raw_filename

            # Атомарное создание бэкапа SQLite
            src_conn = sqlite3.connect(str(src_p), timeout=20.0)
            dst_conn = sqlite3.connect(str(raw_path))
            try:
                with dst_conn:
                    src_conn.backup(dst_conn)
            finally:
                dst_conn.close()
                src_conn.close()

            final_path = raw_path
            final_filename = raw_filename

            if compress_zip:
                zip_filename = f"{raw_filename}.zip"
                zip_path = self.backups_dir / zip_filename
                with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                    zf.write(raw_path, arcname=raw_filename)
                raw_path.unlink(missing_ok=True)
                final_path = zip_path
                final_filename = zip_filename

        elif t_type == "mariadb":
            # Для MariaDB формируем SQL дамп и сжимаем в zip
            exp = self.export_database(target_id, table_name="all", export_format="sql")
            if not exp.get("success"):
                return {"success": False, "error": f"Ошибка дампа MariaDB: {exp.get('error')}"}

            raw_path = Path(exp["filepath"])
            raw_filename = f"backup_{safe_tid}_{stamp}.sql"
            target_raw = self.backups_dir / raw_filename
            shutil.move(raw_path, target_raw)

            final_path = target_raw
            final_filename = raw_filename

            if compress_zip:
                zip_filename = f"{raw_filename}.zip"
                zip_path = self.backups_dir / zip_filename
                with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                    zf.write(target_raw, arcname=raw_filename)
                target_raw.unlink(missing_ok=True)
                final_path = zip_path
                final_filename = zip_filename
        else:
            return {"success": False, "error": f"Неподдерживаемый тип базы: {t_type}"}

        sz = final_path.stat().st_size
        return {
            "success": True,
            "filename": final_filename,
            "filepath": str(final_path),
            "download_url": f"/api/v1/db-manager/download/{final_filename}",
            "target": target["id"],
            "size_bytes": sz,
            "size_human": self._format_bytes(sz),
            "is_compressed": compress_zip,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "message": f"Бэкап успешно создан: {final_filename} ({self._format_bytes(sz)}).",
        }

    def list_backups(self) -> List[Dict[str, Any]]:
        """Возвращает список всех существующих резервных копий."""
        backups: List[Dict[str, Any]] = []
        if not self.backups_dir.exists():
            return backups

        for p in self.backups_dir.glob("backup_*"):
            if p.is_file():
                sz = p.stat().st_size
                mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat()
                is_zip = p.suffix.lower() == ".zip"
                backups.append({
                    "filename": p.name,
                    "filepath": str(p),
                    "download_url": f"/api/v1/db-manager/download/{p.name}",
                    "size_bytes": sz,
                    "size_human": self._format_bytes(sz),
                    "is_compressed": is_zip,
                    "created_at": mtime,
                })

        backups.sort(key=lambda x: x["created_at"], reverse=True)
        return backups

    def delete_backup(self, filename: str) -> Dict[str, Any]:
        """Удаляет файл резервной копии."""
        safe_name = Path(filename).name
        target_path = self.backups_dir / safe_name
        if target_path.exists() and target_path.is_file():
            target_path.unlink()
            return {"success": True, "message": f"Бэкап {safe_name} успешно удален."}
        return {"success": False, "error": f"Файл {safe_name} не найден."}

    def restore_backup(self, backup_name: str, target_id: Optional[str] = None) -> Dict[str, Any]:
        """Восстанавливает базу данных из резервной копии.

        Args:
            backup_name: Имя файла бэкапа в data/backups/.
            target_id: Целевая база для восстановления.

        Returns:
            Dict[str, Any]: Результат восстановления.
        """
        safe_name = Path(backup_name).name
        b_path = self.backups_dir / safe_name
        if not b_path.exists():
            return {"success": False, "error": f"Файл бэкапа {safe_name} не найден."}

        # Распаковываем, если zip
        temp_extracted: Optional[Path] = None
        if b_path.suffix.lower() == ".zip":
            with zipfile.ZipFile(b_path, "r") as zf:
                names = zf.namelist()
                if not names:
                    return {"success": False, "error": "Архив бэкапа пуст."}
                extracted_name = names[0]
                temp_extracted = self.backups_dir / f"tmp_restore_{extracted_name}"
                with zf.open(extracted_name) as source, open(temp_extracted, "wb") as target:
                    shutil.copyfileobj(source, target)
            working_path = temp_extracted
        else:
            working_path = b_path

        try:
            # Если целевая база не указана — определяем из имени бэкапа
            resolved_tid = target_id
            if not resolved_tid:
                if "sqlite_knowledge" in working_path.name:
                    resolved_tid = "sqlite:knowledge"
                elif "sqlite_instruments" in working_path.name:
                    resolved_tid = "sqlite:instruments"
                elif "sqlite_telemetry" in working_path.name:
                    resolved_tid = "sqlite:telemetry"
                elif "hostinger_tool_chains" in working_path.name:
                    resolved_tid = "hostinger:tool_chains"
                elif "hostinger_comp_knowledge" in working_path.name:
                    resolved_tid = "hostinger:comp_knowledge"
                else:
                    resolved_tid = "sqlite:knowledge"

            target = self.resolve_target(resolved_tid)
            t_type = target.get("type")

            if t_type == "sqlite":
                dest_p = Path(target.get("path", ""))
                dest_p.parent.mkdir(parents=True, exist_ok=True)
                # Безопасно копируем
                shutil.copy2(working_path, dest_p)
                return {
                    "success": True,
                    "target": target["id"],
                    "restored_from": safe_name,
                    "message": f"База SQLite ({target['id']}) успешно восстановлена из бэкапа {safe_name}.",
                }

            elif t_type == "mariadb":
                # Для MariaDB выполняем SQL скрипт
                sql_content = working_path.read_text(encoding="utf-8")
                res = self.execute_query(target["id"], sql_content)
                if not res.get("success"):
                    return {"success": False, "error": f"Ошибка выполнения SQL дампа: {res.get('error')}"}
                return {
                    "success": True,
                    "target": target["id"],
                    "restored_from": safe_name,
                    "message": f"База MariaDB ({target['id']}) успешно восстановлена из SQL дампа {safe_name}.",
                }
            return {"success": False, "error": f"Неподдерживаемый тип базы: {t_type}"}
        finally:
            if temp_extracted and temp_extracted.exists():
                temp_extracted.unlink(missing_ok=True)

    @staticmethod
    def _format_bytes(size: int) -> str:
        """Форматирует размер в байтах в человекочитаемый вид."""
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.2f} MB"
        return f"{size / (1024 * 1024 * 1024):.2f} GB"
