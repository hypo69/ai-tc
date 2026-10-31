# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry Sqlite - TelemetryInventoryStorageMixin
# =============================================================================
# Description:
#   Миксин фасада хранилища: инвентаризация и выборки дисков, томов, CPU, RAM, GPU и сетевых адаптеров.
#   Вынесено при декомпозиции TelemetryStorage (этап 4 ТЗ оптимизации).
#   Атрибуты хоста: _reader, _writer, _buffer, _maintenance, _aggregator, _cm.
#
# Usage Examples:
#   Python API:
#     from apps.windows.telemetry.sqlite.storage_inventory import TelemetryInventoryStorageMixin
#
#     class TelemetryStorage(TelemetryInventoryStorageMixin): ...
#
# File: storage_inventory.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry.sqlite
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-20 09:38:00
# =============================================================================

from __future__ import annotations

"""Миксин фасада хранилища: инвентаризация и выборки дисков, томов, CPU, RAM, GPU и сетевых адаптеров."""

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


class TelemetryInventoryStorageMixin:
    """Миксин фасада хранилища: инвентаризация и выборки дисков, томов, CPU, RAM, GPU и сетевых адаптеров."""

    def save_disk_inventory(self, disk_data: Any) -> None:
        """Сохранить или обновить паспорт физического накопителя."""
        rec = {'type': 'disk_inventory', 'data': disk_data}
        if self._buffer.buffer_mode == 'direct':
            self._writer.batch_insert_records([rec])
            return
        self._buffer.enqueue(rec)

    def save_volume_inventory(self, volume_data: Any) -> None:
        """Сохранить или обновить паспорт логического тома."""
        rec = {'type': 'volume_inventory', 'data': volume_data}
        if self._buffer.buffer_mode == 'direct':
            self._writer.batch_insert_records([rec])
            return
        self._buffer.enqueue(rec)

    def save_disk_health_snapshot(self, health_data: Any) -> None:
        """Сохранить снимок здоровья / SMART / TBW накопителя."""
        rec = {'type': 'disk_health', 'data': health_data}
        if self._buffer.buffer_mode == 'direct':
            self._writer.batch_insert_records([rec])
            return
        self._buffer.enqueue(rec)

    def save_disk_performance_sample(self, perf_data: Any) -> None:
        """Сохранить сэмпл производительности диска."""
        rec = {'type': 'disk_performance', 'data': perf_data}
        if self._buffer.buffer_mode == 'direct':
            self._writer.batch_insert_records([rec])
            return
        self._buffer.enqueue(rec)

    def save_disk_io_event(self, io_event_data: Any) -> None:
        """Сохранить событие прямого ввода-вывода."""
        rec = {'type': 'disk_io_event', 'data': io_event_data}
        if self._buffer.buffer_mode == 'direct':
            self._writer.batch_insert_records([rec])
            return
        self._buffer.enqueue(rec)

    def get_disk_inventory(self, disk_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Извлечь паспортные данные физических дисков."""
        return self._reader.get_disk_inventory(disk_id=disk_id)

    def get_volume_inventory(self) -> List[Dict[str, Any]]:
        """Извлечь паспортные данные логических томов."""
        return self._reader.get_volume_inventory()

    def get_disk_health_history(
        self,
        disk_id: Optional[int] = None,
        serial_number: Optional[str] = None,
        limit: int = 100,
        since_epoch: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Извлечь историю здоровья и SMART/TBW накопителей."""
        return self._reader.get_disk_health_history(disk_id=disk_id, serial_number=serial_number, limit=limit, since_epoch=since_epoch)

    def get_disk_performance_samples(
        self,
        disk_name: Optional[str] = None,
        limit: int = 100,
        since_epoch: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Извлечь сэмплы производительности дисков."""
        return self._reader.get_disk_performance_samples(disk_name=disk_name, limit=limit, since_epoch=since_epoch)

    def get_disk_io_events(
        self,
        pid: Optional[int] = None,
        disk_id: Optional[int] = None,
        limit: int = 100,
        since_epoch: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Извлечь события ввода-вывода процессов."""
        return self._reader.get_disk_io_events(pid=pid, disk_id=disk_id, limit=limit, since_epoch=since_epoch)

    def save_cpu_inventory(self, cpu_data: Any) -> None:
        """Сохранить или обновить паспорт процессора."""
        rec = {'type': 'cpu_inventory', 'data': cpu_data}
        if self._buffer.buffer_mode == 'direct':
            self._writer.batch_insert_records([rec])
            return
        self._buffer.enqueue(rec)

    def save_cpu_telemetry_sample(self, sample_data: Any) -> None:
        """Сохранить снимок телеметрии процессора."""
        rec = {'type': 'cpu_telemetry', 'data': sample_data}
        if self._buffer.buffer_mode == 'direct':
            self._writer.batch_insert_records([rec])
            return
        self._buffer.enqueue(rec)

    def get_cpu_inventory(self, processor_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Извлечь паспортные данные процессоров."""
        return self._reader.get_cpu_inventory(processor_id=processor_id)

    def get_cpu_telemetry_samples(
        self,
        processor_id: Optional[int] = None,
        limit: int = 100,
        since_epoch: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Извлечь историю метрик процессора."""
        return self._reader.get_cpu_telemetry_samples(processor_id=processor_id, limit=limit, since_epoch=since_epoch)

    def save_ram_module_inventory(self, module_data: Any) -> None:
        """Сохранить или обновить паспорт планки оперативной памяти."""
        rec = {'type': 'ram_module_inventory', 'data': module_data}
        if self._buffer.buffer_mode == 'direct':
            self._writer.batch_insert_records([rec])
            return
        self._buffer.enqueue(rec)

    def save_ram_telemetry_sample(self, sample_data: Any) -> None:
        """Сохранить снимок телеметрии оперативной памяти."""
        rec = {'type': 'ram_telemetry', 'data': sample_data}
        if self._buffer.buffer_mode == 'direct':
            self._writer.batch_insert_records([rec])
            return
        self._buffer.enqueue(rec)

    def get_ram_module_inventory(self) -> List[Dict[str, Any]]:
        """Извлечь паспортные данные физических планок оперативной памяти."""
        return self._reader.get_ram_module_inventory()

    def get_ram_telemetry_samples(
        self,
        limit: int = 100,
        since_epoch: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Извлечь историю метрик оперативной памяти."""
        return self._reader.get_ram_telemetry_samples(limit=limit, since_epoch=since_epoch)

    def save_gpu_inventory(self, gpu_data: Any) -> None:
        """Сохранить или обновить паспорт графического ускорителя."""
        rec = {'type': 'gpu_inventory', 'data': gpu_data}
        if self._buffer.buffer_mode == 'direct':
            self._writer.batch_insert_records([rec])
            return
        self._buffer.enqueue(rec)

    def save_gpu_telemetry_sample(self, sample_data: Any) -> None:
        """Сохранить снимок телеметрии графического ускорителя."""
        rec = {'type': 'gpu_telemetry', 'data': sample_data}
        if self._buffer.buffer_mode == 'direct':
            self._writer.batch_insert_records([rec])
            return
        self._buffer.enqueue(rec)

    def get_gpu_inventory(self, gpu_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Извлечь паспортные данные GPU."""
        return self._reader.get_gpu_inventory(gpu_id=gpu_id)

    def get_gpu_telemetry_samples(
        self,
        gpu_id: Optional[int] = None,
        name: Optional[str] = None,
        limit: int = 100,
        since_epoch: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Извлечь историю метрик GPU."""
        return self._reader.get_gpu_telemetry_samples(gpu_id=gpu_id, name=name, limit=limit, since_epoch=since_epoch)

    def save_network_adapter_inventory(self, adapter_data: Any) -> None:
        """Сохранить или обновить паспорт сетевого адаптера."""
        rec = {'type': 'network_adapter_inventory', 'data': adapter_data}
        if self._buffer.buffer_mode == 'direct':
            self._writer.batch_insert_records([rec])
            return
        self._buffer.enqueue(rec)

    def save_network_adapter_sample(self, sample_data: Any) -> None:
        """Сохранить сэмпл показателей сетевого адаптера."""
        rec = {'type': 'network_adapter_sample', 'data': sample_data}
        if self._buffer.buffer_mode == 'direct':
            self._writer.batch_insert_records([rec])
            return
        self._buffer.enqueue(rec)

    def get_network_adapter_inventory(self) -> List[Dict[str, Any]]:
        """Извлечь паспортные данные сетевых адаптеров."""
        return self._reader.get_network_adapter_inventory()

    def get_network_adapter_samples(
        self,
        adapter_name: Optional[str] = None,
        limit: int = 100,
        since_epoch: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Извлечь сэмплы показателей сетевых адаптеров."""
        return self._reader.get_network_adapter_samples(adapter_name=adapter_name, limit=limit, since_epoch=since_epoch)

    def get_monitor_inventory(self) -> List[Dict[str, Any]]:
        """Извлечь паспортные данные подключенных мониторов и дисплеев."""
        return self._reader.get_monitor_inventory()

    def get_hardware_components(
        self,
        include_removed: bool = True,
        only_present: bool = False,
    ) -> List[Dict[str, Any]]:
        """Извлечь зарегистрированные аппаратные компоненты с флагами присутствия."""
        return self._reader.get_hardware_components(include_removed=include_removed, only_present=only_present)

    def get_pending_hardware_components(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Извлечь компоненты оборудования, ожидающие AI-обогащения ссылками."""
        return self._reader.get_pending_hardware_components(limit=limit)

    def get_hardware_component_by_key(self, component_key: str) -> Optional[Dict[str, Any]]:
        """Извлечь аппаратный компонент по ключу."""
        return self._reader.get_hardware_component_by_key(component_key)

    def get_hardware_component_history(self, component_key: str) -> List[Dict[str, Any]]:
        """Извлечь историю событий установки/переустановки/удаления компонента."""
        return self._reader.get_hardware_component_history(component_key)

    def save_hardware_component(self, comp_data: Dict[str, Any]) -> int:
        """Сохранить или обновить паспорт аппаратного компонента."""
        with self._cm.lock, self._cm.get_connection() as conn:
            row_id = self._writer.upsert_hardware_component(conn.cursor(), comp_data)
            conn.commit()
            return row_id

    def sync_hardware_components_lifecycle(
        self,
        components: List[Dict[str, Any]],
        categories: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Синхронизирует текущий срез оборудования с базой данных, отслеживая подключение и отключение компонентов.

        Args:
            components: Список собранных компонентов текущего сканирования.
            categories: Список категорий, охваченных текущим сбором (для обнаружения удаленных).

        Returns:
            Dict[str, Any]: Сводка синхронизации {'saved_count': ..., 'removed_keys': [...]}.
        """
        active_keys: List[str] = []
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            for comp in components:
                key = comp.get("component_key")
                if key:
                    active_keys.append(key)
                self._writer.upsert_hardware_component(cursor, comp)

            # Вычисляем просканированные категории, если не переданы явно
            cat_list = categories or list({c.get("category") for c in components if c.get("category")})
            removed_keys = self._writer.mark_missing_hardware_components_removed(
                cursor=cursor,
                active_keys=active_keys,
                categories=cat_list,
            )
            conn.commit()
            return {
                "saved_count": len(components),
                "removed_count": len(removed_keys),
                "removed_keys": removed_keys,
            }

    def record_hardware_component_event(
        self,
        component_key: str,
        event_type: str,
        details: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None,
    ) -> int:
        """Записать событие жизненного цикла компонента (installed, removed, reinstalled)."""
        return self._writer.record_hardware_component_event(
            component_key=component_key,
            event_type=event_type,
            details=details,
            timestamp=timestamp,
        )

    def update_hardware_component_links(
        self,
        component_key: str,
        vendor_url: Optional[str] = None,
        status: str = "completed",
    ) -> bool:
        """Обновить ссылки на сайт производителя и изображение компонента."""
        return self._writer.update_hardware_component_links(
            component_key=component_key,
            vendor_url=vendor_url,
            status=status,
        )

    def update_hardware_component_production_date(
        self,
        component_key: str,
        production_date: Optional[str] = None,
        source: Optional[str] = None,
        status: str = "completed",
    ) -> bool:
        """Обновить дату производства компонента."""
        return self._writer.update_hardware_component_production_date(
            component_key=component_key,
            production_date=production_date,
            source=source,
            status=status,
        )


