# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry Sqlite - TelemetryAuditReaderMixin
# =============================================================================
# Description:
#   Миксин чтения аудитов: перезагрузки, архивы оборудования и автозагрузки,
#   журналы, брандмауэр, службы, Defender, ПО, процессы и Live Stream из 12 базовых таблиц.
#
# File: reader_audits.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry.sqlite
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 16:01:00
# =============================================================================

from __future__ import annotations

"""Миксин чтения аудитов: перезагрузки, архивы оборудования и автозагрузки, брандмауэр, службы, Defender, ПО и процессы."""

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .delta_inventory import DeltaInventory

try:
    from logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class TelemetryAuditReaderMixin:
    """Миксин чтения аудитов из 12 консолидированных таблиц SQLite."""

    def get_reboot_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Извлекает историю сессий перезагрузок из таблицы power_sessions."""
        results: List[Dict[str, Any]] = []
        try:
            with self._cm.lock, self._cm.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    SELECT * FROM power_sessions
                    WHERE record_type = 'reboot' OR record_type = 'session'
                    ORDER BY boot_time DESC, created_at DESC LIMIT ?
                    ''',
                    (limit,),
                )
                for row in cursor.fetchall():
                    item = dict(row)
                    item["downtime_seconds"] = item.get("uptime_seconds", 0.0)
                    item["initiated_by_user"] = item.get("user") or item.get("initiator")
                    item["initiated_by_process"] = item.get("process")
                    item["primary_reason"] = item.get("reason")
                    item["raw_json"] = item.get("details_json")
                    item["events_chain_json"] = item.get("events_json")
                    for f in ("bugcheck_params_json", "evidence_json", "events_chain_json", "raw_json"):
                        if item.get(f):
                            try:
                                item[f.replace("_json", "")] = json.loads(item[f])
                            except Exception:
                                pass
                    results.append(item)
        except Exception as ex:
            logger.error(f"Ошибка извлечения истории перезагрузок: {ex}")
        return results

    def get_latest_reboot_session(self) -> Optional[Dict[str, Any]]:
        """Возвращает самую последнюю запись сессии перезагрузки."""
        history = self.get_reboot_history(limit=1)
        return history[0] if history else None

    def get_extended_audits(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Возвращает историю расширенных системных аудитов из inventory_state."""
        results: List[Dict[str, Any]] = []
        try:
            with self._cm.lock, self._cm.get_connection() as conn:
                rows = DeltaInventory.get_active(conn.cursor(), "os_extended_audit")
                rows.sort(key=lambda x: float(x.get("created_at") or 0.0), reverse=True)
                for item in rows[:limit]:
                    if item.get("raw_json"):
                        try:
                            item["data"] = json.loads(item["raw_json"]) if isinstance(item["raw_json"], str) else item["raw_json"]
                        except Exception:
                            pass
                    results.append(item)
        except Exception as ex:
            logger.error(f"Ошибка извлечения расширенных аудитов: {ex}")
        return results

    def get_latest_extended_audit(self) -> Optional[Dict[str, Any]]:
        """Возвращает последний расширенный системный аудит."""
        audits = self.get_extended_audits(limit=1)
        return audits[0] if audits else None

    def get_hardware_audits(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Возвращает историю аудитов аппаратного обеспечения из hardware_components (category='hardware_audit')."""
        results: List[Dict[str, Any]] = []
        try:
            with self._cm.lock, self._cm.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM hardware_components WHERE category = 'hardware_audit' ORDER BY last_seen DESC, id DESC LIMIT ?",
                    (limit,),
                )
                for row in cursor.fetchall():
                    d = dict(row)
                    specs = json.loads(d["specs_json"]) if d.get("specs_json") else {}
                    item = {**d, **specs}
                    if item.get("raw_json"):
                        try:
                            item["data"] = json.loads(item["raw_json"]) if isinstance(item["raw_json"], str) else item["raw_json"]
                        except Exception:
                            pass
                    results.append(item)
        except Exception as ex:
            logger.error(f"Ошибка извлечения аудитов оборудования: {ex}")
        return results

    def get_latest_hardware_audit(self) -> Optional[Dict[str, Any]]:
        """Возвращает самый последний сохраненный аудит аппаратного обеспечения."""
        audits = self.get_hardware_audits(limit=1)
        return audits[0] if audits else None

    def get_startup_archives(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Возвращает историю архивных снимков автозапуска из inventory_state (domain='startup_archive')."""
        results: List[Dict[str, Any]] = []
        try:
            with self._cm.lock, self._cm.get_connection() as conn:
                rows = DeltaInventory.get_active(conn.cursor(), "startup_archive")
                rows.sort(key=lambda x: float(x.get("created_at") or 0.0), reverse=True)
                for item in rows[:limit]:
                    if item.get("raw_json"):
                        try:
                            item["data"] = json.loads(item["raw_json"]) if isinstance(item["raw_json"], str) else item["raw_json"]
                        except Exception:
                            pass
                    results.append(item)
        except Exception as ex:
            logger.error(f"Ошибка извлечения архивов автозапуска: {ex}")
        return results

    def get_latest_startup_archive(self) -> Optional[Dict[str, Any]]:
        """Возвращает самый последний сохраненный снимок автозапуска."""
        audits = self.get_startup_archives(limit=1)
        return audits[0] if audits else None

    def get_startup_changes(self, limit: int = 100, archive_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Возвращает историю зафиксированных изменений в автозапуске из inventory_changes."""
        results: List[Dict[str, Any]] = []
        try:
            with self._cm.lock, self._cm.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM inventory_changes WHERE domain = 'startup_changes' ORDER BY created_at DESC, id DESC LIMIT ?",
                    (max(limit * 2, 100),),
                )
                for row in cursor.fetchall():
                    d = dict(row)
                    diff = json.loads(d["diff_json"]) if d.get("diff_json") else {}
                    item = {**d, **diff}
                    if archive_id and item.get("archive_id") != archive_id:
                        continue
                    for f in ("previous_value", "current_value"):
                        if isinstance(item.get(f), str):
                            try:
                                item[f] = json.loads(item[f])
                            except Exception:
                                pass
                    results.append(item)
                    if len(results) >= limit:
                        break
        except Exception as ex:
            logger.error(f"Ошибка извлечения изменений автозапуска: {ex}")
        return results

    def get_latest_event_log_channels(self) -> List[Dict[str, Any]]:
        """Извлечение каналов журналов событий (хранение в SQLite отключено, чтение через WevtAPI)."""
        return []

    def get_event_log_entries(
        self,
        channel: str = "System",
        level: str = "",
        limit: int = 50,
        hours: int = 24,
    ) -> List[Dict[str, Any]]:
        """Выборка записей журнала событий (хранение кеша в SQLite отключено)."""
        return []

    def get_latest_event_log_intelligence_profile(self, channel: str = "System") -> Optional[Dict[str, Any]]:
        """Извлечение последнего сохраненного профиля Log Intelligence (хранение в SQLite отключено)."""
        return None

    def get_latest_event_log_report(self) -> Optional[Dict[str, Any]]:
        """Формирование сводного отчета о журналах и ошибках из базы данных."""
        return None

    def get_latest_firewall_profiles(self) -> Optional[Dict[str, Any]]:
        """Извлечение текущего состояния профилей брандмауэра из Change-Only инвентаризации."""
        with self._cm.lock, self._cm.get_connection() as conn:
            rows = DeltaInventory.get_active(conn.cursor(), "firewall_profiles")
        if not rows:
            return None
        return {**rows[0], "timestamp": rows[0]["last_changed"]}

    def get_latest_firewall_rules(self, direction: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
        """Выборка актуальных правил брандмауэра из Change-Only инвентаризации."""
        with self._cm.lock, self._cm.get_connection() as conn:
            rules = DeltaInventory.get_active(conn.cursor(), "firewall_rules")
        if direction:
            rules = [r for r in rules if str(r.get("direction", "")).lower() == direction.lower()]
        return rules[:int(limit)]

    def get_latest_services_list(self, status: Optional[str] = None, limit: int = 500) -> List[Dict[str, Any]]:
        """Извлечение актуального списка служб Windows из Change-Only инвентаризации."""
        with self._cm.lock, self._cm.get_connection() as conn:
            services = DeltaInventory.get_active(conn.cursor(), "services")
        if status:
            services = [s for s in services if str(s.get("status", "")).lower() == status.lower()]
        return services[:int(limit)]

    def get_inventory_changes(self, domain: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Журнал дельт инвентаризации (added/removed/modified) с датой обнаружения."""
        with self._cm.lock, self._cm.get_connection() as conn:
            return DeltaInventory.get_changes(conn.cursor(), domain=domain, limit=limit)

    def get_latest_services_report(self) -> Optional[Dict[str, Any]]:
        """Формирование сводного отчета о службах Windows."""
        services = self.get_latest_services_list(limit=1000)
        if not services:
            return None
        total = len(services)
        running = sum(1 for s in services if str(s.get("status", "")).upper() in ("RUNNING", "4", "SERVICE_RUNNING"))
        stopped = sum(1 for s in services if str(s.get("status", "")).upper() in ("STOPPED", "1", "SERVICE_STOPPED"))
        orphaned = sum(1 for s in services if s.get("is_orphaned"))

        return {
            "total_services": total,
            "running_services": running,
            "stopped_services": stopped,
            "orphaned_services": orphaned,
            "services": services,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_service_change_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Извлечение истории изменений служб из inventory_changes (domain='service_change_events')."""
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT id, timestamp, created_at, entity_key, change_type, diff_json
                FROM inventory_changes
                WHERE domain = 'service_change_events'
                ORDER BY id DESC LIMIT ?
                ''',
                (int(limit),),
            )
            rows = []
            for r in cursor.fetchall():
                d = dict(r)
                diff = json.loads(d["diff_json"]) if d.get("diff_json") else {}
                item = {**d, **diff}
                if item.get("details_json") and not item.get("details"):
                    try:
                        item["details"] = json.loads(item["details_json"])
                    except Exception:
                        pass
                rows.append(item)
            return rows

    def get_latest_throttling_snapshot(self) -> Optional[Dict[str, Any]]:
        """Извлечение последнего снимка троттлинга процессора и термических зон из sensor_polls."""
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT * FROM sensor_polls
                WHERE sensor_category = 'throttling' OR sensor_id = 'cpu_throttling'
                ORDER BY id DESC LIMIT 1
                '''
            )
            row = cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            payload = json.loads(d["raw_json"]) if d.get("raw_json") else {}
            res = {**d, **payload}
            if "throttling_reasons" not in res:
                res["throttling_reasons"] = json.loads(res["throttling_reasons_json"]) if res.get("throttling_reasons_json") else []
            if "thermal_zones" not in res:
                res["thermal_zones"] = []
            return res

    def get_latest_forensics_snapshot(self) -> Optional[Dict[str, Any]]:
        """Извлечение последнего снимка поведенческой форензики из inventory_state."""
        history = self.get_forensics_history(limit=1)
        return history[0] if history else None

    def get_forensics_history(self, limit: int = 50, hours: float = 24.0) -> List[Dict[str, Any]]:
        """Извлечение хронологической истории снимков форензики из inventory_state."""
        with self._cm.lock, self._cm.get_connection() as conn:
            rows = DeltaInventory.get_active(conn.cursor(), "forensics")
            rows.sort(key=lambda x: float(x.get("created_at") or 0.0), reverse=True)
            results = []
            for d in rows[:limit]:
                item = dict(d)
                item.setdefault("camera_active_apps", [])
                item.setdefault("microphone_active_apps", [])
                item.setdefault("userassist_top_apps", [])
                results.append(item)
            return results

    def get_latest_process_leak_report(self, limit: int = 20) -> Optional[Dict[str, Any]]:
        """Извлечение последнего снимка утечек ресурсов процессов из process_snapshots (sample_type='leak')."""
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT instance_id, timestamp, raw_json
                FROM process_snapshots
                WHERE sample_type = 'leak'
                ORDER BY id DESC LIMIT 1
                '''
            )
            row = cursor.fetchone()
            if not row:
                return None
            snap_id = row["instance_id"]
            raw_meta = json.loads(row["raw_json"]) if row["raw_json"] else {}
            report = {
                "snapshot_id": snap_id,
                "timestamp": row["timestamp"],
                "total_processes": raw_meta.get("total_processes", 0),
                "suspicious_count": raw_meta.get("suspicious_count", 0),
            }

            cursor.execute(
                '''
                SELECT pid, name, num_handles AS handles_count, gdi_objects, user_objects,
                       page_faults, working_set_mb, leak_risk_score, raw_json
                FROM process_snapshots
                WHERE sample_type = 'leak' AND instance_id = ?
                ORDER BY num_handles DESC
                LIMIT ?
                ''',
                (snap_id, int(limit)),
            )
            items = []
            for r in cursor.fetchall():
                d = dict(r)
                rm = json.loads(d["raw_json"]) if d.get("raw_json") else {}
                d["leak_risk_reasons"] = rm.get("leak_risk_reasons", [])
                items.append(d)
            report["all_processes"] = items
            report["top_handle_hogs"] = sorted(items, key=lambda x: x.get("handles_count", 0), reverse=True)[:10]
            report["top_gdi_hogs"] = sorted(items, key=lambda x: x.get("gdi_objects", 0), reverse=True)[:10]
            report["top_page_fault_hogs"] = sorted(items, key=lambda x: x.get("page_faults", 0), reverse=True)[:10]
            report["suspicious_processes"] = [x for x in items if str(x.get("leak_risk_score", "normal")).lower() not in ("normal", "low")]
            return report

    def get_latest_defender_status(self) -> Optional[Dict[str, Any]]:
        """Извлечение статуса Защитника Windows из inventory_state (domain='defender_status')."""
        with self._cm.lock, self._cm.get_connection() as conn:
            rows = DeltaInventory.get_active(conn.cursor(), "defender_status")
            if not rows:
                return None
            d = dict(rows[0])
            if d.get("raw_status_json"):
                try:
                    d.update(json.loads(d["raw_status_json"]))
                except Exception:
                    pass
            return d

    def get_latest_defender_exclusions(self, limit: int = 200) -> List[Dict[str, Any]]:
        """Извлечение исключений антивируса Defender из inventory_state (domain='defender_exclusions')."""
        with self._cm.lock, self._cm.get_connection() as conn:
            rows = DeltaInventory.get_active(conn.cursor(), "defender_exclusions")
            items = []
            for r in rows[:limit]:
                d = dict(r)
                d["type"] = d.get("exclusion_type", "path")
                d["value"] = d.get("exclusion_value", "")
                items.append(d)
            return items

    def get_latest_defender_asr_rules(self) -> List[Dict[str, Any]]:
        """Извлечение правил ASR Защитника Windows из inventory_state (domain='defender_asr')."""
        with self._cm.lock, self._cm.get_connection() as conn:
            rows = DeltaInventory.get_active(conn.cursor(), "defender_asr")
            items = []
            for r in rows:
                d = dict(r)
                d["guid"] = d.get("rule_guid", "")
                d["name"] = d.get("rule_name", "")
                d["state"] = d.get("rule_action", "not_configured")
                items.append(d)
            return items

    def get_latest_defender_threats(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Извлечение обнаруженных угроз Defender из таблицы incidents (domain='defender_threat')."""
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT * FROM incidents
                WHERE domain = 'defender_threat'
                ORDER BY id DESC LIMIT ?
                ''',
                (limit,),
            )
            rows = []
            for r in cursor.fetchall():
                d = dict(r)
                details = json.loads(d["details_json"]) if d.get("details_json") else {}
                item = {**d, **details}
                item.setdefault("resources", [])
                item["status"] = item.get("status", "Cleaned")
                item["initial_detection_time"] = item.get("detection_time") or item.get("timestamp")
                rows.append(item)
            return rows

    def get_latest_defender_diagnostics(self) -> Dict[str, Any]:
        """Сводная диагностика безопасности Defender."""
        status = self.get_latest_defender_status() or {}
        exclusions = self.get_latest_defender_exclusions()
        asr_rules = self.get_latest_defender_asr_rules()
        threats = self.get_latest_defender_threats()
        return {
            "status": status,
            "exclusions": exclusions,
            "asr_rules": asr_rules,
            "threats": threats,
            "total_exclusions": len(exclusions),
            "total_asr_rules": len(asr_rules),
            "active_threats_count": len(threats),
        }

    def get_latest_process_network_activity(
        self,
        limit: int = 100,
        only_internet: bool = True,
    ) -> List[Dict[str, Any]]:
        """Извлечение сетевой активности процессов из таблицы process_snapshots."""
        def _is_ext_internet(addr: str) -> bool:
            if not addr or addr in ("-", "", "::"):
                return False
            ip = addr.rsplit(":", 1)[0] if ":" in addr else addr
            ip = ip.strip("[]")
            if not ip or ip in ("127.0.0.1", "::1", "0.0.0.0", "::", "localhost") or ip.startswith("127.") or ip.startswith("fe80:"):
                return False
            return True

        def _guess_service(addr: str) -> str:
            port = None
            if ":" in addr:
                try:
                    port = int(addr.rsplit(":", 1)[1])
                except Exception:
                    pass
            known = {
                80: "Web/HTTP",
                443: "Web/HTTPS",
                53: "DNS",
                22: "SSH",
                8000: "HTTP-Alt",
                8001: "TC-API",
                8080: "HTTP-Proxy",
                3389: "RDP",
                445: "SMB",
                139: "NetBIOS",
            }
            return known.get(port, f"Port {port}" if port else "TCP/IP")

        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT pid, name, username, status, read_bytes_sec, write_bytes_sec, sockets_json, raw_json
                FROM process_snapshots
                WHERE sample_type = 'network' OR (sockets_json IS NOT NULL AND sockets_json != '' AND sockets_json != '[]')
                ORDER BY id DESC
                LIMIT ?
                ''',
                (max(limit * 2, 100),),
            )
            formatted: List[Dict[str, Any]] = []
            for r in cursor.fetchall():
                d = dict(r)
                proc_n = d.get("name") or "unknown"
                user_n = d.get("username") or ""
                sockets = []
                if d.get("sockets_json"):
                    try:
                        sockets = json.loads(d["sockets_json"])
                    except Exception:
                        pass
                if not sockets and d.get("raw_json"):
                    try:
                        rj = json.loads(d["raw_json"])
                        if isinstance(rj, dict) and ("remote_address" in rj or "local_address" in rj):
                            sockets = [rj]
                    except Exception:
                        pass

                for s in (sockets if isinstance(sockets, list) else []):
                    if not isinstance(s, dict):
                        continue
                    rem = s.get("remote_address") or s.get("remote") or ""
                    loc = s.get("local_address") or s.get("local") or ""
                    is_ext = _is_ext_internet(rem)
                    if only_internet and not is_ext:
                        continue
                    srv = s.get("service_type") or (_guess_service(rem) if rem else _guess_service(loc))
                    sent_kb_val = float(s.get("sent_kb", 0.0) or 0.0)
                    recv_kb_val = float(s.get("recv_kb", 0.0) or 0.0)
                    sent_rate = float(s.get("write_speed_kbs") or d.get("write_bytes_sec") or 0.0)
                    recv_rate = float(s.get("read_speed_kbs") or d.get("read_bytes_sec") or 0.0)
                    formatted.append({
                        "pid": int(d.get("pid") or 0),
                        "name": proc_n,
                        "process_name": proc_n,
                        "user": user_n,
                        "local_address": loc,
                        "remote_address": rem,
                        "protocol": s.get("protocol") or s.get("type") or "TCP",
                        "status": s.get("status") or d.get("status") or "ESTABLISHED",
                        "is_internet": is_ext,
                        "service_type": srv,
                        "service_name": srv,
                        "sent_kb": sent_kb_val,
                        "recv_kb": recv_kb_val,
                        "bytes_sent": int(sent_kb_val * 1024),
                        "bytes_recv": int(recv_kb_val * 1024),
                        "delta_sent_kb": 0.0,
                        "delta_recv_kb": 0.0,
                        "send_rate_kb": sent_rate,
                        "recv_rate_kb": recv_rate,
                        "sent_rate_kbs": sent_rate,
                        "recv_rate_kbs": recv_rate,
                        "sent_summary": f"{proc_n} -> {srv}",
                        "recv_summary": f"{srv} -> {proc_n}",
                    })
                    if len(formatted) >= limit:
                        return formatted
            return formatted[:limit]

    def get_software_inventory_from_db(self, limit: int = 200, offset: int = 0) -> List[Dict[str, Any]]:
        """Извлечение инвентаря установленного ПО из inventory_state (domain='software')."""
        with self._cm.lock, self._cm.get_connection() as conn:
            rows = DeltaInventory.get_active(conn.cursor(), "software")
            rows.sort(key=lambda x: str(x.get("display_name") or "").lower())
            sliced = rows[int(offset) : int(offset) + int(limit)]
            for r in sliced:
                locs = json.loads(r.get("storage_locations_json") or "[]") if isinstance(r.get("storage_locations_json"), str) else (r.get("storage_locations") or [])
                ai = json.loads(r.get("ai_research_json") or "{}") if isinstance(r.get("ai_research_json"), str) and r.get("ai_research_json") else {}
                r["storage_locations_count"] = len(locs)
                r["total_storage_bytes"] = sum(int(loc.get("size_bytes", 0) or 0) for loc in locs if isinstance(loc, dict))
                r["ai_summary"] = ai.get("summary") if isinstance(ai, dict) else None
                r["ai_confidence"] = ai.get("confidence_level") if isinstance(ai, dict) else None
            return sliced

    def get_software_app_details_from_db(self, app_id: str) -> Optional[Dict[str, Any]]:
        """Извлечение полной карточки установленной программы из inventory_state (domain='software')."""
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT attrs_json FROM inventory_state WHERE domain = 'software' AND entity_key = ?",
                (app_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            app_data = json.loads(row[0]) if row[0] else {}
            app_data["storage_locations"] = json.loads(app_data.get("storage_locations_json") or "[]")
            app_data["config_files"] = json.loads(app_data.get("config_files_json") or "[]")
            app_data["ai_research"] = json.loads(app_data.get("ai_research_json") or "null")
            app_data["execution_info"] = json.loads(app_data.get("execution_info_json") or "null")
            return app_data

    def get_latest_software_audit_report(self) -> Optional[Dict[str, Any]]:
        """Извлечение последнего сводного отчета аудита ПО из inventory_state (domain='software_audit')."""
        reports = self.get_software_audit_reports_history(limit=1)
        if not reports:
            return None
        res = reports[0]
        res["categories_breakdown"] = json.loads(res.get("categories_breakdown_json") or "{}")
        res["top_launched"] = json.loads(res.get("top_launched_json") or "[]")
        res["recently_launched"] = json.loads(res.get("recently_launched_json") or "[]")
        res["never_launched_or_dormant"] = json.loads(res.get("never_launched_or_dormant_json") or "[]")
        return res

    def get_software_audit_reports_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Извлечение истории отчетов аудита ПО из inventory_state (domain='software_audit')."""
        with self._cm.lock, self._cm.get_connection() as conn:
            rows = DeltaInventory.get_active(conn.cursor(), "software_audit")
            rows.sort(key=lambda x: float(x.get("created_at") or 0.0), reverse=True)
            return rows[:int(limit)]

    def get_latest_software_scanner_report(self) -> Optional[Dict[str, Any]]:
        """Извлечение последнего сохраненного отчета сканирования ПО и спящих программ из inventory_state (domain='software_scanner')."""
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT attrs_json FROM inventory_state WHERE domain = 'software_scanner' AND entity_key = 'latest'"
            )
            row = cursor.fetchone()
            if row and row[0]:
                try:
                    payload = json.loads(row[0])
                    if payload.get("raw_json"):
                        raw_data = json.loads(payload["raw_json"]) if isinstance(payload["raw_json"], str) else payload["raw_json"]
                        if raw_data and isinstance(raw_data, dict) and "inventory" in raw_data:
                            return raw_data
                    if payload.get("inventory_json"):
                        inv = json.loads(payload["inventory_json"])
                        stats = json.loads(payload.get("stats_json") or "{}")
                        orphans = json.loads(payload.get("orphan_items_json") or "[]")
                        return {
                            "scan_id": payload.get("report_id", "telemetry_db"),
                            "mode": "telemetry",
                            "started_at": payload.get("timestamp"),
                            "completed_at": payload.get("timestamp"),
                            "stats": stats,
                            "inventory": inv,
                            "orphan_items": orphans,
                            "errors": [],
                        }
                except Exception as ex:
                    logger.debug(f"Ошибка парсинга software_scanner из inventory_state: {ex}")

        # Fallback-синтез из данных телеметрии (software_audit и software), уже накопленных в telemetry.db
        audit_rep = self.get_latest_software_audit_report()
        if audit_rep:
            try:
                dormant_list = audit_rep.get("never_launched_or_dormant") or []
                dormant_names = {
                    (d.get("display_name") or d.get("name") or "").strip().lower()
                    for d in dormant_list if isinstance(d, dict)
                }
                apps = self.get_software_inventory_from_db(limit=5000)
                inventory: List[Dict[str, Any]] = []
                for app in apps:
                    d_name = (app.get("display_name") or app.get("name") or "").strip()
                    if not d_name:
                        continue
                    last_run = app.get("last_run_time")
                    run_count = int(app.get("run_count") or 0)
                    is_dormant = d_name.lower() in dormant_names or (not last_run)
                    status = "dormant" if is_dormant and last_run else ("never_launched" if not last_run else "active")
                    days_since = None
                    if last_run:
                        try:
                            lr_dt = datetime.fromisoformat(str(last_run).replace("Z", "+00:00"))
                            days_since = max(0, (datetime.now(timezone.utc) - lr_dt.replace(tzinfo=timezone.utc)).days)
                            if days_since > 90:
                                status = "dormant"
                        except Exception:
                            pass
                    card = {
                        "id": str(app.get("app_id") or app.get("entity_key") or d_name),
                        "name": d_name,
                        "publisher": app.get("publisher") or "—",
                        "version": app.get("version") or "—",
                        "install_location": app.get("install_location") or "",
                        "main_executable": app.get("uninstall_string") or "",
                        "status": status,
                        "days_since_last_run": days_since,
                        "last_execution": str(last_run) if last_run else None,
                        "run_count": run_count,
                        "is_orphan": False,
                        "uninstall_string": app.get("uninstall_string") or "",
                        "evidence": [
                            {
                                "evidence_type": "registry",
                                "source": "telemetry.db (inventory_state)",
                                "path": app.get("install_location") or app.get("registry_key") or "HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall",
                                "last_execution": str(last_run) if last_run else None,
                            }
                        ],
                    }
                    inventory.append(card)

                # Поиск сиротских служб в telemetry.db
                orphans: List[Dict[str, Any]] = []
                with self._cm.lock, self._cm.get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT attrs_json FROM inventory_state WHERE domain = 'services' AND attrs_json LIKE '%\"is_orphaned\": 1%'"
                    )
                    for (srv_row,) in cur.fetchall():
                        try:
                            srv_d = json.loads(srv_row)
                            orphans.append({
                                "source": "service",
                                "path": srv_d.get("binpath") or "",
                                "product_name": srv_d.get("display_name") or srv_d.get("name") or "Битый сервис",
                            })
                        except Exception:
                            pass

                total_identified = len(inventory)
                dormant_cnt = sum(1 for c in inventory if c["status"] in ("dormant", "never_launched"))
                active_cnt = sum(1 for c in inventory if c["status"] == "active")

                return {
                    "scan_id": "telemetry_db_synthesized",
                    "mode": "telemetry",
                    "started_at": audit_rep.get("timestamp"),
                    "completed_at": audit_rep.get("timestamp"),
                    "stats": {
                        "total_evidence_found": total_identified + len(orphans),
                        "total_software_identified": total_identified,
                        "active_count": active_cnt,
                        "dormant_count": dormant_cnt,
                        "orphan_count": len(orphans),
                        "errors_count": 0,
                        "duration_ms": 15.0,
                    },
                    "inventory": inventory,
                    "orphan_items": orphans,
                    "errors": [],
                }
            except Exception as e:
                logger.debug(f"Ошибка синтеза отчета из telemetry.db: {e}")

        return None

    def get_dormant_software_from_db(self, min_days: int = 90) -> List[Dict[str, Any]]:
        """Извлечение спящих программ (>min_days или без запусков) из telemetry.db."""
        report = self.get_latest_software_scanner_report()
        if not report or not report.get("inventory"):
            return []
        dormant = []
        for card in report.get("inventory", []):
            st = card.get("status")
            days = card.get("days_since_last_run")
            if st in ("dormant", "never_launched") or (days is not None and days >= min_days):
                dormant.append(card)
        return dormant

    def get_orphan_software_from_db(self) -> List[Dict[str, Any]]:
        """Извлечение списка обнаруженных сирот и битых записей из telemetry.db."""
        report = self.get_latest_software_scanner_report()
        if not report:
            return []
        return report.get("orphan_items") or []

    def get_process_audit_history(self, pid: int, limit: int = 100) -> List[Dict[str, Any]]:
        """Извлекает историческую выборку глубокого аудита процесса по PID из process_snapshots (sample_type='audit')."""
        results: List[Dict[str, Any]] = []
        try:
            with self._cm.lock, self._cm.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    SELECT * FROM process_snapshots
                    WHERE sample_type = 'audit' AND pid = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    ''',
                    (pid, max(1, limit)),
                )
                for row in cursor.fetchall():
                    item = dict(row)
                    conns_raw = item.get("sockets_json") or item.get("network_connections_json")
                    item["network_connections_json"] = conns_raw
                    if conns_raw:
                        try:
                            item["connections"] = json.loads(conns_raw)
                        except Exception:
                            item["connections"] = []
                    else:
                        item["connections"] = []
                    if item.get("open_files_json"):
                        try:
                            item["open_files"] = json.loads(item["open_files_json"])
                        except Exception:
                            item["open_files"] = []
                    else:
                        item["open_files"] = []
                    results.append(item)
        except Exception as ex:
            logger.debug(f"Ошибка извлечения истории аудита для PID {pid}: {ex}")
        return results

    def get_process_lifecycle_sessions(
        self,
        app_name: Optional[str] = None,
        username: Optional[str] = None,
        parent_name: Optional[str] = None,
        pid: Optional[int] = None,
        is_alive: Optional[bool] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Извлекает сессии жизненного цикла процессов с поддержкой фильтрации."""
        results: List[Dict[str, Any]] = []
        where_clauses: List[str] = []
        params: List[Any] = []

        if app_name:
            where_clauses.append("LOWER(name) LIKE ?")
            params.append(f"%{app_name.lower()}%")
        if username:
            where_clauses.append("LOWER(username) LIKE ?")
            params.append(f"%{username.lower()}%")
        if parent_name:
            where_clauses.append("LOWER(parent_name) LIKE ?")
            params.append(f"%{parent_name.lower()}%")
        if pid is not None:
            where_clauses.append("pid = ?")
            params.append(pid)
        if is_alive is not None:
            where_clauses.append("is_alive = ?")
            params.append(1 if is_alive else 0)

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        query = f"""
            SELECT * FROM process_lifecycle_sessions
            {where_sql}
            ORDER BY created_ts DESC
            LIMIT ?
        """
        params.append(max(1, limit))

        try:
            with self._cm.lock, self._cm.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, tuple(params))
                for row in cursor.fetchall():
                    item = dict(row)
                    if item.get("files_accessed_json"):
                        try:
                            item["files_accessed"] = json.loads(item["files_accessed_json"])
                        except Exception:
                            item["files_accessed"] = []
                    if item.get("remote_endpoints_json"):
                        try:
                            item["remote_endpoints"] = json.loads(item["remote_endpoints_json"])
                        except Exception:
                            item["remote_endpoints"] = []
                    results.append(item)
        except Exception as ex:
            logger.debug(f"Ошибка извлечения сессий жизненного цикла процессов: {ex}")
        return results

    def get_process_lifecycle_by_instance_id(self, instance_id: str) -> Optional[Dict[str, Any]]:
        """Извлекает сессию жизненного цикла по уникальному instance_id."""
        try:
            with self._cm.lock, self._cm.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM process_lifecycle_sessions WHERE instance_id = ?", (instance_id,))
                row = cursor.fetchone()
                if row:
                    item = dict(row)
                    if item.get("files_accessed_json"):
                        try:
                            item["files_accessed"] = json.loads(item["files_accessed_json"])
                        except Exception:
                            item["files_accessed"] = []
                    if item.get("remote_endpoints_json"):
                        try:
                            item["remote_endpoints"] = json.loads(item["remote_endpoints_json"])
                        except Exception:
                            item["remote_endpoints"] = []
                    return item
        except Exception as ex:
            logger.debug(f"Ошибка извлечения сессии {instance_id}: {ex}")
        return None

    def get_app_summary_report(
        self, app_name: Optional[str] = None, username: Optional[str] = None
    ) -> Dict[str, Any]:
        """Формирует агрегированный отчет по приложениям/пользователям/инициаторам из БД."""
        sessions = self.get_process_lifecycle_sessions(app_name=app_name, username=username, limit=1000)
        total_runs = len(sessions)
        active_now = sum(1 for s in sessions if s.get("is_alive"))
        total_lifetime = sum(float(s.get("lifetime_sec") or 0.0) for s in sessions)
        total_cpu = sum(float(s.get("cpu_time_total_sec") or 0.0) for s in sessions)
        total_read_mb = round(sum(int(s.get("io_read_bytes") or 0) for s in sessions) / (1024 ** 2), 2)
        total_write_mb = round(sum(int(s.get("io_write_bytes") or 0) for s in sessions) / (1024 ** 2), 2)
        peak_ws_mb = max((float(s.get("peak_working_set_mb") or 0.0) for s in sessions), default=0.0)

        initiators: Dict[str, int] = {}
        users: Dict[str, int] = {}
        for s in sessions:
            p_name = s.get("parent_name") or s.get("initiator_type") or "unknown"
            initiators[p_name] = initiators.get(p_name, 0) + 1
            u_name = s.get("username") or "Unknown"
            users[u_name] = users.get(u_name, 0) + 1

        return {
            "app_filter": app_name,
            "user_filter": username,
            "total_launches": total_runs,
            "active_now": active_now,
            "total_lifetime_sec": round(total_lifetime, 2),
            "total_cpu_time_sec": round(total_cpu, 2),
            "peak_memory_mb": peak_ws_mb,
            "total_io_read_mb": total_read_mb,
            "total_io_write_mb": total_write_mb,
            "initiators": initiators,
            "users": users,
            "sessions": sessions[:50],
        }

    def get_process_incident_timeline(self, pid: int, limit: int = 100) -> Optional[Dict[str, Any]]:
        """Восстанавливает сквозную хронику инцидента процесса (CPU, RAM, Диск, Сеть)."""
        from apps.windows.sdk.modules.process_manager import IncidentTimelineBuilder
        samples = self.get_process_audit_history(pid=pid, limit=limit)
        builder = IncidentTimelineBuilder()

        if samples:
            timeline = builder.build_timeline_from_samples(samples)
            if timeline:
                return timeline.to_dict()

        sessions = self.get_process_lifecycle_sessions(pid=pid, limit=1)
        if sessions:
            sess = sessions[0]
            sample_data = {
                "instance_id": sess.get("instance_id"),
                "pid": sess.get("pid"),
                "name": sess.get("name"),
                "timestamp": sess.get("created_at"),
                "created_at": sess.get("created_ts"),
                "username": sess.get("username"),
                "parent_name": sess.get("parent_name"),
                "initiator_type": sess.get("initiator_type"),
                "cmdline": sess.get("cmdline"),
                "cpu_percent": 0.0,
                "working_set_mb": sess.get("peak_working_set_mb", 0.0),
                "private_mb": sess.get("peak_private_mb", 0.0),
                "write_bytes": sess.get("io_write_bytes", 0),
                "read_bytes": sess.get("io_read_bytes", 0),
                "write_operations": sess.get("io_write_ops", 0),
                "open_files": sess.get("files_accessed", []),
                "connections": [{"remote_address": ep.split(":")[0], "remote_port": ep.split(":")[1]} for ep in sess.get("remote_endpoints", []) if ":" in ep],
                "is_alive": sess.get("is_alive", 1),
            }
            timeline = builder.build_timeline_from_samples([sample_data])
            if timeline:
                return timeline.to_dict()

        return None

    def get_hardware_config_changes(
        self, component_type: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Возвращает историю всех зафиксированных изменений конфигурации оборудования из hardware_component_history."""
        query = "SELECT * FROM hardware_component_history"
        params: List[Any] = []
        if component_type:
            query += " WHERE component_type = ?"
            params.append(str(component_type).upper())
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(max(1, limit))

        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            changes: List[Dict[str, Any]] = []
            for r in rows:
                d = dict(r)
                changes.append({
                    "id": d.get("id"),
                    "timestamp": d.get("timestamp"),
                    "created_at": d.get("created_at"),
                    "component_type": d.get("component_type"),
                    "change_type": d.get("change_type"),
                    "component_name": d.get("component_name"),
                    "old_config": json.loads(d["old_config_json"]) if d.get("old_config_json") else None,
                    "new_config": json.loads(d["new_config_json"]) if d.get("new_config_json") else None,
                    "summary": d.get("summary"),
                })
            return changes

    def get_live_stream_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Возвращает список сохраненных компактных сессий live stream из telemetry_rollups (tier='live_session')."""
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM telemetry_rollups WHERE tier = 'live_session' ORDER BY bucket_start DESC LIMIT ?",
                (max(1, limit),),
            )
            rows = cursor.fetchall()
            sessions: List[Dict[str, Any]] = []
            for r in rows:
                d = dict(r)
                payload = json.loads(d["payload_json"]) if d.get("payload_json") else {}
                item = {**d, **payload}
                if item.get("top_cpu_consumers_json") and "top_cpu_consumers" not in item:
                    item["top_cpu_consumers"] = json.loads(item["top_cpu_consumers_json"])
                if item.get("top_ram_consumers_json") and "top_ram_consumers" not in item:
                    item["top_ram_consumers"] = json.loads(item["top_ram_consumers_json"])
                if item.get("top_disk_consumers_json") and "top_disk_consumers" not in item:
                    item["top_disk_consumers"] = json.loads(item["top_disk_consumers_json"])
                if item.get("full_metrics_json") and "full_metrics" not in item:
                    item["full_metrics"] = json.loads(item["full_metrics_json"])
                sessions.append(item)
            return sessions

    def get_live_stream_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Возвращает детальный отчет по сессии live stream по ее session_id из telemetry_rollups."""
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM telemetry_rollups WHERE tier = 'live_session' AND (session_id = ? OR sensor_id = ?) LIMIT 1",
                (session_id, session_id),
            )
            row = cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            payload = json.loads(d["payload_json"]) if d.get("payload_json") else {}
            item = {**d, **payload}
            if item.get("top_cpu_consumers_json") and "top_cpu_consumers" not in item:
                item["top_cpu_consumers"] = json.loads(item["top_cpu_consumers_json"])
            if item.get("top_ram_consumers_json") and "top_ram_consumers" not in item:
                item["top_ram_consumers"] = json.loads(item["top_ram_consumers_json"])
            if item.get("top_disk_consumers_json") and "top_disk_consumers" not in item:
                item["top_disk_consumers"] = json.loads(item["top_disk_consumers_json"])
            if item.get("full_metrics_json") and "full_metrics" not in item:
                item["full_metrics"] = json.loads(item["full_metrics_json"])
            return item

    def get_hardware_comparison_report(
        self,
        change_id: Optional[int] = None,
        component_type: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Формирует сравнительный отчет производительности и ресурсопотребления «Было / Стало»."""
        changes = self.get_hardware_config_changes(component_type=component_type, limit=10)
        target_change: Optional[Dict[str, Any]] = None
        if change_id is not None:
            for ch in changes:
                if ch["id"] == change_id:
                    target_change = ch
                    break
        elif changes:
            target_change = changes[0]

        all_sessions = self.get_live_stream_sessions(limit=100)
        before_session: Optional[Dict[str, Any]] = None
        after_session: Optional[Dict[str, Any]] = None

        if target_change:
            change_epoch = float(target_change["created_at"])
            before_candidates = [s for s in all_sessions if float(s.get("ended_ts") or 0.0) <= change_epoch]
            after_candidates = [s for s in all_sessions if float(s.get("started_ts") or 0.0) >= change_epoch]

            if before_candidates:
                before_session = before_candidates[0]
            if after_candidates:
                after_session = after_candidates[-1]

        if not before_session and len(all_sessions) >= 2:
            before_session = all_sessions[-1]
        if not after_session and len(all_sessions) >= 1:
            after_session = all_sessions[0]

        if not target_change and not before_session:
            return None

        deltas: Dict[str, Any] = {}
        conclusions: List[str] = []

        if before_session and after_session and before_session.get("session_id") != after_session.get("session_id"):
            cpu_avg_diff = round(float(after_session.get("cpu_avg_percent") or 0.0) - float(before_session.get("cpu_avg_percent") or 0.0), 2)
            cpu_max_diff = round(float(after_session.get("cpu_max_percent") or 0.0) - float(before_session.get("cpu_max_percent") or 0.0), 2)
            deltas["cpu_avg_percent_diff"] = cpu_avg_diff
            deltas["cpu_max_percent_diff"] = cpu_max_diff

            if cpu_avg_diff < 0:
                conclusions.append(f"Средняя нагрузка CPU снизилась на {abs(cpu_avg_diff)}%.")
            elif cpu_avg_diff > 0:
                conclusions.append(f"Средняя нагрузка CPU возросла на {cpu_avg_diff}%.")

            b_temp = before_session.get("cpu_avg_temp_c")
            a_temp = after_session.get("cpu_avg_temp_c")
            if b_temp is not None and a_temp is not None:
                temp_diff = round(float(a_temp) - float(b_temp), 1)
                deltas["cpu_avg_temp_diff_c"] = temp_diff
                if temp_diff < 0:
                    conclusions.append(f"Температура процессора упала на {abs(temp_diff)}°C.")
                elif temp_diff > 0:
                    conclusions.append(f"Температура процессора выросла на {temp_diff}°C.")

            b_ram_pct = before_session.get("ram_avg_percent")
            a_ram_pct = after_session.get("ram_avg_percent")
            if b_ram_pct is not None and a_ram_pct is not None:
                ram_pct_diff = round(float(a_ram_pct) - float(b_ram_pct), 1)
                deltas["ram_avg_percent_diff"] = ram_pct_diff
                if ram_pct_diff < 0:
                    conclusions.append(f"Утилизация оперативной памяти снизилась на {abs(ram_pct_diff)}% (больше запаса свободной памяти).")

            b_disk_speed = float(before_session.get("disk_read_mbs") or 0.0) + float(before_session.get("disk_write_mbs") or 0.0)
            a_disk_speed = float(after_session.get("disk_read_mbs") or 0.0) + float(after_session.get("disk_write_mbs") or 0.0)
            deltas["disk_throughput_diff_mbs"] = round(a_disk_speed - b_disk_speed, 2)

        summary_conclusion = " ".join(conclusions) if conclusions else "Данные производительности зафиксированы."

        return {
            "change_info": target_change,
            "has_before_after_sessions": (before_session is not None and after_session is not None and before_session.get("session_id") != after_session.get("session_id")),
            "before_session": before_session,
            "after_session": after_session,
            "metrics_comparison": deltas,
            "conclusion": summary_conclusion,
        }

