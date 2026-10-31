# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry - Service
# =============================================================================
# Description:
#   Фоновый сервис посекундного сбора системных метрик с сохранением в SQLite.
#
# Usage Examples:
#   Python API:
#     from apps.windows.telemetry.service import TelemetryLoggerService
#
#     instance = TelemetryLoggerService.get_instance()
#
# File: service.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-30 12:45:00
# =============================================================================

from __future__ import annotations
"""Фоновый сервис периодического сбора системных метрик с сохранением в SQLite."""

import asyncio
from datetime import datetime, timezone
import threading
import time
from typing import Any, Dict, List, Optional
try:
    from logger import logger
except ImportError:
    from logger import logger
from .collector import SystemCollector
from apps.windows.analytics.hardware_history_manager import HardwareHistoryManager
from .sqlite import TelemetryStorage
from .telemetry_config import TelemetryConfigManager
from .w64_collector import AIW64Collector
from .w64_etw_collector import AIW64ETWCollector

class TelemetryLoggerService:
    """Сервис периодического сбора системной телеметрии, аудита оборудования и W64/ETW событий в SQLite."""
    _instance: Optional[TelemetryLoggerService] = None

    def __init__(
        self,
        interval_sec: Optional[float] = None,
        top_processes: Optional[int] = None,
        collector: Optional[SystemCollector] = None,
        storage: Optional[TelemetryStorage] = None,
        hardware_audit_interval_sec: Optional[float] = None,
        rollup_interval_sec: Optional[float] = None,
        enable_w64: Optional[bool] = None,
        config_manager: Optional[TelemetryConfigManager] = None,
        db_cleanup_interval_sec: Optional[float] = None,
    ) -> None:
        """Инициализирует сервис сбора системных метрик.

        Args:
            interval_sec: Интервал между замерами телеметрии в секундах (по умолчанию из config.json).
            top_processes: Лимит сохраняемых активных процессов (по умолчанию из config.json).
            collector: Экземпляр сборщика SystemCollector (опционально).
            storage: Экземпляр хранилища TelemetryStorage (опционально).
            hardware_audit_interval_sec: Интервал периодического аудита железа (по умолчанию из config.json).
            rollup_interval_sec: Интервал запуска обобщения старых данных (по умолчанию из config.json).
            enable_w64: Включение подсистемы сбора событий W64/ETW (по умолчанию из config.json).
            config_manager: Менеджер конфигурации.
            db_cleanup_interval_sec: Интервал фонового контроля размера базы данных (сек).
        """
        self.config_manager = config_manager or TelemetryConfigManager()
        self._custom_interval_set = (interval_sec is not None)
        self.interval_sec = max(
            0.1,
            interval_sec if interval_sec is not None else self.config_manager.get_light_poll_interval_seconds()
        )
        self.top_processes = max(
            1,
            top_processes if top_processes is not None else self.config_manager.get_effective_process_limit()
        )
        self.hardware_audit_interval_sec = max(
            1.0,
            hardware_audit_interval_sec if hardware_audit_interval_sec is not None else self.config_manager.get_hardware_audit_interval_seconds()
        )
        self.rollup_interval_sec = max(
            1.0,
            rollup_interval_sec if rollup_interval_sec is not None else self.config_manager.get_aggregation_interval()
        )
        self.collector = collector or SystemCollector()
        self.storage = storage or TelemetryStorage.get_instance()
        self.db_cleanup_interval_sec = max(
            5.0,
            db_cleanup_interval_sec if db_cleanup_interval_sec is not None else self.config_manager.get_db_cleanup_interval_seconds()
        )

        cfg = self.config_manager.get_config()
        w64_cfg = cfg.get('w64_collector', {})
        self.enable_w64 = enable_w64 if enable_w64 is not None else w64_cfg.get('enabled', True)

        self._w64_collector: Optional[AIW64Collector] = None
        self._w64_etw_collector: Optional[AIW64ETWCollector] = None

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._ticks_count = 0
        self._start_time: Optional[float] = None
        self._last_tick_time: Optional[float] = None
        self._last_hw_audit_time: Optional[float] = None
        self._last_startup_audit_time: Optional[float] = None
        self._last_extended_audit_time: Optional[float] = None
        self._last_def_audit_time: Optional[float] = None
        self._last_proc_sync_time: Optional[float] = None
        self._last_software_audit_time: Optional[float] = None
        self._last_rollup_time: Optional[float] = None
        self._last_db_cleanup_time: Optional[float] = None
        self._last_error: Optional[str] = None
        self._last_snapshot: Optional[Any] = None
        self._process_auditor: Optional[Any] = None
        self._last_process_audit_sample: Optional[Any] = None
        self._lifecycle_tracker: Optional[Any] = None
        self._last_lifecycle_scan_time: Optional[float] = None
        self._previous_mode: Optional[str] = None
        self._live_stream_active: bool = False
        self._live_stream_session_id: Optional[str] = None
        self._live_stream_start_time: Optional[float] = None
        self._live_stream_timeout_sec: Optional[float] = None
        self._last_hardware_snapshot: Optional[Dict[str, Any]] = None

        # Индивидуальные интервалы тяжелых опросов (сек)
        self.heavy_poll_interval_sec: float = self.config_manager.get_heavy_poll_interval_seconds()
        self.startup_audit_interval_sec: float = self.config_manager.get_startup_audit_interval_seconds()
        self.extended_audit_interval_sec: float = self.config_manager.get_extended_audit_interval_seconds()
        self.defender_audit_interval_sec: float = self.config_manager.get_defender_audit_interval_seconds()
        self.process_activity_sync_interval_sec: float = self.config_manager.get_process_activity_sync_interval_seconds()
        self.software_audit_interval_sec: float = self.config_manager.get_software_audit_interval_seconds()
        self.internet_speed_interval_sec: float = 3600.0
        self._last_internet_speed_time: Optional[float] = None

    @classmethod
    def get_instance(cls) -> TelemetryLoggerService:
        """Возвращает глобальный синглтон сервиса телеметрии.

        Returns:
            TelemetryLoggerService: Единственный экземпляр сервиса.
        """
        if cls._instance is None:
            cls._instance = TelemetryLoggerService()
        return cls._instance

    @property
    def light_poll_interval_sec(self) -> float:
        """Интервал легкого тика опроса системы (сек)."""
        return self.interval_sec

    @property
    def is_running(self) -> bool:
        """Проверяет, запущен ли фоновый сбор телеметрии.

        Returns:
            bool: True если сбор активен, иначе False.
        """
        return self._running and self._thread is not None and self._thread.is_alive()

    @property
    def history_manager(self) -> HardwareHistoryManager:
        """Возвращает менеджер истории оборудования."""
        return self.collector.history_manager

    @property
    def w64_collector(self) -> Optional[AIW64Collector]:
        """Возвращает сборщик W64 событий (создается лениво при enable_w64)."""
        if self._w64_collector is None and self.enable_w64:
            self._init_w64_collectors()
        return self._w64_collector

    @w64_collector.setter
    def w64_collector(self, val: Optional[AIW64Collector]) -> None:
        self._w64_collector = val

    @property
    def w64_etw_collector(self) -> Optional[AIW64ETWCollector]:
        """Возвращает сборщик ETW событий (создается лениво при enable_w64)."""
        if self._w64_etw_collector is None and self.enable_w64:
            self._init_w64_collectors()
        return self._w64_etw_collector

    @w64_etw_collector.setter
    def w64_etw_collector(self, val: Optional[AIW64ETWCollector]) -> None:
        self._w64_etw_collector = val

    def _init_w64_collectors(self) -> None:
        """Инициализирует W64 и ETW сборщики при необходимости."""
        if not self.enable_w64:
            return
        cfg = self.config_manager.get_config()
        w64_cfg = cfg.get('w64_collector', {})
        if self._w64_collector is None:
            self._w64_collector = AIW64Collector(
                storage=self.storage,
                enable_file_monitoring=w64_cfg.get('enable_file_monitoring', False),
                enable_process_monitoring=w64_cfg.get('enable_process_monitoring', False),
                enable_registry_monitoring=w64_cfg.get('enable_registry_monitoring', False),
                enable_network_monitoring=w64_cfg.get('enable_network_monitoring', False),
                enable_event_log_monitoring=False,
            )
        if self._w64_etw_collector is None:
            self._w64_etw_collector = AIW64ETWCollector(
                storage=self.storage,
                enable_process_trace=w64_cfg.get('enable_process_trace', False),
                enable_disk_trace=w64_cfg.get('enable_disk_trace', False),
                enable_network_trace=w64_cfg.get('enable_network_trace', False),
                enable_registry_trace=w64_cfg.get('enable_registry_trace', False),
            )

    def start(self) -> bool:
        """Запускает фоновый поток сбора телеметрии, аудита оборудования и W64/ETW сборщиков.

        Returns:
            bool: True если сервис успешно запущен, False если уже работал.
        """
        if self.is_running:
            logger.debug('Сервис сбора телеметрии уже запущен.')
            return False
        self._stop_event.clear()
        self._running = True
        self._start_time = time.time()
        self._last_error = None
        self._last_hw_audit_time = None
        self._last_startup_audit_time = None
        self._last_extended_audit_time = None
        self._last_def_audit_time = None
        self._last_proc_sync_time = None
        self._last_rollup_time = None
        self._last_db_cleanup_time = None
        self._last_internet_speed_time = None

        if self.enable_w64:
            self._init_w64_collectors()
            if self.w64_collector:
                self.w64_collector.start()
            if self.w64_etw_collector:
                self.w64_etw_collector.start()

        # При каждом старте телеметрии фиксируем снимок автозапуска в хранилище
        try:
            startup_entry = self.collector.archive_startup_state(auto_diff=True)
            if startup_entry:
                self.storage.save_startup_archive(startup_entry)
        except Exception as st_init_ex:
            logger.debug(f'Фиксация снимка автозапуска при старте телеметрии: {st_init_ex}')

        # При старте телеметрии фиксируем снимок состояния Defender и безопасности в БД
        try:
            threading.Thread(target=self.collect_and_save_defender_state, name='DefenderInitCollector', daemon=True).start()
        except Exception as def_init_ex:
            logger.debug(f'Ошибка запуска инициализации Defender: {def_init_ex}')

        # При старте телеметрии синхронизируем паспорта активности процессов в SQLite
        try:
            from apps.windows.sdk.core.process_activity_engine import ProcessActivityEngine
            threading.Thread(
                target=lambda: ProcessActivityEngine(storage=self.storage).sync_processes(),
                name='ProcessActivityInitCollector',
                daemon=True,
            ).start()
        except Exception as proc_init_ex:
            logger.debug(f'Ошибка запуска инициализации активности процессов: {proc_init_ex}')

        # При старте телеметрии обеспечиваем детальный аудит и паспорт оборудования (CPU/RAM/GPU)
        try:
            threading.Thread(target=self._init_hardware_inventory, name='HardwareInventoryInit', daemon=True).start()
        except Exception as hw_init_ex:
            logger.debug(f'Ошибка инициализации оборудования при старте: {hw_init_ex}')

        # При старте телеметрии сохраняем начальный снимок системы в SQLite, если активен стриминг
        if self.is_streaming_active():
            try:
                threading.Thread(
                    target=self._collect_initial_snapshot,
                    name='TelemetryInitialCollector',
                    daemon=True,
                ).start()
            except Exception as init_snap_ex:
                logger.debug(f'Ошибка запуска начального сбора телеметрии: {init_snap_ex}')

        self._thread = threading.Thread(target=self._worker_loop, name='TelemetryLoggerWorker', daemon=True)
        self._thread.start()
        logger.info(f'Фоновый сервис телеметрии запущен в БД (интервал: {self.interval_sec}с, аудит железа: {self.hardware_audit_interval_sec}с, W64: {self.enable_w64}, БД: {self.storage.db_path})')
        return True

    def stop(self) -> bool:
        """Останавливает фоновый поток сбора телеметрии и W64/ETW сборщиков.

        Returns:
            bool: True если сервис был остановлен, False если он не работал.
        """
        if not self._running:
            return False
        self._running = False
        self._stop_event.set()

        if self.w64_collector:
            self.w64_collector.stop()
        if self.w64_etw_collector:
            self.w64_etw_collector.stop()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._thread = None
        try:
            self.storage.flush()
        except Exception:
            pass
        logger.info(f'Фоновый сервис телеметрии остановлен. Всего тиков: {self._ticks_count}')
        return True

    def sync_config_from_manager(self) -> bool:
        """Синхронизирует интервалы и настройки сервиса из менеджера конфигурации при их изменении.

        Returns:
            bool: True если конфигурация изменилась и была применена, иначе False.
        """
        self.config_manager.check_tc_mode_auto_switch()
        if self.config_manager.check_and_reload():
            if not self._custom_interval_set:
                self.interval_sec = max(0.1, self.config_manager.get_light_poll_interval_seconds())
            self.top_processes = max(1, self.config_manager.get_effective_process_limit())
            self.heavy_poll_interval_sec = max(1.0, self.config_manager.get_heavy_poll_interval_seconds())
            self.hardware_audit_interval_sec = max(1.0, self.config_manager.get_hardware_audit_interval_seconds())
            self.startup_audit_interval_sec = max(1.0, self.config_manager.get_startup_audit_interval_seconds())
            self.extended_audit_interval_sec = max(1.0, self.config_manager.get_extended_audit_interval_seconds())
            self.defender_audit_interval_sec = max(1.0, self.config_manager.get_defender_audit_interval_seconds())
            self.process_activity_sync_interval_sec = max(1.0, self.config_manager.get_process_activity_sync_interval_seconds())
            self.software_audit_interval_sec = max(1.0, self.config_manager.get_software_audit_interval_seconds())
            self.db_cleanup_interval_sec = max(5.0, self.config_manager.get_db_cleanup_interval_seconds())
            self.rollup_interval_sec = max(1.0, self.config_manager.get_aggregation_interval())
            current_mode = self.config_manager.get_telemetry_mode()
            if self._previous_mode == 'live_stream' and current_mode == 'audit':
                # При отключении live stream составляем отчет ресурсопотребления и компактифицируем
                try:
                    logger.info("📊 [Телеметрия] Остановка live stream -> финализация профиля сессии и компактификация")
                    self.stop_live_stream()
                except Exception as purge_ex:
                    logger.warning(f"Ошибка финализации live stream: {purge_ex}")
            self._previous_mode = current_mode
            logger.info(
                f"🔄 [Сервис телеметрии] Конфигурация config.json обновлена 'на лету': "
                f"легкий={self.interval_sec}с, аудит железа={self.hardware_audit_interval_sec}с, "
                f"автозапуск={self.startup_audit_interval_sec}с, Defender={self.defender_audit_interval_sec}с, "
                f"активность процессов={self.process_activity_sync_interval_sec}с, аудит ПО={self.software_audit_interval_sec}с, mode={current_mode}"
            )
            return True
        return False

    def _init_hardware_inventory(self) -> None:
        """Собирает и сохраняет детальный паспорт оборудования (включая CPU) в БД телеметрии."""
        try:
            self.check_hardware_configuration_changes()
            archive_entry = self.collector.archive_hardware_state(auto_diff=True)
            if archive_entry:
                self.storage.save_hardware_archive(archive_entry)
        except Exception as ex:
            logger.debug(f"[TelemetryService] Ошибка фоновой инвентаризации железа: {ex}")

    def is_streaming_active(self) -> bool:
        """Проверяет активность режима стриминга системных метрик (on-demand сессия или через конфигурацию)."""
        if self._live_stream_active:
            return True
        return self.config_manager.is_streaming_enabled()

    def is_live_stream_active(self) -> bool:
        """Алиас для is_streaming_active()."""
        return self.is_streaming_active()

    def is_audit_active(self) -> bool:
        """Проверяет активность процесса аудита (Audit запускается на старте телеметрии в любом случае)."""
        return self.config_manager.is_audit_enabled()

    def start_live_stream(self, duration_seconds: Optional[float] = None, trigger_source: str = 'manual') -> str:
        """Активирует режим live stream по запросу (on-demand).

        Args:
            duration_seconds: Ограничение длительности сессии в секундах (по таймауту).
            trigger_source: Источник запуска ('manual', 'api', 'benchmark').

        Returns:
            str: Уникальный session_id запущенной сессии.
        """
        import uuid
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        session_id = f"live-{now.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
        self._live_stream_active = True
        self._live_stream_session_id = session_id
        self._live_stream_start_time = time.time()
        self._live_stream_timeout_sec = float(duration_seconds) if duration_seconds is not None else None
        logger.info(f"🚀 [Live Stream] Активирован режим по запросу (ID: {session_id}, таймаут: {duration_seconds}с)")
        return session_id

    def stop_live_stream(self) -> Optional[Dict[str, Any]]:
        """Останавливает режим live stream, формирует отчет ресурсопотребления и компактифицирует тики.

        Returns:
            Optional[Dict[str, Any]]: Сформированный профиль сессии или None.
        """
        if not self.is_live_stream_active():
            return None

        now_ts = time.time()
        session_id = self._live_stream_session_id or f"live-session-{int(now_ts)}"
        start_ts = self._live_stream_start_time or (now_ts - 60.0)

        self._live_stream_active = False
        self._live_stream_session_id = None
        self._live_stream_start_time = None
        self._live_stream_timeout_sec = None

        # 1. Агрегация и сохранение отчета сессии live stream
        report = self.storage.finalize_live_stream_session(
            session_id=session_id,
            started_ts=start_ts,
            ended_ts=now_ts,
        )

        # 2. Компактификация сырых тиков (БД не раздувается)
        self.storage.compact_live_stream_data()

        logger.info(f"🏁 [Live Stream] Сессия {session_id} остановлена. Профиль ресурсопотребления сохранен.")
        return report

    def check_hardware_configuration_changes(self) -> List[Dict[str, Any]]:
        """Сравнивает текущий состав оборудования с предыдущим снимком и фиксирует изменения в БД навсегда.

        Returns:
            List[Dict[str, Any]]: Список зафиксированных изменений конфигурации («было / стало»).
        """
        detected_changes: List[Dict[str, Any]] = []
        try:
            current_snap: Dict[str, Any] = {}
            # Считываем текущий инвентарь из БД
            cpus = self.storage.get_cpu_inventory()
            if cpus:
                c = cpus[0]
                current_snap['cpu'] = {
                    'name': c.get('name'),
                    'cores': c.get('logical_cores'),
                    'physical_cores': c.get('physical_cores'),
                    'vendor': c.get('vendor'),
                }

            rams = self.storage.get_ram_module_inventory()
            if rams:
                total_ram_gb = sum(float(r.get('capacity_gb') or 0.0) for r in rams)
                current_snap['ram'] = {
                    'total_gb': round(total_ram_gb, 1),
                    'modules_count': len(rams),
                    'serials': sorted([str(r.get('serial_number') or '') for r in rams if r.get('serial_number')]),
                }

            gpus = self.storage.get_gpu_inventory()
            if gpus:
                current_snap['gpu'] = {
                    'names': sorted([str(g.get('name') or '') for g in gpus]),
                    'vram_gb': max([float(g.get('vram_gb') or 0.0) for g in gpus], default=0.0),
                }

            disks = self.storage.get_disk_inventory()
            if disks:
                current_snap['disks'] = {
                    'serials': sorted([str(d.get('serial_number') or '') for d in disks if d.get('serial_number')]),
                    'models': sorted([str(d.get('product') or '') for d in disks if d.get('product')]),
                }

            if not current_snap:
                return []

            if self._last_hardware_snapshot is None:
                # Первый снимок сессии - сохраняем как исходную точку
                self._last_hardware_snapshot = current_snap
                return []

            old_snap = self._last_hardware_snapshot

            # Проверка изменения CPU
            if 'cpu' in old_snap and 'cpu' in current_snap:
                if old_snap['cpu'].get('name') != current_snap['cpu'].get('name'):
                    old_c = old_snap['cpu']
                    new_c = current_snap['cpu']
                    summary = f"Замена процессора: {old_c.get('name')} -> {new_c.get('name')}"
                    ch_id = self.storage.save_hardware_config_change(
                        component_type='CPU',
                        change_type='REPLACED',
                        component_name=str(new_c.get('name')),
                        old_config=old_c,
                        new_config=new_c,
                        summary=summary,
                    )
                    detected_changes.append({'id': ch_id, 'type': 'CPU', 'summary': summary})

            # Проверка изменения RAM
            if 'ram' in old_snap and 'ram' in current_snap:
                if old_snap['ram'].get('total_gb') != current_snap['ram'].get('total_gb') or old_snap['ram'].get('modules_count') != current_snap['ram'].get('modules_count'):
                    old_r = old_snap['ram']
                    new_r = current_snap['ram']
                    summary = f"Изменение оперативной памяти: {old_r.get('total_gb')}GB ({old_r.get('modules_count')} мод.) -> {new_r.get('total_gb')}GB ({new_r.get('modules_count')} мод.)"
                    ch_id = self.storage.save_hardware_config_change(
                        component_type='RAM',
                        change_type='MODIFIED',
                        component_name='RAM Memory',
                        old_config=old_r,
                        new_config=new_r,
                        summary=summary,
                    )
                    detected_changes.append({'id': ch_id, 'type': 'RAM', 'summary': summary})

            # Проверка изменения GPU
            if 'gpu' in old_snap and 'gpu' in current_snap:
                if old_snap['gpu'].get('names') != current_snap['gpu'].get('names'):
                    old_g = old_snap['gpu']
                    new_g = current_snap['gpu']
                    summary = f"Замена видеокарты: {', '.join(old_g.get('names', []))} -> {', '.join(new_g.get('names', []))}"
                    ch_id = self.storage.save_hardware_config_change(
                        component_type='GPU',
                        change_type='REPLACED',
                        component_name=str(new_g.get('names', ['GPU'])[0]),
                        old_config=old_g,
                        new_config=new_g,
                        summary=summary,
                    )
                    detected_changes.append({'id': ch_id, 'type': 'GPU', 'summary': summary})

            # Проверка изменения Disks
            if 'disks' in old_snap and 'disks' in current_snap:
                if old_snap['disks'].get('serials') != current_snap['disks'].get('serials'):
                    old_d = old_snap['disks']
                    new_d = current_snap['disks']
                    summary = f"Изменение дисковой конфигурации: {', '.join(old_d.get('models', []))} -> {', '.join(new_d.get('models', []))}"
                    ch_id = self.storage.save_hardware_config_change(
                        component_type='DISK',
                        change_type='MODIFIED',
                        component_name='Storage Disks',
                        old_config=old_d,
                        new_config=new_d,
                        summary=summary,
                    )
                    detected_changes.append({'id': ch_id, 'type': 'DISK', 'summary': summary})

            self._last_hardware_snapshot = current_snap
        except Exception as ex:
            logger.debug(f"Ошибка при детекции изменений конфигурации железа: {ex}")

        return detected_changes

    def get_hardware_comparison_report(
        self,
        change_id: Optional[int] = None,
        component_type: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Формирует сравнительный отчет производительности до и после апгрейда железа («Было / Стало»)."""
        return self.storage.get_hardware_comparison_report(change_id=change_id, component_type=component_type)

    def _collect_initial_snapshot(self) -> None:
        """Собирает и сохраняет начальный снимок системы при старте сервиса."""
        try:
            snapshot = asyncio.run(self.collector.get_snapshot(process_limit=self.top_processes, force_live=True))
            self._last_snapshot = snapshot
            self.storage.save_snapshot(snapshot, top_n=self.top_processes)
            logger.info("✅ [Телеметрия] Начальный снимок системы успешно зафиксирован в SQLite БД.")
        except Exception as ex:
            logger.debug(f"Ошибка сохранения начального снимка: {ex}")

    def _worker_loop(self) -> None:
        """Основной рабочий цикл фонового сбора метрик, записи в БД и аудита изменений."""
        while not self._stop_event.is_set():
            loop_start = time.time()
            try:
                # Проверка изменения config.json 'на лету'
                self.sync_config_from_manager()

                # 1. Постоянный аудит процессов (Audit работает непрерывно)
                if self.is_audit_active():
                    target_pid = self.config_manager.get_audit_target_pid()
                    if target_pid is not None:
                        audit_sample = self.audit_process_once(target_pid)
                        if not audit_sample:
                            logger.debug(f"[Audit] Целевой процесс PID={target_pid} не обнаружен или завершился")

                # 2. Сбор и сохранение системного снимка на КАЖДОМ тике независимо от режима:
                # потребление ресурсов приложениями копится для истории всегда (audit и streaming).
                try:
                    loop = None
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = None
                    if loop and loop.is_running():
                        task = asyncio.run_coroutine_threadsafe(
                            self.collector.get_snapshot(process_limit=self.top_processes, force_live=True),
                            loop,
                        )
                        snapshot = task.result(timeout=30.0)
                    else:
                        snapshot = asyncio.run(
                            self.collector.get_snapshot(process_limit=self.top_processes, force_live=True)
                        )
                    self._last_snapshot = snapshot
                    self.storage.save_snapshot(snapshot, top_n=self.top_processes)
                except Exception as snap_err:
                    logger.warning(f'Ошибка сбора/сохранения снимка телеметрии в БД: {snap_err}')

                # Контроль таймаута Live Stream (если был запущен on-demand)
                if self.is_streaming_active() and self._live_stream_timeout_sec and self._live_stream_start_time:
                    if loop_start - self._live_stream_start_time >= self._live_stream_timeout_sec:
                        self.stop_live_stream()

                self._ticks_count += 1
                self._last_tick_time = time.time()

                # 3. Аудит изменений и периодические проверки (Audit запускается на старте в любом случае)
                if self.is_audit_active():
                    # Отслеживание жизненного цикла процессов (рождение, завершение, инициаторы)
                    try:
                        self.track_lifecycle_delta()
                    except Exception as life_ex:
                        logger.debug(f'Ошибка отслеживания жизненного цикла процессов: {life_ex}')

                    # 1. Тяжелый аудит аппаратного оборудования (железа)
                    if self._last_hw_audit_time is None or loop_start - self._last_hw_audit_time >= self.hardware_audit_interval_sec:
                        try:
                            self.check_hardware_configuration_changes()
                            archive_entry = self.collector.archive_hardware_state(auto_diff=True)
                            if archive_entry:
                                self.storage.save_hardware_archive(archive_entry)
                        except Exception as hw_ex:
                            logger.debug(f'Ошибка при периодическом аудите железа: {hw_ex}')
                        self._last_hw_audit_time = loop_start

                    # 2. Тяжелый аудит автозапуска Windows
                    if self._last_startup_audit_time is None or loop_start - self._last_startup_audit_time >= self.startup_audit_interval_sec:
                        try:
                            startup_archive = self.collector.archive_startup_state(auto_diff=True)
                            if startup_archive:
                                self.storage.save_startup_archive(startup_archive)
                        except Exception as st_ex:
                            logger.debug(f'Ошибка при периодическом аудите автозапуска: {st_ex}')
                        self._last_startup_audit_time = loop_start

                    # 3. Расширенный аудит системы
                    if self._last_extended_audit_time is None or loop_start - self._last_extended_audit_time >= self.extended_audit_interval_sec:
                        try:
                            self.collector.get_extended_system_audit()
                        except Exception as ext_ex:
                            logger.debug(f'Ошибка при периодическом расширенном аудите: {ext_ex}')
                        self._last_extended_audit_time = loop_start

                    # 4. Аудит безопасности и состояния Microsoft Defender
                    if self._last_def_audit_time is None or loop_start - self._last_def_audit_time >= self.defender_audit_interval_sec:
                        try:
                            self.collect_and_save_defender_state()
                        except Exception as def_ex:
                            logger.debug(f'Ошибка при периодическом аудите Defender: {def_ex}')
                        self._last_def_audit_time = loop_start

                    # 5. Синхронизация активности и паспортов процессов
                    if self._last_proc_sync_time is None or loop_start - self._last_proc_sync_time >= self.process_activity_sync_interval_sec:
                        try:
                            from apps.windows.sdk.core.process_activity_engine import ProcessActivityEngine
                            ProcessActivityEngine(storage=self.storage).sync_processes()
                        except Exception as proc_ex:
                            logger.debug(f'Ошибка при периодической синхронизации активности процессов: {proc_ex}')
                        self._last_proc_sync_time = loop_start

                    # 6. Периодический аудит установленного ПО и артефактов запусков
                    if self._last_software_audit_time is None or loop_start - self._last_software_audit_time >= self.software_audit_interval_sec:
                        try:
                            from apps.windows.sdk.core.software_audit import SoftwareAuditEngine
                            SoftwareAuditEngine().generate_audit_report(save_to_db=True)
                        except Exception as sw_ex:
                            logger.debug(f'Ошибка при периодическом аудите ПО: {sw_ex}')
                        try:
                            from apps.windows.sdk.software_scanner.controller import DeepSoftwareScanner
                            from apps.windows.sdk.software_scanner.models import ScanMode
                            sc_rep = DeepSoftwareScanner().run_scan(mode=ScanMode.QUICK)
                            if sc_rep:
                                self.storage.save_software_scanner_report(sc_rep)
                        except Exception as sc_ex:
                            logger.debug(f'Ошибка при сохранении периодического отчета сканера ПО в telemetry.db: {sc_ex}')
                        self._last_software_audit_time = loop_start

                    # 7. Периодический замер скорости интернета FAST.com (1 раз в час, буфер на 144 записи)
                    if self._last_internet_speed_time is None or loop_start - self._last_internet_speed_time >= self.internet_speed_interval_sec:
                        try:
                            from apps.windows.telemetry.internet_speed import get_internet_speed_sensor
                            get_internet_speed_sensor().check_and_run_hourly(force=False, skip_if_busy=True)
                        except Exception as net_ex:
                            logger.debug(f'Ошибка фонового теста скорости интернета FAST.com: {net_ex}')
                        self._last_internet_speed_time = loop_start
                if self._last_rollup_time is None or loop_start - self._last_rollup_time >= self.rollup_interval_sec:
                    try:
                        self.run_rollups()
                        self._last_rollup_time = loop_start
                    except Exception as roll_ex:
                        logger.debug(f'Ошибка при периодическом обобщении процессов: {roll_ex}')
                if self._last_db_cleanup_time is None or loop_start - self._last_db_cleanup_time >= self.db_cleanup_interval_sec:
                    try:
                        self.cleanup_db()
                        self._last_db_cleanup_time = loop_start
                    except Exception as clean_ex:
                        logger.debug(f'Ошибка при периодическом контроле размера БД: {clean_ex}')
            except (RuntimeError, ValueError) as shut_ex:
                if 'shutdown' in str(shut_ex).lower() or 'closed file' in str(shut_ex).lower():
                    break
                self._last_error = str(shut_ex)
                logger.debug(f'Ошибка при сборе системной телеметрии: {shut_ex}')
            except Exception as ex:
                self._last_error = str(ex)
                logger.debug(f'Ошибка при сборе системной телеметрии: {ex}')
            elapsed = time.time() - loop_start
            sleep_time = max(0.01, self.get_tick_interval() - elapsed)
            if self._stop_event.wait(timeout=sleep_time):
                break

    def collect_and_save_defender_state(self) -> None:
        """Опрашивает текущее состояние Microsoft Defender и сохраняет снимок в базу данных SQLite."""
        try:
            from apps.windows.sdk.modules.defender.core.defender_service import DefenderService
            from apps.windows.sdk.modules.defender.core.asr_manager import ASRManager
            from apps.windows.sdk.modules.defender.core.exclusions_auditor import ExclusionsAuditor
            from apps.windows.sdk.modules.defender.core.threat_manager import ThreatManager

            def_svc = DefenderService()
            asr_mgr = ASRManager(def_svc)
            excl_aud = ExclusionsAuditor(def_svc)
            threat_mgr = ThreatManager(def_svc)

            status = def_svc.get_defender_status()
            asr_rules = asr_mgr.get_asr_rules()
            excl_report = excl_aud.audit_exclusions()
            threats = threat_mgr.get_threats_history(limit=50)

            all_exclusions = excl_report.path_exclusions + excl_report.extension_exclusions + excl_report.process_exclusions
            snap_id = f"snap_defender_{int(datetime.now(timezone.utc).timestamp())}"
            self.storage.save_defender_snapshot(
                snapshot_id=snap_id,
                defender_status=status,
                exclusions=all_exclusions,
                asr_rules=asr_rules,
                threats=threats,
            )
            logger.debug(f'Снимок состояния Defender зафиксирован в БД ({snap_id})')

            # Операционные события Windows читаются веб-интерфейсом на лету через WevtAPI.
        except Exception as e:
            logger.debug(f'Ошибка сбора и сохранения состояния Defender: {e}')

    def get_tick_interval(self) -> float:
        """Возвращает размер тика: interval_seconds из config.json.

        Ускоренный интервал аудита (audit_interval_sec) применяется только пока
        задан целевой PID глубокого аудита, и только если он меньше базового тика.

        Returns:
            float: Интервал ожидания между тиками в секундах.
        """
        if self.config_manager.get_audit_target_pid() is not None:
            return min(self.interval_sec, self.config_manager.get_audit_interval_sec())
        return self.interval_sec

    def run_rollups(self) -> Dict[str, Any]:
        """Запускает каскад агрегации (сенсоры и процессы) и очистку истории по сроку хранения.

        Returns:
            Dict[str, Any]: Результаты агрегации и число удалённых строк истории.
        """
        pipeline_res = self.storage.run_aggregation_pipeline(tick_seconds=self.get_tick_interval())
        purged = self.storage.purge_history(self.config_manager.get_history_retention_days())
        return {'pipeline': pipeline_res, 'history_purged': purged}

    def cleanup_db(self) -> Dict[str, Any]:
        """Запускает процедуру контроля размера и усечения базы данных телеметрии.

        Returns:
            Dict[str, Any]: Отчет о результатах контроля размера.
        """
        return self.storage.enforce_size_limit()

    def get_status(self) -> Dict[str, Any]:
        """Возвращает текущий статус сервиса телеметрии.

        Returns:
            Dict[str, Any]: Словарь с состоянием и статистикой работы сервиса.
        """
        uptime = (time.time() - self._start_time) if self._start_time else 0.0
        return {
            'is_running': self.is_running,
            'telemetry_mode': self.config_manager.get_telemetry_mode(),
            'audit_active': self.is_audit_active(),
            'streaming_active': self.is_streaming_active(),
            'live_stream_active': self.is_live_stream_active(),
            'audit_target_pid': self.config_manager.get_audit_target_pid(),
            'current_live_session_id': self._live_stream_session_id,
            'interval_sec': self.interval_sec,
            'light_poll_interval_sec': self.interval_sec,
            'light_poll_interval_seconds': self.interval_sec,
            'heavy_poll_interval_sec': self.heavy_poll_interval_sec,
            'heavy_poll_interval_seconds': self.heavy_poll_interval_sec,
            'top_processes_limit': self.top_processes,
            'hardware_audit_interval_sec': self.hardware_audit_interval_sec,
            'startup_audit_interval_sec': self.startup_audit_interval_sec,
            'extended_audit_interval_sec': self.extended_audit_interval_sec,
            'defender_audit_interval_sec': self.defender_audit_interval_sec,
            'process_activity_sync_interval_sec': self.process_activity_sync_interval_sec,
            'software_audit_interval_sec': self.software_audit_interval_sec,
            'heavy_polls_intervals': {
                'hardware_audit_interval_sec': self.hardware_audit_interval_sec,
                'startup_audit_interval_sec': self.startup_audit_interval_sec,
                'extended_audit_interval_sec': self.extended_audit_interval_sec,
                'defender_audit_interval_sec': self.defender_audit_interval_sec,
                'process_activity_sync_interval_sec': self.process_activity_sync_interval_sec,
                'software_audit_interval_sec': self.software_audit_interval_sec,
            },
            'ticks_recorded': self._ticks_count,
            'uptime_seconds': uptime,
            'last_tick_epoch': self._last_tick_time,
            'last_hw_audit_epoch': self._last_hw_audit_time,
            'last_startup_audit_epoch': self._last_startup_audit_time,
            'last_extended_audit_epoch': self._last_extended_audit_time,
            'last_def_audit_epoch': self._last_def_audit_time,
            'last_proc_sync_epoch': self._last_proc_sync_time,
            'last_software_audit_epoch': self._last_software_audit_time,
            'last_error': self._last_error,
            'storage_stats': self.storage.get_storage_stats(),
        }

    def get_last_snapshot(self) -> Optional[Any]:
        """Возвращает последний собранный снапшот.

        Returns:
            Optional[Any]: Последний снапшот или None.
        """
        return self._last_snapshot

    def get_history(self, limit: int=60) -> List[Dict[str, Any]]:
        """Возвращает историю системных снимков из SQLite базы данных.

        Args:
            limit: Количество последних записей.

        Returns:
            List[Dict[str, Any]]: Список исторических срезов.
        """
        return self.storage.get_snapshots(limit=limit)

    def record_event(self, event_type: str, event_details: Dict[str, Any], severity: str='info') -> int:
        """Записывает событие в SQLite базу данных телеметрии.

        Args:
            event_type: Тип события (hardware_change, process_start, driver_update).
            event_details: Детали события.
            severity: Уровень серьезности события.

        Returns:
            int: ID добавленной записи события.
        """
        logger.info(f'[Событие Telemetry] {event_type}: {event_details}')
        try:
            return self.storage.save_event(event_type, event_details, severity=severity)
        except Exception as ex:
            logger.error(f'Не удалось записать событие в базу данных: {ex}')
            return 0

    @property
    def last_process_audit_sample(self) -> Optional[Any]:
        """Возвращает последний снимок глубокого аудита процесса."""
        return self._last_process_audit_sample

    def track_lifecycle_delta(self) -> Optional[Any]:
        """Сканирует жизненный цикл процессов (рождение, завершение, инициаторы) и сохраняет в БД."""
        if self._lifecycle_tracker is None:
            from apps.windows.sdk.modules.process_manager import ProcessLifecycleTracker
            self._lifecycle_tracker = ProcessLifecycleTracker()

        delta = self._lifecycle_tracker.scan_processes_delta()
        for s in delta.created_sessions:
            try:
                self.storage.upsert_process_lifecycle_session(s)
            except Exception as ex:
                logger.debug(f'Ошибка сохранения старта процесса {s.instance_id}: {ex}')
        for s in delta.terminated_sessions:
            try:
                self.storage.upsert_process_lifecycle_session(s)
            except Exception as ex:
                logger.debug(f'Ошибка сохранения завершения процесса {s.instance_id}: {ex}')
        return delta

    def audit_process_once(self, pid: int) -> Optional[Any]:
        """Выполняет глубокий аудит целевого процесса по PID и сохраняет его в БД.

        Args:
            pid: Идентификатор процесса Windows (PID).

        Returns:
            Optional[Any]: Снимок ProcessAuditSample или None.
        """
        if self._process_auditor is None:
            from apps.windows.sdk.modules.process_manager import ProcessAuditor
            self._process_auditor = ProcessAuditor()

        sample = self._process_auditor.audit_process(pid)
        if sample:
            self._last_process_audit_sample = sample
            try:
                self.storage.save_process_audit_sample(sample)
                # Синхронизация сессии процесса
                if sample.instance_id:
                    endpoints = [f"{c.get('remote_ip')}:{c.get('remote_port')}" for c in sample.network.connections if c.get('remote_ip')]
                    self.storage.upsert_process_lifecycle_session({
                        "instance_id": sample.instance_id,
                        "pid": sample.pid,
                        "ppid": sample.ppid,
                        "name": sample.name,
                        "exe_path": sample.executable,
                        "cmdline": sample.cmdline,
                        "username": sample.username,
                        "parent_name": sample.parent_name,
                        "parent_exe": sample.parent_executable,
                        "initiator_type": sample.initiator_type,
                        "created_at": sample.timestamp,
                        "created_ts": sample.creation_time,
                        "is_alive": sample.is_alive,
                        "lifetime_sec": sample.uptime_sec,
                        "cpu_time_user_sec": sample.cpu.user_time_sec,
                        "cpu_time_kernel_sec": sample.cpu.kernel_time_sec,
                        "cpu_time_total_sec": sample.cpu.total_cpu_time_sec,
                        "cpu_cycles": sample.cpu.cpu_cycles,
                        "peak_working_set_mb": sample.memory.peak_working_set_mb or sample.memory.working_set_mb,
                        "peak_private_mb": sample.memory.private_mb,
                        "io_read_bytes": sample.io.read_bytes,
                        "io_write_bytes": sample.io.write_bytes,
                        "io_read_ops": sample.io.read_operations,
                        "io_write_ops": sample.io.write_operations,
                        "files_accessed": sample.io.open_files,
                        "remote_endpoints": endpoints,
                    })
            except Exception as db_err:
                logger.debug(f'Ошибка сохранения аудита процесса PID={pid}: {db_err}')
        return sample

    def activate_audit_mode(self, pid: int, interval_sec: Optional[float] = None) -> bool:
        """Активирует режим аудита для отслеживания целевого процесса по PID.

        Args:
            pid: Идентификатор целевого процесса (PID).
            interval_sec: Интервал замеров аудита (сек).

        Returns:
            bool: True при успешной активации.
        """
        success = self.config_manager.activate_audit_mode(pid=pid, interval_sec=interval_sec)
        if success:
            self.sync_config_from_manager()
        return success

    def activate_live_stream_mode(self) -> bool:
        """Переключает службу в режим непрерывного потока системных метрик live stream.

        Returns:
            bool: True при успешном переключении.
        """
        success = self.config_manager.activate_live_stream_mode()
        if success:
            self.sync_config_from_manager()
        return success

    def activate_streaming_mode(self, interval_sec: Optional[float] = None) -> bool:
        """Активирует режим стриминга метрик реального времени. Аудит при этом продолжает работу.

        Args:
            interval_sec: Интервал сбора снимков метрик (сек).

        Returns:
            bool: True при успешной активации.
        """
        success = self.config_manager.activate_streaming_mode(interval_sec=interval_sec)
        if success:
            self.sync_config_from_manager()
        return success

    def deactivate_streaming_mode(self) -> bool:
        """Отключает стриминг метрик отдельно от аудита. Аудит продолжает работу.

        Returns:
            bool: True при успешном отключении.
        """
        if self._live_stream_active:
            self.stop_live_stream()
        success = self.config_manager.deactivate_streaming_mode()
        if success:
            self.sync_config_from_manager()
        return success

    def deactivate_live_stream_mode(self) -> bool:
        """Алиас для отключения стриминга (live stream)."""
        return self.deactivate_streaming_mode()

    def activate_both_mode(self, pid: Optional[int] = None, interval_sec: Optional[float] = None) -> bool:
        """Активирует оба процесса одновременно: и стриминг, и аудит.

        Args:
            pid: Идентификатор процесса Windows (PID) для аудита.
            interval_sec: Интервал сбора замеров (сек).

        Returns:
            bool: True при успешной активации обоих процессов.
        """
        success = self.config_manager.activate_both_mode(pid=pid, interval_sec=interval_sec)
        if success:
            self.sync_config_from_manager()
        return success
