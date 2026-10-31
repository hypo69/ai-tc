# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry Sqlite - Writer
# =============================================================================
# Description:
#   Класс TelemetryWriter для сериализации и записи телеметрии в 12 базовых
#   таблиц SQLite.
#
# Usage Examples:
#   Python API:
#     from apps.windows.telemetry.sqlite.writer import TelemetryWriter
#
#     writer = TelemetryWriter(connection_manager)
#     saved = writer.batch_insert_records(records)
#
# File: writer.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry.sqlite
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-16 17:15:00
# =============================================================================

from __future__ import annotations

"""Класс TelemetryWriter для сериализации, подготовки строк и транзакционной записи в 12 таблиц SQLite."""

import json
import uuid
from datetime import datetime, timezone
from typing import (
    Any,
    Dict,
    List,
    Optional,
)

from .connection import TelemetryConnectionManager
from .delta_tracker import DeltaStateTracker
from .writer_audits import TelemetryAuditWriterMixin
from .writer_inventory import TelemetryInventoryWriterMixin
from .writer_snapshots import TelemetrySnapshotWriterMixin

try:
    from logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class TelemetryWriter(TelemetrySnapshotWriterMixin, TelemetryInventoryWriterMixin, TelemetryAuditWriterMixin):
    """Выполняет пакетную и прямую вставку записей телеметрии в базу данных SQLite."""

    def __init__(self, connection_manager: TelemetryConnectionManager) -> None:
        """Инициализирует писатель телеметрии.

        Args:
            connection_manager: Менеджер соединений SQLite.
        """
        self._cm = connection_manager
        self._delta_tracker = DeltaStateTracker()

    @property
    def delta_tracker(self) -> DeltaStateTracker:
        """Возвращает трекер дельт."""
        return self._delta_tracker

    def batch_insert_records(self, records: List[Dict[str, Any]]) -> int:
        """Выполняет пакетную вставку разнородных записей в SQLite в единой транзакции.

        Args:
            records: Список словарей записей.

        Returns:
            int: Общее число сохраненных записей.
        """
        if not records or self._cm.read_only:
            return 0

        saved_total = 0
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            sensor_poll_rows: List[tuple] = []
            sensor_agg_rows: List[tuple] = []

            for item in records:
                rec_type = item.get("type")

                if rec_type == "snapshot":
                    saved_total += self.insert_snapshot_row(cursor, item)

                elif rec_type == "sensor_poll":
                    sensor_poll_rows.append(self.prepare_sensor_poll_row(item.get("data", {}), item.get("timestamp")))

                elif rec_type == "sensor_polls_batch":
                    ts = item.get("timestamp")
                    for s in item.get("data", []):
                        sensor_poll_rows.append(self.prepare_sensor_poll_row(s, ts))

                elif rec_type == "sensor_aggregates_batch":
                    now_epoch = datetime.now(timezone.utc).timestamp()
                    for a in item.get("data", []):
                        p_start = str(a.get("period_start") or "")
                        try:
                            b_start = datetime.fromisoformat(p_start).timestamp()
                        except Exception:
                            b_start = now_epoch
                        avg_v = a.get("avg")
                        min_v = a.get("min")
                        max_v = a.get("max")
                        sensor_agg_rows.append((
                            str(a.get("sensor_id") or ""),
                            b_start,
                            p_start,
                            str(a.get("period_end") or ""),
                            avg_v,
                            min_v,
                            max_v,
                            avg_v,
                            min_v,
                            max_v,
                            int(a.get("count") or 0),
                            json.dumps(a, ensure_ascii=False, default=str),
                            now_epoch,
                        ))

                elif rec_type == "hardware_archive":
                    saved_total += self.insert_hardware_archive_row(cursor, item.get("data", {}))

                elif rec_type == "startup_archive":
                    saved_total += self.insert_startup_archive_row(cursor, item.get("data", {}))

                elif rec_type == "event":
                    saved_total += self.insert_event_row(cursor, {
                        "timestamp": item.get("timestamp"),
                        "event_type": item.get("event_type", ""),
                        "severity": item.get("severity", "info"),
                        "message": json.dumps(item.get("details", {}), ensure_ascii=False, default=str),
                        "raw_json": item.get("details", {}),
                    })

                elif rec_type == "disk_inventory":
                    saved_total += self.upsert_disk_inventory(cursor, item.get("data") or item)

                elif rec_type == "volume_inventory":
                    saved_total += self.upsert_volume_inventory(cursor, item.get("data") or item)

                elif rec_type == "disk_health":
                    saved_total += self.insert_disk_health_snapshot(cursor, item.get("data") or item)

                elif rec_type == "disk_performance":
                    saved_total += self.insert_disk_performance_sample(cursor, item.get("data") or item)

                elif rec_type == "disk_io_event":
                    saved_total += self.insert_disk_io_event(cursor, item.get("data") or item)

                elif rec_type in ("cpu_inventory", "cpu_inv"):
                    saved_total += self.upsert_cpu_inventory(cursor, item.get("data") or item)

                elif rec_type in ("ram_module_inventory", "ram_inventory", "ram_module"):
                    saved_total += self.upsert_ram_module_inventory(cursor, item.get("data") or item)

                elif rec_type in ("gpu_inventory", "gpu_inv"):
                    saved_total += self.upsert_gpu_inventory(cursor, item.get("data") or item)

                elif rec_type in ("network_adapter_inventory", "net_inventory", "net_adapter_inv"):
                    saved_total += self.upsert_network_adapter_inventory(cursor, item.get("data") or item)

                elif rec_type in ("cpu_telemetry", "cpu_sample"):
                    saved_total += self.insert_cpu_telemetry_sample(cursor, item.get("data") or item)

                elif rec_type in ("ram_telemetry", "ram_sample"):
                    saved_total += self.insert_ram_telemetry_sample(cursor, item.get("data") or item)

                elif rec_type in ("gpu_telemetry", "gpu_sample"):
                    saved_total += self.insert_gpu_telemetry_sample(cursor, item.get("data") or item)

                elif rec_type in ("network_adapter_sample", "network_sample", "net_sample"):
                    saved_total += self.insert_network_adapter_sample(cursor, item.get("data") or item)

                elif rec_type == "app_poll":
                    saved_total += self.insert_app_poll(cursor, item.get("data") or item)

                elif rec_type == "app_polls_batch":
                    for p in item.get("data", []):
                        saved_total += self.insert_app_poll(cursor, p)

                elif rec_type == "app_event":
                    saved_total += self.insert_app_event(cursor, item.get("data") or item)

                elif rec_type == "app_events_batch":
                    for ev in item.get("data", []):
                        saved_total += self.insert_app_event(cursor, ev)

                elif rec_type == "app_param_change":
                    saved_total += self.insert_app_param_change(cursor, item.get("data") or item)

                elif rec_type == "app_param_changes_batch":
                    for pc in item.get("data", []):
                        saved_total += self.insert_app_param_change(cursor, pc)

                elif rec_type == "device_event":
                    ev_payload = dict(item.get("data") or {})
                    if item.get("timestamp") and not ev_payload.get("timestamp"):
                        ev_payload["timestamp"] = item["timestamp"]
                    if "device_instance_id" in ev_payload and "device_id" not in ev_payload:
                        ev_payload["device_id"] = ev_payload["device_instance_id"]
                    now_dt = datetime.now(timezone.utc)
                    ts_str = ev_payload.get("timestamp") or now_dt.isoformat()
                    created_at = float(ev_payload.get("created_at") or now_dt.timestamp())
                    dev_id = str(ev_payload.get("device_id") or "unknown")
                    ev_type = str(ev_payload.get("event_type") or "state_change")
                    fname = str(ev_payload.get("friendly_name") or dev_id)
                    has_prob = 1 if ev_payload.get("has_problem") else 0
                    inc_id = str(ev_payload.get("incident_id") or f"dev_{int(created_at * 1000)}_{uuid.uuid4().hex[:8]}")
                    cursor.execute(
                        '''
                        INSERT INTO incidents (
                            incident_id, timestamp, created_at, domain, trigger_type, severity,
                            title, device_id, message, details_json
                        ) VALUES (?, ?, ?, 'device_event', ?, ?, ?, ?, ?, ?);
                        ''',
                        (
                            inc_id,
                            ts_str,
                            created_at,
                            ev_type,
                            "WARNING" if has_prob else "INFO",
                            fname,
                            dev_id,
                            str(ev_payload.get("details") or f"{fname}: {ev_type}"),
                            json.dumps(ev_payload, ensure_ascii=False, default=str),
                        ),
                    )
                    saved_total += 1

                elif rec_type == "w64_event":
                    w64_payload = dict(item.get("data") or {})
                    w64_payload.setdefault("provider", item.get("provider", "w64_collector"))
                    saved_total += self.insert_w64_event(cursor, w64_payload)

                elif rec_type == "process_provenance_event":
                    saved_total += self.insert_process_provenance_event(cursor, item.get("data") or {})

                elif rec_type == "process_provenance_events_batch":
                    for ev in item.get("data", []):
                        saved_total += self.insert_process_provenance_event(cursor, ev)

                elif rec_type == "incident":
                    saved_total += self.insert_incident(cursor, item.get("data") or {})

                elif rec_type == "system_rollup":
                    saved_total += self.upsert_system_rollup(cursor, item.get("data") or {})

                elif rec_type == "reboot_session":
                    saved_total += self.insert_reboot_session(cursor, item.get("data") or {})

                elif rec_type == "extended_audit":
                    aud_payload = dict(item.get("data") or {})
                    if item.get("timestamp") and not aud_payload.get("timestamp"):
                        aud_payload["timestamp"] = item["timestamp"]
                    saved_total += self.insert_extended_audit(cursor, aud_payload)

            if sensor_poll_rows:
                cursor.executemany(
                    '''
                    INSERT INTO sensor_polls (
                        sensor_id, timestamp, created_at, hardware_name, hardware_type,
                        sensor_category, sensor_name, unit, value, value_numeric, status, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                    sensor_poll_rows,
                )
                saved_total += len(sensor_poll_rows)

            if sensor_agg_rows:
                cursor.executemany(
                    '''
                    INSERT OR REPLACE INTO telemetry_rollups (
                        tier, sensor_id, bucket_start, period_start, period_end,
                        value_avg, value_min, value_max, avg_val, min_val, max_val,
                        sample_count, payload_json, created_at
                    ) VALUES ('hourly', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                    sensor_agg_rows,
                )
                saved_total += len(sensor_agg_rows)

            conn.commit()
        return saved_total

    def prepare_sensor_poll_row(self, s: Dict[str, Any], timestamp: Optional[str] = None) -> tuple:
        """Подготавливает кортеж для вставки в sensor_polls."""
        now_dt = datetime.now(timezone.utc)
        ts_str = timestamp or s.get("timestamp") or now_dt.isoformat()
        try:
            now_epoch = datetime.fromisoformat(ts_str).timestamp()
        except Exception:
            now_epoch = now_dt.timestamp()
        sid = str(s.get("id") or s.get("sensor_id") or "")
        s_name = s.get("sensor_name") or s.get("name") or (f"Sensor #{sid}" if sid else "Sensor")
        cat = s.get("sensor_category") or s.get("category") or "General"

        hw_type = s.get("hardware_type")
        if not hw_type:
            sid_l = sid.lower()
            cat_l = cat.lower()
            if "disk" in sid_l or "storage" in sid_l or "storage" in cat_l:
                hw_type = "storage"
            elif "gpu" in sid_l or "vram" in sid_l or "graphics" in sid_l:
                hw_type = "gpu"
            elif "ram" in sid_l or "memory" in sid_l:
                hw_type = "memory"
            elif "net" in sid_l or "nic" in sid_l or "network" in cat_l:
                hw_type = "network"
            else:
                hw_type = "cpu"

        hw_name = s.get("hardware_name") or ("Storage" if hw_type == "storage" else "System")
        unit = s.get("unit", "")
        raw_val = s.get("value", s.get("value_num", 0.0))
        try:
            val_float = round(float(raw_val), 2)
        except (ValueError, TypeError):
            val_float = 0.0

        raw_json_str = s.get("raw_json")
        if not raw_json_str:
            try:
                raw_json_str = json.dumps(s, ensure_ascii=False, default=str)
            except Exception:
                raw_json_str = None

        return (
            sid,
            ts_str,
            now_epoch,
            hw_name,
            hw_type,
            cat,
            s_name,
            unit,
            val_float,
            val_float,
            s.get("status") or "OK",
            raw_json_str,
        )

    def prepare_app_poll_row(self, p: Dict[str, Any]) -> tuple:
        """Подготавливает кортеж для вставки опроса состояния приложения."""
        now_dt = datetime.now(timezone.utc)
        ts_str = p.get("timestamp") or now_dt.isoformat()
        try:
            now_epoch = datetime.fromisoformat(ts_str).timestamp()
        except Exception:
            now_epoch = now_dt.timestamp()
        app = p.get("app", "unknown")
        poll_type = p.get("poll_type", "poll")
        metric_name = p.get("metric_name", "metric")
        val = p.get("value")
        try:
            val_num = float(val) if val is not None and not isinstance(val, (dict, list)) else None
        except (ValueError, TypeError):
            val_num = None
        unit = p.get("unit", "")
        status = p.get("status", "OK")
        details = p.get("details", "")
        details_str = json.dumps(details, ensure_ascii=False) if isinstance(details, (dict, list)) else str(details or "")
        raw_json = json.dumps({"app": app, "poll_type": poll_type, "metric_name": metric_name, "value": val, "unit": unit, "status": status, "details": details}, ensure_ascii=False)
        return (ts_str, now_epoch, app, poll_type, metric_name, val_num, unit, status, details_str, raw_json)

    def prepare_app_event_row(self, ev: Dict[str, Any]) -> tuple:
        """Подготавливает кортеж для вставки события приложения."""
        now_dt = datetime.now(timezone.utc)
        ts_str = ev.get("timestamp") or now_dt.isoformat()
        try:
            now_epoch = datetime.fromisoformat(ts_str).timestamp()
        except Exception:
            now_epoch = now_dt.timestamp()
        app = ev.get("app", "unknown")
        event_type = ev.get("event_type", "event")
        status = ev.get("status", "OK")
        details = ev.get("details", "")
        details_str = json.dumps(details, ensure_ascii=False) if isinstance(details, (dict, list)) else str(details or "")
        raw_json = json.dumps({"app": app, "event_type": event_type, "status": status, "details": details}, ensure_ascii=False)
        return (ts_str, now_epoch, app, event_type, status, details_str, raw_json)

    def prepare_app_param_row(self, pc: Dict[str, Any]) -> tuple:
        """Подготавливает кортеж для вставки изменения параметра приложения."""
        now_dt = datetime.now(timezone.utc)
        ts_str = pc.get("timestamp") or now_dt.isoformat()
        try:
            now_epoch = datetime.fromisoformat(ts_str).timestamp()
        except Exception:
            now_epoch = now_dt.timestamp()
        app = pc.get("app", "unknown")
        param_name = pc.get("param_name", "param")
        old_val = pc.get("old_value")
        new_val = pc.get("new_value")
        old_str = json.dumps(old_val, ensure_ascii=False) if isinstance(old_val, (dict, list)) else str(old_val or "")
        new_str = json.dumps(new_val, ensure_ascii=False) if isinstance(new_val, (dict, list)) else str(new_val or "")
        status = pc.get("status", "SUCCESS")
        user = pc.get("user", "system")
        details = pc.get("details", "")
        details_str = json.dumps(details, ensure_ascii=False) if isinstance(details, (dict, list)) else str(details or "")
        raw_json = json.dumps({"app": app, "param_name": param_name, "old_value": old_val, "new_value": new_val, "status": status, "user": user, "details": details}, ensure_ascii=False)
        return (ts_str, now_epoch, app, param_name, old_str, new_str, status, user, details_str, raw_json)

    def prepare_device_event_row(self, event: Dict[str, Any], timestamp: Optional[str] = None) -> tuple:
        """Подготавливает кортеж для вставки события оборудования."""
        now_dt = datetime.now(timezone.utc)
        ts_str = timestamp or event.get("timestamp") or now_dt.isoformat()
        try:
            now_epoch = datetime.fromisoformat(ts_str).timestamp()
        except Exception:
            now_epoch = now_dt.timestamp()
        raw_json = json.dumps(event, ensure_ascii=False, default=str)
        return (
            ts_str, now_epoch, event.get("event_type", ""), event.get("device_instance_id", ""),
            event.get("friendly_name", ""), event.get("device_class", ""), event.get("category", ""),
            int(bool(event.get("has_problem", False))), event.get("problem_code", 0),
            event.get("status_code", 0), event.get("manufacturer", ""),
            event.get("flapping_count_in_window", 0), event.get("uptime_seconds", 0.0), raw_json,
        )

    def prepare_w64_event_row(self, event_data: Dict[str, Any], provider: str = "w64_collector") -> tuple:
        """Подготавливает кортеж для вставки события w64."""
        now_dt = datetime.now(timezone.utc)
        ts_str = event_data.get("timestamp") or now_dt.isoformat()
        try:
            now_epoch = datetime.fromisoformat(ts_str).timestamp()
        except Exception:
            now_epoch = now_dt.timestamp()
        event_id = str(event_data.get("event_id") or f"evt_{int(now_epoch)}")
        event_type = str(event_data.get("event_type", "unknown"))
        path_val = event_data.get("path")
        pid_val = event_data.get("pid")
        if pid_val is not None:
            try:
                pid_val = int(pid_val)
            except (ValueError, TypeError):
                pid_val = None
        name_val = event_data.get("name")
        raw_json = json.dumps(event_data, ensure_ascii=False, default=str)
        return (event_id, ts_str, now_epoch, event_type, path_val, pid_val, name_val, provider, raw_json)

    def prepare_process_provenance_row(self, p: Any) -> tuple:
        """Подготавливает кортеж для вставки события provenance процесса."""
        p_dict = p if isinstance(p, dict) else (p.model_dump() if hasattr(p, "model_dump") else (vars(p) if hasattr(p, "__dict__") else p))
        now_dt = datetime.now(timezone.utc)
        ts_str = p_dict.get("timestamp") or now_dt.isoformat()
        try:
            now_epoch = datetime.fromisoformat(ts_str).timestamp()
        except Exception:
            now_epoch = now_dt.timestamp()

        pid = int(p_dict.get("pid") or 0)
        event_id = p_dict.get("event_id") or f"pp_{int(now_epoch * 1000)}_{pid}"
        event_type = p_dict.get("event_type") or "ProcessCreated"
        ppid = int(p_dict["ppid"]) if p_dict.get("ppid") is not None else None
        name = p_dict.get("name") or "unknown"
        exe_path = p_dict.get("executable_path") or p_dict.get("executable")
        cmdline = p_dict.get("command_line") or p_dict.get("cmdline")
        user = p_dict.get("user") or p_dict.get("username")
        sid = p_dict.get("sid")
        session_id = int(p_dict["session_id"]) if p_dict.get("session_id") is not None else None
        integrity = p_dict.get("integrity_level")
        elevation = int(bool(p_dict.get("elevation", False)))
        parent_name = p_dict.get("parent_name")
        parent_cmdline = p_dict.get("parent_cmdline")
        ancestor_chain = p_dict.get("ancestor_chain") or p_dict.get("ancestor_chain_str")
        if isinstance(ancestor_chain, list):
            ancestor_chain = " -> ".join(ancestor_chain)
        launch_reason = p_dict.get("launch_reason") or p_dict.get("why_was_it_created")
        source = p_dict.get("source") or "system"
        creation_time = p_dict.get("creation_time") or ts_str
        process_guid = p_dict.get("process_guid") or f"proc_{pid}_{creation_time}"
        parent_guid = p_dict.get("parent_guid")
        details = p_dict.get("details") or p_dict.get("details_json")
        details_json = json.dumps(details, ensure_ascii=False) if isinstance(details, (dict, list)) else (str(details) if details else None)

        return (
            event_id, ts_str, now_epoch, event_type, process_guid, parent_guid,
            pid, ppid, name, exe_path, cmdline, user, sid, session_id,
            integrity, elevation, parent_name, parent_cmdline,
            ancestor_chain, launch_reason, source, details_json, None,
        )

