# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry - Engine
# =============================================================================
# Description:
#   Асинхронное многоскоростное ядро сбора телеметрии (Multi-Rate Decoupled Telemetry Engine).
#   Реализует 4-уровневое разделение контуров сбора с адаптивным управлением частотой,
#   Zero-Delay запуском (< 2 мс) и дедупликацией записи в SQLite (Deadband + Heartbeat).
#
# Usage Examples:
#   Python API:
#     from apps.windows.telemetry.telemetry_engine import TelemetryEngine
#
#     engine = TelemetryEngine()
#     await engine.start()
#
# File: telemetry_engine.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 18:55:00
# =============================================================================

from __future__ import annotations
"""Асинхронное многоскоростное ядро сбора телеметрии и адаптивного управления интервалами."""

import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False

try:
    from logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

from .collector import SystemCollector
from .incident_detector import IncidentDetector, TelemetryRingBuffer
from .models import (
    CpuMetrics,
    GpuMetrics,
    MemoryMetrics,
    NetworkInterfaceMetrics,
    ProcessMetrics,
    SystemSnapshot,
)
from .sampling_controller import SamplingController
from .sqlite import TelemetryStorage
from .telemetry_config import TelemetryConfigManager, get_telemetry_config_manager
from apps.windows.sdk.win32_ffi.nethelper import IPHelperAPI, NetworkSocketInfo


class DeadbandTracker:
    """Трекер зон нечувствительности (Deadband) для адаптивной фильтрации сенсоров на базе конфигурации."""

    def __init__(
        self,
        temp_threshold: Optional[float] = None,
        cpu_load_threshold: Optional[float] = None,
        freq_threshold_mhz: Optional[float] = None,
        power_threshold_w: Optional[float] = None,
        fan_threshold_rpm: Optional[float] = None,
        heartbeat_interval_sec: Optional[float] = None,
        config_manager: Optional[TelemetryConfigManager] = None,
    ) -> None:
        """Инициализирует пороги фильтрации из конфигурации (config.json -> multi_rate_engine.deadband).

        Args:
            temp_threshold: Порог температуры (°C).
            cpu_load_threshold: Порог загрузки CPU (%).
            freq_threshold_mhz: Порог частоты (МГц).
            power_threshold_w: Порог мощности (Вт).
            fan_threshold_rpm: Порог скорости вентилятора (RPM).
            heartbeat_interval_sec: Интервал контрольного кадра Heartbeat (сек).
            config_manager: Экземпляр TelemetryConfigManager.
        """
        self._config_manager = config_manager or get_telemetry_config_manager()
        db_cfg = self._config_manager.get_deadband_config()

        self.temp_threshold = float(temp_threshold if temp_threshold is not None else db_cfg.get('temperature_c', 1.0))
        self.cpu_load_threshold = float(cpu_load_threshold if cpu_load_threshold is not None else db_cfg.get('cpu_load_pct', 3.0))
        self.freq_threshold_mhz = float(freq_threshold_mhz if freq_threshold_mhz is not None else db_cfg.get('freq_mhz', 50.0))
        self.power_threshold_w = float(power_threshold_w if power_threshold_w is not None else db_cfg.get('power_w', 2.0))
        self.fan_threshold_rpm = float(fan_threshold_rpm if fan_threshold_rpm is not None else db_cfg.get('fan_rpm', 100.0))
        self.network_bytes_threshold = float(db_cfg.get('network_bytes', 10485760.0))
        self.network_packets_threshold = float(db_cfg.get('network_packets', 10000.0))
        self.disk_space_gb_threshold = float(db_cfg.get('disk_space_gb', 0.5))
        self.default_threshold = float(db_cfg.get('default_threshold', 2.0))
        self.heartbeat_interval_sec = float(heartbeat_interval_sec if heartbeat_interval_sec is not None else db_cfg.get('heartbeat_interval_seconds', 60.0))
        self.ignore_cumulative_network_spikes = bool(db_cfg.get('ignore_cumulative_network_spikes', True))

        self._last_values: Dict[str, float] = {}
        self._last_saved_values: Dict[str, float] = {}
        self._last_saved_time: Dict[str, float] = {}

    def _get_threshold_for_sensor(self, sensor_id: str, category: str, unit: str) -> float:
        """Определяет порог Deadband для конкретного сенсора на основе конфигурации."""
        cat_lower = category.lower()
        unit_lower = unit.lower()
        sid_lower = sensor_id.lower()

        if 'temp' in cat_lower or '°c' in unit_lower or 'temp' in sid_lower:
            return self.temp_threshold
        if 'load' in cat_lower or '%' in unit_lower or 'util' in sid_lower:
            return self.cpu_load_threshold
        if 'clock' in cat_lower or 'mhz' in unit_lower or 'freq' in sid_lower:
            return self.freq_threshold_mhz
        if 'power' in cat_lower or 'w' in unit_lower or 'power' in sid_lower:
            return self.power_threshold_w
        if 'fan' in cat_lower or 'rpm' in unit_lower or 'fan' in sid_lower:
            return self.fan_threshold_rpm
        if 'bytes' in sid_lower or unit_lower in ('b', 'b/s'):
            return self.network_bytes_threshold
        if 'packets' in sid_lower or unit_lower == 'pkts':
            return self.network_packets_threshold
        if unit_lower == 'gb' or 'free_gb' in sid_lower:
            return self.disk_space_gb_threshold
        return self.default_threshold

    def check_spike(self, readings: List[Dict[str, Any]]) -> bool:
        """Проверяет, превысил ли хотя бы один физический датчик порог Deadband с прошлого замера.

        Args:
            readings: Список текущих показаний датчиков.

        Returns:
            bool: True если зафиксирован всплеск (Trigger-Up), иначе False.
        """
        has_spike = False
        for r in readings:
            sid = str(r.get('id') or r.get('sensor_id') or '')
            if not sid:
                continue
            raw_val = r.get('value', r.get('value_num', 0.0))
            try:
                val = float(raw_val)
            except (TypeError, ValueError):
                continue

            sid_lower = sid.lower()
            cat_lower = str(r.get('sensor_category') or '').lower()
            is_cumulative_net = (
                self.ignore_cumulative_network_spikes
                and cat_lower == 'network'
                and ('_bytes_' in sid_lower or '_packets_' in sid_lower)
            )

            prev_val = self._last_values.get(sid)
            threshold = self._get_threshold_for_sensor(
                sid,
                str(r.get('sensor_category') or ''),
                str(r.get('unit') or ''),
            )

            if prev_val is not None and not is_cumulative_net:
                delta = abs(val - prev_val)
                if delta >= threshold:
                    has_spike = True

            self._last_values[sid] = val

        return has_spike

    def filter_records_for_storage(
        self, readings: List[Dict[str, Any]], now_epoch: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """Фильтрует записи для записи в БД: сохраняет только изменения > Deadband или Heartbeat.

        Args:
            readings: Список текущих показаний датчиков.
            now_epoch: Текущее время Unix epoch.

        Returns:
            List[Dict[str, Any]]: Отфильтрованные записи для сохранения в SQLite.
        """
        now = now_epoch if now_epoch is not None else time.time()
        to_store: List[Dict[str, Any]] = []

        for r in readings:
            sid = str(r.get('id') or r.get('sensor_id') or '')
            if not sid:
                continue
            raw_val = r.get('value', r.get('value_num', 0.0))
            try:
                val = float(raw_val)
            except (TypeError, ValueError):
                continue

            last_saved = self._last_saved_values.get(sid)
            last_time = self._last_saved_time.get(sid, 0.0)
            threshold = self._get_threshold_for_sensor(
                sid,
                str(r.get('sensor_category') or ''),
                str(r.get('unit') or ''),
            )

            should_save = False
            if last_saved is None:
                should_save = True
            elif abs(val - last_saved) >= threshold:
                should_save = True
            elif (now - last_time) >= self.heartbeat_interval_sec:
                should_save = True

            if should_save:
                self._last_saved_values[sid] = val
                self._last_saved_time[sid] = now
                to_store.append(r)

        return to_store


class TelemetryEngine:
    """Асинхронное ядро сбора системной телеметрии (Multi-Rate Decoupled Telemetry Engine)."""

    def __init__(
        self,
        collector: Optional[SystemCollector] = None,
        storage: Optional[TelemetryStorage] = None,
        config_manager: Optional[TelemetryConfigManager] = None,
    ) -> None:
        """Инициализирует ядро телеметрии с независимыми контурами.

        Args:
            collector: Экземпляр SystemCollector для системных вызовов.
            storage: Экземпляр TelemetryStorage для персистентности.
            config_manager: Экземпляр TelemetryConfigManager.
        """
        self.collector = collector or SystemCollector()
        self.storage = storage or TelemetryStorage.get_instance()
        self.config_manager = config_manager or TelemetryConfigManager()

        self.is_running = False
        self.static_inventory_loaded = False
        self.static_catalog: Dict[str, Any] = {}

        mr_cfg = self.config_manager.get_multi_rate_config()
        rb_cap = int(mr_cfg.get('ring_buffer_capacity', 600))
        rb_max_mb = int(mr_cfg.get('ring_buffer_max_mb', 32))

        self.deadband_tracker = DeadbandTracker(config_manager=self.config_manager)
        self.sampling_controller = SamplingController(config_manager=self.config_manager)
        self.ring_buffer = TelemetryRingBuffer(capacity=rb_cap, max_bytes=rb_max_mb * 1024 * 1024)
        self.incident_detector = IncidentDetector(
            sampling_controller=self.sampling_controller,
            ring_buffer=self.ring_buffer,
            storage=self.storage,
            config_manager=self.config_manager,
        )
        self.ip_helper = IPHelperAPI() if hasattr(IPHelperAPI, '__init__') else None

        self._tasks: List[asyncio.Task] = []
        self._current_sensor_interval: float = float(mr_cfg.get('level2_adaptive_initial_interval_seconds', 2.0))
        self._cooldown_ticks: int = 0
        self._main_tick_count: int = 0
        self._last_snapshot: Optional[SystemSnapshot] = None
        self._last_smart_scan_time: float = 0.0
        self._last_battery_scan_time: float = 0.0
        self._last_security_scan_time: float = 0.0
        self._last_scm_scan_time: float = 0.0
        self._last_sockets_scan_time: float = 0.0

    async def start(self) -> None:
        """Единая асинхронная точка входа запуска службы телеметрии.

        Обеспечивает Zero-Delay старт (< 2 мс) и разделение контуров по 4 приоритетам.
        """
        if self.is_running:
            logger.debug("[TelemetryEngine] Сервис уже запущен.")
            return

        self.is_running = True
        logger.info("[TelemetryEngine] 🚀 Запуск Multi-Rate Decoupled Telemetry Engine...")

        # 1. ЗАПУСК ГЛАВНОГО REAL-TIME ЦИКЛА (LEVEL 3) - Стартует мгновенно (< 2 мс)
        main_task = asyncio.create_task(
            self._main_realtime_tick_loop(),
            name="MainRealtimeTickTask",
        )
        self._tasks.append(main_task)

        # 2. ОТЛОЖЕННЫЙ ЗАПУСК СТАТИЧЕСКОГО ПАСПОРТА (LEVEL 0) - Задержка 200 мс
        deferred_task = asyncio.create_task(
            self._deferred_static_inventory_task(),
            name="DeferredStaticInventoryTask",
        )
        self._tasks.append(deferred_task)

        # 3. АДАПТИВНЫЙ ДИНАМИЧЕСКИЙ КОНТУР СЕНСОРОВ (LEVEL 2) - Задержка 500 мс
        adaptive_task = asyncio.create_task(
            self._adaptive_sensors_loop(),
            name="AdaptiveSensorsTask",
        )
        self._tasks.append(adaptive_task)

        # 4. НИЗКОЧАСТОТНЫЙ ФОНОВЫЙ ОПРОС (LEVEL 1) - Задержка 5.0 с
        low_freq_task = asyncio.create_task(
            self._low_frequency_background_loop(),
            name="LowFrequencyTask",
        )
        self._tasks.append(low_freq_task)

        # 5. ПАКЕТНЫЙ WAL-СБРОС БУФЕРА В SQLITE (Раз в 5.0 с)
        wal_writer_task = asyncio.create_task(
            self._batch_wal_flusher_loop(),
            name="BatchWalFlusherTask",
        )
        self._tasks.append(wal_writer_task)

        logger.info("[TelemetryEngine] ✅ Все контуры телеметрии инициализированы.")

    async def stop(self) -> None:
        """Корректно останавливает все асинхронные задачи и сбрасывает буферы."""
        if not self.is_running:
            return

        self.is_running = False
        logger.info("[TelemetryEngine] Остановка ядра телеметрии...")

        for task in self._tasks:
            if not task.done():
                task.cancel()

        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        # Финальный сброс буфера в SQLite
        try:
            self.storage.flush()
        except Exception as ex:
            logger.debug(f"[TelemetryEngine] Ошибка при финальном сбросе буфера: {ex}")

        logger.info(f"[TelemetryEngine] Сервис остановлен. Выполнено главных тиков: {self._main_tick_count}")

    async def _main_realtime_tick_loop(self) -> None:
        """Главный высокоприоритетный Real-Time контур (Level 3): PID, системные счетчики, детектор инцидентов.

        СТРОГОЕ ПРАВИЛО: Только нативные быстрые C-FFI вызовы (psutil, GetPerformanceInfo).
        Никаких WMI, COM, heavy IOCTL или синхронных блокировок!
        """
        logger.info("[MainTick] ⚡ Главный Real-Time контур (Level 3) успешно запущен!")
        self._main_tick_count = 0

        while self.is_running:
            t0 = time.perf_counter()
            self._main_tick_count += 1

            try:
                # 1. Попроцессные метрики по PID (CPU, RAM, handles, threads) с кэшированием токенов
                top_procs = await self._collect_pid_metrics_fast()

                # 2. Базовые системные метрики (CPU, RAM + Commit/Pool, Диск I/O + Latency, Сеть I/O)
                cpu_m = self._get_fast_cpu_metrics()
                mem_m = self.collector.get_memory_metrics()
                parts, disk_io = self.collector.get_disk_metrics()
                net_m = self.collector.get_network_metrics()

                snapshot = SystemSnapshot(
                    hostname=self.static_catalog.get('hostname') or 'localhost',
                    uptime_seconds=round(time.time() - (psutil.boot_time() if PSUTIL_AVAILABLE else time.time()), 1),
                    cpu=cpu_m,
                    memory=mem_m,
                    disks=parts,
                    disk_io=disk_io,
                    network=net_m,
                    top_processes=top_procs,
                )
                self._last_snapshot = snapshot

                # 3. Запись в кольцевой буфер предыстории и проверка на инциденты (CPU spike, RAM pressure)
                try:
                    self.ring_buffer.append(snapshot.model_dump())
                    self.incident_detector.evaluate_snapshot(snapshot)
                except Exception as inc_err:
                    logger.debug(f"[MainTick] Ошибка детектора инцидентов: {inc_err}")

                # 4. Сохраняем в буфер SQLite без блокирующего fsync
                self.storage.save_snapshot(snapshot, top_n=len(top_procs))

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[MainTick] Ошибка в главном тике #{self._main_tick_count}: {e}", exc_info=True)

            dt = time.perf_counter() - t0
            mr_cfg = self.config_manager.get_multi_rate_config()
            base_rt = float(mr_cfg.get('level3_realtime_interval_seconds', 1.0))
            target_interval = self.sampling_controller.get_effective_interval(base_interval=base_rt)
            sleep_time = max(0.05, target_interval - dt)
            try:
                await asyncio.sleep(sleep_time)
            except asyncio.CancelledError:
                break

    async def _deferred_static_inventory_task(self) -> None:
        """Отложенный сбор статического паспорта системы (Level 0).

        Запускается асинхронно СТРОГО ПОСЛЕ старта главного цикла (пауза 200 мс).
        Тяжелые вызовы WMI/COM/реестра выносятся в ThreadPoolExecutor.
        """
        try:
            await asyncio.sleep(0.2)
        except asyncio.CancelledError:
            return

        logger.info("[Level-0] 🔍 Начало фонового сбора статического паспорта системы...")
        t0 = time.perf_counter()

        loop = asyncio.get_running_loop()
        try:
            self.static_catalog = await loop.run_in_executor(None, self._heavy_hardware_inventory_probe)
            self.static_inventory_loaded = True

            # Фиксируем паспорт и снимки в БД
            try:
                archive_entry = self.collector.archive_hardware_state(auto_diff=True)
                if archive_entry:
                    self.storage.save_hardware_archive(archive_entry)
            except Exception as hw_err:
                logger.debug(f"[Level-0] Ошибка архивирования оборудования: {hw_err}")

            try:
                startup_entry = self.collector.archive_startup_state(auto_diff=True)
                if startup_entry:
                    self.storage.save_startup_archive(startup_entry)
            except Exception as st_err:
                logger.debug(f"[Level-0] Ошибка архивирования автозапуска: {st_err}")

            dt = time.perf_counter() - t0
            logger.info(f"[Level-0] ✅ Паспорт системы сформирован за {dt:.2f}s и сохранен в памяти.")
        except asyncio.CancelledError:
            pass
        except Exception as ex:
            logger.error(f"[Level-0] Ошибка сбора статического паспорта: {ex}")

    def _heavy_hardware_inventory_probe(self) -> Dict[str, Any]:
        """Синхронный тяжелый опрос WMI, SPD памяти, спецификаций GPU и дисков."""
        ident = self.collector.get_system_identity()
        ram_sticks = self.collector.get_ram_sticks_sync() if hasattr(self.collector, 'get_ram_sticks_sync') else []
        if not ram_sticks and hasattr(self.collector, 'get_ram_sticks'):
            try:
                ram_sticks = asyncio.run(self.collector.get_ram_sticks())
            except Exception:
                ram_sticks = []

        phys_disks = self.collector.get_physical_disks_health(force=True)
        gpus = self.collector.get_gpu_metrics()

        cpu_model_name = "x86_64"
        if hasattr(self.collector, '_resolve_cpu_model'):
            try:
                cpu_model_name = asyncio.run(self.collector._resolve_cpu_model())
            except Exception:
                pass

        return {
            "hostname": ident.get("hostname", ""),
            "username": ident.get("username", ""),
            "os_build": ident.get("os_build", ""),
            "os_install_date": ident.get("os_install_date", ""),
            "system_language": ident.get("system_language", ""),
            "user_locale": ident.get("user_locale", ""),
            "timezone": ident.get("timezone", ""),
            "cpu_model": cpu_model_name,
            "ram_spd": [f"{r.manufacturer} {r.speed_mhz}MHz ({r.part_number})" for r in (ram_sticks or [])],
            "disks_passport": [f"{d.model} ({d.size_gb}GB, {d.media_type})" for d in (phys_disks or [])],
            "gpu_specs": [f"{g.name} ({g.vendor}, {g.memory_total_gb}GB)" for g in (gpus or [])],
        }

    async def _adaptive_sensors_loop(self) -> None:
        """Адаптивный динамический контур (Level 2): опрос сенсоров по параметрам из config.json.

        Использует Deadband, Trigger-Up (min_interval при всплеске), Cooldown
        и Exponential Back-Off (* backoff_multiplier при штиле до max_interval).
        """
        mr_cfg = self.config_manager.get_multi_rate_config()
        min_int = float(mr_cfg.get('level2_adaptive_min_interval_seconds', 0.5))
        try:
            await asyncio.sleep(min_int)
        except asyncio.CancelledError:
            return

        self._current_sensor_interval = float(mr_cfg.get('level2_adaptive_initial_interval_seconds', 2.0))
        self._cooldown_ticks = 0

        while self.is_running:
            t0 = time.perf_counter()
            mr_cfg = self.config_manager.get_multi_rate_config()
            min_interval = float(mr_cfg.get('level2_adaptive_min_interval_seconds', 0.5))
            max_interval = float(mr_cfg.get('level2_adaptive_max_interval_seconds', 30.0))
            cooldown_limit = int(mr_cfg.get('level2_cooldown_ticks', 10))
            backoff_mult = float(mr_cfg.get('level2_backoff_multiplier', 1.5))

            try:
                loop = asyncio.get_running_loop()
                readings = await loop.run_in_executor(None, self._poll_sensors_sync)

                # Проверка всплеска по Deadband
                has_spike = self.deadband_tracker.check_spike(readings)

                if has_spike:
                    self._current_sensor_interval = min_interval
                    self._cooldown_ticks = cooldown_limit
                elif self._cooldown_ticks > 0:
                    self._current_sensor_interval = min_interval
                    self._cooldown_ticks -= 1
                else:
                    # Плавное замедление при штиле
                    self._current_sensor_interval = min(max_interval, self._current_sensor_interval * backoff_mult)

                # Дедупликация и запись в SQLite (только изменения > Deadband или Heartbeat)
                filtered_readings = self.deadband_tracker.filter_records_for_storage(readings)
                if filtered_readings:
                    self.storage.save_sensor_polls(filtered_readings)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[AdaptiveSensors] Ошибка: {e}")

            dt = time.perf_counter() - t0
            sleep_time = max(0.05, self._current_sensor_interval - dt)
            try:
                await asyncio.sleep(sleep_time)
            except asyncio.CancelledError:
                break

    def _poll_sensors_sync(self) -> List[Dict[str, Any]]:
        """Синхронный сбор доступных сенсоров."""
        try:
            from .sensors import get_hardware_sensors
            sensors = get_hardware_sensors()
            return [
                {
                    "id": s.sensor_id,
                    "sensor_name": s.name,
                    "sensor_category": s.category,
                    "unit": s.unit,
                    "value": s.value,
                    "hardware_type": getattr(s, "hardware_type", "cpu"),
                    "hardware_name": getattr(s, "hardware_name", "System"),
                }
                for s in sensors
            ]
        except Exception as ex:
            logger.debug(f"[AdaptiveSensors] Ошибка сбора сенсоров: {ex}")
            return []

    async def _low_frequency_background_loop(self) -> None:
        """Низкочастотный фоновый опрос (Level 1) с интервалами из config.json."""
        mr_cfg = self.config_manager.get_multi_rate_config()
        try:
            await asyncio.sleep(float(mr_cfg.get('wal_flush_interval_seconds', 5.0)))
        except asyncio.CancelledError:
            return

        while self.is_running:
            now = time.time()
            loop = asyncio.get_running_loop()
            mr_cfg = self.config_manager.get_multi_rate_config()
            smart_interval = float(mr_cfg.get('level1_smart_interval_seconds', 43200.0))
            battery_interval = float(mr_cfg.get('level1_battery_interval_seconds', 900.0))
            security_interval = float(mr_cfg.get('level1_security_interval_seconds', 3600.0))
            scm_interval = float(mr_cfg.get('level1_scm_interval_seconds', 1800.0))
            sched_check_interval = float(mr_cfg.get('level1_schedule_check_interval_seconds', 60.0))

            try:
                # 1. SMART SSD/NVMe
                if now - self._last_smart_scan_time >= smart_interval:
                    await loop.run_in_executor(None, self._poll_smart_sync)
                    self._last_smart_scan_time = now

                # 2. Аккумулятор и профиль питания
                if now - self._last_battery_scan_time >= battery_interval:
                    await loop.run_in_executor(None, self._poll_battery_sync)
                    self._last_battery_scan_time = now

                # 3. Аудит Defender и безопасности
                if now - self._last_security_scan_time >= security_interval:
                    await loop.run_in_executor(None, self._poll_security_sync)
                    self._last_security_scan_time = now

                # 4. Реестр служб SCM и задач планировщика
                if now - self._last_scm_scan_time >= scm_interval:
                    await loop.run_in_executor(None, self._poll_scm_tasks_sync)
                    self._last_scm_scan_time = now

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[LowFreq] Ошибка: {e}")

            try:
                await asyncio.sleep(sched_check_interval)
            except asyncio.CancelledError:
                break

    def _poll_smart_sync(self) -> None:
        """Опрос SMART накопителей."""
        try:
            self.collector.get_physical_disks_health(force=True)
            logger.info("[LowFreq] 💾 S.M.A.R.T. опрос физических накопителей успешно выполнен.")
        except Exception as ex:
            logger.debug(f"[LowFreq] SMART error: {ex}")

    def _poll_battery_sync(self) -> None:
        """Опрос состояния батареи."""
        try:
            self.collector.get_battery_metrics()
        except Exception as ex:
            logger.debug(f"[LowFreq] Battery error: {ex}")

    def _poll_security_sync(self) -> None:
        """Опрос состояния безопасности и Defender."""
        try:
            from .service import TelemetryLoggerService
            svc = TelemetryLoggerService.get_instance()
            svc.collect_and_save_defender_state()
            logger.info("[LowFreq] 🛡️ Аудит безопасности Defender зафиксирован в БД.")
        except Exception as ex:
            logger.debug(f"[LowFreq] Security audit error: {ex}")

    def _poll_scm_tasks_sync(self) -> None:
        """Опрос состояния служб и планировщика."""
        try:
            self.collector.get_extended_system_audit()
        except Exception as ex:
            logger.debug(f"[LowFreq] SCM/Tasks audit error: {ex}")

    async def _batch_wal_flusher_loop(self) -> None:
        """Периодический сброс буфера в SQLite транзакцией с интервалом из конфигурации."""
        while self.is_running:
            try:
                mr_cfg = self.config_manager.get_multi_rate_config()
                flush_sec = float(mr_cfg.get('wal_flush_interval_seconds', self.config_manager.get_flush_interval_seconds()))
                await asyncio.sleep(flush_sec)
                self.storage.flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"[WalFlusher] Ошибка сброса буфера: {e}")

    async def _collect_pid_metrics_fast(self) -> List[ProcessMetrics]:
        """Быстрый сбор метрик активных процессов через psutil без блокировок."""
        if not PSUTIL_AVAILABLE:
            return []
        loop = asyncio.get_running_loop()
        top_n = self.config_manager.get_effective_process_limit()
        return await loop.run_in_executor(None, self.collector.get_top_processes, top_n, 'cpu')

    async def _collect_network_sockets_fast(self) -> List[NetworkSocketInfo]:
        """Быстрый опрос сокетов через iphlpapi.dll."""
        if not self.ip_helper:
            return []
        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(None, self.ip_helper.get_tcp_connections)
        except Exception:
            return []

    def _get_fast_cpu_metrics(self) -> CpuMetrics:
        """Получение базовых метрик CPU с поядерным распределением."""
        total_p = 0.0
        freq_mhz = 0.0
        per_core: List[float] = []
        if PSUTIL_AVAILABLE:
            try:
                per_core = psutil.cpu_percent(interval=None, percpu=True)
                total_p = round(sum(per_core) / max(len(per_core), 1), 1) if per_core else round(psutil.cpu_percent(interval=None), 1)
                cf = psutil.cpu_freq()
                if cf:
                    freq_mhz = round(cf.current, 1)
            except Exception:
                pass

        model_name = self.static_catalog.get("cpu_model") or getattr(self.collector, '_cpu_model_cached', None) or "x86_64"

        return CpuMetrics(
            model=model_name,
            total_percent=total_p,
            per_core_percent=per_core,
            frequency_mhz=freq_mhz,
            physical_cores=psutil.cpu_count(logical=False) or 1 if PSUTIL_AVAILABLE else 1,
            logical_cores=psutil.cpu_count(logical=True) or 1 if PSUTIL_AVAILABLE else 1,
        )

