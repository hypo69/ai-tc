"""
=============================================================================
Process Name: Test Windows Admin Subtabs and Layout Structure
=============================================================================
Description:
    Модульные тесты для проверки структуры разметки вкладки tab-windows-admin:
    - Расположение блока суб-вкладок (winadmin-subtabs) вверху сразу под tab-header
    - Соответствие структуры навигации эталонам tab-system-control и tab-processes-load-inspector
    - Корректность вложенности панелей и баланс корневого контейнера windows-admin-root
    - Экспорт и работоспособность функции switchWindowsAdminSubTab в main.js

File: test_windows_admin_subtabs.py
Project: ai-windows-admin
Package: tests
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-10-20 19:03:00
=============================================================================
"""

from pathlib import Path
import pytest


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_WEBGUI_DIR = _PROJECT_ROOT / "apps" / "windows" / "api" / "webgui"


def test_windows_admin_subtabs_placement_and_layout() -> None:
    """Проверяет корректное верхнее расположение суб-вкладок в tab_windows_admin."""
    html_file = _WEBGUI_DIR / "tab_windows_admin" / "index.html"
    assert html_file.exists(), f"Файл {html_file} не найден"
    content = html_file.read_text(encoding="utf-8")

    # 1. Проверяем наличие ключевых узлов структуры
    idx_root = content.find('id="windows-admin-root"')
    idx_tab_header = content.find('class="tab-header')
    idx_subtabs_container = content.find('id="winadmin-subtabs"')
    idx_tab_content = content.find('id="winadmin-subtabs-content"')
    idx_users_pane = content.find('id="subtab-winadmin-users"')
    idx_metrics = content.find('id="winadmin-hostname"')
    idx_privacy_radar = content.find('id="privacy-radar-widget"')

    assert idx_root != -1, "Корневой контейнер windows-admin-root не найден"
    assert idx_tab_header != -1, "tab-header не найден"
    assert idx_subtabs_container != -1, "Контейнер суб-вкладок winadmin-subtabs не найден"
    assert idx_tab_content != -1, "Контейнер tab-content не найден"
    assert idx_users_pane != -1, "Панель subtab-winadmin-users не найдена"
    assert idx_metrics != -1, "Виджет метрик хоста не найден"
    assert idx_privacy_radar != -1, "Виджет privacy radar не найден"

    # 2. Суб-вкладки ДОЛЖНЫ быть ВВЕРХУ:
    # root -> tab_header -> winadmin-subtabs -> tab-content -> subtab-winadmin-users -> metrics/radar
    assert idx_root < idx_tab_header, "windows-admin-root должен предшествовать tab-header"
    assert idx_tab_header < idx_subtabs_container, "tab-header должен предшествовать суб-вкладкам"
    assert idx_subtabs_container < idx_tab_content, "Суб-вкладки должны располагаться НАВЕРХУ перед содержимым tab-content"
    assert idx_subtabs_container < idx_metrics, "Суб-вкладки должны быть ВВЕРХУ над метриками хоста"
    assert idx_subtabs_container < idx_privacy_radar, "Суб-вкладки должны быть ВВЕРХУ над виджетом Privacy Radar"

    # 3. Единый стиль кнопок сабтабов как в tab-system-control и tab-processes-load-inspector
    assert "btn btn-sm btn-outline-primary" in content, "Кнопки суб-вкладок должны иметь класс btn-outline-primary"
    assert 'border-bottom border-secondary border-opacity-25' in content, "Полоса суб-вкладок должна иметь стандартный разделитель"

    # 4. Проверяем наличие всех 7 обязательных кнопок суб-вкладок
    required_buttons = [
        "subtab-winadmin-users-btn",
        "subtab-winadmin-groups-btn",
        "subtab-winadmin-events-btn",
        "subtab-winadmin-security-btn",
        "subtab-winadmin-pid-btn",
        "subtab-winadmin-catalog-btn",
        "subtab-winadmin-acl-btn",
    ]
    for btn_id in required_buttons:
        assert f'id="{btn_id}"' in content, f"Кнопка суб-вкладки {btn_id} отсутствует в index.html"


def test_windows_admin_main_js_subtab_switching() -> None:
    """Проверяет логику переключения субпанелей в main.js вкладки tab_windows_admin."""
    js_file = _WEBGUI_DIR / "tab_windows_admin" / "main.js"
    assert js_file.exists(), f"Файл {js_file} не найден"
    content = js_file.read_text(encoding="utf-8")

    # Проверяем экспорт и логику switchWindowsAdminSubTab
    assert "export function switchWindowsAdminSubTab(" in content
    assert "window.switchWindowsAdminSubTab = switchWindowsAdminSubTab;" in content
    assert "subtab-winadmin-" in content
    assert "new window.bootstrap.Tab(btn).show()" in content

