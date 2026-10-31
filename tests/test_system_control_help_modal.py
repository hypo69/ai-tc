"""
=============================================================================
Process Name: Test Windows System Control - Atomic & Composite Help Subsystem
=============================================================================
Description:
  Юнит-тесты для проверки подсистемы контекстной справки вкладки tab_system_control:
  1. Наличие всех 6 атомарных блоков справки.
  2. Проверка композитного файла help/index.html и директив [data-help-include].
  3. Проверка соответствия стандартам тем (отсутствие hardcoded HEX/RGB цветов).
  4. Проверка интеграции кнопки вызова справки в tab_system_control/index.html.
  5. Проверка полноты ключей локализации systemControlHelp по всем 4 локалям.

File: test_system_control_help_modal.py
Project: ai-windows-admin
Package: tests
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-10-31 18:23:30
=============================================================================
"""

import json
import re
import pytest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
WEBGUI_DIR = BASE_DIR / "apps" / "windows" / "api" / "webgui"
HELP_DIR = WEBGUI_DIR / "tab_system_control" / "help"
BLOCKS_DIR = HELP_DIR / "blocks"

SYSTEM_CONTROL_BLOCKS = [
    "block_summary_dashboard.html",
    "block_event_logs.html",
    "block_power_lifecycle.html",
    "block_defender_logs.html",
    "block_forensics.html",
    "block_throttling.html",
]


def test_system_control_help_files_exist():
    """Проверка наличия файлов справки вкладки tab_system_control."""
    assert HELP_DIR.exists(), f"Директория {HELP_DIR} должна существовать"
    assert (HELP_DIR / "index.html").is_file(), "Композитный index.html должен существовать"
    assert (HELP_DIR / "README.md").is_file(), "README.md документации должен существовать"

    for block_name in SYSTEM_CONTROL_BLOCKS:
        block_path = BLOCKS_DIR / block_name
        assert block_path.is_file(), f"Атомарный блок {block_name} должен существовать"
        content = block_path.read_text(encoding="utf-8")
        assert len(content.strip()) > 50, f"Блок {block_name} не должен быть пустым"
        assert "data-help-block" in content, f"Блок {block_name} должен содержать data-help-block"


def test_system_control_composite_includes():
    """Проверка корректности сборки композитного шаблона."""
    composite_path = HELP_DIR / "index.html"
    content = composite_path.read_text(encoding="utf-8")

    for block_name in SYSTEM_CONTROL_BLOCKS:
        expected = f"/html/tab_system_control/help/blocks/{block_name}"
        assert expected in content, f"Инклюд {expected} должен быть в composite"

    assert "data-help-jump=" in content, "Навигация [data-help-jump] должна присутствовать"


def test_system_control_no_hardcoded_colors():
    """Проверка отсутствия hardcoded HEX/RGB цветов."""
    hex_pattern = re.compile(r'style="[^"]*#[0-9a-fA-F]{3,6}[^"]*"')
    rgb_pattern = re.compile(r'style="[^"]*rgba?\([^)]+\)[^"]*"')

    all_templates = [HELP_DIR / "index.html"] + [BLOCKS_DIR / f for f in SYSTEM_CONTROL_BLOCKS]

    for template_path in all_templates:
        text = template_path.read_text(encoding="utf-8")
        assert not hex_pattern.search(text), f"Обнаружен HEX цвет в {template_path.name}"
        assert not rgb_pattern.search(text), f"Обнаружен RGB цвет в {template_path.name}"


def test_system_control_header_trigger_button():
    """Проверка интеграции кнопки вызова справки в заголовок index.html вкладки."""
    index_html = (WEBGUI_DIR / "tab_system_control" / "index.html").read_text(encoding="utf-8")
    assert 'data-help-url="/html/tab_system_control/help/index.html"' in index_html


def test_system_control_i18n_keys():
    """Проверка ключей systemControlHelp во всех поддерживаемых языках."""
    locales = ["ru", "en", "uk", "he"]
    for lang in locales:
        loc_file = WEBGUI_DIR / "locales" / f"{lang}.json"
        assert loc_file.is_file(), f"Файл локали {lang}.json должен существовать"
        data = json.loads(loc_file.read_text(encoding="utf-8"))

        assert "systemControlHelp" in data, f"Секция systemControlHelp должна быть в {lang}.json"
        sc_help = data["systemControlHelp"]
        assert "composite" in sc_help
        assert "summary" in sc_help
        assert "eventLogs" in sc_help
        assert "power" in sc_help
        assert "defender" in sc_help
        assert "forensics" in sc_help
        assert "throttling" in sc_help
