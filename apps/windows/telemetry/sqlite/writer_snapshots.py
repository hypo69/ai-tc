# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry Sqlite - TelemetrySnapshotWriterMixin
# =============================================================================
# Description:
#   Миксин записи снапшотов, процессов, сенсоров, событий, инцидентов и агрегатов
#   в 12 консолидированных таблиц базы данных телеметрии SQLite.
#
# File: writer_snapshots.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry.sqlite
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 18:55:00
# =============================================================================

from __future__ import annotations

"""Миксин записи снапшотов, процессов, сенсоров, событий, инцидентов и агрегатов в 12 базовых таблиц."""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from .delta_inventory import DeltaInventory
from .writer_inventory import _upsert_hw_component_row


def _safe_float_epoch(val: Any) -> Optional[float]:
    """Безопасное преобразование временной метки (число, ISO-строка) в секунды Unix epoch."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        try:
            return float(val)
        except (ValueError, TypeError):
            try:
                return datetime.fromisoformat(val).timestamp()
            except Exception:
                return None
    return None


def _dump_json_safe(val: Any) -> Optional[str]:
    """Безопасная сериализация объектов в JSON с поддержкой Pydantic-моделей."""
    if val is None:
        return None
    if isinstance(val, str):
        return val
    try:
        if isinstance(val, list):
            clean_list = [
                it.model_dump() if hasattr(it, "model_dump") else (vars(it) if hasattr(it, "__dict__") else it)
                for it in val
            ]
            return json.dumps(clean_list, ensure_ascii=False)
        if isinstance(val, dict):
            return json.dumps(val, ensure_ascii=False)
        if hasattr(val, "model_dump"):
            return json.dumps(val.model_dump(), ensure_ascii=False)
        return json.dumps(val, ensure_ascii=False)
    except Exception:
        return None


class TelemetrySnapshotWriterMixin:
    """Миксин записи снапшотов, процессов, сенсоров, событий и агрегатов."""

    def insert_snapshot_row(self, cursor: sqlite3.Cursor, item: Dict[str, Any]) -> int:
        """Вставляет строку системного снимка и процессов с дельта-фильтрацией в system_snapshots и process_snapshots."""
        self._delta_tracker.ensure_seeded(cursor)
        now_epoch = datetime.now(timezone.utc).timestamp()

        raw_snap = item.get("data") if isinstance(item, dict) and "data" in item else item
        if hasattr(raw_snap, "to_dict"):
            snap_dict = raw_snap.to_dict()
        elif hasattr(raw_snap, "model_dump"):
            snap_dict = raw_snap.model_dump(mode="json")
        elif isinstance(raw_snap, dict):
            snap_dict = dict(raw_snap)
        else:
            return 0

        ts_str = snap_dict.get("timestamp") or datetime.now(timezone.utc).isoformat()
        cpu = snap_dict.get("cpu") or {}
        mem = snap_dict.get("memory") or {}
        disk_io = snap_dict.get("disk_io") or {}
        net_io = snap_dict.get("network_io")
        net_sent_total = 0.0
        net_recv_total = 0.0
        if isinstance(net_io, dict) and net_io:
            net_sent_total = float(net_io.get("bytes_sent_per_sec") or net_io.get("bytes_sent_sec") or 0.0)
            net_recv_total = float(net_io.get("bytes_recv_per_sec") or net_io.get("bytes_recv_sec") or 0.0)
        else:
            net_list = snap_dict.get("network") or []
            for iface in net_list:
                if isinstance(iface, dict):
                    net_sent_total += float(iface.get("bytes_sent_per_sec") or iface.get("bytes_sent_sec") or 0.0)
                    net_recv_total += float(iface.get("bytes_recv_per_sec") or iface.get("bytes_recv_sec") or 0.0)
                elif hasattr(iface, "bytes_sent_per_sec"):
                    net_sent_total += float(getattr(iface, "bytes_sent_per_sec", 0.0) or getattr(iface, "bytes_sent_sec", 0.0) or 0.0)
                    net_recv_total += float(getattr(iface, "bytes_recv_per_sec", 0.0) or getattr(iface, "bytes_recv_sec", 0.0) or 0.0)
        gpus = snap_dict.get("gpus") or []

        gpu_load = 0.0
        gpu_temp = None
        gpu_vram = None
        if gpus and isinstance(gpus, list) and len(gpus) > 0:
            first_gpu = gpus[0] if isinstance(gpus[0], dict) else {}
            gpu_load = float(first_gpu.get("load_percent", 0.0) or 0.0)
            gpu_temp = first_gpu.get("temperature_celsius")
            gpu_vram = first_gpu.get("memory_used_mb")

        input_langs = snap_dict.get("input_languages")
        disks_list = snap_dict.get("disks")
        phys_disks = snap_dict.get("physical_disks")
        monitors_list = snap_dict.get("monitors")
        updates_dict = snap_dict.get("updates")
        office_dict = snap_dict.get("office")
        onedrive_dict = snap_dict.get("onedrive")
        battery_dict = snap_dict.get("battery")
        ram_sticks = snap_dict.get("ram_sticks")
        ports_list = snap_dict.get("listening_ports")
        alerts_list = snap_dict.get("alerts")
        hw_audit = snap_dict.get("hardware_audit")

        cpu_tot = snap_dict.get("cpu_total_percent")
        if cpu_tot is None:
            cpu_tot = cpu.get("total_percent", 0.0)
        cpu_freq = snap_dict.get("cpu_frequency_mhz")
        if cpu_freq is None:
            cpu_freq = cpu.get("frequency_mhz", 0.0)
        cpu_temp = snap_dict.get("cpu_temp_c")
        if cpu_temp is None:
            cpu_temp = cpu.get("temperature_celsius")
        cpu_power = snap_dict.get("cpu_power_w")
        if cpu_power is None:
            cpu_power = cpu.get("package_power_watts") or cpu.get("power_watts")

        mem_tot = snap_dict.get("memory_total_gb")
        if mem_tot is None:
            mem_tot = mem.get("total_gb", 0.0)
        mem_used = snap_dict.get("memory_used_gb")
        if mem_used is None:
            mem_used = mem.get("used_gb", 0.0)
        mem_pct = snap_dict.get("memory_percent")
        if mem_pct is None:
            mem_pct = mem.get("percent", 0.0)
        swap_pct = snap_dict.get("swap_percent")
        if swap_pct is None:
            swap_pct = mem.get("swap_percent", 0.0)

        raw_fields: Dict[str, Any] = {
            "timestamp": ts_str,
            "created_at": now_epoch,
            "hostname": snap_dict.get("hostname"),
            "username": snap_dict.get("username"),
            "uptime_seconds": float(snap_dict.get("uptime_seconds", 0.0) or 0.0),
            "os_name": snap_dict.get("os_name"),
            "os_build": snap_dict.get("os_build"),
            "os_install_date": snap_dict.get("os_install_date"),
            "system_language": snap_dict.get("system_language"),
            "os_install_language": snap_dict.get("os_install_language"),
            "user_locale": snap_dict.get("user_locale"),
            "system_locale": snap_dict.get("system_locale"),
            "timezone": snap_dict.get("timezone"),
            "codepage": snap_dict.get("codepage"),
            "input_languages_json": _dump_json_safe(input_langs),
            "disks_json": _dump_json_safe(disks_list),
            "physical_disks_json": _dump_json_safe(phys_disks),
            "monitors_json": _dump_json_safe(monitors_list),
            "updates_json": _dump_json_safe(updates_dict),
            "office_json": _dump_json_safe(office_dict),
            "onedrive_json": _dump_json_safe(onedrive_dict),
            "battery_json": _dump_json_safe(battery_dict),
            "ram_sticks_json": _dump_json_safe(ram_sticks),
            "listening_ports_json": _dump_json_safe(ports_list),
            "alerts_json": _dump_json_safe(alerts_list),
            "cpu_total_percent": float(cpu_tot or 0.0),
            "cpu_frequency_mhz": float(cpu_freq or 0.0),
            "cpu_temp_c": float(cpu_temp) if cpu_temp is not None else None,
            "cpu_power_w": float(cpu_power) if cpu_power is not None else None,
            "memory_total_gb": float(mem_tot or 0.0),
            "memory_used_gb": float(mem_used or 0.0),
            "memory_percent": float(mem_pct or 0.0),
            "swap_percent": float(swap_pct or 0.0),
            "gpu_load_percent": gpu_load,
            "gpu_temp_c": float(gpu_temp) if gpu_temp is not None else None,
            "gpu_vram_used_mb": float(gpu_vram) if gpu_vram is not None else None,
            "disk_read_bytes_sec": float(disk_io.get("read_bytes_per_sec", 0.0) or 0.0),
            "disk_write_bytes_sec": float(disk_io.get("write_bytes_per_sec", 0.0) or 0.0),
            "disk_read_count_sec": float(disk_io.get("read_count_per_sec", 0.0) or 0.0),
            "disk_write_count_sec": float(disk_io.get("write_count_per_sec", 0.0) or 0.0),
            "network_sent_bytes_sec": float(net_sent_total),
            "network_recv_bytes_sec": float(net_recv_total),
            "hardware_audit": json.dumps(hw_audit, ensure_ascii=False) if isinstance(hw_audit, (dict, list)) else hw_audit,
        }

        delta_fields, has_static_changes = self._delta_tracker.filter_snapshot_delta(raw_fields)

        if has_static_changes:
            slim_raw = {
                k: v for k, v in snap_dict.items()
                if k not in (
                    "top_processes", "disks", "physical_disks", "monitors",
                    "updates", "office", "onedrive", "battery", "ram_sticks",
                    "listening_ports", "alerts", "hardware_audit",
                )
            }
            raw_json_str = json.dumps(slim_raw, ensure_ascii=False)
        else:
            raw_json_str = None

        cursor.execute(
            '''
            INSERT INTO system_snapshots (
                timestamp, created_at, hostname, username, uptime_seconds,
                os_name, os_build, os_install_date, system_language, os_install_language,
                user_locale, system_locale, timezone, codepage, input_languages_json,
                disks_json, physical_disks_json, monitors_json, updates_json, office_json,
                onedrive_json, battery_json, ram_sticks_json, listening_ports_json, alerts_json,
                cpu_total_percent, cpu_frequency_mhz, cpu_temp_c, cpu_power_w,
                memory_total_gb, memory_used_gb, memory_percent, swap_percent,
                gpu_load_percent, gpu_temp_c, gpu_vram_used_mb,
                disk_read_bytes_sec, disk_write_bytes_sec, disk_read_count_sec, disk_write_count_sec,
                network_sent_bytes_sec, network_recv_bytes_sec, hardware_audit, raw_json
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            );
            ''',
            (
                delta_fields.get("timestamp"),
                delta_fields.get("created_at"),
                delta_fields.get("hostname"),
                delta_fields.get("username"),
                delta_fields.get("uptime_seconds"),
                delta_fields.get("os_name"),
                delta_fields.get("os_build"),
                delta_fields.get("os_install_date"),
                delta_fields.get("system_language"),
                delta_fields.get("os_install_language"),
                delta_fields.get("user_locale"),
                delta_fields.get("system_locale"),
                delta_fields.get("timezone"),
                delta_fields.get("codepage"),
                delta_fields.get("input_languages_json"),
                delta_fields.get("disks_json"),
                delta_fields.get("physical_disks_json"),
                delta_fields.get("monitors_json"),
                delta_fields.get("updates_json"),
                delta_fields.get("office_json"),
                delta_fields.get("onedrive_json"),
                delta_fields.get("battery_json"),
                delta_fields.get("ram_sticks_json"),
                delta_fields.get("listening_ports_json"),
                delta_fields.get("alerts_json"),
                delta_fields.get("cpu_total_percent"),
                delta_fields.get("cpu_frequency_mhz"),
                raw_fields.get("cpu_temp_c"),
                raw_fields.get("cpu_power_w"),
                raw_fields.get("memory_total_gb"),
                delta_fields.get("memory_used_gb"),
                delta_fields.get("memory_percent"),
                delta_fields.get("swap_percent"),
                delta_fields.get("gpu_load_percent"),
                raw_fields.get("gpu_temp_c"),
                raw_fields.get("gpu_vram_used_mb"),
                delta_fields.get("disk_read_bytes_sec"),
                delta_fields.get("disk_write_bytes_sec"),
                delta_fields.get("disk_read_count_sec"),
                delta_fields.get("disk_write_count_sec"),
                delta_fields.get("network_sent_bytes_sec"),
                delta_fields.get("network_recv_bytes_sec"),
                delta_fields.get("hardware_audit"),
                raw_json_str,
            ),
        )
        snapshot_id = cursor.lastrowid

        # Инвентаризация оборудования обновляется только при изменении статической конфигурации
        if has_static_changes:
            if cpu and isinstance(cpu, dict) and (cpu.get("model") or cpu.get("name")):
                self.upsert_cpu_inventory(cursor, {
                    "processor_id": 0,
                    "name": cpu.get("model") or cpu.get("name"),
                    "vendor": cpu.get("vendor") or "",
                    "architecture": cpu.get("architecture") or "",
                    "physical_cores": cpu.get("cores_physical") or cpu.get("physical_cores") or 0,
                    "logical_cores": cpu.get("cores_logical") or cpu.get("logical_cores") or 0,
                    "base_frequency_mhz": cpu.get("frequency_mhz") or 0.0,
                    "max_frequency_mhz": cpu.get("frequency_max_mhz") or 0.0,
                    "l2_cache_kb": cpu.get("l2_cache_kb"),
                    "l3_cache_kb": cpu.get("l3_cache_kb"),
                    "socket": cpu.get("socket") or "",
                })
            if ram_sticks and isinstance(ram_sticks, list):
                for idx, stick in enumerate(ram_sticks):
                    if isinstance(stick, dict):
                        self.upsert_ram_module_inventory(cursor, {
                            "bank_label": stick.get("bank_label") or f"BANK{idx}",
                            "device_locator": stick.get("device_locator") or stick.get("slot") or f"DIMM{idx}",
                            "manufacturer": stick.get("manufacturer") or "Unknown",
                            "part_number": stick.get("part_number") or "",
                            "serial_number": stick.get("serial_number") or "",
                            "capacity_bytes": int(float(stick.get("capacity_gb", 0.0) or 0.0) * (1024 ** 3)),
                            "capacity_gb": float(stick.get("capacity_gb", 0.0) or 0.0),
                            "speed_mhz": stick.get("speed_mhz") or stick.get("speed") or 0,
                            "memory_type": stick.get("memory_type") or stick.get("type") or "",
                            "form_factor": stick.get("form_factor") or "DIMM",
                        })
            if gpus and isinstance(gpus, list):
                for g_idx, g in enumerate(gpus):
                    if isinstance(g, dict):
                        self.upsert_gpu_inventory(cursor, {
                            "gpu_index": g_idx,
                            "name": g.get("name") or f"GPU {g_idx}",
                            "vendor": g.get("vendor") or "",
                            "driver_version": g.get("driver_version") or "",
                            "vram_total_mb": float(g.get("memory_total_mb", 0.0) or 0.0),
                        })

        processes = snap_dict.get("top_processes") or []
        if processes and snapshot_id:
            proc_rows = []
            for p in processes:
                if not isinstance(p, dict):
                    continue
                mem_mb = float(p.get("memory_mb", 0.0) or 0.0)
                conns = p.get("connections") or p.get("sockets")
                sockets_str = json.dumps(conns, ensure_ascii=False) if conns else p.get("sockets_json")
                proc_rows.append((
                    snapshot_id,
                    "snapshot",
                    ts_str,
                    now_epoch,
                    int(p.get("pid", 0)),
                    str(p.get("name", "unknown")),
                    p.get("status"),
                    float(p.get("cpu_percent", 0.0) or 0.0),
                    mem_mb,
                    float(p.get("memory_percent", 0.0) or 0.0),
                    mem_mb,
                    int(p.get("num_threads", 0) or 0),
                    int(p.get("num_handles", 0) or 0),
                    p.get("username"),
                    float(p.get("read_bytes_sec", 0.0) or 0.0),
                    float(p.get("write_bytes_sec", 0.0) or 0.0),
                    p.get("integrity_level"),
                    int(p["elevation"]) if p.get("elevation") is not None else None,
                    int(p["ppid"]) if p.get("ppid") is not None else None,
                    p.get("parent_name"),
                    p.get("executable_path") or p.get("executable"),
                    p.get("cmdline"),
                    p.get("sid"),
                    int(p["session_id"]) if p.get("session_id") is not None else None,
                    _safe_float_epoch(p.get("creation_time")),
                    p.get("process_guid"),
                    json.dumps(p.get("ancestor_chain"), ensure_ascii=False) if isinstance(p.get("ancestor_chain"), list) else p.get("ancestor_chain"),
                    p.get("launch_reason"),
                    sockets_str,
                ))
            if proc_rows:
                cursor.executemany(
                    '''
                    INSERT INTO process_snapshots (
                        snapshot_id, sample_type, timestamp, created_at, pid, name, status,
                        cpu_percent, memory_mb, memory_percent, working_set_mb,
                        num_threads, num_handles, username, read_bytes_sec, write_bytes_sec,
                        integrity_level, elevation, ppid, parent_name, executable,
                        cmdline, sid, session_id, creation_time, process_guid,
                        ancestor_chain, launch_reason, sockets_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    ''',
                    proc_rows,
                )

        return 1

    def insert_event_row(self, cursor: sqlite3.Cursor, ev_data: Dict[str, Any]) -> int:
        """Вставляет строку системного события в таблицу incidents."""
        now_dt = datetime.now(timezone.utc)
        ts_str = ev_data.get("timestamp") or now_dt.isoformat()
        created_at = float(ev_data.get("created_at") or now_dt.timestamp())
        ev_type = str(ev_data.get("event_type") or "system_event")
        sev = str(ev_data.get("severity") or "INFO")
        source = str(ev_data.get("source") or "System")
        msg = str(ev_data.get("message") or "")
        raw_j = ev_data.get("raw_json")
        if isinstance(raw_j, (dict, list)):
            raw_j = json.dumps(raw_j, ensure_ascii=False)

        inc_id = str(ev_data.get("incident_id") or f"tel_{int(created_at * 1000)}_{uuid.uuid4().hex[:8]}")
        cursor.execute(
            '''
            INSERT INTO incidents (
                incident_id, timestamp, created_at, domain, trigger_type, severity,
                title, provider_name, message, details_json
            ) VALUES (?, ?, ?, 'telemetry_event', ?, ?, ?, ?, ?, ?);
            ''',
            (inc_id, ts_str, created_at, ev_type, sev, source, source, msg, raw_j),
        )
        return 1

    def insert_sensor_row(self, cursor: sqlite3.Cursor, s_data: Dict[str, Any]) -> int:
        """Вставляет строку показаний датчика в sensor_polls только при изменении значения."""
        sensor_id = str(s_data.get("sensor_id") or s_data.get("sensor_name") or "unknown")
        val = s_data.get("value")
        if not self._delta_tracker.filter_sensor_poll(sensor_id, val):
            return 0

        now_dt = datetime.now(timezone.utc)
        ts_str = s_data.get("timestamp") or now_dt.isoformat()
        num_val = float(val) if isinstance(val, (int, float)) else None
        cursor.execute(
            '''
            INSERT INTO sensor_polls (
                sensor_id, timestamp, created_at, hardware_name, hardware_type,
                sensor_category, sensor_type, sensor_name, value, value_numeric,
                min_val, max_val, unit, status, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            ''',
            (
                sensor_id,
                ts_str,
                now_dt.timestamp(),
                s_data.get("hardware_name"),
                s_data.get("hardware_type"),
                s_data.get("sensor_category"),
                s_data.get("sensor_type"),
                s_data.get("sensor_name"),
                val,
                num_val,
                s_data.get("min_val"),
                s_data.get("max_val"),
                s_data.get("unit"),
                s_data.get("status") or "OK",
                json.dumps(s_data.get("raw_json"), ensure_ascii=False) if isinstance(s_data.get("raw_json"), dict) else s_data.get("raw_json"),
            ),
        )
        return 1

    def insert_app_event(self, cursor: sqlite3.Cursor, ev_data: Dict[str, Any]) -> int:
        """Вставляет событие приложения в таблицу incidents (domain='app_event')."""
        now_dt = datetime.now(timezone.utc)
        ts_str = ev_data.get("timestamp") or now_dt.isoformat()
        app_name = str(ev_data.get("app") or "unknown")
        ev_type = str(ev_data.get("event_type") or "info")
        details = ev_data.get("details")
        details_str = json.dumps(details, ensure_ascii=False) if isinstance(details, (dict, list)) else str(details or "")
        inc_id = str(ev_data.get("incident_id") or f"app_{app_name}_{int(now_dt.timestamp() * 1000)}_{uuid.uuid4().hex[:8]}")
        cursor.execute(
            '''
            INSERT INTO incidents (
                incident_id, timestamp, created_at, domain, trigger_type, severity,
                title, app_name, message, details_json
            ) VALUES (?, ?, ?, 'app_event', ?, ?, ?, ?, ?, ?);
            ''',
            (
                inc_id,
                ts_str,
                now_dt.timestamp(),
                ev_type,
                str(ev_data.get("severity") or "INFO"),
                f"{app_name}:{ev_type}",
                app_name,
                str(ev_data.get("message") or ""),
                details_str,
            ),
        )
        return 1

    def insert_app_poll(self, cursor: sqlite3.Cursor, poll_data: Dict[str, Any]) -> int:
        """Вставляет опрос состояния приложения в таблицу incidents (domain='app_poll') при изменении метрики."""
        app = str(poll_data.get("app") or "unknown")
        metric_name = str(poll_data.get("metric_name") or "status")
        val = poll_data.get("value")
        status = str(poll_data.get("status") or "OK")

        if not self._delta_tracker.filter_app_poll(app, metric_name, val, status):
            return 0

        now_dt = datetime.now(timezone.utc)
        ts_str = poll_data.get("timestamp") or now_dt.isoformat()
        details = poll_data.get("details")
        details_str = json.dumps(details, ensure_ascii=False) if isinstance(details, (dict, list)) else str(details or "")
        inc_id = str(poll_data.get("incident_id") or f"poll_{app}_{metric_name}_{int(now_dt.timestamp() * 1000)}_{uuid.uuid4().hex[:8]}")
        cursor.execute(
            '''
            INSERT INTO incidents (
                incident_id, timestamp, created_at, domain, trigger_type, severity,
                title, app_name, value, unit, message, details_json
            ) VALUES (?, ?, ?, 'app_poll', ?, ?, ?, ?, ?, ?, ?, ?);
            ''',
            (
                inc_id,
                ts_str,
                now_dt.timestamp(),
                metric_name,
                status,
                f"{app}:{metric_name}",
                app,
                float(val) if isinstance(val, (int, float)) else None,
                poll_data.get("unit"),
                status,
                details_str,
            ),
        )
        return 1

    def insert_app_param_change(self, cursor: sqlite3.Cursor, ch_data: Dict[str, Any]) -> int:
        """Вставляет изменение параметра приложения в таблицу inventory_changes."""
        now_dt = datetime.now(timezone.utc)
        ts_str = ch_data.get("timestamp") or now_dt.isoformat()
        app_name = str(ch_data.get("app") or "unknown")
        param_name = str(ch_data.get("param_name") or "unknown")
        diff_payload = {
            "app": app_name,
            "param_name": param_name,
            "old_value": str(ch_data.get("old_value")) if ch_data.get("old_value") is not None else None,
            "new_value": str(ch_data.get("new_value")) if ch_data.get("new_value") is not None else None,
            "changed_by": ch_data.get("changed_by") or "system",
        }
        cursor.execute(
            '''
            INSERT INTO inventory_changes (
                timestamp, created_at, domain, entity_key, change_type, diff_json
            ) VALUES (?, ?, ?, ?, 'modified', ?);
            ''',
            (
                ts_str,
                now_dt.timestamp(),
                f"app_params:{app_name}",
                param_name,
                json.dumps(diff_payload, ensure_ascii=False),
            ),
        )
        return 1

    def insert_w64_event(self, cursor: sqlite3.Cursor, w64_data: Dict[str, Any]) -> int:
        """Вставляет нормализованное событие ядра/файловой системы в process_file_events."""
        now_dt = datetime.now(timezone.utc)
        ts_str = w64_data.get("timestamp") or now_dt.isoformat()
        raw_j = w64_data.get("raw_json")
        ev_type = str(w64_data.get("event_type") or "unknown").strip().upper()
        details = {
            "source": "etw",
            "event_type": ev_type,
            "provider": w64_data.get("provider", "w64_collector"),
            "raw": json.loads(raw_j) if isinstance(raw_j, str) and raw_j.startswith("{") else raw_j,
        }
        cursor.execute(
            '''
            INSERT INTO process_file_events (
                pid, process_name, timestamp, created_at, operation_type,
                file_path, target_directory, details_json
            ) VALUES (?, ?, ?, ?, ?, ?, '', ?);
            ''',
            (
                int(w64_data.get("pid") or 0),
                w64_data.get("name") or "",
                ts_str,
                now_dt.timestamp(),
                ev_type,
                str(w64_data.get("path") or ""),
                json.dumps(details, ensure_ascii=False, default=str),
            ),
        )
        return 1

    def insert_reboot_session(self, cursor: sqlite3.Cursor, session_data: Dict[str, Any]) -> int:
        """Вставляет реконструированную сессию перезагрузки в таблицу power_sessions."""
        now_dt = datetime.now(timezone.utc)
        created_at = float(session_data.get("created_at") or now_dt.timestamp())
        sess_id = str(session_data.get("session_id") or f"reboot_{int(created_at * 1000)}")
        boot_time = str(session_data.get("boot_time") or now_dt.isoformat())
        classification = str(session_data.get("classification") or "CLEAN_REBOOT")
        unexpected = 1 if ("BSOD" in classification.upper() or "UNEXPECTED" in classification.upper() or "POWER_LOSS" in classification.upper()) else 0

        cursor.execute(
            '''
            INSERT INTO power_sessions (
                session_id, record_type, boot_time, boot_timestamp, shutdown_time,
                uptime_seconds, shutdown_type, classification, confidence,
                initiator, user, process, reason, summary,
                clean_shutdown, unexpected_shutdown, bugcheck_code,
                bugcheck_params_json, dump_file, evidence_json, events_json,
                details_json, created_at
            ) VALUES (?, 'reboot', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                boot_time = excluded.boot_time,
                shutdown_time = excluded.shutdown_time,
                uptime_seconds = excluded.uptime_seconds,
                shutdown_type = excluded.shutdown_type,
                classification = excluded.classification,
                confidence = excluded.confidence,
                initiator = excluded.initiator,
                process = excluded.process,
                reason = excluded.reason,
                summary = excluded.summary,
                bugcheck_code = excluded.bugcheck_code,
                bugcheck_params_json = excluded.bugcheck_params_json,
                dump_file = excluded.dump_file,
                evidence_json = excluded.evidence_json,
                events_json = excluded.events_json,
                details_json = excluded.details_json;
            ''',
            (
                sess_id,
                boot_time,
                created_at,
                session_data.get("shutdown_time"),
                float(session_data.get("downtime_seconds") or 0.0),
                classification,
                classification,
                session_data.get("confidence", "MEDIUM"),
                session_data.get("initiated_by_user"),
                session_data.get("initiated_by_user"),
                session_data.get("initiated_by_process"),
                session_data.get("primary_reason"),
                session_data.get("summary"),
                0 if unexpected else 1,
                unexpected,
                session_data.get("bugcheck_code"),
                json.dumps(session_data.get("bugcheck_params"), ensure_ascii=False) if isinstance(session_data.get("bugcheck_params"), list) else session_data.get("bugcheck_params_json"),
                session_data.get("dump_file"),
                json.dumps(session_data.get("evidence"), ensure_ascii=False) if isinstance(session_data.get("evidence"), list) else session_data.get("evidence_json"),
                json.dumps(session_data.get("events_chain"), ensure_ascii=False) if isinstance(session_data.get("events_chain"), list) else session_data.get("events_chain_json"),
                json.dumps(session_data.get("raw_json"), ensure_ascii=False) if isinstance(session_data.get("raw_json"), dict) else session_data.get("raw_json"),
                created_at,
            ),
        )
        return 1

    def insert_extended_audit(self, cursor: sqlite3.Cursor, audit_data: Dict[str, Any]) -> int:
        """Сохраняет расширенный системный аудит в Change-Only инвентаризацию (inventory_state)."""
        now_dt = datetime.now(timezone.utc)
        audit_id = str(audit_data.get("audit_id") or f"audit_{int(now_dt.timestamp() * 1000)}")
        raw_j = audit_data.get("raw_json")
        raw_str = json.dumps(raw_j, ensure_ascii=False) if isinstance(raw_j, dict) else str(raw_j or "{}")
        vss_cnt = int(audit_data.get("vss_snapshots_count") or 0)
        payload = {
            "audit_id": audit_id,
            "timestamp": audit_data.get("timestamp") or now_dt.isoformat(),
            "created_at": now_dt.timestamp(),
            "hostname": audit_data.get("hostname"),
            "services_count": int(audit_data.get("services_count") or 0),
            "drivers_count": int(audit_data.get("drivers_count") or 0),
            "startup_items_count": int(audit_data.get("startup_items_count") or 0),
            "scheduled_tasks_count": int(audit_data.get("scheduled_tasks_count") or 0),
            "shares_count": int(audit_data.get("shares_count") or 0),
            "vss_snapshots_count": vss_cnt,
            "Whea_errors_count": int(audit_data.get("whea_errors_count") or 0),
            "whea_errors_count": int(audit_data.get("whea_errors_count") or 0),
            "app_crashes_count": int(audit_data.get("app_crashes_count") or 0),
            "raw_json": raw_str,
        }
        DeltaInventory.patch(cursor, "os_extended_audit", audit_id, payload)
        cursor.execute(
            "UPDATE system_snapshots SET vss_snapshots_count = ? WHERE id = (SELECT MAX(id) FROM system_snapshots);",
            (vss_cnt,),
        )
        return 1

    def insert_hardware_archive_row(self, cursor: sqlite3.Cursor, data: Any) -> int:
        """Сохраняет полный аудит оборудования в таблицу hardware_components (category='hardware_audit')."""
        audit_data = data if isinstance(data, dict) else (data.model_dump() if hasattr(data, "model_dump") else {})
        changes_cnt = int(audit_data.get("changes_count") or audit_data.get("changes_detected") or 0)
        if changes_cnt == 0:
            existing_row = cursor.execute(
                "SELECT 1 FROM hardware_components WHERE category = 'hardware_audit' LIMIT 1;"
            ).fetchone()
            if existing_row:
                return 0

        now_dt = datetime.now(timezone.utc)
        audit_id = str(audit_data.get("archive_id") or audit_data.get("audit_id") or f"hw_{int(now_dt.timestamp() * 1000)}")
        raw_j = audit_data.get("raw_json")
        raw_str = json.dumps(raw_j, ensure_ascii=False) if isinstance(raw_j, dict) else str(raw_j or "{}")
        specs = {
            **audit_data,
            "archive_id": audit_id,
            "audit_id": audit_id,
            "timestamp": audit_data.get("timestamp") or now_dt.isoformat(),
            "created_at": now_dt.timestamp(),
            "hostname": audit_data.get("hostname"),
            "cpu_model": audit_data.get("cpu_model"),
            "motherboard_model": audit_data.get("motherboard_model"),
            "bios_version": audit_data.get("bios_version"),
            "ram_total_gb": float(audit_data.get("ram_total_gb") or 0.0),
            "gpu_count": int(audit_data.get("gpu_count") or 0),
            "disk_count": int(audit_data.get("disk_count") or 0),
            "usb_devices_count": int(audit_data.get("usb_devices_count") or 0),
            "problem_devices_count": int(audit_data.get("problem_devices_count") or 0),
            "changes_count": changes_cnt,
            "raw_json": raw_str,
        }
        return _upsert_hw_component_row(
            cursor=cursor,
            category="hardware_audit",
            component_key=audit_id,
            name=str(audit_data.get("cpu_model") or audit_data.get("hostname") or audit_id),
            model=str(audit_data.get("motherboard_model") or ""),
            specs=specs,
        )

    def insert_startup_archive_row(self, cursor: sqlite3.Cursor, data: Any) -> int:
        """Сохраняет архивный снимок автозапуска в inventory_state (domain='startup_archive')."""
        archive_data = data if isinstance(data, dict) else (data.model_dump() if hasattr(data, "model_dump") else {})
        changes_cnt = int(archive_data.get("changes_count") or archive_data.get("changes_detected") or len(archive_data.get("changes") or []) or 0)
        if changes_cnt == 0 and DeltaInventory.get_active(cursor, "startup_archive"):
            return 0

        now_dt = datetime.now(timezone.utc)
        archive_id = str(archive_data.get("archive_id") or f"startup_{int(now_dt.timestamp() * 1000)}")
        raw_j = archive_data.get("raw_json")
        raw_str = json.dumps(raw_j, ensure_ascii=False) if isinstance(raw_j, dict) else str(raw_j or "{}")
        payload = {
            **archive_data,
            "archive_id": archive_id,
            "timestamp": archive_data.get("timestamp") or now_dt.isoformat(),
            "created_at": now_dt.timestamp(),
            "hostname": archive_data.get("hostname"),
            "total_items": int(archive_data.get("total_items") or 0),
            "registry_count": int(archive_data.get("registry_count") or 0),
            "folders_count": int(archive_data.get("folders_count") or 0),
            "tasks_count": int(archive_data.get("tasks_count") or 0),
            "services_count": int(archive_data.get("services_count") or 0),
            "changes_count": changes_cnt,
            "changes_detected": changes_cnt,
            "raw_json": raw_str,
        }
        DeltaInventory.patch(cursor, "startup_archive", archive_id, payload)
        for ch in (archive_data.get("changes") or []):
            if isinstance(ch, dict):
                self.insert_startup_change(cursor, {**ch, "archive_id": archive_id})
        return 1

    def insert_startup_change(self, cursor: sqlite3.Cursor, change_data: Dict[str, Any]) -> int:
        """Вставляет запись об обнаруженном изменении в автозапуске в таблицу inventory_changes."""
        now_dt = datetime.now(timezone.utc)
        ts_str = change_data.get("timestamp") or now_dt.isoformat()
        archive_id = str(change_data.get("archive_id") or "")
        item_name = str(change_data.get("item_name") or "unknown")
        ch_type = str(change_data.get("change_type") or "MODIFIED")
        diff_payload = {
            "archive_id": archive_id,
            "change_type": ch_type,
            "category": change_data.get("category") or "registry",
            "item_name": item_name,
            "location": change_data.get("location"),
            "previous_value": change_data.get("previous_value"),
            "current_value": change_data.get("current_value"),
            "summary": change_data.get("summary"),
        }
        cursor.execute(
            '''
            INSERT INTO inventory_changes (
                timestamp, created_at, domain, entity_key, change_type, diff_json
            ) VALUES (?, ?, 'startup_changes', ?, ?, ?);
            ''',
            (
                ts_str,
                now_dt.timestamp(),
                f"{archive_id}|{item_name}",
                ch_type,
                json.dumps(diff_payload, ensure_ascii=False, default=str),
            ),
        )
        return 1

    def insert_process_rollup_2min(self, cursor: sqlite3.Cursor, data: Dict[str, Any]) -> int:
        """Вставляет 2-минутный агрегат процесса в таблицу telemetry_rollups (tier='proc_2min')."""
        now_dt = datetime.now(timezone.utc)
        created_at = float(data.get("created_at") or now_dt.timestamp())
        name = str(data.get("name") or "unknown")
        cursor.execute(
            '''
            INSERT OR REPLACE INTO telemetry_rollups (
                tier, sensor_id, bucket_start, period_start, period_end,
                sample_count, cpu_avg, cpu_max, ram_avg, ram_max,
                payload_json, created_at
            ) VALUES ('proc_2min', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            ''',
            (
                name,
                created_at,
                data.get("window_start") or now_dt.isoformat(),
                data.get("window_end") or now_dt.isoformat(),
                int(data.get("sample_count") or 1),
                float(data.get("avg_cpu_percent") or 0.0),
                float(data.get("max_cpu_percent") or 0.0),
                float(data.get("avg_memory_mb") or 0.0),
                float(data.get("max_memory_mb") or 0.0),
                json.dumps(dict(data), ensure_ascii=False, default=str),
                created_at,
            ),
        )
        return 1

    def upsert_process_rollup_daily(self, cursor: sqlite3.Cursor, data: Dict[str, Any]) -> int:
        """Обновляет или вставляет суточную статистику процесса в telemetry_rollups (tier='proc_daily')."""
        now_dt = datetime.now(timezone.utc)
        date_str = str(data.get("date") or now_dt.strftime("%Y-%m-%d"))
        name = str(data.get("name") or "unknown")
        # Детерминированный ключ бакета по дате (YYYYMMDD)
        try:
            bucket_val = float(int(date_str.replace("-", "")))
        except ValueError:
            bucket_val = now_dt.timestamp()

        cursor.execute(
            "SELECT sample_count, cpu_avg, cpu_max, ram_avg, ram_max, payload_json FROM telemetry_rollups WHERE tier = 'proc_daily' AND sensor_id = ? AND bucket_start = ?;",
            (name, bucket_val),
        )
        existing = cursor.fetchone()
        new_samples = int(data.get("sample_count") or 1)
        new_cpu_avg = float(data.get("avg_cpu_percent") or 0.0)
        new_cpu_max = float(data.get("max_cpu_percent") or 0.0)
        new_ram_avg = float(data.get("avg_memory_mb") or 0.0)
        new_ram_max = float(data.get("max_memory_mb") or 0.0)
        new_out = int(data.get("outlier_count") or 0)

        if existing:
            old_samples = int(existing[0] or 0)
            tot_samples = old_samples + new_samples
            merged_cpu_avg = ((float(existing[1] or 0.0) * old_samples) + (new_cpu_avg * new_samples)) / max(1, tot_samples)
            merged_cpu_max = max(float(existing[2] or 0.0), new_cpu_max)
            merged_ram_avg = ((float(existing[3] or 0.0) * old_samples) + (new_ram_avg * new_samples)) / max(1, tot_samples)
            merged_ram_max = max(float(existing[4] or 0.0), new_ram_max)
            old_payload = json.loads(existing[5]) if existing[5] else {}
            tot_out = int(old_payload.get("outlier_count") or 0) + new_out
        else:
            tot_samples = new_samples
            merged_cpu_avg = new_cpu_avg
            merged_cpu_max = new_cpu_max
            merged_ram_avg = new_ram_avg
            merged_ram_max = new_ram_max
            tot_out = new_out

        payload = {
            **data,
            "date": date_str,
            "name": name,
            "sample_count": tot_samples,
            "avg_cpu_percent": merged_cpu_avg,
            "max_cpu_percent": merged_cpu_max,
            "avg_memory_mb": merged_ram_avg,
            "max_memory_mb": merged_ram_max,
            "outlier_count": tot_out,
            "updated_at": now_dt.timestamp(),
        }
        cursor.execute(
            '''
            INSERT OR REPLACE INTO telemetry_rollups (
                tier, sensor_id, bucket_start, period_start, sample_count,
                cpu_avg, cpu_max, ram_avg, ram_max, payload_json, created_at
            ) VALUES ('proc_daily', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            ''',
            (
                name,
                bucket_val,
                date_str,
                tot_samples,
                merged_cpu_avg,
                merged_cpu_max,
                merged_ram_avg,
                merged_ram_max,
                json.dumps(payload, ensure_ascii=False, default=str),
                now_dt.timestamp(),
            ),
        )
        return 1

    def insert_process_outlier(self, cursor: sqlite3.Cursor, data: Dict[str, Any]) -> int:
        """Вставляет аномальный выброс процесса в таблицу process_snapshots (sample_type='outlier')."""
        now_dt = datetime.now(timezone.utc)
        ts_str = data.get("timestamp") or now_dt.isoformat()
        created_at = float(data.get("created_at") or now_dt.timestamp())
        cursor.execute(
            '''
            INSERT INTO process_snapshots (
                sample_type, timestamp, created_at, pid, name, status,
                cpu_percent, memory_mb, num_threads, num_handles,
                read_bytes_sec, write_bytes_sec, username, executable, cmdline,
                is_outlier, raw_json
            ) VALUES ('outlier', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?);
            ''',
            (
                ts_str,
                created_at,
                int(data.get("pid") or 0),
                str(data.get("name") or "unknown"),
                data.get("status"),
                float(data.get("cpu_percent") or 0.0),
                float(data.get("memory_mb") or 0.0),
                int(data.get("num_threads") or 0),
                int(data.get("num_handles") or 0),
                float(data.get("read_bytes_sec") or 0.0),
                float(data.get("write_bytes_sec") or 0.0),
                data.get("username"),
                data.get("executable"),
                data.get("cmdline"),
                json.dumps(dict(data), ensure_ascii=False, default=str),
            ),
        )
        return 1

    def insert_incident(self, cursor: sqlite3.Cursor, data: Dict[str, Any]) -> int:
        """Сохраняет инцидент (Event-Triggered Blackbox) в таблицу incidents."""
        now_dt = datetime.now(timezone.utc)
        cursor.execute(
            '''
            INSERT OR REPLACE INTO incidents (
                incident_id, timestamp, created_at, domain, trigger_type, severity, title,
                window_start, window_end, duration_sec, trigger_metrics_json,
                suspect_processes_json, related_events_json, metrics_summary_json,
                raw_window_json, resolved
            ) VALUES (?, ?, ?, 'incident', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            ''',
            (
                data.get("incident_id", f"inc_{int(now_dt.timestamp() * 1000)}"),
                data.get("timestamp") or now_dt.isoformat(),
                float(data.get("created_at", now_dt.timestamp())),
                data.get("trigger_type", "spike"),
                data.get("severity", "WARNING"),
                data.get("title", "Системная аномалия"),
                data.get("window_start", now_dt.isoformat()),
                data.get("window_end", now_dt.isoformat()),
                float(data.get("duration_sec", 0.0)),
                json.dumps(data.get("trigger_metrics", {}), ensure_ascii=False) if isinstance(data.get("trigger_metrics"), dict) else data.get("trigger_metrics_json"),
                json.dumps(data.get("suspect_processes", []), ensure_ascii=False) if isinstance(data.get("suspect_processes"), list) else data.get("suspect_processes_json"),
                json.dumps(data.get("related_events", []), ensure_ascii=False) if isinstance(data.get("related_events"), list) else data.get("related_events_json"),
                json.dumps(data.get("metrics_summary", {}), ensure_ascii=False) if isinstance(data.get("metrics_summary"), dict) else data.get("metrics_summary_json"),
                json.dumps(data.get("raw_window", []), ensure_ascii=False) if isinstance(data.get("raw_window"), list) else data.get("raw_window_json"),
                int(data.get("resolved", 0)),
            ),
        )
        return 1

    def upsert_system_rollup(self, cursor: sqlite3.Cursor, data: Dict[str, Any]) -> int:
        """Вставляет или обновляет сжатый бакет метрик системы в telemetry_rollups."""
        now_dt = datetime.now(timezone.utc)
        tier = str(data.get("tier") or "1m")
        p_start_epoch = float(data.get("period_start_epoch", 0.0) or 0.0)
        cursor.execute(
            '''
            INSERT INTO telemetry_rollups (
                tier, sensor_id, bucket_start, period_start, period_end,
                period_start_epoch, period_end_epoch, sample_count,
                cpu_avg, cpu_max, cpu_p95, ram_avg, ram_max, ram_used_gb_avg,
                disk_read_bps_avg, disk_write_bps_avg, disk_read_bps_max, disk_write_bps_max,
                net_sent_bps_avg, net_recv_bps_avg, gpu_load_avg, gpu_temp_max, created_at
            ) VALUES (?, '__system__', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(tier, sensor_id, bucket_start) DO UPDATE SET
                period_end = excluded.period_end,
                period_end_epoch = excluded.period_end_epoch,
                sample_count = excluded.sample_count,
                cpu_avg = excluded.cpu_avg,
                cpu_max = MAX(telemetry_rollups.cpu_max, excluded.cpu_max),
                cpu_p95 = excluded.cpu_p95,
                ram_avg = excluded.ram_avg,
                ram_max = MAX(telemetry_rollups.ram_max, excluded.ram_max),
                ram_used_gb_avg = excluded.ram_used_gb_avg,
                disk_read_bps_avg = excluded.disk_read_bps_avg,
                disk_write_bps_avg = excluded.disk_write_bps_avg,
                disk_read_bps_max = MAX(telemetry_rollups.disk_read_bps_max, excluded.disk_read_bps_max),
                disk_write_bps_max = MAX(telemetry_rollups.disk_write_bps_max, excluded.disk_write_bps_max),
                net_sent_bps_avg = excluded.net_sent_bps_avg,
                net_recv_bps_avg = excluded.net_recv_bps_avg,
                gpu_load_avg = excluded.gpu_load_avg,
                gpu_temp_max = MAX(COALESCE(telemetry_rollups.gpu_temp_max, 0), COALESCE(excluded.gpu_temp_max, 0));
            ''',
            (
                tier,
                p_start_epoch,
                data.get("period_start") or now_dt.isoformat(),
                data.get("period_end") or now_dt.isoformat(),
                p_start_epoch,
                float(data.get("period_end_epoch", 0.0) or 0.0),
                int(data.get("sample_count", 1)),
                float(data.get("cpu_avg", 0.0) or 0.0),
                float(data.get("cpu_max", 0.0) or 0.0),
                float(data.get("cpu_p95", 0.0) or 0.0),
                float(data.get("ram_avg", 0.0) or 0.0),
                float(data.get("ram_max", 0.0) or 0.0),
                float(data.get("ram_used_gb_avg", 0.0) or 0.0),
                float(data.get("disk_read_bps_avg", 0.0) or 0.0),
                float(data.get("disk_write_bps_avg", 0.0) or 0.0),
                float(data.get("disk_read_bps_max", 0.0) or 0.0),
                float(data.get("disk_write_bps_max", 0.0) or 0.0),
                float(data.get("net_sent_bps_avg", 0.0) or 0.0),
                float(data.get("net_recv_bps_avg", 0.0) or 0.0),
                float(data.get("gpu_load_avg", 0.0) or 0.0),
                float(data["gpu_temp_max"]) if data.get("gpu_temp_max") is not None else None,
                now_dt.timestamp(),
            ),
        )
        return 1

    def insert_process_provenance_event(self, cursor: sqlite3.Cursor, data: Dict[str, Any]) -> int:
        """Вставляет событие жизненного цикла/provenance процесса в process_lifecycle_sessions."""
        now_dt = datetime.now(timezone.utc)
        ts_str = data.get("timestamp") or now_dt.isoformat()
        created_ts = float(data.get("created_at") or now_dt.timestamp())
        pid = int(data.get("pid") or 0)
        ev_type = str(data.get("event_type") or "START").upper()
        guid = str(data.get("process_guid") or f"{pid}_{int(created_ts * 1000)}")
        inst_id = f"prov_{guid}_{ev_type}_{int(created_ts * 1000)}"
        is_alive = 0 if ev_type in ("STOP", "EXIT", "TERMINATED") else 1

        raw_payload = {
            **data,
            "timestamp": ts_str,
            "created_at": created_ts,
            "event_type": ev_type,
            "process_guid": guid,
        }
        cursor.execute(
            '''
            INSERT OR REPLACE INTO process_lifecycle_sessions (
                instance_id, pid, ppid, name, exe_path, cmdline,
                username, sid, session_id, integrity_level,
                parent_name, parent_guid, initiator_type, status,
                created_at, created_ts, is_alive, exit_code, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            ''',
            (
                inst_id,
                pid,
                int(data["ppid"]) if data.get("ppid") is not None else None,
                str(data.get("name") or "unknown"),
                data.get("executable_path"),
                data.get("cmdline"),
                data.get("user"),
                data.get("sid"),
                int(data["session_id"]) if data.get("session_id") is not None else 1,
                data.get("integrity_level"),
                data.get("parent_name"),
                data.get("parent_guid"),
                data.get("launch_reason") or "provenance",
                f"PROV_{ev_type}",
                ts_str,
                created_ts,
                is_alive,
                int(data["exit_code"]) if data.get("exit_code") is not None else None,
                json.dumps(raw_payload, ensure_ascii=False, default=str),
            ),
        )
        return 1

    def insert_telemetry_spike(self, cursor: sqlite3.Cursor, s_data: Dict[str, Any]) -> int:
        """Записывает статистический всплеск или аномалию сенсора в таблицу incidents (domain='spike')."""
        now_dt = datetime.now(timezone.utc)
        ts_str = s_data.get("timestamp") or now_dt.isoformat()
        created_at = float(s_data.get("created_at") or now_dt.timestamp())
        sensor_id = str(s_data.get("sensor_id") or "unknown")
        spike_type = str(s_data.get("spike_type") or "3sigma")
        details = s_data.get("details")
        details_str = json.dumps(details, ensure_ascii=False) if isinstance(details, dict) else str(details or "")

        inc_id = str(s_data.get("incident_id") or f"spike_{sensor_id}_{int(created_at * 1000)}_{uuid.uuid4().hex[:8]}")
        cursor.execute(
            '''
            INSERT INTO incidents (
                incident_id, timestamp, created_at, domain, trigger_type, severity,
                title, sensor_id, value, baseline_mean, baseline_sigma,
                deviation_factor, unit, details_json
            ) VALUES (?, ?, ?, 'spike', ?, 'WARNING', ?, ?, ?, ?, ?, ?, ?, ?);
            ''',
            (
                inc_id,
                ts_str,
                created_at,
                spike_type,
                f"Spike: {sensor_id}",
                sensor_id,
                float(s_data.get("value") or 0.0),
                float(s_data["baseline_mean"]) if s_data.get("baseline_mean") is not None else None,
                float(s_data["baseline_sigma"]) if s_data.get("baseline_sigma") is not None else None,
                float(s_data["deviation_factor"]) if s_data.get("deviation_factor") is not None else None,
                s_data.get("unit"),
                details_str,
            ),
        )
        return 1

    def insert_process_file_event(self, cursor: sqlite3.Cursor, ev_data: Dict[str, Any]) -> int:
        """Записывает событие файловой активности в таблицу process_file_events."""
        now_dt = datetime.now(timezone.utc)
        ts_str = ev_data.get("timestamp") or now_dt.isoformat()
        created_at = float(ev_data.get("created_at") or now_dt.timestamp())
        cursor.execute(
            '''
            INSERT INTO process_file_events (
                instance_id, pid, process_name, timestamp, created_at,
                operation_type, file_path, target_directory, bytes_transferred
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            ''',
            (
                ev_data.get("instance_id"),
                int(ev_data.get("pid") or 0),
                ev_data.get("process_name") or ev_data.get("name"),
                ts_str,
                created_at,
                str(ev_data.get("operation_type") or ev_data.get("action_type") or ev_data.get("action") or "write"),
                str(ev_data.get("file_path") or ""),
                str(ev_data.get("target_directory") or ""),
                int(ev_data.get("bytes_transferred") or ev_data.get("bytes_affected") or ev_data.get("bytes_count") or 0),
            ),
        )
        return 1

    def insert_process_file_events(self, events: List[Union[Dict[str, Any], Any]]) -> int:
        """Сохраняет пакет событий файловой активности процессов в таблицу process_file_events."""
        if not events or self._cm.read_only:
            return 0
        count = 0
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            for ev in events:
                ev_dict = ev if isinstance(ev, dict) else (ev.model_dump() if hasattr(ev, "model_dump") else (vars(ev) if hasattr(ev, "__dict__") else {}))
                count += self.insert_process_file_event(cursor, ev_dict)
            conn.commit()
        return count

    def insert_process_pid_snapshots(self, snapshots: List[Union[Dict[str, Any], Any]]) -> int:
        """Сохраняет пакет PID-снимков метрик процессов в таблицу process_snapshots."""
        if not snapshots or self._cm.read_only:
            return 0
        now_dt = datetime.now(timezone.utc)
        now_iso = now_dt.isoformat()
        now_epoch = now_dt.timestamp()
        rows = []
        for snap in snapshots:
            d = snap if isinstance(snap, dict) else (snap.model_dump() if hasattr(snap, "model_dump") else (vars(snap) if hasattr(snap, "__dict__") else {}))
            ws_mb = float(d.get("working_set_bytes", 0) or 0) / 1048576.0 if d.get("working_set_bytes") else float(d.get("working_set_mb") or d.get("memory_mb") or 0.0)
            priv_mb = float(d.get("private_bytes", 0) or 0) / 1048576.0 if d.get("private_bytes") else float(d.get("private_mb") or 0.0)
            rows.append((
                "pid_snapshot",
                d.get("timestamp") or now_iso,
                float(d.get("created_at") or now_epoch),
                int(d.get("pid") or 0),
                str(d.get("process_name") or d.get("name") or "unknown"),
                d.get("executable_path") or d.get("executable"),
                float(d.get("cpu_percent") or 0.0),
                float(d.get("user_time_ms", 0) or 0) / 1000.0 if d.get("user_time_ms") else float(d.get("user_time_sec") or 0.0),
                float(d.get("kernel_time_ms", 0) or 0) / 1000.0 if d.get("kernel_time_ms") else float(d.get("kernel_time_sec") or 0.0),
                int(d.get("thread_count") or d.get("num_threads") or 0),
                ws_mb,
                ws_mb,
                priv_mb,
                int(d.get("page_faults_count") or d.get("page_faults") or 0),
                float(d.get("read_bytes_total") or d.get("read_bytes_sec") or 0.0),
                float(d.get("write_bytes_total") or d.get("write_bytes_sec") or 0.0),
                int(d.get("read_ops_total") or d.get("read_operations") or 0),
                int(d.get("write_ops_total") or d.get("write_operations") or 0),
                int(d.get("handle_count") or d.get("num_handles") or 0),
                int(d.get("gdi_objects") or 0),
                int(d.get("user_objects") or 0),
            ))
        with self._cm.lock, self._cm.get_connection() as conn:
            conn.cursor().executemany(
                '''
                INSERT INTO process_snapshots (
                    sample_type, timestamp, created_at, pid, name, executable,
                    cpu_percent, user_time_sec, kernel_time_sec, num_threads,
                    memory_mb, working_set_mb, private_mb, page_faults,
                    read_bytes_sec, write_bytes_sec, read_operations, write_operations,
                    num_handles, gdi_objects, user_objects
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                ''',
                rows,
            )
            conn.commit()
        return len(rows)


