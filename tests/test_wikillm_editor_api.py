# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - WikiLLM Editor Endpoints Tests
# =============================================================================
# Description:
#   Интеграционные тесты для роутера WikiLLM Editor с использованием DatabaseAdapter.
#
# File: test_wikillm_editor_api.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 02:58:00
# =============================================================================

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.windows.api.routers.router_wikillm_editor import router as wikillm_router


@pytest.fixture
def app() -> FastAPI:
    """Фикстура тестового приложения FastAPI."""
    test_app = FastAPI()
    test_app.include_router(wikillm_router)
    return test_app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Фикстура TestClient."""
    return TestClient(app)


def test_wikillm_editor_settings(client: TestClient):
    """Проверка получения и сохранения настроек WikiLLM."""
    resp = client.get("/api/v1/wikillm/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert "model_name" in data
    assert "db_path" in data


def test_wikillm_editor_crud_flow(client: TestClient):
    """Проверка сквозного цикла CRUD сущностей через API роутера WikiLLM Editor."""
    entity_payload = {
        "canonical_key": "win_event_e2e_test",
        "title": "E2E Тестовая запись",
        "category": "security_test",
        "description": "Описание для E2E теста",
        "claims": ["Проверка интеграции с адаптером"],
        "remediation": ["Действие 1"],
        "is_verified": True,
    }

    # 1. Создание сущности
    post_resp = client.post("/api/v1/wikillm/entities", json=entity_payload)
    assert post_resp.status_code == 201

    # 2. Получение сущности по ключу
    get_resp = client.get("/api/v1/wikillm/entities/win_event_e2e_test")
    assert get_resp.status_code == 200
    entity_data = get_resp.json()
    assert entity_data["canonical_key"] == "win_event_e2e_test"
    assert entity_data["title"] == "E2E Тестовая запись"

    # 3. Список сущностей с поиском
    list_resp = client.get("/api/v1/wikillm/entities?q=E2E")
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert any(i["canonical_key"] == "win_event_e2e_test" for i in items)

    # 4. Удаление сущности
    del_resp = client.delete("/api/v1/wikillm/entities/win_event_e2e_test")
    assert del_resp.status_code == 200

    # 5. Проверка удаления
    get_after_del = client.get("/api/v1/wikillm/entities/win_event_e2e_test")
    assert get_after_del.status_code == 404


def test_wikillm_editor_profiles(client: TestClient):
    """Проверка получения профилей точности RAG."""
    resp = client.get("/api/v1/wikillm/profiles")
    assert resp.status_code == 200
    profiles = resp.json()
    assert isinstance(profiles, list)
    assert len(profiles) >= 1
    first = profiles[0]
    assert "profile_name" in first
    assert "score_threshold" in first
    assert "top_k" in first
    assert "fetch_k" in first

