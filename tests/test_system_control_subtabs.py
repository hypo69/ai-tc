"""
=============================================================================
Process Name: Test System Control Subtabs and Active Panel Polling
=============================================================================
Description:
    Модульные тесты для проверки изоляции опроса активной суб-панели вкладки
    tab-system-control, поддержки составного URL вида:
    http://localhost:8001/tc#tab-system-control#<panel_id>,
    корректного обновления URL hash, деактивации опросов при переключении
    вкладок и исключения вкладки из universal panel-loader.

File: test_system_control_subtabs.py
Project: ai-windows-admin
Package: tests
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-10-20 19:15:00
=============================================================================
"""

from pathlib import Path
import pytest


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_WEBGUI_DIR = _PROJECT_ROOT / "apps" / "windows" / "api" / "webgui"


def test_system_control_active_panel_polling_logic() -> None:
    """Проверяет изоляцию сетевых опросов в main.js вкладки system control."""
    js_file = _WEBGUI_DIR / "tab_system_control" / "main.js"
    assert js_file.exists(), f"Файл {js_file} не найден"
    content = js_file.read_text(encoding="utf-8")

    # 1. Проверяем наличие ключевых функций управления субпанелями и изоляции опроса
    assert "function isSystemControlTabActive()" in content, "Функция isSystemControlTabActive() не найдена"
    assert "function normalizeSystemControlSource(" in content, "Функция normalizeSystemControlSource() не найдена"
    assert "function getSystemControlPanelFromHash()" in content, "Функция getSystemControlPanelFromHash() не найдена"
    assert "function updateUrlWithSource(" in content, "Функция updateUrlWithSource() не найдена"
    assert "function fetchActiveSourceData(" in content, "Функция fetchActiveSourceData() не найдена"
    assert "function startPolling()" in content, "Функция startPolling() не найдена"
    assert "function stopPolling()" in content, "Функция stopPolling() не найдена"
    assert "function stopPowerUptimeCounter()" in content, "Функция stopPowerUptimeCounter() не найдена"

    # 2. Проверяем наличие проверок активности вкладки и источника в функциях загрузки
    assert "activeSource !== 'activity'" in content
    assert "activeSource !== 'event-logs'" in content
    assert "activeSource !== 'power-lifecycle'" in content
    assert "activeSource !== 'defender-logs'" in content
    assert "activeSource !== 'summary-dashboard'" in content
    assert "activeSource !== 'forensics'" in content

    # 3. Проверяем, что старый слепой опросчик tab-system-control_poll удален
    assert "tab-system-control_poll" not in content, "Слепой опросчик tab-system-control_poll не удален"

    # 4. Проверяем экспорт функций управления в глобальный контекст
    assert "window.switchSystemControlSource = function(" in content
    assert "window.activateSystemControlTab = function()" in content
    assert "window.deactivateSystemControlTab = function()" in content


def test_tab_core_and_apps_main_system_control_routing() -> None:
    """Проверяет маршрутизацию суб-панелей вкладки tab-system-control в tab-core.js и apps/main.js."""
    tab_core_file = _WEBGUI_DIR / "js" / "tab-core.js"
    assert tab_core_file.exists()
    tab_core_code = tab_core_file.read_text(encoding="utf-8")

    # tab-core.js вызывает switchSystemControlSource при передаче subPanelId
    assert "window.switchSystemControlSource(subPanelId)" in tab_core_code

    apps_main_file = _WEBGUI_DIR / "apps" / "main.js"
    assert apps_main_file.exists()
    apps_main_code = apps_main_file.read_text(encoding="utf-8")

    # apps/main.js вызывает switchSystemControlSource при наличии subPanel
    assert "window.switchSystemControlSource(subPanel)" in apps_main_code

    js_main_file = _WEBGUI_DIR / "js" / "main.js"
    assert js_main_file.exists()
    js_main_code = js_main_file.read_text(encoding="utf-8")

    # js/main.js также поддерживает вызов switchSystemControlSource
    assert "window.switchSystemControlSource(subPanel)" in js_main_code


def test_panel_loader_excludes_system_control() -> None:
    """Проверяет, что universal panel-loader не делает паразитных запросов для tab-system-control."""
    panel_loader_file = _WEBGUI_DIR / "js" / "panel-loader.js"
    assert panel_loader_file.exists()
    code = panel_loader_file.read_text(encoding="utf-8")

    assert "tab-system-control" in code, "panel-loader не исключает вкладку tab-system-control"
    assert "slc-container" in code, "panel-loader не исключает контейнер slc-container"
    assert "scc-container" in code, "panel-loader не исключает контейнер scc-container"


def test_system_control_layout_and_filter_panels_height() -> None:
    """Проверяет корректность стилизации и DOM-структуры фильтров и панелей system control."""
    html_file = _WEBGUI_DIR / "tab_system_control" / "index.html"
    assert html_file.exists()
    html_content = html_file.read_text(encoding="utf-8")

    # 1. Проверяем, что панели фильтров защищены от паразитного min-height: calc(...)
    assert "#panel-system-control-defender-filter" in html_content
    assert "min-height: auto !important;" in html_content

    # 2. Проверяем, что селектор #slc-main-stream-column .slc-panel не растягивает дочерние фильтры
    assert "#slc-main-stream-column .slc-panel {" not in html_content, "Селектор #slc-main-stream-column .slc-panel не должен применяться ко всем вложенным панелям"

    # 3. Проверяем баланс структуры контейнеров (power, defender, forensics, throttling не вложены в main-row)
    idx_main_row_open = html_content.find('id="slc-main-row"')
    idx_pwr = html_content.find('id="slc-power-lifecycle-container"')
    idx_def = html_content.find('id="slc-defender-logs-container"')
    idx_forensics = html_content.find('id="slc-forensics-container"')
    idx_throttling = html_content.find('id="slc-throttling-container"')

    assert idx_main_row_open != -1
    assert idx_pwr > idx_main_row_open
    assert idx_def > idx_pwr
    assert idx_forensics > idx_def
    assert idx_throttling > idx_forensics

    # 4. Проверяем скрытие mainRow в main.js при переключении на внешние суб-панели
    js_file = _WEBGUI_DIR / "tab_system_control" / "main.js"
    assert js_file.exists()
    js_content = js_file.read_text(encoding="utf-8")
    assert "if (mainRow) mainRow.classList.add('d-none');" in js_content


def test_tables_ltr_and_rtl_alignment() -> None:
    """Проверяет выравнивание текста по левому краю в LTR и по правому в RTL во всех таблицах."""
    comp_css = _WEBGUI_DIR / "css" / "components.css"
    assert comp_css.exists()
    comp_text = comp_css.read_text(encoding="utf-8")

    # 1. Проверяем наличие логического выравнивания start для таблиц
    assert "text-align: start !important;" in comp_text

    # 2. Проверяем явные директивы для RTL (выравнивание по правому краю)
    assert '[dir="rtl"] table th' in comp_text
    assert "text-align: right !important;" in comp_text

    # 3. Проверяем явные директивы для LTR (выравнивание по левому краю)
    assert '[dir="ltr"] table th' in comp_text
    assert "text-align: left !important;" in comp_text

    # 4. Проверяем global-overrides.css
    gov_css = _WEBGUI_DIR / "css" / "global-overrides.css"
    assert gov_css.exists()
    gov_text = gov_css.read_text(encoding="utf-8")
    assert '[dir="rtl"] table th' in gov_text
    assert '[dir="ltr"] table th' in gov_text

    # 5. Проверяем, что в заголовках таблиц tab_system_control нет хардкода text-align: right
    html_file = _WEBGUI_DIR / "tab_system_control" / "index.html"
    assert html_file.exists()
    html_content = html_file.read_text(encoding="utf-8")
    assert '<th style="width: 130px; text-align: right;">' not in html_content
    assert '<th style="width: 140px; text-align: right;">' not in html_content
    assert '<th style="width: 180px; text-align: right;">' not in html_content

