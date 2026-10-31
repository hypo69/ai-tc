# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry Sqlite - Delta & LOCF
# =============================================================================
# Description:
#   Движок дельта-трекинга (Change-Only Storage) и реконструкции срезов
#   на основе алгоритма LOCF (Last Observation Carried Forward).
#
# Usage Examples:
#   Python API:
#     from apps.windows.telemetry.sqlite.delta_tracker import DeltaStateTracker, LocfReconstructor
#
#     tracker = DeltaStateTracker()
#     tracker.ensure_seeded(cursor)
#     delta_data, has_static_changes = tracker.filter_snapshot_delta(snap_dict)
#
#     reconstructor = LocfReconstructor()
#     full_snap = reconstructor.reconstruct_snapshot_row(row, conn)
#
# File: delta_tracker.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry.sqlite
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-14 00:55:00
# =============================================================================

from __future__ import annotations
"""Модуль отслеживания изменений (Delta State) и реконструкции верхних срезов (LOCF Forward-Fill)."""

import json
import sqlite3
import threading
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


# Список отслеживаемых полей снимка системы
SNAPSHOT_FIELDS: Tuple[str, ...] = (
    "hostname",
    "username",
    "uptime_seconds",
    "os_name",
    "os_build",
    "os_install_date",
    "system_language",
    "os_install_language",
    "user_locale",
    "system_locale",
    "timezone",
    "codepage",
    "input_languages_json",
    "disks_json",
    "physical_disks_json",
    "monitors_json",
    "updates_json",
    "office_json",
    "onedrive_json",
    "battery_json",
    "ram_sticks_json",
    "listening_ports_json",
    "alerts_json",
    "cpu_total_percent",
    "cpu_frequency_mhz",
    "memory_total_gb",
    "memory_used_gb",
    "memory_percent",
    "swap_percent",
    "gpu_load_percent",
    "gpu_temp_c",
    "disk_read_bytes_sec",
    "disk_write_bytes_sec",
    "disk_read_count_sec",
    "disk_write_count_sec",
    "network_sent_bytes_sec",
    "network_recv_bytes_sec",
    "hardware_audit",
)

# Быстро меняющиеся метрики: их изменение не считается изменением конфигурации
# (не порождает повторную запись raw_json).
VOLATILE_FIELDS: frozenset = frozenset({
    "uptime_seconds",
    "battery_json",
    "alerts_json",
    "cpu_total_percent",
    "cpu_frequency_mhz",
    "memory_used_gb",
    "memory_percent",
    "swap_percent",
    "gpu_load_percent",
    "gpu_temp_c",
    "disk_read_bytes_sec",
    "disk_write_bytes_sec",
    "disk_read_count_sec",
    "disk_write_count_sec",
    "network_sent_bytes_sec",
    "network_recv_bytes_sec",
})


class DeltaStateTracker:
    """Отслеживает предыдущие состояния параметров телеметрии и фильтрует неизменившиеся значения."""

    def __init__(self) -> None:
        """Инициализирует кэш состояний параметров."""
        self._lock = threading.Lock()
        self._last_snapshot_state: Dict[str, Any] = {}
        self._last_sensor_values: Dict[str, Any] = {}
        self._last_app_polls: Dict[str, Any] = {}
        self._last_proc_metrics: Dict[int, Dict[str, Any]] = {}
        self._seeded = False

    def ensure_seeded(self, cursor: sqlite3.Cursor) -> None:
        """Однократно восстанавливает последнее известное состояние полей снимка из БД (LOCF).

        Без этого после каждого рестарта сервиса все статические параметры
        (диски, мониторы, ОС, RAM и т.д.) записывались бы заново.

        Args:
            cursor: Курсор активного соединения SQLite.
        """
        with self._lock:
            if self._seeded:
                return
            self._seeded = True
            for field in SNAPSHOT_FIELDS:
                try:
                    row = cursor.execute(
                        f"SELECT {field} FROM system_snapshots WHERE {field} IS NOT NULL AND {field} != '' "
                        f"ORDER BY id DESC LIMIT 1"
                    ).fetchone()
                except sqlite3.Error:
                    return
                if row and row[0] is not None:
                    self._last_snapshot_state[field] = row[0]

    def reset(self) -> None:
        """Сбрасывает зафиксированные состояния (принудительная полная запись на следующем тике)."""
        with self._lock:
            self._last_snapshot_state.clear()
            self._last_sensor_values.clear()
            self._last_app_polls.clear()
            self._last_proc_metrics.clear()

    def filter_snapshot_delta(self, fields_dict: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
        """Сравнивает поля снимка с последним зафиксированным состоянием.

        Args:
            fields_dict: Словарь подготовленных значений колонок снимка.

        Returns:
            Tuple[Dict[str, Any], bool]: (словарь с дельтами/NULL, флаг изменения хотя бы одного
            статического, не входящего в VOLATILE_FIELDS, параметра).
        """
        with self._lock:
            delta_dict: Dict[str, Any] = {}
            has_static_changes = False

            for field in SNAPSHOT_FIELDS:
                new_val = fields_dict.get(field)
                if self._is_value_changed(self._last_snapshot_state.get(field), new_val):
                    delta_dict[field] = new_val
                    self._last_snapshot_state[field] = new_val
                    has_static_changes = has_static_changes or field not in VOLATILE_FIELDS
                else:
                    # Значение не изменилось -> в БД сохраняется None (NULL)
                    delta_dict[field] = None

            # Обязательные временные маркеры тика сохраняются всегда
            delta_dict["timestamp"] = fields_dict.get("timestamp")
            delta_dict["created_at"] = fields_dict.get("created_at")

            return delta_dict, has_static_changes

    def filter_sensor_poll(self, sensor_id: str, value: Any) -> bool:
        """Проверяет, изменилось ли значение датчика.

        Args:
            sensor_id: Идентификатор сенсора.
            value: Новое показание.

        Returns:
            bool: True если значение изменилось и его нужно сохранить, иначе False.
        """
        with self._lock:
            old_val = self._last_sensor_values.get(sensor_id)
            if self._is_value_changed(old_val, value):
                self._last_sensor_values[sensor_id] = value
                return True
            return False

    def filter_app_poll(self, app: str, metric_name: str, value: Any, status: str) -> bool:
        """Проверяет, изменились ли метрики приложения.

        Args:
            app: Название приложения.
            metric_name: Название метрики.
            value: Значение.
            status: Статус.

        Returns:
            bool: True если метрика или статус изменились, иначе False.
        """
        key = f"{app}:{metric_name}"
        state = (value, status)
        with self._lock:
            old_state = self._last_app_polls.get(key)
            if old_state != state:
                self._last_app_polls[key] = state
                return True
            return False

    @staticmethod
    def _is_value_changed(old_val: Any, new_val: Any) -> bool:
        """Вспомогательный метод определения изменения значения с учетом типов."""
        if old_val is None and (new_val is None or new_val == ""):
            return False
        if old_val is None and new_val is not None:
            return True
        if old_val is not None and new_val is None:
            return False  # Отсутствие данных в текущем тике не затирает старое значение

        # Числовое сравнение с плавающей точкой
        if isinstance(old_val, (int, float)) and isinstance(new_val, (int, float)):
            return abs(float(old_val) - float(new_val)) > 1e-6

        # Сравнение строк / JSON
        return str(old_val) != str(new_val)


class LocfReconstructor:
    """Движок реконструкции верхних срезов (LOCF - Last Observation Carried Forward)."""

    def __init__(self) -> None:
        """Инициализирует восстановитель срезов."""
        self._cached_latest_state: Dict[str, Any] = {}
        self._lock = threading.Lock()

    def update_cached_state(self, fields: Dict[str, Any]) -> None:
        """Обновляет оперативный кэш последнего известного состояния."""
        with self._lock:
            for k, v in fields.items():
                if v is not None and v != "":
                    self._cached_latest_state[k] = v

    def reconstruct_snapshot_row(
        self,
        row: Dict[str, Any],
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        """Восстанавливает полный срез для отдельной строки снимка из БД.

        Для всех полей, равных NULL, подтягивает последние известные значения.

        Args:
            row: Сырая строка снимка из базы данных.
            conn: Подключение к SQLite для поиска исторических предшественников при необходимости.

        Returns:
            Dict[str, Any]: Полностью заполненный словарь системного снимка.
        """
        result = dict(row)
        snap_id = result.get("id")
        created_at = result.get("created_at")

        # Определяем пропущенные поля
        missing_fields = [f for f in SNAPSHOT_FIELDS if result.get(f) is None or result.get(f) == ""]

        if missing_fields and conn is not None and (snap_id is not None or created_at is not None):
            cursor = conn.cursor()
            # Ищем предшествующие значения в истории
            for field in missing_fields:
                if snap_id is not None:
                    cursor.execute(
                        f"SELECT {field} FROM system_snapshots WHERE id <= ? AND {field} IS NOT NULL AND {field} != '' ORDER BY id DESC LIMIT 1",
                        (snap_id,)
                    )
                else:
                    cursor.execute(
                        f"SELECT {field} FROM system_snapshots WHERE created_at <= ? AND {field} IS NOT NULL AND {field} != '' ORDER BY created_at DESC LIMIT 1",
                        (created_at,)
                    )
                prev_row = cursor.fetchone()
                if prev_row and prev_row[0] is not None:
                    result[field] = prev_row[0]

        return result

    def reconstruct_snapshots_batch(
        self,
        rows: List[Dict[str, Any]],
        conn: Optional[sqlite3.Connection] = None,
    ) -> List[Dict[str, Any]]:
        """Выполняет пакетную LOCF реконструкцию для упорядоченного списка снимков.

        Args:
            rows: Список сырых строк снимков (упорядоченных по id ASC или created_at ASC).
            conn: Подключение к SQLite для инициализации базового состояния.

        Returns:
            List[Dict[str, Any]]: Список восстановленных полных снимков.
        """
        if not rows:
            return []

        # Если записи идут в обратном порядке (DESC), временно переворачиваем
        is_desc = False
        if len(rows) > 1 and (rows[0].get("id", 0) or 0) > (rows[-1].get("id", 0) or 0):
            is_desc = True
            rows = list(reversed(rows))

        # Базовое состояние
        current_state: Dict[str, Any] = {}

        # Инициализация первого снимка из БД при необходимости
        first_row = rows[0]
        first_id = first_row.get("id")
        if conn is not None and first_id is not None:
            first_reconstructed = self.reconstruct_snapshot_row(first_row, conn)
            current_state.update(first_reconstructed)
        else:
            current_state.update(first_row)

        reconstructed_list: List[Dict[str, Any]] = []

        for r in rows:
            snap_dict = dict(r)
            # Накладываем изменения текущего тика на текущее состояние LOCF
            for field in SNAPSHOT_FIELDS:
                val = snap_dict.get(field)
                if val is not None and val != "":
                    current_state[field] = val
                else:
                    # Берем предыдущее значение
                    snap_dict[field] = current_state.get(field)

            # Сохраняем временные метки текущего тика
            snap_dict["timestamp"] = r.get("timestamp")
            snap_dict["created_at"] = r.get("created_at")
            snap_dict["id"] = r.get("id")

            reconstructed_list.append(snap_dict)

        if is_desc:
            reconstructed_list.reverse()

        return reconstructed_list

