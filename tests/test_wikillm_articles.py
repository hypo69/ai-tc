# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - WikiLLM Articles & Category Filter
# =============================================================================
# Description:
#   Модульные тесты эндпоинта GET /api/v1/wikillm/articles, фильтрации по категориям,
#   облаку тегов и поисковому запросу согласно ТЗ v23 (Задача №33).
#
# File: test_wikillm_articles.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-13 12:30:00
# =============================================================================

from __future__ import annotations
"""Тесты для фильтрации и отдачи статей базы знаний WikiLLM."""

import pytest
from fastapi.testclient import TestClient

from apps.windows.api.routers.router_wikillm_editor import router as editor_router
from roadmap.code_fixes.patch_31_wikillm_ui_category_filter import (
    DEFAULT_ARTICLES,
    filter_articles,
    router as patch_router,
)
from fastapi import FastAPI


@pytest.fixture
def test_app() -> FastAPI:
    """Фикстура тестового приложения FastAPI со смонтированным роутером WikiLLM."""
    app = FastAPI()
    app.include_router(editor_router)
    return app


@pytest.fixture
def client(test_app: FastAPI) -> TestClient:
    """Фикстура TestClient для отправки запросов."""
    return TestClient(test_app)


def test_filter_articles_default():
    """Проверка фильтрации по умолчанию (без фильтров возвращаются все статьи)."""
    res = filter_articles(DEFAULT_ARTICLES)
    assert len(res) == len(DEFAULT_ARTICLES)
    assert len(res) >= 5


def test_filter_articles_by_category():
    """Проверка фильтрации по категории process."""
    res_browser = filter_articles(DEFAULT_ARTICLES, category="browser")
    assert len(res_browser) > 0
    assert all(a["category"] == "browser" for a in res_browser)

    res_service = filter_articles(DEFAULT_ARTICLES, category="system_service")
    assert len(res_service) > 0
    assert all(a["category"] == "system_service" for a in res_service)

    res_all = filter_articles(DEFAULT_ARTICLES, category="all")
    assert len(res_all) == len(DEFAULT_ARTICLES)


def test_filter_articles_by_tag():
    """Проверка фильтрации по популярным тегам из ТЗ v23."""
    for required_tag in ["memory_leak", "gpu_acceleration", "high_cpu", "untrusted_path"]:
        res = filter_articles(DEFAULT_ARTICLES, tag=required_tag)
        assert len(res) > 0, f"Ожидались статьи для тега {required_tag}"
        assert all(required_tag in a["tags"] for a in res)


def test_filter_articles_category_and_tag_combination():
    """Проверка комбинации фильтров category=browser и tag=memory_leak (ТЗ v23 требование 3)."""
    res = filter_articles(DEFAULT_ARTICLES, category="browser", tag="memory_leak")
    assert len(res) >= 1
    assert any(a["process_name"] == "msedge.exe" for a in res)
    assert all(a["category"] == "browser" and "memory_leak" in a["tags"] for a in res)


def test_filter_articles_search_query():
    """Проверка текстового поиска по поисковой строке search_query."""
    res_edge = filter_articles(DEFAULT_ARTICLES, search_query="Edge")
    assert len(res_edge) >= 1
    assert any("msedge.exe" in a["process_name"] for a in res_edge)

    res_spool = filter_articles(DEFAULT_ARTICLES, search_query="spoolsv")
    assert len(res_spool) == 1
    assert res_spool[0]["category"] == "system_service"

    res_empty = filter_articles(DEFAULT_ARTICLES, search_query="non_existent_process_12345")
    assert len(res_empty) == 0


def test_api_get_articles_endpoint(client: TestClient):
    """Интеграционный тест эндпоинта GET /api/v1/wikillm/articles."""
    response = client.get("/api/v1/wikillm/articles")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["total"] > 0
    assert isinstance(data["articles"], list)


def test_api_get_articles_with_category_and_tag(client: TestClient):
    """Интеграционный тест запроса GET /api/v1/wikillm/articles?category=browser&tag=memory_leak."""
    response = client.get("/api/v1/wikillm/articles?category=browser&tag=memory_leak")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["total"] >= 1
    for article in data["articles"]:
        assert article["category"] == "browser"
        assert "memory_leak" in article["tags"]


def test_api_get_articles_empty_filter(client: TestClient):
    """Проверка ответа при отсутствии совпадений."""
    response = client.get("/api/v1/wikillm/articles?category=browser&tag=untrusted_path")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["total"] == 0
    assert data["articles"] == []


def test_patch_router_direct():
    """Проверка прямого вызова роутера из patch_31_wikillm_ui_category_filter."""
    app = FastAPI()
    app.include_router(patch_router)
    c = TestClient(app)

    response = c.get("/api/v1/wikillm/articles?category=dev_tool&tag=untrusted_path")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert any(a["process_name"] == "git.exe" for a in data["articles"])

