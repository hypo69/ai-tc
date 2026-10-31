# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry Sqlite - TelemetryAuditWriterMixin
# =============================================================================
# Description:
#   Миксин записи аудитов и событий безопасности (брандмауэр, службы, Defender,
#   ПО, питание, утечки и аудит процессов, история апгрейдов железа и Live Stream)
#   в 12 консолидированных таблиц SQLite.
#
# File: writer_audits.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry.sqlite
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-20 20:20:00
# =============================================================================

from __future__ import annotations

"""Миксин записи аудитов, ПО, безопасности, питания и жизненного цикла процессов в 12 базовых таблиц."""

import hashlib
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .delta_inventory import DeltaInventory

try:
    from logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class TelemetryAuditWriterMixin:
    """Миксин записи аудитов и событий безопасности в 12 консолидированных таблиц."""

    def save_event_log_snapshot(
        self,
        snapshot_id: str,
        channels: List[Any],
        entries: List[Any],
        intelligence_profiles: Optional[List[Any]] = None,
    ) -> int:
        """Сохранение снимка каналов и записей журналов в БД телеметрии отключено."""
        logger.debug("[TelemetryAuditWriterMixin] Пропуск записи журналов в БД телеметрии.")
        return 0

    def save_firewall_snapshot(self, snapshot_id: str, profiles: Any, rules: List[Any]) -> int:
        """Синхронизация профилей и правил брандмауэра в Change-Only инвентаризации."""
        if self._cm.read_only:
            return 0
        p = profiles if isinstance(profiles, dict) else (profiles.model_dump() if hasattr(profiles, "model_dump") else vars(profiles))
        profile_attrs = {
            "domain_enabled": int(bool(p.get("domain_enabled", True))),
            "private_enabled": int(bool(p.get("private_enabled", True))),
            "public_enabled": int(bool(p.get("public_enabled", True))),
            "domain_default_inbound": p.get("domain_default_inbound", "Block"),
            "private_default_inbound": p.get("private_default_inbound", "Block"),
            "public_default_inbound": p.get("public_default_inbound", "Block"),
            "stealth_mode_enabled": int(bool(p.get("stealth_mode_enabled", True))),
        }

        rule_items: Dict[str, Dict[str, Any]] = {}
        for r in rules:
            d = r if isinstance(r, dict) else (r.model_dump() if hasattr(r, "model_dump") else vars(r))
            attrs = {
                "name": d.get("name") or d.get("rule_name", ""),
                "display_name": d.get("display_name") or d.get("name", ""),
                "direction": d.get("direction", "Inbound"),
                "action": d.get("action", "Allow"),
                "enabled": int(bool(d.get("enabled", True))),
                "protocol": d.get("protocol", "Any"),
                "local_port": str(d.get("local_port", "") or ""),
                "remote_port": str(d.get("remote_port", "") or ""),
                "program_path": d.get("program_path") or d.get("program", "") or "",
                "profile_mask": int(d.get("profile_mask", 0) or 0),
            }
            key = "|".join(str(attrs[f]) for f in ("direction", "name", "protocol", "local_port", "remote_port", "program_path"))
            rule_items[key] = attrs

        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            s_prof = DeltaInventory.sync(cursor, "firewall_profiles", {"profiles": profile_attrs})
            s_rules = DeltaInventory.sync(cursor, "firewall_rules", rule_items)
            conn.commit()
        changed = sum(s_prof.values()) + sum(s_rules.values())
        if changed:
            logger.info(f"Брандмауэр [{snapshot_id}]: дельты правил {s_rules}, профилей {s_prof}")
        return changed

    def update_firewall_rule_state(self, rule_name: str, enabled: bool) -> bool:
        """Фиксирует изменение состояния правила брандмауэра как дельту в инвентаризации."""
        if self._cm.read_only:
            return False
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            keys = [r["entity_key"] for r in DeltaInventory.get_active(cursor, "firewall_rules") if r.get("name") == rule_name]
            for k in keys:
                DeltaInventory.patch(cursor, "firewall_rules", k, {"enabled": int(bool(enabled))})
            conn.commit()
            return bool(keys)

    def save_services_snapshot(self, snapshot_id: str, services: List[Any]) -> int:
        """Синхронизация состояния служб Windows в Change-Only инвентаризации."""
        if self._cm.read_only or not services:
            return 0
        items: Dict[str, Dict[str, Any]] = {}
        for s in services:
            d = s if isinstance(s, dict) else (s.model_dump() if hasattr(s, "model_dump") else vars(s))
            name = d.get("name") or d.get("service_name", "")
            items[name] = {
                "name": name,
                "display_name": d.get("display_name"),
                "status": d.get("state") or d.get("status", "STOPPED"),
                "startup_type": d.get("start_type") or d.get("startup_type", "Manual"),
                "pid": int(d.get("pid", 0) or 0) if d.get("pid") else None,
                "binpath": d.get("binary_path") or d.get("binpath", ""),
                "user_account": d.get("account") or d.get("user_account", ""),
                "is_orphaned": int(bool(d.get("is_orphaned", False))),
            }
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            stats = DeltaInventory.sync(cursor, "services", items)
            conn.commit()
        changed = sum(stats.values())
        if changed:
            logger.info(f"Службы [{snapshot_id}]: дельты {stats}")
        return changed

    def record_service_change(
        self,
        service_name: str,
        display_name: str,
        action: str,
        old_state: Optional[str] = None,
        new_state: Optional[str] = None,
        performed_by: str = "SYSTEM",
        details: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Фиксация события изменения состояния службы в таблицу inventory_changes."""
        if self._cm.read_only:
            return 0
        now_dt = datetime.now(timezone.utc)
        ts_str = now_dt.isoformat()
        created_at = now_dt.timestamp()
        diff_payload = {
            "timestamp": ts_str,
            "service_name": service_name,
            "display_name": display_name,
            "action": action,
            "old_state": old_state,
            "new_state": new_state,
            "performed_by": performed_by,
            "details": details,
            "details_json": json.dumps(details, ensure_ascii=False) if details else None,
        }
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                INSERT INTO inventory_changes (
                    timestamp, created_at, domain, entity_key, change_type, diff_json
                ) VALUES (?, ?, 'service_change_events', ?, ?, ?)
                ''',
                (
                    ts_str,
                    created_at,
                    service_name,
                    action,
                    json.dumps(diff_payload, ensure_ascii=False),
                ),
            )
            conn.commit()
            return cursor.lastrowid or 0

    def save_throttling_snapshot(
        self,
        snapshot_id: str,
        throttling_data: Any,
        thermal_zones: Optional[List[Any]] = None,
    ) -> int:
        """Сохранение снимка троттлинга процессора и ACPI термических зон в sensor_polls."""
        if self._cm.read_only:
            return 0
        now_dt = datetime.now(timezone.utc)
        ts_str = now_dt.isoformat()
        created_at = now_dt.timestamp()

        t = throttling_data if isinstance(throttling_data, dict) else (throttling_data.model_dump() if hasattr(throttling_data, "model_dump") else vars(throttling_data))
        zones_list = []
        if thermal_zones:
            for z in thermal_zones:
                zd = z if isinstance(z, dict) else (z.model_dump() if hasattr(z, "model_dump") else vars(z))
                zones_list.append({
                    "zone_name": zd.get("zone_name") or zd.get("name", "ThermalZone"),
                    "temperature_c": float(zd.get("temperature_c", 0.0) or 0.0),
                    "critical_limit_c": float(zd.get("critical_limit_c", 100.0) or 100.0) if zd.get("critical_limit_c") is not None else None,
                    "throttling_limit_c": float(zd.get("throttling_limit_c", 90.0) or 90.0) if zd.get("throttling_limit_c") is not None else None,
                    "sensor_provider": zd.get("sensor_provider", "ACPI"),
                })

        payload = {
            "snapshot_id": snapshot_id,
            "timestamp": ts_str,
            "prochot_active": int(bool(t.get("prochot_active", False))),
            "pl1_limit_watts": float(t.get("pl1_limit_watts", 0.0) or 0.0) if t.get("pl1_limit_watts") is not None else None,
            "pl2_limit_watts": float(t.get("pl2_limit_watts", 0.0) or 0.0) if t.get("pl2_limit_watts") is not None else None,
            "current_power_watts": float(t.get("current_power_watts", 0.0) or 0.0) if t.get("current_power_watts") is not None else None,
            "max_core_temp_c": float(t.get("max_core_temp_c", 0.0) or 0.0) if t.get("max_core_temp_c") is not None else None,
            "package_temp_c": float(t.get("package_temp_c", 0.0) or 0.0) if t.get("package_temp_c") is not None else None,
            "dpc_latency_us": int(t.get("dpc_latency_us", 0) or 0),
            "isr_latency_us": int(t.get("isr_latency_us", 0) or 0),
            "throttling_reasons": t.get("throttling_reasons") or t.get("reasons", []),
            "throttling_reasons_json": json.dumps(t.get("throttling_reasons") or t.get("reasons", []), ensure_ascii=False),
            "thermal_zones": zones_list,
        }
        val = float(payload.get("package_temp_c") or payload.get("max_core_temp_c") or 0.0)

        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                INSERT INTO sensor_polls (
                    sensor_id, timestamp, created_at, hardware_name, hardware_type,
                    sensor_category, sensor_type, sensor_name, value, value_numeric,
                    unit, status, raw_json
                ) VALUES ('cpu_throttling', ?, ?, 'CPU', 'cpu', 'throttling', 'Temperature', 'CPU Throttling', ?, ?, 'C', ?, ?);
                ''',
                (
                    ts_str,
                    created_at,
                    val,
                    val,
                    "THROTTLED" if payload["prochot_active"] else "OK",
                    json.dumps(payload, ensure_ascii=False),
                ),
            )
            conn.commit()
            return 1 + len(zones_list)

    def save_forensics_snapshot(self, snapshot_id: str, forensics_data: Any) -> int:
        """Сохранение снимка поведенческой форензики в Change-Only инвентаризацию."""
        if self._cm.read_only:
            return 0
        now_dt = datetime.now(timezone.utc)
        ts_str = now_dt.isoformat()
        created_at = now_dt.timestamp()

        f = forensics_data if isinstance(forensics_data, dict) else (forensics_data.model_dump() if hasattr(forensics_data, "model_dump") else vars(forensics_data))
        payload = {
            "snapshot_id": snapshot_id,
            "timestamp": ts_str,
            "created_at": created_at,
            "foreground_window_title": f.get("foreground_window_title") or f.get("active_window_title", ""),
            "foreground_process_name": f.get("foreground_process_name") or f.get("active_process_name", ""),
            "foreground_pid": int(f.get("foreground_pid", 0) or f.get("active_pid", 0) or 0),
            "user_idle_seconds": int(f.get("user_idle_seconds", 0) or f.get("idle_seconds", 0) or 0),
            "camera_active_apps": f.get("camera_active_apps") or f.get("camera_apps", []),
            "microphone_active_apps": f.get("microphone_active_apps") or f.get("microphone_apps", []),
            "userassist_top_apps": f.get("userassist_top_apps") or f.get("userassist_apps", []),
        }
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            DeltaInventory.patch(cursor, "forensics", snapshot_id, payload)
            conn.commit()
            return 1

    def save_process_leak_snapshot(
        self,
        snapshot_id: str,
        total_processes: Any,
        suspicious_count: int = 0,
        leak_items: Optional[List[Any]] = None,
    ) -> int:
        """Сохранение снимка аудита утечек ресурсов процессов в process_snapshots (sample_type='leak')."""
        if self._cm.read_only:
            return 0
        now_dt = datetime.now(timezone.utc)
        ts_str = now_dt.isoformat()
        created_at = now_dt.timestamp()

        if hasattr(total_processes, "model_dump") or (isinstance(total_processes, dict) and "total_processes" in total_processes):
            rep_dict = total_processes.model_dump() if hasattr(total_processes, "model_dump") else total_processes
            tot_proc = int(rep_dict.get("total_processes", 0))
            susp_cnt = int(rep_dict.get("suspicious_count", 0))
            items_list = rep_dict.get("all_processes") or rep_dict.get("top_handle_hogs") or []
        else:
            tot_proc = int(total_processes or 0)
            susp_cnt = int(suspicious_count or 0)
            items_list = leak_items or []

        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            for it in items_list:
                d = it if isinstance(it, dict) else (it.model_dump() if hasattr(it, "model_dump") else vars(it))
                ws_mb = float(d.get("working_set_mb", 0.0) or d.get("memory_mb", 0.0) or 0.0)
                reasons = d.get("leak_risk_reasons") or d.get("reasons", [])
                raw_meta = {
                    "snapshot_id": snapshot_id,
                    "total_processes": tot_proc,
                    "suspicious_count": susp_cnt,
                    "leak_risk_reasons": reasons,
                }
                cursor.execute(
                    '''
                    INSERT INTO process_snapshots (
                        sample_type, instance_id, timestamp, created_at, pid, name,
                        num_handles, gdi_objects, user_objects, page_faults,
                        working_set_mb, memory_mb, leak_risk_score, raw_json
                    ) VALUES ('leak', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    ''',
                    (
                        str(snapshot_id),
                        ts_str,
                        created_at,
                        int(d.get("pid", 0) or 0),
                        d.get("name") or d.get("process_name", ""),
                        int(d.get("handles_count", 0) or d.get("num_handles", 0) or 0),
                        int(d.get("gdi_objects", 0) or 0),
                        int(d.get("user_objects", 0) or 0),
                        int(d.get("page_faults", 0) or 0),
                        ws_mb,
                        ws_mb,
                        d.get("leak_risk_score", "LOW"),
                        json.dumps(raw_meta, ensure_ascii=False),
                    ),
                )
            conn.commit()

            # Автоматическая ротация: сохранение последних 5 срезов утечек для предотвращения разрастания БД
            try:
                cursor.execute(
                    '''
                    DELETE FROM process_snapshots
                    WHERE sample_type = 'leak' AND instance_id NOT IN (
                        SELECT instance_id FROM (
                            SELECT DISTINCT instance_id, MAX(id) as max_id
                            FROM process_snapshots
                            WHERE sample_type = 'leak'
                            GROUP BY instance_id
                            ORDER BY max_id DESC
                            LIMIT 5
                        )
                    );
                    '''
                )
                conn.commit()
            except Exception:
                pass

            return len(items_list) + 1

    def save_defender_snapshot(
        self,
        snapshot_id: str,
        defender_status: Any,
        exclusions: Optional[List[Any]] = None,
        asr_rules: Optional[List[Any]] = None,
        threats: Optional[List[Any]] = None,
    ) -> int:
        """Сохранение снимка состояния Защитника Windows, исключений, ASR и угроз."""
        if self._cm.read_only:
            return 0
        now_dt = datetime.now(timezone.utc)
        ts_str = now_dt.isoformat()
        created_at = now_dt.timestamp()

        s = defender_status if isinstance(defender_status, dict) else (defender_status.model_dump() if hasattr(defender_status, "model_dump") else vars(defender_status))
        status_attrs = {
            "snapshot_id": snapshot_id,
            "timestamp": ts_str,
            "real_time_protection_enabled": int(bool(s.get("real_time_protection_enabled", True))),
            "cloud_protection_enabled": int(bool(s.get("cloud_protection_enabled", True))),
            "behavior_monitoring_enabled": int(bool(s.get("behavior_monitoring_enabled", True))),
            "tamper_protection_enabled": int(bool(s.get("tamper_protection_enabled", True))),
            "pua_protection_enabled": int(bool(s.get("pua_protection_enabled", True))),
            "antivirus_enabled": int(bool(s.get("antivirus_enabled", True))),
            "antispyware_enabled": int(bool(s.get("antispyware_enabled", True))),
            "engine_version": s.get("engine_version", ""),
            "av_signature_version": s.get("av_signature_version") or s.get("signature_version", ""),
            "last_quick_scan_datetime": s.get("last_quick_scan_datetime"),
            "last_full_scan_datetime": s.get("last_full_scan_datetime"),
            "security_score": int(s.get("security_score", 100) or 100),
            "cfa_state": int(s.get("cfa_state", 0) or 0),
            "raw_status_json": json.dumps(s, ensure_ascii=False, default=str) if isinstance(s, dict) else None,
        }

        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            DeltaInventory.sync(cursor, "defender_status", {"status": status_attrs})

            if exclusions is not None:
                exc_map: Dict[str, Dict[str, Any]] = {}
                for exc in exclusions:
                    d = exc if isinstance(exc, dict) else (exc.model_dump() if hasattr(exc, "model_dump") else vars(exc))
                    et = d.get("type") or d.get("exclusion_type", "path")
                    ev = d.get("value") or d.get("exclusion_value", "")
                    exc_map[f"{et}:{ev}"] = {
                        "exclusion_type": et,
                        "exclusion_value": ev,
                        "risk_level": d.get("risk_level", "SAFE"),
                    }
                DeltaInventory.sync(cursor, "defender_exclusions", exc_map)

            if asr_rules is not None:
                asr_map: Dict[str, Dict[str, Any]] = {}
                for asr in asr_rules:
                    d = asr if isinstance(asr, dict) else (asr.model_dump() if hasattr(asr, "model_dump") else vars(asr))
                    guid = d.get("guid") or d.get("rule_guid", "")
                    asr_map[guid or d.get("name", "rule")] = {
                        "rule_guid": guid,
                        "rule_name": d.get("name") or d.get("rule_name", ""),
                        "rule_action": d.get("action") or d.get("rule_action", "Block"),
                    }
                DeltaInventory.sync(cursor, "defender_asr", asr_map)

            if threats:
                for th in threats:
                    d = th if isinstance(th, dict) else (th.model_dump() if hasattr(th, "model_dump") else vars(th))
                    th_id = str(d.get("threat_id") or d.get("id", ""))
                    th_name = str(d.get("threat_name") or d.get("name", "Threat"))
                    details = {
                        "threat_id": th_id,
                        "threat_name": th_name,
                        "severity": d.get("severity", "High"),
                        "category": d.get("category", "Trojan"),
                        "resources": d.get("resources", []),
                        "detection_time": d.get("detection_time"),
                    }
                    inc_id = str(d.get("incident_id") or f"def_{int(created_at * 1000)}_{uuid.uuid4().hex[:8]}")
                    cursor.execute(
                        '''
                        INSERT INTO incidents (
                            incident_id, timestamp, created_at, domain, trigger_type, severity,
                            title, message, details_json
                        ) VALUES (?, ?, ?, 'defender_threat', ?, ?, ?, ?, ?);
                        ''',
                        (
                            inc_id,
                            str(d.get("detection_time") or ts_str),
                            created_at,
                            str(d.get("category", "Trojan")),
                            str(d.get("severity", "High")),
                            th_name,
                            f"Defender Threat: {th_name}",
                            json.dumps(details, ensure_ascii=False, default=str),
                        ),
                    )

            conn.commit()
            return 1 + (len(exclusions) if exclusions else 0)

    def save_process_network_snapshot(self, snapshot_id: str, network_items: List[Any]) -> int:
        """Сохранение снимка сетевой активности процессов в process_snapshots (sample_type='network')."""
        if self._cm.read_only or not network_items:
            return 0
        now_dt = datetime.now(timezone.utc)
        ts_str = now_dt.isoformat()
        created_at = now_dt.timestamp()

        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            for it in network_items:
                d = it if isinstance(it, dict) else (it.model_dump() if hasattr(it, "model_dump") else vars(it))
                proc_name = d.get("process_name") or d.get("name", "")
                sock_entry = {
                    "local_address": d.get("local_address", ""),
                    "remote_address": d.get("remote_address", ""),
                    "protocol": d.get("protocol", "TCP"),
                    "status": d.get("status", "ESTABLISHED"),
                    "service_type": d.get("service_type", "Internet"),
                    "sent_kb": float(d.get("sent_kb", 0.0) or 0.0),
                    "recv_kb": float(d.get("recv_kb", 0.0) or 0.0),
                    "read_speed_kbs": float(d.get("read_speed_kbs", 0.0) or 0.0),
                    "write_speed_kbs": float(d.get("write_speed_kbs", 0.0) or 0.0),
                }
                cursor.execute(
                    '''
                    INSERT INTO process_snapshots (
                        sample_type, instance_id, timestamp, created_at, pid, name,
                        status, read_bytes_sec, write_bytes_sec, sockets_json, raw_json
                    ) VALUES ('network', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    ''',
                    (
                        str(snapshot_id),
                        ts_str,
                        created_at,
                        int(d.get("pid", 0) or 0),
                        proc_name,
                        sock_entry["status"],
                        sock_entry["read_speed_kbs"],
                        sock_entry["write_speed_kbs"],
                        json.dumps([sock_entry], ensure_ascii=False),
                        json.dumps(sock_entry, ensure_ascii=False),
                    ),
                )
            conn.commit()
            return len(network_items)

    def save_software_inventory(
        self,
        apps: List[Any],
        storage_locations: Optional[List[Any]] = None,
        config_files: Optional[List[Any]] = None,
        ai_research: Optional[List[Any]] = None,
    ) -> int:
        """Сохранение инвентаря установленного ПО в Change-Only таблицу inventory_state (domain='software')."""
        if self._cm.read_only or not apps:
            return 0
        now_dt = datetime.now(timezone.utc)
        ts_str = now_dt.isoformat()

        locs_by_app: Dict[str, list] = {}
        for loc in (storage_locations or []):
            d = loc if isinstance(loc, dict) else (loc.model_dump() if hasattr(loc, "model_dump") else vars(loc))
            locs_by_app.setdefault(d.get("app_id", ""), []).append(d)

        cfgs_by_app: Dict[str, list] = {}
        for cf in (config_files or []):
            d = cf if isinstance(cf, dict) else (cf.model_dump() if hasattr(cf, "model_dump") else vars(cf))
            cfgs_by_app.setdefault(d.get("app_id", ""), []).append(d)

        ai_by_app: Dict[str, Any] = {}
        for ai in (ai_research or []):
            d = ai if isinstance(ai, dict) else (ai.model_dump() if hasattr(ai, "model_dump") else vars(ai))
            ai_by_app[d.get("app_id", "")] = d

        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT entity_key, attrs_json, first_seen FROM inventory_state WHERE domain = 'software';")
            existing_map: Dict[str, Dict[str, Any]] = {}
            for r in cursor.fetchall():
                try:
                    existing_map[r[0]] = {"attrs": json.loads(r[1]), "first_seen": r[2]}
                except Exception:
                    pass

            for app in apps:
                d = app if isinstance(app, dict) else (
                    app.to_dict() if hasattr(app, "to_dict") and callable(app.to_dict)
                    else (app.model_dump() if hasattr(app, "model_dump") and callable(app.model_dump) else vars(app))
                )
                app_id = d.get("app_id") or d.get("id") or d.get("name", "")
                if not app_id and hasattr(app, "name"):
                    app_id = getattr(app, "name")
                if not app_id:
                    app_id = d.get("display_name", "")

                prev_entry = existing_map.get(app_id, {})
                prev_attrs = prev_entry.get("attrs", {})
                first_seen = prev_entry.get("first_seen") or prev_attrs.get("first_seen") or ts_str

                locs = locs_by_app.get(app_id)
                cfgs = cfgs_by_app.get(app_id)
                ai_data = ai_by_app.get(app_id)

                locs_json = json.dumps(locs, ensure_ascii=False, default=str) if locs else prev_attrs.get("storage_locations_json")
                cfgs_json = json.dumps(cfgs, ensure_ascii=False, default=str) if cfgs else prev_attrs.get("config_files_json")
                ai_json = json.dumps(ai_data, ensure_ascii=False, default=str) if ai_data else prev_attrs.get("ai_research_json")

                uninstall_string = d.get("uninstall_string") or getattr(app, "uninstall_string", "") or prev_attrs.get("uninstall_string", "")
                size_bytes = d.get("size_bytes") or getattr(app, "size_bytes", 0)
                if not size_bytes and "size_mb" in d:
                    try:
                        size_bytes = int(float(d["size_mb"]) * 1024 * 1024)
                    except (ValueError, TypeError):
                        size_bytes = 0
                if not size_bytes:
                    size_bytes = int(prev_attrs.get("size_bytes") or 0)

                cat_val = d.get("category") or getattr(app, "category", "")
                category_str = (cat_val.value if hasattr(cat_val, "value") else str(cat_val or "")) or prev_attrs.get("category", "")
                purpose_desc = d.get("purpose_description") or getattr(app, "purpose_description", "") or prev_attrs.get("purpose_description", "")
                reg_key = d.get("registry_key") or getattr(app, "registry_key", "") or prev_attrs.get("registry_key", "")

                exec_info = d.get("execution_info") or getattr(app, "execution_info", None)
                exec_dict = None
                last_run_iso = prev_attrs.get("last_run_time")
                run_count = int(prev_attrs.get("run_count") or 0)
                if exec_info:
                    if isinstance(exec_info, dict):
                        exec_dict = exec_info
                    elif hasattr(exec_info, "to_dict") and callable(exec_info.to_dict):
                        exec_dict = exec_info.to_dict()
                    else:
                        exec_dict = vars(exec_info)
                    last_run = exec_dict.get("last_run_time")
                    if last_run:
                        last_run_iso = last_run.isoformat() if hasattr(last_run, "isoformat") else str(last_run)
                    new_rc = int(exec_dict.get("run_count", 0) or 0)
                    if new_rc > 0:
                        run_count = new_rc

                exec_json = json.dumps(exec_dict, ensure_ascii=False, default=str) if exec_dict else prev_attrs.get("execution_info_json")

                app_record = {
                    "app_id": app_id,
                    "display_name": d.get("display_name") or d.get("name", app_id),
                    "version": d.get("version", ""),
                    "publisher": d.get("publisher", ""),
                    "install_date": d.get("install_date", ""),
                    "install_location": d.get("install_location") or d.get("path", ""),
                    "architecture": d.get("architecture", "x64"),
                    "is_system_component": int(bool(d.get("is_system_component", False))),
                    "uninstall_string": uninstall_string,
                    "size_bytes": int(size_bytes or 0),
                    "category": category_str,
                    "purpose_description": purpose_desc,
                    "registry_key": reg_key,
                    "execution_info_json": exec_json,
                    "last_run_time": last_run_iso,
                    "run_count": run_count,
                    "storage_locations_json": locs_json,
                    "config_files_json": cfgs_json,
                    "ai_research_json": ai_json,
                    "first_seen": first_seen,
                    "last_scanned_at": ts_str,
                }
                attr_json = json.dumps(app_record, ensure_ascii=False, sort_keys=True, default=str)
                s_hash = hashlib.md5(attr_json.encode("utf-8")).hexdigest()
                cursor.execute(
                    '''
                    INSERT INTO inventory_state (
                        domain, entity_key, attrs_hash, attrs_json, first_seen, last_changed, removed_at
                    ) VALUES ('software', ?, ?, ?, ?, ?, NULL)
                    ON CONFLICT(domain, entity_key) DO UPDATE SET
                        attrs_hash = excluded.attrs_hash,
                        attrs_json = excluded.attrs_json,
                        last_changed = excluded.last_changed,
                        removed_at = NULL;
                    ''',
                    (app_id, s_hash, attr_json, first_seen, ts_str),
                )

            conn.commit()
            return len(apps)

    def save_software_audit_report(self, report: Any) -> int:
        """Сохранение сводного аналитического отчета аудита ПО в inventory_state (domain='software_audit')."""
        if self._cm.read_only or not report:
            return 0
        now_dt = datetime.now(timezone.utc)
        ts_str = now_dt.isoformat()
        now_epoch = now_dt.timestamp()

        rep_dict = report if isinstance(report, dict) else (
            report.to_dict() if hasattr(report, "to_dict") and callable(report.to_dict) else vars(report)
        )
        report_id = str(rep_dict.get("report_id") or f"sw_audit_{int(now_epoch * 1000)}")
        timestamp = rep_dict.get("timestamp")
        if hasattr(timestamp, "isoformat"):
            timestamp = timestamp.isoformat()
        timestamp = str(timestamp or ts_str)
        total_apps = int(rep_dict.get("total_apps") or 0)
        active_apps = int(rep_dict.get("active_apps_count") or getattr(report, "active_apps_count", 0) or 0)
        unused_apps = int(rep_dict.get("unused_apps_count") or getattr(report, "unused_apps_count", 0) or 0)
        cats_json = json.dumps(getattr(report, "categories_breakdown", None) or rep_dict.get("categories_breakdown") or {}, ensure_ascii=False)
        top_apps = getattr(report, "top_launched", None) or rep_dict.get("top_launched") or []
        rec_apps = getattr(report, "recently_launched", None) or rep_dict.get("recently_launched") or []
        dormant_apps = getattr(report, "never_launched_or_dormant", None) or rep_dict.get("never_launched_or_dormant") or []

        top_json = json.dumps([a.to_dict() if hasattr(a, "to_dict") else a for a in top_apps], ensure_ascii=False, default=str)
        rec_json = json.dumps([a.to_dict() if hasattr(a, "to_dict") else a for a in rec_apps], ensure_ascii=False, default=str)
        dormant_json = json.dumps([a.to_dict() if hasattr(a, "to_dict") else a for a in dormant_apps], ensure_ascii=False, default=str)
        raw_json = json.dumps(rep_dict, ensure_ascii=False, default=str)

        payload = {
            "report_id": report_id,
            "timestamp": timestamp,
            "created_at": now_epoch,
            "total_apps": total_apps,
            "active_apps_count": active_apps,
            "unused_apps_count": unused_apps,
            "categories_breakdown_json": cats_json,
            "top_launched_json": top_json,
            "recently_launched_json": rec_json,
            "never_launched_or_dormant_json": dormant_json,
            "raw_json": raw_json,
        }

        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            DeltaInventory.patch(cursor, "software_audit", report_id, payload)
            conn.commit()

        apps = getattr(report, "apps", None) or rep_dict.get("apps") or []
        if apps:
            self.save_software_inventory(apps)

        return total_apps

    def save_software_scanner_report(self, report: Any) -> int:
        """Сохранение отчета глубокого сканирования ПО, спящих программ и сирот в inventory_state (domain='software_scanner')."""
        if self._cm.read_only or not report:
            return 0
        now_dt = datetime.now(timezone.utc)
        ts_str = now_dt.isoformat()
        now_epoch = now_dt.timestamp()

        try:
            from apps.windows.sdk.software_scanner.report import ReportFormatter
            if hasattr(report, "scan_id") and not isinstance(report, dict):
                rep_dict = ReportFormatter.to_dict(report)
            elif isinstance(report, dict):
                rep_dict = report
            elif hasattr(report, "to_dict") and callable(report.to_dict):
                rep_dict = report.to_dict()
            else:
                rep_dict = vars(report)
        except Exception:
            rep_dict = report if isinstance(report, dict) else vars(report)

        report_id = str(rep_dict.get("scan_id") or f"sw_scan_{int(now_epoch * 1000)}")
        stats = rep_dict.get("stats") or {}
        inventory = rep_dict.get("inventory") or []
        orphan_items = rep_dict.get("orphan_items") or []

        payload = {
            "report_id": report_id,
            "timestamp": ts_str,
            "created_at": now_epoch,
            "stats_json": json.dumps(stats, ensure_ascii=False, default=str),
            "inventory_json": json.dumps(inventory, ensure_ascii=False, default=str),
            "orphan_items_json": json.dumps(orphan_items, ensure_ascii=False, default=str),
            "raw_json": json.dumps(rep_dict, ensure_ascii=False, default=str),
        }

        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            DeltaInventory.patch(cursor, "software_scanner", "latest", payload)
            DeltaInventory.patch(cursor, "software_scanner", report_id, payload)
            conn.commit()

        return len(inventory)

    def save_software_network_snapshots(self, snapshot_id: str, net_items: List[Any]) -> int:
        """Сохранение снимков сетевой активности ПО (таблица консолидирована)."""
        return 0

    def save_security_events(
        self,
        events: List[Any],
        save_raw: bool = False,
        raw_events: Optional[List[Any]] = None,
    ) -> int:
        """Сохраняет список нормализованных событий журнала безопасности в таблицу incidents (domain='security_event')."""
        if self._cm.read_only or not events:
            return 0

        raw_by_rec: Dict[int, str] = {}
        if save_raw and raw_events:
            for raw in raw_events:
                rd = raw if isinstance(raw, dict) else (raw.model_dump() if hasattr(raw, "model_dump") else vars(raw))
                raw_by_rec[int(rd.get("event_record_id", 0) or 0)] = str(rd.get("raw_xml", ""))

        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            for ev in events:
                d = ev if isinstance(ev, dict) else (ev.model_dump() if hasattr(ev, "model_dump") else vars(ev))
                rec_id = int(d.get("event_record_id", 0) or 0)
                ev_id = int(d.get("event_id", 0) or 0)
                ts_str = str(d.get("timestamp", ""))
                c_at = float(d.get("created_at", time.time()) or time.time())
                channel = str(d.get("channel", "Security"))
                level = str(d.get("level", "Information"))
                msg = str(d.get("message", ""))
                raw_xml = raw_by_rec.get(rec_id) or d.get("raw_xml")

                details = {
                    "event_record_id": rec_id,
                    "event_id": ev_id,
                    "timestamp": ts_str,
                    "created_at": c_at,
                    "computer": str(d.get("computer", "")),
                    "channel": channel,
                    "level": level,
                    "subject_user": str(d.get("subject_user", "")),
                    "subject_domain": str(d.get("subject_domain", "")),
                    "subject_sid": str(d.get("subject_sid", "")),
                    "target_user": str(d.get("target_user", "")),
                    "target_domain": str(d.get("target_domain", "")),
                    "target_sid": str(d.get("target_sid", "")),
                    "process_id": int(d.get("process_id", 0) or 0),
                    "process_name": str(d.get("process_name", "")),
                    "parent_process_id": int(d.get("parent_process_id", 0) or 0),
                    "parent_process_name": str(d.get("parent_process_name", "")),
                    "command_line": str(d.get("command_line", "")),
                    "logon_id": str(d.get("logon_id", "")),
                    "logon_type": d.get("logon_type"),
                    "elevated_token": d.get("elevated_token"),
                    "source_ip": str(d.get("source_ip", "")),
                    "source_port": d.get("source_port"),
                    "object_name": str(d.get("object_name", "")),
                    "status_code": str(d.get("status_code", "")),
                    "message": msg,
                    "event_data": d.get("event_data", {}),
                    "ingested_at": str(d.get("ingested_at", datetime.now(timezone.utc).isoformat())),
                }
                rec_id = d.get("record_id") or d.get("event_record_id")
                ev_id = d.get("event_id", 0)
                inc_id = str(d.get("incident_id") or f"sec_{channel}_{rec_id or int(c_at * 1000)}_{uuid.uuid4().hex[:8]}")
                cursor.execute(
                    '''
                    INSERT INTO incidents (
                        incident_id, timestamp, created_at, domain, trigger_type, severity,
                        title, channel, event_id, event_record_id, message,
                        details_json, raw_xml
                    ) VALUES (?, ?, ?, 'security_event', ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    ''',
                    (
                        inc_id,
                        ts_str,
                        c_at,
                        f"EventID:{ev_id}",
                        level,
                        f"Security Event {ev_id}",
                        channel,
                        ev_id,
                        rec_id,
                        msg,
                        json.dumps(details, ensure_ascii=False, default=str),
                        raw_xml,
                    ),
                )

            conn.commit()
            return len(events)

    def save_security_bookmark(
        self,
        channel: str,
        last_record_id: int,
        bookmark_xml: Optional[str] = None,
        last_timestamp: str = "",
    ) -> None:
        """Сохраняет или обновляет состояние закладки инкрементального сбора в inventory_state."""
        if self._cm.read_only:
            return
        now_epoch = time.time()
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            existing = DeltaInventory.get_active(cursor, "security_bookmarks")
            prev = next((r for r in existing if r.get("channel") == channel), {})
            payload = {
                "channel": channel,
                "last_record_id": int(last_record_id or 0),
                "bookmark_xml": bookmark_xml if bookmark_xml is not None else prev.get("bookmark_xml"),
                "last_timestamp": last_timestamp,
                "updated_at": now_epoch,
            }
            DeltaInventory.patch(cursor, "security_bookmarks", channel, payload)
            conn.commit()

    def save_power_events(self, events: List[Any]) -> int:
        """Сохраняет пакет событий питания в единую таблицу power_sessions (record_type='power_event')."""
        if not events or self._cm.read_only:
            return 0

        now_epoch = time.time()
        saved = 0
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            for ev in events:
                if hasattr(ev, "model_dump"):
                    d = ev.model_dump()
                elif isinstance(ev, dict):
                    d = ev
                else:
                    continue

                eid = int(d.get("event_id", 0))
                provider = str(d.get("provider") or "")
                channel = str(d.get("channel") or "System")
                ts = str(d.get("timestamp") or "")
                c_at = float(d.get("created_at") or now_epoch)
                event_type = str(d.get("event_type") or "event")
                shutdown_type = str(d.get("shutdown_type") or event_type)
                sess_id = f"pev_{eid}_{ts}_{provider}"
                unexpected = 1 if d.get("unexpected") else 0
                bugcheck_params = d.get("bugcheck_params_json")
                if isinstance(bugcheck_params, (dict, list)):
                    bugcheck_params = json.dumps(bugcheck_params, ensure_ascii=False)
                details_json = d.get("details_json")
                if isinstance(details_json, (dict, list)):
                    details_json = json.dumps(details_json, ensure_ascii=False)

                cursor.execute(
                    '''
                    INSERT INTO power_sessions (
                        session_id, record_type, boot_time, boot_timestamp,
                        shutdown_type, classification, user, domain, process,
                        process_id, reason, reason_code, comment, unexpected_shutdown,
                        bugcheck_code, bugcheck_params_json, event_id, provider,
                        channel, details_json, raw_xml, created_at
                    ) VALUES (?, 'power_event', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(session_id) DO UPDATE SET
                        shutdown_type = excluded.shutdown_type,
                        classification = excluded.classification,
                        user = excluded.user,
                        domain = excluded.domain,
                        process = excluded.process,
                        process_id = excluded.process_id,
                        reason = excluded.reason,
                        reason_code = excluded.reason_code,
                        comment = excluded.comment,
                        unexpected_shutdown = excluded.unexpected_shutdown,
                        bugcheck_code = excluded.bugcheck_code,
                        bugcheck_params_json = excluded.bugcheck_params_json,
                        details_json = excluded.details_json,
                        raw_xml = excluded.raw_xml;
                    ''',
                    (
                        sess_id,
                        ts,
                        c_at,
                        shutdown_type,
                        event_type,
                        d.get("user"),
                        d.get("domain"),
                        d.get("process"),
                        d.get("process_id"),
                        d.get("reason"),
                        d.get("reason_code"),
                        d.get("comment"),
                        unexpected,
                        d.get("bugcheck_code"),
                        bugcheck_params,
                        eid,
                        provider,
                        channel,
                        details_json,
                        d.get("raw_xml"),
                        c_at,
                    ),
                )
                saved += 1

            conn.commit()
        return saved

    def save_power_sessions(self, sessions: List[Any]) -> int:
        """Сохраняет пакет реконструированных сессий питания в таблицу power_sessions."""
        if not sessions or self._cm.read_only:
            return 0

        now_epoch = time.time()
        saved = 0
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            for s in sessions:
                if hasattr(s, "model_dump"):
                    d = s.model_dump()
                elif isinstance(s, dict):
                    d = s
                else:
                    continue

                session_id = str(d.get("session_id") or "")
                if not session_id:
                    continue

                boot_time = str(d.get("boot_time") or "")
                boot_ts = float(d.get("boot_timestamp") or 0.0)
                shutdown_time = d.get("shutdown_time")
                shutdown_ts = float(d.get("shutdown_timestamp") or 0.0) if d.get("shutdown_timestamp") is not None else None
                uptime_sec = float(d.get("uptime_seconds") or 0.0)
                uptime_human = str(d.get("uptime_human") or "")
                shutdown_type = str(d.get("shutdown_type") or "Active")
                initiator = d.get("initiator")
                process = d.get("process")
                reason = d.get("reason")
                reason_code = d.get("reason_code")
                comment = d.get("comment")
                clean = 1 if d.get("clean_shutdown", True) else 0
                unexpected = 1 if d.get("unexpected_shutdown", False) else 0
                bugcheck = d.get("bugcheck")
                boot_eid = int(d.get("boot_event_id", 12))
                shutdown_eid = int(d.get("shutdown_event_id")) if d.get("shutdown_event_id") is not None else None

                initiator_chain = d.get("initiator_chain") or []
                chain_json = json.dumps(initiator_chain, ensure_ascii=False) if isinstance(initiator_chain, list) else str(initiator_chain)

                events = d.get("events") or []
                events_json = json.dumps(events, ensure_ascii=False) if isinstance(events, (list, dict)) else str(events)
                c_at = float(d.get("created_at") or now_epoch)

                cursor.execute(
                    '''
                    INSERT INTO power_sessions (
                        session_id, record_type, boot_time, boot_timestamp, shutdown_time, shutdown_timestamp,
                        uptime_seconds, uptime_human, shutdown_type, initiator, process,
                        reason, reason_code, comment, clean_shutdown, unexpected_shutdown,
                        bugcheck, boot_event_id, shutdown_event_id, initiator_chain_json,
                        events_json, created_at
                    ) VALUES (?, 'session', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(session_id) DO UPDATE SET
                        boot_time = excluded.boot_time,
                        boot_timestamp = excluded.boot_timestamp,
                        shutdown_time = excluded.shutdown_time,
                        shutdown_timestamp = excluded.shutdown_timestamp,
                        uptime_seconds = excluded.uptime_seconds,
                        uptime_human = excluded.uptime_human,
                        shutdown_type = excluded.shutdown_type,
                        initiator = excluded.initiator,
                        process = excluded.process,
                        reason = excluded.reason,
                        reason_code = excluded.reason_code,
                        comment = excluded.comment,
                        clean_shutdown = excluded.clean_shutdown,
                        unexpected_shutdown = excluded.unexpected_shutdown,
                        bugcheck = excluded.bugcheck,
                        boot_event_id = excluded.boot_event_id,
                        shutdown_event_id = excluded.shutdown_event_id,
                        initiator_chain_json = excluded.initiator_chain_json,
                        events_json = excluded.events_json,
                        created_at = excluded.created_at;
                    ''',
                    (
                        session_id, boot_time, boot_ts, shutdown_time, shutdown_ts,
                        uptime_sec, uptime_human, shutdown_type, initiator, process,
                        reason, reason_code, comment, clean, unexpected,
                        bugcheck, boot_eid, shutdown_eid, chain_json,
                        events_json, c_at,
                    ),
                )
                saved += 1

            conn.commit()
        return saved

    def save_process_audit_sample(self, sample: Any) -> Optional[int]:
        """Сохраняет снимок глубокого аудита процесса по PID в таблицу process_snapshots (sample_type='audit')."""
        data = sample.to_dict() if hasattr(sample, "to_dict") else dict(sample)
        pid = int(data.get("pid", 0))
        name = str(data.get("name", "unknown"))
        timestamp = str(data.get("timestamp") or datetime.now(timezone.utc).isoformat())
        created_at = float(data.get("created_at") or time.time())
        status = str(data.get("status", "running"))
        is_alive = 1 if data.get("is_alive", True) else 0
        creation_time = float(data.get("creation_time") or 0.0)
        exit_time = float(data.get("exit_time") or 0.0)
        num_handles = int(data.get("num_handles") or 0)
        executable = data.get("executable")
        cmdline = data.get("cmdline")
        username = data.get("username")

        cpu = data.get("cpu", {})
        cpu_percent = float(cpu.get("cpu_percent") if isinstance(cpu, dict) and "cpu_percent" in cpu else data.get("cpu_percent") or 0.0)
        user_time_sec = float(cpu.get("user_time_sec") or 0.0) if isinstance(cpu, dict) else 0.0
        kernel_time_sec = float(cpu.get("kernel_time_sec") or 0.0) if isinstance(cpu, dict) else 0.0
        total_cpu_time_sec = float(cpu.get("total_cpu_time_sec") or 0.0) if isinstance(cpu, dict) else 0.0
        num_threads = int((cpu.get("num_threads") if isinstance(cpu, dict) else None) or data.get("num_threads") or 1)
        vol_ctx = int(cpu.get("context_switches_voluntary") or 0) if isinstance(cpu, dict) else 0
        invol_ctx = int(cpu.get("context_switches_involuntary") or 0) if isinstance(cpu, dict) else 0
        total_ctx = int((cpu.get("total_context_switches") if isinstance(cpu, dict) else None) or (vol_ctx + invol_ctx))
        cpu_cycles = int(cpu.get("cpu_cycles") or 0) if isinstance(cpu, dict) else 0

        mem = data.get("memory", {})
        ws_mb = float((mem.get("working_set_mb") if isinstance(mem, dict) else None) or data.get("working_set_mb") or 0.0)
        peak_ws_mb = float((mem.get("peak_working_set_mb") if isinstance(mem, dict) else None) or 0.0)
        priv_mb = float((mem.get("private_mb") if isinstance(mem, dict) else None) or data.get("private_mb") or 0.0)
        commit_mb = float((mem.get("commit_size_mb") if isinstance(mem, dict) else None) or 0.0)
        page_faults = int((mem.get("page_faults") if isinstance(mem, dict) else None) or 0)

        io = data.get("io", {})
        r_ops = int((io.get("read_operations") if isinstance(io, dict) else None) or 0)
        w_ops = int((io.get("write_operations") if isinstance(io, dict) else None) or 0)
        r_bytes = int((io.get("read_bytes") if isinstance(io, dict) else None) or 0)
        w_bytes = int((io.get("write_bytes") if isinstance(io, dict) else None) or 0)
        r_bytes_sec = float((io.get("read_bytes_sec") if isinstance(io, dict) else None) or 0.0)
        w_bytes_sec = float((io.get("write_bytes_sec") if isinstance(io, dict) else None) or 0.0)
        open_files = (io.get("open_files") if isinstance(io, dict) else None) or []
        open_files_count = int((io.get("open_files_count") if isinstance(io, dict) else None) or len(open_files))
        open_files_json = json.dumps(open_files, ensure_ascii=False)

        net = data.get("network", {})
        tcp_count = int((net.get("tcp_connections_count") if isinstance(net, dict) else None) or 0)
        udp_count = int((net.get("udp_sockets_count") if isinstance(net, dict) else None) or 0)
        conns = (net.get("connections") if isinstance(net, dict) else None) or []
        conns_json = json.dumps(conns, ensure_ascii=False)

        raw_json = json.dumps(data, ensure_ascii=False, default=str)

        try:
            with self._cm.lock, self._cm.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    INSERT INTO process_snapshots (
                        sample_type, instance_id, pid, name, timestamp, created_at,
                        status, is_alive, creation_time, exit_time, num_handles,
                        executable, cmdline, username, cpu_percent, user_time_sec,
                        kernel_time_sec, total_cpu_time_sec, num_threads,
                        total_context_switches, cpu_cycles, memory_mb, working_set_mb,
                        peak_working_set_mb, private_mb, commit_size_mb, page_faults,
                        read_operations, write_operations, read_bytes, write_bytes,
                        read_bytes_sec, write_bytes_sec, open_files_count,
                        tcp_connections_count, udp_sockets_count, sockets_json,
                        open_files_json, raw_json
                    ) VALUES (
                        'audit', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    ''',
                    (
                        data.get("instance_id"),
                        pid, name, timestamp, created_at, status, is_alive,
                        creation_time, exit_time, num_handles, executable, cmdline, username,
                        cpu_percent, user_time_sec, kernel_time_sec, total_cpu_time_sec, num_threads,
                        total_ctx, cpu_cycles, ws_mb, ws_mb, peak_ws_mb,
                        priv_mb, commit_mb, page_faults, r_ops, w_ops,
                        r_bytes, w_bytes, r_bytes_sec, w_bytes_sec,
                        open_files_count, tcp_count, udp_count,
                        conns_json, open_files_json, raw_json,
                    ),
                )
                conn.commit()
                return cursor.lastrowid
        except Exception as ex:
            logger.debug(f"Ошибка сохранения снимка аудита процесса PID={pid}: {ex}")
            return None

    def upsert_process_lifecycle_session(self, session: Any) -> bool:
        """Сохраняет или обновляет запись жизненного цикла процесса по уникальному instance_id."""
        data = session.to_dict() if hasattr(session, "to_dict") else dict(session)
        inst_id = data.get("instance_id")
        if not inst_id:
            return False

        files_json = json.dumps(data.get("files_accessed", []), ensure_ascii=False)
        endpoints_json = json.dumps(data.get("remote_endpoints", []), ensure_ascii=False)
        raw_json = json.dumps(data, ensure_ascii=False, default=str)

        try:
            with self._cm.lock, self._cm.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    INSERT INTO process_lifecycle_sessions (
                        instance_id, pid, ppid, name, friendly_name, exe_path, binary_hash,
                        cmdline, username, parent_name, parent_exe, initiator_type,
                        status, created_at, created_ts, terminated_at, terminated_ts,
                        is_alive, lifetime_sec, exit_code,
                        cpu_time_user_sec, cpu_time_kernel_sec, cpu_time_total_sec, cpu_cycles,
                        peak_working_set_mb, peak_private_mb,
                        io_read_bytes, io_write_bytes, io_read_ops, io_write_ops,
                        files_accessed_json, remote_endpoints_json, raw_json
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    ON CONFLICT(instance_id) DO UPDATE SET
                        status = excluded.status,
                        terminated_at = excluded.terminated_at,
                        terminated_ts = excluded.terminated_ts,
                        is_alive = excluded.is_alive,
                        lifetime_sec = excluded.lifetime_sec,
                        exit_code = excluded.exit_code,
                        cpu_time_user_sec = excluded.cpu_time_user_sec,
                        cpu_time_kernel_sec = excluded.cpu_time_kernel_sec,
                        cpu_time_total_sec = excluded.cpu_time_total_sec,
                        cpu_cycles = excluded.cpu_cycles,
                        peak_working_set_mb = MAX(process_lifecycle_sessions.peak_working_set_mb, excluded.peak_working_set_mb),
                        peak_private_mb = MAX(process_lifecycle_sessions.peak_private_mb, excluded.peak_private_mb),
                        io_read_bytes = excluded.io_read_bytes,
                        io_write_bytes = excluded.io_write_bytes,
                        io_read_ops = excluded.io_read_ops,
                        io_write_ops = excluded.io_write_ops,
                        files_accessed_json = excluded.files_accessed_json,
                        remote_endpoints_json = excluded.remote_endpoints_json,
                        raw_json = excluded.raw_json;
                    ''',
                    (
                        str(inst_id),
                        int(data.get("pid") or 0),
                        int(data.get("ppid") or 0),
                        str(data.get("name") or "unknown"),
                        data.get("friendly_name"),
                        data.get("exe_path") or data.get("executable_path"),
                        data.get("binary_hash"),
                        data.get("cmdline") or data.get("command_line"),
                        data.get("username") or data.get("user_name"),
                        data.get("parent_name"),
                        data.get("parent_exe"),
                        str(data.get("initiator_type") or "unknown"),
                        str(data.get("status") or ("RUNNING" if data.get("is_alive", True) else "EXITED")),
                        str(data.get("created_at") or data.get("start_time") or ""),
                        float(data.get("created_ts") or time.time()),
                        data.get("terminated_at") or data.get("exit_time"),
                        data.get("terminated_ts"),
                        1 if data.get("is_alive", True) else 0,
                        float(data.get("lifetime_sec") or 0.0),
                        data.get("exit_code"),
                        float(data.get("cpu_time_user_sec") or 0.0),
                        float(data.get("cpu_time_kernel_sec") or 0.0),
                        float(data.get("cpu_time_total_sec") or 0.0),
                        data.get("cpu_cycles"),
                        float(data.get("peak_working_set_mb") or 0.0),
                        float(data.get("peak_private_mb") or 0.0),
                        int(data.get("io_read_bytes") or 0),
                        int(data.get("io_write_bytes") or 0),
                        int(data.get("io_read_ops") or 0),
                        int(data.get("io_write_ops") or 0),
                        files_json,
                        endpoints_json,
                        raw_json,
                    ),
                )
                conn.commit()
                return True
        except Exception as ex:
            logger.debug(f"Ошибка сохранения сессии процесса {inst_id}: {ex}")
            return False

    def save_hardware_config_change(
        self,
        component_type: str,
        change_type: str,
        component_name: str,
        old_config: Optional[Dict[str, Any]],
        new_config: Optional[Dict[str, Any]],
        summary: str,
        timestamp: Optional[str] = None,
        created_at: Optional[float] = None,
    ) -> int:
        """Сохраняет запись об изменении аппаратной конфигурации в таблицу hardware_component_history."""
        now_epoch = float(created_at) if created_at is not None else time.time()
        ts_str = timestamp or datetime.now(timezone.utc).isoformat()
        old_json = json.dumps(old_config, ensure_ascii=False) if old_config else None
        new_json = json.dumps(new_config, ensure_ascii=False) if new_config else None

        try:
            with self._cm.lock, self._cm.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    INSERT INTO hardware_component_history (
                        timestamp, created_at, component_type, change_type,
                        component_name, old_config_json, new_config_json, summary
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                    (
                        ts_str,
                        now_epoch,
                        str(component_type).upper(),
                        str(change_type).upper(),
                        str(component_name),
                        old_json,
                        new_json,
                        str(summary),
                    ),
                )
                change_id = cursor.lastrowid or 0
                conn.commit()
                logger.info(f"💾 [Апгрейд оборудования] Сохранено изменение #{change_id}: {summary}")
                return change_id
        except Exception as ex:
            logger.warning(f"Ошибка сохранения изменения конфигурации оборудования: {ex}")
            return 0

    def save_live_stream_session(self, session_data: Dict[str, Any]) -> bool:
        """Сохраняет сводный профиль ресурсопотребления сессии live stream в telemetry_rollups (tier='live_session')."""
        sess_id = session_data.get("session_id")
        if not sess_id:
            return False

        started_ts = float(session_data.get("started_ts") or time.time())
        ended_ts = float(session_data.get("ended_ts") or started_ts)
        payload = {
            **session_data,
            "top_cpu_consumers_json": json.dumps(session_data.get("top_cpu_consumers", []), ensure_ascii=False),
            "top_ram_consumers_json": json.dumps(session_data.get("top_ram_consumers", []), ensure_ascii=False),
            "top_disk_consumers_json": json.dumps(session_data.get("top_disk_consumers", []), ensure_ascii=False),
            "full_metrics_json": json.dumps(session_data.get("full_metrics", {}), ensure_ascii=False),
        }
        try:
            with self._cm.lock, self._cm.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    INSERT OR REPLACE INTO telemetry_rollups (
                        tier, sensor_id, bucket_start, period_start, period_end,
                        period_start_epoch, period_end_epoch,
                        cpu_avg, cpu_max, ram_avg, ram_max, ram_used_gb_avg,
                        gpu_load_avg, gpu_temp_max, session_id, payload_json, created_at
                    ) VALUES ('live_session', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                    (
                        str(sess_id),
                        started_ts,
                        str(session_data.get("started_at") or ""),
                        str(session_data.get("ended_at") or ""),
                        started_ts,
                        ended_ts,
                        float(session_data.get("cpu_avg_percent") or 0.0),
                        float(session_data.get("cpu_max_percent") or 0.0),
                        float(session_data.get("ram_avg_percent") or 0.0),
                        float(session_data.get("ram_max_percent") or 0.0),
                        float(session_data.get("ram_avg_used_gb") or 0.0),
                        float(session_data.get("gpu_avg_percent") or 0.0),
                        session_data.get("gpu_max_temp_c"),
                        str(sess_id),
                        json.dumps(payload, ensure_ascii=False, default=str),
                        ended_ts,
                    ),
                )
                conn.commit()
                logger.info(f"📊 [Live Stream] Сохранен профиль сессии ресурсопотребления {sess_id}")
                return True
        except Exception as ex:
            logger.warning(f"Ошибка сохранения сессии live stream {sess_id}: {ex}")
            return False

    def finalize_live_stream_session(
        self,
        session_id: str,
        started_ts: float,
        ended_ts: float,
        trigger_source: str = "manual",
        hardware_signature: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Агрегирует накопленные за сессию данные из system_snapshots и process_snapshots в компактный отчет."""
        duration = max(0.1, ended_ts - started_ts)
        start_iso = datetime.fromtimestamp(started_ts, tz=timezone.utc).isoformat()
        end_iso = datetime.fromtimestamp(ended_ts, tz=timezone.utc).isoformat()

        try:
            if hasattr(self, "_buffer") and self._buffer:
                self._buffer.flush()
        except Exception:
            pass

        try:
            with self._cm.lock, self._cm.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    SELECT
                        AVG(cpu_total_percent), MAX(cpu_total_percent),
                        AVG(memory_percent), MAX(memory_percent),
                        AVG(memory_used_gb), MAX(memory_used_gb),
                        MAX(memory_total_gb),
                        AVG(cpu_temp_c), MAX(cpu_temp_c), AVG(cpu_power_w),
                        AVG(gpu_load_percent), MAX(gpu_load_percent),
                        AVG(gpu_temp_c), MAX(gpu_temp_c), MAX(gpu_vram_used_mb),
                        AVG(disk_read_bytes_sec), AVG(disk_write_bytes_sec),
                        AVG(network_recv_bytes_sec), AVG(network_sent_bytes_sec)
                    FROM system_snapshots
                    WHERE created_at >= ? AND created_at <= ?
                    ''',
                    (started_ts, ended_ts),
                )
                sys_row = cursor.fetchone()

                cpu_avg = round(float(sys_row[0] or 0.0), 2) if sys_row else 0.0
                cpu_max = round(float(sys_row[1] or 0.0), 2) if sys_row else 0.0
                ram_avg_pct = round(float(sys_row[2] or 0.0), 2) if sys_row else 0.0
                ram_max_pct = round(float(sys_row[3] or 0.0), 2) if sys_row else 0.0
                ram_avg_used = round(float(sys_row[4] or 0.0), 2) if sys_row else 0.0
                ram_max_used = round(float(sys_row[5] or 0.0), 2) if sys_row else 0.0
                ram_total = round(float(sys_row[6] or 0.0), 2) if sys_row else 0.0
                cpu_avg_temp = round(float(sys_row[7]), 1) if (sys_row and sys_row[7] is not None) else None
                cpu_max_temp = round(float(sys_row[8]), 1) if (sys_row and sys_row[8] is not None) else None
                cpu_avg_power = round(float(sys_row[9]), 1) if (sys_row and sys_row[9] is not None) else None

                gpu_avg_load = round(float(sys_row[10] or 0.0), 1) if sys_row else 0.0
                gpu_max_load = round(float(sys_row[11] or 0.0), 1) if sys_row else 0.0
                gpu_avg_temp = round(float(sys_row[12]), 1) if (sys_row and sys_row[12] is not None) else None
                gpu_max_temp = round(float(sys_row[13]), 1) if (sys_row and sys_row[13] is not None) else None
                gpu_max_vram = round(float(sys_row[14] or 0.0), 1) if (sys_row and sys_row[14] is not None) else None

                disk_read_mbs = round(float(sys_row[15] or 0.0) / (1024 * 1024), 2) if sys_row else 0.0
                disk_write_mbs = round(float(sys_row[16] or 0.0) / (1024 * 1024), 2) if sys_row else 0.0
                disk_total_read_mb = round(disk_read_mbs * duration, 2)
                disk_total_write_mb = round(disk_write_mbs * duration, 2)

                net_recv_kb = round(float(sys_row[17] or 0.0) / 1024, 2) if sys_row else 0.0
                net_sent_kb = round(float(sys_row[18] or 0.0) / 1024, 2) if sys_row else 0.0
                net_total_recv_mb = round((net_recv_kb * duration) / 1024, 2)
                net_total_sent_mb = round((net_sent_kb * duration) / 1024, 2)

                cursor.execute(
                    '''
                    SELECT name, pid, AVG(cpu_percent) as avg_c, MAX(cpu_percent) as max_c,
                           AVG(memory_mb) as avg_m, MAX(memory_mb) as max_m
                    FROM process_snapshots
                    WHERE snapshot_id IN (SELECT id FROM system_snapshots WHERE created_at >= ? AND created_at <= ?)
                    GROUP BY name
                    ORDER BY avg_c DESC
                    LIMIT 10
                    ''',
                    (started_ts, ended_ts),
                )
                top_cpu = [
                    {
                        "name": r[0],
                        "pid": r[1],
                        "avg_cpu_percent": round(float(r[2] or 0.0), 2),
                        "max_cpu_percent": round(float(r[3] or 0.0), 2),
                        "avg_memory_mb": round(float(r[4] or 0.0), 1),
                    }
                    for r in cursor.fetchall()
                ]

                cursor.execute(
                    '''
                    SELECT name, pid, MAX(memory_mb) as max_m, AVG(memory_mb) as avg_m
                    FROM process_snapshots
                    WHERE snapshot_id IN (SELECT id FROM system_snapshots WHERE created_at >= ? AND created_at <= ?)
                    GROUP BY name
                    ORDER BY max_m DESC
                    LIMIT 10
                    ''',
                    (started_ts, ended_ts),
                )
                top_ram = [
                    {
                        "name": r[0],
                        "pid": r[1],
                        "max_memory_mb": round(float(r[2] or 0.0), 1),
                        "avg_memory_mb": round(float(r[3] or 0.0), 1),
                    }
                    for r in cursor.fetchall()
                ]

                cursor.execute("SELECT name FROM hardware_components WHERE category = 'cpu' ORDER BY id DESC LIMIT 1")
                cpu_inv_row = cursor.fetchone()
                cpu_model = cpu_inv_row[0] if cpu_inv_row else "Windows Processor"

                cursor.execute("SELECT name FROM hardware_components WHERE category = 'gpu' ORDER BY id DESC LIMIT 1")
                gpu_inv_row = cursor.fetchone()
                gpu_name = gpu_inv_row[0] if gpu_inv_row else None

            session_record = {
                "session_id": session_id,
                "started_at": start_iso,
                "ended_at": end_iso,
                "started_ts": started_ts,
                "ended_ts": ended_ts,
                "duration_seconds": round(duration, 2),
                "trigger_source": trigger_source,
                "hardware_signature": hardware_signature,
                "cpu_model": cpu_model,
                "cpu_avg_percent": cpu_avg,
                "cpu_max_percent": cpu_max,
                "cpu_avg_temp_c": cpu_avg_temp,
                "cpu_max_temp_c": cpu_max_temp,
                "cpu_avg_power_w": cpu_avg_power,
                "ram_total_gb": ram_total,
                "ram_avg_used_gb": ram_avg_used,
                "ram_max_used_gb": ram_max_used,
                "ram_avg_percent": ram_avg_pct,
                "ram_max_percent": ram_max_pct,
                "gpu_name": gpu_name,
                "gpu_avg_percent": gpu_avg_load,
                "gpu_max_percent": gpu_max_load,
                "gpu_avg_temp_c": gpu_avg_temp,
                "gpu_max_temp_c": gpu_max_temp,
                "gpu_max_memory_mb": gpu_max_vram,
                "disk_read_mbs": disk_read_mbs,
                "disk_write_mbs": disk_write_mbs,
                "disk_total_read_mb": disk_total_read_mb,
                "disk_total_write_mb": disk_total_write_mb,
                "network_recv_kb_sec": net_recv_kb,
                "network_sent_kb_sec": net_sent_kb,
                "network_total_recv_mb": net_total_recv_mb,
                "network_total_sent_mb": net_total_sent_mb,
                "top_cpu_consumers": top_cpu,
                "top_ram_consumers": top_ram,
                "top_disk_consumers": [],
                "full_metrics": {
                    "sample_count": len(top_cpu),
                },
            }

            self.save_live_stream_session(session_record)
            return session_record
        except Exception as ex:
            logger.warning(f"Ошибка финализации сессии live stream {session_id}: {ex}")
            return None

    def compact_live_stream_data(self, keep_last_snapshots: int = 5) -> Dict[str, int]:
        """Компактифицирует сырые секундные тики live stream, предотвращая раздувание базы данных."""
        stats: Dict[str, int] = {}
        try:
            with self._cm.lock, self._cm.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("SELECT COUNT(*) FROM process_snapshots WHERE sample_type = 'snapshot';")
                ps_count = cursor.fetchone()[0]
                if ps_count > 10:
                    cursor.execute(
                        '''
                        DELETE FROM process_snapshots
                        WHERE sample_type = 'snapshot' AND id NOT IN (
                            SELECT id FROM process_snapshots WHERE sample_type = 'snapshot' ORDER BY id DESC LIMIT 20
                        )
                        '''
                    )
                    stats["process_snapshots"] = cursor.rowcount

                cursor.execute("SELECT COUNT(*) FROM system_snapshots;")
                ss_count = cursor.fetchone()[0]
                if ss_count > keep_last_snapshots:
                    cursor.execute(
                        '''
                        DELETE FROM system_snapshots
                        WHERE id NOT IN (
                            SELECT id FROM system_snapshots ORDER BY id DESC LIMIT ?
                        )
                        ''',
                        (keep_last_snapshots,),
                    )
                    stats["system_snapshots"] = cursor.rowcount

                conn.commit()
                logger.info(f"🧹 [Компактификация] Сырые тики сжаты в профиль сессии: {stats}")
                return stats
        except Exception as ex:
            logger.debug(f"Ошибка при компактификации тиков live stream: {ex}")
            return stats

