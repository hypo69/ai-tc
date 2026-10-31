# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows SDK - Tool Chains Storage
# =============================================================================
# Description:
#   SQLite хранилище определений, запусков, шагов и доказательств цепочек инструментов.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.core.tool_chains.storage import ToolChainStorage
#     storage = ToolChainStorage()
#
# File: storage.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.core.tool_chains
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 17:35:00
# =============================================================================

from __future__ import annotations

"""SQLite хранилище цепочек инструментов, запусков, артефактов и истории исполнения."""

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional
from logger import logger

from apps.windows.sdk.core.tool_chains.models import (
    ChainDefinition,
    ChainRunReport,
    ChainRunStatus,
    StepExecutionResult,
    StepRunStatus,
)


class ToolChainStorage:
    """Хранилище SQLite для версионирования, аудита и отслеживания состояния цепочек инструментов."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        """Инициализирует базу данных SQLite для цепочек инструментов.

        Args:
            db_path: Путь к файлу базы данных SQLite. По умолчанию `tool_chains.db` в директории данных.
        """
        if db_path is None:
            base_dir = Path(__file__).resolve().parents[4] / "data" / "windows"
            base_dir.mkdir(parents=True, exist_ok=True)
            self._db_path = str(base_dir / "tool_chains.db")
        else:
            self._db_path = db_path

        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Создает подключение к базе данных с поддержкой WAL-режима."""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        return conn

    def _init_db(self) -> None:
        """Создает необходимые таблицы и индексы в SQLite."""
        schema_sql = """
        CREATE TABLE IF NOT EXISTS workflow_definitions (
            chain_id TEXT PRIMARY KEY,
            title_ru TEXT NOT NULL,
            description TEXT,
            category TEXT,
            initial_step_id TEXT,
            definition_json TEXT NOT NULL,
            requires_restore_point INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS workflow_runs (
            run_id TEXT PRIMARY KEY,
            chain_id TEXT,
            user_intent TEXT,
            status TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT,
            total_duration_ms REAL DEFAULT 0.0,
            root_cause_identified TEXT,
            restore_point_id TEXT,
            rolled_back INTEGER DEFAULT 0,
            report_json TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS tool_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            step_id TEXT NOT NULL,
            tool_id TEXT NOT NULL,
            status TEXT NOT NULL,
            exit_code INTEGER DEFAULT 0,
            stdout TEXT,
            stderr TEXT,
            structured_data_json TEXT,
            duration_ms REAL DEFAULT 0.0,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            next_step_decided TEXT,
            FOREIGN KEY (run_id) REFERENCES workflow_runs(run_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_workflow_runs_chain ON workflow_runs(chain_id);
        CREATE INDEX IF NOT EXISTS idx_workflow_runs_status ON workflow_runs(status);
        CREATE INDEX IF NOT EXISTS idx_tool_runs_run_id ON tool_runs(run_id);
        """
        try:
            with self._get_connection() as conn:
                conn.executescript(schema_sql)
        except Exception as e:
            logger.error(f"Ошибка инициализации БД цепочек инструментов: {e}")

    def save_definition(self, definition: ChainDefinition) -> bool:
        """Сохраняет или обновляет определение цепочки инструментов в каталоге."""
        query = """
        INSERT INTO workflow_definitions (chain_id, title_ru, description, category, initial_step_id, definition_json, requires_restore_point, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(chain_id) DO UPDATE SET
            title_ru = excluded.title_ru,
            description = excluded.description,
            category = excluded.category,
            initial_step_id = excluded.initial_step_id,
            definition_json = excluded.definition_json,
            requires_restore_point = excluded.requires_restore_point,
            updated_at = CURRENT_TIMESTAMP;
        """
        try:
            with self._get_connection() as conn:
                conn.execute(
                    query,
                    (
                        definition.chain_id,
                        definition.title_ru,
                        definition.description,
                        definition.category.value,
                        definition.initial_step_id,
                        json.dumps(definition.to_dict(), ensure_ascii=False),
                        1 if definition.requires_restore_point else 0,
                    ),
                )
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения определения цепочки {definition.chain_id}: {e}")
            return False

    def get_definition(self, chain_id: str) -> Optional[Dict[str, Any]]:
        """Загружает сохраненное определение цепочки по идентификатору."""
        query = "SELECT definition_json FROM workflow_definitions WHERE chain_id = ?;"
        try:
            with self._get_connection() as conn:
                row = conn.execute(query, (chain_id,)).fetchone()
                if row:
                    return json.loads(row["definition_json"])
        except Exception as e:
            logger.error(f"Ошибка чтения цепочки {chain_id}: {e}")
        return None

    def list_definitions(self) -> List[Dict[str, Any]]:
        """Возвращает список всех зарегистрированных шаблонов цепочек."""
        query = "SELECT chain_id, title_ru, description, category, initial_step_id, requires_restore_point, updated_at FROM workflow_definitions ORDER BY title_ru ASC;"
        results: List[Dict[str, Any]] = []
        try:
            with self._get_connection() as conn:
                rows = conn.execute(query).fetchall()
                for r in rows:
                    results.append({
                        "chain_id": r["chain_id"],
                        "title_ru": r["title_ru"],
                        "description": r["description"],
                        "category": r["category"],
                        "initial_step_id": r["initial_step_id"],
                        "requires_restore_point": bool(r["requires_restore_point"]),
                        "updated_at": r["updated_at"],
                    })
        except Exception as e:
            logger.error(f"Ошибка получения списка цепочек: {e}")
        return results

    def save_run(self, report: ChainRunReport) -> bool:
        """Сохраняет полный запуск цепочки и все связанные вызовы инструментов."""
        run_query = """
        INSERT INTO workflow_runs (run_id, chain_id, user_intent, status, start_time, end_time, total_duration_ms, root_cause_identified, restore_point_id, rolled_back, report_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_id) DO UPDATE SET
            status = excluded.status,
            end_time = excluded.end_time,
            total_duration_ms = excluded.total_duration_ms,
            root_cause_identified = excluded.root_cause_identified,
            restore_point_id = excluded.restore_point_id,
            rolled_back = excluded.rolled_back,
            report_json = excluded.report_json;
        """
        step_query = """
        INSERT INTO tool_runs (run_id, step_id, tool_id, status, exit_code, stdout, stderr, structured_data_json, duration_ms, start_time, end_time, next_step_decided)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        try:
            with self._get_connection() as conn:
                conn.execute(
                    run_query,
                    (
                        report.run_id,
                        report.chain_id,
                        report.user_intent,
                        report.status.value,
                        report.start_time,
                        report.end_time,
                        report.total_duration_ms,
                        report.root_cause_identified,
                        report.restore_point_id,
                        1 if report.rolled_back else 0,
                        json.dumps(report.to_dict(), ensure_ascii=False),
                    ),
                )
                conn.execute("DELETE FROM tool_runs WHERE run_id = ?;", (report.run_id,))
                for step in report.steps_executed:
                    conn.execute(
                        step_query,
                        (
                            report.run_id,
                            step.step_id,
                            step.tool_id,
                            step.status.value,
                            step.exit_code,
                            step.stdout,
                            step.stderr,
                            json.dumps(step.structured_data, ensure_ascii=False),
                            step.duration_ms,
                            step.start_time,
                            step.end_time,
                            step.next_step_decided,
                        ),
                    )
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения запуска цепочки {report.run_id}: {e}")
            return False

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Загружает сохраненный запуск цепочки по его ID."""
        query = "SELECT report_json FROM workflow_runs WHERE run_id = ?;"
        try:
            with self._get_connection() as conn:
                row = conn.execute(query, (run_id,)).fetchone()
                if row and row["report_json"]:
                    return json.loads(row["report_json"])
        except Exception as e:
            logger.error(f"Ошибка чтения запуска {run_id}: {e}")
        return None

    def list_recent_runs(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Возвращает список последних запусков цепочек."""
        query = """
        SELECT run_id, chain_id, user_intent, status, start_time, end_time, total_duration_ms, root_cause_identified, rolled_back
        FROM workflow_runs
        ORDER BY start_time DESC
        LIMIT ?;
        """
        results: List[Dict[str, Any]] = []
        try:
            with self._get_connection() as conn:
                rows = conn.execute(query, (limit,)).fetchall()
                for r in rows:
                    results.append({
                        "run_id": r["run_id"],
                        "chain_id": r["chain_id"],
                        "user_intent": r["user_intent"],
                        "status": r["status"],
                        "start_time": r["start_time"],
                        "end_time": r["end_time"],
                        "total_duration_ms": r["total_duration_ms"],
                        "root_cause_identified": r["root_cause_identified"],
                        "rolled_back": bool(r["rolled_back"]),
                    })
        except Exception as e:
            logger.error(f"Ошибка получения списка недавних запусков: {e}")
        return results

