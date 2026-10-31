# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Telemetry - Failures Analyzer
# =============================================================================
# Description:
#   Анализатор комплексных сбоев Windows: сбои питания, BSOD (BugCheck),
#   ошибки драйверов и устройств PnP, а также подозрительная активность
#   по данным телеметрии SQLite и системных журналов.
#
# Usage Examples:
#   Python API:
#     from apps.windows.telemetry.failures_analyzer import FailuresAnalyzer
#
#     analyzer = FailuresAnalyzer()
#     summary = analyzer.get_comprehensive_summary(hours=720)
#
# File: failures_analyzer.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-20 09:20:00
# =============================================================================

from __future__ import annotations
"""Анализатор комплексных сбоев Windows: сбои питания, BSOD, ошибки драйверов, краши приложений, WHEA и установки ПО."""

import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

from apps.windows.sdk.win32_ffi.wevtapi import WevtAPI
from apps.windows.sdk.win32_ffi.error_decoder import decode_bugcheck_code, format_system_error
from apps.windows.sdk.core.audits.driver_collector import DriverCollector
from apps.windows.telemetry.power_lifecycle import PowerLifecycleEngine
from apps.windows.telemetry.sqlite import TelemetryStorage


class FailuresAnalyzer:
    """Комплексный анализатор системных сбоев, предвестников отказа железа (WHEA/TDR/Disk), крашей приложений и установок ПО."""

    def __init__(
        self,
        storage: Optional[TelemetryStorage] = None,
        wevtapi: Optional[WevtAPI] = None,
        power_engine: Optional[PowerLifecycleEngine] = None,
        driver_collector: Optional[DriverCollector] = None,
    ) -> None:
        """Инициализация анализатора сбоев.

        Args:
            storage: Экземпляр TelemetryStorage SQLite хранилища.
            wevtapi: Экземпляр WevtAPI для чтения журналов событий.
            power_engine: Экземпляр PowerLifecycleEngine.
            driver_collector: Экземпляр DriverCollector.
        """
        self.storage = storage or TelemetryStorage.get_instance(read_only=True)
        self.wevtapi = wevtapi or WevtAPI()
        self.power_engine = power_engine or PowerLifecycleEngine(wevtapi=self.wevtapi)
        self.driver_collector = driver_collector or DriverCollector()

    def get_comprehensive_summary(self, hours: int = 720) -> Dict[str, Any]:
        """Формирует полную сводную аналитику по всем категориям сбоев, крашей приложений и установок ПО.

        Args:
            hours: Глубина анализа в часах (по умолчанию 720 = 30 дней).

        Returns:
            Dict[str, Any]: Структурированный отчёт для сводной панели WebGUI и AI-диагностики.
        """
        power_failures = self._collect_power_failures(hours=hours)
        bsod_incidents = self._collect_bsod_incidents(hours=hours)
        driver_errors = self._collect_driver_errors(hours=hours)
        suspicious_activity = self._collect_suspicious_activity(hours=hours)
        app_crashes = self._collect_application_crashes_and_exhaustion(hours=hours)
        install_events = self._collect_software_and_update_events(hours=hours)

        # Подсчет ключевых метрик
        power_summary = self.power_engine.get_summary()
        total_sessions = power_summary.total_sessions_count or len(power_failures)
        clean_count = getattr(power_summary, 'clean_shutdowns_count', 0)
        clean_ratio = round((clean_count / total_sessions * 100), 1) if total_sessions > 0 else 100.0

        # Оценка совокупного уровня риска
        risk_score = 0
        if len(bsod_incidents) > 0:
            risk_score += 40
        if len(power_failures) > 0:
            risk_score += min(30, len(power_failures) * 10)
        if any(d.get('severity') == 'critical' for d in driver_errors):
            risk_score += 25
        elif len(driver_errors) > 0:
            risk_score += 15
        if any(s.get('severity') == 'critical' for s in suspicious_activity):
            risk_score += 25
        elif len(suspicious_activity) > 0:
            risk_score += 10
        if any(c.get('severity') == 'critical' for c in app_crashes):
            risk_score += 15

        if risk_score >= 60:
            overall_risk = 'critical'
        elif risk_score >= 25:
            overall_risk = 'warning'
        else:
            overall_risk = 'ok'

        return {
            'status': 'ok',
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'metrics': {
                'power_failures_count': len(power_failures),
                'bsod_count': len(bsod_incidents),
                'driver_errors_count': len(driver_errors),
                'suspicious_activity_count': len(suspicious_activity),
                'app_crashes_count': len(app_crashes),
                'install_events_count': len(install_events),
                'clean_shutdown_ratio': round(clean_ratio, 1),
                'total_sessions': total_sessions,
                'overall_risk': overall_risk,
                'risk_score': min(100, risk_score),
            },
            'power_failures': power_failures,
            'bsod_incidents': bsod_incidents,
            'driver_errors': driver_errors,
            'suspicious_activity': suspicious_activity,
            'app_crashes': app_crashes,
            'install_events': install_events,
        }

    def _collect_power_failures(self, hours: int) -> List[Dict[str, Any]]:
        """Сбор сбоев электропитания (внезапные отключения, Kernel-Power 41, 6008)."""
        failures: List[Dict[str, Any]] = []
        try:
            sessions = self.power_engine.get_sessions(limit=50, unexpected_only=True)
            for s in sessions:
                details = s.details_json if hasattr(s, 'details_json') else {}
                if isinstance(details, str):
                    try:
                        import json
                        details = json.loads(details)
                    except Exception:
                        details = {}

                failures.append({
                    'session_id': s.session_id,
                    'timestamp': s.shutdown_time or s.boot_time,
                    'shutdown_type': s.shutdown_type or 'Unexpected',
                    'uptime_seconds': s.uptime_seconds,
                    'uptime_human': s.uptime_human,
                    'reason': s.reason or 'Внезапный перезапуск / потеря питания',
                    'initiator': s.initiator or 'Hardware / Power Loss',
                    'process': s.process or 'N/A',
                    'boot_event_id': s.boot_event_id,
                    'shutdown_event_id': s.shutdown_event_id,
                    'details': details,
                })
        except Exception as exc:
            logger.warning(f"[FailuresAnalyzer] Ошибка сбора сбоев питания: {exc}")

        try:
            raw_evs = self.wevtapi.read_events(
                channel='System',
                hours=hours,
                event_id=[41, 6008],
                limit=30,
                format_message=True,
            )
            known_times = {f['timestamp'] for f in failures}
            for ev in raw_evs:
                ts = ev.get('timestamp') or ''
                if ts in known_times:
                    continue
                eid = ev.get('event_id', 0)
                msg = ev.get('message') or ev.get('formatted_message') or ''
                ev_data = ev.get('event_data', {}) or {}
                bugcheck_code = ev_data.get('BugcheckCode', '0')
                failures.append({
                    'session_id': f"EV-{eid}-{ev.get('record_id', '')}",
                    'timestamp': ts,
                    'shutdown_type': 'Unexpected',
                    'uptime_seconds': 0,
                    'uptime_human': 'Н/Д',
                    'reason': f"Event ID {eid}: Внезапное отключение питания или сбой ядра",
                    'initiator': 'Microsoft-Windows-Kernel-Power' if eid == 41 else 'EventLog',
                    'process': 'System Kernel',
                    'boot_event_id': eid,
                    'shutdown_event_id': None,
                    'details': {
                        'message': msg,
                        'bugcheck_code': bugcheck_code,
                        'power_button_timestamp': ev_data.get('PowerButtonTimestamp', '0'),
                    },
                })
        except Exception as exc:
            logger.debug(f"[FailuresAnalyzer] WevtAPI чтение событий питания: {exc}")

        return sorted(failures, key=lambda x: x.get('timestamp') or '', reverse=True)

    def _collect_bsod_incidents(self, hours: int) -> List[Dict[str, Any]]:
        """Сбор инцидентов аварийного сбоя ядра (BSOD, BugCheck, WER 1001)."""
        incidents: List[Dict[str, Any]] = []
        try:
            raw_bsod = self.wevtapi.read_events(
                channel='System',
                hours=hours,
                event_id=[1001, 41],
                limit=50,
                format_message=True,
            )
            for ev in raw_bsod:
                eid = ev.get('event_id', 0)
                ev_data = ev.get('event_data', {}) or {}
                msg = ev.get('message') or ev.get('formatted_message') or ''
                bc_code_raw = ev_data.get('BugcheckCode') or ev_data.get('param1')

                if eid == 41 and (not bc_code_raw or str(bc_code_raw) in ('0', '0x0')):
                    continue

                if eid == 1001:
                    prov = (ev.get('provider') or '').lower()
                    if 'bugcheck' not in prov and 'systemerrorreporting' not in prov and 'wer' not in prov and 'save dump' not in msg.lower():
                        continue

                bc_symbol = ''
                bc_desc = ''
                bc_hex = ''
                if bc_code_raw:
                    try:
                        bc_int = int(str(bc_code_raw), 0 if str(bc_code_raw).startswith('0x') else 10)
                        bc_hex = hex(bc_int).upper()
                        decoded = decode_bugcheck_code(bc_int)
                        bc_symbol = decoded.get('symbol', '')
                        bc_desc = decoded.get('name', '') or decoded.get('description', '')
                    except Exception:
                        bc_hex = str(bc_code_raw)

                if not bc_desc:
                    bc_desc = 'Критический сбой ядра (Blue Screen of Death / BugCheck)'

                params = [ev_data.get(f'param{i}') for i in range(1, 6) if ev_data.get(f'param{i}')]

                incidents.append({
                    'id': f"BSOD-{ev.get('record_id', '')}",
                    'timestamp': ev.get('timestamp') or '',
                    'event_id': eid,
                    'provider': ev.get('provider', 'BugCheck'),
                    'bugcheck_code': bc_hex or '0x00000000',
                    'bugcheck_symbol': bc_symbol or 'BUGCHECK_UNKNOWN',
                    'description': bc_desc,
                    'message': msg,
                    'params': params,
                    'computer': ev.get('computer', ''),
                    'severity': 'critical',
                })
        except Exception as exc:
            logger.warning(f"[FailuresAnalyzer] Ошибка сбора BSOD: {exc}")

        return sorted(incidents, key=lambda x: x.get('timestamp') or '', reverse=True)

    def _collect_driver_errors(self, hours: int) -> List[Dict[str, Any]]:
        """Сбор проблемных устройств PnP, ошибок драйверов, WHEA-Logger, TDR видеодрайвера (4101) и ошибок дисков/NTFS."""
        errors: List[Dict[str, Any]] = []

        # 1. Проблемные физические PnP-устройства через DriverCollector (SetupAPI)
        try:
            audit = self.driver_collector.collect()
            for finding in audit.findings:
                ev_data = finding.evidence if isinstance(finding.evidence, dict) else {}
                errors.append({
                    'source': 'pnp_device',
                    'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
                    'name': ev_data.get('FriendlyName') or finding.title,
                    'instance_id': ev_data.get('InstanceId', ''),
                    'device_class': ev_data.get('Class', 'Device'),
                    'error_code': ev_data.get('ProblemCode') or 'Problem',
                    'status': ev_data.get('Status', 'Error'),
                    'message': finding.description,
                    'severity': 'critical' if str(ev_data.get('ProblemCode')) in ('10', '43') else 'warning',
                    'remediation_cmd': finding.actions[0].execution_command if finding.actions else None,
                })
        except Exception as exc:
            logger.warning(f"[FailuresAnalyzer] Ошибка сбора проблемных устройств PnP: {exc}")

        # 2. Ошибки драйверов, WHEA (17, 18, 19, 47), TDR видеокарты (4101), сбои диска/NVMe/NTFS (7, 11, 51, 55, 129, 130)
        try:
            target_ids = [219, 7000, 7026, 411, 17, 18, 19, 20, 47, 4101, 7, 11, 51, 55, 129, 130]
            log_evs = self.wevtapi.read_events(
                channel='System',
                hours=hours,
                event_id=target_ids,
                limit=60,
                format_message=True,
            )
            for ev in log_evs:
                eid = ev.get('event_id', 0)
                msg = ev.get('message') or ev.get('formatted_message') or ''
                prov = ev.get('provider', '') or ''
                prov_low = prov.lower()

                # Фильтрация общих Event ID (7, 11, 17, 51, 55, 129, 130) только по аппаратным провайдерам
                if eid in (7, 11, 51, 129) and not any(k in prov_low for k in ('disk', 'stornvme', 'storahci', 'nvme', 'iaStor', 'partmgr', 'volmgr')):
                    continue
                if eid in (55, 130) and 'ntfs' not in prov_low:
                    continue
                if eid in (17, 18, 19, 47) and 'whea' not in prov_low and 'kernel' not in prov_low:
                    continue

                drv_name = prov or 'Системный компонент'
                status_tag = 'DriverError'
                severity = 'warning'

                if eid == 4101 or 'display' in prov_low:
                    drv_name = 'GPU Display Driver (TDR Reset)'
                    status_tag = 'GPU_TDR_Reset'
                    severity = 'critical'
                elif 'whea' in prov_low or eid in (17, 18, 19, 47):
                    drv_name = f'WHEA Hardware Error (ID {eid})'
                    status_tag = 'WHEA_Hardware_Error'
                    severity = 'critical' if eid in (18, 47) else 'warning'
                elif eid in (7, 11, 51, 129):
                    drv_name = f'Storage Controller / Disk ({prov})'
                    status_tag = 'Storage_IO_Error'
                    severity = 'critical' if eid in (7, 11, 129) else 'warning'
                elif eid in (55, 130):
                    drv_name = 'NTFS File System Corruption'
                    status_tag = 'NTFS_Corruption'
                    severity = 'critical'
                else:
                    m_drv = re.search(r'\\Driver\\([^\s,\.]+)', msg, re.IGNORECASE)
                    if m_drv:
                        drv_name = m_drv.group(1)
                    else:
                        m_srv = re.search(r'Служба\s+"([^"]+)"|service\s+"([^"]+)"', msg, re.IGNORECASE)
                        if m_srv:
                            drv_name = m_srv.group(1) or m_srv.group(2) or prov
                    if eid in (219, 7026):
                        status_tag = 'LoadFailed'

                errors.append({
                    'source': 'system_log',
                    'timestamp': ev.get('timestamp') or '',
                    'name': drv_name,
                    'instance_id': f"EV-{eid}-{ev.get('record_id', '')}",
                    'device_class': prov,
                    'error_code': f"Event {eid}",
                    'status': status_tag,
                    'message': msg,
                    'severity': severity,
                    'remediation_cmd': 'chkdsk /scan' if status_tag == 'NTFS_Corruption' else f"Get-Service -Name '{drv_name}' -ErrorAction SilentlyContinue",
                })
        except Exception as exc:
            logger.debug(f"[FailuresAnalyzer] WevtAPI чтение ошибок драйверов/железа: {exc}")

        return sorted(errors, key=lambda x: x.get('timestamp') or '', reverse=True)

    def _collect_application_crashes_and_exhaustion(self, hours: int) -> List[Dict[str, Any]]:
        """Сбор крашей приложений (Event 1000), зависаний UI (Event 1002) и исчерпания памяти (Event 2004)."""
        crashes: List[Dict[str, Any]] = []
        try:
            app_evs = self.wevtapi.read_events(
                channel='Application',
                hours=hours,
                event_id=[1000, 1002],
                limit=40,
                format_message=True,
            )
            for ev in app_evs:
                eid = ev.get('event_id', 0)
                prov = (ev.get('provider') or '').lower()
                if eid == 1000 and 'application error' not in prov:
                    continue
                if eid == 1002 and 'application hang' not in prov:
                    continue
                msg = ev.get('message') or ev.get('formatted_message') or ''
                ev_data = ev.get('event_data', {}) or {}
                app_name = ev_data.get('param1') or ev_data.get('AppName') or 'Application'
                fault_module = ev_data.get('param4') or ev_data.get('ModName') or ''
                exc_code = ev_data.get('param7') or ev_data.get('ExceptionCode') or ''
                crashes.append({
                    'id': f"APP-{eid}-{ev.get('record_id', '')}",
                    'timestamp': ev.get('timestamp') or '',
                    'event_id': eid,
                    'type': 'Application Crash' if eid == 1000 else 'Application Hang (UI Freeze)',
                    'app_name': app_name,
                    'faulting_module': fault_module,
                    'exception_code': exc_code,
                    'message': msg,
                    'severity': 'critical' if eid == 1000 else 'warning',
                })
        except Exception as exc:
            logger.debug(f"[FailuresAnalyzer] Ошибка чтения крашей приложений: {exc}")

        # Проверка Resource-Exhaustion-Detector (Event ID 2004 в System)
        try:
            res_evs = self.wevtapi.read_events(
                channel='System',
                hours=hours,
                event_id=[2004],
                limit=15,
                format_message=True,
            )
            for ev in res_evs:
                prov = (ev.get('provider') or '').lower()
                if 'resource-exhaustion' not in prov:
                    continue
                msg = ev.get('message') or ev.get('formatted_message') or ''
                crashes.append({
                    'id': f"OOM-2004-{ev.get('record_id', '')}",
                    'timestamp': ev.get('timestamp') or '',
                    'event_id': 2004,
                    'type': 'Virtual Memory Exhaustion (OOM)',
                    'app_name': 'Windows Memory Manager',
                    'faulting_module': 'Pagefile / Commit Charge',
                    'exception_code': 'RESOURCE_EXHAUSTION',
                    'message': msg,
                    'severity': 'critical',
                })
        except Exception as exc:
            logger.debug(f"[FailuresAnalyzer] Ошибка чтения Resource-Exhaustion: {exc}")

        return sorted(crashes, key=lambda x: x.get('timestamp') or '', reverse=True)

    def _collect_software_and_update_events(self, hours: int) -> List[Dict[str, Any]]:
        """Сбор хронологии установок/удалений программ (MsiInstaller) и обновлений Windows Update (19/20)."""
        events: List[Dict[str, Any]] = []
        try:
            msi_evs = self.wevtapi.read_events(
                channel='Application',
                hours=hours,
                event_id=[1033, 1034, 11707, 11724],
                limit=35,
                format_message=True,
            )
            for ev in msi_evs:
                prov = (ev.get('provider') or '').lower()
                if 'msiinstaller' not in prov:
                    continue
                eid = ev.get('event_id', 0)
                msg = ev.get('message') or ev.get('formatted_message') or ''
                action = 'Install' if eid in (1033, 11707) else 'Uninstall'
                events.append({
                    'id': f"MSI-{eid}-{ev.get('record_id', '')}",
                    'timestamp': ev.get('timestamp') or '',
                    'event_id': eid,
                    'source': 'MsiInstaller',
                    'action': action,
                    'message': msg,
                    'status': 'success',
                })
        except Exception as exc:
            logger.debug(f"[FailuresAnalyzer] Ошибка чтения MsiInstaller: {exc}")

        try:
            wu_evs = self.wevtapi.read_events(
                channel='System',
                hours=hours,
                event_id=[19, 20],
                limit=25,
                format_message=True,
            )
            for ev in wu_evs:
                prov = (ev.get('provider') or '').lower()
                if 'windowsupdateclient' not in prov:
                    continue
                eid = ev.get('event_id', 0)
                msg = ev.get('message') or ev.get('formatted_message') or ''
                events.append({
                    'id': f"WU-{eid}-{ev.get('record_id', '')}",
                    'timestamp': ev.get('timestamp') or '',
                    'event_id': eid,
                    'source': 'WindowsUpdateClient',
                    'action': 'Update Installed' if eid == 19 else 'Update Failed',
                    'message': msg,
                    'status': 'success' if eid == 19 else 'error',
                })
        except Exception as exc:
            logger.debug(f"[FailuresAnalyzer] Ошибка чтения WindowsUpdateClient: {exc}")

        return sorted(events, key=lambda x: x.get('timestamp') or '', reverse=True)

    def _collect_suspicious_activity(self, hours: int) -> List[Dict[str, Any]]:
        """Анализ подозрительной активности на основе телеметрии процессов, крашей и событий безопасности."""
        activities: List[Dict[str, Any]] = []

        # 1. Поиск аномальных процессов в базе телеметрии (из Temp, AppData, с утечками или чрезмерным CPU)
        try:
            from .telemetry_config import get_telemetry_config_manager
            th = get_telemetry_config_manager().get_thresholds_config()
            high_cpu_pct = float(th.get('individual_process_high_cpu_pct', 50.0))
            crit_cpu_pct = float(th.get('incident_cpu_pct', 90.0))
            warn_handles = int(th.get('leak_critical_handles', 4000))
            severe_handles = int(th.get('leak_severe_handles', 10000))

            conn = self.storage.get_connection()
            cur = conn.cursor()

            cur.execute(
                """
                SELECT pid, name, executable, cpu_percent, memory_mb, num_handles, timestamp
                FROM process_snapshots
                WHERE cpu_percent >= ? OR num_handles >= ?
                ORDER BY id DESC LIMIT 25
                """,
                (high_cpu_pct, warn_handles),
            )
            for row in cur.fetchall():
                pid = row['pid']
                name = row['name'] or 'Unknown'
                path = row['executable'] or ''
                cpu = float(row['cpu_percent'] or 0.0)
                ws_mb = round(float(row['memory_mb'] or 0), 1)
                handles = int(row['num_handles'] or 0)
                ts = row['timestamp'] or ''

                reasons = []
                severity = 'warning'
                if cpu >= crit_cpu_pct:
                    reasons.append(f"Чрезвычайная нагрузка на CPU: {cpu:.1f}%")
                    severity = 'critical'
                elif cpu >= high_cpu_pct:
                    reasons.append(f"Высокая нагрузка на CPU: {cpu:.1f}%")

                if handles >= severe_handles:
                    reasons.append(f"Критическая утечка дескрипторов (Handles): {handles}")
                    severity = 'critical'
                elif handles >= warn_handles:
                    reasons.append(f"Повышенное число дескрипторов: {handles}")

                lower_path = path.lower()
                if '\\temp\\' in lower_path or '\\tmp\\' in lower_path:
                    reasons.append("Запуск исполняемого файла из временного каталога (Temp)")
                    severity = 'critical'

                if reasons:
                    activities.append({
                        'id': f"SUSP-PROC-{pid}-{ts}",
                        'category': 'process_anomaly',
                        'timestamp': ts,
                        'title': f"Аномалия процесса: {name} (PID {pid})",
                        'process_name': name,
                        'pid': pid,
                        'executable_path': path,
                        'description': '; '.join(reasons),
                        'metrics': {'cpu_pct': cpu, 'ram_mb': ws_mb, 'handles': handles},
                        'severity': severity,
                    })

            # 2. Всплески телеметрии (incidents WHERE domain = 'spike')
            cur.execute("""
                SELECT sensor_id, timestamp, value, trigger_type AS spike_type, details_json AS details
                FROM incidents
                WHERE domain = 'spike'
                ORDER BY id DESC LIMIT 15
            """)
            for row in cur.fetchall():
                sensor = row['sensor_id'] or 'Sensor'
                ts = row['timestamp'] or ''
                val = row['value']
                spike_type = row['spike_type'] or 'spike'
                details = row['details'] or ''
                activities.append({
                    'id': f"SPIKE-{sensor}-{ts}",
                    'category': 'telemetry_spike',
                    'timestamp': ts,
                    'title': f"Всплеск телеметрии: {sensor}",
                    'process_name': 'Telemetry Sensor Engine',
                    'pid': 0,
                    'executable_path': '',
                    'description': f"Аномальное отклонение метрики ({spike_type}): {details or val}",
                    'metrics': {'value': val, 'spike_type': spike_type},
                    'severity': 'info' if 'ping' in sensor else 'warning',
                })

            # 3. События безопасности Defender (CFA блокировки 1121, ASR 1123, угрозы 1116)
            try:
                def_evs = self.wevtapi.read_events(
                    channel='Microsoft-Windows-Windows Defender/Operational',
                    hours=hours,
                    event_id=[1116, 1117, 1121, 1123, 1127],
                    limit=20,
                    format_message=True,
                )
                for ev in def_evs:
                    eid = ev.get('event_id', 0)
                    msg = ev.get('message') or ev.get('formatted_message') or ''
                    ev_data = ev.get('event_data', {}) or {}
                    threat_name = ev_data.get('Threat Name') or ev_data.get('Path') or 'Security Event'
                    proc = ev_data.get('Process Name') or 'Unknown'
                    activities.append({
                        'id': f"DEF-{eid}-{ev.get('record_id', '')}",
                        'category': 'defender_alert',
                        'timestamp': ev.get('timestamp') or '',
                        'title': f"Defender Alert [ID {eid}]: {threat_name}",
                        'process_name': proc,
                        'pid': ev.get('process_id', 0),
                        'executable_path': ev_data.get('Path', ''),
                        'description': msg or f"Зафиксирована активность безопасности Defender (ID {eid})",
                        'metrics': {'event_id': eid},
                        'severity': 'critical' if eid in (1116, 1117) else 'warning',
                    })
            except Exception as exc:
                logger.debug(f"[FailuresAnalyzer] WevtAPI чтение Defender alerts: {exc}")

        except Exception as exc:
            logger.warning(f"[FailuresAnalyzer] Ошибка сбора аномалий телеметрии: {exc}")

        return sorted(activities, key=lambda x: x.get('timestamp') or '', reverse=True)


