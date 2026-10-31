# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry Sqlite - TelemetryAuditStorageMixin
# =============================================================================
# Description:
#   Миксин фасада хранилища: журналы событий, firewall, службы, троттлинг, форензика, Defender, ПО.
#   Вынесено при декомпозиции TelemetryStorage (этап 4 ТЗ оптимизации).
#   Атрибуты хоста: _reader, _writer, _buffer, _maintenance, _aggregator, _cm.
#
# Usage Examples:
#   Python API:
#     from apps.windows.telemetry.sqlite.storage_audits import TelemetryAuditStorageMixin
#
#     class TelemetryStorage(TelemetryAuditStorageMixin): ...
#
# File: storage_audits.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry.sqlite
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-20 20:20:00
# =============================================================================

from __future__ import annotations

"""Миксин фасада хранилища: журналы событий, firewall, службы, троттлинг, форензика, Defender, ПО."""

from typing import (
    Any,
    Dict,
    List,
    Optional,
)


try:
    from logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class TelemetryAuditStorageMixin:
    """Миксин фасада хранилища: журналы событий, firewall, службы, троттлинг, форензика, Defender, ПО."""

    def save_event_log_snapshot(self, snapshot_id: str, channels: List[Any], entries: List[Any], intelligence_profiles: Optional[List[Any]] = None) -> int:
        return self._writer.save_event_log_snapshot(snapshot_id, channels, entries, intelligence_profiles)

    def get_latest_event_log_channels(self) -> List[Dict[str, Any]]:
        return self._reader.get_latest_event_log_channels()

    def get_event_log_entries(self, channel: str = 'System', level: str = '', limit: int = 50, hours: int = 24) -> List[Dict[str, Any]]:
        return self._reader.get_event_log_entries(channel=channel, level=level, limit=limit, hours=hours)

    def get_latest_event_log_intelligence_profile(self, channel: str = 'System') -> Optional[Dict[str, Any]]:
        return self._reader.get_latest_event_log_intelligence_profile(channel=channel)

    def get_latest_event_log_report(self) -> Optional[Dict[str, Any]]:
        return self._reader.get_latest_event_log_report()

    def save_firewall_snapshot(self, snapshot_id: str, profiles: Any, rules: List[Any]) -> int:
        return self._writer.save_firewall_snapshot(snapshot_id, profiles, rules)

    def update_firewall_rule_state(self, rule_name: str, enabled: bool) -> bool:
        return self._writer.update_firewall_rule_state(rule_name, enabled)

    def get_latest_firewall_profiles(self) -> Optional[Dict[str, Any]]:
        return self._reader.get_latest_firewall_profiles()

    def get_latest_firewall_rules(self, direction: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
        return self._reader.get_latest_firewall_rules(direction=direction, limit=limit)

    def save_services_snapshot(self, snapshot_id: str, services: List[Any]) -> int:
        return self._writer.save_services_snapshot(snapshot_id, services)

    def record_service_change(self, service_name: str, display_name: str, action: str, old_state: Optional[str] = None, new_state: Optional[str] = None, performed_by: str = 'SYSTEM', details: Optional[Dict[str, Any]] = None) -> int:
        return self._writer.record_service_change(service_name, display_name, action, old_state, new_state, performed_by, details)

    def get_latest_services_list(self, status: Optional[str] = None, limit: int = 500) -> List[Dict[str, Any]]:
        return self._reader.get_latest_services_list(status=status, limit=limit)

    def get_latest_services_report(self) -> Optional[Dict[str, Any]]:
        return self._reader.get_latest_services_report()

    def get_inventory_changes(self, domain: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Журнал дельт инвентаризации (added/removed/modified) с датой обнаружения."""
        return self._reader.get_inventory_changes(domain=domain, limit=limit)

    def get_service_change_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._reader.get_service_change_events(limit=limit)

    def save_throttling_snapshot(self, snapshot_id: str, throttling_data: Any, thermal_zones: Optional[List[Any]] = None) -> int:
        return self._writer.save_throttling_snapshot(snapshot_id, throttling_data, thermal_zones)

    def get_latest_throttling_snapshot(self) -> Optional[Dict[str, Any]]:
        return self._reader.get_latest_throttling_snapshot()

    def save_forensics_snapshot(self, snapshot_id: str, forensics_data: Any) -> int:
        return self._writer.save_forensics_snapshot(snapshot_id, forensics_data)

    def get_latest_forensics_snapshot(self) -> Optional[Dict[str, Any]]:
        return self._reader.get_latest_forensics_snapshot()

    def get_forensics_history(self, limit: int = 50, hours: float = 24.0) -> List[Dict[str, Any]]:
        return self._reader.get_forensics_history(limit=limit, hours=hours)

    def save_process_leak_snapshot(self, snapshot_id: str, total_processes: Any, suspicious_count: int = 0, leak_items: Optional[List[Any]] = None) -> int:
        return self._writer.save_process_leak_snapshot(snapshot_id, total_processes, suspicious_count, leak_items)

    def get_latest_process_leak_report(self, limit: int = 20) -> Optional[Dict[str, Any]]:
        return self._reader.get_latest_process_leak_report(limit=limit)

    def save_defender_snapshot(self, snapshot_id: str, defender_status: Any, exclusions: Optional[List[Any]] = None, asr_rules: Optional[List[Any]] = None, threats: Optional[List[Any]] = None) -> int:
        return self._writer.save_defender_snapshot(snapshot_id, defender_status, exclusions, asr_rules, threats)

    def get_latest_defender_status(self) -> Optional[Dict[str, Any]]:
        return self._reader.get_latest_defender_status()

    def get_latest_defender_exclusions(self, limit: int = 200) -> List[Dict[str, Any]]:
        return self._reader.get_latest_defender_exclusions(limit=limit)

    def get_latest_defender_asr_rules(self) -> List[Dict[str, Any]]:
        return self._reader.get_latest_defender_asr_rules()

    def get_latest_defender_threats(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._reader.get_latest_defender_threats(limit=limit)

    def get_latest_defender_diagnostics(self) -> Dict[str, Any]:
        return self._reader.get_latest_defender_diagnostics()

    def save_process_network_snapshot(self, snapshot_id: str, network_items: List[Any]) -> int:
        return self._writer.save_process_network_snapshot(snapshot_id, network_items)

    def get_latest_process_network_activity(self, limit: int = 100, only_internet: bool = True) -> List[Dict[str, Any]]:
        return self._reader.get_latest_process_network_activity(limit=limit, only_internet=only_internet)

    def save_software_inventory(self, apps: List[Any], storage_locations: Optional[List[Any]] = None, config_files: Optional[List[Any]] = None, ai_research: Optional[List[Any]] = None) -> int:
        return self._writer.save_software_inventory(apps, storage_locations, config_files, ai_research)

    def save_software_audit_report(self, report: Any) -> int:
        return self._writer.save_software_audit_report(report)

    def save_software_scanner_report(self, report: Any) -> int:
        return self._writer.save_software_scanner_report(report)

    def get_latest_software_audit_report(self) -> Optional[Dict[str, Any]]:
        return self._reader.get_latest_software_audit_report()

    def get_latest_software_scanner_report(self) -> Optional[Dict[str, Any]]:
        return self._reader.get_latest_software_scanner_report()

    def get_dormant_software_from_db(self, min_days: int = 90) -> List[Dict[str, Any]]:
        return self._reader.get_dormant_software_from_db(min_days=min_days)

    def get_orphan_software_from_db(self) -> List[Dict[str, Any]]:
        return self._reader.get_orphan_software_from_db()

    def get_software_audit_reports_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        return self._reader.get_software_audit_reports_history(limit=limit)

    def save_software_network_snapshots(self, snapshot_id: str, net_items: List[Any]) -> int:
        return self._writer.save_software_network_snapshots(snapshot_id, net_items)

    def get_software_inventory_from_db(self, limit: int = 200, offset: int = 0) -> List[Dict[str, Any]]:
        return self._reader.get_software_inventory_from_db(limit=limit, offset=offset)

    def get_software_app_details_from_db(self, app_id: str) -> Optional[Dict[str, Any]]:
        return self._reader.get_software_app_details_from_db(app_id=app_id)

    def save_process_audit_sample(self, sample: Any) -> Optional[int]:
        """Сохранение снимка глубокого аудита процесса по PID в SQLite."""
        return self._writer.save_process_audit_sample(sample)

    def get_process_audit_history(self, pid: int, limit: int = 100) -> List[Dict[str, Any]]:
        """Извлечение истории глубокого аудита процесса по PID из SQLite."""
        return self._reader.get_process_audit_history(pid=pid, limit=limit)

    def upsert_process_lifecycle_session(self, session: Any) -> bool:
        """Сохранение или обновление сессии процесса по instance_id."""
        return self._writer.upsert_process_lifecycle_session(session)

    def get_process_lifecycle_sessions(
        self,
        app_name: Optional[str] = None,
        username: Optional[str] = None,
        parent_name: Optional[str] = None,
        pid: Optional[int] = None,
        is_alive: Optional[bool] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Извлечение сессий жизненного цикла процессов с фильтрацией."""
        return self._reader.get_process_lifecycle_sessions(
            app_name=app_name,
            username=username,
            parent_name=parent_name,
            pid=pid,
            is_alive=is_alive,
            limit=limit,
        )

    def get_process_lifecycle_by_instance_id(self, instance_id: str) -> Optional[Dict[str, Any]]:
        """Извлечение сессии процесса по уникальному instance_id."""
        return self._reader.get_process_lifecycle_by_instance_id(instance_id)

    def get_app_summary_report(
        self, app_name: Optional[str] = None, username: Optional[str] = None
    ) -> Dict[str, Any]:
        """Сводный отчет по запускам приложений, пользователям и инициаторам."""
        return self._reader.get_app_summary_report(app_name=app_name, username=username)

    def get_process_incident_timeline(self, pid: int, limit: int = 100) -> Optional[Dict[str, Any]]:
        """Восстановление хроники инцидента процесса (CPU, RAM, Диск, Сеть)."""
        return self._reader.get_process_incident_timeline(pid=pid, limit=limit)

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
        """Сохранение записи изменения конфигурации оборудования (как было и как стало)."""
        return self._writer.save_hardware_config_change(
            component_type=component_type,
            change_type=change_type,
            component_name=component_name,
            old_config=old_config,
            new_config=new_config,
            summary=summary,
            timestamp=timestamp,
            created_at=created_at,
        )

    def get_hardware_config_changes(
        self, component_type: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Получение истории изменений конфигурации оборудования."""
        return self._reader.get_hardware_config_changes(component_type=component_type, limit=limit)

    def save_live_stream_session(self, session_data: Dict[str, Any]) -> bool:
        """Сохранение компактного отчета ресурсопотребления сессии live stream."""
        return self._writer.save_live_stream_session(session_data)

    def finalize_live_stream_session(
        self,
        session_id: str,
        started_ts: float,
        ended_ts: float,
        trigger_source: str = 'manual',
        hardware_signature: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Финализация сессии live stream и генерация компактного профиля потребления ресурсов."""
        return self._writer.finalize_live_stream_session(
            session_id=session_id,
            started_ts=started_ts,
            ended_ts=ended_ts,
            trigger_source=trigger_source,
            hardware_signature=hardware_signature,
        )

    def compact_live_stream_data(self, keep_last_snapshots: int = 5) -> Dict[str, int]:
        """Компактификация секундных тиков live stream для предотвращения роста БД."""
        return self._writer.compact_live_stream_data(keep_last_snapshots=keep_last_snapshots)

    def get_live_stream_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Получение списка отчетов завершенных сессий live stream."""
        return self._reader.get_live_stream_sessions(limit=limit)

    def get_live_stream_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Получение отчета по конкретной сессии live stream."""
        return self._reader.get_live_stream_session(session_id)

    def get_hardware_comparison_report(
        self,
        change_id: Optional[int] = None,
        component_type: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Формирование сравнительного отчета производительности до и после апгрейда оборудования («Было / Стало»)."""
        return self._reader.get_hardware_comparison_report(
            change_id=change_id, component_type=component_type
        )


