# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry Sqlite - TelemetrySecurityReaderMixin
# =============================================================================
# Description:
#   Миксин чтения событий безопасности и питания: журнал Security (в таблице incidents),
#   неудачные входы, создание процессов, сессии и события питания (в единой таблице power_sessions).
#
# File: reader_security.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry.sqlite
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-16 13:06:00
# =============================================================================

from __future__ import annotations

"""Миксин чтения событий безопасности и питания из консолидированных таблиц incidents, inventory_state и power_sessions."""

import json
import time
from typing import Any, Dict, List, Optional, Union

from .delta_inventory import DeltaInventory

try:
    from logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class TelemetrySecurityReaderMixin:
    """Миксин чтения событий безопасности и питания из 12 базовых таблиц SQLite."""

    @staticmethod
    def _unpack_security_row(row: Any) -> Dict[str, Any]:
        """Распаковывает запись из таблицы incidents (domain='security_event') в формат события безопасности."""
        d = dict(row)
        details = json.loads(d["details_json"]) if d.get("details_json") else {}
        item = {**d, **details}
        item["id"] = d.get("id")
        item["event_id"] = d.get("event_id") or details.get("event_id")
        item["event_record_id"] = d.get("event_record_id") or details.get("event_record_id")
        item["channel"] = d.get("channel") or details.get("channel") or "Security"
        item["timestamp"] = d.get("timestamp") or details.get("timestamp")
        item["created_at"] = d.get("created_at") or details.get("created_at")
        item["message"] = d.get("message") or details.get("message") or ""
        if "event_data" not in item or not isinstance(item.get("event_data"), dict):
            if item.get("event_data_json"):
                try:
                    item["event_data"] = json.loads(item["event_data_json"])
                except Exception:
                    item["event_data"] = {}
            else:
                item["event_data"] = {}
        return item

    def get_security_events(
        self,
        event_id: Optional[int] = None,
        user: Optional[str] = None,
        process_name: Optional[str] = None,
        pid: Optional[int] = None,
        channel: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        since_epoch: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Выборка нормализованных событий журнала безопасности Windows из таблицы incidents."""
        conditions: List[str] = ["domain = 'security_event'"]
        params: List[Any] = []

        if channel:
            conditions.append("channel = ?")
            params.append(str(channel))

        if event_id is not None:
            conditions.append("event_id = ?")
            params.append(int(event_id))

        if since_epoch is not None:
            conditions.append("created_at >= ?")
            params.append(float(since_epoch))

        where_clause = f"WHERE {' AND '.join(conditions)}"
        query = f'''
            SELECT * FROM incidents
            {where_clause}
            ORDER BY id DESC
            LIMIT ?
        '''
        fetch_limit = max((int(limit) + int(offset)) * 3, 200) if (user or process_name or pid is not None) else (int(limit) + int(offset))
        params.append(fetch_limit)

        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = [self._unpack_security_row(r) for r in cursor.fetchall()]

        filtered: List[Dict[str, Any]] = []
        for r in rows:
            if user:
                u_low = user.lower()
                if u_low not in str(r.get("subject_user") or "").lower() and u_low not in str(r.get("target_user") or "").lower():
                    continue
            if process_name:
                p_low = process_name.lower()
                if p_low not in str(r.get("process_name") or "").lower() and p_low not in str(r.get("parent_process_name") or "").lower():
                    continue
            if pid is not None:
                if int(r.get("process_id") or 0) != int(pid) and int(r.get("parent_process_id") or 0) != int(pid):
                    continue
            filtered.append(r)

        return filtered[int(offset) : int(offset) + int(limit)]

    def get_security_failed_logons(self, limit: int = 50, hours: int = 24) -> List[Dict[str, Any]]:
        """Выборка событий неудачных попыток входа и сбоев аутентификации (4625, 4771) из таблицы incidents."""
        since_time = time.time() - (hours * 3600) if hours > 0 else 0.0
        query = '''
            SELECT * FROM incidents
            WHERE domain = 'security_event' AND event_id IN (4625, 4771) AND created_at >= ?
            ORDER BY id DESC
            LIMIT ?
        '''
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (since_time, int(limit)))
            return [self._unpack_security_row(r) for r in cursor.fetchall()]

    def get_security_process_creations(
        self,
        process_name: Optional[str] = None,
        user: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Выборка событий создания процессов (Event ID 4688) из таблицы incidents."""
        events = self.get_security_events(
            event_id=4688,
            user=user,
            process_name=process_name,
            limit=limit,
        )
        return events

    def get_security_bookmark(self, channel: str = "Security") -> Optional[Dict[str, Any]]:
        """Извлечение последней сохраненной закладки для канала журнала событий из inventory_state."""
        with self._cm.lock, self._cm.get_connection() as conn:
            rows = DeltaInventory.get_active(conn.cursor(), "security_bookmarks")
            for r in rows:
                if r.get("channel") == channel or r.get("entity_key") == channel:
                    return dict(r)
            return None

    def get_security_stats(self) -> Dict[str, Any]:
        """Получить сводную статистику по событиям безопасности в базе данных SQLite."""
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*), MAX(event_record_id), MIN(timestamp), MAX(timestamp) FROM incidents WHERE domain = 'security_event'"
            )
            row = cursor.fetchone()
            total_events = row[0] if row else 0
            max_rec_id = row[1] if row and row[1] else 0
            min_ts = row[2] if row and row[2] else ""
            max_ts = row[3] if row and row[3] else ""

            cursor.execute(
                '''
                SELECT event_id, COUNT(*) as cnt
                FROM incidents
                WHERE domain = 'security_event' AND event_id IS NOT NULL
                GROUP BY event_id
                ORDER BY cnt DESC
                LIMIT 10
                '''
            )
            top_ids = {r[0]: r[1] for r in cursor.fetchall()}

            cursor.execute("SELECT COUNT(*) FROM incidents WHERE domain = 'security_event' AND event_id = 4688")
            proc_events = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM incidents WHERE domain = 'security_event' AND event_id = 4625")
            failed_logons = cursor.fetchone()[0]

            return {
                "total_events": total_events,
                "max_record_id": max_rec_id,
                "first_event_time": min_ts,
                "latest_event_time": max_ts,
                "process_creation_count": proc_events,
                "failed_logon_count": failed_logons,
                "top_event_ids": top_ids,
            }

    def get_power_sessions(
        self,
        limit: int = 50,
        offset: int = 0,
        shutdown_type: Optional[str] = None,
        unexpected_only: bool = False,
        clean_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """Извлечь список сессий питания операционной системы из таблицы power_sessions."""
        where_clauses: List[str] = ["(record_type = 'session' OR record_type IS NULL)"]
        params: List[Any] = []

        if shutdown_type:
            where_clauses.append("LOWER(shutdown_type) = LOWER(?)")
            params.append(shutdown_type)

        if unexpected_only:
            where_clauses.append("unexpected_shutdown = 1")
        elif clean_only:
            where_clauses.append("clean_shutdown = 1 AND unexpected_shutdown = 0")

        sql = "SELECT * FROM power_sessions WHERE " + " AND ".join(where_clauses)
        sql += " ORDER BY boot_time DESC LIMIT ? OFFSET ?"
        params.extend([max(1, limit), max(0, offset)])

        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            results: List[Dict[str, Any]] = []
            for row in rows:
                item = dict(row)
                if item.get("initiator_chain_json"):
                    try:
                        item["initiator_chain"] = json.loads(item["initiator_chain_json"])
                    except Exception:
                        item["initiator_chain"] = []
                else:
                    item["initiator_chain"] = []

                if item.get("events_json"):
                    try:
                        item["events"] = json.loads(item["events_json"])
                    except Exception:
                        item["events"] = []
                else:
                    item["events"] = []

                item["clean_shutdown"] = bool(item.get("clean_shutdown"))
                item["unexpected_shutdown"] = bool(item.get("unexpected_shutdown"))
                results.append(item)
            return results

    def get_power_session_by_id(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Извлечь детальную информацию по конкретной сессии питания."""
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            if session_id.isdigit():
                cursor.execute("SELECT * FROM power_sessions WHERE id = ? OR session_id = ?", (int(session_id), session_id))
            else:
                cursor.execute("SELECT * FROM power_sessions WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            if not row:
                return None
            item = dict(row)
            if item.get("initiator_chain_json"):
                try:
                    item["initiator_chain"] = json.loads(item["initiator_chain_json"])
                except Exception:
                    item["initiator_chain"] = []
            else:
                item["initiator_chain"] = []

            if item.get("events_json"):
                try:
                    item["events"] = json.loads(item["events_json"])
                except Exception:
                    item["events"] = []
            else:
                item["events"] = []

            item["clean_shutdown"] = bool(item.get("clean_shutdown"))
            item["unexpected_shutdown"] = bool(item.get("unexpected_shutdown"))
            return item

    def get_power_events(
        self,
        limit: int = 100,
        offset: int = 0,
        event_id: Optional[Union[int, List[int]]] = None,
        event_type: Optional[str] = None,
        hours: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Извлечь события питания и жизненного цикла из единой таблицы power_sessions (record_type='power_event')."""
        where_clauses: List[str] = ["record_type = 'power_event'"]
        params: List[Any] = []

        if isinstance(event_id, list) and event_id:
            placeholders = ", ".join(["?"] * len(event_id))
            where_clauses.append(f"event_id IN ({placeholders})")
            params.extend(event_id)
        elif isinstance(event_id, int) and event_id > 0:
            where_clauses.append("event_id = ?")
            params.append(event_id)

        if event_type:
            where_clauses.append("LOWER(classification) = LOWER(?)")
            params.append(event_type)

        if hours and hours > 0:
            cutoff = time.time() - (hours * 3600)
            where_clauses.append("created_at >= ?")
            params.append(cutoff)

        sql = "SELECT * FROM power_sessions WHERE " + " AND ".join(where_clauses)
        sql += " ORDER BY boot_time DESC, id DESC LIMIT ? OFFSET ?"
        params.extend([max(1, limit), max(0, offset)])

        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            results: List[Dict[str, Any]] = []
            for row in rows:
                item = dict(row)
                item["timestamp"] = item.get("boot_time")
                item["event_type"] = item.get("classification") or item.get("shutdown_type")
                item["unexpected"] = bool(item.get("unexpected_shutdown"))
                if item.get("details_json"):
                    try:
                        item["details"] = json.loads(item["details_json"])
                    except Exception:
                        item["details"] = {}
                else:
                    item["details"] = {}
                results.append(item)
            return results

    def get_power_summary(self) -> Dict[str, Any]:
        """Получить сводную статистику по сессиям и событиям питания из таблицы power_sessions."""
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM power_sessions WHERE record_type = 'session' OR record_type IS NULL")
            total_sessions = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM power_sessions WHERE (record_type = 'session' OR record_type IS NULL) AND clean_shutdown = 1 AND unexpected_shutdown = 0")
            clean_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM power_sessions WHERE (record_type = 'session' OR record_type IS NULL) AND unexpected_shutdown = 1")
            unexpected_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM power_sessions WHERE event_id = 1001 OR bugcheck_code IS NOT NULL OR bugcheck IS NOT NULL")
            bsod_count = cursor.fetchone()[0]

            cursor.execute("SELECT * FROM power_sessions WHERE (record_type = 'session' OR record_type IS NULL) AND shutdown_time IS NOT NULL ORDER BY boot_time DESC LIMIT 1")
            last_shutdown_row = cursor.fetchone()

            last_shutdown_type = last_shutdown_row["shutdown_type"] if last_shutdown_row else None
            last_initiator = last_shutdown_row["initiator"] if last_shutdown_row else None
            last_reason = last_shutdown_row["reason"] if last_shutdown_row else None

            cursor.execute("SELECT * FROM power_sessions WHERE (record_type = 'session' OR record_type IS NULL) AND shutdown_time IS NULL ORDER BY boot_time DESC LIMIT 1")
            active_row = cursor.fetchone()

            cur_boot = active_row["boot_time"] if active_row else ""
            cur_uptime_sec = active_row["uptime_seconds"] if active_row else 0.0
            cur_uptime_human = active_row["uptime_human"] if active_row else ""

            return {
                "total_sessions_count": total_sessions,
                "clean_shutdowns_count": clean_count,
                "unexpected_shutdowns_count": unexpected_count,
                "bsod_count": bsod_count,
                "current_boot_time": cur_boot,
                "current_uptime_seconds": cur_uptime_sec,
                "current_uptime_human": cur_uptime_human,
                "last_shutdown_type": last_shutdown_type,
                "last_initiator": last_initiator,
                "last_reason": last_reason,
            }

