# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Modules Software_Manager Tests - Test Software Manager
# =============================================================================
# Description:
#   # Description:
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.software_manager.tests.test_software_manager import manager
#
#     res = manager()
#
# File: test_software_manager.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.software_manager.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-18 09:30:00
# =============================================================================

from __future__ import annotations
"""Модульные тесты для менеджера пакетов WinGet, Microsoft Store и MSI."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from apps.windows.sdk.modules.software_manager.core.manager import SoftwarePackagesManager
from apps.windows.sdk.modules.software_manager.core.models import PackageActionRequest
from apps.windows.sdk.modules.software_manager.router import init_router


@pytest.fixture
def manager() -> SoftwarePackagesManager:
    return SoftwarePackagesManager()


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(init_router())
    return TestClient(app)


def test_software_report(manager: SoftwarePackagesManager):
    """Проверка генерации отчета об установленном ПО."""
    report = manager.generate_report()
    assert report is not None
    assert report.total_packages > 0
    assert len(report.packages) > 0
    assert report.store_packages_count >= 0


def test_software_store_packages(manager: SoftwarePackagesManager):
    """Проверка фильтрации пакетов Microsoft Store."""
    store_pkgs = manager.list_store_packages()
    assert isinstance(store_pkgs, list)
    for pkg in store_pkgs:
        assert pkg.source == 'msstore'


@pytest.mark.asyncio
async def test_package_action_simulation(manager: SoftwarePackagesManager):
    """Проверка симуляции безопасного действия с пакетом."""
    req = PackageActionRequest(
        package_id='Git.Git',
        action='upgrade',
        dry_run=True,
        confirmed_by_user=False
    )
    res = await manager.execute_package_action(req)
    assert res['status'] == 'DRY_RUN_SUCCESS'


def test_software_endpoints(client: TestClient):
    """Проверка REST эндпоинтов software_manager."""
    resp = client.get('/api/software-manager/report')
    assert resp.status_code == 200
    data = resp.json()
    assert 'packages' in data
    assert 'store_packages_count' in data

    resp_pkgs = client.get('/api/software-manager/packages')
    assert resp_pkgs.status_code == 200

    resp_store = client.get('/api/software-manager/store')
    assert resp_store.status_code == 200
    store_data = resp_store.json()
    assert isinstance(store_data, list)

    resp_filter = client.get('/api/software-manager/packages?source=msstore')
    assert resp_filter.status_code == 200

    resp_search = client.get('/api/software-manager/search?q=python')
    assert resp_search.status_code == 200
    assert len(resp_search.json()) > 0

