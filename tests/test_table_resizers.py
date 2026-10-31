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
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 17:00:00
# =============================================================================

from __future__ import annotations
"""Тесты универсального механизма изменения высоты таблиц и кнопок 100%."""

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_WEBGUI_DIR = _ROOT / "apps" / "windows" / "api" / "webgui"


def test_table_resizer_js_exists():
    """Проверка существования и содержимого универсального скрипта table-resizer.js."""
    script_path = _WEBGUI_DIR / "js" / "table-resizer.js"
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
    css_path = _WEBGUI_DIR / "css" / "components.css"
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
    """Проверка подключения table-resizer.js в apps/index.html и admin/index.html."""
    apps_index = _WEBGUI_DIR / "apps" / "index.html"
    admin_index = _WEBGUI_DIR / "admin" / "index.html"

    assert apps_index.exists()
    assert admin_index.exists()

    assert "table-resizer.js" in apps_index.read_text(encoding="utf-8")
    assert "table-resizer.js" in admin_index.read_text(encoding="utf-8")

