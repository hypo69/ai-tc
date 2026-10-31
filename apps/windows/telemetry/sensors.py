# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry - Sensors
# =============================================================================
# Description:
#   Движок считывания показаний температурных датчиков, напряжений и вентиляторов.
#
# Usage Examples:
#   Python API:
#     from apps.windows.telemetry.sensors import get_hardware_sensors
#
#     res = get_hardware_sensors()
#
# File: sensors.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-30 10:55:00
# =============================================================================

from __future__ import annotations
"""Движок считывания показаний аппаратных сенсоров, сетевых метрик и скорости FAST.com."""

import os
import time
from typing import Any, List, Optional
try:
    import wmi
    _WMI_AVAILABLE = True
except ImportError:
    _WMI_AVAILABLE = False
from logger import logger
from .models import HardwareSensor
from .internet_speed import InternetSpeedSensor
from .sensor_registry import SensorProvider
from .telemetry_config import get_telemetry_config_manager

_SHARED_STORAGE_SENSOR: Optional[Any] = None
_LAST_STORAGE_PROBE_TIME: float = 0.0
_CACHED_STORAGE_SENSORS: List[HardwareSensor] = []

_LAST_CLOUD_PROBE_TIME: float = 0.0
_CACHED_CLOUD_SENSORS: List[HardwareSensor] = []

_LAST_ACPI_PROBE_TIME: float = 0.0
_CACHED_ACPI_SENSORS: List[HardwareSensor] = []


def _probe_acpi_thermal_zones() -> List[HardwareSensor]:
    """Сбор данных температурных зон Windows ACPI через in-process WMI без запуска подпроцессов PowerShell.

    Returns:
        List[HardwareSensor]: Список показаний термальных зон ACPI.
    """
    global _LAST_ACPI_PROBE_TIME, _CACHED_ACPI_SENSORS
    sensors: List[HardwareSensor] = []
    if os.name != 'nt':
        return sensors

    now = time.time()
    acpi_ttl = get_telemetry_config_manager().get_cache_ttl('acpi_thermal_ttl_sec', 15.0)
    if _CACHED_ACPI_SENSORS and (now - _LAST_ACPI_PROBE_TIME) < acpi_ttl:
        return list(_CACHED_ACPI_SENSORS)

    try:
        zones = []
        try:
            import wmi
            import pythoncom
            pythoncom.CoInitialize()
            w = wmi.WMI(namespace='root\\wmi')
            zones = list(w.MSAcpi_ThermalZoneTemperature())
        except (ImportError, Exception):
            try:
                import pythoncom
                import win32com.client
                pythoncom.CoInitialize()
                w = win32com.client.GetObject('winmgmts:\\\\.\\root\\wmi')
                zones = list(w.InstancesOf('MSAcpi_ThermalZoneTemperature'))
            except Exception as ex:
                logger.debug(f'win32com ACPI thermal probe failed: {ex}')

        for idx, zone in enumerate(zones):
            raw_temp = getattr(zone, 'CurrentTemperature', None)
            if raw_temp and raw_temp > 0:
                celsius = round(float(raw_temp) / 10.0 - 273.15, 1)
                if -20.0 <= celsius <= 125.0:
                    zone_name = getattr(zone, 'InstanceName', f'Thermal Zone {idx}')
                    sensor = HardwareSensor(
                        sensor_id=f'acpi_thermal_{idx}',
                        name=f'ACPI {zone_name}',
                        category='temperature',
                        value=celsius,
                        unit='°C'
                    )
                    sensor.provider = SensorProvider.WMI_FALLBACK
                    sensors.append(sensor)
    except Exception as ex:
        logger.debug(f'WMI ACPI thermal probe skipped: {ex}')

    _LAST_ACPI_PROBE_TIME = now
    _CACHED_ACPI_SENSORS = sensors
    return list(sensors)


def _probe_network_sensors() -> List[HardwareSensor]:
    """Probe network interface metrics using Windows native tools.

    Returns:
        List[HardwareSensor]: Network interface telemetry as sensors with provider marker.
    """
    sensors: List[HardwareSensor] = []
    try:
        import psutil
        current_net_io = psutil.net_io_counters(pernic=True)
        if current_net_io:
            for name, stats in current_net_io.items():
                s1 = HardwareSensor(sensor_id=f'net_{name}_bytes_recv', name=f'Network {name} Bytes Received', category='network', value=round(stats.bytes_recv, 2), unit='B')
                s1.provider = SensorProvider.NETWORK_SENSOR
                sensors.append(s1)

                s2 = HardwareSensor(sensor_id=f'net_{name}_bytes_sent', name=f'Network {name} Bytes Sent', category='network', value=round(stats.bytes_sent, 2), unit='B')
                s2.provider = SensorProvider.NETWORK_SENSOR
                sensors.append(s2)

                s3 = HardwareSensor(sensor_id=f'net_{name}_packets_recv', name=f'Network {name} Packets Received', category='network', value=stats.packets_recv, unit='pkts')
                s3.provider = SensorProvider.NETWORK_SENSOR
                sensors.append(s3)

                s4 = HardwareSensor(sensor_id=f'net_{name}_packets_sent', name=f'Network {name} Packets Sent', category='network', value=stats.packets_sent, unit='pkts')
                s4.provider = SensorProvider.NETWORK_SENSOR
                sensors.append(s4)

                s5 = HardwareSensor(sensor_id=f'net_{name}_errors_recv', name=f'Network {name} Errors Received', category='network', value=stats.errin, unit='errors')
                s5.provider = SensorProvider.NETWORK_SENSOR
                sensors.append(s5)

                s6 = HardwareSensor(sensor_id=f'net_{name}_errors_sent', name=f'Network {name} Errors Sent', category='network', value=stats.errout, unit='errors')
                s6.provider = SensorProvider.NETWORK_SENSOR
                sensors.append(s6)

                s7 = HardwareSensor(sensor_id=f'net_{name}_dropped_recv', name=f'Network {name} Dropped Received', category='network', value=stats.dropin, unit='pkts')
                s7.provider = SensorProvider.NETWORK_SENSOR
                sensors.append(s7)

                s8 = HardwareSensor(sensor_id=f'net_{name}_dropped_sent', name=f'Network {name} Dropped Sent', category='network', value=stats.dropout, unit='pkts')
                s8.provider = SensorProvider.NETWORK_SENSOR
                sensors.append(s8)
    except Exception as ex:
        logger.debug(f'Network sensor probe failed: {ex}')
    return sensors


def _probe_internet_speed_sensors() -> List[HardwareSensor]:
    """Собрать показания скорости интернета и характеристик сети FAST.com.

    Returns:
        List[HardwareSensor]: Метрики скорости интернета и задержки с маркером провайдера.
    """
    sensors: List[HardwareSensor] = []
    try:
        sensor = InternetSpeedSensor()
        metrics = sensor.measure_internet_speed()

        s1 = HardwareSensor(
            sensor_id='internet_ping',
            name='Internet Ping',
            category='network',
            value=round(metrics.get('ping_ms', 0.0), 2),
            unit='ms'
        )
        s1.provider = SensorProvider.INTERNET_SPEED
        sensors.append(s1)

        s2 = HardwareSensor(
            sensor_id='internet_download',
            name='Internet Download Speed',
            category='network',
            value=round(metrics.get('download_mbps', 0.0), 2),
            unit='Mbps'
        )
        s2.provider = SensorProvider.INTERNET_SPEED
        sensors.append(s2)

        s3 = HardwareSensor(
            sensor_id='internet_upload',
            name='Internet Upload Speed',
            category='network',
            value=round(metrics.get('upload_mbps', 0.0), 2),
            unit='Mbps'
        )
        s3.provider = SensorProvider.INTERNET_SPEED
        sensors.append(s3)

        s4 = HardwareSensor(
            sensor_id='internet_bufferbloat',
            name='Internet Bufferbloat',
            category='network',
            value=round(metrics.get('bufferbloat_ms', 0.0), 2),
            unit='ms'
        )
        s4.provider = SensorProvider.INTERNET_SPEED
        sensors.append(s4)

        s5 = HardwareSensor(
            sensor_id='internet_latency_loaded',
            name='Internet Loaded Latency',
            category='network',
            value=round(metrics.get('latency_loaded_ms', 0.0), 2),
            unit='ms'
        )
        s5.provider = SensorProvider.INTERNET_SPEED
        sensors.append(s5)

        averages = metrics.get('averages') or {}
        if averages.get('count', 0) > 0:
            s_avg_dl = HardwareSensor(
                sensor_id='internet_download_avg_144h',
                name='Internet Download Speed Avg (144h)',
                category='network',
                value=round(averages.get('download_avg_mbps', 0.0), 2),
                unit='Mbps'
            )
            s_avg_dl.provider = SensorProvider.INTERNET_SPEED
            sensors.append(s_avg_dl)

            s_avg_ul = HardwareSensor(
                sensor_id='internet_upload_avg_144h',
                name='Internet Upload Speed Avg (144h)',
                category='network',
                value=round(averages.get('upload_avg_mbps', 0.0), 2),
                unit='Mbps'
            )
            s_avg_ul.provider = SensorProvider.INTERNET_SPEED
            sensors.append(s_avg_ul)

            s_avg_ping = HardwareSensor(
                sensor_id='internet_ping_avg_144h',
                name='Internet Ping Avg (144h)',
                category='network',
                value=round(averages.get('ping_avg_ms', 0.0), 2),
                unit='ms'
            )
            s_avg_ping.provider = SensorProvider.INTERNET_SPEED
            sensors.append(s_avg_ping)
    except Exception as ex:
        logger.debug(f'Ошибка опроса сенсора скорости интернета: {ex}')
    return sensors


def _probe_storage_sensors() -> List[HardwareSensor]:
    """Сбор сенсоров температуры и надежности накопителей с переиспользованием инстанса и кэшем.

    :return: Список объектов HardwareSensor для дисков с provider marker.
    """
    global _SHARED_STORAGE_SENSOR, _LAST_STORAGE_PROBE_TIME, _CACHED_STORAGE_SENSORS
    sensors: List[HardwareSensor] = []
    if os.name != 'nt':
        return sensors
    now = time.time()
    storage_ttl = get_telemetry_config_manager().get_cache_ttl('storage_smart_ttl_sec', 30.0)
    if _CACHED_STORAGE_SENSORS and (now - _LAST_STORAGE_PROBE_TIME) < storage_ttl:
        return list(_CACHED_STORAGE_SENSORS)
    try:
        from apps.windows.sdk.modules.storage_manager.core.windows_storage_sensor import WindowsStorageSensor
        if _SHARED_STORAGE_SENSOR is None:
            _SHARED_STORAGE_SENSOR = WindowsStorageSensor(timeout_sec=int(storage_ttl))
        disks = _SHARED_STORAGE_SENSOR.get_physical_disks()
        for disk in disks:
            disk_slug = disk.device_id.replace('\\', '_').replace('.', '_')
            if disk.temperature_c is not None:
                s1 = HardwareSensor(sensor_id=f'disk_temp_{disk_slug}', name=f'{disk.friendly_name} Temperature', category='temperature', value=float(disk.temperature_c), unit='°C')
                s1.provider = SensorProvider.WINDOWS_STORAGE
                sensors.append(s1)
            if disk.wear_percentage is not None:
                s2 = HardwareSensor(sensor_id=f'disk_wear_{disk_slug}', name=f'{disk.friendly_name} Wear', category='wear', value=float(disk.wear_percentage), unit='%')
                s2.provider = SensorProvider.WINDOWS_STORAGE
                sensors.append(s2)
        _LAST_STORAGE_PROBE_TIME = now
        _CACHED_STORAGE_SENSORS = sensors
    except Exception as ex:
        logger.debug(f'Ошибка сбора сенсоров накопителей: {ex}')
    return list(sensors)


def _probe_cloud_storage_sensors() -> List[HardwareSensor]:
    """Сбор сенсоров свободного и занятого места для облачного хранилища OneDrive.

    Returns:
        List[HardwareSensor]: Список сенсоров для дисков OneDrive с provider marker.
    """
    global _LAST_CLOUD_PROBE_TIME, _CACHED_CLOUD_SENSORS
    now = time.time()
    cloud_ttl = get_telemetry_config_manager().get_cache_ttl('cloud_storage_ttl_sec', 120.0)
    if _CACHED_CLOUD_SENSORS and (now - _LAST_CLOUD_PROBE_TIME) < cloud_ttl:
        return list(_CACHED_CLOUD_SENSORS)

    import shutil
    sensors: List[HardwareSensor] = []
    od_paths: List[str] = []
    for env_var in ('OneDrive', 'OneDriveConsumer', 'OneDriveCommercial'):
        val = os.environ.get(env_var)
        if val and os.path.exists(val) and (val not in od_paths):
            od_paths.append(val)
    if not od_paths:
        home = os.path.expanduser('~')
        candidate = os.path.join(home, 'OneDrive')
        if os.path.exists(candidate):
            od_paths.append(candidate)
    if os.name == 'nt':
        try:
            import winreg
            for subkey in ('Software\\Microsoft\\OneDrive\\Accounts\\Personal', 'Software\\Microsoft\\OneDrive\\Accounts\\Business1', 'Software\\Microsoft\\OneDrive'):
                try:
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, subkey) as k:
                        val, _ = winreg.QueryValueEx(k, 'UserFolder')
                        if val and os.path.exists(val) and (val not in od_paths):
                            od_paths.append(val)
                except OSError:
                    pass
        except Exception:
            pass
    for idx, od_path in enumerate(od_paths):
        try:
            usage = shutil.disk_usage(od_path)
            free_gb = round(usage.free / 1024 ** 3, 2)
            total_gb = round(usage.total / 1024 ** 3, 2)
            used_pct = round(usage.used / max(usage.total, 1) * 100.0, 1)
            slug = f'_{idx + 1}' if len(od_paths) > 1 else ''
            label_suffix = f' ({os.path.basename(od_path)})' if len(od_paths) > 1 else ''

            s1 = HardwareSensor(sensor_id=f'onedrive{slug}_free_gb', name=f'OneDrive Free Space{label_suffix}', category='storage', value=free_gb, unit='GB')
            s1.provider = SensorProvider.SENSOR_COLLECTOR
            sensors.append(s1)

            s2 = HardwareSensor(sensor_id=f'onedrive{slug}_used_percent', name=f'OneDrive Used Percent{label_suffix}', category='storage', value=used_pct, unit='%')
            s2.provider = SensorProvider.SENSOR_COLLECTOR
            sensors.append(s2)

            s3 = HardwareSensor(sensor_id=f'onedrive{slug}_total_gb', name=f'OneDrive Total Capacity{label_suffix}', category='storage', value=total_gb, unit='GB')
            s3.provider = SensorProvider.SENSOR_COLLECTOR
            sensors.append(s3)
        except Exception as ex:
            logger.debug(f'Ошибка сбора сенсора для OneDrive ({od_path}): {ex}')
    _LAST_CLOUD_PROBE_TIME = now
    _CACHED_CLOUD_SENSORS = sensors
    return list(sensors)


def get_hardware_sensors(include_internet_speed: bool = False) -> List[HardwareSensor]:
    """Retrieve all available hardware sensors across all supported backends.

    Args:
        include_internet_speed: Включать ли активный замер скорости FAST.com (по умолчанию False,
            так как активный сетевой тест занимает 5-15с и не должен вызываться в быстром цикле датчиков).

    Returns:
        List[HardwareSensor]: Consolidated list of active hardware sensors.
    """
    all_sensors: List[HardwareSensor] = []
    all_sensors.extend(_probe_acpi_thermal_zones())
    all_sensors.extend(_probe_storage_sensors())
    all_sensors.extend(_probe_cloud_storage_sensors())
    all_sensors.extend(_probe_network_sensors())
    if include_internet_speed:
        all_sensors.extend(_probe_internet_speed_sensors())
    return all_sensors
