# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Diagnostics Explain Error Handling & No Timeout
# =============================================================================
# Description:
#   Тесты обработки ошибок модели AI в роутере диагностики: отсутствие таймаутов,
#   запрет эвристической подмены ответов и корректный возврат ошибки клиенту без записи в WikiLLM.
#
# Usage Examples:
#   pytest tests/test_diagnostics_explain_errors_and_no_timeout.py
#
# File: test_diagnostics_explain_errors_and_no_timeout.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 14:15:00
# =============================================================================

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from apps.windows.api.routers.router_diagnostics import init_router


@pytest.fixture
def api_client() -> TestClient:
    """Фикстура тестового клиента FastAPI с подключенным роутером диагностики."""
    from fastapi import FastAPI
    app = FastAPI()
    router = init_router()
    app.include_router(router)
    return TestClient(app)


def test_explain_endpoint_does_not_substitute_heuristic_on_model_error(api_client: TestClient) -> None:
    """Проверяет, что при ошибке модели сервер НЕ подставляет эвристический ответ, а возвращает ошибку 502."""
    error_json = json.dumps({
        "error": {
            "code": 429,
            "message": "Resource has been exhausted (e.g. check quota).",
            "status": "RESOURCE_EXHAUSTED"
        }
    })

    with patch("src.ai.gemini.generative_ai.GoogleGenerativeAI.ask", new_callable=AsyncMock) as mock_ask:
        mock_ask.return_value = error_json

        res = api_client.post("/api/v1/diagnostics/explain", json={
            "table_type": "process",
            "title": "malware.exe",
            "subtitle": "C:\\temp\\malware.exe",
            "metadata": {"pid": 9999},
            "model": "gemini-2.5-flash",
            "provider": "gemini"
        })

        assert res.status_code == 502
        data = res.json()
        assert "detail" in data
        detail = data["detail"]
        assert "error" in detail
        assert detail["error"]["code"] == 429
        assert detail["error"]["status"] == "RESOURCE_EXHAUSTED"


def test_explain_endpoint_handles_model_exception_without_fake_answer(api_client: TestClient) -> None:
    """Проверяет, что при исключении провайдера возвращается ошибка 502 со структурированным JSON."""
    with patch("src.ai.gemini.generative_ai.GoogleGenerativeAI.ask", new_callable=AsyncMock) as mock_ask:
        mock_ask.side_effect = RuntimeError("API key quota reached")

        res = api_client.post("/api/v1/diagnostics/explain", json={
            "table_type": "software",
            "title": "TestApp",
            "subtitle": "Test Publisher",
            "metadata": {},
            "model": "gemini-2.5-flash",
            "provider": "gemini"
        })

        assert res.status_code == 502
        data = res.json()
        detail = data.get("detail", {})
        assert "error" in detail
        assert "quota" in detail["error"]["message"].lower()


def test_explain_endpoint_success_returns_model_data(api_client: TestClient) -> None:
    """Проверяет успешный возврат валидного JSON ответа модели."""
    valid_model_response = json.dumps({
        "summary": "Легитимный системный компонент Windows",
        "developer": "Microsoft Corporation",
        "category": "Системный процесс",
        "security_verdict": "Безопасен",
        "performance_impact": "Минимальное",
        "recommendation": "Оставить без изменений",
        "action_steps": ["Проверять журнал раз в неделю"]
    })

    with patch("src.ai.gemini.generative_ai.GoogleGenerativeAI.ask", new_callable=AsyncMock) as mock_ask:
        mock_ask.return_value = valid_model_response

        res = api_client.post("/api/v1/diagnostics/explain", json={
            "table_type": "process",
            "title": "custom_agent_test.exe",
            "subtitle": "C:\\Program Files\\CustomApp\\agent.exe",
            "metadata": {"pid": 1234},
            "model": "gemini-2.5-flash",
            "provider": "gemini",
            "force_refresh": True
        })

        assert res.status_code == 200
        data = res.json()
        assert data["summary"] == "Легитимный системный компонент Windows"
        assert data["developer"] == "Microsoft Corporation"
        assert data["is_verified"] is False

