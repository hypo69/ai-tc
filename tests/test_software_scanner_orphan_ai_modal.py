# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Software Scanner Orphan AI Modal
# =============================================================================
# Description:
#   Модульные тесты для проверки интеграции универсального модального окна
#   ИИ-помощника (AIModalDialog) для строк таблицы обнаруженных сирот и остатков ПО,
#   а также выделения блока сирот в самостоятельную субпанель с кнопкой навигации.
#
# Usage Examples:
#   pytest tests/test_software_scanner_orphan_ai_modal.py -v
#
# File: test_software_scanner_orphan_ai_modal.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 15:20:00
# =============================================================================

from __future__ import annotations
"""Тесты интеграции модального окна ИИ-ассистента и самостоятельной субпанели сирот."""

import json
from pathlib import Path
import pytest
from apps.windows.api.diagnostics_prompt_manager import prompt_manager, DEFAULT_PROMPTS


def test_orphan_prompt_templates_exist_and_valid() -> None:
    """Проверяет наличие и валидность JSON-шаблонов промптов для сирот ПО."""
    prompts_dir = Path("apps/windows/prompts/diagnostics")

    orphan_json = prompts_dir / "orphan.json"
    panel_json = prompts_dir / "panel-software-scanner-orphans.json"

    assert orphan_json.exists(), "Файл orphan.json должен существовать"
    assert panel_json.exists(), "Файл panel-software-scanner-orphans.json должен существовать"

    with open(orphan_json, "r", encoding="utf-8") as f:
        data_orphan = json.load(f)
    with open(panel_json, "r", encoding="utf-8") as f:
        data_panel = json.load(f)

    for data in [data_orphan, data_panel]:
        assert "table_type" in data
        assert "name" in data
        assert "system_instruction" in data
        assert "prompt_template" in data
        assert "questions_prompt" in data
        assert "{title}" in data["prompt_template"]
        assert "{subtitle}" in data["prompt_template"]
        assert "{metadata}" in data["prompt_template"]
        assert "{raw_data}" in data["prompt_template"]


def test_diagnostics_prompt_manager_resolves_orphan_prompts() -> None:
    """Проверяет правильность разрешения промптов для сирот через DiagnosticsPromptManager."""
    t_orphan = prompt_manager.get_template("orphan")
    assert t_orphan.table_type in ("orphan", "software")
    assert "сирот" in t_orphan.name.lower() or "остатк" in t_orphan.name.lower()

    t_panel = prompt_manager.get_template("software", panel_id="panel-software-scanner-orphans")
    assert "сирот" in t_panel.name.lower() or "остатк" in t_panel.name.lower()

    formatted = t_panel.format_prompt(
        title="Служба CDD",
        subtitle="Services_SCM",
        metadata={"Источник": "SCM"},
        raw_data='{"binary_exists": false}',
    )
    assert "Служба CDD" in formatted
    assert "Services_SCM" in formatted

    q_formatted = t_panel.format_questions_prompt(
        title="Служба CDD",
        subtitle="Services_SCM",
        metadata={"Источник": "SCM"},
        raw_data='{"binary_exists": false}',
    )
    assert len(q_formatted) > 10


def test_webgui_panel_dormant_has_ai_modal_integration() -> None:
    """Проверяет наличие обработчиков клика и вызова AIModalDialog в panel_dormant/panel.js."""
    panel_js_path = Path("apps/windows/api/webgui/tab_software_monitor/panel_dormant/panel.js")
    assert panel_js_path.exists(), "Файл panel_dormant/panel.js должен существовать"

    content = panel_js_path.read_text(encoding="utf-8")

    # Проверка функции открытия модального окна сироты
    assert "openOrphanAiModal" in content, "Функция openOrphanAiModal должна быть определена"
    assert "resolveAIModal" in content, "Функция resolveAIModal должна быть реализована"

    # Проверка вызова modal.show с каноническими параметрами
    assert "panel-software-scanner-orphans" in content, "Канонический panelId должен присутствовать"
    assert "tableType: 'orphan'" in content or 'tableType: "orphan"' in content

    # Проверка рендеринга строк таблицы сирот с классом sw-orphan-row и стилем курсора
    assert "sw-orphan-row" in content, "Строкам таблицы сирот должен присваиваться класс sw-orphan-row"
    assert "cursor: pointer" in content, "Строкам таблицы сирот должен задаваться стиль cursor: pointer"
    assert "data-orphan-index" in content, "Строкам должен присваиваться data-orphan-index"
    assert "sw-orphans-nav-badge" in content, "Бейдж навигации должен обновляться"


def test_webgui_html_markup_orphans_standalone_panel() -> None:
    """Проверяет HTML-разметку самостоятельной субпанели и кнопки навигации в меню."""
    html_path = Path("apps/windows/api/webgui/tab_software_monitor/index.html")
    assert html_path.exists(), "Файл index.html вкладки tab_software_monitor должен существовать"

    content = html_path.read_text(encoding="utf-8")

    # Кнопка субвкладки в меню
    assert 'id="subtab-sw-orphans-btn"' in content
    assert 'data-bs-target="#subpane-sw-orphans"' in content
    assert 'id="sw-orphans-nav-badge"' in content

    # Самостоятельная субпанель
    assert 'id="subpane-sw-orphans"' in content
    assert 'role="tabpanel"' in content
    assert 'id="panel-software-scanner-orphans"' in content
    assert 'id="sw-orphans-table-body"' in content
    assert 'id="sw-orphans-count-badge"' in content


def test_subtabs_navigation_panel_routing() -> None:
    """Проверяет регистрацию навигации субпанели сирот в panel_subtabs/panel.js."""
    subtabs_js = Path("apps/windows/api/webgui/tab_software_monitor/panel_subtabs/panel.js")
    assert subtabs_js.exists()

    content = subtabs_js.read_text(encoding="utf-8")
    assert "subtab-sw-orphans-btn" in content
    assert "renderOrphans" in content
    assert "'orphans'" in content or '"orphans"' in content

