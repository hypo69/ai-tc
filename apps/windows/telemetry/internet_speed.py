# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry - Internet Speed
# =============================================================================
# Description:
#   Сенсор телеметрии скорости интернета и характеристик сети на базе FAST.com.
#   Выполняет периодический замер (1 раз в час / 3600 сек), сохраняет кольцевую
#   историю на 144 записи (6 суток) и рассчитывает скользящее среднее (SMA / медиану).
#
# Usage Examples:
#   Python API:
#     from apps.windows.telemetry.internet_speed import get_internet_speed_sensor
#
#     sensor = get_internet_speed_sensor()
#     metrics = sensor.measure_internet_speed()
#     stats = sensor.get_average_stats()
#     print(stats['download_avg_mbps'], stats['count'])
#
# File: internet_speed.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-30 10:55:00
# =============================================================================

from __future__ import annotations
"""Сенсор телеметрии скорости интернета FAST.com с буфером на 144 записи и усреднением."""

import asyncio
import json
import os
import statistics
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    _PSUTIL_AVAILABLE = False

from logger import logger
from apps.windows.sdk.modules.network.speedtest import NetworkSpeedTester

_speed_cache: Optional[tuple[float, Dict[str, Any]]] = None
_CACHE_TTL = 3600  # 1 час между замерами скорости для снижения нагрузки на сеть
_cache_lock = threading.Lock()
_bg_test_running = False
_bg_lock = threading.Lock()
_shared_sensor: Optional[InternetSpeedSensor] = None


def get_default_history_path() -> Path:
    """Возвращает путь к файлу истории замеров internet_speed_history.json.

    Returns:
        Path: Путь к персистентному файлу JSON.
    """
    try:
        from apps.windows.telemetry.telemetry_config import get_telemetry_config_manager
        mgr = get_telemetry_config_manager()
        data_dir = mgr.get_data_path()
    except Exception:
        appdata = os.environ.get('APPDATA') or os.environ.get('LOCALAPPDATA')
        if appdata and os.path.exists(appdata):
            data_dir = Path(appdata) / 'ai-tc' / 'telemetry'
        else:
            data_dir = Path.home() / '.config' / 'ai-tc' / 'telemetry'
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / 'internet_speed_history.json'


class InternetSpeedSensor:
    """Сенсор измерения скорости интернета, кольцевого буфера на 144 записи и усреднения."""

    def __init__(
        self,
        cache_ttl: int = _CACHE_TTL,
        max_history: int = 144,
        history_path: Optional[Path] = None,
    ) -> None:
        """Инициализация сенсора скорости интернета.

        Args:
            cache_ttl: Время жизни кеша замера в секундах (по умолчанию 3600 сек = 1 час).
            max_history: Максимальное количество хранимых записей (по умолчанию 144 = 6 суток).
            history_path: Пользовательский путь к файлу сохранения истории.
        """
        self.cache_ttl = cache_ttl
        self.max_history = max_history
        self.history_path = history_path or get_default_history_path()
        self._speedtester = NetworkSpeedTester()
        self._history_lock = threading.Lock()
        self._history: List[Dict[str, Any]] = []
        self._load_history()

    @classmethod
    def clear_cache(cls) -> None:
        """Очистить глобальный кеш замеров скорости интернета."""
        global _speed_cache
        with _cache_lock:
            _speed_cache = None

    def _load_history(self) -> None:
        """Загружает историю замеров из дискового JSON-файла."""
        if not self.history_path.is_file():
            return
        try:
            with open(self.history_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                with self._history_lock:
                    self._history = data[-self.max_history:]
        except Exception as ex:
            logger.debug(f'Не удалось загрузить историю скорости интернета: {ex}')

    def _save_history(self) -> None:
        """Сохраняет текущую историю замеров в дисковый JSON-файл."""
        try:
            with self._history_lock:
                records = list(self._history)
            tmp_path = self.history_path.with_suffix('.tmp')
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(records, f, ensure_ascii=False, indent=2)
            if tmp_path.exists():
                tmp_path.replace(self.history_path)
        except Exception as ex:
            logger.debug(f'Не удалось сохранить историю скорости интернета: {ex}')

    def get_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Возвращает накопленные исторические записи замеров скорости.

        Args:
            limit: Максимальное количество последних записей.

        Returns:
            List[Dict[str, Any]]: Список записей замеров.
        """
        with self._history_lock:
            records = list(self._history)
        if limit is not None and limit > 0:
            return records[-limit:]
        return records

    def append_record(self, record: Dict[str, Any]) -> None:
        """Добавляет замер в историю с ротацией при превышении лимита 144 записей.

        Args:
            record: Словарь метрик замера скорости.
        """
        with self._history_lock:
            self._history.append(record)
            if len(self._history) > self.max_history:
                self._history = self._history[-self.max_history:]
        self._save_history()

    def get_average_stats(self) -> Dict[str, Any]:
        """Вычисляет усредненную статистику по накопленным записям истории (до 144 записей).

        Returns:
            Dict[str, Any]: Словарь с агрегированными показателями (avg, min, max, median).
        """
        records = self.get_history()
        count = len(records)
        if count == 0:
            return {
                'count': 0,
                'max_history': self.max_history,
                'download_avg_mbps': 0.0,
                'download_min_mbps': 0.0,
                'download_max_mbps': 0.0,
                'download_median_mbps': 0.0,
                'upload_avg_mbps': 0.0,
                'upload_min_mbps': 0.0,
                'upload_max_mbps': 0.0,
                'upload_median_mbps': 0.0,
                'ping_avg_ms': 0.0,
                'ping_min_ms': 0.0,
                'ping_max_ms': 0.0,
                'ping_median_ms': 0.0,
                'bufferbloat_avg_ms': 0.0,
                'period_hours': 0.0,
            }

        downloads = [float(r.get('download_mbps', 0.0)) for r in records if float(r.get('download_mbps', 0.0)) > 0.0] or [0.0]
        uploads = [float(r.get('upload_mbps', 0.0)) for r in records if float(r.get('upload_mbps', 0.0)) > 0.0] or [0.0]
        pings = [float(r.get('ping_ms', 0.0)) for r in records if float(r.get('ping_ms', 0.0)) > 0.0] or [0.0]
        bloats = [float(r.get('bufferbloat_ms', 0.0)) for r in records]

        first_epoch = float(records[0].get('epoch', 0.0) or records[0].get('measured_at', 0.0))
        last_epoch = float(records[-1].get('epoch', 0.0) or records[-1].get('measured_at', 0.0))
        period_hours = round(max(0.0, last_epoch - first_epoch) / 3600.0, 1) if (first_epoch and last_epoch) else 0.0

        return {
            'count': count,
            'max_history': self.max_history,
            'download_avg_mbps': round(sum(downloads) / len(downloads), 2),
            'download_min_mbps': round(min(downloads), 2),
            'download_max_mbps': round(max(downloads), 2),
            'download_median_mbps': round(float(statistics.median(downloads)), 2),
            'upload_avg_mbps': round(sum(uploads) / len(uploads), 2),
            'upload_min_mbps': round(min(uploads), 2),
            'upload_max_mbps': round(max(uploads), 2),
            'upload_median_mbps': round(float(statistics.median(uploads)), 2),
            'ping_avg_ms': round(sum(pings) / len(pings), 2),
            'ping_min_ms': round(min(pings), 2),
            'ping_max_ms': round(max(pings), 2),
            'ping_median_ms': round(float(statistics.median(pings)), 2),
            'bufferbloat_avg_ms': round(sum(bloats) / len(bloats), 2),
            'first_timestamp': records[0].get('timestamp', ''),
            'last_timestamp': records[-1].get('timestamp', ''),
            'period_hours': period_hours,
        }

    def is_network_busy(self, threshold_bytes_sec: float = 5.0 * 1024 * 1024, sample_sec: float = 0.5) -> bool:
        """Проверяет, занята ли сеть прямо сейчас хостом.

        Args:
            threshold_bytes_sec: Порог активного трафика (по умолчанию 5 МБ/с).
            sample_sec: Интервал снятия замера дельты сетевого I/O.

        Returns:
            bool: True если сеть активно используется хостом.
        """
        if not _PSUTIL_AVAILABLE or not psutil:
            return False
        try:
            io1 = psutil.net_io_counters()
            time.sleep(sample_sec)
            io2 = psutil.net_io_counters()
            dt = max(0.001, sample_sec)
            speed = ((io2.bytes_recv - io1.bytes_recv) + (io2.bytes_sent - io1.bytes_sent)) / dt
            return speed > threshold_bytes_sec
        except Exception:
            return False

    def _run_speedtest_sync(self) -> Dict[str, Any]:
        """Синхронно выполнить полный цикл теста скорости FAST.com."""
        try:
            loop = None
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(lambda: asyncio.run(self._speedtester.run_full_speedtest()))
                    return future.result(timeout=60.0)
            else:
                return asyncio.run(self._speedtester.run_full_speedtest())
        except Exception as ex:
            logger.error(f'Ошибка выполнения теста скорости FAST.com в сенсоре телеметрии: {ex}')
            return {
                'download': {'speed_mbps': 0.0, 'status': 'ERROR'},
                'upload': {'speed_mbps': 0.0, 'status': 'ERROR'},
                'ping_ms': 0.0,
                'latency_unloaded_ms': 0.0,
                'latency_loaded_ms': 0.0,
                'bufferbloat_ms': 0.0,
                'meta': {'ip': 'N/A', 'isp': 'Unknown'},
                'provider': 'fast.com',
                'server': 'N/A'
            }

    def _perform_measurement_and_cache(self) -> Dict[str, Any]:
        """Выполняет замер скорости, добавляет в историю 144 записей и сохраняет в кэш."""
        global _speed_cache, _bg_test_running
        try:
            report = self._run_speedtest_sync()
            download_mbps = float(report.get('download', {}).get('speed_mbps', 0.0))
            upload_mbps = float(report.get('upload', {}).get('speed_mbps', 0.0))
            ping_ms = float(report.get('ping_ms', report.get('latency_unloaded_ms', 0.0)))
            latency_loaded_ms = float(report.get('latency_loaded_ms', 0.0))
            bufferbloat_ms = float(report.get('bufferbloat_ms', 0.0))
            meta = report.get('meta', {})
            now_ts = time.time()
            iso_ts = datetime.now(timezone.utc).isoformat()

            result: Dict[str, Any] = {
                'available': report.get('download', {}).get('status') == 'SUCCESS' or download_mbps > 0.0,
                'download_mbps': download_mbps,
                'upload_mbps': upload_mbps,
                'ping_ms': ping_ms,
                'latency_unloaded_ms': float(report.get('latency_unloaded_ms', ping_ms)),
                'latency_loaded_ms': latency_loaded_ms,
                'bufferbloat_ms': bufferbloat_ms,
                'provider': 'fast.com',
                'server': report.get('server', 'FAST.com CDN'),
                'ip': meta.get('ip', 'N/A'),
                'isp': meta.get('isp', 'Unknown ISP'),
                'measured_at': now_ts,
                'timestamp': iso_ts,
                'epoch': now_ts,
            }

            # Добавляем успешный замер в кольцевую историю на 144 записи
            if result['available']:
                self.append_record(result)

            with _cache_lock:
                _speed_cache = (time.monotonic(), result)

            logger.info(
                f'🌐 [Телеметрия FAST.com] Скорость: ↓{download_mbps:.1f} Mbps, '
                f'↑{upload_mbps:.1f} Mbps, пинг: {ping_ms:.1f} мс, bufferbloat: {bufferbloat_ms:.1f} мс'
            )
            return dict(result)
        finally:
            with _bg_lock:
                _bg_test_running = False

    def trigger_async_measure(self) -> None:
        """Запускает измерение скорости в фоновом потоке, если оно еще не выполняется."""
        global _bg_test_running
        with _bg_lock:
            if _bg_test_running:
                return
            _bg_test_running = True

        thread = threading.Thread(
            target=self._perform_measurement_and_cache,
            name="InternetSpeedTestWorker",
            daemon=True
        )
        thread.start()

    def check_and_run_hourly(self, force: bool = False, skip_if_busy: bool = True) -> Dict[str, Any]:
        """Проверяет интервал (1 час) и запускает замер скорости при необходимости.

        Args:
            force: Запустить замер принудительно, игнорируя интервал 3600с.
            skip_if_busy: Отложить замер, если сеть сейчас активно нагружена (> 5 МБ/с).

        Returns:
            Dict[str, Any]: Результат последнего замера с усредненными показателями.
        """
        now = time.time()
        records = self.get_history()
        last_record = records[-1] if records else None

        if not force and last_record:
            last_epoch = float(last_record.get('epoch', 0.0) or last_record.get('measured_at', 0.0))
            if (now - last_epoch) < self.cache_ttl:
                res = dict(last_record)
                res['averages'] = self.get_average_stats()
                return res

        if skip_if_busy and self.is_network_busy():
            logger.info("⏸️ [FAST.com] Сеть активно используется (> 5 МБ/с), замер скорости интернета отложен")
            res = dict(last_record) if last_record else {'available': False, 'status': 'SKIPPED_BUSY'}
            res['averages'] = self.get_average_stats()
            return res

        self.trigger_async_measure()
        res = dict(last_record) if last_record else {'available': True, 'status': 'IN_PROGRESS'}
        res['averages'] = self.get_average_stats()
        return res

    def measure_internet_speed(self, force_refresh: bool = False, sync: bool = False) -> Dict[str, Any]:
        """Измеряет профиль интернет-соединения через FAST.com с кешированием на 1 час.

        Args:
            force_refresh: Принудительно инициировать новый замер.
            sync: Выполнить замер синхронно с блокировкой текущего потока.

        Returns:
            Dict[str, Any]: Словарь метрик и усредненных показателей.
        """
        global _speed_cache
        with _cache_lock:
            if not force_refresh and _speed_cache is not None:
                cached_at, cached_result = _speed_cache
                if time.monotonic() - cached_at < self.cache_ttl:
                    res = dict(cached_result)
                    res['averages'] = self.get_average_stats()
                    return res

        if sync:
            res = self._perform_measurement_and_cache()
            res['averages'] = self.get_average_stats()
            return res

        self.trigger_async_measure()

        with _cache_lock:
            if _speed_cache is not None:
                _, cached_result = _speed_cache
                res = dict(cached_result)
                res['averages'] = self.get_average_stats()
                return res

        records = self.get_history()
        if records:
            res = dict(records[-1])
            res['averages'] = self.get_average_stats()
            return res

        return {
            'available': True,
            'download_mbps': 0.0,
            'upload_mbps': 0.0,
            'ping_ms': 0.0,
            'latency_unloaded_ms': 0.0,
            'latency_loaded_ms': 0.0,
            'bufferbloat_ms': 0.0,
            'provider': 'fast.com',
            'server': 'FAST.com CDN (замер в фоне...)',
            'ip': 'N/A',
            'isp': 'Unknown ISP',
            'measured_at': 0.0,
            'averages': self.get_average_stats(),
        }


def get_internet_speed_sensor() -> InternetSpeedSensor:
    """Возвращает глобальный синглтон сенсора скорости интернета FAST.com.

    Returns:
        InternetSpeedSensor: Синглтон сенсора.
    """
    global _shared_sensor
    if _shared_sensor is None:
        _shared_sensor = InternetSpeedSensor()
    return _shared_sensor


def get_internet_speed_sensors() -> List[Dict[str, Any]]:
    """Получить показания сетевых метрик скорости и скользящего среднего (144 записи) в формате списка сенсоров.

    Returns:
        List[Dict[str, Any]]: Список метрик сенсоров интернета.
    """
    sensor = get_internet_speed_sensor()
    metrics = sensor.measure_internet_speed()
    averages = metrics.get('averages') or sensor.get_average_stats()

    sensors = [
        {
            'sensor_id': 'internet_ping',
            'name': 'Internet Ping Latency',
            'category': 'network',
            'value': metrics.get('ping_ms', 0.0),
            'unit': 'ms'
        },
        {
            'sensor_id': 'internet_download',
            'name': 'Internet Download Speed',
            'category': 'network',
            'value': metrics.get('download_mbps', 0.0),
            'unit': 'Mbps'
        },
        {
            'sensor_id': 'internet_upload',
            'name': 'Internet Upload Speed',
            'category': 'network',
            'value': metrics.get('upload_mbps', 0.0),
            'unit': 'Mbps'
        },
        {
            'sensor_id': 'internet_bufferbloat',
            'name': 'Internet Bufferbloat',
            'category': 'network',
            'value': metrics.get('bufferbloat_ms', 0.0),
            'unit': 'ms'
        },
        {
            'sensor_id': 'internet_latency_loaded',
            'name': 'Internet Loaded Latency',
            'category': 'network',
            'value': metrics.get('latency_loaded_ms', 0.0),
            'unit': 'ms'
        },
    ]

    # Добавляем усредненные сенсоры по истории 144 записей (6 дней)
    if averages.get('count', 0) > 0:
        sensors.extend([
            {
                'sensor_id': 'internet_download_avg_144h',
                'name': 'Internet Download Speed Avg (144h)',
                'category': 'network',
                'value': averages.get('download_avg_mbps', 0.0),
                'unit': 'Mbps'
            },
            {
                'sensor_id': 'internet_upload_avg_144h',
                'name': 'Internet Upload Speed Avg (144h)',
                'category': 'network',
                'value': averages.get('upload_avg_mbps', 0.0),
                'unit': 'Mbps'
            },
            {
                'sensor_id': 'internet_ping_avg_144h',
                'name': 'Internet Ping Avg (144h)',
                'category': 'network',
                'value': averages.get('ping_avg_ms', 0.0),
                'unit': 'ms'
            },
            {
                'sensor_id': 'internet_history_count',
                'name': 'Internet Speed Samples Count',
                'category': 'network',
                'value': averages.get('count', 0),
                'unit': 'samples'
            },
        ])

    return sensors
