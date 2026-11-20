# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Tests - Network SMB Sharing & LAN Visibility Diagnostics
# =============================================================================
# Description:
#   Модульные и API-тесты для WindowsSmbSharingManager, расширенного
#   NetworkDiscoveryManager (4 службы) и 4-уровневой диагностики видимости ПК
#   в локальной сети (LanVisibilityDiagnostics + Rollback).
#
# File: test_network_smb_visibility.py
# Project: ai-tc
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20 21:58:00
# =============================================================================

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.windows.sdk.modules.network import router as net_router_mod
from apps.windows.sdk.modules.network.discovery import NetworkDiscoveryManager
from apps.windows.sdk.modules.network.lan_visibility_diagnostics import LanVisibilityDiagnostics
from apps.windows.sdk.modules.network.smb_sharing import (
    SmbCreateShareRequest,
    WindowsSmbSharingManager,
)


def _make_smb_snapshot_json(
    *,
    smb1: bool = False,
    smb2: bool = True,
    server_running: bool = True,
    workstation_running: bool = True,
    fw_enabled: bool = True,
    include_user_share: bool = True,
) -> str:
    """Формирует мок-ответ PowerShell для WindowsSmbSharingManager.get_status()."""
    shares = [
        {'name': 'IPC$', 'path': '', 'description': 'Remote IPC', 'scope_name': '*', 'special': True},
        {'name': 'C$', 'path': 'C:\\', 'description': 'Default share', 'scope_name': '*', 'special': True},
    ]
    if include_user_share:
        shares.append(
            {'name': 'PublicDocs', 'path': 'D:\\PublicDocs', 'description': 'Документы', 'scope_name': '*', 'special': False}
        )
    payload = {
        'server_config': {
            'available': True,
            'smb1_enabled': smb1,
            'smb2_enabled': smb2,
            'require_security_signature': False,
            'encrypt_data': False,
        },
        'lanman_server': {
            'name': 'LanmanServer',
            'display_name': 'Server',
            'status': 'Running' if server_running else 'Stopped',
            'start_type': 'Automatic',
            'running': server_running,
        },
        'lanman_workstation': {
            'name': 'LanmanWorkstation',
            'display_name': 'Workstation',
            'status': 'Running' if workstation_running else 'Stopped',
            'start_type': 'Automatic',
            'running': workstation_running,
        },
        'firewall_rules': [
            {'enabled': fw_enabled, 'direction': 'Inbound', 'profile': 'Private, Domain'},
            {'enabled': fw_enabled, 'direction': 'Outbound', 'profile': 'Private, Domain'},
        ],
        'shares': shares,
    }
    return json.dumps(payload)


def _make_discovery_ps_runner(
    *,
    category: str = 'Private',
    fdres_running: bool = True,
    fdphost_running: bool = True,
    ssdp_running: bool = True,
    upnp_running: bool = False,
    fw_enabled: bool = True,
    commands_log: List[str] | None = None,
):
    """Создаёт мок PowerShell-раннера для NetworkDiscoveryManager."""

    def runner(script: str) -> Tuple[int, str, str]:
        if commands_log is not None:
            commands_log.append(script)
        if 'Get-NetConnectionProfile' in script:
            return 0, json.dumps([
                {
                    'Name': 'HomeLAN',
                    'InterfaceAlias': 'Ethernet',
                    'InterfaceIndex': 7,
                    'NetworkCategory': category,
                    'IPv4Connectivity': 'Internet',
                }
            ]), ''
        if 'Get-Service -Name FDResPub' in script:
            return 0, json.dumps([
                {'Name': 'FDResPub', 'DisplayName': 'FDResPub', 'Status': 'Running' if fdres_running else 'Stopped', 'StartType': 'Automatic'},
                {'Name': 'fdPHost', 'DisplayName': 'fdPHost', 'Status': 'Running' if fdphost_running else 'Stopped', 'StartType': 'Manual'},
                {'Name': 'SSDPSRV', 'DisplayName': 'SSDPSRV', 'Status': 'Running' if ssdp_running else 'Stopped', 'StartType': 'Manual'},
                {'Name': 'upnphost', 'DisplayName': 'upnphost', 'Status': 'Running' if upnp_running else 'Stopped', 'StartType': 'Manual'},
            ]), ''
        if 'Get-NetFirewallRule' in script and 'Set-NetFirewallRule' not in script:
            return 0, json.dumps([
                {'Name': 'NETDIS-FDPHOST-In-UDP', 'DisplayName': 'NetDis', 'Enabled': 1 if fw_enabled else 2, 'Direction': 'Inbound', 'Action': 'Allow', 'Group': '@FirewallAPI.dll,-32752'},
                {'Name': 'NETDIS-FDRESPUB-In-UDP', 'DisplayName': 'NetDis2', 'Enabled': 1 if fw_enabled else 2, 'Direction': 'Inbound', 'Action': 'Allow', 'Group': '@FirewallAPI.dll,-32752'},
            ]), ''
        return 0, 'OK', ''

    return runner


def test_discovery_inspects_all_four_services() -> None:
    """Проверяет опрос всех 4 служб сетевого обнаружения (FDResPub, fdPHost, SSDPSRV, upnphost)."""
    mgr = NetworkDiscoveryManager(
        ps_runner=_make_discovery_ps_runner(ssdp_running=True, upnp_running=False)
    )
    state = mgr.inspect()
    assert state['is_discovery_enabled'] is True
    assert state['services']['fdres_running'] is True
    assert state['services']['fdphost_running'] is True
    assert state['services']['ssdp_running'] is True
    assert state['services']['upnp_running'] is False


def test_smb_status_detects_smb1_warning_and_user_shares() -> None:
    """Проверяет парсинг конфигурации SMB1/SMB2/3, правил @FirewallAPI.dll,-28502 и шар."""
    def ps_runner(script: str) -> Tuple[int, str, str]:
        return 0, _make_smb_snapshot_json(smb1=True, smb2=True, fw_enabled=True, include_user_share=True), ''

    mgr = WindowsSmbSharingManager(ps_runner=ps_runner, is_admin_fn=lambda: True)
    status = mgr.get_status()

    assert status.is_admin is True
    assert status.smb1_warning is True
    assert status.server_config.smb2_enabled is True
    assert status.firewall.is_enabled is True
    assert status.firewall.group_identifier == '@FirewallAPI.dll,-28502'
    assert status.user_shares_count == 1
    assert len(status.shares) == 3
    assert status.ready_for_file_sharing is True


def test_smb_toggle_requires_admin_and_protects_special_shares() -> None:
    """Проверяет требование прав администратора и запрет удаления системных шар."""
    def ps_runner(script: str) -> Tuple[int, str, str]:
        return 0, _make_smb_snapshot_json(), ''

    non_admin = WindowsSmbSharingManager(ps_runner=ps_runner, is_admin_fn=lambda: False)
    res = non_admin.toggle_file_sharing(enable=True)
    assert res.success is False
    assert res.requires_admin is True

    admin = WindowsSmbSharingManager(ps_runner=ps_runner, is_admin_fn=lambda: True)
    rem_sys = admin.remove_share('ADMIN$')
    assert rem_sys.success is False
    assert 'запрещено' in rem_sys.message.lower()

    bad_path = admin.create_share(SmbCreateShareRequest(name='TestShare', path='C:\\Temp;whoami'))
    assert bad_path.success is False

    with pytest.raises(ValueError):
        admin.get_share_access('bad;name')


def test_visibility_diagnostics_detects_firewall_and_smb1_issues(tmp_path: Path) -> None:
    """Проверяет независимую 4-уровневую диагностику при выключенном Firewall и включённом SMB1."""
    disc = NetworkDiscoveryManager(
        ps_runner=_make_discovery_ps_runner(category='Private', fdres_running=True, fw_enabled=False)
    )
    smb = WindowsSmbSharingManager(
        ps_runner=lambda _s: (0, _make_smb_snapshot_json(smb1=True, smb2=True, fw_enabled=False), ''),
        is_admin_fn=lambda: True,
    )
    diag = LanVisibilityDiagnostics(
        discovery_manager=disc,
        smb_manager=smb,
        snapshot_dir=tmp_path,
        is_admin_fn=lambda: True,
    )

    report = diag.diagnose()
    codes = {f.code for f in report.findings}
    assert report.overall_status == 'error'
    assert report.is_discoverable is False
    assert report.is_file_sharing_ready is False
    assert 'VIS006' in codes  # Firewall блокирует Discovery
    assert 'VIS007' in codes  # Firewall блокирует File Sharing
    assert 'VIS008' in codes  # Включён небезопасный SMB 1.0
    assert len(report.levels) == 4


def test_visibility_diagnostics_detects_public_profile_and_stopped_services(tmp_path: Path) -> None:
    """Проверяет выявление Public-профиля, остановленной FDResPub и отсутствия пользовательских шар."""
    disc = NetworkDiscoveryManager(
        ps_runner=_make_discovery_ps_runner(category='Public', fdres_running=False, fw_enabled=True)
    )
    smb = WindowsSmbSharingManager(
        ps_runner=lambda _s: (0, _make_smb_snapshot_json(smb1=False, smb2=True, fw_enabled=True, include_user_share=False), ''),
        is_admin_fn=lambda: True,
    )
    diag = LanVisibilityDiagnostics(
        discovery_manager=disc,
        smb_manager=smb,
        snapshot_dir=tmp_path,
        is_admin_fn=lambda: True,
    )

    report = diag.diagnose()
    codes = {f.code for f in report.findings}
    assert 'VIS001' in codes
    assert 'VIS003' in codes
    assert 'VIS010' in codes
    assert report.is_discoverable is False
    assert report.is_file_sharing_ready is False


def test_snapshot_create_list_and_rollback(tmp_path: Path) -> None:
    """Проверяет создание снимка, чтение истории и откат конфигурации (Rollback)."""
    executed: List[str] = []
    disc = NetworkDiscoveryManager(
        ps_runner=_make_discovery_ps_runner(category='Private', fw_enabled=False, commands_log=executed)
    )
    smb_cmds: List[str] = []

    def smb_runner(script: str) -> Tuple[int, str, str]:
        smb_cmds.append(script)
        if 'Get-SmbServerConfiguration' in script:
            return 0, _make_smb_snapshot_json(fw_enabled=False), ''
        return 0, 'OK', ''

    smb = WindowsSmbSharingManager(ps_runner=smb_runner, is_admin_fn=lambda: True)
    diag = LanVisibilityDiagnostics(
        discovery_manager=disc,
        smb_manager=smb,
        snapshot_dir=tmp_path,
        is_admin_fn=lambda: True,
    )

    snap = diag.create_snapshot(reason='before_test')
    assert snap.snapshot_id.startswith('net_')
    listed = diag.list_snapshots()
    assert len(listed) == 1
    assert listed[0].snapshot_id == snap.snapshot_id

    rb = diag.rollback(snap.snapshot_id)
    assert rb.success is True
    assert any('Set-NetConnectionProfile' in cmd for cmd in executed)
    assert any('Disable-NetFirewallRule' in cmd for cmd in smb_cmds)


def test_network_sharing_and_visibility_api_endpoints(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет REST API эндпоинты /api/v1/network/sharing/* и /api/v1/network/visibility/*."""
    disc = NetworkDiscoveryManager(ps_runner=_make_discovery_ps_runner(category='Private', fw_enabled=True))
    smb = WindowsSmbSharingManager(
        ps_runner=lambda s: (0, _make_smb_snapshot_json() if 'Get-SmbServerConfiguration' in s else '[]', ''),
        is_admin_fn=lambda: True,
    )
    diag = LanVisibilityDiagnostics(
        discovery_manager=disc,
        smb_manager=smb,
        snapshot_dir=tmp_path,
        is_admin_fn=lambda: True,
    )

    monkeypatch.setattr(net_router_mod, '_smb_sharing', smb)
    monkeypatch.setattr(net_router_mod, '_visibility_diag', diag)

    app = FastAPI()
    app.include_router(net_router_mod.router)
    client = TestClient(app)

    r_status = client.get('/api/v1/network/sharing/status')
    assert r_status.status_code == 200
    assert r_status.json()['ready_for_file_sharing'] is True

    r_diag = client.get('/api/v1/network/visibility/diagnose')
    assert r_diag.status_code == 200
    body = r_diag.json()
    assert body['is_discoverable'] is True
    assert len(body['levels']) == 4

    r_snap = client.post('/api/v1/network/visibility/snapshots?reason=api_test')
    assert r_snap.status_code == 200
    snap_id = r_snap.json()['snapshot_id']

    r_list = client.get('/api/v1/network/visibility/snapshots')
    assert r_list.status_code == 200
    assert r_list.json()['total'] == 1

    r_rb_missing = client.post('/api/v1/network/visibility/rollback/nonexistent_id')
    assert r_rb_missing.status_code == 404

    r_rb = client.post(f'/api/v1/network/visibility/rollback/{snap_id}')
    assert r_rb.status_code == 200
    assert r_rb.json()['success'] is True
