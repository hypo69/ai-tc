# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry Sqlite - TelemetrySnapshotStorageMixin
# =============================================================================
# Description:
#   Миксин фасада хранилища: сохранение и чтение снапшотов, сенсоров, событий, процессов, инцидентов и аудитов.
#   Вынесено при декомпозиции TelemetryStorage (этап 4 ТЗ оптимизации).
#   Атрибуты хоста: _reader, _writer, _buffer, _maintenance, _aggregator, _cm.
#
# Usage Examples:
#   Python API:
#     from apps.windows.telemetry.sqlite.storage_snapshots import TelemetrySnapshotStorageMixin
#
#     class TelemetryStorage(TelemetrySnapshotStorageMixin): ...
#
# File: storage_snapshots.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry.sqlite
# Author: hypo69
# Updated: 2026-10-16 23:05:00
# =============================================================================

from __future__ import annotations

"""Миксин фасада хранилища: сохранение и чтение снапшотов, сенсоров, событий, процессов, инцидентов и аудитов."""

from datetime import datetime, timezone
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Union,
)

from ..models import (
    HardwareArchiveEntry,
    ProcessLifecycleEvent,
    ProcessProvenanceInfo,
    StartupArchiveEntry,
    SystemMetricRollup,
    SystemSnapshot,
    TelemetryIncident,
)

try:
    from logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class TelemetrySnapshotStorageMixin:
    """Миксин фасада хранилища: сохранение и чтение снапшотов, сенсоров, событий, процессов, инцидентов и аудитов."""

    def save_snapshot(self, snapshot: SystemSnapshot, top_n: int = 20) -> int:
        if self._buffer.buffer_mode == 'direct':
            with self._cm.lock, self._cm.get_connection() as conn:
                snap_id = self._writer.insert_snapshot_row(conn.cursor(), {'data': snapshot, 'top_n': top_n})
                conn.commit()
                return snap_id
        snap_dict = snapshot if isinstance(snapshot, dict) else (snapshot.model_dump() if hasattr(snapshot, 'model_dump') else (vars(snapshot) if hasattr(snapshot, '__dict__') else snapshot))
        self._buffer.enqueue({'type': 'snapshot', 'data': snap_dict, 'top_n': top_n})
        return 1

    def save_sensor_poll(self, sensor_item: Dict[str, Any], timestamp: Optional[str] = None) -> int:
        if self._buffer.buffer_mode == 'direct':
            return self._writer.batch_insert_records([{'type': 'sensor_poll', 'data': sensor_item, 'timestamp': timestamp}])
        self._buffer.enqueue({'type': 'sensor_poll', 'data': sensor_item, 'timestamp': timestamp})
        return 1

    def save_sensor_polls_batch(self, items: List[Dict[str, Any]], timestamp: Optional[str] = None, deduplicate: bool = True) -> int:
        if not items:
            return 0
        if deduplicate:
            from ..sensor_registry import SensorDeduplicator, SensorProvider
            deduplicator = SensorDeduplicator()
            for item in items:
                sensor_id = str(item.get('id', ''))
                value = item.get('value', 0.0)
                provider_raw = item.get('_provider', SensorProvider.SENSOR_COLLECTOR)
                if isinstance(provider_raw, str):
                    try:
                        provider = SensorProvider[provider_raw.upper()]
                    except KeyError:
                        provider = SensorProvider.SENSOR_COLLECTOR
                elif isinstance(provider_raw, SensorProvider):
                    provider = provider_raw
                else:
                    provider = SensorProvider.SENSOR_COLLECTOR
                deduplicator.add(sensor_id, provider, value)
            unique_providers = deduplicator.get_unique()
            items = [it for it in items if str(it.get('id', '')) in unique_providers]

        if not items:
            return 0
        if self._buffer.buffer_mode == 'direct':
            return self._writer.batch_insert_records([{'type': 'sensor_polls_batch', 'data': items, 'timestamp': timestamp}])
        self._buffer.enqueue({'type': 'sensor_polls_batch', 'data': items, 'timestamp': timestamp})
        return len(items)

    def save_sensor_aggregates_batch(self, aggregates: List[Dict[str, Any]]) -> int:
        if not aggregates:
            return 0
        if self._buffer.buffer_mode == 'direct':
            return self._writer.batch_insert_records([{'type': 'sensor_aggregates_batch', 'data': aggregates}])
        self._buffer.enqueue({'type': 'sensor_aggregates_batch', 'data': aggregates})
        return len(aggregates)

    def save_event(self, event_type: str, event_details: Dict[str, Any], severity: str = 'info', timestamp: Optional[str] = None) -> int:
        rec = {'type': 'event', 'event_type': event_type, 'details': event_details, 'severity': severity, 'timestamp': timestamp}
        if self._buffer.buffer_mode == 'direct':
            return self._writer.batch_insert_records([rec])
        self._buffer.enqueue(rec)
        return 1

    def save_hardware_archive(self, archive_entry: HardwareArchiveEntry) -> int:
        entry_dict = archive_entry if isinstance(archive_entry, dict) else (archive_entry.model_dump() if hasattr(archive_entry, 'model_dump') else (vars(archive_entry) if hasattr(archive_entry, '__dict__') else archive_entry))
        if self._buffer.buffer_mode == 'direct':
            return self._writer.batch_insert_records([{'type': 'hardware_archive', 'data': entry_dict}])
        self._buffer.enqueue({'type': 'hardware_archive', 'data': entry_dict})
        return 1

    def save_startup_archive(self, archive_entry: StartupArchiveEntry) -> int:
        """Сохраняет снимок аудита автозапуска и зафиксированные изменения в БД."""
        entry_dict = archive_entry if isinstance(archive_entry, dict) else (archive_entry.model_dump() if hasattr(archive_entry, 'model_dump') else (vars(archive_entry) if hasattr(archive_entry, '__dict__') else archive_entry))
        if self._buffer.buffer_mode == 'direct':
            return self._writer.batch_insert_records([{'type': 'startup_archive', 'data': entry_dict}])
        self._buffer.enqueue({'type': 'startup_archive', 'data': entry_dict})
        return 1

    def save_app_poll(self, app: str, poll_type: str, metric_name: str, value: Any, unit: str = '', status: str = 'OK', details: Any = '', timestamp: Optional[str] = None) -> int:
        rec = {'type': 'app_poll', 'app': app, 'poll_type': poll_type, 'metric_name': metric_name, 'value': value, 'unit': unit, 'status': status, 'details': details, 'timestamp': timestamp}
        if self._buffer.buffer_mode == 'direct':
            return self._writer.batch_insert_records([rec])
        self._buffer.enqueue(rec)
        return 1

    def save_app_event(self, app: str, event_type: str, status: str = 'OK', details: Any = '', timestamp: Optional[str] = None) -> int:
        rec = {'type': 'app_event', 'app': app, 'event_type': event_type, 'status': status, 'details': details, 'timestamp': timestamp}
        if self._buffer.buffer_mode == 'direct':
            return self._writer.batch_insert_records([rec])
        self._buffer.enqueue(rec)
        return 1

    def save_app_param_change(self, app: str, param_name: str, old_value: Any, new_value: Any, status: str = 'SUCCESS', user: str = 'system', details: Any = '', timestamp: Optional[str] = None) -> int:
        rec = {'type': 'app_param_change', 'app': app, 'param_name': param_name, 'old_value': old_value, 'new_value': new_value, 'status': status, 'user': user, 'details': details, 'timestamp': timestamp}
        if self._buffer.buffer_mode == 'direct':
            return self._writer.batch_insert_records([rec])
        self._buffer.enqueue(rec)
        return 1

    def save_app_polls_batch(self, polls: List[Dict[str, Any]]) -> int:
        if not polls:
            return 0
        if self._buffer.buffer_mode == 'direct':
            return self._writer.batch_insert_records([{'type': 'app_polls_batch', 'data': polls}])
        self._buffer.enqueue({'type': 'app_polls_batch', 'data': polls})
        return len(polls)

    def save_app_events_batch(self, events: List[Dict[str, Any]]) -> int:
        if not events:
            return 0
        if self._buffer.buffer_mode == 'direct':
            return self._writer.batch_insert_records([{'type': 'app_events_batch', 'data': events}])
        self._buffer.enqueue({'type': 'app_events_batch', 'data': events})
        return len(events)

    def save_app_param_changes_batch(self, param_changes: List[Dict[str, Any]]) -> int:
        if not param_changes:
            return 0
        if self._buffer.buffer_mode == 'direct':
            return self._writer.batch_insert_records([{'type': 'app_param_changes_batch', 'data': param_changes}])
        self._buffer.enqueue({'type': 'app_param_changes_batch', 'data': param_changes})
        return len(param_changes)

    def save_custom_record(self, source_file: str, payload: Dict[str, Any], timestamp: Optional[str] = None) -> int:
        return 0

    def save_device_event(self, event: Dict[str, Any], timestamp: Optional[str] = None) -> int:
        rec = {'type': 'device_event', 'data': event, 'timestamp': timestamp}
        if self._buffer.buffer_mode == 'direct':
            return self._writer.batch_insert_records([rec])
        self._buffer.enqueue(rec)
        return 1

    def save_w64_event(self, event_data: Dict[str, Any], provider: str = 'w64_collector') -> int:
        rec = {'type': 'w64_event', 'data': event_data, 'provider': provider}
        if self._buffer.buffer_mode == 'direct':
            return self._writer.batch_insert_records([rec])
        self._buffer.enqueue(rec)
        return 1

    def save_process_provenance_event(self, event: Union[ProcessLifecycleEvent, ProcessProvenanceInfo, Dict[str, Any]]) -> bool:
        ev_dict = event if isinstance(event, dict) else (event.model_dump() if hasattr(event, 'model_dump') else (vars(event) if hasattr(event, '__dict__') else event))
        if self._buffer.buffer_mode == 'direct':
            return self._writer.batch_insert_records([{'type': 'process_provenance_event', 'data': ev_dict}]) > 0
        self._buffer.enqueue({'type': 'process_provenance_event', 'data': ev_dict})
        return True

    def save_process_provenance_batch(self, events: List[Union[ProcessLifecycleEvent, ProcessProvenanceInfo, Dict[str, Any]]]) -> int:
        if not events:
            return 0
        ev_dicts = [e if isinstance(e, dict) else (e.model_dump() if hasattr(e, 'model_dump') else (vars(e) if hasattr(e, '__dict__') else e)) for e in events]
        if self._buffer.buffer_mode == 'direct':
            return self._writer.batch_insert_records([{'type': 'process_provenance_events_batch', 'data': ev_dicts}])
        self._buffer.enqueue({'type': 'process_provenance_events_batch', 'data': ev_dicts})
        return len(events)

    def save_incident(self, incident: TelemetryIncident) -> bool:
        return self._writer.batch_insert_records([{
            'type': 'incident',
            'data': incident if isinstance(incident, dict) else (incident.model_dump() if hasattr(incident, 'model_dump') else (vars(incident) if hasattr(incident, '__dict__') else incident))
        }]) > 0 or True

    def save_system_rollup(self, rollup: SystemMetricRollup) -> bool:
        return self._writer.batch_insert_records([{
            'type': 'system_rollup',
            'data': rollup if isinstance(rollup, dict) else (rollup.model_dump() if hasattr(rollup, 'model_dump') else (vars(rollup) if hasattr(rollup, '__dict__') else rollup))
        }]) > 0 or True

    def save_reboot_session(self, session: Any) -> int:
        return self._writer.batch_insert_records([{
            'type': 'reboot_session',
            'data': session if isinstance(session, dict) else (session.model_dump() if hasattr(session, 'model_dump') else (vars(session) if hasattr(session, '__dict__') else session))
        }]) or 1

    def save_extended_audit(self, audit: Any, timestamp: Optional[str] = None) -> int:
        return self._writer.batch_insert_records([{
            'type': 'extended_audit',
            'data': audit if isinstance(audit, dict) else (audit.model_dump() if hasattr(audit, 'model_dump') else (vars(audit) if hasattr(audit, '__dict__') else audit)),
            'timestamp': timestamp,
        }]) or 1

    def get_snapshots(self, limit: int = 60, since_epoch: Optional[float] = None) -> List[Dict[str, Any]]:
        return self._reader.get_snapshots(limit=limit, since_epoch=since_epoch)

    def get_latest_snapshot_full(self) -> Optional[Dict[str, Any]]:
        """Извлекает и десериализует последний системный снимок со всеми метаданными и процессами."""
        return self._reader.get_latest_snapshot_full()

    def get_latest_network_profile(self) -> Dict[str, Any]:
        """Извлекает последний зафиксированный в telemetry.db сетевой профиль хоста."""
        return self._reader.get_latest_network_profile()

    def get_latest_cpu(self) -> Optional[Dict[str, Any]]:
        return self._reader.get_latest_cpu()

    def get_cpu_history(self, limit: int = 60, since_epoch: Optional[float] = None) -> List[Dict[str, Any]]:
        return self._reader.get_cpu_history(limit=limit, since_epoch=since_epoch)

    def get_latest_storage_data(self) -> Dict[str, Any]:
        return self._reader.get_latest_storage_data()

    def get_snapshot_processes(self, snapshot_id: int) -> List[Dict[str, Any]]:
        return self._reader.get_snapshot_processes(snapshot_id=snapshot_id)

    def get_process_history(self, name: Optional[str] = None, pid: Optional[int] = None, limit: int = 100) -> List[Dict[str, Any]]:
        return self._reader.get_process_history(name=name, pid=pid, limit=limit)

    def get_process_provenance_history(self, **kwargs: Any) -> List[Dict[str, Any]]:
        return self._reader.get_process_provenance_history(**kwargs)

    def get_process_lineage(self, guid_or_pid: Union[str, int]) -> List[Dict[str, Any]]:
        return self._reader.get_process_lineage(guid_or_pid=guid_or_pid)

    def get_latest_processes(self, limit: int = 50, sort_by: str = 'cpu') -> List[Dict[str, Any]]:
        return self._reader.get_latest_processes(limit=limit, sort_by=sort_by)

    def get_process_stats(self, name: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
        return self._reader.get_process_stats(name=name, limit=limit)

    def get_events(self, event_type: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        return self._reader.get_events(event_type=event_type, limit=limit)

    def get_sensor_history(self, sensor_id: Optional[str] = None, category: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        return self._reader.get_sensor_history(sensor_id=sensor_id, category=category, limit=limit)

    def get_latest_sensors(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        return self._reader.get_latest_sensors(limit=limit)

    def get_cpu_hierarchy_metrics(self) -> Dict[str, Any]:
        """Извлекает иерархические метрики процессора, ядер, потоков и сенсоров из базы телеметрии."""
        return self._reader.get_cpu_hierarchy_metrics()

    def get_app_polls(self, app: Optional[str] = None, metric_name: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        return self._reader.get_app_polls(app=app, metric_name=metric_name, limit=limit)

    def get_app_events(self, app: Optional[str] = None, event_type: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        return self._reader.get_app_events(app=app, event_type=event_type, limit=limit)

    def get_app_param_changes(self, app: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        return self._reader.get_app_param_changes(app=app, limit=limit)

    def get_custom_records(self, source_file: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        return self._reader.get_custom_records(source_file=source_file, limit=limit)

    def get_device_events(self, event_type: Optional[str] = None, device_instance_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        return self._reader.get_device_events(event_type=event_type, device_instance_id=device_instance_id, limit=limit)

    def get_device_install_date(self, device_instance_id: str) -> Optional[str]:
        return self._reader.get_device_install_date(device_instance_id=device_instance_id)

    def get_or_create_device_install_date(
        self,
        device_instance_id: str,
        friendly_name: Optional[str] = None,
        device_class: Optional[str] = None,
        default_date: Optional[str] = None,
    ) -> str:
        """Возвращает существующую дату установки устройства или сохраняет новую."""
        existing = self._reader.get_device_install_date(device_instance_id)
        if existing:
            return existing
        date_to_save = default_date or datetime.now(timezone.utc).strftime('%d.%m.%Y %H:%M')
        if not self.read_only:
            try:
                with self._cm.lock, self._cm.get_connection() as conn:
                    cursor = conn.cursor()
                    self._writer.upsert_device_inventory(
                        cursor=cursor,
                        device_instance_id=device_instance_id,
                        friendly_name=friendly_name,
                        device_class=device_class,
                        install_date=date_to_save,
                    )
                    conn.commit()
            except Exception as ex:
                logger.debug(f'Ошибка сохранения инвентаря устройства: {ex}')
        return date_to_save

    def get_w64_events(self, event_type: Optional[str] = None, provider: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        return self._reader.get_w64_events(event_type=event_type, provider=provider, limit=limit)

    def get_incidents(self, limit: int = 50, trigger_type: Optional[str] = None, severity: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._reader.get_incidents(limit=limit, trigger_type=trigger_type, severity=severity)

    def get_system_rollups(self, tier: str = '1m', start_epoch: Optional[float] = None, end_epoch: Optional[float] = None, limit: int = 100) -> List[Dict[str, Any]]:
        return self._reader.get_system_rollups(tier=tier, start_epoch=start_epoch, end_epoch=end_epoch, limit=limit)

    def get_reboot_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._reader.get_reboot_history(limit=limit)

    def get_latest_reboot_session(self) -> Optional[Dict[str, Any]]:
        return self._reader.get_latest_reboot_session()

    def get_extended_audits(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._reader.get_extended_audits(limit=limit)

    def get_latest_extended_audit(self) -> Optional[Dict[str, Any]]:
        return self._reader.get_latest_extended_audit()

    def get_hardware_audits(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._reader.get_hardware_audits(limit=limit)

    def get_latest_hardware_audit(self) -> Optional[Dict[str, Any]]:
        return self._reader.get_latest_hardware_audit()

    def get_startup_archives(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._reader.get_startup_archives(limit=limit)

    def get_latest_startup_archive(self) -> Optional[Dict[str, Any]]:
        return self._reader.get_latest_startup_archive()

    def get_startup_changes(self, limit: int = 100, archive_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._reader.get_startup_changes(limit=limit, archive_id=archive_id)

    def get_telemetry_rollups(self, level: str = 'hourly', sensor_id: Optional[str] = None, start_epoch: Optional[float] = None, end_epoch: Optional[float] = None, limit: int = 100) -> List[Dict[str, Any]]:
        return self._reader.get_telemetry_rollups(level=level, sensor_id=sensor_id, start_epoch=start_epoch, end_epoch=end_epoch, limit=limit)

    def get_telemetry_spikes(self, sensor_id: Optional[str] = None, start_epoch: Optional[float] = None, limit: int = 100) -> List[Dict[str, Any]]:
        return self._reader.get_telemetry_spikes(sensor_id=sensor_id, start_epoch=start_epoch, limit=limit)

    def get_telemetry_time_ranges(self) -> Dict[str, Any]:
        """Возвращает временные диапазоны и доступные интервалы из БД телеметрии."""
        return self._reader.get_telemetry_time_ranges()

    def get_history_by_interval(self, interval: str = 'seconds', metric: str = 'all', limit: int = 120) -> List[Dict[str, Any]]:
        """Возвращает исторические срезы снимков под указанный интервал."""
        return self._reader.get_history_by_interval(interval=interval, metric=metric, limit=limit)

    def get_process_provenance_analytics(
        self,
        cmdline_pattern: Optional[str] = None,
        name: Optional[str] = None,
        parent_name: Optional[str] = None,
        days: int = 7,
    ) -> Dict[str, Any]:
        """Возвращает многоуровневую аналитику потребления ресурсов процессом."""
        return self._reader.get_process_provenance_analytics(
            cmdline_pattern=cmdline_pattern,
            name=name,
            parent_name=parent_name,
            days=days,
        )

    save_sensor_polls = save_sensor_polls_batch

