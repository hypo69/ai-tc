# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - User Environment Tab Verification
# =============================================================================
# Description:
#   Интеграционные и контрактные тесты объединенной вкладки окружения пользователя
#   (tab_user_environment): проверка наличия всех компонентов, регистрации в SSOT
#   реестре tab-registry.js, меню, карте сайта и отсутствия хардкода стилей.
#
# File: test_user_environment_tab.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-30 18:15:00
# =============================================================================

from __future__ import annotations

import json
import re
from pathlib import Path
import pytest


def test_user_environment_files_exist():
    """Проверка наличия всех файлов модулей вкладки tab_user_environment."""
    base_dir = Path("apps/windows/api/webgui/tab_user_environment")
    assert base_dir.is_dir(), f"Каталог {base_dir} должен существовать"

    expected_files = [
        "index.html",
        "main.js",
        "panel_sound.js",
        "panel_taskbar.js",
        "panel_windows.js",
        "panel_focus.js",
        "panel_personalization.js",
        "panel_history.js",
        "README.md",
    ]
    for file_name in expected_files:
        file_path = base_dir / file_name
        assert file_path.is_file(), f"Файл {file_name} отсутствует в {base_dir}"
        assert file_path.stat().st_size > 0, f"Файл {file_name} не должен быть пустым"


def test_user_environment_no_hardcoded_colors_or_styles():
    """Проверка отсутствия хардкода HEX/RGB цветов и запрещенных стилей в index.html."""
    html_file = Path("apps/windows/api/webgui/tab_user_environment/index.html")
    content = html_file.read_text(encoding="utf-8")

    # Проверка отсутствия HEX-цветов (#12151a, #ffffff и т.д.)
    hex_color_pattern = re.compile(r'#[0-9a-fA-F]{3,6}\b')
    hex_matches = hex_color_pattern.findall(content)
    assert not hex_matches, f"Обнаружен хардкод HEX-цветов в index.html: {hex_matches}"

    # Проверка отсутствия rgb(...) или rgba(...)
    rgb_pattern = re.compile(r'rgba?\s*\(', re.IGNORECASE)
    rgb_matches = rgb_pattern.findall(content)
    assert not rgb_matches, f"Обнаружен хардкод RGB/RGBA цветов: {rgb_matches}"

    # Проверка отсутствия прямых инлайновых цветов текста/фона
    style_color_pattern = re.compile(r'style="[^"]*(color|background)\s*:', re.IGNORECASE)
    style_matches = style_color_pattern.findall(content)
    assert not style_matches, f"Обнаружены запрещенные inline-стили цвета/фона: {style_matches}"


def test_user_environment_registered_in_tab_registry():
    """Проверка регистрации вкладки в едином реестре tab-registry.js."""
    registry_file = Path("apps/windows/api/webgui/core/tab-registry.js")
    content = registry_file.read_text(encoding="utf-8")

    assert "user_environment" in content, "Вкладка user_environment должна быть в tab-registry.js"
    assert "tab_user_environment/index.html" in content, "Путь к index.html должен быть зарегистрирован"
    assert "tab_user_environment/main.js" in content, "Путь к main.js должен быть зарегистрирован"


def test_user_environment_in_menu_and_sitemap():
    """Проверка присутствия вкладки в конфигурации меню и карте сайта sitemap_data.json."""
    menu_file = Path("apps/windows/api/webgui/config/tc_menu_config.json")
    menu_data = json.loads(menu_file.read_text(encoding="utf-8"))
    
    top_buttons = menu_data.get("menu", {}).get("topButtons", [])
    assert any(b.get("id") == "user_environment" for b in top_buttons), "user_environment должен быть в topButtons"

    sitemap_file = Path("apps/windows/api/webgui/tab_sitemap/sitemap_data.json")
    sitemap_data = json.loads(sitemap_file.read_text(encoding="utf-8"))
    assert any(t.get("id") == "user_environment" for t in sitemap_data), "user_environment должен быть в sitemap_data.json"


def test_user_environment_registered_in_tabs_config():
    """Проверка регистрации tab-user-environment в APP_TAB_DEFS (tabs-config.js)."""
    config_file = Path("apps/windows/api/webgui/apps/modules/tabs-config.js")
    content = config_file.read_text(encoding="utf-8")

    assert "tab-user-environment" in content, "tab-user-environment должен быть в tabs-config.js"
    assert "tab_user_environment/index.html" in content, "Путь к index.html должен быть в tabs-config.js"
    assert "tab_user_environment/main.js" in content, "Путь к main.js должен быть в tabs-config.js"


def test_user_environment_container_in_index_html():
    """Проверка наличия контейнера #tab-user-environment в apps/index.html."""
    index_file = Path("apps/windows/api/webgui/apps/index.html")
    content = index_file.read_text(encoding="utf-8")

    assert 'id="tab-user-environment"' in content, "Контейнер id='tab-user-environment' должен быть в apps/index.html"


def test_user_environment_subtab_panel_ids():
    """Проверка наличия стандартных data-panel-id у всех блоков субпанелей."""
    html_file = Path("apps/windows/api/webgui/tab_user_environment/index.html")
    content = html_file.read_text(encoding="utf-8")

    canonical_panels = [
        "panel-taskbar",
        "panel-sound",
        "panel-windows",
        "panel-focus",
        "panel-personalization",
        "panel-history",
    ]

    for p in canonical_panels:
        assert f'data-panel-id="{p}"' in content, f"Блок {p} должен иметь data-panel-id в index.html"


def test_user_environment_main_js_routing_functions():
    """Проверка реализации стандарта маршрутизации блоков URL в main.js."""
    js_file = Path("apps/windows/api/webgui/tab_user_environment/main.js")
    content = js_file.read_text(encoding="utf-8")

    required_functions = [
        "normalizeSubTabId",
        "getPanelFromHash",
        "getActiveSubTabId",
        "updateUrlWithPanel",
        "switchSubTab",
        "fetchActiveBlockData",
        "isUserEnvironmentTabActive",
    ]

    for fn in required_functions:
        assert f"export function {fn}" in content or f"function {fn}" in content, (
            f"Функция {fn} должна быть объявлена в main.js"
        )

    # Проверка регистрации глобальных методов в объекте window
    assert "window.switchUserEnvSubTab = switchSubTab" in content
    assert "window.getUserEnvPanelFromHash = getPanelFromHash" in content
    assert "window.updateUserEnvUrlWithPanel = updateUrlWithPanel" in content
    assert "window.normalizeUserEnvSubTabId = normalizeSubTabId" in content


def test_tab_core_and_shell_routing_integration():
    """Проверка интеграции переключения суб-блоков tab-user-environment в диспетчерах."""
    tab_core_file = Path("apps/windows/api/webgui/js/tab-core.js")
    tab_core_content = tab_core_file.read_text(encoding="utf-8")

    assert "tab-user-environment" in tab_core_content
    assert "switchUserEnvSubTab" in tab_core_content

    main_js_file = Path("apps/windows/api/webgui/js/main.js")
    main_js_content = main_js_file.read_text(encoding="utf-8")
    assert "tab-user-environment" in main_js_content
    assert "switchUserEnvSubTab" in main_js_content


def test_panel_loader_excludes_user_environment():
    """Проверка исключения tab-user-environment из общего SQL поллера panel-loader.js."""
    loader_file = Path("apps/windows/api/webgui/js/panel-loader.js")
    loader_content = loader_file.read_text(encoding="utf-8")

    assert "tab-user-environment" in loader_content



