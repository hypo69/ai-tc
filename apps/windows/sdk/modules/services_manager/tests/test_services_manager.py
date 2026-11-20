# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Apps Windows Modules Services_Manager Tests - Test Services Manager
# =============================================================================
# Description:
#   Тестирование каталога служб Windows, инспектора связей (svchost-группы,
#   per-user суффиксы, зависимости, общие PID), глубокого досье и REST API.
#
# Usage Examples:
#   Python API:
#     pytest apps/windows/sdk/modules/services_manager/tests/test_services_manager.py
#
# File: test_services_manager.py
# Project: ai-tc
# Package: apps.windows.sdk.modules.services_manager.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20 16:45:00
# =============================================================================

from __future__ import annotations

"""Тестирование модуля управления службами Windows, графа связей и досье."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.windows.sdk.modules.services_manager.core.inspector import (
    ServiceCatalogInspector,
    extract_svchost_group,
    parse_per_user_service_name,
)
from apps.windows.sdk.modules.services_manager.core.manager import ServicesManager
from apps.windows.sdk.modules.services_manager.core.models import (
    ServiceActionRequest,
    ServiceItem,
)
from apps.windows.sdk.modules.services_manager.router import init_router


@pytest.fixture
def manager() -> ServicesManager:
    return ServicesManager()


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(init_router())
    return TestClient(app)


@pytest.mark.parametrize(
    'name, expected',
    [
        ('OneSyncSvc_12345', (True, 'OneSyncSvc', '12345')),
        ('CDPUserSvc_4a7f2', (True, 'CDPUserSvc', '4a7f2')),
        ('wuauserv', (False, 'wuauserv', '')),
        ('OneSyncSvc', (False, 'OneSyncSvc', '')),
    ],
)
def test_parse_per_user_service_name(name: str, expected: tuple) -> None:
    """Проверка распознавания динамического суффикса per-user экземпляров служб."""
    assert parse_per_user_service_name(name) == expected


@pytest.mark.parametrize(
    'binpath, expected',
    [
        (r'C:\Windows\system32\svchost.exe -k UnistackSvcGroup -p', 'UnistackSvcGroup'),
        (r'%SystemRoot%\System32\svchost.exe -k "netsvcs"', 'netsvcs'),
        (r'C:\Program Files\App\service.exe -k dummy', ''),
        ('', ''),
    ],
)
def test_extract_svchost_group(binpath: str, expected: str) -> None:
    """Проверка извлечения имени группы svchost из командной строки службы."""
    assert extract_svchost_group(binpath) == expected


def test_inspector_graph_and_clusters() -> None:
    """Проверка построения графа групп svchost, общих PID и per-user экземпляров."""
    inspector = ServiceCatalogInspector()
    services = [
        ServiceItem(
            name='OneSyncSvc_1a2b3',
            display_name='Sync Host',
            status='RUNNING',
            pid=4200,
            binary_path=r'C:\Windows\system32\svchost.exe -k UnistackSvcGroup',
            svchost_group='UnistackSvcGroup',
            host_process_name='svchost.exe',
            is_per_user=True,
            base_service_name='OneSyncSvc',
            instance_suffix='1a2b3',
            memory_mb=42.5,
            network_connections_count=2,
        ),
        ServiceItem(
            name='UserDataSvc_1a2b3',
            display_name='User Data Access',
            status='RUNNING',
            pid=4200,
            binary_path=r'C:\Windows\system32\svchost.exe -k UnistackSvcGroup',
            svchost_group='UnistackSvcGroup',
            host_process_name='svchost.exe',
            is_per_user=True,
            base_service_name='UserDataSvc',
            instance_suffix='1a2b3',
            memory_mb=42.5,
            network_connections_count=2,
        ),
    ]
    graph = inspector.build_graph_report(services)
    assert graph.total_services == 2
    assert graph.total_groups == 1
    assert graph.svchost_groups[0].group_name == 'UnistackSvcGroup'
    assert graph.svchost_groups[0].total_services == 2
    assert graph.svchost_groups[0].total_memory_mb == 42.5
    assert graph.total_shared_pid_clusters == 1
    assert graph.shared_pid_clusters[0].pid == 4200
    assert graph.total_per_user_instances == 2


def test_services_report(manager: ServicesManager) -> None:
    """Проверка генерации обогащенного отчета о службах."""
    report = manager.generate_report()
    assert report is not None
    assert report.total_services > 0
    assert report.svchost_groups_count >= 0


@pytest.mark.asyncio
async def test_service_action_simulation(manager: ServicesManager) -> None:
    """Проверка симуляции безопасного действия со службой."""
    req = ServiceActionRequest(
        name='wuauserv',
        action='restart',
        dry_run=True,
        confirmed_by_user=False,
    )
    res = await manager.execute_service_action(req)
    assert res['status'] == 'DRY_RUN_SUCCESS'


def test_services_endpoints_and_graph_dossier(client: TestClient) -> None:
    """Проверка REST эндпоинтов /scan, /summary, /graph и /dossier/{name}."""
    resp_scan = client.post('/api/v1/services-manager/scan')
    assert resp_scan.status_code == 200
    scan_data = resp_scan.json()
    assert scan_data['total_services'] > 0
    assert len(scan_data['services']) > 0

    resp_summary = client.get('/api/v1/services-manager/summary')
    assert resp_summary.status_code == 200
    assert resp_summary.json()['total_services'] == scan_data['total_services']

    resp_graph = client.get('/api/v1/services-manager/graph')
    assert resp_graph.status_code == 200
    graph_data = resp_graph.json()
    assert graph_data['total_services'] == scan_data['total_services']
    assert 'svchost_groups' in graph_data
    assert 'shared_pid_clusters' in graph_data
    assert 'per_user_instances' in graph_data

    # Проверяем глубокое досье на реальной службе из каталога (приоритетно svchost-служба)
    sample_svc = next(
        (s for s in scan_data['services'] if s.get('svchost_group') and s.get('status') == 'RUNNING'),
        scan_data['services'][0],
    )
    resp_dossier = client.get(f"/api/v1/services-manager/dossier/{sample_svc['name']}")
    assert resp_dossier.status_code == 200
    dossier = resp_dossier.json()
    assert dossier['service']['name'] == sample_svc['name']
    assert len(dossier['relations_chain']) >= 1
    assert len(dossier['graph_nodes']) >= 1
    assert 'registry' in dossier
    assert 'network_connections' in dossier
    assert 'recent_events' in dossier

    # Несуществующая служба должна возвращать 404
    resp_404 = client.get('/api/v1/services-manager/dossier/__non_existent_service_xyz__')
    assert resp_404.status_code == 404
