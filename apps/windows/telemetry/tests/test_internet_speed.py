# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Telemetry Tests - Internet Speed Sensor
# =============================================================================
# Description:
#   Модульные тесты сенсора скорости интернета FAST.com:
#   - Кольцевой буфер на 144 записи (6 суток) и автоматическая ротация.
#   - Расчет скользящего среднего, минимума, максимума и медианы.
#   - Персистентность истории на диске в формате JSON.
#   - Проверка интервала 1 раз в час (3600с) и защита от забивания сети.
#   - Формирование усредненных сенсоров телеметрии.
#
# File: test_internet_speed.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-30 10:55:00
# =============================================================================

from __future__ import annotations
"""Модульные тесты сенсора скорости интернета FAST.com и буфера на 144 записи."""

import json
import time
from pathlib import Path
import pytest

from apps.windows.telemetry.internet_speed import (
    InternetSpeedSensor,
    get_internet_speed_sensors,
)


def test_sensor_initialization(tmp_path: Path) -> None:
    """Проверка инициализации сенсора с параметрами по умолчанию."""
    hist_file = tmp_path / "test_history.json"
    sensor = InternetSpeedSensor(cache_ttl=3600, max_history=144, history_path=hist_file)

    assert sensor.max_history == 144
    assert sensor.cache_ttl == 3600
    assert len(sensor.get_history()) == 0
    stats = sensor.get_average_stats()
    assert stats["count"] == 0
    assert stats["download_avg_mbps"] == 0.0


def test_append_and_ring_buffer_144_limit(tmp_path: Path) -> None:
    """Проверка строгого удержания лимита 144 записей (ротация старых)."""
    hist_file = tmp_path / "test_history.json"
    sensor = InternetSpeedSensor(cache_ttl=3600, max_history=144, history_path=hist_file)

    # Добавляем 160 записей
    for i in range(160):
        sensor.append_record({
            "timestamp": f"2026-10-30T{i:02d}:00:00Z",
            "epoch": 1000.0 + i * 3600.0,
            "download_mbps": float(100 + i),
            "upload_mbps": float(50 + i),
            "ping_ms": 15.0,
            "bufferbloat_ms": 5.0,
            "provider": "fast.com",
            "server": "Netflix CDN",
        })

    history = sensor.get_history()
    assert len(history) == 144
    # Первой должна остаться запись с i = 16 (160 - 144 = 16)
    assert history[0]["download_mbps"] == 116.0
    # Последней должна быть запись с i = 159
    assert history[-1]["download_mbps"] == 259.0


def test_average_stats_calculation(tmp_path: Path) -> None:
    """Проверка математической точности усреднения метрик по накопленным записям."""
    hist_file = tmp_path / "test_history.json"
    sensor = InternetSpeedSensor(cache_ttl=3600, max_history=144, history_path=hist_file)

    records = [
        {"download_mbps": 100.0, "upload_mbps": 40.0, "ping_ms": 10.0, "bufferbloat_ms": 2.0, "epoch": 1000.0},
        {"download_mbps": 200.0, "upload_mbps": 60.0, "ping_ms": 20.0, "bufferbloat_ms": 4.0, "epoch": 4600.0},
        {"download_mbps": 300.0, "upload_mbps": 80.0, "ping_ms": 30.0, "bufferbloat_ms": 6.0, "epoch": 8200.0},
    ]
    for r in records:
        sensor.append_record(r)

    stats = sensor.get_average_stats()
    assert stats["count"] == 3
    assert stats["download_avg_mbps"] == 200.0
    assert stats["download_min_mbps"] == 100.0
    assert stats["download_max_mbps"] == 300.0
    assert stats["download_median_mbps"] == 200.0

    assert stats["upload_avg_mbps"] == 60.0
    assert stats["ping_avg_ms"] == 20.0
    assert stats["bufferbloat_avg_ms"] == 4.0
    assert stats["period_hours"] == 2.0


def test_history_disk_persistence(tmp_path: Path) -> None:
    """Проверка сохранения и восстановления истории из JSON-файла на диске."""
    hist_file = tmp_path / "speed_history.json"
    sensor1 = InternetSpeedSensor(max_history=144, history_path=hist_file)

    sensor1.append_record({
        "timestamp": "2026-10-30T10:00:00Z",
        "epoch": 1700000000.0,
        "download_mbps": 250.5,
        "upload_mbps": 95.2,
        "ping_ms": 12.3,
        "bufferbloat_ms": 3.1,
    })

    assert hist_file.exists()
    # Создаем новый экземпляр сенсора с тем же файлом
    sensor2 = InternetSpeedSensor(max_history=144, history_path=hist_file)
    restored_history = sensor2.get_history()
    assert len(restored_history) == 1
    assert restored_history[0]["download_mbps"] == 250.5
    assert restored_history[0]["upload_mbps"] == 95.2


def test_hourly_interval_and_busy_logic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверка соблюдения интервала 1 час и откладывания при занятой сети."""
    hist_file = tmp_path / "test_history.json"
    sensor = InternetSpeedSensor(cache_ttl=3600, max_history=144, history_path=hist_file)

    # Добавляем свежую запись
    now = 50000.0
    sensor.append_record({
        "timestamp": "2026-10-30T10:00:00Z",
        "epoch": now,
        "download_mbps": 180.0,
        "upload_mbps": 70.0,
        "ping_ms": 14.0,
        "bufferbloat_ms": 2.0,
    })

    # 1. Проверяем вызов через 30 минут (1800с) - замер не должен запускаться
    monkeypatch.setattr(time, "time", lambda: now + 1800.0)
    res = sensor.check_and_run_hourly(force=False, skip_if_busy=True)
    assert res["download_mbps"] == 180.0
    assert "averages" in res

    # 2. Проверяем вызов через 2 часа (7200с), но сеть занята хостом
    monkeypatch.setattr(time, "time", lambda: now + 7200.0)
    monkeypatch.setattr(sensor, "is_network_busy", lambda: True)
    res_busy = sensor.check_and_run_hourly(force=False, skip_if_busy=True)
    assert res_busy["download_mbps"] == 180.0
    assert res_busy["averages"]["count"] == 1


def test_sensors_generation_with_averages(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверка генерации списка сенсоров телеметрии со скользящим средним за 144 записи."""
    hist_file = tmp_path / "test_history.json"
    sensor = InternetSpeedSensor(cache_ttl=3600, max_history=144, history_path=hist_file)

    sensor.append_record({
        "download_mbps": 350.0,
        "upload_mbps": 120.0,
        "ping_ms": 8.0,
        "bufferbloat_ms": 1.5,
        "latency_loaded_ms": 15.0,
        "epoch": time.time(),
    })

    # Подменяем синглтон
    import apps.windows.telemetry.internet_speed as mod
    monkeypatch.setattr(mod, "_shared_sensor", sensor)

    sensors = get_internet_speed_sensors()
    sensor_ids = {s["sensor_id"] for s in sensors}

    # Мгновенные датчики
    assert "internet_download" in sensor_ids
    assert "internet_upload" in sensor_ids
    assert "internet_ping" in sensor_ids
    # Усредненные за 144 точки датчики
    assert "internet_download_avg_144h" in sensor_ids
    assert "internet_upload_avg_144h" in sensor_ids
    assert "internet_ping_avg_144h" in sensor_ids
    assert "internet_history_count" in sensor_ids
