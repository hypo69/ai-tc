"""
=============================================================================
Process Name: Test Windows Admin PID Inspector and Process Search
=============================================================================
Description:
    Модульные тесты для проверки функционала PID-инспектора в tab-windows-admin:
    - Переименование URL hash в #tab-windows-admin#panel-pid-inspector
    - Поддержка нормализации hash (#pid, #pid-inspector, #pid-инспектор)
    - Наличие в DOM элементов: поиск по PID, поиск по названию, выпадающий список
      процессов и кнопка обновления списка
    - Экспорт и интерфейсы в panel_pid_inspector/panel.js и main.js

File: test_tab_windows_admin_pid_inspector.py
Project: ai-tc
Package: tests
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-11-20 15:51:30
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

    # 1. Проверяем кнопку суб-вкладки с обновленным data-panel-id="pid-inspector"
    assert 'id="subtab-winadmin-pid-btn"' in content, "Кнопка суб-вкладки subtab-winadmin-pid-btn не найдена"
    assert 'data-panel-id="pid-inspector"' in content, "data-panel-id должен быть установлен в pid-inspector"
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

    # 1. Проверяем нормализацию subtab ID для pid-inspector
    assert "pid-inspector" in content, "main.js должен содержать идентификатор панели pid-inspector"
    assert "inspector" in content, "main.js должен поддерживать проверку inspector"
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

    # Проверяем использование API для загрузки всех процессов без лимитов и досье
    assert "/api/v1/process-manager/list?limit=0&sort_by=name&live=true" in content, (
        "Загрузка процессов должна запрашивать все активные процессы без лимита"
    )
    assert "limit=300" not in content, "Искусственный лимит limit=300 должен быть удален"
    assert "/api/v1/windows/identity/explain-pid/" in content, "Досье должно запрашиваться через explain-pid"


def test_process_manager_list_returns_all_active_processes() -> None:
    """Проверяет, что /api/v1/process-manager/list?limit=0&live=true возвращает все активные процессы без обрезки."""
    import psutil
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from apps.windows.sdk.modules.process_manager.router import init_router

    app = FastAPI()
    app.include_router(init_router())
    client = TestClient(app)

    expected_count = len(list(psutil.process_iter(["pid"])))
    resp = client.get("/api/v1/process-manager/list?limit=0&sort_by=name&live=true")
    assert resp.status_code == 200
    items = resp.json()
    assert isinstance(items, list)
    # Допускаем небольшой дрейф запущенных/завершённых процессов между замерами, но не обрезку до 10/50/300
    assert len(items) >= int(expected_count * 0.8), (
        f"Ожидались все активные процессы (~{expected_count}), получено только {len(items)}"
    )
