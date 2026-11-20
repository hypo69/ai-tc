# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Apps Windows Telemetry Tests - Monitor Inventory
# =============================================================================
# Description:
#   TDD-тесты извлечения спецификаций мониторов и множественных дисплеев
#   из таблицы hardware_components и system_snapshots, а также обогащения
#   сводных данных системы в query_system_summary_full.
#
# Usage Examples:
#   pytest apps/windows/telemetry/tests/test_monitor_inventory.py
#
# File: test_monitor_inventory.py
# Project: ai-tc
# Package: apps.windows.telemetry.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20 15:05:00
# =============================================================================

from __future__ import annotations

import gc
import json
import shutil
import tempfile
from pathlib import Path
import pytest

from apps.windows.telemetry.sqlite import TelemetryStorage
from apps.windows.api.routers.about_system.query_summary import query_system_summary_full


@pytest.fixture
def temp_storage():
    """Создает изолированный экземпляр TelemetryStorage во временной папке."""
    tmpdir = tempfile.mkdtemp()
    db_file = Path(tmpdir) / "test_monitors.db"
    storage = TelemetryStorage(db_path=str(db_file), buffer_mode="direct")
    yield storage
    gc.collect()
    shutil.rmtree(tmpdir, ignore_errors=True)


def test_monitor_inventory_from_hardware_components(temp_storage):
    """Проверка извлечения нескольких мониторов из таблицы hardware_components."""
    storage = temp_storage
    # Записываем два тестовых монитора в hardware_components
    with storage._cm.lock, storage._cm.get_connection() as conn:
        cur = conn.cursor()
        mon1_specs = {
            "component_key": "mon_dell_27",
            "category": "Monitors & Displays",
            "name": "DELL S2721QS",
            "vendor": "Dell",
            "model": "DELL S2721QS",
            "properties_json": {
                "Устройство": r"\\.\DISPLAY1",
                "Название дисплея (EDID)": "DELL S2721QS",
                "Производитель": "Dell",
                "Разрешение экрана": "3840 x 2160",
                "Частота развертки": "60 Hz",
                "Ориентация": "горизонтальная",
                "Подключенный видеоадаптер": "NVIDIA GeForce RTX 4070",
                "Основной монитор": "Да (Основной)",
                "Серийный номер (S/N)": "HL35M43",
            },
        }
        mon2_specs = {
            "component_key": "mon_lg_portrait",
            "category": "Monitors & Displays",
            "name": "LG 27UK850",
            "vendor": "LG Electronics",
            "model": "LG 27UK850",
            "properties_json": {
                "Устройство": r"\\.\DISPLAY2",
                "Название дисплея (EDID)": "LG 27UK850",
                "Производитель": "LG Electronics",
                "Разрешение экрана": "1080 x 1920",
                "Частота развертки": "60 Hz",
                "Ориентация": "вертикальная",
                "Подключенный видеоадаптер": "NVIDIA GeForce RTX 4070",
                "Основной монитор": "Нет (Вторичный)",
                "Серийный номер (S/N)": "901NTRX",
            },
        }
        cur.execute(
            """
            INSERT INTO hardware_components (component_key, category, name, vendor, model, specs_json, first_seen, last_seen, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 100.0, 100.0, 100.0)
            """,
            ("mon_dell_27", "Monitors & Displays", "DELL S2721QS", "Dell", "DELL S2721QS", json.dumps(mon1_specs)),
        )
        cur.execute(
            """
            INSERT INTO hardware_components (component_key, category, name, vendor, model, specs_json, first_seen, last_seen, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 100.0, 100.0, 100.0)
            """,
            ("mon_lg_portrait", "Monitors & Displays", "LG 27UK850", "LG Electronics", "LG 27UK850", json.dumps(mon2_specs)),
        )
        conn.commit()

    monitors = storage.get_monitor_inventory()
    assert len(monitors) == 2

    m1 = next(m for m in monitors if m["device"] == r"\\.\DISPLAY1")
    assert m1["name"] == "DELL S2721QS"
    assert m1["width"] == 3840
    assert m1["height"] == 2160
    assert m1["frequency_hz"] == 60
    assert m1["is_primary"] is True
    assert m1["orientation"] == "горизонтальная"
    assert m1["adapter"] == "NVIDIA GeForce RTX 4070"

    m2 = next(m for m in monitors if m["device"] == r"\\.\DISPLAY2")
    assert m2["name"] == "LG 27UK850"
    assert m2["width"] == 1080
    assert m2["height"] == 1920
    assert m2["is_primary"] is False
    assert m2["orientation"] == "вертикальная"


@pytest.mark.asyncio
async def test_query_system_summary_enriches_monitors(temp_storage):
    """Проверка обогащения мониторов в query_system_summary_full."""
    storage = temp_storage
    # Добавляем в инвентарь реальное имя
    with storage._cm.lock, storage._cm.get_connection() as conn:
        cur = conn.cursor()
        specs = {
            "component_key": "mon_real",
            "category": "Monitors & Displays",
            "name": "Samsung Odyssey G7",
            "vendor": "Samsung",
            "properties_json": {
                "Устройство": r"\\.\DISPLAY1",
                "Название дисплея (EDID)": "Samsung Odyssey G7",
                "Производитель": "Samsung",
                "Разрешение экрана": "2560 x 1440",
                "Частота развертки": "240 Hz",
                "Ориентация": "горизонтальная",
                "Подключенный видеоадаптер": "NVIDIA RTX",
                "Основной монитор": "Да (Основной)",
            },
        }
        cur.execute(
            """
            INSERT INTO hardware_components (component_key, category, name, vendor, model, specs_json, first_seen, last_seen, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 100.0, 100.0, 100.0)
            """,
            ("mon_real", "Monitors & Displays", "Samsung Odyssey G7", "Samsung", "Odyssey", json.dumps(specs)),
        )
        # Вставляем снимок с Generic именем
        cur.execute(
            """
            INSERT INTO system_snapshots (
                timestamp, created_at, hostname, monitors_json
            ) VALUES (
                '2026-10-20T09:00:00', 100.0, 'TEST-PC', ?
            )
            """,
            (
                json.dumps([
                    {
                        "device": r"\\.\DISPLAY1",
                        "name": "Generic PnP Monitor",
                        "adapter": "NVIDIA RTX",
                        "width": 2560,
                        "height": 1440,
                        "frequency_hz": 240,
                        "is_primary": True,
                    }
                ]),
            ),
        )
        conn.commit()

    summary = await query_system_summary_full(storage)
    monitors = summary.get("monitors", [])
    assert len(monitors) == 1
    # Generic имя должно быть заменено на название из hardware_components
    assert monitors[0]["name"] == "Samsung Odyssey G7"
    assert monitors[0]["vendor"] == "Samsung"
    assert monitors[0]["is_primary"] is True
    assert monitors[0]["orientation"] == "горизонтальная"


def test_monitor_inventory_skips_primary_monitor_dummy_and_falls_back(temp_storage, monkeypatch):
    """Если в hardware_components активна только заглушка Primary Monitor, она игнорируется."""
    storage = temp_storage
    with storage._cm.lock, storage._cm.get_connection() as conn:
        cur = conn.cursor()
        dummy_specs = {
            "component_key": "monitors_displays_primary_monitor_1920x1080_60hz",
            "category": "Monitors & Displays",
            "name": "Primary Monitor (1920x1080 @ 60Hz, горизонтальная)",
            "vendor": "Универсальный монитор",
            "model": "Primary Monitor",
            "properties_json": {
                "Устройство": r"\\.\DISPLAY1",
                "Название дисплея (EDID)": "Primary Monitor",
                "Производитель": "Универсальный монитор",
                "Разрешение экрана": "1920 x 1080",
                "Частота развертки": "60 Hz",
                "Ориентация": "горизонтальная",
                "Подключенный видеоадаптер": "Display Adapter",
                "Основной монитор": "Да (Основной)",
            },
        }
        cur.execute(
            """
            INSERT INTO hardware_components (component_key, category, name, vendor, model, status, specs_json, first_seen, last_seen, updated_at)
            VALUES (?, ?, ?, ?, ?, 'OK', ?, 100.0, 100.0, 100.0)
            """,
            (
                "monitors_displays_primary_monitor_1920x1080_60hz",
                "Monitors & Displays",
                "Primary Monitor (1920x1080 @ 60Hz, горизонтальная)",
                "Универсальный монитор",
                "Primary Monitor",
                json.dumps(dummy_specs),
            ),
        )
        # Последний снимок содержит заглушку, а предыдущий — реальные 3 монитора
        cur.execute(
            """
            INSERT INTO system_snapshots (timestamp, created_at, hostname, monitors_json)
            VALUES ('2026-11-20T10:00:00', 100.0, 'TEST-PC', ?)
            """,
            (
                json.dumps([
                    {"device": r"\\.\DISPLAY1", "name": "Dell S2721QS", "vendor": "Dell", "serial_number": "HL35M43", "adapter": "NVIDIA GT 710", "width": 1920, "height": 1080, "frequency_hz": 60, "is_primary": False},
                    {"device": r"\\.\DISPLAY2", "name": "T27B300", "vendor": "Samsung", "serial_number": "", "adapter": "NVIDIA GT 710", "width": 1080, "height": 1920, "frequency_hz": 60, "is_primary": False},
                    {"device": r"\\.\DISPLAY5", "name": "32inch LG FHD", "vendor": "LG Electronics", "serial_number": "16843009", "adapter": "Intel UHD 630", "width": 1920, "height": 1080, "frequency_hz": 59, "is_primary": True},
                ]),
            ),
        )
        cur.execute(
            """
            INSERT INTO system_snapshots (timestamp, created_at, hostname, monitors_json)
            VALUES ('2026-11-20T11:00:00', 200.0, 'TEST-PC', ?)
            """,
            (
                json.dumps([
                    {"device": r"\\.\DISPLAY1", "name": "Primary Monitor", "vendor": "", "adapter": "Display Adapter", "width": 1920, "height": 1080, "frequency_hz": 60, "is_primary": True},
                ]),
            ),
        )
        conn.commit()

    monitors = storage.get_monitor_inventory()
    assert len(monitors) == 3
    names = {m["name"] for m in monitors}
    assert names == {"Dell S2721QS", "T27B300", "32inch LG FHD"}


@pytest.mark.asyncio
async def test_query_system_summary_ignores_dummy_primary_monitor_and_queries_live(temp_storage, monkeypatch):
    """Если в БД только заглушка Primary Monitor, query_system_summary_full опрашивает живые мониторы."""
    from apps.windows.telemetry.models import MonitorInfo
    from apps.windows.telemetry.collector import SystemCollector

    storage = temp_storage
    with storage._cm.lock, storage._cm.get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO system_snapshots (timestamp, created_at, hostname, monitors_json)
            VALUES ('2026-11-20T11:00:00', 200.0, 'TEST-PC', ?)
            """,
            (
                json.dumps([
                    {"device": r"\\.\DISPLAY1", "name": "Primary Monitor", "adapter": "Display Adapter", "width": 1920, "height": 1080, "frequency_hz": 60, "is_primary": True},
                ]),
            ),
        )
        conn.commit()

    fake_live = [
        MonitorInfo(device=r"\\.\DISPLAY1", name="Dell S2721QS", vendor="Dell", serial_number="HL35M43", adapter="NVIDIA GT 710", width=1920, height=1080, frequency_hz=60, bits_per_pixel=32, is_primary=False, orientation="горизонтальная"),
        MonitorInfo(device=r"\\.\DISPLAY5", name="32inch LG FHD", vendor="LG Electronics", serial_number="16843009", adapter="Intel UHD 630", width=1920, height=1080, frequency_hz=59, bits_per_pixel=32, is_primary=True, orientation="горизонтальная"),
    ]
    monkeypatch.setattr(SystemCollector, "get_monitors", lambda self: fake_live)

    summary = await query_system_summary_full(storage)
    monitors = summary.get("monitors", [])
    assert len(monitors) == 2
    assert {m["serial_number"] for m in monitors} == {"HL35M43", "16843009"}


