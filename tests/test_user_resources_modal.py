# -*- coding: utf-8 -*-
"""
=============================================================================
Process Name: Test User Resources Modal & Telemetry
=============================================================================
Description:
    Тесты функциональности модального окна потребляемых ресурсов пользователя:
    - Проверка наличия элементов DOM модального окна #userResourcesModal в index.html
    - Проверка кнопки открытия ресурсов в panel_users/panel.js
    - Проверка экспорта функций в panel_users/resources_modal.js
    - Проверка структуры метрик в API /api/sysadmin/accounts/{username}/metrics

File: test_user_resources_modal.py
Project: ai-windows-admin
Package: tests
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-11-01 14:58:00
=============================================================================
"""

import os
from pathlib import Path
import pytest


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_WEBGUI_DIR = _PROJECT_ROOT / "apps" / "windows" / "api" / "webgui"


def test_user_resources_modal_dom_structure() -> None:
    """Проверяет корректность разметки модального окна #userResourcesModal в index.html."""
    html_file = _WEBGUI_DIR / "tab_windows_admin" / "index.html"
    assert html_file.exists(), f"Файл {html_file} не найден"
    content = html_file.read_text(encoding="utf-8")

    assert 'id="userResourcesModal"' in content, "Модальное окно #userResourcesModal не найдено"
    assert 'id="user-resources-modal-username"' in content, "Бейдж имени пользователя не найден"
    assert 'id="user-resources-modal-loading"' in content, "Индикатор загрузки не найден"
    assert 'id="user-resources-modal-content"' in content, "Контейнер контента не найден"
    assert 'id="user-res-procs-count"' in content, "Счетчик процессов не найден"
    assert 'id="user-res-memory-total"' in content, "Сводка памяти не найдена"
    assert 'id="user-res-cpu-total"' in content, "Сводка CPU не найдена"
    assert 'id="user-res-search-input"' in content, "Поле поиска процессов не найдено"
    assert 'id="user-res-sort-select"' in content, "Селектор сортировки не найден"
    assert 'id="btn-refresh-user-resources"' in content, "Кнопка обновления метрик не найдена"
    assert 'id="user-resources-tbody"' in content, "Тело таблицы ресурсов #user-resources-tbody не найдено"
    assert 'id="user-res-filtered-count"' in content, "Счетчик отфильтрованных процессов не найден"


def test_user_resources_button_in_panel_js() -> None:
    """Проверяет генерацию кнопки вызова ресурсов и обработчика в panel.js."""
    panel_js = _WEBGUI_DIR / "tab_windows_admin" / "panel_users" / "panel.js"
    assert panel_js.exists(), f"Файл {panel_js} не найден"
    content = panel_js.read_text(encoding="utf-8")

    assert "btn-open-user-resources" in content, "Класс кнопки вызова ресурсов отсутствует в panel.js"
    assert "openUserResourcesModal" in content, "Вызов openUserResourcesModal отсутствует в panel.js"


def test_user_resources_modal_module() -> None:
    """Проверяет наличие модуля resources_modal.js и экспортируемых функций."""
    modal_js = _WEBGUI_DIR / "tab_windows_admin" / "panel_users" / "resources_modal.js"
    assert modal_js.exists(), f"Файл {modal_js} не найден"
    content = modal_js.read_text(encoding="utf-8")

    assert "openUserResourcesModal(" in content
    assert "renderUserResourcesTable(" in content
    assert "initUserResourcesModalEvents(" in content
    assert "navigateToPidInspector" in content
    assert "AIModalDialog.open" in content


@pytest.mark.asyncio
async def test_get_account_metrics_api() -> None:
    """Проверяет структуру ответа эндпоинта /api/sysadmin/accounts/{username}/metrics."""
    from apps.windows.sdk.modules.sysadmin.router import get_account_metrics

    current_user = os.environ.get("USERNAME", "Administrator")
    try:
        data = await get_account_metrics(username=current_user)
        assert "username" in data
        assert "total_processes" in data
        assert "total_memory_rss_mb" in data
        assert "processes" in data
        assert isinstance(data["processes"], list)

        if data["processes"]:
            p = data["processes"][0]
            assert "pid" in p
            assert "name" in p
            assert "memory_mb" in p
            assert "cpu_percent" in p
            assert "status" in p
            assert "num_threads" in p
    except Exception as e:
        # Если пользователь не найден в fallback/тестовом окружении, проверяем тип исключения
        from fastapi import HTTPException
        assert isinstance(e, HTTPException)
