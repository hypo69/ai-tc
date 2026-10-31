# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Hardware Collector and Auditor
# =============================================================================
# Description:
#   Модульные тесты для низкоуровневого коллектора телеметрии оборудования
#   (HardwareCollector) и аналитического движка аудита (HardwareAuditor).
#
# Usage Examples:
#   CLI:
#     pytest tests/test_hardware_collector_and_auditor.py -v
#
# File: test_hardware_collector_and_auditor.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 08:00:00
# =============================================================================

from __future__ import annotations
"""Модульные тесты для сбора телеметрии и аудита оборудования."""

from datetime import datetime, timezone
import pytest

from apps.windows.telemetry.hardware_collector import HardwareCollector
from apps.windows.analytics.hardware_auditor import HardwareAuditor
from apps.windows.telemetry.collector import SystemCollector
from apps.windows.telemetry.models import DriverInfo, HardwareDeviceAudit, HardwareSensor


def test_hardware_collector_init_and_collect() -> None:
    """Тест инициализации и сбора устройств через HardwareCollector."""
    collector = HardwareCollector()
    report = collector.collect_hardware_report()

    assert report is not None
    assert report.devices_count >= 1
    assert len(report.devices) >= 1
    assert isinstance(report.summary, str)
    assert "Сбор телеметрии завершен" in report.summary


def test_hardware_collector_date_parsing() -> None:
    """Тест парсинга дат WMI и строковых форматов."""
    collector = HardwareCollector()

    # WMI формат YYYYMMDD...
    dt_wmi = collector._parse_wmi_date("20240501120000.000000+000")
    assert dt_wmi is not None
    assert dt_wmi.year == 2024
    assert dt_wmi.month == 5
    assert dt_wmi.day == 1

    # ISO формат YYYY-MM-DD
    dt_iso = collector._parse_wmi_date("2023-11-20")
    assert dt_iso is not None
    assert dt_iso.year == 2023
    assert dt_iso.month == 11
    assert dt_iso.day == 20

    # Пустые значения
    assert collector._parse_wmi_date(None) is None
    assert collector._parse_wmi_date("") is None
    assert collector._parse_wmi_date("None") is None


def test_hardware_collector_sensor_binding() -> None:
    """Тест привязки сенсоров телеметрии к устройствам."""
    collector = HardwareCollector()

    gpu_device = HardwareDeviceAudit(
        device_id="PCI\\VEN_10DE&DEV_128B",
        name="NVIDIA GeForce GT 710",
        device_class="Display",
        status="OK"
    )

    sensors = [
        HardwareSensor(sensor_id="gpu_temp", name="GPU Temperature", sensor_type="Temperature", value=45.0, unit="°C"),
        HardwareSensor(sensor_id="cpu_temp", name="CPU Package", sensor_type="Temperature", value=50.0, unit="°C"),
    ]

    matched = collector._bind_sensors_to_device(gpu_device, sensors)
    assert len(matched) == 1
    assert matched[0].sensor_id == "gpu_temp"


def test_hardware_auditor_driver_currency_analysis() -> None:
    """Тест аналитической оценки актуальности драйверов в HardwareAuditor."""
    auditor = HardwareAuditor()

    # Свежий драйвер
    fresh_date = datetime.now(timezone.utc)
    status_fresh, age_fresh = auditor.evaluate_driver_currency(fresh_date, "NVIDIA", "Display")
    assert status_fresh == "Актуален"
    assert age_fresh is not None and age_fresh >= 0

    # Старый сторонний драйвер (> 2 лет)
    old_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
    status_old, _ = auditor.evaluate_driver_currency(old_date, "Intel", "Display")
    assert "устарел" in status_old.lower()

    # Системный драйвер Microsoft (> 5 лет, но класс System)
    status_ms, _ = auditor.evaluate_driver_currency(old_date, "Microsoft", "System")
    assert status_ms == "Стандартный системный драйвер"


def test_system_collector_integration_with_hardware_collector() -> None:
    """Тест интеграции SystemCollector с HardwareCollector."""
    system_collector = SystemCollector()
    assert hasattr(system_collector, "hardware_collector")
    assert isinstance(system_collector.hardware_collector, HardwareCollector)

    report = system_collector.get_hardware_audit()
    assert report is not None
    assert report.devices_count > 0

