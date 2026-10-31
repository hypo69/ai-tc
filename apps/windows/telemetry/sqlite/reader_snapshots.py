# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry Sqlite - TelemetrySnapshotReaderMixin
# =============================================================================
# Description:
#   Миксин чтения снапшотов системы и процессов, истории, сводок, инцидентов,
#   сенсоров и иерархии CPU из 12 консолидированных таблиц SQLite.
#
# File: reader_snapshots.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry.sqlite
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-20 18:43:00
# =============================================================================

from __future__ import annotations

"""Миксин чтения снапшотов системы и процессов, истории, сводок, инцидентов, сенсоров и иерархии CPU."""

import json
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional, Union

try:
    from logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class TelemetrySnapshotReaderMixin:
    """Миксин чтения снапшотов системы и процессов, истории, сводок, инцидентов, сенсоров и иерархии CPU."""

    def get_snapshots(self, limit: int = 60, since_epoch: Optional[float] = None) -> List[Dict[str, Any]]:
        """Извлекает исторические срезы системной телеметрии с LOCF-реконструкцией параметров."""
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            if since_epoch is not None:
                cursor.execute(
                    "SELECT * FROM system_snapshots WHERE created_at >= ? ORDER BY id DESC LIMIT ?",
                    (since_epoch, limit),
                )
            else:
                cursor.execute("SELECT * FROM system_snapshots ORDER BY id DESC LIMIT ?", (limit,))
            raw_rows = [dict(row) for row in cursor.fetchall()]
            return self._reconstructor.reconstruct_snapshots_batch(raw_rows, conn)

    def get_latest_cpu(self) -> Optional[Dict[str, Any]]:
        """Извлекает последние метрики процессора с LOCF-восстановлением параметров."""
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT id, timestamp, created_at, hostname, cpu_total_percent, cpu_frequency_mhz
                FROM system_snapshots
                WHERE cpu_total_percent IS NOT NULL
                ORDER BY id DESC
                LIMIT 1;
                '''
            )
            row = cursor.fetchone()
            if not row:
                cursor.execute(
                    "SELECT id, timestamp, created_at, hostname, cpu_total_percent, cpu_frequency_mhz FROM system_snapshots ORDER BY id DESC LIMIT 1;"
                )
                row = cursor.fetchone()
            return dict(row) if row else None

    def get_cpu_history(self, limit: int = 60, since_epoch: Optional[float] = None) -> List[Dict[str, Any]]:
        """Извлекает историю нагрузки процессора с LOCF-реконструкцией пропусков."""
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            if since_epoch is not None:
                cursor.execute(
                    '''
                    SELECT id, timestamp, created_at, cpu_total_percent, cpu_frequency_mhz
                    FROM system_snapshots
                    WHERE created_at >= ?
                    ORDER BY id DESC
                    LIMIT ?;
                    ''',
                    (since_epoch, limit),
                )
            else:
                cursor.execute(
                    '''
                    SELECT id, timestamp, created_at, cpu_total_percent, cpu_frequency_mhz
                    FROM system_snapshots
                    ORDER BY id DESC
                    LIMIT ?;
                    ''',
                    (limit,),
                )
            raw_rows = [dict(r) for r in cursor.fetchall()]
            if not raw_rows:
                return []

            last_cpu_pct = 0.0
            last_cpu_freq = 0.0
            min_id = min(r.get("id", 0) for r in raw_rows)
            cursor.execute(
                "SELECT cpu_total_percent, cpu_frequency_mhz FROM system_snapshots WHERE id < ? AND cpu_total_percent IS NOT NULL ORDER BY id DESC LIMIT 1",
                (min_id,),
            )
            init_row = cursor.fetchone()
            if init_row:
                last_cpu_pct = float(init_row[0] or 0.0)
                last_cpu_freq = float(init_row[1] or 0.0)

            raw_rows.reverse()
            for r in raw_rows:
                if r.get("cpu_total_percent") is not None:
                    last_cpu_pct = float(r["cpu_total_percent"])
                else:
                    r["cpu_total_percent"] = last_cpu_pct

                if r.get("cpu_frequency_mhz") is not None:
                    last_cpu_freq = float(r["cpu_frequency_mhz"])
                else:
                    r["cpu_frequency_mhz"] = last_cpu_freq

            raw_rows.reverse()
            return raw_rows

    def get_latest_storage_data(self) -> Dict[str, Any]:
        """Извлекает последние данные о накопителях и разделах с гарантированной LOCF-подтяжкой."""
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT id, timestamp, created_at, disks_json, physical_disks_json
                FROM system_snapshots
                ORDER BY id DESC
                LIMIT 1;
                '''
            )
            row = cursor.fetchone()
            if not row:
                return {"partitions": [], "physical_disks": []}

            partitions: List[Dict[str, Any]] = []
            if row["disks_json"]:
                try:
                    partitions = json.loads(row["disks_json"])
                except Exception:
                    partitions = []
            if not partitions:
                cursor.execute(
                    '''
                    SELECT disks_json FROM system_snapshots
                    WHERE disks_json IS NOT NULL AND disks_json != '' AND disks_json != '[]'
                    ORDER BY id DESC LIMIT 1;
                    '''
                )
                locf_d = cursor.fetchone()
                if locf_d and locf_d["disks_json"]:
                    try:
                        partitions = json.loads(locf_d["disks_json"])
                    except Exception:
                        partitions = []

            physical_disks: List[Dict[str, Any]] = []
            if row["physical_disks_json"]:
                try:
                    physical_disks = json.loads(row["physical_disks_json"])
                except Exception:
                    physical_disks = []
            if not physical_disks:
                cursor.execute(
                    '''
                    SELECT physical_disks_json FROM system_snapshots
                    WHERE physical_disks_json IS NOT NULL AND physical_disks_json != '' AND physical_disks_json != '[]'
                    ORDER BY id DESC LIMIT 1;
                    '''
                )
                locf_p = cursor.fetchone()
                if locf_p and locf_p["physical_disks_json"]:
                    try:
                        physical_disks = json.loads(locf_p["physical_disks_json"])
                    except Exception:
                        physical_disks = []

            return {
                "id": row["id"],
                "timestamp": row["timestamp"],
                "created_at": row["created_at"],
                "partitions": partitions,
                "physical_disks": physical_disks,
            }

    def get_latest_snapshot_full(self) -> Optional[Dict[str, Any]]:
        """Извлекает и десериализует последний системный снимок с полной LOCF-реконструкцией всех параметров."""
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM system_snapshots ORDER BY id DESC LIMIT 1;")
            row = cursor.fetchone()
            if not row:
                return None

            snap_row = self._reconstructor.reconstruct_snapshot_row(dict(row), conn)
            snap_id = snap_row.get("id")

            raw_json_str = snap_row.get("raw_json")
            if not raw_json_str:
                locf_raw = cursor.execute(
                    "SELECT raw_json FROM system_snapshots WHERE raw_json IS NOT NULL ORDER BY id DESC LIMIT 1;"
                ).fetchone()
                raw_json_str = locf_raw[0] if locf_raw else None
            full_dict: Dict[str, Any] = {}
            if raw_json_str and isinstance(raw_json_str, str):
                try:
                    full_dict = json.loads(raw_json_str)
                except Exception:
                    full_dict = {}

            for field in (
                "hostname", "username", "uptime_seconds", "os_name", "os_build", "os_install_date",
                "system_language", "os_install_language", "user_locale", "system_locale", "timezone", "codepage",
                "cpu_total_percent", "cpu_frequency_mhz", "memory_total_gb", "memory_used_gb", "memory_percent",
                "swap_percent", "gpu_load_percent", "gpu_temp_c", "disk_read_bytes_sec", "disk_write_bytes_sec",
                "disk_read_count_sec", "disk_write_count_sec", "network_sent_bytes_sec", "network_recv_bytes_sec", "timestamp",
            ):
                if snap_row.get(field) is not None:
                    full_dict[field] = snap_row[field]

            if not full_dict.get("os_install_date"):
                try:
                    locf_date = cursor.execute(
                        "SELECT os_install_date FROM system_snapshots WHERE os_install_date IS NOT NULL AND os_install_date != '' ORDER BY id DESC LIMIT 1;"
                    ).fetchone()
                    if locf_date and locf_date[0]:
                        full_dict["os_install_date"] = locf_date[0]
                except Exception:
                    pass

            json_column_mappings = {
                "input_languages_json": "input_languages",
                "disks_json": "disks",
                "physical_disks_json": "physical_disks",
                "monitors_json": "monitors",
                "updates_json": "updates",
                "office_json": "office",
                "onedrive_json": "onedrive",
                "battery_json": "battery",
                "ram_sticks_json": "ram_sticks",
                "listening_ports_json": "listening_ports",
                "alerts_json": "alerts",
                "hardware_audit": "hardware_audit",
            }
            for col_name, target_key in json_column_mappings.items():
                val_str = snap_row.get(col_name)
                if val_str and isinstance(val_str, str):
                    try:
                        full_dict[target_key] = json.loads(val_str)
                    except Exception:
                        pass

            if "top_processes" not in full_dict or not full_dict["top_processes"]:
                if snap_id:
                    cursor.execute(
                        "SELECT pid, name, status, cpu_percent, memory_mb, memory_percent, num_threads, num_handles, "
                        "username, read_bytes_sec, write_bytes_sec, integrity_level, elevation, ppid, parent_name, "
                        "executable as executable_path, cmdline, sid, session_id, creation_time, process_guid, ancestor_chain, launch_reason "
                        "FROM process_snapshots WHERE snapshot_id = ? ORDER BY cpu_percent DESC LIMIT 50;",
                        (snap_id,),
                    )
                    full_dict["top_processes"] = [dict(p) for p in cursor.fetchall()]

            if "cpu" not in full_dict or not isinstance(full_dict.get("cpu"), dict):
                full_dict["cpu"] = {
                    "total_percent": float(snap_row.get("cpu_total_percent") or 0.0),
                    "frequency_mhz": float(snap_row.get("cpu_frequency_mhz") or 0.0),
                    "model": full_dict.get("cpu_model", "Intel / AMD Processor"),
                    "architecture": "x86_64",
                }
            if "memory" not in full_dict or not isinstance(full_dict.get("memory"), dict):
                tot_m = float(snap_row.get("memory_total_gb") or 0.0)
                used_m = float(snap_row.get("memory_used_gb") or 0.0)
                full_dict["memory"] = {
                    "total_gb": tot_m,
                    "used_gb": used_m,
                    "available_gb": max(0.0, tot_m - used_m),
                    "percent": float(snap_row.get("memory_percent") or 0.0),
                    "swap_percent": float(snap_row.get("swap_percent") or 0.0),
                }
            if "disk_io" not in full_dict or not isinstance(full_dict.get("disk_io"), dict):
                full_dict["disk_io"] = {}

            full_dict["cpu"].update({
                "total_percent": float(snap_row.get("cpu_total_percent") or 0.0),
                "frequency_mhz": float(snap_row.get("cpu_frequency_mhz") or 0.0),
            })
            full_dict["memory"].update({
                "used_gb": float(snap_row.get("memory_used_gb") or 0.0),
                "percent": float(snap_row.get("memory_percent") or 0.0),
                "swap_percent": float(snap_row.get("swap_percent") or 0.0),
            })
            full_dict["disk_io"].update({
                "read_bytes_per_sec": float(snap_row.get("disk_read_bytes_sec") or 0.0),
                "write_bytes_per_sec": float(snap_row.get("disk_write_bytes_sec") or 0.0),
                "read_count_per_sec": float(snap_row.get("disk_read_count_sec") or 0.0),
                "write_count_per_sec": float(snap_row.get("disk_write_count_sec") or 0.0),
            })
            gpus = full_dict.get("gpus")
            if isinstance(gpus, list) and gpus and isinstance(gpus[0], dict):
                gpus[0]["load_percent"] = float(snap_row.get("gpu_load_percent") or 0.0)
                gpus[0]["temperature_celsius"] = float(snap_row.get("gpu_temp_c") or 0.0)

            return full_dict

    def get_snapshot_processes(self, snapshot_id: int) -> List[Dict[str, Any]]:
        """Извлекает список процессов, зафиксированных в снимке."""
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM process_snapshots WHERE snapshot_id = ? ORDER BY cpu_percent DESC, memory_mb DESC",
                (snapshot_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_process_history(
        self,
        name: Optional[str] = None,
        pid: Optional[int] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Извлекает историю поведения процесса по имени или PID."""
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            if pid is not None and name is not None:
                cursor.execute(
                    "SELECT * FROM process_snapshots WHERE pid = ? AND name LIKE ? ORDER BY id DESC LIMIT ?",
                    (pid, f"%{name}%", limit),
                )
            elif pid is not None:
                cursor.execute(
                    "SELECT * FROM process_snapshots WHERE pid = ? ORDER BY id DESC LIMIT ?",
                    (pid, limit),
                )
            elif name is not None:
                cursor.execute(
                    "SELECT * FROM process_snapshots WHERE name LIKE ? ORDER BY id DESC LIMIT ?",
                    (f"%{name}%", limit),
                )
            else:
                cursor.execute("SELECT * FROM process_snapshots ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_latest_processes(self, limit: int = 50, sort_by: str = "cpu") -> List[Dict[str, Any]]:
        """Извлекает процессы из самого последнего зафиксированного снимка."""
        sort_key = (sort_by or "cpu").lower()
        if sort_key in ("handles", "descriptors"):
            order_col = "num_handles DESC, cpu_percent DESC"
        elif sort_key in ("memory", "ram", "memory_mb"):
            order_col = "memory_mb DESC, cpu_percent DESC"
        elif sort_key == "memory_percent":
            order_col = "memory_percent DESC, cpu_percent DESC"
        elif sort_key == "name":
            order_col = "name ASC"
        elif sort_key == "pid":
            order_col = "pid ASC"
        else:
            order_col = "cpu_percent DESC, memory_mb DESC"

        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(id) FROM system_snapshots;")
            row = cursor.fetchone()
            last_snap_id = row[0] if row and row[0] is not None else None
            if last_snap_id is None:
                cursor.execute("SELECT MAX(snapshot_id) FROM process_snapshots WHERE snapshot_id IS NOT NULL;")
                row = cursor.fetchone()
                last_snap_id = row[0] if row and row[0] is not None else None

            results: List[Dict[str, Any]] = []
            if last_snap_id is not None:
                sql = f'''
                    SELECT pid, name, status, cpu_percent, memory_mb, memory_percent,
                           num_threads, num_handles, username, read_bytes_sec, write_bytes_sec,
                           integrity_level, elevation, ppid, parent_name, executable, cmdline, timestamp
                    FROM process_snapshots
                    WHERE snapshot_id = ?
                    ORDER BY {order_col}
                '''
                if limit is not None and limit > 0:
                    cursor.execute(sql + " LIMIT ?", (last_snap_id, limit))
                else:
                    cursor.execute(sql, (last_snap_id,))
                results = [dict(r) for r in cursor.fetchall()]

            if results:
                return results

            # Fallback к последним замерам в process_snapshots или активным сессиям в process_lifecycle_sessions
            try:
                cursor.execute(
                    '''
                    SELECT pid, name, status,
                           0.0 as cpu_percent, peak_working_set_mb as memory_mb, 0.0 as memory_percent,
                           1 as num_threads, 0 as num_handles, username,
                           0.0 as read_bytes_sec, 0.0 as write_bytes_sec,
                           integrity_level, 0 as elevation, ppid, parent_name,
                           exe_path as executable, cmdline, created_at as timestamp
                    FROM process_lifecycle_sessions
                    WHERE is_alive = 1
                    ORDER BY peak_working_set_mb DESC
                    LIMIT ?
                    ''',
                    (int(limit or 50),),
                )
                return [dict(r) for r in cursor.fetchall()]
            except Exception as e:
                logger.debug(f"[reader_snapshots] Ошибка fallback выборки процессов: {e}")
                return []

    def get_process_stats(self, name: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
        """Возвращает агрегированную статистику процессов и выбросы из telemetry_rollups и process_snapshots."""
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            if name:
                cursor.execute(
                    "SELECT * FROM telemetry_rollups WHERE tier = 'proc_2min' AND sensor_id LIKE ? ORDER BY id DESC LIMIT ?",
                    (f"%{name}%", limit),
                )
            else:
                cursor.execute("SELECT * FROM telemetry_rollups WHERE tier = 'proc_2min' ORDER BY id DESC LIMIT ?", (limit,))
            rollups_2min = []
            for r in cursor.fetchall():
                d = dict(r)
                payload = json.loads(d["payload_json"]) if d.get("payload_json") else {}
                rollups_2min.append({**d, **payload})

            if name:
                cursor.execute(
                    "SELECT * FROM telemetry_rollups WHERE tier = 'proc_daily' AND sensor_id LIKE ? ORDER BY bucket_start DESC LIMIT ?",
                    (f"%{name}%", limit),
                )
            else:
                cursor.execute("SELECT * FROM telemetry_rollups WHERE tier = 'proc_daily' ORDER BY bucket_start DESC LIMIT ?", (limit,))
            daily_stats = []
            for r in cursor.fetchall():
                d = dict(r)
                payload = json.loads(d["payload_json"]) if d.get("payload_json") else {}
                daily_stats.append({**d, **payload})

            if name:
                cursor.execute(
                    "SELECT * FROM process_snapshots WHERE (sample_type = 'outlier' OR is_outlier = 1) AND name LIKE ? ORDER BY id DESC LIMIT ?",
                    (f"%{name}%", limit),
                )
            else:
                cursor.execute(
                    "SELECT * FROM process_snapshots WHERE sample_type = 'outlier' OR is_outlier = 1 ORDER BY id DESC LIMIT ?",
                    (limit,),
                )
            outliers = []
            for r in cursor.fetchall():
                d = dict(r)
                raw = json.loads(d["raw_json"]) if d.get("raw_json") else {}
                outliers.append({**d, **raw})

            return {
                "name_filter": name,
                "rollups_2min": rollups_2min,
                "daily_stats": daily_stats,
                "outliers": outliers,
                "total_rollups_count": len(rollups_2min),
                "total_outliers_count": len(outliers),
            }

    def get_events(self, event_type: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Извлекает список зафиксированных событий телеметрии из таблицы incidents."""
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            if event_type:
                cursor.execute(
                    "SELECT * FROM incidents WHERE domain = 'telemetry_event' AND trigger_type = ? ORDER BY id DESC LIMIT ?",
                    (event_type, limit),
                )
            else:
                cursor.execute(
                    "SELECT * FROM incidents WHERE domain = 'telemetry_event' ORDER BY id DESC LIMIT ?",
                    (limit,),
                )
            results: List[Dict[str, Any]] = []
            for row in cursor.fetchall():
                d = dict(row)
                results.append({
                    "id": d["id"],
                    "timestamp": d["timestamp"],
                    "created_at": d["created_at"],
                    "event_type": d.get("trigger_type"),
                    "severity": d.get("severity"),
                    "source": d.get("provider_name") or d.get("title"),
                    "message": d.get("message"),
                    "raw_json": d.get("details_json"),
                })
            return results

    def get_sensor_history(
        self,
        sensor_id: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Извлекает историю показаний сенсоров."""
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            if sensor_id and category:
                cursor.execute(
                    "SELECT * FROM sensor_polls WHERE sensor_id = ? AND sensor_category = ? ORDER BY id DESC LIMIT ?",
                    (sensor_id, category, limit),
                )
            elif sensor_id:
                cursor.execute("SELECT * FROM sensor_polls WHERE sensor_id = ? ORDER BY id DESC LIMIT ?", (sensor_id, limit))
            elif category:
                cursor.execute("SELECT * FROM sensor_polls WHERE sensor_category = ? ORDER BY id DESC LIMIT ?", (category, limit))
            else:
                cursor.execute("SELECT * FROM sensor_polls ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_latest_sensors(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Извлекает последнее актуальное значение каждого сенсора."""
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            query = '''
                SELECT s1.* FROM sensor_polls s1
                INNER JOIN (
                    SELECT sensor_id, MAX(id) as max_id
                    FROM sensor_polls
                    GROUP BY sensor_id
                ) s2 ON s1.id = s2.max_id
                ORDER BY s1.sensor_category, s1.sensor_name
            '''
            if limit is not None:
                cursor.execute(query + " LIMIT ?", (limit,))
            else:
                cursor.execute(query)
            return [dict(row) for row in cursor.fetchall()]

    def get_cpu_hierarchy_metrics(self) -> Dict[str, Any]:
        """Извлекает структурированные иерархические метрики процессора из SQLite."""
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()

            query_sensors = '''
                SELECT s1.* FROM sensor_polls s1
                INNER JOIN (
                    SELECT sensor_id, MAX(id) as max_id
                    FROM sensor_polls
                    WHERE hardware_type = 'cpu' OR (
                        hardware_name NOT LIKE '%GPU%'
                        AND hardware_name NOT LIKE '%Storage%'
                        AND hardware_name NOT LIKE '%Disk%'
                        AND sensor_id NOT LIKE 'disk_speed_%'
                        AND (hardware_type = 'system' OR sensor_category IN ('Voltages', 'Powers', 'Clocks', 'Temperatures', 'Load', 'voltages', 'powers', 'clocks', 'temperatures', 'load'))
                    )
                    GROUP BY sensor_id
                ) s2 ON s1.id = s2.max_id
                ORDER BY s1.sensor_category, s1.sensor_name
            '''
            cursor.execute(query_sensors)
            sensors = [dict(row) for row in cursor.fetchall()]

            cursor.execute("SELECT * FROM system_snapshots ORDER BY id DESC LIMIT 1")
            snap_row = cursor.fetchone()
            if snap_row:
                latest_snapshot = self._reconstructor.reconstruct_snapshot_row(dict(snap_row), conn)
                if not latest_snapshot.get("raw_json"):
                    locf_raw = cursor.execute(
                        "SELECT raw_json FROM system_snapshots WHERE raw_json IS NOT NULL ORDER BY id DESC LIMIT 1;"
                    ).fetchone()
                    if locf_raw:
                        latest_snapshot["raw_json"] = locf_raw[0]
            else:
                latest_snapshot = None

            cursor.execute("SELECT * FROM hardware_components WHERE category = 'cpu' ORDER BY id ASC LIMIT 1")
            inv_row = cursor.fetchone()
            cpu_inv = None
            if inv_row:
                d = dict(inv_row)
                specs = json.loads(d["specs_json"]) if d.get("specs_json") else {}
                cpu_inv = {
                    **specs,
                    "id": d["id"],
                    "first_seen": d["first_seen"],
                    "last_seen": d["last_seen"],
                    "updated_at": d["updated_at"],
                }

            cursor.execute(
                '''
                SELECT timestamp, created_at, cpu_total_percent, cpu_frequency_mhz
                FROM system_snapshots
                ORDER BY id DESC
                LIMIT 60
                '''
            )
            history_rows = [dict(r) for r in cursor.fetchall()]
            history_rows.reverse()

            return {
                "sensors": sensors,
                "snapshot": latest_snapshot,
                "inventory": cpu_inv,
                "history": history_rows,
            }

    def get_incidents(self, limit: int = 50, trigger_type: Optional[str] = None, severity: Optional[str] = None) -> List[Dict[str, Any]]:
        """Возвращает список зафиксированных инцидентов."""
        query = "SELECT * FROM incidents WHERE domain = 'incident'"
        params: List[Any] = []
        if trigger_type:
            query += " AND trigger_type = ?"
            params.append(trigger_type)
        if severity:
            query += " AND severity = ?"
            params.append(severity)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        results: List[Dict[str, Any]] = []
        try:
            with self._cm.lock, self._cm.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, tuple(params))
                for row in cursor.fetchall():
                    item = dict(row)
                    for f in ("trigger_metrics_json", "suspect_processes_json", "related_events_json", "metrics_summary_json", "raw_window_json"):
                        if item.get(f):
                            try:
                                item[f.replace("_json", "")] = json.loads(item[f])
                            except Exception:
                                item[f.replace("_json", "")] = []
                    results.append(item)
        except Exception as ex:
            logger.error(f"Ошибка при получении инцидентов: {ex}")
        return results

    def get_system_rollups(
        self,
        tier: str = "1m",
        start_epoch: Optional[float] = None,
        end_epoch: Optional[float] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Возвращает сжатые бакеты метрик за период."""
        query = "SELECT * FROM telemetry_rollups WHERE tier = ?"
        params: List[Any] = [tier]
        if start_epoch is not None:
            query += " AND period_start_epoch >= ?"
            params.append(start_epoch)
        if end_epoch is not None:
            query += " AND period_end_epoch <= ?"
            params.append(end_epoch)
        query += " ORDER BY period_start_epoch DESC LIMIT ?"
        params.append(limit)

        results: List[Dict[str, Any]] = []
        try:
            with self._cm.lock, self._cm.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, tuple(params))
                for row in cursor.fetchall():
                    results.append(dict(row))
        except Exception as ex:
            logger.error(f"Ошибка при получении rollups: {ex}")
        return results

    def get_process_provenance_history(
        self,
        guid: Optional[str] = None,
        pid: Optional[int] = None,
        name: Optional[str] = None,
        user: Optional[str] = None,
        event_type: Optional[str] = None,
        hours: Optional[int] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Извлечение исторических событий provenance процессов из process_lifecycle_sessions."""
        results: List[Dict[str, Any]] = []
        query = "SELECT * FROM process_lifecycle_sessions WHERE 1=1"
        params: List[Any] = []

        if hours is not None:
            cutoff = time.time() - (hours * 3600)
            query += " AND created_ts >= ?"
            params.append(cutoff)
        if guid:
            query += " AND (instance_id LIKE ? OR raw_json LIKE ?)"
            params.extend([f"%{guid}%", f"%{guid}%"])
        if pid is not None:
            query += " AND pid = ?"
            params.append(pid)
        if name:
            query += " AND name LIKE ?"
            params.append(f"%{name}%")
        if user:
            query += " AND (username LIKE ? OR sid LIKE ?)"
            params.extend([f"%{user}%", f"%{user}%"])
        if event_type:
            query += " AND status LIKE ?"
            params.append(f"%{event_type.upper()}%")

        query += " ORDER BY created_ts DESC LIMIT ?"
        params.append(limit)

        try:
            with self._cm.lock, self._cm.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, tuple(params))
                for row in cursor.fetchall():
                    d = dict(row)
                    raw = json.loads(d["raw_json"]) if d.get("raw_json") else {}
                    item = {
                        **d,
                        **raw,
                        "id": d["id"],
                        "timestamp": raw.get("timestamp") or d.get("created_at"),
                        "created_at": d.get("created_ts"),
                        "event_type": raw.get("event_type") or (d.get("status", "").replace("PROV_", "") if str(d.get("status", "")).startswith("PROV_") else "START"),
                        "process_guid": raw.get("process_guid") or d.get("instance_id"),
                        "executable_path": d.get("exe_path"),
                        "user": d.get("username"),
                        "launch_reason": d.get("initiator_type"),
                    }
                    if item.get("details_json") and isinstance(item["details_json"], str):
                        try:
                            item["details"] = json.loads(item["details_json"])
                        except Exception:
                            item["details"] = item["details_json"]
                    results.append(item)
        except Exception as ex:
            logger.error(f"Ошибка извлечения provenance процессов: {ex}")
        return results

    def get_process_lineage(self, guid_or_pid: Union[str, int]) -> List[Dict[str, Any]]:
        """Построение полной восходящей цепочки предков (lineage) процесса."""
        str_val = str(guid_or_pid)
        chain: List[Dict[str, Any]] = []
        visited_guids: set = set()
        visited_pids: set = set()

        history = self.get_process_provenance_history(guid=str_val, limit=1)
        if not history and str_val.isdigit():
            history = self.get_process_provenance_history(pid=int(str_val), limit=1)

        current_node: Optional[Dict[str, Any]] = history[0] if history else None

        while current_node:
            node_guid = current_node.get("process_guid")
            node_pid = current_node.get("pid")

            if (node_guid and node_guid in visited_guids) or (node_pid and node_pid in visited_pids):
                break

            if node_guid:
                visited_guids.add(node_guid)
            if node_pid:
                visited_pids.add(node_pid)

            chain.append(current_node)
            parent_guid = current_node.get("parent_guid")
            parent_pid = current_node.get("ppid") or current_node.get("parent_pid")

            parent_node = None
            if parent_guid:
                parent_hist = self.get_process_provenance_history(guid=parent_guid, limit=1)
                if parent_hist:
                    parent_node = parent_hist[0]

            if not parent_node and parent_pid:
                parent_hist = self.get_process_provenance_history(pid=int(parent_pid), limit=1)
                if parent_hist:
                    parent_node = parent_hist[0]

            current_node = parent_node

        chain.reverse()
        return chain

    def get_telemetry_rollups(
        self,
        level: str = "hourly",
        sensor_id: Optional[str] = None,
        start_epoch: Optional[float] = None,
        end_epoch: Optional[float] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Извлекает агрегированные показатели сенсоров для заданного уровня из единой таблицы telemetry_rollups."""
        lvl_clean = str(level).strip().lower()
        if lvl_clean not in ("hourly", "daily", "weekly", "monthly", "yearly"):
            lvl_clean = "hourly"

        conditions = ["tier = ?"]
        params: List[Any] = [lvl_clean]

        if sensor_id is not None:
            conditions.append("sensor_id = ?")
            params.append(sensor_id)
        if start_epoch is not None:
            conditions.append("bucket_start >= ?")
            params.append(float(start_epoch))
        if end_epoch is not None:
            conditions.append("bucket_start < ?")
            params.append(float(end_epoch))

        where_clause = f"WHERE {' AND '.join(conditions)}"
        query = f"SELECT * FROM telemetry_rollups {where_clause} ORDER BY bucket_start DESC LIMIT ?"
        params.append(int(limit))

        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_telemetry_spikes(
        self,
        sensor_id: Optional[str] = None,
        start_epoch: Optional[float] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Извлекает зафиксированные статистические всплески и аномалии сенсоров из таблицы incidents."""
        conditions = ["domain = 'spike'"]
        params: List[Any] = []

        if sensor_id is not None:
            conditions.append("sensor_id = ?")
            params.append(sensor_id)
        if start_epoch is not None:
            conditions.append("created_at >= ?")
            params.append(float(start_epoch))

        where_clause = f"WHERE {' AND '.join(conditions)}"
        query = f"SELECT * FROM incidents {where_clause} ORDER BY created_at DESC LIMIT ?"
        params.append(int(limit))

        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            results: List[Dict[str, Any]] = []
            for row in cursor.fetchall():
                d = dict(row)
                results.append({
                    **d,
                    "spike_type": d.get("trigger_type"),
                    "details": d.get("details_json"),
                })
            return results

    def get_process_pid_snapshot(self, pid: int) -> Optional[Dict[str, Any]]:
        """Извлекает последний канонический снимок метрик процесса по PID из process_snapshots."""
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT
                    pid,
                    name AS process_name,
                    executable AS executable_path,
                    cpu_percent,
                    CAST(COALESCE(user_time_sec, 0) * 1000 AS INTEGER) AS user_time_ms,
                    CAST(COALESCE(kernel_time_sec, 0) * 1000 AS INTEGER) AS kernel_time_ms,
                    num_threads AS thread_count,
                    CAST(COALESCE(working_set_mb, memory_mb, 0) * 1048576 AS INTEGER) AS working_set_bytes,
                    CAST(COALESCE(private_mb, 0) * 1048576 AS INTEGER) AS private_bytes,
                    COALESCE(page_faults, 0) AS page_faults_count,
                    0 AS gpu_vram_bytes,
                    0.0 AS gpu_utilization,
                    CAST(COALESCE(read_bytes_sec, 0) AS INTEGER) AS read_bytes_total,
                    CAST(COALESCE(write_bytes_sec, 0) AS INTEGER) AS write_bytes_total,
                    COALESCE(read_operations, 0) AS read_ops_total,
                    COALESCE(write_operations, 0) AS write_ops_total,
                    0 AS net_bytes_sent_total,
                    0 AS net_bytes_recv_total,
                    num_handles AS handle_count,
                    COALESCE(gdi_objects, 0) AS gdi_objects,
                    COALESCE(user_objects, 0) AS user_objects,
                    timestamp
                FROM process_snapshots
                WHERE pid = ?
                ORDER BY id DESC
                LIMIT 1
                ''',
                (pid,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_process_file_events(
        self,
        pid: Optional[int] = None,
        directory: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Извлекает события файловой активности с фильтрацией по PID и/или директории."""
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            conditions = []
            params: List[Any] = []
            if pid is not None:
                conditions.append("pid = ?")
                params.append(pid)
            if directory:
                conditions.append("target_directory LIKE ?")
                params.append(f"%{directory}%")

            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            query = f"SELECT * FROM process_file_events {where_clause} ORDER BY event_id DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, tuple(params))
            return [dict(row) for row in cursor.fetchall()]

    def get_telemetry_time_ranges(self) -> Dict[str, Any]:
        """Определяет временные границы данных в таблице system_snapshots и формирует список доступных интервалов."""
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT MIN(created_at) as min_ts, MAX(created_at) as max_ts, COUNT(*) as cnt "
                "FROM system_snapshots;"
            )
            row = cursor.fetchone()

            min_ts = row["min_ts"] if row and row["min_ts"] is not None else None
            max_ts = row["max_ts"] if row and row["max_ts"] is not None else None
            total_cnt = int(row["cnt"]) if row and row["cnt"] is not None else 0

            now = time.time()
            span_seconds = 0.0
            if min_ts is not None and max_ts is not None:
                span_seconds = max(0.0, float(max_ts - min_ts), float(now - min_ts))

            intervals_definition = [
                {"id": "seconds", "label": "Секунды", "seconds": 120, "min_span": 0},
                {"id": "minutes", "label": "Минуты", "seconds": 3600, "min_span": 60},
                {"id": "hours", "label": "Часы", "seconds": 86400, "min_span": 3600},
                {"id": "days", "label": "Дни", "seconds": 86400 * 7, "min_span": 86400},
                {"id": "weeks", "label": "Недели", "seconds": 86400 * 30, "min_span": 86400 * 7},
                {"id": "months", "label": "Месяцы", "seconds": 86400 * 365, "min_span": 86400 * 30},
                {"id": "all", "label": "Все", "seconds": None, "min_span": 0},
            ]

            available_intervals = []
            for item in intervals_definition:
                is_avail = (span_seconds >= item["min_span"]) if item["min_span"] > 0 else True
                if item["id"] == "all":
                    is_avail = True
                if is_avail:
                    available_intervals.append({
                        "id": item["id"],
                        "label": item["label"],
                        "seconds": item["seconds"],
                        "is_available": True,
                    })

            return {
                "status": "ok",
                "min_created_at": min_ts,
                "max_created_at": max_ts,
                "span_seconds": round(span_seconds, 1),
                "total_snapshots": total_cnt,
                "intervals": available_intervals,
                "available_ids": [i["id"] for i in available_intervals],
            }

    def get_history_by_interval(
        self,
        interval: str = "seconds",
        metric: str = "all",
        limit: int = 120,
    ) -> List[Dict[str, Any]]:
        """Выбирает исторические точки системных снимков под указанный интервал с downsampling."""
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            now = time.time()
            interval_lower = (interval or "seconds").lower().strip()

            since_ts = None
            if interval_lower == "seconds":
                since_ts = now - 120
            elif interval_lower == "minutes":
                since_ts = now - 3600
            elif interval_lower == "hours":
                since_ts = now - 86400
            elif interval_lower == "days":
                since_ts = now - (86400 * 7)
            elif interval_lower == "weeks":
                since_ts = now - (86400 * 30)
            elif interval_lower == "months":
                since_ts = now - (86400 * 365)
            elif interval_lower == "all":
                since_ts = None

            if since_ts is not None:
                cursor.execute(
                    "SELECT id, timestamp, created_at, cpu_total_percent, cpu_frequency_mhz, "
                    "memory_total_gb, memory_used_gb, memory_percent, swap_percent, "
                    "gpu_load_percent, gpu_temp_c, disk_read_bytes_sec, disk_write_bytes_sec, "
                    "network_sent_bytes_sec, network_recv_bytes_sec "
                    "FROM system_snapshots WHERE created_at >= ? ORDER BY id ASC;",
                    (since_ts,),
                )
            else:
                cursor.execute(
                    "SELECT id, timestamp, created_at, cpu_total_percent, cpu_frequency_mhz, "
                    "memory_total_gb, memory_used_gb, memory_percent, swap_percent, "
                    "gpu_load_percent, gpu_temp_c, disk_read_bytes_sec, disk_write_bytes_sec, "
                    "network_sent_bytes_sec, network_recv_bytes_sec "
                    "FROM system_snapshots ORDER BY id ASC;"
                )

            rows = [dict(r) for r in cursor.fetchall()]

            if not rows:
                cursor.execute(
                    "SELECT id, timestamp, created_at, cpu_total_percent, cpu_frequency_mhz, "
                    "memory_total_gb, memory_used_gb, memory_percent, swap_percent, "
                    "gpu_load_percent, gpu_temp_c, disk_read_bytes_sec, disk_write_bytes_sec, "
                    "network_sent_bytes_sec, network_recv_bytes_sec "
                    "FROM system_snapshots ORDER BY id DESC LIMIT ?;",
                    (limit,),
                )
                rows = [dict(r) for r in cursor.fetchall()]
                rows.reverse()

            if len(rows) > limit:
                step = len(rows) / float(limit)
                downsampled = [rows[int(i * step)] for i in range(limit)]
                if rows[-1] not in downsampled:
                    downsampled[-1] = rows[-1]
                rows = downsampled

            return rows

    def get_app_polls(
        self,
        app: Optional[str] = None,
        metric_name: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Извлекает историю опросов приложений из таблицы incidents (domain='app_poll')."""
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            conditions = ["domain = 'app_poll'"]
            params: List[Any] = []
            if app:
                conditions.append("app_name = ?")
                params.append(app)
            if metric_name:
                conditions.append("trigger_type = ?")
                params.append(metric_name)
            where_sql = " WHERE " + " AND ".join(conditions)
            cursor.execute(f"SELECT * FROM incidents{where_sql} ORDER BY id DESC LIMIT ?", (*params, int(limit)))
            results: List[Dict[str, Any]] = []
            for row in cursor.fetchall():
                d = dict(row)
                results.append({
                    "id": d["id"],
                    "timestamp": d["timestamp"],
                    "created_at": d["created_at"],
                    "app": d.get("app_name"),
                    "metric_name": d.get("trigger_type"),
                    "value": d.get("value"),
                    "unit": d.get("unit"),
                    "status": d.get("severity") or d.get("message") or "OK",
                    "details": d.get("details_json"),
                })
            return results

    def get_app_events(
        self,
        app: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Извлекает события приложений из таблицы incidents (domain='app_event')."""
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            conditions = ["domain = 'app_event'"]
            params: List[Any] = []
            if app:
                conditions.append("app_name = ?")
                params.append(app)
            if event_type:
                conditions.append("trigger_type = ?")
                params.append(event_type)
            where_sql = " WHERE " + " AND ".join(conditions)
            cursor.execute(f"SELECT * FROM incidents{where_sql} ORDER BY id DESC LIMIT ?", (*params, int(limit)))
            results: List[Dict[str, Any]] = []
            for row in cursor.fetchall():
                d = dict(row)
                results.append({
                    "id": d["id"],
                    "timestamp": d["timestamp"],
                    "created_at": d["created_at"],
                    "app": d.get("app_name"),
                    "event_type": d.get("trigger_type"),
                    "status": d.get("severity") or "OK",
                    "details": d.get("details_json"),
                })
            return results

    def get_app_param_changes(
        self,
        app: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Извлекает изменения параметров приложений из таблицы inventory_changes."""
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            if app:
                cursor.execute(
                    "SELECT * FROM inventory_changes WHERE domain = ? ORDER BY id DESC LIMIT ?",
                    (f"app_params:{app}", int(limit)),
                )
            else:
                cursor.execute(
                    "SELECT * FROM inventory_changes WHERE domain LIKE 'app_params:%' ORDER BY id DESC LIMIT ?",
                    (int(limit),),
                )
            results: List[Dict[str, Any]] = []
            for row in cursor.fetchall():
                d = dict(row)
                diff = json.loads(d["diff_json"]) if d.get("diff_json") else {}
                results.append({
                    "id": d["id"],
                    "timestamp": d["timestamp"],
                    "created_at": d["created_at"],
                    **diff,
                })
            return results

    def get_custom_records(
        self,
        source_file: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Возвращает пустой список (пользовательские сырые логи в SQLite отключены)."""
        return []

    def get_w64_events(
        self,
        event_type: Optional[str] = None,
        provider: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Извлекает нормализованные события w64 из таблицы process_file_events."""
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            if event_type:
                clean_type = event_type.strip().upper()
                cursor.execute(
                    "SELECT * FROM process_file_events WHERE (operation_type = ? OR operation_type = ?) ORDER BY event_id DESC LIMIT ?",
                    (clean_type, f"w64:{clean_type}", int(limit)),
                )
            else:
                cursor.execute(
                    "SELECT * FROM process_file_events WHERE (details_json LIKE '%etw%' OR details_json LIKE '%w64%' OR operation_type LIKE 'w64:%') ORDER BY event_id DESC LIMIT ?",
                    (int(limit),),
                )
            results: List[Dict[str, Any]] = []
            for row in cursor.fetchall():
                d = dict(row)
                details = json.loads(d["details_json"]) if d.get("details_json") else {}
                if provider and details.get("provider") != provider:
                    continue
                results.append({
                    "id": d["event_id"],
                    "timestamp": d["timestamp"],
                    "created_at": d["created_at"],
                    "event_type": details.get("event_type") or str(d.get("operation_type") or "").replace("w64:", "").upper(),
                    "path": d.get("file_path"),
                    "pid": d.get("pid"),
                    "name": d.get("process_name"),
                    "provider": details.get("provider"),
                    "raw_json": details.get("raw"),
                })
            return results

    def get_process_provenance_analytics(
        self,
        cmdline_pattern: Optional[str] = None,
        name: Optional[str] = None,
        parent_name: Optional[str] = None,
        days: int = 7,
    ) -> Dict[str, Any]:
        """Возвращает многоуровневую аналитику потребления ресурсов процессом (по тикам за 24ч, суточную историю за неделю и профиль за всё время).

        Args:
            cmdline_pattern: Подстрока поиска в командной строке.
            name: Имя исполняемого файла процесса.
            parent_name: Имя родительской программы-инициатора.
            days: Глубина выборки суточной истории в днях.

        Returns:
            Dict[str, Any]: Структурированный отчёт с тиками за сутки, суточной динамикой и пожизненной статистикой.
        """
        now_epoch = time.time()
        last_24h_epoch = now_epoch - 86400.0
        cutoff_days_epoch = now_epoch - (float(days) * 86400.0)

        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()

            rollups_query = """
            SELECT tier, sensor_id, bucket_start, sample_count, cpu_avg, cpu_max, ram_avg, ram_max, payload_json
            FROM telemetry_rollups
            WHERE tier IN ('proc_daily', 'proc_weekly', 'proc_all_time')
            """
            cursor.execute(rollups_query)
            all_rollups = cursor.fetchall()

            processes_data: Dict[str, Dict[str, Any]] = {}

            for r in all_rollups:
                tier = r["tier"]
                pl = json.loads(r["payload_json"]) if r["payload_json"] else {}

                p_cmd = pl.get("cmdline") or ""
                p_name = pl.get("name") or ""
                p_parent = pl.get("parent_name") or ""

                if cmdline_pattern and cmdline_pattern.lower() not in p_cmd.lower():
                    continue
                if name and name.lower() not in p_name.lower():
                    continue
                if parent_name and parent_name.lower() not in p_parent.lower():
                    continue

                proc_key = f"{p_parent}->{p_name}:{p_cmd}"
                if proc_key not in processes_data:
                    processes_data[proc_key] = {
                        "name": p_name,
                        "cmdline": p_cmd,
                        "parent_name": p_parent,
                        "recent_ticks_24h": [],
                        "daily_history": [],
                        "weekly_summary": None,
                        "all_time": {},
                    }

                if tier == "proc_daily" and float(r["bucket_start"] or 0) >= cutoff_days_epoch:
                    processes_data[proc_key]["daily_history"].append(pl)
                elif tier == "proc_weekly":
                    processes_data[proc_key]["weekly_summary"] = pl
                elif tier == "proc_all_time":
                    processes_data[proc_key]["all_time"] = pl

            ticks_query = """
            SELECT
                p.timestamp,
                p.created_at,
                p.pid,
                p.name,
                p.cpu_percent,
                p.memory_mb,
                p.read_bytes_sec,
                p.write_bytes_sec,
                p.instance_id,
                COALESCE(l.cmdline, p.cmdline, p.name) as cmdline,
                COALESCE(l.parent_name, p.parent_name, 'Unknown') as parent_name
            FROM process_snapshots p
            LEFT JOIN process_lifecycle_sessions l ON p.instance_id = l.instance_id
            WHERE p.sample_type = 'snapshot' AND p.created_at >= ?
            ORDER BY p.created_at ASC
            """
            cursor.execute(ticks_query, (last_24h_epoch,))
            for tick in cursor.fetchall():
                t_dict = dict(tick)
                p_cmd = t_dict["cmdline"] or ""
                p_name = t_dict["name"] or ""
                p_parent = t_dict["parent_name"] or ""

                if cmdline_pattern and cmdline_pattern.lower() not in p_cmd.lower():
                    continue
                if name and name.lower() not in p_name.lower():
                    continue
                if parent_name and parent_name.lower() not in p_parent.lower():
                    continue

                proc_key = f"{p_parent}->{p_name}:{p_cmd}"
                if proc_key not in processes_data:
                    processes_data[proc_key] = {
                        "name": p_name,
                        "cmdline": p_cmd,
                        "parent_name": p_parent,
                        "recent_ticks_24h": [],
                        "daily_history": [],
                        "weekly_summary": None,
                        "all_time": {},
                    }

                processes_data[proc_key]["recent_ticks_24h"].append({
                    "timestamp": t_dict["timestamp"],
                    "created_at": t_dict["created_at"],
                    "pid": t_dict["pid"],
                    "cpu_percent": t_dict["cpu_percent"],
                    "memory_mb": t_dict["memory_mb"],
                    "instance_id": t_dict["instance_id"],
                })

            res_list = list(processes_data.values())
            return {
                "matched_processes_count": len(res_list),
                "processes": res_list,
                "days_requested": days,
            }

    def get_latest_network_profile(self) -> Dict[str, Any]:
        """Извлекает последний зафиксированный в telemetry.db сетевой профиль хоста."""
        snap = self.get_latest_snapshot_full() or {}
        net_prof = snap.get("network_profile")
        if isinstance(net_prof, dict) and net_prof.get("current_category"):
            return net_prof

        # Резервный сбор параметров для старых записей снимков без network_profile
        category = "Public"
        net_name = "Network"
        if os.name == "nt":
            try:
                import winreg
                key_path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\NetworkList\Profiles"
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                    cnt, _, _ = winreg.QueryInfoKey(key)
                    for i in range(cnt):
                        sub = winreg.EnumKey(key, i)
                        with winreg.OpenKey(key, sub) as sk:
                            pname, _ = winreg.QueryValueEx(sk, "ProfileName")
                            cat, _ = winreg.QueryValueEx(sk, "Category")
                            category = "Public" if cat == 0 else ("Private" if cat == 1 else "Domain")
                            net_name = pname
                            break
            except Exception:
                pass

        discovery_enabled = False
        if os.name == "nt":
            try:
                import psutil
                s = psutil.win_service_get("FDResPub")
                discovery_enabled = (s.status() == "running")
            except Exception:
                discovery_enabled = False

        return {
            "status": "ok",
            "current_category": category,
            "primary_interface_alias": net_name,
            "primary_interface_index": None,
            "is_discovery_enabled": discovery_enabled,
        }



