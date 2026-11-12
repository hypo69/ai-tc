"""
=============================================================================
Process Name: Test Windows Admin PID Inspector and Process Search
=============================================================================
Description:
    Модульные тесты для проверки функционала PID-инспектора в tab-windows-admin:
    - Переименование URL hash в #tab-windows-admin#pid-инспецтор
    - Поддержка нормализации hash (#pid, #pid-инспецтор, #pid-инспектор)
    - Наличие в DOM элементов: поиск по PID, поиск по названию, выпадающий список
      процессов и кнопка обновления списка
    - Экспорт и интерфейсы в panel_pid_inspector/panel.js и main.js

File: test_tab_windows_admin_pid_inspector.py
Project: ai-windows-admin
Package: tests
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-11-01 15:35:00
=============================================================================
"""

from pathlib import Path
import pytest


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_WEBGUI_DIR = _PROJECT_ROOT / "apps" / "windows" / "api" / "webgui"


def test_pid_inspector_dom_structure() -> None:
    """Проверяет наличие всех компонентов поиска процессов и выпадающего списка в index.html."""
    html_file = _WEBGUI_DIR / "tab_windows_admin" / "index.html"
    assert html_file.exists(), f"Файл {html_file} не найден"
    content = html_file.read_text(encoding="utf-8")

    # 1. Проверяем кнопку суб-вкладки с обновленным data-panel-id="pid-инспецтор"
    assert 'id="subtab-winadmin-pid-btn"' in content, "Кнопка суб-вкладки subtab-winadmin-pid-btn не найдена"
    assert 'data-panel-id="pid-инспецтор"' in content, "data-panel-id должен быть установлен в pid-инспецтор"
    assert "PID-инспектор" in content, "Заголовок вкладки должен отображать 'PID-инспектор'"

    # 2. Проверяем элементы управления панели
    assert 'id="input-explain-pid"' in content, "Поле ввода PID (input-explain-pid) не найдено"
    assert 'id="input-explain-name"' in content, "Поле поиска по названию (input-explain-name) не найдено"
    assert 'id="select-explain-process"' in content, "Выпадающий список процессов (select-explain-process) не найден"
    assert 'id="btn-refresh-processes-list"' in content, "Кнопка обновления списка процессов не найдена"
    assert 'id="btn-explain-pid"' in content, "Кнопка исследования процесса не найдена"
    assert 'id="pid-dossier-output"' in content, "Контейнер досье процесса не найден"


def test_main_js_pid_inspector_routing() -> None:
    """Проверяет логику нормализации URL hash и маршрутизацию в main.js."""
    js_file = _WEBGUI_DIR / "tab_windows_admin" / "main.js"
    assert js_file.exists(), f"Файл {js_file} не найден"
    content = js_file.read_text(encoding="utf-8")

    # 1. Проверяем нормализацию subtab ID для pid-инспецтор
    assert "pid-инспецтор" in content, "main.js должен содержать идентификатор панели pid-инспецтор"
    assert "инспецтор" in content, "main.js должен поддерживать проверку инспецтор"
    assert "initPidInspector" in content, "main.js должен вызывать initPidInspector"
    assert "window.initPidInspector = initPidInspector;" in content

    # 2. Проверяем обработку декодирования URI компонентов
    assert "decodeURIComponent" in content, "main.js должен декодировать кириллические фрагменты hash"


def test_panel_pid_inspector_js_exports() -> None:
    """Проверяет экспорт ключевых функций в panel_pid_inspector/panel.js."""
    panel_js = _WEBGUI_DIR / "tab_windows_admin" / "panel_pid_inspector" / "panel.js"
    assert panel_js.exists(), f"Файл {panel_js} не найден"
    content = panel_js.read_text(encoding="utf-8")

    # Проверяем экспорт функций инспектора и поиска
    assert "export async function handleExplainPid(" in content
    assert "export async function loadProcessesList(" in content
    assert "export function renderProcessOptions(" in content
    assert "export function filterProcessesByName(" in content
    assert "export function onProcessSelected(" in content
    assert "export async function initPidInspector(" in content

    # Проверяем использование API для загрузки процессов и досье
    assert "/api/process-manager/list" in content, "Загрузка процессов должна обращаться к /api/process-manager/list"
    assert "/api/windows/identity/explain-pid/" in content, "Досье должно запрашиваться через explain-pid"
