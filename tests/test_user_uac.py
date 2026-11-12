# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - User UAC Configuration Tests
# =============================================================================
# Description:
#   Модульные тесты проверки подсистемы конфигурации UAC (User Account Control)
#   для локальных пользователей Windows (Admin Approval Mode, SAM-флаги, реестр).
#
# Usage Examples:
#   pytest tests/test_user_uac.py -v
#
# File: test_user_uac.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 13:55:00
# =============================================================================

"""Модульные тесты для проверки функционала настройки UAC пользователей."""

import pytest
from unittest.mock import MagicMock, patch

from apps.windows.sdk.modules.accounts_identity.models import (
    AccountDetails,
    UserUacConfig,
    UserUacUpdateRequest,
)
from apps.windows.sdk.modules.accounts_identity.subsystems.subsystem_02_users import UsersSubsystem


def test_user_uac_models_validation():
    """Проверка валидации моделей UserUacConfig и UserUacUpdateRequest."""
    cfg = UserUacConfig(
        username="test_admin",
        sid="S-1-5-21-12345-500",
        is_admin=True,
        uac_role="admin",
        is_builtin_admin=True,
        filter_admin_token=True,
        enable_lua=True,
        consent_prompt_behavior_admin=5,
        consent_prompt_behavior_user=3,
        prompt_on_secure_desktop=True,
        enable_virtualization=True,
        enabled=True,
        password_never_expires=False,
        cannot_change_password=False,
        password_required=True,
        groups=["Administrators", "Users"],
    )
    assert cfg.username == "test_admin"
    assert cfg.is_admin is True
    assert cfg.uac_role == "admin"
    assert cfg.filter_admin_token is True

    update_req = UserUacUpdateRequest(
        uac_role="standard",
        consent_prompt_behavior_admin=2,
        prompt_on_secure_desktop=True,
        password_never_expires=True,
    )
    assert update_req.uac_role == "standard"
    assert update_req.consent_prompt_behavior_admin == 2
    assert update_req.password_never_expires is True


def test_get_user_uac_not_found():
    """Проверка возврата None при запросе UAC для несуществующего пользователя."""
    mock_bridge = MagicMock()
    mock_bridge.run_powershell_json.return_value = []
    mock_bridge.run_command.return_value = (0, "", "")

    subsys = UsersSubsystem(bridge=mock_bridge)
    with patch.object(subsys, "get_user_info", return_value=None):
        res = subsys.get_user_uac("non_existent_user_99999")
        assert res is None


def test_get_user_uac_success():
    """Проверка успешного формирования конфигурации UAC для пользователя."""
    mock_bridge = MagicMock()
    subsys = UsersSubsystem(bridge=mock_bridge)

    fake_user = AccountDetails(
        name="onela",
        sid="S-1-5-21-3883612645-4145461085-1751314526-1001",
        full_name="Onela Administrator",
        description="Local Admin Account",
        enabled=True,
        password_required=True,
        password_never_expires=False,
        cannot_change_password=False,
    )

    with patch.object(subsys, "get_user_info", return_value=fake_user):
        mock_bridge.run_powershell_json.return_value = ["Administrators", "Users"]
        res = subsys.get_user_uac("onela")

        assert res is not None
        assert res.username == "onela"
        assert res.is_admin is True
        assert res.uac_role == "admin"
        assert res.is_builtin_admin is False
        assert res.enabled is True
        assert "Administrators" in res.groups


def test_update_user_uac_flow():
    """Проверка применения параметров UAC через UsersSubsystem."""
    mock_bridge = MagicMock()
    mock_bridge.run_command.return_value = (0, "Success", "")
    mock_bridge.run_powershell_json.return_value = "Administrators"

    subsys = UsersSubsystem(bridge=mock_bridge)

    fake_user = AccountDetails(
        name="test_user",
        sid="S-1-5-21-1111-2222-3333-1005",
        enabled=True,
    )

    req = UserUacUpdateRequest(
        uac_role="admin",
        enabled=True,
        password_never_expires=True,
        cannot_change_password=False,
        password_required=True,
    )

    with patch.object(subsys, "get_user_info", return_value=fake_user), \
         patch.object(subsys, "enable_user") as mock_enable, \
         patch.object(subsys, "set_password_never_expires") as mock_never_exp, \
         patch.object(subsys, "set_cannot_change_password") as mock_cannot_chg, \
         patch.object(subsys, "get_user_uac") as mock_get_uac:

        mock_get_uac.return_value = UserUacConfig(
            username="test_user",
            sid=fake_user.sid,
            is_admin=True,
            uac_role="admin",
            password_never_expires=True,
        )

        res = subsys.update_user_uac("test_user", req)

        assert res.username == "test_user"
        assert res.uac_role == "admin"
        assert mock_enable.called
        assert mock_never_exp.called
        assert mock_cannot_chg.called
