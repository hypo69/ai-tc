# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Tests - Network Infra API & UI markup
# =============================================================================
# Description:
#   Интеграционные тесты маршрутов /api/network/infra/* в существующем
#   FastAPI-приложении ai-tc (подмена источников Windows) и проверка разметки
#   вкладки tab-network (идентификаторы панелей, размещение меню).
#
# File: test_network_infra_api.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 16:20:00
# =============================================================================

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.windows.api.server import create_app
from apps.windows.sdk.modules.network.infra import router as infra_router
from apps.windows.sdk.modules.network.infra.collectors_virtual import WslNetworkCollector
from apps.windows.sdk.modules.network.infra.ps_runner import PsResult
from apps.windows.sdk.modules.network.infra.service import NetworkInfraService
from apps.windows.sdk.modules.network.infra.settings import InfraSettings
from apps.windows.sdk.modules.network.infra.store import NetworkInfraStore
from tests.test_network_infra import FakeRunner, base_scripts, hv_scripts

WEBGUI = Path(__file__).resolve().parents[1] / 'apps' / 'windows' / 'api' / 'webgui' / 'tab_network'
PANELS = ['overview', 'adapters', 'switches', 'ip-config', 'nat', 'wsl', 'diagnostics', 'history']


@pytest.fixture()
def client(tmp_path):
    runner = FakeRunner(hv_scripts(), wsl_path=None)
    st = InfraSettings(cache_ttl_sec=0, db_path=str(tmp_path / 'api.db'))
    svc = NetworkInfraService(runner, NetworkInfraStore(st.resolved_db_path()), st)
    svc.wsl = WslNetworkCollector(runner, tmp_path / 'none')
    infra_router.set_service(svc)
    yield TestClient(create_app())
    infra_router.set_service(None)


def test_routes_registered_in_existing_app(client):
    assert client.get('/api/network/infra/summary').status_code == 200
    assert client.get('/api/network/infra/snapshots').status_code == 200
    assert client.get('/api/network/infra/snapshots/compare?base=a&target=b').status_code == 404
    # существующие маршруты сетевого терминала не нарушены (не 404)
    assert client.get('/api/network/subnets').status_code != 404


def test_resources_have_status_envelope(client):
    for name, status in (('adapters', 'ok'), ('ip-config', 'ok'), ('routes', 'ok'), ('switches', 'ok'),
                         ('nat', 'ok'), ('wsl', 'not_installed')):
        body = client.get(f'/api/network/infra/{name}').json()
        assert body['status'] == status and 'collected_at' in body and 'errors' in body and isinstance(body['items'], list)
    assert client.get('/api/network/infra/routes?family=IPv4').json()['items']
    assert client.get('/api/network/infra/routes?family=IPv6').json()['items'] == []
    assert client.get('/api/network/infra/routes?family=bad').status_code == 400


def test_summary_and_diagnostics(client):
    body = client.get('/api/network/infra/summary').json()
    assert body['summary']['adapters_total'] == 2 and body['summary']['switches_count'] == 2
    diag = client.post('/api/network/infra/diagnostics/run').json()
    assert any(f['rule_code'] == 'NET006' for f in diag['findings'])
    assert client.get('/api/network/infra/history/findings?severity=bad').status_code == 400


def test_snapshots_history_compare_and_errors(client):
    a = client.post('/api/network/infra/snapshots').json()
    b = client.post('/api/network/infra/snapshots').json()
    assert a['id'] != b['id'] and client.get('/api/network/infra/snapshots').json()['items'][0]['id'] == b['id']
    detail = client.get(f"/api/network/infra/snapshots/{a['id']}").json()
    assert detail['data']['adapters'] and detail['sources']['adapters']['status'] == 'ok'
    diff = client.get(f"/api/network/infra/snapshots/compare?base={a['id']}&target={b['id']}").json()
    assert diff['changes'] == [] and diff['base_id'] == a['id']
    assert client.get('/api/network/infra/snapshots/nope').status_code == 404
    assert client.get(f"/api/network/infra/snapshots/compare?base={a['id']}&target=nope").status_code == 404
    assert client.get('/api/network/infra/history/findings').json()['items']
    assert client.post('/api/network/infra/history/prune').json() == {'removed': 0}


def test_partial_availability_reported_not_500(tmp_path):
    s = base_scripts()
    s['Get-NetRoute'] = PsResult(ok=False, error='x', stderr='Access is denied', access_denied=True)
    runner = FakeRunner(s, wsl_path=None)
    st = InfraSettings(cache_ttl_sec=0, db_path=str(tmp_path / 'p.db'))
    svc = NetworkInfraService(runner, NetworkInfraStore(st.resolved_db_path()), st)
    svc.wsl = WslNetworkCollector(runner, tmp_path / 'none')
    infra_router.set_service(svc)
    try:
        body = TestClient(create_app()).get('/api/network/infra/routes').json()
    finally:
        infra_router.set_service(None)
    assert body['status'] == 'data_unavailable' and body['needs_elevation'] and body['items'] == []


# --------------------------------------------------------------- разметка UI
def _html() -> str:
    return (WEBGUI / 'index.html').read_text(encoding='utf-8')


def test_ui_panel_ids_and_single_navigation():
    html = _html()
    for p in PANELS:
        pid = f'panel-network-{p}'
        assert len(re.findall(rf'id="{pid}"', html)) == 1, pid
        assert f'data-bs-target="#{pid}"' in html
    for bad in re.findall(r'id="(tab-network-[\w-]+)"', html):
        pytest.fail(f'Запрещённый ID {bad}')
    ids = re.findall(r'(?<![-\w])id="([^"]+)"', html)
    assert len(ids) == len(set(ids)), 'Дубли DOM-идентификаторов'
    # Меню - в существующем блоке под заголовком, главная вкладка не дублируется
    marker = html.index('Отдельный блок меню суб-вкладок ПОД названием вкладки')
    nav = html.index('id="network-subtabs-nav"', marker)
    nav_end = html.index('id="panel-network-kpi-summary"', nav)
    nav_html = html[nav:nav_end]
    for p in PANELS:
        assert f'data-bs-target="#panel-network-{p}"' in nav_html
    assert 'id="tab-network"' not in html
    assert 'data-bs-toggle="pill"' in nav_html and 'new Tab' not in html


def test_main_js_reuses_existing_navigation_handler():
    js = (WEBGUI / 'main.js').read_text(encoding='utf-8')
    assert js.count("getElementById('network-subtabs-nav')") == 1
    assert "startsWith('#panel-network-')" in js and "'#panel-network-adapters'" in js
    assert "'tab-network'" in js


def test_main_tab_registered_once():
    reg = (WEBGUI.parent / 'core' / 'tab-registry.js').read_text(encoding='utf-8')
    assert len(re.findall(r"tabId: 'tab-network'", reg)) == 1

