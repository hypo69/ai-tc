"""
=============================================================================
Process Name: Test Processes Load Inspector Subtabs and Routing
=============================================================================
Description:
    Модульные тесты для проверки изоляции опроса активной суб-панели вкладки
    tab-processes-load-inspector, поддержки составного URL вида:
    http://localhost:8001/tc#tab-processes-load-inspector#<panel_id>,
    корректного обновления URL hash и остановки фонового опроса неактивных панелей.

File: test_processes_load_inspector_subtabs.py
Project: ai-windows-admin
Package: tests
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-10-16 23:45:00
=============================================================================
"""

from pathlib import Path
from starlette.testclient import TestClient
import pytest


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_WEBGUI_DIR = _PROJECT_ROOT / "apps" / "windows" / "api" / "webgui"


def test_processes_load_inspector_active_panel_polling_logic() -> None:
    """Проверяет изоляцию сетевых опросов в main.js вкладки processes load inspector."""
    js_file = _WEBGUI_DIR / "tab_processes_load_inspector" / "main.js"
    assert js_file.exists(), f"Файл {js_file} не найден"
    content = js_file.read_text(encoding="utf-8")

    # 1. Проверяем наличие ключевых функций управления субпанелями
    assert "function getActiveSubTabId()" in content, "Функция getActiveSubTabId() не найдена"
    assert "function normalizeSubTabId(" in content, "Функция normalizeSubTabId() не найдена"
    assert "function getPanelFromHash()" in content, "Функция getPanelFromHash() не найдена"
    assert "function updateUrlWithPanel(" in content, "Функция updateUrlWithPanel() не найдена"
    assert "function fetchActiveSubTabOnly(" in content, "Функция fetchActiveSubTabOnly() не найдена"

    # 2. Проверяем, что каждая функция опроса опрашивает API ТОЛЬКО при активности своей суб-панели
    assert "getActiveSubTabId() !== 'manager'" in content, "fetchProcessManagerSummary не содержит проверку активной субпанели manager"
    assert "getActiveSubTabId() !== 'top'" in content, "fetchHostProcesses не содержит проверку активной субпанели top"
    assert "getActiveSubTabId() !== 'net'" in content, "fetchNetworkActivity не содержит проверку активной субпанели net"
    assert "getActiveSubTabId() !== 'files'" in content, "fetchLiveFileEvents не содержит проверку активной субпанели files"
    assert "getActiveSubTabId() !== 'leaks'" in content, "fetchProcessLeaks не содержит проверку активной субпанели leaks"

    # 3. Проверяем, что activateTab загружает только активную субпанель, а не все сразу
    assert "await fetchActiveSubTabOnly(true);" in content, "activateTab не вызывает fetchActiveSubTabOnly"
    # Проверяем, что массив calls со всеми панелями был удален из activateTab
    assert "calls = [" not in content, "Старый массив массовых параллельных вызовов calls остался в main.js"

    # 4. Проверяем экспорт функций управления в глобальный контекст
    assert "window.getActiveProcessesSubTabId = getActiveSubTabId;" in content
    assert "window.fetchActiveProcessesSubTab = fetchActiveSubTabOnly;" in content
    assert "window.switchProcessesSubTab = switchProcessesSubTab;" in content


def test_tab_core_and_apps_main_subpanel_routing() -> None:
    """Проверяет маршрутизацию составного хэша вида #tab#panel в tab-core.js и apps/main.js."""
    tab_core_file = _WEBGUI_DIR / "js" / "tab-core.js"
    assert tab_core_file.exists()
    tab_core_code = tab_core_file.read_text(encoding="utf-8")

    # tab-core.js нормализует tabId отсекая субпанель при поиске контейнера
    assert "split('#')[0]" in tab_core_code, "normalizeTabId не отсекает субпанель от tabId"
    # tab-core.js сохраняет субпанель в URL hash
    assert "targetHash = subPanelId ? `#${id}#${subPanelId}` : `#${id}`" in tab_core_code
    # tab-core.js передает subPanelId в switchProcessesSubTab
    assert "window.switchProcessesSubTab(subPanelId, false)" in tab_core_code

    apps_main_file = _WEBGUI_DIR / "apps" / "main.js"
    assert apps_main_file.exists()
    apps_main_code = apps_main_file.read_text(encoding="utf-8")

    # apps/main.js поддерживает субпанели при switchAppTab
    assert "subPanel ? `${normId}#${subPanel}` : normId" in apps_main_code
    assert "window.switchProcessesSubTab(subPanel, false)" in apps_main_code
    # apps/main.js слушает событие hashchange
    assert "window.addEventListener('hashchange'" in apps_main_code


def test_panel_loader_excludes_processes_inspector() -> None:
    """Проверяет, что universal panel-loader не делает паразитных запросов для processes inspector."""
    panel_loader_file = _WEBGUI_DIR / "js" / "panel-loader.js"
    assert panel_loader_file.exists()
    code = panel_loader_file.read_text(encoding="utf-8")

    assert "tab-processes-load-inspector" in code, "panel-loader не исключает вкладку tab-processes-load-inspector"
    assert "!tabPane.classList.contains('active')" in code, "panel-loader не проверяет активность родительской вкладки"


def test_tc_ps1_supports_panel_parameter() -> None:
    """Проверяет наличие параметра Panel и корректность сборки URL в сценарии tc.ps1."""
    tc_file = _PROJECT_ROOT / "tc.ps1"
    assert tc_file.exists(), f"Сценарий {tc_file} не найден"
    tc_code = tc_file.read_text(encoding="utf-8")

    # Проверяем параметр Panel
    assert "[Alias('PanelId', 'SubTab', 'SubPanel')]" in tc_code, "Алиасы PanelId, SubTab, SubPanel отсутствуют в tc.ps1"
    assert "[string]$Panel" in tc_code, "Параметр $Panel отсутствует в tc.ps1"

    # Проверяем сборку составного URL с панелью
    assert "cleanPanel = $Panel.Trim().Trim('#')" in tc_code
    assert "${t_}#${cleanPanel}" in tc_code


def test_process_manager_tab_consolidation_into_processes_inspector() -> None:
    """Проверяет перенос вкладки tab-process-manager в tab-processes-load-inspector как панель."""
    import json

    # 1. Проверяем редирект в apps/main.js
    apps_main = (_WEBGUI_DIR / "apps" / "main.js").read_text(encoding="utf-8")
    assert "tabId === 'tab-process-manager' || tabId === 'process-manager'" in apps_main
    assert "window.switchProcessesSubTab('manager')" in apps_main

    # 2. Проверяем редирект в js/main.js
    js_main = (_WEBGUI_DIR / "js" / "main.js").read_text(encoding="utf-8")
    assert "tabId === 'tab-process-manager' || tabId === 'process-manager'" in js_main

    # 3. Проверяем авто-маппинг в tc.ps1
    tc_ps1 = (_PROJECT_ROOT / "tc.ps1").read_text(encoding="utf-8")
    assert '$t_ -eq "tab-process-manager"' in tc_ps1
    assert '$t_ = "tab-processes-load-inspector"' in tc_ps1

    # 4. Проверяем конфигурацию меню config_menues/tc_menu_config.json
    menu_path = _WEBGUI_DIR / "config_menues" / "tc_menu_config.json"
    assert menu_path.exists()
    menu_data = json.loads(menu_path.read_text(encoding="utf-8"))
    sidebar_items = menu_data.get("menu", {}).get("sidebarItems", [])
    pm_item = next((item for item in sidebar_items if item.get("id") == "process_manager"), None)
    assert pm_item is not None, "Элемент process_manager отсутствует в меню"
    assert pm_item.get("visible") is False, "Элемент process_manager должен быть скрыт из меню как отдельная вкладка"
    assert pm_item.get("tab") == "tab-processes-load-inspector#manager", "Целевая вкладка process_manager должна указывать на панель manager"

