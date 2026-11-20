# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Test Table Resizers & 100% Expand Buttons
# =============================================================================
# Description:
#   Модульные тесты для проверки оснащения таблиц с изменяемыми данными:
#   1. Проверка наличия и структуры универсального модуля table-resizer.js.
#   2. Проверка глобальных стилей .sys-table-resizer и .btn-table-expand-100 в components.css.
#   3. Проверка разметки вкладки processes_load_inspector_tab (панели хоста и Deep Dive).
#   4. Проверка подключения скрипта в apps/index.html и admin/index.html.
#
# Usage Examples:
#   pytest tests/test_table_resizers.py -v
#
# File: test_table_resizers.py
# Project: ai-tc
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20 16:35:00
# =============================================================================

from __future__ import annotations
"""Тесты универсального механизма изменения высоты таблиц и кнопок 100%."""

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_WEBGUI_DIR = _ROOT / "apps" / "windows" / "api" / "webgui"
_COMMON_WEBGUI_DIR = _ROOT / "apps" / "common" / "webgui"


def test_table_resizer_js_exists():
    """Проверка существования и содержимого универсального скрипта table-resizer.js."""
    script_path = (_COMMON_WEBGUI_DIR / "js" / "table-resizer.js") if (_COMMON_WEBGUI_DIR / "js" / "table-resizer.js").exists() else (_WEBGUI_DIR / "js" / "table-resizer.js")
    assert script_path.exists(), f"Файл {script_path} должен существовать"
    content = script_path.read_text(encoding="utf-8")
    assert "class TableResizerInstance" in content
    assert "setupTableResizer" in content
    assert "autoAdjustTableHeight" in content
    assert "initAllTableResizers" in content
    assert "isExpanded100" in content
    assert "MutationObserver" in content


def test_components_css_has_resizer_and_expand_styles():
    """Проверка наличия стилей .sys-table-resizer и .btn-table-expand-100 в components.css."""
    css_path = (_COMMON_WEBGUI_DIR / "css" / "components.css") if (_COMMON_WEBGUI_DIR / "css" / "components.css").exists() else (_WEBGUI_DIR / "css" / "components.css")
    assert css_path.exists(), f"Файл {css_path} должен существовать"
    content = css_path.read_text(encoding="utf-8")
    assert ".sys-table-resizer" in content
    assert ".sys-table-resizer-grip" in content
    assert ".btn-table-expand-100" in content
    assert ".table-responsive.expanded-100" in content


def test_processes_load_inspector_has_resizers_and_expand_buttons():
    """Проверка наличия ползунков и кнопок 100% во всех ключевых таблицах processes_load_inspector_tab."""
    html_path = _WEBGUI_DIR / "tab_processes_load_inspector" / "index.html"
    if not html_path.exists():
        html_path = _WEBGUI_DIR / "processes_load_inspector_tab" / "index.html"
    assert html_path.exists(), f"Файл {html_path} должен существовать"
    content = html_path.read_text(encoding="utf-8")

    # 1. Топ процессов хоста (Live Stream)
    assert 'id="sys-proc-table-container"' in content
    assert 'id="sys-proc-table-resizer"' in content
    assert 'id="btn-sys-proc-expand"' in content

    # 2. Сетевая активность программ (Интернет)
    assert 'id="proc-net-table-container"' in content
    assert 'id="proc-net-table-resizer"' in content
    assert 'id="btn-proc-net-expand"' in content

    # 3. Изменения файлов в реальном времени (ReadDirectoryChangesW)
    assert 'id="proc-watcher-table-container"' in content
    assert 'id="proc-watcher-table-resizer"' in content
    assert 'id="btn-proc-watcher-expand"' in content

    # 4. Deep Dive сокеты и файлы
    assert 'id="inst-sockets-table-container"' in content
    assert 'id="inst-sockets-table-resizer"' in content
    assert 'id="btn-inst-sockets-expand"' in content

    assert 'id="inst-file-events-table-container"' in content
    assert 'id="inst-file-events-table-resizer"' in content
    assert 'id="btn-inst-file-expand"' in content


def test_processes_load_inspector_main_js_integration():
    """Проверка вызова setupTableResizer и autoAdjustTableHeight в processes_load_inspector_tab/main.js."""
    js_path = _WEBGUI_DIR / "tab_processes_load_inspector" / "main.js"
    if not js_path.exists():
        js_path = _WEBGUI_DIR / "processes_load_inspector_tab" / "main.js"
    assert js_path.exists(), f"Файл {js_path} должен существовать"
    content = js_path.read_text(encoding="utf-8")
    assert "window.setupTableResizer" in content
    assert "window.autoAdjustTableHeight?.('sys-proc-table-container'" in content
    assert "window.autoAdjustTableHeight?.('proc-net-table-container'" in content
    assert "window.autoAdjustTableHeight?.('proc-watcher-table-container'" in content


def test_index_html_files_include_table_resizer():
    """Проверка подключения table-resizer.js и table-sorter.js во всех входных HTML-страницах."""
    entry_pages = [
        _WEBGUI_DIR / "index.html",
        _WEBGUI_DIR / "apps" / "index.html",
        _WEBGUI_DIR / "admin" / "index.html",
        _WEBGUI_DIR / "user" / "index.html",
        _WEBGUI_DIR / "system_inspector.html",
    ]

    for page in entry_pages:
        assert page.exists(), f"Файл {page} должен существовать"
        content = page.read_text(encoding="utf-8")
        assert "table-resizer.js" in content, f"В {page} отсутствует подключение table-resizer.js"
        assert "table-sorter.js" in content, f"В {page} отсутствует подключение table-sorter.js"


def test_table_sorter_js_exists_and_exports_api():
    """Проверка существования и структуры универсального сортировщика таблиц table-sorter.js."""
    sorter_path = _COMMON_WEBGUI_DIR / "js" / "table-sorter.js"
    assert sorter_path.exists(), f"Файл {sorter_path} должен существовать"
    content = sorter_path.read_text(encoding="utf-8")
    assert "window.TableSorter" in content
    assert "sortTableByColumn" in content
    assert "parseCellValue" in content
    assert "data-sort-dir" in content
    assert "ut-sortable" in content
    assert "MutationObserver" in content


def test_table_resizer_universal_auto_discovery():
    """Проверка универсального обнаружения всех таблиц и компактной шапки со ссылкой 100%."""
    resizer_path = _COMMON_WEBGUI_DIR / "js" / "table-resizer.js"
    content = resizer_path.read_text(encoding="utf-8")
    assert "ensureTableContainer" in content
    assert "isAutoDiscovered" in content
    assert "ut-table-header-bar" in content
    assert "startGlobalTableObserver" in content


def test_components_css_universal_sorting_and_ltr_rtl_alignment():
    """Проверка стилей сортировки и LTR/RTL-выравнивания таблиц в обоих файлах components.css."""
    for css_path in (_WEBGUI_DIR / "css" / "components.css", _COMMON_WEBGUI_DIR / "css" / "components.css"):
        assert css_path.exists(), f"Файл {css_path} должен существовать"
        content = css_path.read_text(encoding="utf-8")
        assert "table thead th.ut-sortable" in content
        assert '[data-sort-dir="asc"]' in content
        assert '[data-sort-dir="desc"]' in content
        assert ".ut-table-header-bar" in content
        assert ".table-responsive thead th" in content
        assert "position: sticky;" in content
        assert "text-align: left !important;" in content
        assert '[dir="rtl"] table td' in content
        assert "text-align: right !important;" in content


def test_global_i18n_syncs_rtl_direction():
    """Проверка синхронизации атрибута dir (ltr/rtl) в global-i18n.js."""
    i18n_path = _WEBGUI_DIR / "js" / "global-i18n.js"
    assert i18n_path.exists()
    content = i18n_path.read_text(encoding="utf-8")
    assert "syncRtlDirection" in content
    assert "setAttribute('dir'" in content


