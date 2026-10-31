# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry Sqlite - TelemetrySecurityStorageMixin
# =============================================================================
# Description:
#   Миксин фасада хранилища: события безопасности, питание, PID-снимки и файловые события процессов.
#   Вынесено при декомпозиции TelemetryStorage (этап 4 ТЗ оптимизации).
#   Атрибуты хоста: _reader, _writer, _buffer, _maintenance, _aggregator, _cm.
#
# Usage Examples:
#   Python API:
#     from apps.windows.telemetry.sqlite.storage_security import TelemetrySecurityStorageMixin
#
#     class TelemetryStorage(TelemetrySecurityStorageMixin): ...
#
# File: storage_security.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry.sqlite
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-11 11:30:00
# =============================================================================

from __future__ import annotations

"""Миксин фасада хранилища: события безопасности, питание, PID-снимки и файловые события процессов."""

from typing import (
    Any,
    Dict,
    List,
    Optional,
    Union,
)


try:
    from logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class TelemetrySecurityStorageMixin:
    """Миксин фасада хранилища: события безопасности, питание, PID-снимки и файловые события процессов."""

    def save_security_events(
        self,
        events: List[Any],
        save_raw: bool = False,
        raw_events: Optional[List[Any]] = None,
    ) -> int:
        """Сохраняет события безопасности Windows в SQLite."""
        return self._writer.save_security_events(events, save_raw=save_raw, raw_events=raw_events)

    def save_security_bookmark(
        self,
        channel: str,
        last_record_id: int,
        bookmark_xml: Optional[str] = None,
        last_timestamp: str = '',
    ) -> None:
        """Сохраняет состояние закладки сбора событий в SQLite."""
        self._writer.save_security_bookmark(
            channel=channel,
            last_record_id=last_record_id,
            bookmark_xml=bookmark_xml,
            last_timestamp=last_timestamp,
        )

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
        """Выборка нормализованных событий безопасности Windows."""
        return self._reader.get_security_events(
            event_id=event_id,
            user=user,
            process_name=process_name,
            pid=pid,
            channel=channel,
            limit=limit,
            offset=offset,
            since_epoch=since_epoch,
        )

    def get_security_failed_logons(self, limit: int = 50, hours: int = 24) -> List[Dict[str, Any]]:
        """Выборка неудачных попыток входа (Event 4625, 4771)."""
        return self._reader.get_security_failed_logons(limit=limit, hours=hours)

    def get_security_process_creations(
        self,
        process_name: Optional[str] = None,
        user: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Выборка запусков процессов (Event 4688) с командной строкой."""
        return self._reader.get_security_process_creations(
            process_name=process_name,
            user=user,
            limit=limit,
        )

    def get_security_bookmark(self, channel: str = 'Security') -> Optional[Dict[str, Any]]:
        """Получить сохраненную закладку канала."""
        return self._reader.get_security_bookmark(channel=channel)

    def get_security_stats(self) -> Dict[str, Any]:
        """Получить сводную статистику по событиям безопасности."""
        return self._reader.get_security_stats()

    def save_power_events(self, events: List[Any]) -> int:
        """Сохраняет события питания в SQLite."""
        return self._writer.save_power_events(events)

    def save_power_sessions(self, sessions: List[Any]) -> int:
        """Сохраняет реконструированные сессии питания в SQLite."""
        return self._writer.save_power_sessions(sessions)

    def get_power_sessions(
        self,
        limit: int = 50,
        offset: int = 0,
        shutdown_type: Optional[str] = None,
        unexpected_only: bool = False,
        clean_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """Извлечь список сессий питания операционной системы."""
        return self._reader.get_power_sessions(
            limit=limit,
            offset=offset,
            shutdown_type=shutdown_type,
            unexpected_only=unexpected_only,
            clean_only=clean_only,
        )

    def get_power_session_by_id(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Извлечь детальную информацию по конкретной сессии питания."""
        return self._reader.get_power_session_by_id(session_id=session_id)

    def get_power_events(
        self,
        limit: int = 100,
        offset: int = 0,
        event_id: Optional[Union[int, List[int]]] = None,
        event_type: Optional[str] = None,
        hours: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Извлечь события питания и жизненного цикла."""
        return self._reader.get_power_events(
            limit=limit,
            offset=offset,
            event_id=event_id,
            event_type=event_type,
            hours=hours,
        )

    def get_power_summary(self) -> Dict[str, Any]:
        """Получить сводную статистику по сессиям и событиям питания."""
        return self._reader.get_power_summary()

    def get_process_pid_snapshot(self, pid: int) -> Optional[Dict[str, Any]]:
        """Получить последний снимок метрик процесса по PID (< 5 мс)."""
        return self._reader.get_process_pid_snapshot(pid=pid)

    def get_process_file_events(
        self,
        pid: Optional[int] = None,
        directory: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Получить события файловой активности процесса."""
        return self._reader.get_process_file_events(pid=pid, directory=directory, limit=limit)

    def insert_process_pid_snapshots(self, snapshots: List[Union[Dict[str, Any], Any]]) -> int:
        """Сохранить снимки метрик процессов по PID."""
        return self._writer.insert_process_pid_snapshots(snapshots=snapshots)

    def insert_process_file_events(self, events: List[Union[Dict[str, Any], Any]]) -> int:
        """Сохранить события файловой активности."""
        return self._writer.insert_process_file_events(events=events)

