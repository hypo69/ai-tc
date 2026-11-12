# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - API v1 Keys and Google Accounts Suite
# =============================================================================
# Description:
#   Тесты верификации эндпоинтов /api/v1/keys, /api/v1/keys/agy
#   и /api/v1/admin/google-accounts (включая проверку legacy-алиасов).
#
# Usage Examples:
#   CLI:
#     pytest tests/test_api_v1_keys_and_accounts.py
#
# File: test_api_v1_keys_and_accounts.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-03 16:05:00
# =============================================================================

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from apps.windows.api.server import create_app


@pytest.fixture(scope="module")
def api_client() -> TestClient:
    """Фикстура тестового клиента FastAPI приложения."""
    app = create_app()
    return TestClient(app)


def test_v1_keys_endpoint(api_client: TestClient) -> None:
    """Проверка доступности эндпоинта GET /api/v1/keys."""
    resp = api_client.get("/api/v1/keys")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_v1_keys_agy_endpoint(api_client: TestClient) -> None:
    """Проверка доступности эндпоинта GET /api/v1/keys/agy."""
    resp = api_client.get("/api/v1/keys/agy")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_v1_admin_google_accounts_endpoint(api_client: TestClient) -> None:
    """Проверка доступности эндпоинта GET /api/v1/admin/google-accounts."""
    resp = api_client.get("/api/v1/admin/google-accounts")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "success"
    assert "accounts" in data


def test_legacy_aliases_compatibility(api_client: TestClient) -> None:
    """Проверка доступности legacy-алиасов для обратной совместимости."""
    resp_keys = api_client.get("/api/keys/")
    assert resp_keys.status_code == 200

    resp_agy = api_client.get("/api/keys/agy")
    assert resp_agy.status_code == 200

    resp_google = api_client.get("/api/admin/google-accounts")
    assert resp_google.status_code == 200
