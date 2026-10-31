"""
=============================================================================
Process Name: Test WebGUI Subtabs Builder Tool
=============================================================================
Description:
  Набор юнит-тестов для CLI инструмента генерации субменю и суб-вкладок
  subtabs_builder.py (.agents/skills/webgui-developer/scripts/subtabs_builder.py).
  Проверяет корректность разметки кнопок меню в стиле верхнего меню,
  оберток tab-pane и генерацию JS-хелпера с поддержкой URL маршрутизации.

File: test_subtabs_builder.py
Project: ai-windows-admin
Package: tests
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-10-28 16:40:00
=============================================================================
"""

import sys
from pathlib import Path

# Подключаем директорию скриптов навыка
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / ".agents" / "skills" / "webgui-developer" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from subtabs_builder import (
    build_subtabs_header_html,
    build_tab_pane_wrapper,
    build_subtabs_js_helper,
    parse_tabs_cli_arg,
)


def test_parse_tabs_cli_arg():
    """Проверяет парсинг строки параметров подвкладок."""
    arg_str = "manager:'Диспетчер процессов':bi-layout-text-window-reverse:text-primary top:'Топ процессов':bi-speedometer2"
    parsed = parse_tabs_cli_arg(arg_str)

    assert len(parsed) == 2
    assert parsed[0]['id'] == 'manager'
    assert parsed[0]['label'] == 'Диспетчер процессов'
    assert parsed[0]['icon'] == 'bi-layout-text-window-reverse'
    assert parsed[0]['icon_color'] == 'text-primary'

    assert parsed[1]['id'] == 'top'
    assert parsed[1]['label'] == 'Топ процессов'
    assert parsed[1]['icon'] == 'bi-speedometer2'
    assert parsed[1]['icon_color'] == ''


def test_build_subtabs_header_html():
    """Проверяет генерацию HTML разметки шапки с кнопками меню в стиле верхнего меню."""
    tabs = [
        {"id": "tab1", "label": "Вкладка 1", "icon": "bi-cpu", "icon_color": "text-primary"},
        {"id": "tab2", "label": "Вкладка 2", "icon": "bi-memory", "icon_color": "text-warning"},
    ]
    html = build_subtabs_header_html(
        title="Тестовый Заголовок",
        subtitle="Тестовый Подзаголовок",
        icon="⚡",
        prefix="test",
        tabs=tabs,
        extra_badge='<span id="badge">OK</span>',
        extra_btn='<button id="btn">Click</button>'
    )

    assert "Тестовый Заголовок" in html
    assert "Тестовый Подзаголовок" in html
    assert "⚡" in html
    assert "<!-- Блок меню переключения панелей на вкладке. Выбранная панель добавляется в url -->" in html
    assert 'id="test-subtabs-nav"' in html
    assert 'class="d-flex align-items-center gap-1 flex-wrap"' in html
    assert 'id="subtab-test-tab1-btn"' in html
    assert 'data-panel-id="tab1"' in html
    assert 'data-bs-target="#subpane-test-tab1"' in html
    assert 'class="btn btn-sm btn-outline-primary active d-flex align-items-center gap-1.5 py-1 px-2.5 rounded"' in html
    assert 'class="btn btn-sm btn-outline-primary d-flex align-items-center gap-1.5 py-1 px-2.5 rounded"' in html
    assert '<span id="badge">OK</span>' in html
    assert '<button id="btn">Click</button>' in html


def test_build_tab_pane_wrapper():
    """Проверяет генерацию обертки tab-pane."""
    pane_active = build_tab_pane_wrapper("test", "active_tab", "<div>Контент 1</div>", is_active=True, panel_id="panel-1")
    assert 'id="subpane-test-active_tab"' in pane_active
    assert 'class="tab-pane fade show active"' in pane_active
    assert 'data-panel-id="panel-1"' in pane_active
    assert '<div>Контент 1</div>' in pane_active

    pane_inactive = build_tab_pane_wrapper("test", "inactive_tab", "<div>Контент 2</div>", is_active=False)
    assert 'id="subpane-test-inactive_tab"' in pane_inactive
    assert 'class="tab-pane fade"' in pane_inactive
    assert 'show active' not in pane_inactive


def test_build_subtabs_js_helper():
    """Проверяет генерацию функции switchSubTab с поддержкой URL маршрутизации."""
    tabs = [
        {"id": "first", "label": "Первая"},
        {"id": "second", "label": "Вторая"},
    ]
    js = build_subtabs_js_helper("sample", tabs, function_name="switchMySampleTab")

    assert "window.switchMySampleTab = function(subtabId, updateUrl = true)" in js
    assert "updateUrlWithPanel(canonical);" in js
    assert "case 'first':" in js
    assert "btnId = 'subtab-sample-first-btn';" in js
    assert "case 'second':" in js
    assert "btnId = 'subtab-sample-second-btn';" in js
    assert "let btnId = 'subtab-sample-first-btn';" in js
    assert "window.bootstrap.Tab" in js
    assert "data-panel-id" in js

