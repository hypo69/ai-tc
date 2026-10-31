# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - CPU Load Panel
# =============================================================================
# Description:
#   Модульные тесты панели «Загрузка CPU»:
#   - Проверка строгого чтения данных из базы данных telemetry.db
#   - Отсутствие внешних сборщиков и прямого аппаратного опроса в роутере
#   - Построение иерархии процессора (CPU -> ядра -> потоки -> сенсоры)
#
# File: test_cpu_load_panel.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 07:35:00
# =============================================================================

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock

from apps.windows.api.routers.router_cpu_load import (
    build_cpu_load,
    init_router,
    CpuLoadResponse,
    CpuCoreMetric,
    CpuThreadMetric,
    CpuSensorMetric,
)


class TestCpuLoadPanel(unittest.TestCase):
    """Тестирование роутера и сборки метрик CPU из базы данных."""

    def test_01_no_psutil_imported_in_router_module(self) -> None:
        """Проверка, что роутер не импортирует psutil и не выполняет аппаратных опросов."""
        import apps.windows.api.routers.router_cpu_load as mod
        self.assertFalse(hasattr(mod, "psutil"), "Роутер не должен содержать зависимость от psutil!")

    def test_02_build_cpu_load_from_db_records(self) -> None:
        """Проверка сборки иерархии процессора строго из структур БД."""
        db_inventory = {
            "name": "AMD Ryzen 5 5600X 6-Core Processor",
            "vendor": "AMD",
            "architecture": "x86_64",
            "physical_cores": 6,
            "logical_cores": 12,
            "base_frequency_mhz": 3700.0,
            "max_frequency_mhz": 4600.0,
            "l2_cache_kb": 3072,
            "l3_cache_kb": 32768,
            "socket": "AM4",
        }
        db_snapshot = {
            "cpu_total_percent": 18.5,
            "cpu": {
                "model": "AMD Ryzen 5 5600X 6-Core Processor",
                "total_percent": 18.5,
                "cores_usage": [12.0, 15.0, 22.0, 18.0, 10.0, 8.0, 25.0, 30.0, 14.0, 16.0, 19.0, 21.0],
            },
        }
        db_sensors = [
            {
                "sensor_id": "cpu_package_temp",
                "sensor_name": "CPU Package",
                "sensor_category": "Temperatures",
                "unit": "°C",
                "value": 48.5,
            },
            {
                "sensor_id": "cpu_package_power",
                "sensor_name": "CPU Package",
                "sensor_category": "Powers",
                "unit": "W",
                "value": 65.2,
            },
        ]
        db_history = [
            {"timestamp": "2026-10-15T07:00:00Z", "cpu_total_percent": 15.0},
            {"timestamp": "2026-10-15T07:01:00Z", "cpu_total_percent": 18.5},
        ]

        resp = build_cpu_load(
            sensors=db_sensors,
            snapshot=db_snapshot,
            history_rows=db_history,
            inventory=db_inventory,
        )

        self.assertIsInstance(resp, CpuLoadResponse)
        self.assertEqual(resp.status, "ok")
        self.assertEqual(resp.name, "AMD Ryzen 5 5600X 6-Core Processor")
        self.assertEqual(resp.total_percent, 18.5)
        self.assertEqual(resp.package_temperature_c, 48.5)
        self.assertEqual(resp.package_power_w, 65.2)
        self.assertEqual(len(resp.cores), 6)
        self.assertEqual(len(resp.threads), 12)
        self.assertEqual(resp.cores_count, 6)
        self.assertEqual(resp.threads_count, 12)
        self.assertEqual(resp.meta.get("source"), "telemetry.db/cpu_hierarchy")

    def test_03_endpoint_reads_strictly_from_telemetry_storage(self) -> None:
        """Проверка, что эндпоинт GET /api/v1/panel/cpu-load обращается только к get_cpu_hierarchy_metrics()."""
        mock_storage = MagicMock()
        mock_storage.get_cpu_hierarchy_metrics.return_value = {
            "sensors": [],
            "snapshot": {
                "cpu_total_percent": 25.0,
                "cpu": {
                    "model": "Test CPU Model",
                    "physical_cores": 4,
                    "logical_cores": 8,
                    "total_percent": 25.0,
                },
            },
            "inventory": {
                "name": "Test CPU Model",
                "physical_cores": 4,
                "logical_cores": 8,
            },
            "history": [],
        }

        router = init_router(storage=mock_storage)
        endpoint = router.routes[0].endpoint
        resp = asyncio.run(endpoint())

        self.assertEqual(resp.status, "ok")
        self.assertEqual(resp.name, "Test CPU Model")
        self.assertEqual(resp.total_percent, 25.0)
        self.assertEqual(resp.cores_count, 4)
        self.assertEqual(resp.threads_count, 8)
        mock_storage.get_cpu_hierarchy_metrics.assert_called_once()


if __name__ == "__main__":
    unittest.main()

