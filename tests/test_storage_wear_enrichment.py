# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Storage Wear & POH Enrichment
# =============================================================================
# Description:
#   Тесты гарантированного обогащения наработки (Power On Hours / Старт) и SMART-показателей
#   накопителей из базы данных SQLite, а также валидация роутера panel-about-disks-wear.
#
# File: test_storage_wear_enrichment.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-16 19:15:00
# =============================================================================

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from apps.windows.sdk.modules.storage_manager.core.windows_storage_sensor import (
    StorageDiskHealthInfo,
    _enrich_disks_from_telemetry_db,
    _enrich_disks_with_raw_smart,
)
from apps.windows.api.routers.router_panel import _resolve_panel_sql, PANEL_SQL_REGISTRY
from apps.windows.api.routers.about_system.query_diagnostics import query_storage_battery_from_db


def test_router_panel_disks_wear_registry():
    """Проверка регистрации panel-about-disks-wear и алиасов в PANEL_SQL_REGISTRY."""
    assert "panel-about-disks-wear" in PANEL_SQL_REGISTRY
    assert "panel-about-system-4-iznos-nakopiteley-i-batarei" in PANEL_SQL_REGISTRY

    meta_wear = _resolve_panel_sql("panel-about-disks-wear")
    meta_alias = _resolve_panel_sql("panel-about-system-4-iznos-nakopiteley-i-batarei")
    assert meta_wear["table"] == "system_snapshots"
    assert meta_alias["table"] == "system_snapshots"
    assert meta_wear["sql"] == meta_alias["sql"]


def test_enrich_disks_from_telemetry_db_enrichment():
    """Проверка обогащения наработки диска из SQLite снапшота."""
    disk = StorageDiskHealthInfo(
        device_id="Disk0",
        friendly_name="TOSHIBA HDWD110",
        model="TOSHIBA HDWD110",
        serial_number="17H1BK1FS",
        bus_type="SATA",
        media_type="HDD",
        size_gb=931.5,
        power_on_hours=0,
        temperature_c=0.0,
    )

    mock_storage = MagicMock()
    mock_storage.connection.__enter__.return_value.cursor.return_value.fetchall.return_value = []
    mock_storage.get_latest_snapshot_full.return_value = {
        "physical_disks": [
            {
                "device_id": "Disk0",
                "model": "TOSHIBA HDWD110",
                "serial_number": "17H1BK1FS",
                "power_on_hours": 13890,
                "temperature_celsius": 39.0,
            }
        ]
    }

    with patch("apps.windows.telemetry.sqlite.TelemetryStorage.get_instance", return_value=mock_storage):
        _enrich_disks_from_telemetry_db([disk])

    assert disk.power_on_hours == 13890
    assert disk.temperature_c == 39.0


def test_query_storage_battery_from_db_poh_guarantee():
    """Проверка, что query_storage_battery_from_db извлекает данные дисков строго из SQLite и рассчитывает наработку."""
    mock_storage = MagicMock()
    mock_storage.get_latest_storage_data.return_value = {
        "physical_disks": [
            {
                "device_id": "Disk1",
                "model": "CT1000MX500SSD1",
                "serial_number": "2105E4F070F5",
                "power_on_hours": 10445,
                "temperature_celsius": 32.0,
                "size_gb": 931.5,
                "wear_percentage": 0.0,
                "health_status": "Healthy",
            }
        ],
        "partitions": [
            {
                "device": "D:",
                "fstype": "NTFS",
                "free_gb": 72.9,
                "total_gb": 931.5,
                "used_gb": 858.6,
            }
        ],
    }
    mock_storage.get_latest_snapshot_full.return_value = {
        "battery": {
            "has_battery": False,
        },
        "disk_io": {
            "read_bytes_per_sec": 1000,
            "write_bytes_per_sec": 500,
        },
    }

    result = query_storage_battery_from_db(mock_storage)

    assert result["status"] == "ok"
    assert len(result["disks_wear"]) == 1
    d = result["disks_wear"][0]
    assert d["device_id"] == "Disk 1"
    assert d["power_on_hours"] == 10445
    assert d["first_power_on"] is not None
    assert d["temperature_c"] == 32.0
    assert d["health_pct"] == 100
    assert "Healthy" in d["health_status"]


def test_enrich_disks_with_raw_smart():
    """Проверка прямого Win32 IOCTL SMART обогащения накопителей."""
    disk = StorageDiskHealthInfo(
        device_id="Disk0",
        friendly_name="TOSHIBA HDWD110",
        model="TOSHIBA HDWD110",
        serial_number="17H1BK1FS",
        bus_type="SATA",
        media_type="HDD",
        size_gb=931.5,
        power_on_hours=0,
        temperature_c=0.0,
    )

    mock_raw_io = MagicMock()
    mock_raw_io.query_smart_health.return_value = {
        "power_on_hours": 13933,
        "temperature_c": 38.0,
        "percentage_used": 0.0,
        "reallocated_sectors": 0,
    }

    with patch("apps.windows.sdk.modules.storage_manager.core.raw_disk_io.WindowsRawDiskIO", return_value=mock_raw_io):
        _enrich_disks_with_raw_smart([disk])

    assert disk.power_on_hours == 13933
    assert disk.temperature_c == 38.0
    mock_raw_io.query_smart_health.assert_called_once_with(0, "SATA")


def test_query_storage_battery_from_db_smart_from_db():
    """Проверка извлечения SMART метрик и наработки накопителя напрямую из БД."""
    mock_storage = MagicMock()
    mock_storage.get_latest_storage_data.return_value = {
        "physical_disks": [
            {
                "device_id": "Disk 2",
                "model": "WDC WD20EZRZ-00Z5HB0",
                "bus_type": "SATA",
                "power_on_hours": 37928,
                "temperature_c": 37.0,
                "size_gb": 1863.0,
            }
        ],
        "partitions": [],
    }
    mock_storage.get_latest_snapshot_full.return_value = {
        "battery": {"has_battery": False},
        "disk_io": {},
    }

    result = query_storage_battery_from_db(mock_storage)

    assert result["status"] == "ok"
    assert len(result["disks_wear"]) == 1
    d = result["disks_wear"][0]
    assert d["power_on_hours"] == 37928.0
    assert "37,928 ч" in d["power_on_hours_formatted"]
    assert d["first_power_on"] is not None
    assert d["temperature_c"] == 37.0


def test_query_storage_battery_from_db_usb_from_db():
    """Проверка считывания наработки и даты первого старта для USB накопителей из снимка БД."""
    mock_storage = MagicMock()
    mock_storage.get_latest_storage_data.return_value = {
        "physical_disks": [
            {
                "device_id": "Disk 4",
                "model": "Cruzer Glide 3.0",
                "serial_number": "4C530000170109209224",
                "bus_type": "USB",
                "power_on_hours": 48,
                "first_power_on": "2026-10-14",
                "temperature_c": None,
                "size_gb": 116.8,
            }
        ],
        "partitions": [],
    }
    mock_storage.get_latest_snapshot_full.return_value = {
        "battery": {"has_battery": False},
        "disk_io": {},
    }

    result = query_storage_battery_from_db(mock_storage)

    assert result["status"] == "ok"
    assert len(result["disks_wear"]) == 1
    d = result["disks_wear"][0]
    assert d["device_id"] == "Disk 4"
    assert d["power_on_hours"] == 48
    assert d["first_power_on"] == "2026-10-14"
    assert "ч" in d["power_on_hours_formatted"]


def test_query_storage_battery_free_gb_and_partition_resolution():
    """Проверка гарантированного расчета free_gb и сопоставления разделов накопителей."""
    mock_storage = MagicMock()
    mock_storage.get_latest_storage_data.return_value = {
        "physical_disks": [
            {
                "device_id": "Disk 0",
                "model": "Samsung SSD 990 EVO Plus 2TB",
                "size_gb": 1863.0,
                "health_status": "Healthy",
                "bus_type": "NVMe",
                "media_type": "SSD",
            },
            {
                "device_id": "Disk 1",
                "model": "CT1000MX500SSD1",
                "size_gb": 931.5,
                "health_status": "Healthy",
                "bus_type": "SATA",
                "media_type": "SSD",
                "partitions": ["D: [NTFS]"],
            },
        ],
        "partitions": [
            {
                "device": "C:\\",
                "mountpoint": "C:\\",
                "fstype": "NTFS",
                "total_gb": 1861.9,
                "used_gb": 921.3,
                "free_gb": 940.6,
            },
            {
                "device": "D:\\",
                "mountpoint": "D:\\",
                "fstype": "NTFS",
                "total_gb": 931.5,
                "used_gb": 859.2,
                "free_gb": 72.3,
            },
        ],
    }
    mock_storage.get_latest_snapshot_full.return_value = {
        "battery": {"has_battery": False},
        "disk_io": {},
    }

    # Имитируем сопоставление Disk 0 -> C:, а Disk 1 берется по fallback d["partitions"]
    mock_mapping = ({"0": ["C:"]}, {})

    with patch("apps.windows.api.routers.about_system.query_diagnostics._resolve_disk_num_to_letters_map", return_value=mock_mapping):
        res = query_storage_battery_from_db(mock_storage)

    assert res["status"] == "ok"
    disks = res["disks_wear"]
    assert len(disks) == 2

    # Disk 0 (через _resolve_disk_num_to_letters_map)
    d0 = disks[0]
    assert d0["id"] == "Disk 0"
    assert "C:" in d0["partitions"]
    assert d0["free_gb"] == 940.6
    assert d0["used_gb"] == 922.4
    assert d0["total_gb"] == 1863.0

    # Disk 1 (через fallback по d["partitions"])
    d1 = disks[1]
    assert d1["id"] == "Disk 1"
    assert "D:" in d1["partitions"]
    assert d1["free_gb"] == 72.3
    assert d1["used_gb"] == 859.2
    assert d1["total_gb"] == 931.5


@pytest.mark.asyncio
async def test_hardware_tree_physical_disk_power_on_hours_and_launch_date():
    """Проверка присутствия наработки (POH) и даты первого запуска для физических дисков в дереве оборудования."""
    from apps.windows.telemetry import SystemCollector

    collector = SystemCollector()
    nodes = await collector.get_hardware_tree_async(force=True)
    disk_nodes = [n for n in nodes if n.category == "Physical Disk"]

    if disk_nodes:
        # Хотя бы у одного реального диска должны присутствовать наработка и расчетный первый запуск
        has_poh = any("Время наработки (Power-On Hours)" in d.properties for d in disk_nodes)
        has_first_launch = any("Первый запуск накопителя (расчетный)" in d.properties for d in disk_nodes)

        assert has_poh is True, "Ни у одного накопителя не обнаружено время наработки"
        assert has_first_launch is True, "Ни у одного накопителя не обнаружен расчетный первый запуск"




