# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Tests - Network Remote Auth
# =============================================================================
# Description:
#   Модульные тесты аутентификации на удалённых компьютерах в локальной сети
#   (SMB / WinRM) и API-эндпоинта POST /api/v1/network/devices/login.
#
# File: test_network_remote_auth.py
# Project: ai-tc
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20 17:20:00
# =============================================================================

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.windows.sdk.modules.network.remote_auth import (
    RemoteLoginResult,
    WindowsRemoteAuthenticator,
)
from apps.windows.sdk.modules.network.router import router as network_router


def test_validate_ip_valid_and_invalid() -> None:
    """Проверяет валидацию IP-адреса и защиту от инъекций."""
    assert WindowsRemoteAuthenticator.validate_ip(' 10.0.0.15 ') == '10.0.0.15'
    with pytest.raises(ValueError):
        WindowsRemoteAuthenticator.validate_ip('10.0.0.15; whoami')
    with pytest.raises(ValueError):
        WindowsRemoteAuthenticator.validate_ip('not-an-ip')


def test_authenticate_smb_success_with_shares() -> None:
    """Проверяет успешный вход по SMB и перечисление общих папок."""
    auth = WindowsRemoteAuthenticator()
    with patch.object(auth, 'is_port_open', return_value=True), \
         patch.object(auth, '_wnet_add_connection', return_value=0) as mock_add, \
         patch.object(auth, '_enum_remote_shares', return_value=['Users', 'Public', 'IPC$']):
        res = auth.authenticate('10.0.0.20', 'Administrator', 'secret123', protocol='smb')

    assert res.success is True
    assert res.protocol_used == 'smb'
    assert res.error_code == 0
    assert res.details['shares'] == ['Users', 'Public', 'IPC$']
    assert res.details['shares_count'] == 3
    mock_add.assert_called_once_with('\\\\10.0.0.20\\IPC$', '10.0.0.20\\Administrator', 'secret123')


def test_authenticate_smb_conflict_retry() -> None:
    """Проверяет сброс конфликтующей сессии (код 1219) и повторный вход."""
    auth = WindowsRemoteAuthenticator()
    with patch.object(auth, 'is_port_open', return_value=True), \
         patch.object(auth, '_wnet_add_connection', side_effect=[1219, 0]) as mock_add, \
         patch.object(auth, '_wnet_cancel_connection', return_value=0) as mock_cancel, \
         patch.object(auth, '_enum_remote_shares', return_value=[]):
        res = auth.authenticate('10.0.0.21', 'DOMAIN\\admin', 'pass', protocol='smb')

    assert res.success is True
    assert mock_cancel.call_count == 1
    assert mock_add.call_count == 2


def test_authenticate_smb_wrong_password_stops_auto() -> None:
    """Проверяет, что ошибка 1326 (неверный пароль) возвращается сразу без скрытия."""
    auth = WindowsRemoteAuthenticator()
    with patch.object(auth, 'is_port_open', return_value=True), \
         patch.object(auth, '_wnet_add_connection', return_value=1326), \
         patch.object(auth, 'authenticate_winrm') as mock_winrm:
        res = auth.authenticate('10.0.0.22', 'user', 'wrong', protocol='auto')

    assert res.success is False
    assert res.error_code == 1326
    assert 'Неверное имя пользователя или пароль' in res.message
    mock_winrm.assert_not_called()


def test_authenticate_auto_fallback_to_winrm() -> None:
    """Проверяет автоматический переход на WinRM, если порт SMB 445 закрыт."""
    auth = WindowsRemoteAuthenticator()
    fake_winrm = RemoteLoginResult(
        success=True,
        ip='10.0.0.23',
        username='admin',
        protocol_used='winrm',
        message='Успешный вход через WinRM',
        error_code=0,
        latency_ms=42.0,
        details={'computer': 'OFFICE-PC', 'user': 'admin'},
    )
    with patch.object(auth, 'is_port_open', return_value=False), \
         patch.object(auth, 'authenticate_winrm', return_value=fake_winrm) as mock_winrm:
        res = auth.authenticate('10.0.0.23', 'admin', 'pass', protocol='auto')

    assert res.success is True
    assert res.protocol_used == 'winrm'
    assert res.details['computer'] == 'OFFICE-PC'
    mock_winrm.assert_called_once()


def test_api_devices_login_endpoint() -> None:
    """Проверяет HTTP-эндпоинт POST /api/v1/network/devices/login."""
    app = FastAPI()
    app.include_router(network_router)
    client = TestClient(app)

    fake_res = RemoteLoginResult(
        success=True,
        ip='10.0.0.25',
        username='admin',
        protocol_used='smb',
        message='Успешный вход на 10.0.0.25 по протоколу SMB (IPC$)',
        error_code=0,
        latency_ms=12.5,
        details={'shares': ['C$'], 'shares_count': 1},
    )

    with patch('apps.windows.sdk.modules.network.router._remote_auth.authenticate', return_value=fake_res), \
         patch('apps.windows.sdk.modules.network.router._telemetry_logger.log_event', new=MagicMock()):
        resp = client.post(
            '/api/v1/network/devices/login',
            json={'ip': '10.0.0.25', 'username': 'admin', 'password': 'secret', 'protocol': 'auto'},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body['success'] is True
    assert body['protocol_used'] == 'smb'
    assert body['details']['shares'] == ['C$']


def test_api_devices_login_invalid_ip_returns_400() -> None:
    """Проверяет возврат HTTP 400 при передаче невалидного IP-адреса."""
    app = FastAPI()
    app.include_router(network_router)
    client = TestClient(app)

    resp = client.post(
        '/api/v1/network/devices/login',
        json={'ip': 'bad-ip; calc', 'username': 'admin', 'password': 'secret', 'protocol': 'auto'},
    )
    assert resp.status_code == 400
