# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - AI Smart Tooltips Mechanism
# =============================================================================
# Description:
#   Модульные и интеграционные тесты механизма интеллектуальных всплывающих
#   подсказок ИИ (AI Smart Tooltips), появляющихся НАД элементами интерфейса,
#   проверки кэша WikiLLM/ИИ и вызова стандартного модального окна ассистента.
#
# File: test_ai_smart_tooltips.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 18:09:00
# =============================================================================

from __future__ import annotations

from pathlib import Path
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


def test_tooltip_script_assets_served(api_client: TestClient) -> None:
    """Проверяет доступность обновленного скрипта global-tooltips-i18n.js через HTTP."""
    res = api_client.get("/html/js/global-tooltips-i18n.js")
    assert res.status_code == 200, "Скрипт /html/js/global-tooltips-i18n.js недоступен"
    content = res.text
    assert "AISmartTooltip" in content, "AISmartTooltip не найден в global-tooltips-i18n.js"
    assert "DEFAULT_KNOWLEDGE_BASE" in content, "DEFAULT_KNOWLEDGE_BASE отсутствует в скрипте"
    assert "cfa" in content, "Термин cfa отсутствует в базе знаний тултипов"
    assert "AIModalDialog" in content, "Связка с AIModalDialog отсутствует в тултипе"


def test_tooltip_styles_in_components_css(api_client: TestClient) -> None:
    """Проверяет наличие CSS стилей для тултипов НАД элементом в components.css."""
    res = api_client.get("/html/css/components.css")
    assert res.status_code == 200, "Файл /html/css/components.css недоступен"
    css = res.text
    assert ".ai-smart-tooltip-container" in css, "Селектор .ai-smart-tooltip-container отсутствует"
    assert ".ai-smart-tooltip-arrow" in css, "Стрелка .ai-smart-tooltip-arrow отсутствует"
    assert "var(--ui-bg-surface-elevated" in css, "CSS-переменные темы не используются в тултипе"
    assert ".ai-smart-tooltip-btn" in css, "Кнопка действия .ai-smart-tooltip-btn отсутствует в стилях"


def test_defender_tab_contains_cfa_tooltip_attributes(api_client: TestClient) -> None:
    """Проверяет разметку вкладки Defender на наличие атрибутов тултипов на кнопке CFA и смежных табах."""
    res = api_client.get("/html/tab_defender_firewall/index.html")
    assert res.status_code == 200, "Вкладка Defender недоступна"
    html = res.text
    assert 'id="def-tab-cfa-btn"' in html, "Кнопка def-tab-cfa-btn отсутствует"
    assert 'data-term="cfa"' in html, "Атрибут data-term='cfa' отсутствует на кнопке CFA"
    assert 'data-ai-tooltip="true"' in html, "Атрибут data-ai-tooltip отсутствует"
    assert 'Ransomware / CFA' in html, "Текст Ransomware / CFA отсутствует на кнопке"


def test_index_html_includes_versioned_tooltip_scripts(api_client: TestClient) -> None:
    """Проверяет актуальную версию скрипта тултипов и css в index.html."""
    import re
    res = api_client.get("/tc")
    assert res.status_code == 200, "Страница /tc недоступна"
    html = res.text
    assert re.search(r"global-tooltips-i18n\.js\?v=202610\d{2}_v\d+", html), "Не обновлена версия скрипта тултипов в index.html"
    assert "main.css?v=" in html, "Не обновлена версия main.css в index.html"


def test_ai_modal_dialog_dispatches_explained_event() -> None:
    """Проверяет, что контроллер ai_modal_dialog/main.js диспатчит событие ai-modal:explained."""
    modal_js_path = Path("apps/windows/api/webgui/ai_modal_dialog/main.js")
    assert modal_js_path.exists(), "Файл ai_modal_dialog/main.js не найден"
    content = modal_js_path.read_text(encoding="utf-8")
    assert "ai-modal:explained" in content, "Диспатч события ai-modal:explained отсутствует в ai_modal_dialog/main.js"


def test_system_control_tab_contains_ai_tooltip_attributes(api_client: TestClient) -> None:
    """Проверяет разметку вкладки tab-system-control на наличие data-ai-tooltip и data-term."""
    res = api_client.get("/html/tab_system_control/index.html")
    assert res.status_code == 200, "Вкладка System Control недоступна"
    html = res.text

    # Проверка верхней панели журналов (источники)
    for src in ["summary-dashboard", "event-logs", "activity", "power-lifecycle", "defender-logs"]:
        assert f'data-source="{src}"' in html and f'data-term="{src}"' in html and 'data-ai-tooltip="true"' in html

    # Проверка кнопок действий
    assert 'id="btn-slc-scan" data-term="slc-scan" data-ai-tooltip="true"' in html
    assert 'id="btn-slc-refresh" data-term="slc-refresh" data-ai-tooltip="true"' in html

    # Проверка режимов аналитики
    assert 'data-term="mode-live"' in html
    assert 'data-term="mode-audit"' in html
    assert 'data-term="mode-rag"' in html
    assert 'data-term="mode-incidents"' in html
    assert 'data-term="mode-timeline"' in html
    assert 'data-term="mode-errors"' in html
    assert 'data-term="mode-raw"' in html

    # Проверка кнопок ИИ и аналитики сбоев
    assert 'id="btn-slc-ask-ai" data-term="ask-ai" data-ai-tooltip="true"' in html
    assert 'id="btn-sum-ask-ai" data-term="ask-ai" data-ai-tooltip="true"' in html
    assert 'id="btn-sum-refresh" data-term="sum-refresh" data-ai-tooltip="true"' in html
    assert 'id="btn-sum-export" data-term="sum-export" data-ai-tooltip="true"' in html

    # Проверка табов категорий сбоев
    assert 'id="btn-sum-tab-power" data-term="sum-power"' in html or 'data-target="power" data-term="sum-power"' in html
    assert 'id="btn-sum-tab-bsod" data-term="sum-bsod"' in html or 'data-target="bsod" data-term="sum-bsod"' in html
    assert 'id="btn-sum-tab-drivers" data-term="sum-drivers"' in html or 'data-target="drivers" data-term="sum-drivers"' in html
    assert 'id="btn-sum-tab-suspicious" data-term="sum-suspicious"' in html or 'data-target="suspicious" data-term="sum-suspicious"' in html


def test_system_control_main_js_initializes_tooltips() -> None:
    """Проверяет, что main.js вкладки tab-system-control вызывает AISmartTooltip.initAll."""
    js_path = Path("apps/windows/api/webgui/tab_system_control/main.js")
    assert js_path.exists(), "Файл tab_system_control/main.js не найден"
    content = js_path.read_text(encoding="utf-8")
    assert "AISmartTooltip" in content, "AISmartTooltip не упомянут в main.js"
    assert "AISmartTooltip.initAll" in content, "Вызов AISmartTooltip.initAll отсутствует в main.js"


def test_software_scanner_tab_contains_ai_tooltip_attributes(api_client: TestClient) -> None:
    """Проверяет разметку вкладки tab-software-monitor на наличие атрибутов data-ai-tooltip и data-term."""
    res = api_client.get("/html/tab_software_monitor/index.html")
    assert res.status_code == 200, "Вкладка Software Monitor недоступна"
    html = res.text

    # Проверка главных суб-вкладок
    for sub in ["inventory", "packages", "dormant", "transparency", "heavy", "sockets"]:
        assert f'id="subtab-sw-{sub}-btn"' in html and f'data-term="sw-{sub}"' in html and 'data-ai-tooltip="true"' in html

    # Проверка вложенных суб-вкладок менеджера пакетов
    assert 'id="sw-subtab-winget-btn" data-term="sw-winget" data-ai-tooltip="true"' in html
    assert 'id="sw-subtab-ninite-btn" data-term="sw-ninite" data-ai-tooltip="true"' in html

    # Проверка контролов запуска сканирования ПО
    assert 'id="sw-scan-mode-select" data-term="sw-scan-modes" data-ai-tooltip="true"' in html
    assert 'id="sw-btn-trigger-scan" data-term="sw-scan-trigger" data-ai-tooltip="true"' in html

    # Проверка фильтров статусов
    assert 'data-filter="dormant" data-term="sw-filter-dormant" data-ai-tooltip="true"' in html
    assert 'data-filter="orphan" data-term="sw-filter-orphan" data-ai-tooltip="true"' in html
    assert 'data-filter="store_app" data-term="sw-filter-store" data-ai-tooltip="true"' in html

    # Проверка кнопок обновления тяжелых ресурсов и сокетов
    assert 'id="sw-btn-refresh-heavy" data-term="sw-refresh-heavy" data-ai-tooltip="true"' in html
    assert 'id="sw-btn-refresh-sockets" data-term="sw-refresh-sockets" data-ai-tooltip="true"' in html


def test_software_scanner_main_js_initializes_tooltips() -> None:
    """Проверяет, что main.js вкладки tab-software-monitor вызывает AISmartTooltip.initAll."""
    js_path = Path("apps/windows/api/webgui/tab_software_monitor/main.js")
    assert js_path.exists(), "Файл tab_software_monitor/main.js не найден"
    content = js_path.read_text(encoding="utf-8")
    assert "AISmartTooltip" in content, "AISmartTooltip не упомянут в tab_software_monitor/main.js"
    assert "AISmartTooltip.initAll" in content, "Вызов AISmartTooltip.initAll отсутствует в tab_software_monitor/main.js"


def test_software_scanner_terms_in_knowledge_base(api_client: TestClient) -> None:
    """Проверяет наличие терминов tab-software-scanner в базе знаний global-tooltips-i18n.js."""
    res = api_client.get("/html/js/global-tooltips-i18n.js")
    assert res.status_code == 200, "Скрипт тултипов недоступен"
    content = res.text
    for term in [
        'sw-inventory', 'sw-packages', 'sw-dormant', 'sw-transparency',
        'sw-heavy', 'sw-sockets', 'sw-winget', 'sw-ninite',
        'sw-scan-trigger', 'sw-scan-modes', 'sw-filter-dormant',
        'sw-filter-orphan', 'sw-filter-store', 'sw-refresh-heavy', 'sw-refresh-sockets'
    ]:
        assert f"'{term}'" in content, f"Термин {term} отсутствует в базе знаний скрипта тултипов"


def test_windows_admin_tab_contains_ai_tooltip_attributes(api_client: TestClient) -> None:
    """Проверяет разметку вкладки tab-windows-admin на наличие атрибутов data-ai-tooltip и data-term."""
    res = api_client.get("/html/tab_windows_admin/index.html")
    assert res.status_code == 200, "Вкладка Windows Admin недоступна"
    html = res.text

    # Проверка кнопок заголовка
    assert 'id="btn-winadmin-refresh" data-term="winadmin-refresh" data-ai-tooltip="true"' in html
    assert 'id="btn-open-create-user-modal" data-term="winadmin-create-user" data-ai-tooltip="true"' in html

    # Проверка виджетов Privacy Radar и Windows Backup
    assert 'id="privacy-radar-widget" data-term="winadmin-privacy-radar" data-ai-tooltip="true"' in html
    assert 'id="windows-backup-widget" data-term="winadmin-backup" data-ai-tooltip="true"' in html

    # Проверка навигационных суб-вкладок
    assert 'id="subtab-winadmin-users-btn"' in html and 'data-term="winadmin-users"' in html
    assert 'id="subtab-winadmin-groups-btn"' in html and 'data-term="winadmin-groups"' in html
    assert 'id="subtab-winadmin-events-btn"' in html and 'data-term="winadmin-events"' in html
    assert 'id="subtab-winadmin-security-btn"' in html and 'data-term="winadmin-security"' in html
    assert 'id="subtab-winadmin-pid-btn"' in html and 'data-term="winadmin-pid"' in html
    assert 'id="subtab-winadmin-catalog-btn"' in html and 'data-term="winadmin-catalog"' in html
    assert 'id="subtab-winadmin-acl-btn"' in html and 'data-term="winadmin-acl"' in html

    # Проверка фильтров пользователей
    assert 'data-filter="hidden" data-term="winadmin-filter-hidden" data-ai-tooltip="true"' in html
    assert 'data-filter="admins" data-term="winadmin-filter-admins" data-ai-tooltip="true"' in html

    # Проверка кнопок аудита
    assert 'id="btn-check-who-is-admin" data-term="winadmin-audit-admins" data-ai-tooltip="true"' in html
    assert 'id="btn-check-service-logon" data-term="winadmin-audit-service" data-ai-tooltip="true"' in html
    assert 'id="btn-check-rdp" data-term="winadmin-audit-rdp" data-ai-tooltip="true"' in html
    assert 'id="btn-check-orphaned" data-term="winadmin-audit-orphaned" data-ai-tooltip="true"' in html

    # Проверка ACL кнопок
    assert 'id="btn-acl-takeown" data-term="winadmin-acl-takeown" data-ai-tooltip="true"' in html
    assert 'id="btn-acl-reset-default" data-term="winadmin-acl-reset" data-ai-tooltip="true"' in html
    assert 'id="btn-acl-backup-create" data-term="winadmin-acl-backup" data-ai-tooltip="true"' in html
    assert 'id="btn-acl-restore-rollback" data-term="winadmin-acl-rollback" data-ai-tooltip="true"' in html
    assert 'id="btn-winadmin-acl-inspect" data-term="winadmin-acl-inspect" data-ai-tooltip="true"' in html
    assert 'id="btn-winadmin-acl-grant" data-term="winadmin-acl-grant" data-ai-tooltip="true"' in html


def test_windows_admin_main_js_initializes_tooltips() -> None:
    """Проверяет, что main.js вкладки tab-windows-admin вызывает AISmartTooltip.initAll."""
    js_path = Path("apps/windows/api/webgui/tab_windows_admin/main.js")
    assert js_path.exists(), "Файл tab_windows_admin/main.js не найден"
    content = js_path.read_text(encoding="utf-8")
    assert "AISmartTooltip" in content, "AISmartTooltip не упомянут в tab_windows_admin/main.js"
    assert "AISmartTooltip.initAll" in content, "Вызов AISmartTooltip.initAll отсутствует в tab_windows_admin/main.js"


def test_windows_admin_terms_in_knowledge_base(api_client: TestClient) -> None:
    """Проверяет наличие терминов tab-windows-admin в базе знаний global-tooltips-i18n.js."""
    res = api_client.get("/html/js/global-tooltips-i18n.js")
    assert res.status_code == 200, "Скрипт тултипов недоступен"
    content = res.text
    for term in [
        'winadmin-users', 'winadmin-groups', 'winadmin-events', 'winadmin-security',
        'winadmin-pid', 'winadmin-catalog', 'winadmin-acl', 'winadmin-refresh',
        'winadmin-create-user', 'winadmin-privacy-radar', 'winadmin-backup',
        'winadmin-audit-admins', 'winadmin-audit-service', 'winadmin-audit-rdp',
        'winadmin-audit-orphaned', 'winadmin-acl-takeown', 'winadmin-acl-reset',
        'winadmin-acl-backup', 'winadmin-acl-rollback', 'winadmin-acl-inspect',
        'winadmin-acl-grant', 'winadmin-filter-hidden', 'winadmin-filter-admins'
    ]:
        assert f"'{term}'" in content, f"Термин {term} отсутствует в базе знаний скрипта тултипов"


def test_diagnostics_prompt_manager_ui_navigation_registered() -> None:
    """Проверяет регистрацию шаблона ui_navigation и алиасов в DiagnosticsPromptManager."""
    from apps.windows.api.diagnostics_prompt_manager import prompt_manager

    # Проверка нормализации алиасов
    assert prompt_manager.normalize_table_type("ui_navigation") == "ui_navigation"
    assert prompt_manager.normalize_table_type("ui_element") == "ui_navigation"
    assert prompt_manager.normalize_table_type("tooltip") == "ui_navigation"
    assert prompt_manager.normalize_table_type("navigation") == "ui_navigation"

    # Проверка получения шаблона
    tmpl = prompt_manager.get_template("ui_navigation")
    assert tmpl.table_type == "ui_navigation"
    assert "гид" in tmpl.name.lower() or "руководство" in tmpl.name.lower() or "навигации" in tmpl.name.lower()
    assert "ассистент" in tmpl.system_instruction.lower() or "гид" in tmpl.name.lower()
    assert "action_steps" in tmpl.prompt_template
    assert tmpl.questions_prompt is not None and "3" in tmpl.questions_prompt


def test_global_tooltips_uses_ui_navigation_and_rich_context(api_client: TestClient) -> None:
    """Проверяет, что тултипы передают tableType: 'ui_navigation' и содержат термин forensics."""
    res = api_client.get("/html/js/global-tooltips-i18n.js")
    assert res.status_code == 200, "Скрипт тултипов недоступен"
    content = res.text

    # Проверка, что в базе знаний есть сущность forensics
    assert "'forensics':" in content, "Сущность forensics отсутствует в DEFAULT_KNOWLEDGE_BASE"
    assert "Форензика" in content or "черный ящик" in content.lower()

    # Проверка, что тултип больше не передает захардкоженный tableType: 'security'
    assert "tableType: 'ui_navigation'" in content, "tableType: 'ui_navigation' отсутствует в handleActionClick"
    assert "tableType: 'security'" not in content, "Остался устаревший tableType: 'security' в handleActionClick"

    # Проверка формирования расширенного контекста
    assert "paneSummarySnippet" in content
    assert "fullRawContent" in content


def test_prompt_endpoint_serves_ui_navigation(api_client: TestClient) -> None:
    """Проверяет доступность эндпоинта шаблона ui_navigation через REST API."""
    res = api_client.get("/api/v1/diagnostics/prompts/ui_navigation")
    assert res.status_code == 200, "Эндпоинт /api/v1/diagnostics/prompts/ui_navigation вернул ошибку"
    data = res.json()
    assert data["table_type"] == "ui_navigation"
    assert "system_instruction" in data
    assert "prompt_template" in data
    assert len(data["system_instruction"]) > 50


def test_processes_load_inspector_tab_contains_ai_tooltip_attributes(api_client: TestClient) -> None:
    """Проверяет разметку вкладки tab-processes-load-inspector на наличие атрибутов data-ai-tooltip и data-term."""
    res = api_client.get("/html/tab_processes_load_inspector/index.html")
    assert res.status_code == 200, "Вкладка Processes Load Inspector недоступна"
    html = res.text

    # Проверка контролов шапки
    assert 'id="engine-status-badge" data-term="proc-engine-status" data-ai-tooltip="true"' in html
    assert 'id="btn-global-refresh" data-term="proc-global-refresh" data-ai-tooltip="true"' in html

    # Проверка 5 суб-вкладок
    assert 'id="subtab-proc-manager-btn"' in html and 'data-term="proc-subtab-manager"' in html
    assert 'id="subtab-proc-top-btn"' in html and 'data-term="proc-subtab-top"' in html
    assert 'id="subtab-proc-net-btn"' in html and 'data-term="proc-subtab-net"' in html
    assert 'id="subtab-proc-files-btn"' in html and 'data-term="proc-subtab-files"' in html
    assert 'id="subtab-proc-leaks-btn"' in html and 'data-term="proc-subtab-leaks"' in html

    # Проверка карточек и кнопок Process Manager
    assert 'id="pm-filter-card-apps" data-term="pm-card-apps" data-ai-tooltip="true"' in html
    assert 'id="pm-filter-card-bg" data-term="pm-card-bg" data-ai-tooltip="true"' in html
    assert 'id="pm-filter-card-win" data-term="pm-card-win" data-ai-tooltip="true"' in html
    assert 'id="pm-filter-card-all" data-term="pm-card-all" data-ai-tooltip="true"' in html
    assert 'id="pm-refresh-btn" data-term="pm-refresh" data-ai-tooltip="true"' in html
    assert 'id="pm-category-filter-group" role="group" data-term="pm-category-filters" data-ai-tooltip="true"' in html
    assert 'id="pm-toggle-expand-btn" data-term="pm-toggle-expand" data-ai-tooltip="true"' in html
    assert 'id="pm-btn-open-ai-modal" data-term="pm-ai-modal" data-ai-tooltip="true"' in html
    assert 'id="pm-btn-investigate-powershell" data-term="pm-investigate-ps" data-ai-tooltip="true"' in html
    assert 'id="pm-btn-prompt-settings" data-term="pm-prompt-settings" data-ai-tooltip="true"' in html

    # Проверка контролов Top Stream и Сети
    assert 'id="btn-sys-pause-proc" data-term="proc-top-pause" data-ai-tooltip="true"' in html
    assert 'id="btn-sys-refresh-proc" data-term="proc-top-refresh" data-ai-tooltip="true"' in html
    assert 'id="btn-proc-net-filter-internet" data-term="proc-net-filter-internet" data-ai-tooltip="true"' in html
    assert 'id="btn-proc-pause-net" data-term="proc-net-pause" data-ai-tooltip="true"' in html
    assert 'id="btn-proc-refresh-net" data-term="proc-net-refresh" data-ai-tooltip="true"' in html

    # Проверка Files Watcher и Leak Hunter
    assert 'id="proc-watch-dir-badge" data-term="proc-watch-badge" data-ai-tooltip="true"' in html
    assert 'id="btn-proc-watch-exclusions" data-term="proc-watch-exclusions" data-ai-tooltip="true"' in html
    assert 'id="btn-proc-change-watch-dir" data-term="proc-watch-change-dir" data-ai-tooltip="true"' in html
    assert 'id="btn-proc-refresh-watcher" data-term="proc-watch-refresh" data-ai-tooltip="true"' in html
    assert 'data-term="diag-leaks-total" data-ai-tooltip="true"' in html
    assert 'data-term="diag-leaks-suspicious" data-ai-tooltip="true"' in html
    assert 'data-term="diag-leaks-handles" data-ai-tooltip="true"' in html
    assert 'data-term="diag-leaks-gdi" data-ai-tooltip="true"' in html
    assert 'id="diag-leaks-filter-group" role="group" data-term="diag-leaks-filters" data-ai-tooltip="true"' in html
    assert 'id="btn-diag-leaks-refresh" data-term="diag-leaks-refresh" data-ai-tooltip="true"' in html


def test_processes_load_inspector_main_js_initializes_tooltips() -> None:
    """Проверяет, что main.js вкладки tab-processes-load-inspector вызывает AISmartTooltip.initAll."""
    js_path = Path("apps/windows/api/webgui/tab_processes_load_inspector/main.js")
    assert js_path.exists(), "Файл tab_processes_load_inspector/main.js не найден"
    content = js_path.read_text(encoding="utf-8")
    assert "AISmartTooltip" in content, "AISmartTooltip не упомянут в tab_processes_load_inspector/main.js"
    assert "AISmartTooltip.initAll" in content, "Вызов AISmartTooltip.initAll отсутствует в tab_processes_load_inspector/main.js"


def test_processes_load_inspector_terms_in_knowledge_base(api_client: TestClient) -> None:
    """Проверяет наличие терминов tab-processes-load-inspector в базе знаний global-tooltips-i18n.js."""
    res = api_client.get("/html/js/global-tooltips-i18n.js")
    assert res.status_code == 200, "Скрипт тултипов недоступен"
    content = res.text
    for term in [
        'proc-engine-status', 'proc-global-refresh', 'proc-subtab-manager',
        'proc-subtab-top', 'proc-subtab-net', 'proc-subtab-files', 'proc-subtab-leaks',
        'pm-card-apps', 'pm-card-bg', 'pm-card-win', 'pm-card-all',
        'pm-refresh', 'pm-category-filters', 'pm-toggle-expand', 'pm-ai-modal',
        'pm-investigate-ps', 'pm-prompt-settings', 'proc-top-pause', 'proc-top-refresh',
        'proc-net-filter-internet', 'proc-net-pause', 'proc-net-refresh',
        'proc-watch-badge', 'proc-watch-exclusions', 'proc-watch-change-dir',
        'proc-watch-refresh', 'diag-leaks-total', 'diag-leaks-suspicious',
        'diag-leaks-handles', 'diag-leaks-gdi', 'diag-leaks-filters', 'diag-leaks-refresh'
    ]:
        assert f"'{term}'" in content, f"Термин {term} отсутствует в базе знаний скрипта тултипов"



def test_internals_logs_tooltip_content(api_client: TestClient) -> None:
    """Проверяет правильный текст тултипа для элемента Центр логов в разметке и локалях."""
    res = api_client.get("/html/tab_app_internals/index.html")
    assert res.status_code == 200, "Вкладка App Internals недоступна"
    html = res.text

    # Проверяем атрибут title на кнопке Центра логов
    expected_tooltip = "Просмотр внутренних логов программы ai-tc"
    assert f'title="{expected_tooltip}"' in html, "Неправильный текст тултипа для Центра логов в index.html"
    assert 'data-i18n="internals.subtabLogsLabel">Центр логов</span>' in html

    # Проверяем локаль ru.json
    loc_res = api_client.get("/html/locales/ru.json")
    assert loc_res.status_code == 200, "Локаль ru.json недоступна"
    loc_data = loc_res.json()
    assert loc_data.get("internals", {}).get("subtabLogsTitle") == expected_tooltip
    assert loc_data.get("tooltips", {}).get("internals-logs", {}).get("summary") == expected_tooltip


def test_tooltips_editor_subtab_in_tab_app_internals(api_client: TestClient) -> None:
    """Проверяет регистрацию и разметку субпанели tooltips-editor во вкладке tab-app-internals."""
    res = api_client.get("/html/tab_app_internals/index.html")
    assert res.status_code == 200
    html = res.text

    assert 'id="subtab-internals-tooltips-editor-btn"' in html, "Кнопка субпанели tooltips-editor отсутствует"
    assert 'data-panel-id="tooltips-editor"' in html
    assert 'id="subpane-internals-tooltips-editor"' in html, "Контейнер субпанели tooltips-editor отсутствует"


def test_tooltips_router_api_crud(api_client: TestClient) -> None:
    """Проверяет работу CRUD эндпоинтов роутера /api/v1/tooltips."""
    # 1. Получение списка
    list_res = api_client.get("/api/v1/tooltips?lang=ru")
    assert list_res.status_code == 200
    data = list_res.json()
    assert data["status"] == "success"
    assert "items" in data
    assert any(item["key"] == "internals-logs" for item in data["items"])

    # 2. Получение конкретной подсказки
    item_res = api_client.get("/api/v1/tooltips/internals-logs?lang=ru")
    assert item_res.status_code == 200
    item = item_res.json()
    assert item["key"] == "internals-logs"
    assert item["summary"] == "Просмотр внутренних логов программы ai-tc"

    # 3. Сохранение тестовой подсказки
    test_key = "test_custom_probe"
    post_payload = {
        "key": test_key,
        "title": "Тестовый зонд",
        "fullTitle": "Тестовый диагностический зонд",
        "summary": "Проверка диагностических сенсоров",
        "category": "Тестирование",
        "icon": "🧪",
        "lang": "ru",
        "source": "custom"
    }
    save_res = api_client.post("/api/v1/tooltips", json=post_payload)
    assert save_res.status_code == 200
    assert save_res.json()["key"] == test_key

    # 4. Проверка созданной подсказки
    get_custom = api_client.get(f"/api/v1/tooltips/{test_key}?lang=ru")
    assert get_custom.status_code == 200
    assert get_custom.json()["summary"] == "Проверка диагностических сенсоров"

    # 5. Удаление тестовой подсказки
    del_res = api_client.delete(f"/api/v1/tooltips/{test_key}?lang=ru")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "success"
