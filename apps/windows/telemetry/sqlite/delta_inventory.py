# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry Sqlite - Delta Inventory
# =============================================================================
# Description:
#   Универсальное хранилище «списочных» состояний (службы, правила брандмауэра,
#   профили и т.п.) в режиме Change-Only: в БД пишутся только появления,
#   исчезновения и изменения элементов с датой обнаружения.
#
# Usage Examples:
#   Python API:
#     from apps.windows.telemetry.sqlite.delta_inventory import DeltaInventory
#
#     stats = DeltaInventory.sync(cursor, 'services', {'Spooler': {'state': 'RUNNING'}})
#     active = DeltaInventory.get_active(cursor, 'services')
#
# File: delta_inventory.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry.sqlite
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-16 13:25:00
# =============================================================================

from __future__ import annotations

"""Change-Only хранилище инвентаризации: текущее состояние + журнал дельт с датами обнаружения."""

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

DELTA_INVENTORY_DDL: Tuple[str, ...] = (
    '''
    CREATE TABLE IF NOT EXISTS inventory_state (
        domain TEXT NOT NULL,
        entity_key TEXT NOT NULL,
        attrs_json TEXT NOT NULL DEFAULT '{}',
        attrs_hash TEXT NOT NULL DEFAULT '',
        first_seen TEXT NOT NULL DEFAULT '',
        last_changed TEXT NOT NULL DEFAULT '',
        removed_at TEXT,
        state_json TEXT,
        updated_at REAL DEFAULT 0.0,
        PRIMARY KEY (domain, entity_key)
    ) WITHOUT ROWID;
    ''',
    '''
    CREATE TABLE IF NOT EXISTS inventory_changes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        domain TEXT NOT NULL,
        entity_key TEXT NOT NULL,
        change_type TEXT NOT NULL,
        detected_at TEXT NOT NULL DEFAULT '',
        timestamp TEXT,
        created_at REAL DEFAULT 0.0,
        old_json TEXT,
        new_json TEXT,
        diff_json TEXT
    );
    ''',
)

DELTA_INVENTORY_INDEX_DDL: Tuple[str, ...] = (
    'CREATE INDEX IF NOT EXISTS idx_inv_changes_domain_time ON inventory_changes(domain, detected_at);',
)

INVENTORY_SCHEMA_SQL: str = "\n".join((*DELTA_INVENTORY_DDL, *DELTA_INVENTORY_INDEX_DDL))


def _hash(attrs: Dict[str, Any]) -> str:
    """Возвращает стабильный хэш атрибутов (порядок ключей не влияет)."""
    return hashlib.sha1(json.dumps(attrs, sort_keys=True, ensure_ascii=False, default=str).encode('utf-8')).hexdigest()


class DeltaInventory:
    """Синхронизация наборов сущностей с БД: записываются только дельты."""

    @staticmethod
    def sync(
        cursor: sqlite3.Cursor,
        domain: str,
        items: Dict[str, Dict[str, Any]],
        detected_at: Optional[str] = None,
    ) -> Dict[str, int]:
        """Сравнивает полный текущий набор сущностей домена с сохранённым и пишет только изменения.

        Args:
            cursor: Курсор активного соединения SQLite.
            domain: Имя домена (например, 'services', 'firewall_rules').
            items: Полный текущий набор {ключ сущности: атрибуты}.
            detected_at: ISO-время обнаружения (по умолчанию — текущее UTC).

        Returns:
            Dict[str, int]: Счётчики {'added', 'removed', 'modified'}; все нули — в БД ничего не записано.
        """
        ts = detected_at or datetime.now(timezone.utc).isoformat()
        stats = {'added': 0, 'removed': 0, 'modified': 0}

        cursor.execute(
            'SELECT entity_key, attrs_json, attrs_hash, removed_at FROM inventory_state WHERE domain = ?',
            (domain,),
        )
        stored = {r[0]: (r[1], r[2], r[3]) for r in cursor.fetchall()}

        for key, attrs in items.items():
            new_json = json.dumps(attrs, sort_keys=True, ensure_ascii=False, default=str)
            new_hash = _hash(attrs)
            prev = stored.get(key)
            if prev is None or prev[2] is not None:
                # Новая сущность или вернувшаяся после исчезновения
                cursor.execute(
                    'INSERT OR REPLACE INTO inventory_state '
                    '(domain, entity_key, attrs_json, attrs_hash, first_seen, last_changed, removed_at) '
                    'VALUES (?, ?, ?, ?, ?, ?, NULL)',
                    (domain, key, new_json, new_hash, ts, ts),
                )
                DeltaInventory._log(cursor, domain, key, 'added', ts, None, new_json)
                stats['added'] += 1
            elif prev[1] != new_hash:
                cursor.execute(
                    'UPDATE inventory_state SET attrs_json = ?, attrs_hash = ?, last_changed = ? '
                    'WHERE domain = ? AND entity_key = ?',
                    (new_json, new_hash, ts, domain, key),
                )
                DeltaInventory._log(cursor, domain, key, 'modified', ts, prev[0], new_json)
                stats['modified'] += 1

        for key, (old_json, _h, removed_at) in stored.items():
            if removed_at is None and key not in items:
                cursor.execute(
                    'UPDATE inventory_state SET removed_at = ?, last_changed = ? WHERE domain = ? AND entity_key = ?',
                    (ts, ts, domain, key),
                )
                DeltaInventory._log(cursor, domain, key, 'removed', ts, old_json, None)
                stats['removed'] += 1

        return stats

    @staticmethod
    def patch(
        cursor: sqlite3.Cursor,
        domain: str,
        key: str,
        updates: Dict[str, Any],
        detected_at: Optional[str] = None,
    ) -> bool:
        """Точечно изменяет или создаёт атрибуты одной активной сущности и журналирует изменение.

        Returns:
            bool: True если сущность добавлена или атрибуты действительно изменились, иначе False.
        """
        cursor.execute(
            'SELECT attrs_json FROM inventory_state WHERE domain = ? AND entity_key = ? AND removed_at IS NULL',
            (domain, key),
        )
        row = cursor.fetchone()
        ts = detected_at or datetime.now(timezone.utc).isoformat()
        if not row:
            new_json = json.dumps(updates, sort_keys=True, ensure_ascii=False, default=str)
            cursor.execute(
                'INSERT OR REPLACE INTO inventory_state '
                '(domain, entity_key, attrs_json, attrs_hash, first_seen, last_changed, removed_at, state_json, updated_at) '
                'VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?)',
                (domain, key, new_json, _hash(updates), ts, ts, new_json, datetime.now(timezone.utc).timestamp()),
            )
            DeltaInventory._log(cursor, domain, key, 'added', ts, None, new_json)
            return True
        attrs = json.loads(row[0]) if row[0] else {}
        merged = {**attrs, **updates}
        if merged == attrs:
            return False
        new_json = json.dumps(merged, sort_keys=True, ensure_ascii=False, default=str)
        cursor.execute(
            'UPDATE inventory_state SET attrs_json = ?, attrs_hash = ?, last_changed = ?, state_json = ?, updated_at = ? WHERE domain = ? AND entity_key = ?',
            (new_json, _hash(merged), ts, new_json, datetime.now(timezone.utc).timestamp(), domain, key),
        )
        DeltaInventory._log(cursor, domain, key, 'modified', ts, row[0], new_json)
        return True

    @staticmethod
    def get_active(cursor: sqlite3.Cursor, domain: str) -> List[Dict[str, Any]]:
        """Возвращает активные сущности домена: атрибуты + first_seen/last_changed."""
        cursor.execute(
            'SELECT entity_key, attrs_json, first_seen, last_changed FROM inventory_state '
            'WHERE domain = ? AND removed_at IS NULL ORDER BY entity_key',
            (domain,),
        )
        return [
            {**json.loads(r[1]), 'entity_key': r[0], 'first_seen': r[2], 'last_changed': r[3]}
            for r in cursor.fetchall()
        ]

    @staticmethod
    def get_changes(cursor: sqlite3.Cursor, domain: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Возвращает журнал дельт (новые сверху), опционально по домену."""
        if domain:
            cursor.execute(
                'SELECT * FROM inventory_changes WHERE domain = ? ORDER BY id DESC LIMIT ?', (domain, int(limit))
            )
        else:
            cursor.execute('SELECT * FROM inventory_changes ORDER BY id DESC LIMIT ?', (int(limit),))
        cols = [d[0] for d in cursor.description]
        result: List[Dict[str, Any]] = []
        for r in cursor.fetchall():
            d = dict(zip(cols, r))
            d['old'] = json.loads(d.pop('old_json')) if d.get('old_json') else None
            d['new'] = json.loads(d.pop('new_json')) if d.get('new_json') else None
            result.append(d)
        return result

    @staticmethod
    def _log(cursor: sqlite3.Cursor, domain: str, key: str, change_type: str, ts: str,
             old_json: Optional[str], new_json: Optional[str]) -> None:
        """Добавляет запись в журнал дельт."""
        cursor.execute(
            'INSERT INTO inventory_changes (domain, entity_key, change_type, detected_at, old_json, new_json) '
            'VALUES (?, ?, ?, ?, ?, ?)',
            (domain, key, change_type, ts, old_json, new_json),
        )

