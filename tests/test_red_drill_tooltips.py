# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Tests - Red Drill Tooltips Verification
# =============================================================================
# Description:
#   Модульные тесты для проверки отсутствия всплывающих подсказок (tooltips,
#   title, data-bs-title, data-i18n-title) для иконки красной дрели во всем
#   веб-интерфейсе системы ai-tc.
#
# Usage Examples:
#   pytest tests/test_red_drill_tooltips.py -v
#
# File: test_red_drill_tooltips.py
# Project: ai-tc
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-13 13:35:00
# =============================================================================

"""Модульные тесты для проверки отсутствия всплывающих подсказок для иконки красной дрели."""

import re
from pathlib import Path
import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_WEBGUI_DIR = _PROJECT_ROOT / "apps" / "windows" / "api" / "webgui"


def test_red_drill_no_title_in_html_and_js_templates() -> None:
    """Проверяет отсутствие подсказок title="..." в разметке и js-шаблонах с red_drill.png."""
    files_to_check = [
        _WEBGUI_DIR / "tab_about_system" / "index.html",
        _WEBGUI_DIR / "tab_processes_load_inspector" / "panel_leak_hunter" / "panel.js",
        _WEBGUI_DIR / "tab_processes_load_inspector" / "panel_process_manager" / "panel.js",
        _WEBGUI_DIR / "tab_processes_load_inspector" / "panel_top_stream" / "panel.js",
        _WEBGUI_DIR / "tab_system_inspector" / "index.html",
        _WEBGUI_DIR / "tab_system_inspector" / "panel_gpu" / "panel.js",
        _WEBGUI_DIR / "tab_windows_admin" / "panel_users" / "panel.js",
    ]

    for file_path in files_to_check:
        assert file_path.exists(), f"Файл {file_path} не найден"
        content = file_path.read_text(encoding="utf-8")

        # Ищем кнопки и картинки с красной дрелью
        # 1. Проверяем, что в кнопках дрели нет непустых подсказок
        # Допускаются только title="" или отсутствие title
        leak_btn_matches = re.findall(
            r'<button[^>]*class="[^"]*(?:btn-drilldown-proc|sys-drill-btn|panel-toggle-drill|pm-btn-drilldown)[^"]*"[^>]*>',
            content,
            re.IGNORECASE,
        )
        for btn in leak_btn_matches:
            title_match = re.search(r'title="([^"]*)"', btn, re.IGNORECASE)
            if title_match:
                assert title_match.group(1) == "", (
                    f"В файле {file_path.name} найдена непустая подсказка title: {btn}"
                )
            assert "data-i18n-title" not in btn, (
                f"В файле {file_path.name} найден атрибут data-i18n-title в кнопке дрели: {btn}"
            )


def test_global_tooltips_manager_suppresses_red_drill() -> None:
    """Проверяет наличие механизма принудительного подавления подсказок дрели в скриптах тултипов."""
    files_to_check = [
        _WEBGUI_DIR / "global-tooltips-i18n.js",
        _WEBGUI_DIR / "js" / "global-tooltips-i18n.js",
        _PROJECT_ROOT / "apps" / "common" / "webgui" / "js" / "global-tooltips-i18n.js",
    ]

    for file_path in files_to_check:
        assert file_path.exists(), f"Файл {file_path} не найден"
        content = file_path.read_text(encoding="utf-8")

        assert "isRedDrill" in content, (
            f"Метод isRedDrill отсутствует в {file_path.name}"
        )
        assert "red_drill" in content, (
            f"Проверка red_drill отсутствует в {file_path.name}"
        )
