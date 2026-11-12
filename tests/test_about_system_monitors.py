# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - About System Monitors
# =============================================================================
# Description:
#   Тестирование корректного отображения всех подключенных мониторов и фильтрации
#   фиктивных виртуальных дисплеев Session 0 (WinDisc) в панели «О системе».
#
# File: test_about_system_monitors.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-03 14:05:00
# =============================================================================

from pathlib import Path
import pytest
from unittest.mock import MagicMock

from apps.windows.telemetry.sqlite import TelemetryStorage
from apps.windows.api.routers.about_system.query_summary import query_system_summary_full


@pytest.mark.asyncio
async def test_summary_monitors_contains_all_three_displays():
    """Проверка присутствия всех подключенных мониторов в сводке системы."""
    storage = TelemetryStorage.get_instance(read_only=True)
    summary = await query_system_summary_full(storage)

    monitors = summary.get("monitors", [])
    assert len(monitors) >= 3, f"Ожидалось не менее 3 мониторов, получено: {len(monitors)}"

    devices = [m.get("device") for m in monitors]
    for dev in devices:
        assert "windisc" not in str(dev).lower(), f"Обнаружен фиктивный WinDisc монитор: {dev}"

    # Проверяем наличие основного монитора
    primary_monitors = [m for m in monitors if m.get("is_primary")]
    assert len(primary_monitors) >= 1, "Должен присутствовать хотя бы один основной монитор"

    # Проверяем полноту атрибутов каждого дисплея
    for m in monitors:
        assert m.get("name"), "Имя монитора должно быть заполнено"
        assert m.get("width") and m.get("height"), "Разрешение экрана должно быть заполнено"
        assert m.get("frequency_hz"), "Частота развертки должна быть заполнена"
        assert m.get("orientation") in ("горизонтальная", "вертикальная"), "Ориентация должна быть указана"
        assert "adapter" in m, "Поле видеоадаптера должно присутствовать"


@pytest.mark.asyncio
async def test_session0_windisc_is_filtered_and_replaced_with_inventory():
    """Проверка вытеснения фиктивного WinDisc монитора из снимка Session 0 реальным инвентарем."""
    mock_storage = MagicMock(spec=TelemetryStorage)
    mock_storage.get_latest_snapshot_full.return_value = {
        "hostname": "TEST-HOST",
        "monitors": [
            {
                "device": "WinDisc",
                "name": "Display Monitor",
                "vendor": "",
                "width": 1024,
                "height": 768,
                "frequency_hz": 60,
                "is_primary": True,
            }
        ]
    }
    mock_storage.get_monitor_inventory.return_value = [
        {
            "device": "\\\\.\\DISPLAY1",
            "name": "DELL S2721QS",
            "vendor": "Dell",
            "adapter": "NVIDIA GeForce GT 710",
            "width": 1920,
            "height": 1080,
            "frequency_hz": 60,
            "is_primary": False,
            "orientation": "горизонтальная",
            "serial_number": "HL35M43",
            "production_date": "Service Tag: HL35M43",
        },
        {
            "device": "\\\\.\\DISPLAY2",
            "name": "T27B300",
            "vendor": "Samsung",
            "adapter": "NVIDIA GeForce GT 710",
            "width": 1080,
            "height": 1920,
            "frequency_hz": 60,
            "is_primary": False,
            "orientation": "вертикальная",
            "serial_number": "",
            "production_date": None,
        },
        {
            "device": "\\\\.\\DISPLAY5",
            "name": "32inch LG FHD",
            "vendor": "LG Electronics",
            "adapter": "Intel(R) UHD Graphics 630",
            "width": 1920,
            "height": 1080,
            "frequency_hz": 59,
            "is_primary": True,
            "orientation": "горизонтальная",
            "serial_number": "16843009",
            "production_date": None,
        },
    ]

    summary = await query_system_summary_full(mock_storage)
    monitors = summary.get("monitors", [])

    assert len(monitors) == 3, f"Ожидалось 3 монитора из инвентаря, получено: {len(monitors)}"
    devices = [m.get("device") for m in monitors]
    assert "WinDisc" not in devices, "Фиктивный WinDisc должен быть отфильтрован"
    assert "\\\\.\\DISPLAY1" in devices
    assert "\\\\.\\DISPLAY2" in devices
    assert "\\\\.\\DISPLAY5" in devices


def test_frontend_render_monitors_spec_structure():
    """Проверка структуры и логики renderMonitorsSpec в panel_identity/panel.js."""
    panel_js_path = Path("apps/windows/api/webgui/tab_about_system/panel_identity/panel.js")
    assert panel_js_path.exists(), "Файл panel_identity/panel.js должен существовать"

    content = panel_js_path.read_text(encoding="utf-8")
    assert "renderMonitorsSpec" in content, "Функция renderMonitorsSpec должна экспортироваться"
    assert "windisc" in content.lower(), "Функция renderMonitorsSpec должна фильтровать windisc"
    assert "serial_number" in content, "renderMonitorsSpec должна поддерживать отображение серийного номера"
    assert "production_date" in content, "renderMonitorsSpec должна поддерживать дату производства"
