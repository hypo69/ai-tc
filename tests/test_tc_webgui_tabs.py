# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - TC WebGUI Tabs Registration
# =============================================================================
# Description:
#   Интеграционные тесты регистрации и доступности консолидированных вкладок
#   интерфейса Test Computer (/tc), включая «Внутренняя кухня» (tab-app-internals),
#   «Экосистема ИИ» (tab-ai-ecosystem), «Накопители» (tab-storage-management) и
#   «Мониторинг ПО» (tab-software-monitor).
#
# File: test_tc_webgui_tabs.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-20 15:25:00
# =============================================================================

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from apps.windows.api.server import create_app


@pytest.fixture(scope="module")
def api_client() -> TestClient:
    """Фикстура тестового клиента FastAPI приложения TC.

    Returns:
        TestClient: Инициализированный клиент для выполнения HTTP запросов.
    """
    app = create_app()
    return TestClient(app)


def test_tc_index_contains_consolidated_tab_panes(api_client: TestClient) -> None:
    """Проверяет наличие контейнеров консолидированных вкладок в главной странице /tc."""
    res = api_client.get("/tc")
    assert res.status_code == 200
    html = res.text
    assert 'id="tab-app-internals"' in html, "Контейнер tab-app-internals отсутствует в /tc"
    assert 'id="tab-ai-ecosystem"' in html, "Контейнер tab-ai-ecosystem отсутствует в /tc"
    assert 'id="tab-storage-management"' in html, "Контейнер tab-storage-management отсутствует в /tc"
    assert 'id="tab-software-monitor"' in html, "Контейнер tab-software-monitor отсутствует в /tc"


def test_tc_tabs_config_contains_app_internals(api_client: TestClient) -> None:
    """Проверяет регистрацию вкладки app_internals и software_monitor в модуле конфигурации tabs-config.js."""
    res = api_client.get("/html/apps/modules/tabs-config.js")
    assert res.status_code == 200
    js = res.text
    assert "tab-app-internals" in js, "Вкладка tab-app-internals не найдена в tabs-config.js"
    assert "tab-ai-ecosystem" in js, "Вкладка tab-ai-ecosystem не найдена в tabs-config.js"
    assert "tab-storage-management" in js, "Вкладка tab-storage-management не найдена в tabs-config.js"
    assert "tab-software-monitor" in js, "Вкладка tab-software-monitor не найдена в tabs-config.js"


def test_app_internals_assets_served(api_client: TestClient) -> None:
    """Проверяет доступность статических файлов панели Внутренняя кухня."""
    res_html = api_client.get("/html/tab_app_internals/index.html")
    assert res_html.status_code == 200
    assert "app-internals-container" in res_html.text
    assert "internals-telemetry-embed-container" in res_html.text
    assert "internals-models-embed-container" in res_html.text
    assert "internals-logs-embed-container" in res_html.text
    assert "internals-etw-embed-container" in res_html.text
    assert "internals-settings-embed-container" in res_html.text
    assert 'data-panel-id="telemetry"' in res_html.text
    assert 'data-panel-id="models"' in res_html.text
    assert 'data-panel-id="logs"' in res_html.text
    assert 'data-panel-id="etw"' in res_html.text
    assert 'data-panel-id="settings"' in res_html.text
    assert 'data-panel-id="wikillm-db"' in res_html.text
    assert 'data-panel-id="instruments"' in res_html.text
    assert 'data-panel-id="wikillm-params"' in res_html.text
    assert 'data-panel-id="wikillm-editor"' in res_html.text

    res_js = api_client.get("/html/tab_app_internals/main.js")
    assert res_js.status_code == 200
    assert "initAppInternalsTab" in res_js.text
    assert "switchAppInternalsSubTab" in res_js.text
    assert "getAppInternalsPanelFromHash" in res_js.text
    assert "updateAppInternalsUrlWithPanel" in res_js.text



def test_software_hub_assets_served(api_client: TestClient) -> None:
    """Проверяет доступность консолидированного шаблона и скрипта вкладки Мониторинг ПО."""
    res_html = api_client.get("/html/tab_software_monitor/index.html")
    assert res_html.status_code == 200
    assert "software-monitor-container" in res_html.text
    assert "sw-inventory-embed-container" in res_html.text
    assert "sw-packages-embed-container" in res_html.text
    assert "subpane-sw-dormant" in res_html.text
    assert "subtab-sw-startup-btn" in res_html.text
    assert "subpane-sw-startup" in res_html.text
    assert "sw-startup-embed-container" in res_html.text
    assert "sw-transparency-embed-container" in res_html.text
    assert "sw-ninite-embed-container" in res_html.text
    assert "sw-store-embed-container" in res_html.text
    assert "sw-subtab-winget-btn" in res_html.text
    assert "sw-subtab-msi-btn" in res_html.text
    assert "sw-msi-embed-container" in res_html.text

    res_js = api_client.get("/html/tab_software_monitor/main.js")
    assert res_js.status_code == 200
    assert "initSoftwareMonitorTab" in res_js.text
    assert "switchSoftwareSubTab" in res_js.text

    res_subtabs = api_client.get("/html/tab_software_monitor/panel_subtabs/panel.js")
    assert res_subtabs.status_code == 200
    assert "sw-startup-embed-container" in res_subtabs.text
    assert "initStorePackagesPanel" in res_subtabs.text
    assert "initWingetPackagesPanel" in res_subtabs.text
    assert "initMsiPackagesPanel" in res_subtabs.text

    res_winget = api_client.get("/html/tab_software_monitor/panel_winget/panel.js")
    assert res_winget.status_code == 200
    assert "initWingetPackagesPanel" in res_winget.text

    res_msi = api_client.get("/html/tab_software_monitor/panel_msi/panel.js")
    assert res_msi.status_code == 200
    assert "initMsiPackagesPanel" in res_msi.text


def test_startup_auditor_panel_integration(api_client: TestClient) -> None:
    """Проверяет интеграцию панели Автозапуск программ в Мониторинг ПО и правила маршрутизации."""
    # 1. Доступность статики tab_startup_auditor
    html_res = api_client.get("/html/tab_startup_auditor/index.html")
    assert html_res.status_code == 200
    assert "startup-auditor-container" in html_res.text

    js_res = api_client.get("/html/tab_startup_auditor/main.js")
    assert js_res.status_code == 200
    assert "initStartupAuditorTab" in js_res.text

    # 2. Редирект в apps/main.js
    apps_main = api_client.get("/apps/static/main.js")
    assert apps_main.status_code == 200
    assert "tab-startup-auditor" in apps_main.text
    assert "switchSoftwareSubTab('startup')" in apps_main.text

    # 3. Редирект в js/main.js
    js_main = api_client.get("/html/js/main.js")
    assert js_main.status_code == 200
    assert "tab-startup-auditor" in js_main.text
    assert "switchSoftwareSubTab('startup')" in js_main.text

    # 4. Сопоставление в tab-core.js
    tab_core = api_client.get("/html/js/tab-core.js")
    assert tab_core.status_code == 200
    assert "'tab-startup-auditor': 'tab-software-monitor'" in tab_core.text


def test_tc_menu_config_contains_installed_software(api_client: TestClient) -> None:
    """Проверяет наличие кнопки Мониторинг ПО в верхнем меню конфигурации tc_menu_config.json."""
    res = api_client.get("/api/v1/menu/config?target=tc")
    assert res.status_code == 200
    data = res.json()
    top_buttons = data.get("menu", {}).get("topButtons", [])
    sw_btn = next((b for b in top_buttons if b.get("id") in ("software_monitor", "software_scanner")), None)
    assert sw_btn is not None, "Элемент software_monitor отсутствует в topButtons"
    assert sw_btn.get("tab") in ("tab-software-monitor", "tab-software-scanner")
    assert sw_btn.get("label") in ("Мониторинг ПО", "Установленные программы")
    assert sw_btn.get("visible") is True


def test_telemetry_config_api_available(api_client: TestClient) -> None:
    """Проверяет работоспособность эндпоинта конфигурации телеметрии для суб-панели Телеметрия."""
    res = api_client.get("/api/windows/telemetry/config")
    assert res.status_code == 200
    data = res.json()
    assert data.get("success") is True
    assert "config" in data


def test_about_system_bundle_api(api_client: TestClient) -> None:
    """Проверяет полный агрегированный срез конфигурации компьютера (/api/v1/about-system/bundle)."""
    res = api_client.get("/api/v1/about-system/bundle")
    assert res.status_code == 200
    data = res.json()
    assert data.get("status") == "ok"
    assert "summary" in data
    assert "hardware" in data
    assert "storage_battery" in data
    assert "backup" in data
    assert "control_status" in data
    assert "kpi" in data


def test_tc_ps1_target_url_about_system() -> None:
    """Проверяет, что стартовый URL в сценарии tc.ps1 всегда открывает #tab-about-system."""
    from pathlib import Path
    tc_ps1 = Path("tc.ps1")
    assert tc_ps1.exists()
    content = tc_ps1.read_text(encoding="utf-8")
    assert "#tab-about-system" in content
    assert "#tab-system-control" not in content


def test_panel_loader_and_apps_main_skip_about_system(api_client: TestClient) -> None:
    """Проверяет, что панели tab-about-system исключены из индивидуального опроса panel-loader."""
    res_loader = api_client.get("/html/js/panel-loader.js")
    assert res_loader.status_code == 200
    assert "tab-about-system" in res_loader.text

    res_main = api_client.get("/html/apps/main.js")
    assert res_main.status_code == 200
    assert "switchAppTab('tab-about-system')" in res_main.text


def test_hardware_tree_full_telemetry_properties(api_client: TestClient) -> None:
    """Проверяет сбор исчерпывающих параметров оборудования (CPUID, Stepping, Motherboard, Disks)."""
    res = api_client.get("/api/v1/about-system/bundle")
    assert res.status_code == 200
    data = res.json()
    hw_nodes = data.get("hardware", [])
    assert len(hw_nodes) > 0, "Hardware tree не должен быть пустым"

    # Проверка параметров процессора
    cpu_node = next((n for n in hw_nodes if n.get("category") == "Processor (CPU)"), None)
    assert cpu_node is not None, "Узел Processor (CPU) отсутствует в hardware tree"
    cpu_props = cpu_node.get("properties", {})
    assert "Идентификатор CPUID" in cpu_props, "Параметр 'Идентификатор CPUID' отсутствует в свойствах CPU"
    assert "Кодовый идентификатор (ProcessorId)" in cpu_props or "Базовая частота" in cpu_props

    # Проверка параметров физических дисков
    disk_nodes = [n for n in hw_nodes if n.get("category") == "Physical Disk"]
    assert len(disk_nodes) > 0, "Узлы Physical Disk отсутствуют в hardware tree"
    for d in disk_nodes:
        props = d.get("properties", {})
        assert "Тип накопителя" in props
        assert "Интерфейс / Шина подключения" in props
        assert "Стиль разметки разделов" in props


def test_hardware_enrichment_status_and_components_db(api_client: TestClient) -> None:
    """Проверяет эндпоинт статуса обогащения компонентов и наличие ключей в таблице hardware_components."""
    res = api_client.get("/api/v1/about-system/hardware-enrichment-status")
    assert res.status_code == 200
    data = res.json()
    assert "components" in data
    assert "pending_count" in data
    assert "total_count" in data
    assert isinstance(data["components"], dict)

    # Проверяем, что в bundle узлы содержат поля обогащения и жизненного цикла
    bundle_res = api_client.get("/api/v1/about-system/bundle")
    assert bundle_res.status_code == 200
    hw_nodes = bundle_res.json().get("hardware", [])
    assert len(hw_nodes) > 0
    sample_node = hw_nodes[0]
    assert "component_key" in sample_node
    assert "vendor_url" in sample_node
    assert "is_present" in sample_node
    assert "install_count" in sample_node


def test_hardware_component_lifecycle_and_history_api(api_client: TestClient) -> None:
    """Проверяет эндпоинт истории жизненного цикла аппаратного компонента (/hardware-component-history)."""
    # 1. Получаем зарегистрированный компонент
    stat_res = api_client.get("/api/v1/about-system/hardware-enrichment-status")
    assert stat_res.status_code == 200
    comps = stat_res.json().get("components", {})
    assert len(comps) > 0, "В таблице hardware_components должны быть записи"
    sample_key = next(iter(comps.keys()))

    # Гарантируем наличие тестового события в истории для проверки эндпоинта
    from apps.windows.telemetry.sqlite import TelemetryStorage
    storage = TelemetryStorage.get_instance()
    storage.record_hardware_component_event(
        component_key=sample_key,
        event_type="installed",
        details={"status": "initial_test_setup"},
    )

    # 2. Запрашиваем историю компонента
    hist_res = api_client.get(f"/api/v1/about-system/hardware-component-history?component_key={sample_key}")
    assert hist_res.status_code == 200
    hist_data = hist_res.json()
    assert hist_data.get("component_key") == sample_key
    assert "component" in hist_data
    assert "history" in hist_data
    assert isinstance(hist_data["history"], list)
    assert len(hist_data["history"]) >= 1, "Должно быть минимум одно событие (installed/reinstalled)"
    first_ev = hist_data["history"][0]
    ev_type = (first_ev.get("change_type") or first_ev.get("event_type") or "").lower()
    assert ev_type in ("installed", "reinstalled", "removed")
    assert "timestamp" in first_ev


def test_theme_editor_assets_and_navigation(api_client: TestClient) -> None:
    """Проверяет регистрацию вкладки theme_editor, доступность HTML/JS ассетов и кнопку в userSettingsModal."""
    # 1. Проверяем главную страницу /tc на наличие контейнера и кнопки в userSettingsModal
    tc_res = api_client.get("/tc")
    assert tc_res.status_code == 200
    html = tc_res.text
    assert 'id="tab-theme-editor"' in html, "Контейнер tab-theme-editor отсутствует в /tc"
    assert 'id="userSettingsModal"' in html, "Модальное окно userSettingsModal отсутствует в /tc"
    assert 'data-tab="tab-theme-editor"' in html, "Кнопка навигации data-tab='tab-theme-editor' отсутствует в /tc"

    # 2. Проверяем регистрацию в tabs-config.js
    cfg_res = api_client.get("/html/apps/modules/tabs-config.js")
    assert cfg_res.status_code == 200
    assert "tab-theme-editor" in cfg_res.text, "theme-editor не найден в tabs-config.js"

    # 3. Проверяем отдачу статических файлов вкладки Редактора тем
    html_res = api_client.get("/html/tab_theme_editor/index.html")
    assert html_res.status_code == 200
    assert "Редактор тем" in html_res.text
    assert 'id="theme-preset-select"' in html_res.text, "Селектор id='theme-preset-select' отсутствует в index.html"
    assert "<script" not in html_res.text, "В index.html вкладки не должно быть тегов <script>"

    js_res = api_client.get("/html/tab_theme_editor/main.js")
    assert js_res.status_code == 200
    assert "initThemeEditorTab" in js_res.text
    assert "activateThemeEditorTab" in js_res.text
    assert "deactivateThemeEditorTab" in js_res.text
    assert "restoreUserTheme" in js_res.text

    # 4. Проверяем поддержку временного предпросмотра и восстановления темы в theme-engine.js и theme.js
    engine_res = api_client.get("/html/js/theme-engine.js")
    assert engine_res.status_code == 200
    assert "previewTheme" in engine_res.text
    assert "restoreUserTheme" in engine_res.text

    theme_res = api_client.get("/html/js/theme.js")
    assert theme_res.status_code == 200
    assert "previewTheme" in theme_res.text
    assert "restoreUserTheme" in theme_res.text


def test_sitemap_tab_and_metadata_registration(api_client: TestClient) -> None:
    """Проверяет регистрацию вкладки sitemap, отдачу статики, sitemap_data.json и пункт меню."""
    # 1. Проверяем наличие контейнера tab-sitemap в главной странице /tc
    tc_res = api_client.get("/tc")
    assert tc_res.status_code == 200
    assert 'id="tab-sitemap"' in tc_res.text, "Контейнер tab-sitemap отсутствует в /tc"
    assert 'data-tab="tab-sitemap"' in tc_res.text, "Кнопка навигации data-tab='tab-sitemap' отсутствует в /tc"

    # 2. Проверяем регистрацию в tabs-config.js
    cfg_res = api_client.get("/html/apps/modules/tabs-config.js")
    assert cfg_res.status_code == 200
    assert "tab-sitemap" in cfg_res.text, "tab-sitemap не найден в tabs-config.js"

    # 3. Проверяем отдачу HTML/JS ассетов вкладки
    html_res = api_client.get("/html/tab_sitemap/index.html")
    assert html_res.status_code == 200
    assert "Карта сайта (Sitemap)" in html_res.text
    assert "<script" not in html_res.text, "В index.html вкладки не должно быть тегов <script>"

    js_res = api_client.get("/html/tab_sitemap/main.js")
    assert js_res.status_code == 200
    assert "initSitemapTab" in js_res.text
    assert "deactivateSitemapTab" in js_res.text

    # 4. Проверяем отдачу sitemap_data.json и полноту метаданных
    data_res = api_client.get("/html/tab_sitemap/sitemap_data.json")
    assert data_res.status_code == 200
    sitemap_items = data_res.json()
    assert len(sitemap_items) >= 75, "В sitemap_data.json должно быть не менее 75 вкладок"
    sitemap_tab = next((t for t in sitemap_items if t.get("id") == "sitemap"), None)
    assert sitemap_tab is not None, "Вкладка sitemap отсутствует в sitemap_data.json"
    assert "Карта сайта" in sitemap_tab.get("title", "")
    assert len(sitemap_tab.get("features", [])) > 0

    # 5. Проверяем наличие sitemap в меню tc_menu_config.json
    menu_res = api_client.get("/api/v1/menu/config?target=tc")
    assert menu_res.status_code == 200
    menu_data = menu_res.json()
    sidebar_items = menu_data.get("menu", {}).get("sidebarItems", [])
    sitemap_menu_item = next((i for i in sidebar_items if i.get("id") == "sitemap"), None)
    assert sitemap_menu_item is not None, "sitemap отсутствует в sidebarItems меню"
    assert sitemap_menu_item.get("visible") is True


def test_defender_firewall_tab_registration(api_client: TestClient) -> None:
    """Проверяет регистрацию вкладки tab-defender-firewall, отдачу статики и доступность эндпоинта брандмауэра."""
    # 1. Проверяем наличие контейнера tab-defender-firewall в /tc
    tc_res = api_client.get("/tc")
    assert tc_res.status_code == 200
    assert 'id="tab-defender-firewall"' in tc_res.text, "Контейнер tab-defender-firewall отсутствует в /tc"

    # 2. Проверяем регистрацию в tabs-config.js
    cfg_res = api_client.get("/html/apps/modules/tabs-config.js")
    assert cfg_res.status_code == 200
    assert "tab-defender-firewall" in cfg_res.text, "tab-defender-firewall не найден в tabs-config.js"
    assert "tab_defender_firewall" in cfg_res.text, "tab_defender_firewall не найден в tabs-config.js"

    # 3. Проверяем отдачу HTML/JS ассетов вкладки tab_defender_firewall
    html_res = api_client.get("/html/tab_defender_firewall/index.html")
    assert html_res.status_code == 200
    assert "subpane-defender" in html_res.text
    assert "subpane-firewall" in html_res.text
    assert "fw-tbody" in html_res.text
    assert "<script" not in html_res.text, "В index.html вкладки не должно быть тегов <script>"

    js_res = api_client.get("/html/tab_defender_firewall/main.js")
    assert js_res.status_code == 200
    assert "initDefenderFirewallTab" in js_res.text
    assert "activateDefenderFirewallTab" in js_res.text
    assert "fetchFirewallSummary" in js_res.text
    assert "initFirewallSubtab" in js_res.text

    # 4. Проверяем работу API эндпоинта сводки брандмауэра
    fw_res = api_client.get("/api/firewall-manager/summary")
    assert fw_res.status_code == 200
    fw_data = fw_res.json()
    assert "profiles" in fw_data
    assert "rules" in fw_data
    assert len(fw_data["rules"]) > 0

    # 5. Проверяем меню tc_menu_config.json
    menu_res = api_client.get("/api/v1/menu/config?target=tc")
    assert menu_res.status_code == 200
    menu_data = menu_res.json()
    top_buttons = menu_data.get("menu", {}).get("topButtons", [])
    def_btn = next((b for b in top_buttons if b.get("id") == "windows_defender"), None)
    assert def_btn is not None, "windows_defender отсутствует в topButtons меню"
    assert def_btn.get("tab") == "tab-defender-firewall"


def test_tc_navbar_and_settings_modal(api_client: TestClient) -> None:
    """Проверяет компоновку верхней навигации и увеличенного модального окна настроек (/tc)."""
    tc_res = api_client.get("/tc")
    assert tc_res.status_code == 200
    html = tc_res.text

    # 1. В верхней навигации справа только шестеренка настроек
    assert 'id="user-settings-gear-btn"' in html
    assert 'bi-gear-fill' in html

    # 2. Кнопка меню слева
    assert 'id="apps-drawer-toggle-btn"' in html

    # 3. Модальное окно увеличено (modal-lg)
    assert 'id="userSettingsModal"' in html
    assert 'modal-dialog modal-dialog-centered modal-lg' in html

    # 4. Брендинг и бейдж модели внутри модального окна
    assert 'Test Computer' in html
    assert 'id="apps-model-badge"' in html
    assert 'id="apps-model-text"' in html

    # 5. Инструмент проверки доступности модели и селекторы языка/темы
    assert 'id="model-ping-input"' in html
    assert 'id="btn-model-ping-send"' in html
    assert 'id="apps-lang-selector"' in html
    assert 'id="apps-theme-selector"' in html

    # 6. Проверка, что элементы меню используют иконки фреймворка (bi-*)
    menu_res = api_client.get("/api/v1/menu/config?target=tc")
    assert menu_res.status_code == 200
    menu_data = menu_res.json()
    for btn in menu_data.get("menu", {}).get("topButtons", []):
        icon = btn.get("icon", "")
        assert icon.startswith("bi-"), f"Иконка кнопки {btn.get('id')} не из фреймворка: {icon}"
    for item in menu_data.get("menu", {}).get("sidebarItems", []):
        icon = item.get("icon", "")
        assert icon.startswith("bi-"), f"Иконка элемента бокового меню {item.get('id')} не из фреймворка: {icon}"


def test_processes_load_inspector_leaks_subtab(api_client: TestClient) -> None:
    """Проверяет интеграцию панели аудита утечек ресурсов (Leak Hunter) во вкладку инспектора процессов."""
    # 1. Проверяем разметку index.html вкладки tab_processes_load_inspector
    res_html = api_client.get("/html/tab_processes_load_inspector/index.html")
    assert res_html.status_code == 200
    html = res_html.text
    assert "subtab-proc-leaks-btn" in html, "Кнопка суб-вкладки subtab-proc-leaks-btn отсутствует"
    assert "subpane-proc-leaks" in html, "Контейнер суб-вкладки subpane-proc-leaks отсутствует"
    assert "diag-leaks-tbody" in html, "Таблица diag-leaks-tbody отсутствует"
    assert "diag-leaks-total-proc" in html, "Метрика diag-leaks-total-proc отсутствует"
    assert "diag-leaks-suspicious-count" in html, "Метрика diag-leaks-suspicious-count отсутствует"
    assert "proc-leaks-table-resizer" in html, "Ресайзер таблицы proc-leaks-table-resizer отсутствует"

    # 2. Проверяем логику main.js вкладки tab_processes_load_inspector
    res_js = api_client.get("/html/tab_processes_load_inspector/main.js")
    assert res_js.status_code == 200
    js = res_js.text
    assert "fetchProcessLeaks" in js, "Функция fetchProcessLeaks не найдена в main.js"
    assert "renderProcessLeaksTable" in js, "Функция renderProcessLeaksTable не найдена в main.js"
    assert "subtab-proc-leaks-btn" in js, "Селектор кнопки суб-вкладки утечек не найден в main.js"
    assert "leaks" in js, "Маршрутизация суб-вкладки leaks не найдена в switchProcessesSubTab"

    # 3. Проверяем редирект в apps/main.js
    res_apps_js = api_client.get("/html/apps/main.js")
    assert res_apps_js.status_code == 200
    apps_js = res_apps_js.text
    assert "process-leaks" in apps_js, "Редирект process-leaks отсутствует в apps/main.js"
    assert "switchProcessesSubTab" in apps_js, "Вызов switchProcessesSubTab отсутствует в apps/main.js"

    # 4. Проверяем эндпоинт API утечек процессов
    leaks_res = api_client.get("/api/v1/system/diagnostics/leaks?limit=50")
    assert leaks_res.status_code == 200
    data = leaks_res.json()
    assert "total_processes" in data
    assert "suspicious_count" in data
    assert "all_processes" in data
    assert isinstance(data["all_processes"], list)








