# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Tests - SAM Password & Security Policy
# =============================================================================
# Description:
#   Юнит-тесты для подсистемы AuthPolicySubsystem (чтение и редактирование
#   полной политики безопасности Windows SAM через secedit и net accounts)
#   и REST API эндпоинтов /identity/auth/policies.
#
# File: test_sam_password_policy.py
# Project: ai-tc
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20 15:33:00
# =============================================================================

"""Тесты полной политики безопасности Windows SAM (PasswordPolicy и API)."""

from __future__ import annotations

import os
from typing import List, Tuple
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.windows.sdk.modules.accounts_identity.models import (
    PasswordPolicy,
    PasswordPolicyUpdateRequest,
)
from apps.windows.sdk.modules.accounts_identity.router import router as identity_router
from apps.windows.sdk.modules.accounts_identity.subsystems.subsystem_05_auth import (
    AuthPolicySubsystem,
)


class _FakeBridge:
    """Мок-мост Win32IdentityBridge для детерминированного тестирования SAM."""

    def __init__(
        self,
        secedit_export_text: str = "",
        secedit_export_ret: int = 0,
        secedit_configure_ret: int = 0,
        net_accounts_out: str = "",
    ) -> None:
        self.secedit_export_text = secedit_export_text
        self.secedit_export_ret = secedit_export_ret
        self.secedit_configure_ret = secedit_configure_ret
        self.net_accounts_out = net_accounts_out
        self.captured_inf_content: str = ""
        self.commands: List[List[str]] = []

    def run_command(self, args: List[str]) -> Tuple[int, str, str]:
        self.commands.append(args)
        if args[:2] == ["secedit", "/export"]:
            if self.secedit_export_ret == 0:
                cfg_idx = args.index("/cfg") + 1
                with open(args[cfg_idx], "w", encoding="utf-16") as f:
                    f.write(self.secedit_export_text)
            return self.secedit_export_ret, "", ""
        if args[:2] == ["secedit", "/configure"]:
            cfg_idx = args.index("/cfg") + 1
            if os.path.exists(args[cfg_idx]):
                with open(args[cfg_idx], "r", encoding="utf-16") as f:
                    self.captured_inf_content = f.read()
            err = "" if self.secedit_configure_ret == 0 else "Access denied"
            return self.secedit_configure_ret, "", err
        if args[:2] == ["net", "accounts"]:
            return 0, self.net_accounts_out, ""
        return 0, "", ""


SAMPLE_SECEDIT_INF = """[Unicode]
Unicode=yes
[System Access]
MinimumPasswordAge = 2
MaximumPasswordAge = -1
MinimumPasswordLength = 12
PasswordComplexity = 1
PasswordHistorySize = 5
LockoutBadCount = 4
ResetLockoutCount = 15
LockoutDuration = -1
AllowAdministratorLockout = 1
RequireLogonToChangePassword = 1
ForceLogoffWhenHourExpire = 1
NewAdministratorName = "SysAdmin"
NewGuestName = "Visitor"
ClearTextPassword = 1
LSAAnonymousNameLookup = 1
EnableAdminAccount = 1
EnableGuestAccount = 0
[Version]
signature="$CHICAGO$"
Revision=1
"""

SAMPLE_NET_ACCOUNTS = """Force user logoff how long after time expires?:       Never
Minimum password age (days):                          0
Maximum password age (days):                          UNLIMITED
Minimum password length:                              8
Length of password history maintained:                None
Lockout threshold:                                    Never
Lockout duration (minutes):                           30
Lockout observation window (minutes):                 30
Computer role:                                        WORKSTATION
"""


def test_get_password_policy_parses_all_secedit_fields() -> None:
    """Проверяет полный разбор всех 17 параметров SAM из secedit и роли компьютера."""
    bridge = _FakeBridge(
        secedit_export_text=SAMPLE_SECEDIT_INF,
        net_accounts_out=SAMPLE_NET_ACCOUNTS,
    )
    subsys = AuthPolicySubsystem(bridge=bridge)
    pol = subsys.get_password_policy()

    assert pol.min_password_length == 12
    assert pol.max_password_age_days == 0  # -1 нормализуется в 0 (бессрочно)
    assert pol.min_password_age_days == 2
    assert pol.password_history_length == 5
    assert pol.password_complexity is True
    assert pol.reversible_encryption is True

    assert pol.lockout_threshold == 4
    assert pol.lockout_duration_minutes == 0  # -1 нормализуется в 0 (до админа)
    assert pol.lockout_window_minutes == 15
    assert pol.allow_admin_lockout is True

    assert pol.force_logoff_when_hour_expire is True
    assert pol.require_logon_to_change_password is True
    assert pol.lsa_anonymous_name_lookup is True
    assert pol.enable_admin_account is True
    assert pol.enable_guest_account is False
    assert pol.new_admin_name == "SysAdmin"
    assert pol.new_guest_name == "Visitor"
    assert pol.computer_role == "WORKSTATION"


def test_get_password_policy_fallback_to_net_accounts() -> None:
    """Проверяет fallback-парсинг net accounts при недоступности secedit."""
    bridge = _FakeBridge(
        secedit_export_ret=5,
        net_accounts_out=SAMPLE_NET_ACCOUNTS,
    )
    subsys = AuthPolicySubsystem(bridge=bridge)
    pol = subsys.get_password_policy()

    assert pol.min_password_length == 8
    assert pol.max_password_age_days == 0  # UNLIMITED -> 0
    assert pol.password_history_length == 0  # None -> 0
    assert pol.lockout_threshold == 0  # Never -> 0
    assert pol.computer_role == "WORKSTATION"


def test_update_password_policy_generates_valid_inf_and_maps_unlimited() -> None:
    """Проверяет генерацию INF и маппинг 0 -> -1 для бессрочных параметров."""
    bridge = _FakeBridge(
        secedit_export_text=SAMPLE_SECEDIT_INF,
        net_accounts_out=SAMPLE_NET_ACCOUNTS,
    )
    subsys = AuthPolicySubsystem(bridge=bridge)
    req = PasswordPolicyUpdateRequest(
        min_password_length=10,
        max_password_age_days=0,
        password_complexity=True,
        lockout_threshold=5,
        lockout_duration_minutes=0,
        lockout_window_minutes=15,
        allow_admin_lockout=False,
        new_admin_name="LocalAdmin",
    )
    ok, msg, _ = subsys.update_password_policy(req)

    assert ok is True
    assert "успешно" in msg.lower()
    inf = bridge.captured_inf_content
    assert "MinimumPasswordLength = 10" in inf
    assert "MaximumPasswordAge = -1" in inf
    assert "PasswordComplexity = 1" in inf
    assert "LockoutBadCount = 5" in inf
    assert "LockoutDuration = -1" in inf
    assert "ResetLockoutCount = 15" in inf
    assert "AllowAdministratorLockout = 0" in inf
    assert 'NewAdministratorName = "LocalAdmin"' in inf


def test_update_password_policy_validates_age_and_lockout_constraints() -> None:
    """Проверяет валидацию взаимозависимостей сроков пароля, блокировки и имен."""
    bridge = _FakeBridge(
        secedit_export_text=SAMPLE_SECEDIT_INF,
        net_accounts_out=SAMPLE_NET_ACCOUNTS,
    )
    subsys = AuthPolicySubsystem(bridge=bridge)

    with pytest.raises(ValueError, match="Минимальный срок действия пароля"):
        subsys.update_password_policy(
            PasswordPolicyUpdateRequest(min_password_age_days=30, max_password_age_days=30)
        )

    with pytest.raises(ValueError, match="Окно сброса блокировки"):
        subsys.update_password_policy(
            PasswordPolicyUpdateRequest(
                lockout_threshold=5,
                lockout_duration_minutes=10,
                lockout_window_minutes=20,
            )
        )

    with pytest.raises(ValueError, match="недопустимые символы"):
        subsys.update_password_policy(PasswordPolicyUpdateRequest(new_admin_name='Bad"Name'))


def test_router_auth_policies_get_and_put() -> None:
    """Проверяет REST API GET и PUT /identity/auth/policies."""
    app = FastAPI()
    app.include_router(identity_router)
    client = TestClient(app)

    fake_policy = PasswordPolicy(
        min_password_length=10,
        max_password_age_days=60,
        password_complexity=True,
        lockout_threshold=5,
        lockout_duration_minutes=15,
        lockout_window_minutes=10,
        computer_role="WORKSTATION",
    )

    with patch("apps.windows.sdk.modules.accounts_identity.router._service") as mock_srv:
        mock_srv.get_password_policy.return_value = fake_policy
        mock_srv.update_password_policy.return_value = (True, "Политика обновлена", fake_policy)

        r_get = client.get("/identity/auth/policies")
        assert r_get.status_code == 200
        data_get = r_get.json()
        assert data_get["min_password_length"] == 10
        assert data_get["password_complexity"] is True
        assert data_get["computer_role"] == "WORKSTATION"

        r_put = client.put("/identity/auth/policies", json={"min_password_length": 10, "password_complexity": True})
        assert r_put.status_code == 200
        assert r_put.json()["status"] == "ok"
        assert r_put.json()["policy"]["min_password_length"] == 10

        mock_srv.update_password_policy.side_effect = ValueError("Некорректный диапазон")
        r_bad = client.put("/identity/auth/policies", json={"min_password_age_days": 50, "max_password_age_days": 10})
        assert r_bad.status_code == 400

        mock_srv.update_password_policy.side_effect = None
        mock_srv.update_password_policy.return_value = (False, "Требуются права администратора", fake_policy)
        r_forbid = client.put("/identity/auth/policies", json={"min_password_length": 12})
        assert r_forbid.status_code == 403
