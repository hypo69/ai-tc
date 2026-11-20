# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Tests - Network Remote Access Settings
# =============================================================================
# Description:
#   Модульные тесты диагностики и настройки входящего удалённого доступа Windows
#   (SMB 445, WinRM 5985, сетевой профиль Private, UAC Remote Restrictions)
#   и API-эндпоинтов /api/v1/network/remote-access/status и /apply.
#
# File: test_network_remote_access.py
# Project: ai-tc
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20 20:51:00
# =============================================================================

from __future__ import annotations

from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.windows.sdk.modules.network.remote_access_settings import (
    RemoteAccessActionResult,
    RemoteAccessStatus,
    RemoteAccessStepResult,
    WindowsRemoteAccessManager,
)
from apps.windows.sdk.modules.network.router import router as network_router


def test_get_status_computes_readiness() -> None:
    """Проверяет расчёт готовности SMB 445, WinRM 5985 и определение профиля Public."""
    mgr = WindowsRemoteAccessManager()
    snapshot = {
        'network_profiles': [
            {'name': 'Wi-Fi', 'interface_alias': 'Wi-Fi', 'interface_index': 7, 'category': 'Public'},
        ],
        'smb_service': {'name': 'LanmanServer', 'status': 'Running', 'start_type': 'Automatic', 'running': True},
        'winrm_service': {'name': 'WinRM', 'status': 'Stopped', 'start_type': 'Manual', 'running': False},
        'smb_firewall_enabled': True,
        'winrm_firewall_enabled': False,
    }
    with patch.object(mgr, '_query_system_snapshot', return_value=snapshot), \
         patch.object(mgr, 'is_admin', return_value=True), \
         patch.object(mgr, 'is_local_port_listening', side_effect=lambda p: p == 445), \
         patch.object(mgr, 'read_uac_remote_allowed', return_value=True):
        status = mgr.get_status()

    assert status.is_admin is True
    assert status.has_public_profile is True
    assert status.ready_for_smb is True
    assert status.ready_for_winrm is False
    assert status.uac_remote_allowed is True


def test_apply_action_requires_admin() -> None:
    """Проверяет Fail-Fast при отсутствии прав администратора."""
    mgr = WindowsRemoteAccessManager()
    dummy_status = RemoteAccessStatus(is_admin=False, hostname='TEST-PC')
    with patch.object(mgr, 'is_admin', return_value=False), \
         patch.object(mgr, 'get_status', return_value=dummy_status):
        res = mgr.apply_action('enable_all')

    assert res.success is False
    assert res.requires_admin is True
    assert res.steps == []


def test_apply_enable_all_executes_all_steps() -> None:
    """Проверяет выполнение всех 6 шагов комплексного включения SMB 445 + WinRM 5985."""
    mgr = WindowsRemoteAccessManager()
    ok_step = RemoteAccessStepResult(step='ok', success=True, message='done')
    ready_status = RemoteAccessStatus(
        is_admin=True,
        hostname='TEST-PC',
        port_445_listening=True,
        port_5985_listening=True,
        smb_firewall_enabled=True,
        winrm_firewall_enabled=True,
        uac_remote_allowed=True,
        ready_for_smb=True,
        ready_for_winrm=True,
    )
    with patch.object(mgr, 'is_admin', return_value=True), \
         patch.object(mgr, '_set_private_profile', return_value=ok_step) as m_prof, \
         patch.object(mgr, '_set_smb_service', return_value=ok_step) as m_smb_s, \
         patch.object(mgr, '_set_smb_firewall', return_value=ok_step) as m_smb_f, \
         patch.object(mgr, '_set_winrm_service', return_value=ok_step) as m_wrm_s, \
         patch.object(mgr, '_set_winrm_firewall', return_value=ok_step) as m_wrm_f, \
         patch.object(mgr, '_set_uac_remote_allowed', return_value=ok_step) as m_uac, \
         patch.object(mgr, 'get_status', return_value=ready_status):
        res = mgr.apply_action('enable_all')

    assert res.success is True
    assert len(res.steps) == 6
    m_prof.assert_called_once()
    m_smb_s.assert_called_once_with(True)
    m_smb_f.assert_called_once_with(True)
    m_wrm_s.assert_called_once_with(True)
    m_wrm_f.assert_called_once_with(True)
    m_uac.assert_called_once_with(True)


def test_api_remote_access_endpoints() -> None:
    """Проверяет FastAPI-эндпоинты GET /status и POST /apply."""
    app = FastAPI()
    app.include_router(network_router)
    client = TestClient(app)

    mock_status = RemoteAccessStatus(
        is_admin=True,
        hostname='DESKTOP-TEST',
        port_445_listening=True,
        smb_firewall_enabled=True,
        ready_for_smb=True,
    )
    mock_result = RemoteAccessActionResult(
        success=True,
        action='enable_smb_firewall',
        message='Входящий порт SMB (TCP 445) открыт в брандмауэре',
        steps=[RemoteAccessStepResult(step='Брандмауэр SMB (TCP 445)', success=True, message='OK')],
        status=mock_status,
    )

    with patch('apps.windows.sdk.modules.network.router._remote_access.get_status', return_value=mock_status), \
         patch('apps.windows.sdk.modules.network.router._remote_access.apply_action', return_value=mock_result):
        r_status = client.get('/api/v1/network/remote-access/status')
        assert r_status.status_code == 200
        assert r_status.json()['ready_for_smb'] is True

        r_apply = client.post('/api/v1/network/remote-access/apply', json={'action': 'enable_smb_firewall'})
        assert r_apply.status_code == 200
        body = r_apply.json()
        assert body['success'] is True
        assert body['action'] == 'enable_smb_firewall'

        r_bad = client.post('/api/v1/network/remote-access/apply', json={'action': 'invalid_action'})
        assert r_bad.status_code == 422
