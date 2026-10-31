"""
=============================================================================
Process Name: Test Windows Log Settings - Atomic & Composite Help Subsystem
=============================================================================
Description:
  Набор юнит-тестов для проверки корректности подсистемы контекстной справки:
  1. Существование композитной страницы и всех 6 атомарных блоков.
  2. Валидация отсутствия жестко закодированных HEX/RGB цветов (GEMINI.md).
  3. Проверка директив [data-help-include] в композитном шаблоне index.html.
  4. Проверка полноты ключей локализации logSettingsHelp во всех языковых файлах (ru, en, uk, he).
  5. Проверка включения help-modal.js в index.html и apps/index.html.

File: test_log_settings_help_modal.py
Project: ai-windows-admin
Package: tests
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-10-31 17:49:30
=============================================================================
"""

import os
import re
import json
import pytest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
WEBGUI_DIR = BASE_DIR / "apps" / "windows" / "api" / "webgui"
HELP_DIR = WEBGUI_DIR / "tab_log_settings" / "help"
BLOCKS_DIR = HELP_DIR / "blocks"

ATOMIC_BLOCK_FILES = [
    "block_kpi_cards.html",
    "block_domains_catalog.html",
    "block_channels_config.html",
    "block_security_telemetry.html",
    "block_provenance_lifecycle.html",
    "block_event_inspector.html",
]


def test_help_files_exist():
    """Проверка наличия всех атомарных блоков и композитного файла index.html."""
    assert HELP_DIR.exists(), f"Директория {HELP_DIR} должна существовать"
    assert (HELP_DIR / "index.html").is_file(), "Композитный index.html должен существовать"
    assert (HELP_DIR / "README.md").is_file(), "README.md документации должен существовать"

    for block_name in ATOMIC_BLOCK_FILES:
        block_path = BLOCKS_DIR / block_name
        assert block_path.is_file(), f"Атомарный блок {block_name} должен существовать"
        content = block_path.read_text(encoding="utf-8")
        assert len(content.strip()) > 50, f"Блок {block_name} не должен быть пустым"
        assert "data-help-block" in content, f"Блок {block_name} должен содержать data-help-block"


def test_composite_includes_all_blocks():
    """Проверка того, что композитный index.html ссылается на все 6 атомарных блоков."""
    composite_path = HELP_DIR / "index.html"
    content = composite_path.read_text(encoding="utf-8")

    for block_name in ATOMIC_BLOCK_FILES:
        expected_include = f"/html/tab_log_settings/help/blocks/{block_name}"
        assert expected_include in content, f"Инклюд {expected_include} должен присутствовать в help/index.html"

    # Проверка навигационных прыжков
    assert "data-help-jump=" in content, "В композитном файле должна быть навигация [data-help-jump]"


def test_no_hardcoded_colors_in_help_templates():
    """Проверка стандарта тем: запрет прямого указания HEX (#...) и RGB в стилях."""
    hex_color_pattern = re.compile(r'style="[^"]*#[0-9a-fA-F]{3,6}[^"]*"')
    rgb_color_pattern = re.compile(r'style="[^"]*rgba?\([^)]+\)[^"]*"')

    all_templates = [HELP_DIR / "index.html"] + [BLOCKS_DIR / f for f in ATOMIC_BLOCK_FILES]

    for template_path in all_templates:
        text = template_path.read_text(encoding="utf-8")
        assert not hex_color_pattern.search(text), f"Обнаружен жестко заданный HEX цвет в {template_path.name}"
        assert not rgb_color_pattern.search(text), f"Обнаружен жестко заданный RGB цвет в {template_path.name}"


def test_help_modal_controller_script_registered():
    """Проверка интеграции help-modal.js в главные оболочки index.html и apps/index.html."""
    controller_file = WEBGUI_DIR / "js" / "help-modal.js"
    assert controller_file.is_file(), "Файл help-modal.js должен существовать"

    controller_code = controller_file.read_text(encoding="utf-8")
    assert "class HelpModalController" in controller_code
    assert "window.HelpModal" in controller_code
    assert "resolveIncludes" in controller_code

    index_html = (WEBGUI_DIR / "index.html").read_text(encoding="utf-8")
    apps_index_html = (WEBGUI_DIR / "apps" / "index.html").read_text(encoding="utf-8")

    assert "help-modal.js" in index_html, "help-modal.js должен быть подключен в index.html"
    assert "help-modal.js" in apps_index_html, "help-modal.js должен быть подключен в apps/index.html"


def test_i18n_keys_present_in_all_locales():
    """Проверка наличия секции logSettingsHelp во всех поддерживаемых локалях."""
    locales = ["ru", "en", "uk", "he"]
    for lang in locales:
        loc_file = WEBGUI_DIR / "locales" / f"{lang}.json"
        assert loc_file.is_file(), f"Файл локали {lang}.json должен существовать"
        data = json.loads(loc_file.read_text(encoding="utf-8"))

        assert "logSettingsHelp" in data, f"Секция logSettingsHelp должна присутствовать в {lang}.json"
        help_section = data["logSettingsHelp"]
        assert "composite" in help_section
        assert "kpiCards" in help_section
        assert "domains" in help_section
        assert "channels" in help_section
        assert "security" in help_section
        assert "provLifecycle" in help_section
        assert "inspector" in help_section
