"""
=============================================================================
Process Name: Test Windows Software Monitor - Atomic & Composite Help Subsystem
=============================================================================
Description:
  Юнит-тесты для проверки подсистемы контекстной справки вкладки tab_software_monitor:
  1. Наличие всех 6 атомарных блоков справки.
  2. Проверка композитного файла help/index.html и директив [data-help-include].
  3. Проверка соответствия стандартам тем (отсутствие hardcoded HEX/RGB цветов).
  4. Проверка интеграции кнопки вызова справки в tab_software_monitor/index.html.
  5. Проверка полноты ключей локализации softwareMonitorHelp по всем 4 локалям.

File: test_software_monitor_help_modal.py
Project: ai-windows-admin
Package: tests
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-10-31 18:38:00
=============================================================================
"""

import json
import re
import pytest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
WEBGUI_DIR = BASE_DIR / "apps" / "windows" / "api" / "webgui"
HELP_DIR = WEBGUI_DIR / "tab_software_monitor" / "help"
BLOCKS_DIR = HELP_DIR / "blocks"

SOFTWARE_MONITOR_BLOCKS = [
    "block_inventory.html",
    "block_packages.html",
    "block_dormant_orphans.html",
    "block_startup.html",
    "block_transparency.html",
    "block_heavy_sockets.html",
]


def test_software_monitor_help_files_exist():
    """Проверка наличия файлов справки вкладки tab_software_monitor."""
    assert HELP_DIR.exists(), f"Директория {HELP_DIR} должна существовать"
    assert (HELP_DIR / "index.html").is_file(), "Композитный index.html должен существовать"
    assert (HELP_DIR / "README.md").is_file(), "README.md документации должен существовать"

    for block_name in SOFTWARE_MONITOR_BLOCKS:
        block_path = BLOCKS_DIR / block_name
        assert block_path.is_file(), f"Атомарный блок {block_name} должен существовать"
        content = block_path.read_text(encoding="utf-8")
        assert len(content.strip()) > 50, f"Блок {block_name} не должен быть пустым"
        assert "data-help-block" in content, f"Блок {block_name} должен содержать data-help-block"


def test_software_monitor_composite_includes():
    """Проверка корректности сборки композитного шаблона."""
    composite_path = HELP_DIR / "index.html"
    content = composite_path.read_text(encoding="utf-8")

    for block_name in SOFTWARE_MONITOR_BLOCKS:
        expected = f"/html/tab_software_monitor/help/blocks/{block_name}"
        assert expected in content, f"Инклюд {expected} должен присутствовать в composite"

    assert "data-help-jump=" in content, "Навигация [data-help-jump] должна присутствовать"


def test_software_monitor_no_hardcoded_colors():
    """Проверка отсутствия hardcoded HEX/RGB цветов."""
    hex_pattern = re.compile(r'style="[^"]*#[0-9a-fA-F]{3,6}[^"]*"')
    rgb_pattern = re.compile(r'style="[^"]*rgba?\([^)]+\)[^"]*"')

    all_templates = [HELP_DIR / "index.html"] + [BLOCKS_DIR / f for f in SOFTWARE_MONITOR_BLOCKS]

    for template_path in all_templates:
        text = template_path.read_text(encoding="utf-8")
        assert not hex_pattern.search(text), f"Обнаружен HEX цвет в {template_path.name}"
        assert not rgb_pattern.search(text), f"Обнаружен RGB цвет в {template_path.name}"


def test_software_monitor_header_trigger_button():
    """Проверка интеграции кнопки вызова справки в заголовок index.html вкладки."""
    index_html = (WEBGUI_DIR / "tab_software_monitor" / "index.html").read_text(encoding="utf-8")
    assert 'data-help-url="/html/tab_software_monitor/help/index.html"' in index_html


def test_software_monitor_i18n_keys():
    """Проверка ключей softwareMonitorHelp во всех поддерживаемых языках."""
    locales = ["ru", "en", "uk", "he"]
    for lang in locales:
        loc_file = WEBGUI_DIR / "locales" / f"{lang}.json"
        assert loc_file.is_file(), f"Файл локали {lang}.json должен существовать"
        data = json.loads(loc_file.read_text(encoding="utf-8"))

        assert "softwareMonitorHelp" in data, f"Секция softwareMonitorHelp должна быть в {lang}.json"
        sm_help = data["softwareMonitorHelp"]
        assert "composite" in sm_help
        assert "inventory" in sm_help
        assert "packages" in sm_help
        assert "dormant" in sm_help
        assert "startup" in sm_help
        assert "transparency" in sm_help
        assert "heavySockets" in sm_help
