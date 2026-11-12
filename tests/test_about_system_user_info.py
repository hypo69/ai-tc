# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - About System User Info
# =============================================================================
# Description:
#   Тестирование сбора расширенной информации о пользователе операционной
#   системы Windows (имя, фамилия, должность/описание, SID, профиль, группы).
#
# File: test_about_system_user_info.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 15:33:00
# =============================================================================

from pathlib import Path
import pytest
from fastapi import FastAPI, APIRouter
from fastapi.testclient import TestClient

from apps.windows.api.routers.about_system.helpers import (
    get_current_user_account_info,
    get_windows_language_packs,
)
from apps.windows.api.routers.about_system.query_summary import query_system_summary_full
from apps.windows.api.routers.about_system.endpoints_system import register_system_action_endpoints
from apps.windows.telemetry.sqlite import TelemetryStorage


def test_get_current_user_account_info():
    """Проверка сбора информации о текущем пользователе ОС."""
    info = get_current_user_account_info()
    assert isinstance(info, dict)
    assert "username" in info
    assert len(info["username"]) > 0
    assert "full_name" in info
    assert "description" in info
    assert "sid" in info
    assert "profile_dir" in info
    assert "groups" in info
    assert isinstance(info["groups"], list)
    assert "is_admin" in info
    assert isinstance(info["is_admin"], bool)


@pytest.mark.asyncio
async def test_query_system_summary_full_contains_user():
    """Проверка наличия полной информации о пользователе в снимке сводки системы."""
    storage = TelemetryStorage()
    snap = await query_system_summary_full(storage)
    assert isinstance(snap, dict)
    assert "user" in snap
    user_obj = snap["user"]
    assert isinstance(user_obj, dict)
    assert snap.get("username") == user_obj.get("username")
    assert "user_full_name" in snap
    assert "user_description" in snap
    assert "user_sid" in snap
    assert "user_profile" in snap
    assert "user_groups" in snap


def test_regional_options_endpoint_user_attributes():
    """Проверка возврата расширенных полей пользователя в эндпоинте /api/v1/system/regional-options."""
    app = FastAPI()
    router = APIRouter()
    storage = TelemetryStorage()
    register_system_action_endpoints(router, storage)
    app.include_router(router)

    client = TestClient(app)
    response = client.get("/api/v1/system/regional-options")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "ok"
    assert "current_username" in data
    assert "current_user_fullname" in data
    assert "current_user_description" in data
    assert "current_user_sid" in data
    assert "current_user_profile" in data
    assert "current_user_groups" in data
    assert isinstance(data.get("current_user_groups"), list)


def test_get_windows_language_packs():
    """Проверка сбора языковых пакетов Windows (Русский, Иврит, Английский)."""
    packs = get_windows_language_packs()
    assert isinstance(packs, list)
    assert len(packs) >= 3
    tags = [p["tag"].lower() for p in packs]
    assert "ru-ru" in tags
    assert "he-il" in tags
    assert "en-us" in tags
    for p in packs:
        assert "name" in p
        assert "native_name" in p
        assert "is_installed" in p
        assert "is_active" in p


def test_regional_options_contains_language_packs():
    """Проверка наличия списка language_packs в ответе /api/v1/system/regional-options."""
    app = FastAPI()
    router = APIRouter()
    storage = TelemetryStorage()
    register_system_action_endpoints(router, storage)
    app.include_router(router)

    client = TestClient(app)
    response = client.get("/api/v1/system/regional-options")
    assert response.status_code == 200
    data = response.json()
    assert "language_packs" in data
    assert isinstance(data["language_packs"], list)
    assert len(data["language_packs"]) >= 3


def test_install_language_pack_invalid_tag():
    """Проверка валидации невалидного тэга языка в эндпоинте установки языкового пакета."""
    app = FastAPI()
    router = APIRouter()
    storage = TelemetryStorage()
    register_system_action_endpoints(router, storage)
    app.include_router(router)

    client = TestClient(app)
    response = client.post("/api/v1/system/install-language-pack", json={"tag": "invalid;injection"})
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "error"
    assert "Недопустимый языковой тэг" in data.get("message", "")


def test_about_system_html_contains_full_user_and_network_panel():
    """Проверка наличия переименованной панели 'User Environment, Network, Regional & Security',
    полных атрибутов пользователя (имя, логин, права, должность, профиль, SID, группы)
    и сетевых элементов (профиль, обнаружение, модалка pane-net)."""
    html_path = Path("apps/windows/api/webgui/tab_about_system/index.html")
    assert html_path.exists()
    content = html_path.read_text(encoding="utf-8")

    # 1. Проверка заголовка и комментария панели
    assert "<!-- User Environment, Network, Regional & Security -->" in content
    assert "Окружение пользователя, сеть и безопасность" in content

    # 2. Проверка полных полей информации о пользователе
    assert 'id="about-ident-fullname"' in content
    assert 'id="about-ident-username"' in content
    assert 'id="about-ident-privilege-badge"' in content
    assert 'id="about-ident-privilege"' in content
    assert 'id="about-ident-job-badge"' in content
    assert 'id="about-ident-job-title"' in content
    assert 'id="about-ident-user-profile"' in content
    assert 'id="about-ident-user-sid-box"' in content
    assert 'id="about-ident-user-sid"' in content
    assert 'id="about-ident-user-groups-chips"' in content

    # 3. Проверка сетевых элементов
    assert 'id="about-net-category-badge"' in content
    assert 'id="about-net-iface-name"' in content
    assert 'id="btn-net-profile-private"' in content
    assert 'id="btn-net-profile-public"' in content
    assert 'id="about-net-discovery-pill"' in content
    assert 'id="btn-net-discovery-on"' in content
    assert 'id="btn-net-discovery-off"' in content

    # 4. Проверка модального окна региона и сети
    assert 'id="btn-tab-net"' in content
    assert 'id="pane-net"' in content
    assert 'id="reg-net-host-input"' in content
    assert 'id="btn-reg-save-host"' in content
    assert 'id="reg-net-wg-input"' in content
    assert 'id="btn-reg-save-wg"' in content
    assert 'id="btn-modal-net-private"' in content
    assert 'id="btn-modal-net-public"' in content
    assert 'id="btn-reg-toggle-discovery"' in content
    assert 'id="reg-usr-sid-badge"' in content
    assert 'id="reg-usr-profile-badge"' in content
    assert 'id="reg-usr-groups-badge"' in content


def test_about_system_html_contains_password_policy_and_reset_pane():
    """Проверка наличия элементов политики паролей и смены пароля в модальном окне (pane-usr)."""
    html_path = Path("apps/windows/api/webgui/tab_about_system/index.html")
    assert html_path.exists()
    content = html_path.read_text(encoding="utf-8")

    # 1. Информационные бейджи состояния пароля
    assert 'id="reg-usr-pwd-lastset"' in content
    assert 'id="reg-usr-pwd-expires"' in content
    assert 'id="reg-usr-pwd-badcount"' in content

    # 2. Переключатели политики пароля пользователя
    assert 'id="reg-usr-pwd-never-expires"' in content
    assert 'id="reg-usr-pwd-cannot-change"' in content
    assert 'id="reg-usr-pwd-required"' in content

    # 3. Поля смены пароля
    assert 'id="reg-usr-new-pwd"' in content
    assert 'id="reg-usr-confirm-pwd"' in content
    assert 'id="btn-toggle-new-pwd"' in content
    assert 'id="btn-toggle-confirm-pwd"' in content
    assert 'id="btn-reg-change-pwd"' in content

    # 4. Глобальная политика паролей SAM
    assert 'id="reg-pol-min-len"' in content
    assert 'id="reg-pol-max-age"' in content
    assert 'id="reg-pol-lockout"' in content
    assert 'id="btn-reg-save-policy"' in content


def test_regional_options_endpoint_password_policy_attributes():
    """Проверка возврата параметров политики паролей в эндпоинте /api/v1/system/regional-options."""
    app = FastAPI()
    router = APIRouter()
    storage = TelemetryStorage()
    register_system_action_endpoints(router, storage)
    app.include_router(router)

    client = TestClient(app)
    response = client.get("/api/v1/system/regional-options")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "ok"
    assert "password_required" in data
    assert "password_never_expires" in data
    assert "cannot_change_password" in data
    assert "min_password_length" in data
    assert "max_password_age_days" in data
    assert "lockout_threshold" in data


def test_change_user_password_endpoint_validation():
    """Проверка валидации эндпоинта смены пароля пользователя."""
    app = FastAPI()
    router = APIRouter()
    storage = TelemetryStorage()
    register_system_action_endpoints(router, storage)
    app.include_router(router)

    client = TestClient(app)
    # 1. Пустой пароль
    resp = client.post("/api/v1/system/change-user-password", json={"username": "testuser", "new_password": ""})
    # Pydantic validation error or endpoint error
    assert resp.status_code in (200, 422)
    if resp.status_code == 200:
        assert resp.json().get("status") == "error"

    # 2. Недопустимое имя пользователя
    resp2 = client.post("/api/v1/system/change-user-password", json={"username": "bad;user|inject", "new_password": "ValidPassword123!"})
    assert resp2.status_code == 200
    assert resp2.json().get("status") == "error"
    assert "Недопустимое имя" in resp2.json().get("message", "")


def test_set_password_policy_endpoint(monkeypatch):
    """Проверка эндпоинта настройки глобальной политики паролей."""
    app = FastAPI()
    router = APIRouter()
    storage = TelemetryStorage()
    register_system_action_endpoints(router, storage)
    app.include_router(router)

    from apps.windows.api.routers.about_system import endpoints_system
    monkeypatch.setattr(endpoints_system, "set_password_policy_helper", lambda min_len, max_age, lockout: {"status": "ok", "message": "Политика обновлена"})

    client = TestClient(app)
    resp = client.post("/api/v1/system/set-password-policy", json={"min_password_length": 8, "max_password_age_days": 60, "lockout_threshold": 5})
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "ok"
    assert "Политика обновлена" in data.get("message", "")




