# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Settings Catalog, Resolver & Commands
# =============================================================================
# Description:
#   Комплексные тесты декларативного каталога настроек Windows Control Catalog,
#   резолвера версионной совместимости SettingsResolver, модуля верификации,
#   исполнителя WindowsSettingsExecutor и REST API эндпоинтов /api/v1/settings/*.
#
# File: test_settings_catalog.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 13:06:00
# =============================================================================

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from apps.windows.api.server import create_app
from apps.windows.sdk.settings.catalog import WINDOWS_SETTINGS, get_settings_catalog
from apps.windows.sdk.settings.resolver import SettingsResolver
from apps.windows.sdk.settings.verification import SettingsVerification
from apps.windows.commands.windows_settings import WindowsSettingsExecutor


@pytest.fixture(scope="module")
def api_client() -> TestClient:
    """Фикстура тестового клиента API."""
    app = create_app()
    return TestClient(app)


def test_settings_catalog_definitions() -> None:
    """Проверяет полноту и корректность определений декларативного каталога."""
    catalog = get_settings_catalog()
    assert "MONITOR.ROTATE" in catalog
    assert "TASKBAR.SET_ALIGNMENT" in catalog
    assert "TASKBAR.SET_POSITION" in catalog
    assert "TASKBAR.SET_AUTOHIDE" in catalog

    mon_rotate = catalog["MONITOR.ROTATE"]
    assert mon_rotate.category == "Display"
    assert mon_rotate.backend == "display_config"
    assert mon_rotate.scope == "monitor"
    assert "landscape" in mon_rotate.values
    assert "portrait" in mon_rotate.values

    tb_align = catalog["TASKBAR.SET_ALIGNMENT"]
    assert tb_align.category == "Taskbar"
    assert tb_align.values == ["left", "center"]

    tb_pos = catalog["TASKBAR.SET_POSITION"]
    assert tb_pos.category == "Taskbar"
    assert tb_pos.capability == "version_dependent"
    assert "bottom" in tb_pos.values


def test_settings_resolver_compatibility_checks() -> None:
    """Проверяет логику резолва версионной совместимости с текущей ОС."""
    resolver = SettingsResolver()

    # 1. Поворот экрана поддерживается везде
    res_rotate = resolver.resolve("MONITOR.ROTATE")
    assert res_rotate.status == "supported"
    assert res_rotate.is_supported is True
    assert res_rotate.recommended_backend == "display_config"

    # 2. Выравнивание значков панели задач
    res_align = resolver.resolve("TASKBAR.SET_ALIGNMENT")
    if resolver.is_win11:
        assert res_align.status == "supported"
        assert res_align.is_supported is True
    else:
        assert res_align.status == "unsupported"
        assert res_align.is_supported is False

    # 3. Расположение панели задач
    res_pos = resolver.resolve("TASKBAR.SET_POSITION")
    if resolver.is_win11:
        assert res_pos.status == "version_dependent"
    else:
        assert res_pos.status == "supported"

    # 4. Несуществующая команда
    res_unknown = resolver.resolve("NON_EXISTENT_CMD")
    assert res_unknown.status == "unsupported"
    assert res_unknown.is_supported is False


def test_settings_verification_module() -> None:
    """Проверяет считывание текущего состояния и верификацию параметров."""
    verifier = SettingsVerification()

    align_state = verifier.get_current_state("TASKBAR.SET_ALIGNMENT")
    assert align_state in ("left", "center")

    pos_state = verifier.get_current_state("TASKBAR.SET_POSITION")
    assert pos_state in ("bottom", "top", "left", "right")

    autohide_state = verifier.get_current_state("TASKBAR.SET_AUTOHIDE")
    assert isinstance(autohide_state, bool)

    assert verifier.supports_rollback("MONITOR.ROTATE") is True
    assert verifier.supports_rollback("TASKBAR.SET_POSITION") is True


def test_windows_settings_executor_contracts_and_validation() -> None:
    """Проверяет валидацию параметров и единый контракт выполнения команд."""
    executor = WindowsSettingsExecutor()

    # Валидация некорректных параметров (Fail-Fast)
    invalid_res = executor.execute("MONITOR.ROTATE", {"orientation": "upside_down_unknown"})
    assert invalid_res.success is False
    assert invalid_res.error is not None
    assert "Недопустимое значение ориентации" in invalid_res.error

    # Проверка контракта структуры результата
    assert hasattr(invalid_res, "command")
    assert hasattr(invalid_res, "requested")
    assert hasattr(invalid_res, "actual")
    assert hasattr(invalid_res, "rollback_supported")


def test_rest_api_settings_catalog_endpoint(api_client: TestClient) -> None:
    """Проверяет REST API эндпоинт каталога настроек /api/v1/settings/catalog."""
    resp = api_client.get("/api/v1/settings/catalog")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "success"
    assert data.get("total") >= 4
    items = data.get("items", [])
    rotate_item = next((i for i in items if i.get("id") == "MONITOR.ROTATE"), None)
    assert rotate_item is not None
    assert rotate_item.get("status") == "supported"


def test_rest_api_displays_endpoint(api_client: TestClient) -> None:
    """Проверяет REST API эндпоинт списка мониторов /api/v1/settings/displays."""
    resp = api_client.get("/api/v1/settings/displays")
    assert resp.status_code == 200
    displays = resp.json()
    assert isinstance(displays, list)


def test_rest_api_taskbar_state_endpoint(api_client: TestClient) -> None:
    """Проверяет REST API эндпоинт параметров панели задач /api/v1/settings/taskbar."""
    resp = api_client.get("/api/v1/settings/taskbar")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "success"
    state = data.get("state", {})
    assert "position" in state
    assert "alignment_label" in state


def test_rest_api_execute_endpoint_contract(api_client: TestClient) -> None:
    """Проверяет единый контракт эндпоинта /api/v1/settings/execute."""
    resp = api_client.post(
        "/api/v1/settings/execute",
        json={"command": "TASKBAR.SET_AUTOHIDE", "params": {"enabled": False}},
    )
    assert resp.status_code == 200
    res = resp.json()
    assert "success" in res
    assert "command" in res
    assert "requested" in res
    assert "actual" in res
    assert res.get("command") == "TASKBAR.SET_AUTOHIDE"

