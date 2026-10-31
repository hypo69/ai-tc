# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Diagnostics Quick Questions & WikiLLM Enrichment
# =============================================================================
# Description:
#   Комплексные тесты динамической генерации трех вопросов по теме промпта
#   и последующего обогащения базы знаний WikiLLM результатами ответов модели.
#
# Usage Examples:
#   pytest tests/test_diagnostics_quick_questions.py
#
# File: test_diagnostics_quick_questions.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 13:16:00
# =============================================================================

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from apps.windows.api.diagnostics_prompt_manager import (
    DiagnosticPromptTemplate,
    prompt_manager,
    DEFAULT_PROMPTS,
)
from apps.windows.api.routers.router_diagnostics import init_router


@pytest.fixture
def api_client() -> TestClient:
    """Фикстура тестового клиента FastAPI с подключенным роутером диагностики."""
    from fastapi import FastAPI
    app = FastAPI()
    router = init_router()
    app.include_router(router)
    return TestClient(app)


def test_default_prompts_have_questions_prompt() -> None:
    """Все дефолтные шаблоны промптов содержат вопросы по теме сущности."""
    expected_keys = [
        "power_session",
        "power_event",
        "cpu",
        "gpu",
        "software",
        "process",
        "service",
        "network",
        "user_account",
        "security_event",
        "task",
        "registry",
        "disk",
        "startup",
        "website",
        "rag_doc",
        "app_log",
        "help",
        "generic",
    ]
    for key in expected_keys:
        assert key in DEFAULT_PROMPTS, f"Шаблон '{key}' отсутствует в DEFAULT_PROMPTS"
        tmpl = prompt_manager.get_template(key)
        assert tmpl.questions_prompt, f"У шаблона '{key}' отсутствует questions_prompt"
        assert "3" in tmpl.questions_prompt, f"В questions_prompt для '{key}' должно быть указание на 3 вопроса"

        # Проверка форматирования короткого промпта на вопросы
        formatted_q = tmpl.format_questions_prompt(
            title="Test Title",
            subtitle="Test Subtitle",
            metadata={"status": "active"},
            raw_data="raw=1"
        )
        assert "Test Title" in formatted_q
        assert "3" in formatted_q


def test_suggest_questions_endpoint_fallback(api_client: TestClient) -> None:
    """Эндпоинт /suggest-questions возвращает ровно 3 контекстных вопроса системного администратора."""
    payload = {
        "table_type": "process",
        "title": "explorer.exe",
        "subtitle": "PID: 4512",
        "metadata": {"cpu": "1.2%", "memory_mb": 128},
        "raw_data": "C:\\Windows\\explorer.exe",
        "model": "gemini-3.1-flash-lite",
        "provider": "gemini"
    }
    resp = api_client.post("/api/v1/diagnostics/suggest-questions", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert "questions" in data
    assert isinstance(data["questions"], list)
    assert len(data["questions"]) == 3
    # Проверяем, что вопросы относятся к процессу
    joined_text = " ".join(data["questions"]).lower()
    assert "процесс" in joined_text or "explorer.exe" in joined_text or "безопасн" in joined_text


def test_suggest_questions_for_power_session(api_client: TestClient) -> None:
    """Эндпоинт /suggest-questions возвращает вопросы по сессии питания и аптайму."""
    payload = {
        "table_type": "power_session",
        "title": "Сессия #14",
        "subtitle": "Shutdown | Uptime: 4h 12m",
        "metadata": {"event_id": 1074, "initiator": "shutdown.exe"},
    }
    resp = api_client.post("/api/v1/diagnostics/suggest-questions", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert len(data["questions"]) == 3
    joined_text = " ".join(data["questions"]).lower()
    assert "сесси" in joined_text or "питани" in joined_text or "аптайм" in joined_text or "выключен" in joined_text


def test_chat_endpoint_enriches_wikillm(api_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Эндпоинт /chat отвечает на вопрос и обогащает базу знаний WikiLLM парой вопрос-ответ."""
    from apps.windows.wikillm.router import get_engine
    engine = get_engine()

    test_title = "test_daemon_svc.exe"
    test_question = "Зачем процессу test_daemon_svc.exe сетевой порт 8080?"
    test_answer = "Порт 8080 используется данным сервисом для локального REST API мониторинга телеметрии."

    payload = {
        "table_type": "service",
        "title": test_title,
        "subtitle": "Port: 8080",
        "question": test_question,
        "metadata": {"port": 8080, "protocol": "TCP"},
        "stream": False,
        "enrich_wikillm": True,
        "model": "gemini-3.1-flash-lite",
        "provider": "gemini"
    }

    # Имитируем ответ модели
    async def mock_ask(*args, **kwargs):
        return test_answer

    from src.ai.gemini.generative_ai import GoogleGenerativeAI
    monkeypatch.setattr(GoogleGenerativeAI, "ask", mock_ask)

    resp = api_client.post("/api/v1/diagnostics/chat", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "ok"
    assert data["enriched"] is True
    assert test_answer in data["answer"]
    canonical_key = data["canonical_key"]
    assert canonical_key is not None

    # Проверяем, что знание сохранилось в базе WikiLLM
    saved_entity = engine.storage.get_entity(canonical_key)
    assert saved_entity is not None
    # Проверяем наличие Claim с вопросом и ответом
    statements = [c.statement for c in saved_entity.claims]
    assert any(test_question in s and test_answer in s for s in statements)

