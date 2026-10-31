# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Storage Load Panel
# =============================================================================
# Description:
#   Модульные тесты панели «Параметры накопителей (Диски SSD / HDD / NVMe)»:
#   - Проверка возврата всех физических накопителей без перезаписи по модели
#   - Корректная обработка словарей из SQLite и объектов PhysicalDiskHealth
#   - Расчет сводки емкости хранилища и температуры
#   - Привязка разделов к соответствующим физическим дискам
#
# File: test_storage_load_panel.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 11:46:00
# =============================================================================

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from apps.windows.api.routers.router_storage_load import (
    DiskDriveMetric,
    DiskPartitionMetric,
    StorageSummary,
    StorageLoadResponse,
    build_storage_load,
    _detect_media_type,
    extract_smart_temperature,
)


class TestStorageLoadPanel(unittest.TestCase):
    """Тестирование сборки телеметрии дисков и накопителей для панели."""

    def test_01_all_physical_disks_preserved_without_overwrite(self) -> None:
        """Проверка, что несколько дисков (включая диски с одинаковыми моделями) не перезаписываются."""
        disks_data = [
            {
                "device_id": "Disk0",
                "model": "Samsung SSD 980 1TB",
                "serial_number": "S111",
                "media_type": "NVMe",
                "size_gb": 1000.0,
                "temperature_celsius": 42.0,
                "health_status": "Healthy",
            },
            {
                "device_id": "Disk1",
                "model": "Samsung SSD 980 1TB",  # Идентичная модель!
                "serial_number": "S222",
                "media_type": "NVMe",
                "size_gb": 1000.0,
                "temperature_celsius": 44.0,
                "health_status": "Healthy",
            },
            {
                "device_id": "Disk2",
                "model": "TOSHIBA HDWD110",
                "serial_number": "T333",
                "media_type": "HDD",
                "size_gb": 2000.0,
                "temperature_celsius": 36.0,
                "health_status": "Healthy",
            },
        ]

        partitions_data = [
            {
                "device": "C:\\",
                "mountpoint": "C:\\",
                "fstype": "NTFS",
                "total_gb": 950.0,
                "used_gb": 400.0,
                "free_gb": 550.0,
                "used_percent": 42.1,
            },
            {
                "device": "D:\\",
                "mountpoint": "D:\\",
                "fstype": "NTFS",
                "total_gb": 950.0,
                "used_gb": 600.0,
                "free_gb": 350.0,
                "used_percent": 63.2,
            },
        ]

        # Имитируем сопоставление разделов через IOCTL
        with patch(
            "apps.windows.api.routers.router_storage_load._resolve_disk_num_to_letters_map",
            return_value=({"0": ["C:"], "1": ["D:"]}, {}),
        ):
            resp = build_storage_load(
                physical_disks=disks_data,
                partitions_data=partitions_data,
            )

        # Все 3 диска должны сохраниться
        self.assertEqual(len(resp.drives), 3, "Все 3 диска должны присутствовать в ответе")
        self.assertEqual(resp.drives[0].id, "Disk0")
        self.assertEqual(resp.drives[1].id, "Disk1")
        self.assertEqual(resp.drives[2].id, "Disk2")

        # Проверяем уникальность серийных номеров
        self.assertEqual(resp.drives[0].serial_number, "S111")
        self.assertEqual(resp.drives[1].serial_number, "S222")
        self.assertEqual(resp.drives[2].serial_number, "T333")

        # Проверяем привязку разделов
        self.assertIn("C:\\", resp.drives[0].partitions)
        self.assertIn("D:\\", resp.drives[1].partitions)
        self.assertEqual(len(resp.drives[2].partitions), 0)

        # Проверяем сводку
        self.assertEqual(resp.summary.drives_count, 3)
        self.assertEqual(resp.summary.partitions_count, 2)
        self.assertEqual(resp.summary.total_gb, 4000.0)
        self.assertEqual(resp.summary.max_temperature_c, 44.0)

    def test_02_object_and_dict_compatibility(self) -> None:
        """Проверка извлечения характеристик как из объектов, так и из словарей."""
        class MockDiskObj:
            def __init__(self) -> None:
                self.device_id = "Disk3"
                self.model = "Crucial MX500"
                self.serial_number = "CRU123"
                self.media_type = "SSD"
                self.size_gb = 500.0
                self.temperature_c = 33.0
                self.health_status = "Healthy"
                self.power_on_hours = 5000
                self.wear_percentage = 2.0
                self.lifetime_write_tb = 12.5
                self.lifetime_read_tb = 15.0
                self.lifetime_write_bytes = 12500000000000
                self.lifetime_read_bytes = 15000000000000

        obj_disk = MockDiskObj()
        dict_disk = {
            "device_id": "Disk4",
            "model": "Generic USB Flash",
            "serial_number": "USB999",
            "media_type": "External",
            "size_gb": 64.0,
            "temperature_celsius": 0.0,
            "health_status": "Healthy",
        }

        with patch(
            "apps.windows.api.routers.router_storage_load._resolve_disk_num_to_letters_map",
            return_value=({}, {}),
        ):
            resp = build_storage_load(
                physical_disks=[obj_disk, dict_disk],
                partitions_data=[],
            )

        self.assertEqual(len(resp.drives), 2)
        d0 = resp.drives[0]
        self.assertEqual(d0.name, "Crucial MX500")
        self.assertEqual(d0.total_gb, 500.0)
        self.assertEqual(d0.temperature_c, 33.0)
        self.assertEqual(d0.power_on_hours, 5000)
        self.assertEqual(d0.life_percent, 98.0)

        d1 = resp.drives[1]
        self.assertEqual(d1.name, "Generic USB Flash")
        self.assertEqual(d1.total_gb, 64.0)
        self.assertIsNone(d1.temperature_c, "Температура 0.0 на флешке должна отфильтровываться в None")

    def test_03_fallback_to_partitions_when_no_physical_disks(self) -> None:
        """Проверка работы роутера при отсутствии физических дисков (fallback на разделы)."""
        partitions_data = [
            {
                "device": "C:\\",
                "mountpoint": "C:\\",
                "fstype": "NTFS",
                "total_gb": 500.0,
                "used_gb": 200.0,
                "free_gb": 300.0,
                "used_percent": 40.0,
            }
        ]

        resp = build_storage_load(
            physical_disks=[],
            partitions_data=partitions_data,
        )

        self.assertEqual(len(resp.drives), 0)
        self.assertEqual(len(resp.partitions), 1)
        self.assertEqual(resp.summary.total_gb, 500.0)
        self.assertEqual(resp.summary.used_gb, 200.0)
        self.assertEqual(resp.summary.free_gb, 300.0)
        self.assertEqual(resp.summary.used_percent, 40.0)

    def test_04_io_counters_enrichment_and_byte_counters(self) -> None:
        """Проверка обогащения счетчиками прочитанных/записанных байтов и форматирования."""
        class MockIoStat:
            def __init__(self, rb: int, wb: int, rc: int, wc: int) -> None:
                self.read_bytes = rb
                self.write_bytes = wb
                self.read_count = rc
                self.write_count = wc

        mock_perdisk = {
            "PhysicalDrive0": MockIoStat(rb=10737418240, wb=5368709120, rc=1000, wc=500),  # 10 GB R, 5 GB W
            "PhysicalDrive1": MockIoStat(rb=104857600, wb=209715200, rc=200, wc=150),      # 100 MB R, 200 MB W
        }

        disks_data = [
            {
                "device_id": "Disk0",
                "model": "NVMe Drive 0",
                "media_type": "NVMe",
                "size_gb": 1000.0,
            },
            {
                "device_id": "Disk1",
                "model": "SATA SSD 1",
                "media_type": "SSD",
                "size_gb": 500.0,
            },
        ]

        with patch("psutil.disk_io_counters", return_value=mock_perdisk):
            with patch("apps.windows.api.routers.router_storage_load._resolve_disk_num_to_letters_map", return_value=({}, {})):
                resp = build_storage_load(physical_disks=disks_data, partitions_data=[])

        self.assertEqual(len(resp.drives), 2)
        d0 = resp.drives[0]
        self.assertEqual(d0.read_bytes, 10737418240)
        self.assertEqual(d0.write_bytes, 5368709120)
        self.assertEqual(d0.read_count, 1000)
        self.assertEqual(d0.write_count, 500)
        self.assertEqual(d0.data_written_raw, "5.00 GB")
        self.assertEqual(d0.data_read_raw, "10.00 GB")

        d1 = resp.drives[1]
        self.assertEqual(d1.read_bytes, 104857600)
        self.assertEqual(d1.write_bytes, 209715200)
        self.assertEqual(d1.data_written_raw, "200.0 MB")
        self.assertEqual(d1.data_read_raw, "100.0 MB")


if __name__ == "__main__":
    unittest.main()

