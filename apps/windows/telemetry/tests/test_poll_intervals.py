# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry Tests - Poll Intervals
# =============================================================================
# Description:
#   Тестирование независимых интервалов опросов для легких и тяжелых задач:
#   - Загрузка light_poll_interval_seconds, heavy_poll_interval_seconds и
#     индивидуальных интервалов из блока heavy_polls_intervals.
#   - Проверка специализированных геттеров TelemetryConfigManager.
#   - Проверка синхронизации индивидуальных интервалов в TelemetryLoggerService.
#
# File: test_poll_intervals.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 01:42:00
# =============================================================================

import json
import tempfile
import time
from pathlib import Path
import pytest

from apps.windows.telemetry.telemetry_config import TelemetryConfigManager
from apps.windows.telemetry.service import TelemetryLoggerService
from apps.windows.telemetry.sqlite import TelemetryStorage


@pytest.fixture
def temp_config_file():
    """Создает временный JSON-файл конфигурации с индивидуальными интервалами."""
    cfg_data = {
        "mode": "live_stream",
        "interval_seconds": 5.0,
        "light_poll_interval_seconds": 4.5,
        "heavy_poll_interval_seconds": 75.0,
        "heavy_polls_intervals": {
            "hardware_audit_interval_sec": 80.0,
            "startup_audit_interval_sec": 150.0,
            "extended_audit_interval_sec": 240.0,
            "defender_audit_interval_sec": 110.0,
            "process_activity_sync_interval_sec": 45.0,
            "wmi_interval_sec": 95.0,
            "smart_interval_sec": 250.0,
            "handles_interval_sec": 55.0,
            "network_ports_interval_sec": 25.0,
            "disk_scan_interval_sec": 36000.0
        },
        "log_level": "INFO",
        "modules": {
            "cpu": True,
            "memory": True,
            "disks": True,
            "network": True,
            "processes": True,
            "sensors": False
        }
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(cfg_data, f, ensure_ascii=False, indent=2)
        temp_path = Path(f.name)

    yield temp_path

    if temp_path.exists():
        temp_path.unlink()


def test_config_manager_loads_individual_intervals(temp_config_file):
    """Проверяет загрузку легких и тяжелых индивидуальных интервалов из конфига."""
    cfg_mgr = TelemetryConfigManager(config_path=temp_config_file)

    assert cfg_mgr.get_light_poll_interval_seconds() == 4.5
    assert cfg_mgr.get_heavy_poll_interval_seconds() == 75.0
    assert cfg_mgr.get_hardware_audit_interval_seconds() == 80.0
    assert cfg_mgr.get_startup_audit_interval_seconds() == 150.0
    assert cfg_mgr.get_extended_audit_interval_seconds() == 240.0
    assert cfg_mgr.get_defender_audit_interval_seconds() == 110.0
    assert cfg_mgr.get_process_activity_sync_interval_seconds() == 45.0

    all_intervals = cfg_mgr.get_all_intervals()
    assert all_intervals["light_poll_interval_seconds"] == 4.5
    assert all_intervals["heavy_poll_interval_seconds"] == 75.0
    assert all_intervals["heavy_polls_intervals"]["smart_interval_sec"] == 250.0
    assert all_intervals["heavy_polls_intervals"]["network_ports_interval_sec"] == 25.0


def test_config_manager_default_fallback():
    """Проверяет fallback к значениям по умолчанию при отсутствии секций в конфиге."""
    cfg_data = {"interval_seconds": 7.0}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(cfg_data, f)
        temp_path = Path(f.name)

    try:
        cfg_mgr = TelemetryConfigManager(config_path=temp_path)
        # Если light_poll_interval_seconds не задан, fallback на interval_seconds (7.0)
        assert cfg_mgr.get_light_poll_interval_seconds() == 7.0
        # Дефолтные значения тяжелых опросов
        assert cfg_mgr.get_heavy_poll_interval_seconds() == 90.0
        assert cfg_mgr.get_hardware_audit_interval_seconds() == 90.0
        assert cfg_mgr.get_startup_audit_interval_seconds() == 180.0
        assert cfg_mgr.get_extended_audit_interval_seconds() == 300.0
        assert cfg_mgr.get_defender_audit_interval_seconds() == 120.0
        assert cfg_mgr.get_process_activity_sync_interval_seconds() == 60.0
    finally:
        if temp_path.exists():
            temp_path.unlink()


def test_service_initialization_with_poll_intervals(temp_config_file):
    """Проверяет инициализацию и синхронизацию интервалов в TelemetryLoggerService."""
    tmp_dir = tempfile.mkdtemp(prefix="test_intervals_")
    db_path = Path(tmp_dir) / "test_intervals.db"
    storage = TelemetryStorage(db_path=db_path)
    cfg_mgr = TelemetryConfigManager(config_path=temp_config_file)

    try:
        service = TelemetryLoggerService(storage=storage, config_manager=cfg_mgr)

        # Проверяем, что интервалы сервиса считались из config_manager
        assert service.light_poll_interval_sec == 4.5
        assert service.heavy_poll_interval_sec == 75.0
        assert service.hardware_audit_interval_sec == 80.0
        assert service.startup_audit_interval_sec == 150.0
        assert service.extended_audit_interval_sec == 240.0
        assert service.defender_audit_interval_sec == 110.0
        assert service.process_activity_sync_interval_sec == 45.0

        status = service.get_status()
        assert status["light_poll_interval_seconds"] == 4.5
        assert status["heavy_poll_interval_seconds"] == 75.0
        assert "heavy_polls_intervals" in status
        assert status["heavy_polls_intervals"]["hardware_audit_interval_sec"] == 80.0
        assert status["heavy_polls_intervals"]["startup_audit_interval_sec"] == 150.0

        # Обновляем файл конфигурации и вызываем sync_config_from_manager
        with open(temp_config_file, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        cfg["light_poll_interval_seconds"] = 3.0
        cfg["heavy_polls_intervals"]["hardware_audit_interval_sec"] = 40.0
        with open(temp_config_file, "w", encoding="utf-8") as f:
            json.dump(cfg, f)

        # Даем отметке времени файла гарантированно измениться
        time.sleep(0.1)
        # sync_config_from_manager сам проверяет check_and_reload()
        service.sync_config_from_manager()

        assert service.light_poll_interval_sec == 3.0
        assert service.hardware_audit_interval_sec == 40.0
    finally:
        storage.close()
        import gc
        import shutil
        del storage
        gc.collect()
        shutil.rmtree(tmp_dir, ignore_errors=True)

