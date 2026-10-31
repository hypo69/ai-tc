"""
=============================================================================
Process Name: Test Windows Processes Load Inspector - Help Subsystem
=============================================================================
Description:
  Юнит-тесты для проверки подсистемы контекстной справки вкладки tab_processes_load_inspector:
  1. Наличие всех 6 атомарных блоков справки.
  2. Проверка композитного файла help/index.html и директив [data-help-include].
  3. Проверка соответствия стандартам тем (отсутствие hardcoded HEX/RGB цветов).
  4. Проверка интеграции кнопки вызова справки в tab_processes_load_inspector/index.html.
  5. Проверка полноты ключей локализации processesInspectorHelp по всем 4 локалям.

File: test_processes_load_inspector_help_modal.py
Project: ai-windows-admin
Package: tests
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-10-31 18:41:00
=============================================================================
"""

import json
import re
import pytest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
WEBGUI_DIR = BASE_DIR / "apps" / "windows" / "api" / "webgui"
HELP_DIR = WEBGUI_DIR / "tab_processes_load_inspector" / "help"
BLOCKS_DIR = HELP_DIR / "blocks"

PROCESSES_INSPECTOR_BLOCKS = [
    "block_manager.html",
    "block_top_stream.html",
    "block_network_activity.html",
    "block_file_changes.html",
    "block_leak_hunter.html",
    "block_deep_dive.html",
]


def test_processes_inspector_help_files_exist():
    """Проверка наличия файлов справки вкладки tab_processes_load_inspector."""
    assert HELP_DIR.exists(), f"Директория {HELP_DIR} должна существовать"
    assert (HELP_DIR / "index.html").is_file(), "Композитный index.html должен существовать"
    assert (HELP_DIR / "README.md").is_file(), "README.md документации должен существовать"

    for block_name in PROCESSES_INSPECTOR_BLOCKS:
        block_path = BLOCKS_DIR / block_name
        assert block_path.is_file(), f"Атомарный блок {block_name} должен существовать"
        content = block_path.read_text(encoding="utf-8")
        assert len(content.strip()) > 50, f"Блок {block_name} не должен быть пустым"
        assert "data-help-block" in content, f"Блок {block_name} должен содержать data-help-block"


def test_processes_inspector_composite_includes():
    """Проверка корректности сборки композитного шаблона."""
    composite_path = HELP_DIR / "index.html"
    content = composite_path.read_text(encoding="utf-8")

    for block_name in PROCESSES_INSPECTOR_BLOCKS:
        expected = f"/html/tab_processes_load_inspector/help/blocks/{block_name}"
        assert expected in content, f"Инклюд {expected} должен присутствовать в composite"

    assert "data-help-jump=" in content, "Навигация [data-help-jump] должна присутствовать"


def test_processes_inspector_no_hardcoded_colors():
    """Проверка отсутствия hardcoded HEX/RGB цветов."""
    hex_pattern = re.compile(r'style="[^"]*#[0-9a-fA-F]{3,6}[^"]*"')
    rgb_pattern = re.compile(r'style="[^"]*rgba?\([^)]+\)[^"]*"')

    all_templates = [HELP_DIR / "index.html"] + [BLOCKS_DIR / f for f in PROCESSES_INSPECTOR_BLOCKS]

    for template_path in all_templates:
        text = template_path.read_text(encoding="utf-8")
        assert not hex_pattern.search(text), f"Обнаружен HEX цвет в {template_path.name}"
        assert not rgb_pattern.search(text), f"Обнаружен RGB цвет в {template_path.name}"


def test_processes_inspector_header_trigger_button():
    """Проверка интеграции кнопки вызова справки в заголовок index.html вкладки."""
    index_html = (WEBGUI_DIR / "tab_processes_load_inspector" / "index.html").read_text(encoding="utf-8")
    assert 'data-help-url="/html/tab_processes_load_inspector/help/index.html"' in index_html


def test_processes_inspector_i18n_keys():
    """Проверка ключей processesInspectorHelp во всех поддерживаемых языках."""
    locales = ["ru", "en", "uk", "he"]
    for lang in locales:
        loc_file = WEBGUI_DIR / "locales" / f"{lang}.json"
        assert loc_file.is_file(), f"Файл локали {lang}.json должен существовать"
        data = json.loads(loc_file.read_text(encoding="utf-8"))

        assert "processesInspectorHelp" in data, f"Секция processesInspectorHelp должна быть в {lang}.json"
        pi_help = data["processesInspectorHelp"]
        assert "composite" in pi_help
        assert "manager" in pi_help
        assert "topStream" in pi_help
        assert "network" in pi_help
        assert "fileChanges" in pi_help
        assert "leakHunter" in pi_help
        assert "deepDive" in pi_help
