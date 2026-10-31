# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows SDK Core - Power Monitor
# =============================================================================
# Description:
#   Модуль отслеживания состояний питания (Power-Aware Monitoring) для Windows.
#   Обеспечивает корректную обработку выключения экрана, режима сна S3,
#   гибернации S4 и возобновления работы системы без ложных измерений во время сна.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.core.power_monitor import PowerStateMonitor
#
#     monitor = PowerStateMonitor()
#     status = monitor.get_system_power_status()
#
# File: power_monitor.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-16 13:13:00
# =============================================================================

from __future__ import annotations
"""Модуль отслеживания состояний питания (Power-Aware Monitoring) для Windows."""

import ctypes
from ctypes import wintypes
import datetime
import json
import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class SYSTEM_POWER_STATUS(ctypes.Structure):
    """Структура Win32 API GetSystemPowerStatus."""
    _fields_ = [
        ("ACLineStatus", ctypes.c_byte),
        ("BatteryFlag", ctypes.c_byte),
        ("BatteryLifePercent", ctypes.c_byte),
        ("SystemStatusFlag", ctypes.c_byte),
        ("BatteryLifeTime", ctypes.c_ulong),
        ("BatteryFullLifeTime", ctypes.c_ulong),
    ]


class PowerStateMonitor:
    """Управление состояниями питания и отслеживание разрывов телеметрии."""

    def __init__(self, db_storage: Optional[Any] = None) -> None:
        """Инициализация монитора питания.

        Args:
            db_storage: Экземпляр TelemetryStorage или None.
        """
        self.db_storage = db_storage
        self._current_state = 'WORKING'
        self._is_active = False
        self._last_tick_time = time.time()
        self._session_id = f"power_session_{int(time.time())}"

    def start(self) -> None:
        """Запустить мониторинг состояния питания."""
        self._is_active = True
        self._current_state = 'WORKING'
        self._last_tick_time = time.time()
        logger.info("PowerStateMonitor запущен. Сессия: %s", self._session_id)

    def stop(self) -> None:
        """Остановить мониторинг состояния питания."""
        self._is_active = False
        logger.info("PowerStateMonitor остановлен.")

    def get_state(self) -> str:
        """Получить текущее состояние питания.

        Returns:
            str: Текущее состояние ('WORKING', 'SUSPENDING', 'SLEEPING', 'RESUMING', и т.д.).
        """
        return self._current_state

    def get_system_power_status(self) -> Dict[str, Any]:
        """Получить статус батареи и электропитания через Win32 API GetSystemPowerStatus.

        Returns:
            dict: Состояние сетевого питания, процент заряда батареи и флаги.
        """
        status = SYSTEM_POWER_STATUS()
        if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
            ac_status = {0: 'Offline', 1: 'Online', 255: 'Unknown'}.get(status.ACLineStatus, 'Unknown')
            battery_percent = status.BatteryLifePercent if status.BatteryLifePercent != 255 else None
            return {
                'ac_status': ac_status,
                'battery_percent': battery_percent,
                'battery_flag': status.BatteryFlag,
            }
        return {'ac_status': 'Unknown', 'battery_percent': None}

    def handle_power_event(
        self,
        event_type: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Обработать внешнее событие питания (например PBT_APMSUSPEND, PBT_APMRESUME).

        Args:
            event_type: Тип события ('SUSPENDING', 'RESUMING', 'DISPLAY_OFF', 'WORKING').
            details: Дополнительные детали события.

        Returns:
            dict: Результат обработки события.
        """
        prev_state = self._current_state
        self._current_state = event_type
        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()

        event_data = {
            'timestamp_utc': now_utc,
            'event_type': event_type,
            'previous_state': prev_state,
            'new_state': event_type,
            'session_id': self._session_id,
            'details': details or {},
        }

        logger.info("Переход состояния питания: %s -> %s", prev_state, event_type)

        if self.db_storage and hasattr(self.db_storage, 'execute_write'):
            try:
                now_epoch = time.time()
                query = """
                    INSERT INTO power_sessions (
                        session_id, record_type, event_id, provider, channel,
                        start_time, start_epoch, classification, details_json, created_at
                    ) VALUES (?, 'event', ?, ?, ?, ?, ?, ?, ?, ?)
                """
                self.db_storage.execute_write(
                    query,
                    (
                        f"pwr_evt_{int(now_epoch * 1000)}",
                        int(now_epoch),
                        "PowerStateMonitor",
                        "System",
                        now_utc,
                        now_epoch,
                        event_type,
                        json.dumps(event_data, ensure_ascii=False),
                        now_epoch,
                    ),
                )
            except Exception as err:
                logger.warning("Не удалось записать power_event в БД: %s", err)

        return event_data

    def detect_gap(
        self,
        last_sample_time: float,
        current_time: float,
        expected_interval: float = 2.0,
        threshold_multiplier: float = 3.0,
    ) -> Optional[Dict[str, Any]]:
        """Обнаружить разрыв сбора данных (например из-за сна S3 или задержки).

        Args:
            last_sample_time: Время предыдущего измерения (timestamp).
            current_time: Текущее время (timestamp).
            expected_interval: Ожидаемый интервал опроса в секундах (по умолчанию 2.0).
            threshold_multiplier: Множитель для определения разрыва (по умолчанию 3.0).

        Returns:
            dict | None: Метаданные о разрыве или None при нормальном интервале.
        """
        elapsed = current_time - last_sample_time
        if elapsed > (expected_interval * threshold_multiplier):
            gap_duration = elapsed - expected_interval
            start_utc = datetime.datetime.fromtimestamp(
                last_sample_time, datetime.timezone.utc
            ).isoformat()
            end_utc = datetime.datetime.fromtimestamp(
                current_time, datetime.timezone.utc
            ).isoformat()

            confidence = 'confirmed' if self._current_state in ('SLEEPING', 'RESUMING') else 'probable'
            gap_data = {
                'start_utc': start_utc,
                'end_utc': end_utc,
                'gap_type': 'sleep' if confidence == 'confirmed' else 'unknown',
                'duration_seconds': round(gap_duration, 2),
                'confidence': confidence,
            }

            logger.info("Обнаружен разрыв телеметрии: %.2f сек (Тип: %s)", gap_duration, confidence)

            if self.db_storage and hasattr(self.db_storage, 'execute_write'):
                try:
                    now_epoch = time.time()
                    query = """
                        INSERT INTO incidents (
                            incident_id, timestamp, created_at, domain, trigger_type,
                            severity, title, window_start, window_end, duration_sec, details_json
                        ) VALUES (?, ?, ?, 'telemetry_gap', ?, 'INFO', ?, ?, ?, ?, ?)
                    """
                    self.db_storage.execute_write(
                        query,
                        (
                            f"gap_{int(now_epoch * 1000)}",
                            end_utc,
                            now_epoch,
                            gap_data['gap_type'],
                            f"Разрыв сбора телеметрии ({confidence})",
                            start_utc,
                            end_utc,
                            gap_data['duration_seconds'],
                            json.dumps(gap_data, ensure_ascii=False),
                        ),
                    )
                except Exception as err:
                    logger.warning("Не удалось записать telemetry_gap в БД: %s", err)

            return gap_data

        return None


PowerAwareMonitor = PowerStateMonitor

__all__ = [
    'PowerStateMonitor',
    'PowerAwareMonitor',
    'SYSTEM_POWER_STATUS',
]

