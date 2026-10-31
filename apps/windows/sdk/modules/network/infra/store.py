# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Network Infra - Snapshot Store (SQLite)
# =============================================================================
# Description:
#   Хранилище истории снимков сетевой конфигурации. Таблицы: метаданные снимков,
#   статусы источников, нормализованные объекты, диагностические результаты.
#   Ограничение роста: максимум снимков и возраст (retention), очистка при
#   сохранении и по запросу.
#
# Usage Examples:
#   store = NetworkInfraStore(Path('infra.db'), max_snapshots=200, retention_days=90)
#   sid = store.save_snapshot(collection)
#
# File: store.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.network.infra
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 16:00:00
# =============================================================================

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from logger import logger

_SCHEMA = '''
CREATE TABLE IF NOT EXISTS network_snapshots (
    id TEXT PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT NOT NULL, status TEXT NOT NULL,
    errors_json TEXT NOT NULL DEFAULT '[]', objects_count INTEGER NOT NULL DEFAULT 0,
    findings_count INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS network_snapshot_sources (
    snapshot_id TEXT NOT NULL REFERENCES network_snapshots(id) ON DELETE CASCADE, source TEXT NOT NULL,
    status TEXT NOT NULL, description TEXT, data_json TEXT NOT NULL, PRIMARY KEY (snapshot_id, source));
CREATE TABLE IF NOT EXISTS network_snapshot_objects (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id TEXT NOT NULL REFERENCES network_snapshots(id) ON DELETE CASCADE, data_key TEXT NOT NULL,
    object_id TEXT NOT NULL, kind TEXT NOT NULL, name TEXT, source TEXT, data_json TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_net_obj_snapshot ON network_snapshot_objects(snapshot_id);
CREATE TABLE IF NOT EXISTS network_snapshot_findings (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id TEXT NOT NULL REFERENCES network_snapshots(id) ON DELETE CASCADE, rule_code TEXT NOT NULL,
    severity TEXT NOT NULL, title TEXT, checked_at TEXT, data_json TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_net_find_snapshot ON network_snapshot_findings(snapshot_id);
'''


class SnapshotNotFound(KeyError):
    """Снимок с указанным идентификатором не найден."""


class NetworkInfraStore:
    """SQLite-хранилище снимков сетевой конфигурации."""

    def __init__(self, db_path: Path, max_snapshots: int = 200, retention_days: int = 90) -> None:
        """Инициализирует хранилище и создаёт схему.

        Args:
            db_path: Путь к файлу БД.
            max_snapshots: Максимум хранимых снимков.
            retention_days: Максимальный возраст снимка, дней.
        """
        self.db_path = Path(db_path)
        self.max_snapshots = max_snapshots
        self.retention_days = retention_days
        self._lock = threading.Lock()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn:
            conn.executescript(_SCHEMA)
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.execute('PRAGMA foreign_keys=ON')
        conn.row_factory = sqlite3.Row
        return conn

    def save_snapshot(self, collection: Dict[str, Any]) -> str:
        """Сохраняет снимок и применяет политику хранения.

        Args:
            collection: Результат сбора (started_at, finished_at, status, sources, data, findings).

        Returns:
            str: Идентификатор сохранённого снимка.
        """
        sid = uuid.uuid4().hex
        data: Dict[str, List[Dict[str, Any]]] = collection.get('data', {})
        findings = collection.get('findings', [])
        errors = [e for s in collection.get('sources', {}).values() for e in s.get('errors', [])]
        objects_count = sum(len(v) for v in data.values())
        with self._lock, closing(self._connect()) as conn:
            conn.execute('INSERT INTO network_snapshots VALUES (?,?,?,?,?,?,?)',
                         (sid, collection['started_at'], collection['finished_at'], collection['status'],
                          json.dumps(errors, ensure_ascii=False), objects_count, len(findings)))
            conn.executemany('INSERT INTO network_snapshot_sources VALUES (?,?,?,?,?)',
                             [(sid, name, meta.get('status', 'unknown'), meta.get('source', ''),
                               json.dumps(meta, ensure_ascii=False)) for name, meta in collection['sources'].items()])
            conn.executemany(
                'INSERT INTO network_snapshot_objects (snapshot_id,data_key,object_id,kind,name,source,data_json) VALUES (?,?,?,?,?,?,?)',
                [(sid, key, it['id'], it['kind'], it.get('name'), it.get('source'), json.dumps(it, ensure_ascii=False))
                 for key, items in data.items() for it in items])
            conn.executemany(
                'INSERT INTO network_snapshot_findings (snapshot_id,rule_code,severity,title,checked_at,data_json) VALUES (?,?,?,?,?,?)',
                [(sid, f['rule_code'], f['severity'], f['title'], f['checked_at'], json.dumps(f, ensure_ascii=False))
                 for f in findings])
            conn.commit()
            self._prune(conn)
        logger.info(f'[NetworkInfra] Снимок {sid} сохранён: объектов={objects_count}, диагностик={len(findings)}')
        return sid

    def _prune(self, conn: sqlite3.Connection) -> int:
        """Удаляет снимки старше retention_days и сверх max_snapshots."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=self.retention_days)).isoformat(timespec='seconds')
        removed = conn.execute('DELETE FROM network_snapshots WHERE finished_at < ?', (cutoff,)).rowcount
        removed += conn.execute(
            'DELETE FROM network_snapshots WHERE id NOT IN (SELECT id FROM network_snapshots '
            'ORDER BY finished_at DESC, rowid DESC LIMIT ?)', (self.max_snapshots,)).rowcount
        conn.commit()
        if removed:
            logger.info(f'[NetworkInfra] Очистка истории: удалено снимков {removed}')
        return removed

    def prune(self) -> int:
        """Выполняет очистку истории по политике хранения.

        Returns:
            int: Количество удалённых снимков.
        """
        with self._lock, closing(self._connect()) as conn:
            return self._prune(conn)

    def list_snapshots(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Возвращает метаданные снимков (новые первыми).

        Args:
            limit: Максимальное число записей.

        Returns:
            List[Dict[str, Any]]: Метаданные со статусами источников.
        """
        with closing(self._connect()) as conn:
            rows = conn.execute('SELECT * FROM network_snapshots ORDER BY finished_at DESC, rowid DESC LIMIT ?',
                                (max(1, min(limit, 500)),)).fetchall()
            result = []
            for r in rows:
                srcs = conn.execute('SELECT source,status FROM network_snapshot_sources WHERE snapshot_id=?', (r['id'],)).fetchall()
                result.append({'id': r['id'], 'started_at': r['started_at'], 'finished_at': r['finished_at'],
                               'status': r['status'], 'errors': json.loads(r['errors_json']),
                               'objects_count': r['objects_count'], 'findings_count': r['findings_count'],
                               'sources': {s['source']: s['status'] for s in srcs}})
            return result

    def get_snapshot(self, snapshot_id: str) -> Dict[str, Any]:
        """Возвращает полный снимок (метаданные, источники, объекты, диагностики).

        Args:
            snapshot_id: Идентификатор снимка.

        Returns:
            Dict[str, Any]: Снимок.

        Raises:
            SnapshotNotFound: Снимок не найден.
        """
        with closing(self._connect()) as conn:
            head = conn.execute('SELECT * FROM network_snapshots WHERE id=?', (snapshot_id,)).fetchone()
            if head is None:
                raise SnapshotNotFound(snapshot_id)
            sources = {r['source']: json.loads(r['data_json']) for r in conn.execute(
                'SELECT source,data_json FROM network_snapshot_sources WHERE snapshot_id=?', (snapshot_id,))}
            data: Dict[str, List[Dict[str, Any]]] = {}
            for r in conn.execute('SELECT data_key,data_json FROM network_snapshot_objects WHERE snapshot_id=? ORDER BY seq', (snapshot_id,)):
                data.setdefault(r['data_key'], []).append(json.loads(r['data_json']))
            findings = [json.loads(r['data_json']) for r in conn.execute(
                'SELECT data_json FROM network_snapshot_findings WHERE snapshot_id=? ORDER BY seq', (snapshot_id,))]
        return {'id': head['id'], 'started_at': head['started_at'], 'finished_at': head['finished_at'],
                'status': head['status'], 'errors': json.loads(head['errors_json']), 'sources': sources,
                'data': data, 'findings': findings}

    def findings_history(self, limit: int = 200, severity: Optional[str] = None) -> List[Dict[str, Any]]:
        """Возвращает историю диагностических результатов по всем снимкам.

        Args:
            limit: Максимум записей.
            severity: Необязательный фильтр по важности.

        Returns:
            List[Dict[str, Any]]: Результаты с полем snapshot_id.
        """
        sql = ('SELECT f.snapshot_id, f.data_json FROM network_snapshot_findings f JOIN network_snapshots s ON s.id=f.snapshot_id '
               + ('WHERE f.severity=? ' if severity else '') + 'ORDER BY s.finished_at DESC, f.seq LIMIT ?')
        args = ((severity,) if severity else ()) + (max(1, min(limit, 1000)),)
        with closing(self._connect()) as conn:
            return [{**json.loads(r['data_json']), 'snapshot_id': r['snapshot_id']} for r in conn.execute(sql, args)]

