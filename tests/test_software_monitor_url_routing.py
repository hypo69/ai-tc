"""
=============================================================================
Process Name: Test Windows WebGUI - URL Routing & Blocks Deep-Linking Across Tabs
=============================================================================
Description:
  Комплексные юнит-тесты валидации двухуровневой маршрутизации в URL:
  #tab-<tabId>#panel-<panelId>#block-<blockId>
  1. Software Monitor: кнопки sw-packages-subtabs (data-block-id и data-panel-id),
     хэш #tab-software-monitor#panel-packages#block-ninite.
  2. System Control: #tab-system-control#panel-forensics#block-userassist и timeline.
  3. App Internals: #tab-app-internals#panel-wikillm-system#block-sys-storage.
  4. Storage Management: #tab-storage-management#panel-volumes и panel-wear.
  5. AI Ecosystem: #tab-ai-ecosystem#panel-agents, panel-skills, panel-mcp.
  6. Tab Core: универсальная функция setPanelHash с поддержкой panel и blockId.
  7. Стандарты и навыки: отражение регламента в webgui-developer/SKILL.md и WEBGUI.md.

File: test_software_monitor_url_routing.py
Project: ai-windows-admin
Package: tests
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-11-12 02:30:00
=============================================================================
"""

import re
from pathlib import Path
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
WEBGUI_DIR = BASE_DIR / "apps" / "windows" / "api" / "webgui"
SKILLS_DIR = BASE_DIR / ".agents" / "skills"
STANDARDS_DIR = BASE_DIR / ".ai" / "instructions" / "standards"


def test_packages_subtabs_attributes():
    """Проверка наличия data-block-id и data-panel-id у кнопок менеджера пакетов."""
    index_html = WEBGUI_DIR / "tab_software_monitor" / "index.html"
    assert index_html.is_file(), "index.html должен существовать"
    content = index_html.read_text(encoding="utf-8")

    assert 'id="sw-subtab-winget-btn"' in content
    assert 'data-block-id="block-winget"' in content
    assert 'id="sw-subtab-msi-btn"' in content
    assert 'data-block-id="block-msi"' in content
    assert 'id="sw-subtab-store-btn"' in content
    assert 'data-block-id="block-store"' in content
    assert 'id="sw-subtab-ninite-btn"' in content
    assert 'data-block-id="block-ninite"' in content

    # Проверка разметки контейнеров tab-pane
    assert 'id="sw-subpane-ninite"' in content
    assert 'data-block-id="block-ninite"' in content


def test_panel_subtabs_routing_functions():
    """Проверка реализации методов маршрутизации блоков в panel_subtabs/panel.js."""
    panel_js = WEBGUI_DIR / "tab_software_monitor" / "panel_subtabs" / "panel.js"
    assert panel_js.is_file(), "panel_subtabs/panel.js должен существовать"
    content = panel_js.read_text(encoding="utf-8")

    assert "export function normalizeBlockId" in content
    assert "export function getBlockFromHash" in content
    assert "export function switchSoftwareBlock" in content
    assert "export function updateUrlWithPanel" in content
    assert "export function switchSoftwareSubTab" in content

    # Проверка формата формирования хэша: #panel-${canonical}${blockSuffix}
    assert "#panel-${canonical}${blockSuffix}" in content
    assert "block-ninite" in content
    assert "window.switchSoftwareBlock" in content
    assert "window.getSoftwareBlockFromHash" in content


def test_main_orchestrator_integration():
    """Проверка интеграции маршрутизации блоков в tab_software_monitor/main.js."""
    main_js = WEBGUI_DIR / "tab_software_monitor" / "main.js"
    assert main_js.is_file(), "main.js должен существовать"
    content = main_js.read_text(encoding="utf-8")

    assert "getBlockFromHash" in content
    assert "switchSoftwareBlock" in content
    assert "window.switchSoftwareBlock = switchSoftwareBlock;" in content
    assert "switchSoftwareSubTab(targetPanel, targetBlock, false);" in content


def test_apps_main_and_js_main_delegation():
    """Проверка передачи blockId в switchSoftwareSubTab из глобальных маршрутизаторов."""
    apps_main = WEBGUI_DIR / "apps" / "main.js"
    assert apps_main.is_file(), "apps/main.js должен существовать"
    apps_content = apps_main.read_text(encoding="utf-8")

    assert "window.switchSoftwareSubTab(subPanel, blockId, false);" in apps_content
    assert "window.switchSoftwareSubTab('packages', 'block-ninite');" in apps_content

    js_main = WEBGUI_DIR / "js" / "main.js"
    assert js_main.is_file(), "js/main.js должен существовать"
    js_content = js_main.read_text(encoding="utf-8")

    assert "window.switchSoftwareSubTab(subPanel, blockId, false);" in js_content


def test_other_tabs_panel_and_block_routing():
    """Проверка поддержки формата #panel- и #block- в других вкладках WebGUI."""
    # 1. System Control
    sys_control_main = WEBGUI_DIR / "tab_system_control" / "main.js"
    assert sys_control_main.is_file()
    sys_content = sys_control_main.read_text(encoding="utf-8")
    assert "#panel-${canonical}${blockSuffix}" in sys_content
    assert "#block-" in sys_content

    # 2. App Internals
    app_internals_utils = WEBGUI_DIR / "tab_app_internals" / "common" / "ui_utils.js"
    assert app_internals_utils.is_file()
    internals_content = app_internals_utils.read_text(encoding="utf-8")
    assert "#panel-${canonical}${blockSuffix}" in internals_content

    # 3. Storage Management
    storage_main = WEBGUI_DIR / "tab_storage_management" / "main.js"
    assert storage_main.is_file()
    storage_content = storage_main.read_text(encoding="utf-8")
    assert "#panel-${canonical}" in storage_content

    # 4. AI Ecosystem
    ai_main = WEBGUI_DIR / "tab_ai_ecosystem" / "main.js"
    assert ai_main.is_file()
    ai_content = ai_main.read_text(encoding="utf-8")
    assert "#panel-${canonical}" in ai_content

    # 5. Tab Core setPanelHash
    tab_core_js = WEBGUI_DIR / "js" / "tab-core.js"
    assert tab_core_js.is_file()
    core_content = tab_core_js.read_text(encoding="utf-8")
    assert "export function setPanelHash(tabId, panelId, blockId = null)" in core_content
    assert "#${normTab}#${normPanel}${blockSuffix}" in core_content


def test_skills_and_standards_documentation():
    """Проверка фиксации стандартов в навыках и руководствах разработки."""
    skill_doc = SKILLS_DIR / "webgui-developer" / "SKILL.md"
    assert skill_doc.is_file()
    skill_content = skill_doc.read_text(encoding="utf-8")
    assert "#tab-<tabId>#panel-<panelId>#block-<blockId>" in skill_content
    assert "data-block-id" in skill_content

    webgui_std = STANDARDS_DIR / "WEBGUI.md"
    assert webgui_std.is_file()
    std_content = webgui_std.read_text(encoding="utf-8")
    assert "#tab-<tabId>#panel-<panelId>#block-<blockId>" in std_content
