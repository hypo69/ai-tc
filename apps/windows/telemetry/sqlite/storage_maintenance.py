# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry Sqlite - TelemetryMaintenanceStorageMixin
# =============================================================================
# Description:
#   Миксин фасада хранилища: обслуживание БД (размер, WAL, vacuum, очистка) и агрегация.
#   Вынесено при декомпозиции TelemetryStorage (этап 4 ТЗ оптимизации).
#   Атрибуты хоста: _reader, _writer, _buffer, _maintenance, _aggregator, _cm.
#
# Usage Examples:
#   Python API:
#     from apps.windows.telemetry.sqlite.storage_maintenance import TelemetryMaintenanceStorageMixin
#
#     class TelemetryStorage(TelemetryMaintenanceStorageMixin): ...
#
# File: storage_maintenance.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry.sqlite
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-30 13:05:00
# =============================================================================

from __future__ import annotations

"""Миксин фасада хранилища: обслуживание БД (размер, WAL, vacuum, очистка) и агрегация."""

from typing import (
    Any,
    Dict,
    Optional,
    Union,
)

from .aggregator import AggregationLevel

try:
    from logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class TelemetryMaintenanceStorageMixin:
    """Миксин фасада хранилища: обслуживание БД (размер, WAL, vacuum, очистка) и агрегация."""

    def get_db_file_sizes(self) -> Dict[str, int]:
        return self._maintenance.get_db_file_sizes()

    def get_total_db_size_mb(self) -> float:
        return self._maintenance.get_total_db_size_mb()

    def checkpoint_wal(self) -> bool:
        return self._maintenance.checkpoint_wal()

    def vacuum(self) -> bool:
        return self._maintenance.vacuum()

    def get_storage_stats(self) -> Dict[str, Any]:
        return self._maintenance.get_storage_stats(
            buffered_count=self.get_buffered_count(),
            buffer_mode=self.get_buffer_mode(),
            buffer_size=self._buffer.buffer_size,
            flush_interval_seconds=self._buffer.flush_interval_seconds,
        )

    def cleanup_old_records(self, retention_days: Optional[int] = None, vacuum_after: bool = False) -> int:
        return self._maintenance.cleanup_old_records(retention_days=retention_days, vacuum_after=vacuum_after)

    def purge_live_stream_tables(self, vacuum: bool = True) -> Dict[str, int]:
        """Очищает таблицы потокового режима live stream и сбрасывает кэш в памяти."""
        if hasattr(self, '_buffer') and self._buffer is not None:
            self._buffer.clear()
        if hasattr(self, '_writer') and hasattr(self._writer, 'delta_tracker'):
            self._writer.delta_tracker.reset()
        return self._maintenance.purge_live_stream_tables(vacuum=vacuum)

    def enforce_size_limit(self, max_size_mb: Optional[float] = None, target_ratio: float = 0.85) -> Dict[str, Any]:
        return self._maintenance.enforce_size_limit(max_size_mb=max_size_mb, target_ratio=target_ratio)

    def prune_to_size(self, target_size_mb: float) -> Dict[str, Any]:
        return self.enforce_size_limit(max_size_mb=target_size_mb, target_ratio=0.95)

    def run_tiered_compaction(self, thorough_mode: bool = False, now_epoch: Optional[float] = None) -> Dict[str, Any]:
        """Запускает каскадное многоуровневое усреднение снимков (5с -> 30с -> 3м -> 10м -> 36ч)."""
        return self._maintenance.run_tiered_compaction(thorough_mode=thorough_mode, now_epoch=now_epoch)

    def purge_history(self, retention_days: int) -> int:
        """Удаляет историю железа и приложений старше срока (0 — хранить вечно)."""
        return self._maintenance.purge_history(retention_days)

    def aggregate_sensors(self, level: Union[AggregationLevel, str], start_epoch: Optional[float] = None, end_epoch: Optional[float] = None, detect_spikes: bool = True) -> Dict[str, Any]:
        return self._aggregator.aggregate(level=level, start_epoch=start_epoch, end_epoch=end_epoch, detect_spikes=detect_spikes)

    def aggregate_hourly(self, start_epoch: Optional[float] = None, end_epoch: Optional[float] = None, detect_spikes: bool = True) -> Dict[str, Any]:
        return self._aggregator.aggregate_hourly(start_epoch=start_epoch, end_epoch=end_epoch, detect_spikes=detect_spikes)

    def aggregate_daily(self, start_epoch: Optional[float] = None, end_epoch: Optional[float] = None) -> Dict[str, Any]:
        return self._aggregator.aggregate_daily(start_epoch=start_epoch, end_epoch=end_epoch)

    def aggregate_weekly(self, start_epoch: Optional[float] = None, end_epoch: Optional[float] = None) -> Dict[str, Any]:
        return self._aggregator.aggregate_weekly(start_epoch=start_epoch, end_epoch=end_epoch)

    def aggregate_monthly(self, start_epoch: Optional[float] = None, end_epoch: Optional[float] = None) -> Dict[str, Any]:
        return self._aggregator.aggregate_monthly(start_epoch=start_epoch, end_epoch=end_epoch)

    def aggregate_yearly(self, start_epoch: Optional[float] = None, end_epoch: Optional[float] = None) -> Dict[str, Any]:
        return self._aggregator.aggregate_yearly(start_epoch=start_epoch, end_epoch=end_epoch)

    def run_aggregation_pipeline(self, start_epoch: Optional[float] = None, end_epoch: Optional[float] = None, detect_spikes: bool = True, tick_seconds: float = 5.0) -> Dict[str, Any]:
        return self._aggregator.run_pipeline(start_epoch=start_epoch, end_epoch=end_epoch, detect_spikes=detect_spikes, tick_seconds=tick_seconds)

    def start_background_aggregator(self, interval_seconds: float = 300.0) -> None:
        """Запускает фоновый регламентный планировщик агрегации."""
        self._aggregator.start_background_scheduler(interval_seconds=interval_seconds)

    def stop_background_aggregator(self) -> None:
        """Останавливает фоновый регламентный планировщик агрегации."""
        self._aggregator.stop_background_scheduler()

    get_stats = get_storage_stats

