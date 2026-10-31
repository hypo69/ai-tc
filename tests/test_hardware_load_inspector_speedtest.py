# -*- coding: utf-8 -*-
"""Тесты интеграции панели Speedtest в tab-hardware-load-inspector.

Файл: tests/test_hardware_load_inspector_speedtest.py
Project: ai-windows-admin
Package: tests
Updated: 2026-10-30 11:05:00
"""

from pathlib import Path


def test_system_inspector_html_contains_speedtest_panel() -> None:
    """Проверяет наличие встроенного блока Speedtest в HTML-шаблоне tab_system_inspector."""
    html_path = Path("apps/windows/api/webgui/tab_system_inspector/index.html")
    assert html_path.is_file(), f"Файл не найден: {html_path}"
    content = html_path.read_text(encoding="utf-8")

    # Проверка карточки сети и блока Speedtest
    assert 'id="sys-card-net"' in content
    assert 'id="sys-net-speedtest"' in content
    assert 'data-panel-id="speedtest"' in content
    assert 'id="sys-btn-run-speedtest"' in content

    # Проверка 4 основных шкал (Download, Upload, Ping, Grade)
    assert 'id="sys-speed-val-download"' in content
    assert 'id="sys-speed-val-upload"' in content
    assert 'id="sys-speed-val-ping"' in content
    assert 'id="sys-speed-val-grade"' in content

    # Проверка таблицы опорных серверов
    assert 'id="sys-speed-servers-tbody"' in content

    # Проверка стилей
    assert ".speed-gauge-card" in content
    assert ".net-panel" in content


def test_system_inspector_panel_network_js_integration() -> None:
    """Проверяет подключение логики Speedtest и роутинга в panel_network/panel.js."""
    js_path = Path("apps/windows/api/webgui/tab_system_inspector/panel_network/panel.js")
    assert js_path.is_file(), f"Файл не найден: {js_path}"
    content = js_path.read_text(encoding="utf-8")

    # Проверка импорта функций speedtest
    assert "runInternetSpeedtest" in content
    assert "fetchLatestSpeedtest" in content

    # Проверка привязки кнопки и роутинга
    assert "sys-btn-run-speedtest" in content
    assert "handleNetworkHashRouting" in content
    assert "speedtest" in content


def test_tab_network_panel_speedtest_multitarget_support() -> None:
    """Проверяет поддержку синхронизации нескольких вкладок в panel_speedtest/panel.js."""
    js_path = Path("apps/windows/api/webgui/tab_network/panel_speedtest/panel.js")
    assert js_path.is_file(), f"Файл не найден: {js_path}"
    content = js_path.read_text(encoding="utf-8")

    # Проверка мульти-обновления кнопок и статусов
    assert "updateAllButtons" in content
    assert "sys-btn-run-speedtest" in content
    assert "sys-speed-val-download" in content
    assert "sys-speed-servers-tbody" in content
