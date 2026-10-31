# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Diagnostics JSON Parser
# =============================================================================
# Description:
#   Модульные тесты для надежного парсинга JSON ответов моделей ИИ,
#   включая обработку неэкранированных управляющих символов и сценарии исправления.
#
# File: test_diagnostics_json_parser.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-16 19:15:00
# =============================================================================

import pytest
from apps.windows.api.routers.router_diagnostics import _extract_and_parse_json


def test_parse_json_with_raw_newlines_inside_strings():
    """Проверка успешного парсинга JSON со сырыми переносами строк внутри строковых значений (баг RFC 8259 / strict=False)."""
    raw_response = (
        "```json\n"
        "{\n"
        '  "summary": "**Аудит интерфейсного элемента Windows Defender.**\\n\\nДанное событие фиксирует вход.",\n'
        '  "raw_lines": "Line 1\nLine 2\nLine 3",\n'
        '  "developer": "Microsoft Defender"\n'
        "}\n"
        "```"
    )
    # Заменяем \\n на реальный байт перевода строки 0x0A, как возвращает модель
    actual_llm_output = raw_response.replace("\\n", "\n")

    data, err = _extract_and_parse_json(actual_llm_output)
    assert err is None, f"Ошибка парсинга не должна возникать: {err}"
    assert isinstance(data, dict)
    assert "Line 1\nLine 2" in data["raw_lines"]
    assert data["developer"] == "Microsoft Defender"


def test_parse_json_with_trailing_commas():
    """Проверка парсинга JSON с висячими запятыми (trailing commas)."""
    raw = """
    {
        "title": "Тест",
        "items": [
            "пункт 1",
            "пункт 2",
        ],
    }
    """
    data, err = _extract_and_parse_json(raw)
    assert err is None
    assert isinstance(data, dict)
    assert len(data["items"]) == 2


def test_parse_json_list():
    """Проверка парсинга JSON-массива вопросов."""
    raw = """
    Вот сгенерированные вопросы:
    ```
    [
        "Как проверить ASR?",
        "Какие журналы смотреть?",
        "Каковы последствия блокировки?"
    ]
    ```
    Надеюсь, они помогут.
    """
    data, err = _extract_and_parse_json(raw)
    assert err is None
    assert isinstance(data, list)
    assert len(data) == 3
    assert data[0] == "Как проверить ASR?"


def test_parse_invalid_json_returns_error():
    """Проверка возврата ошибки для полностью поврежденного JSON."""
    raw = "Это просто текстовый ответ модели без какого-либо JSON {незакрытая скобка"
    data, err = _extract_and_parse_json(raw)
    assert data is None
    assert err is not None


@pytest.mark.asyncio
async def test_explain_element_heals_invalid_json_via_model_repair(monkeypatch):
    """Проверка сценария: при первичном сломанном ответе парсер отправляет запрос модели на исправление и успешно получает валидный JSON."""
    from unittest.mock import AsyncMock
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from apps.windows.api.routers.router_diagnostics import init_router

    app = FastAPI()
    app.include_router(init_router())
    client = TestClient(app)

    # Имитируем ответы модели: 1-й вызов - битый JSON, 2-й вызов (запрос исправления) - валидный JSON
    mock_responses = [
        "Невалидный ответ { \"summary\": \"Текст без закрывающей кавычки и скобок",
        """```json
        {
            "summary": "Исправленное заключение",
            "developer": "Microsoft",
            "category": "Безопасность",
            "security_verdict": "Легитимно",
            "performance_impact": "Норма",
            "recommendation": "Действий не требуется",
            "action_steps": ["Шаг 1", "Шаг 2"]
        }
        ```"""
    ]

    mock_ask = AsyncMock(side_effect=mock_responses)

    # Мокаем GoogleGenerativeAI.ask
    from src.ai.gemini.generative_ai import GoogleGenerativeAI
    monkeypatch.setattr(GoogleGenerativeAI, "ask", mock_ask)

    resp = client.post(
        "/api/v1/diagnostics/explain",
        json={
            "title": "ASR Rule",
            "subtitle": "Defender",
            "provider": "gemini",
            "model": "gemini-3.5-flash-lite",
        }
    )

    assert resp.status_code == 200, f"Ожидался 200 OK после исправления, получен {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["summary"] == "Исправленное заключение"
    assert body["developer"] == "Microsoft"
    # Проверяем, что модель была вызвана дважды (первичный вызов + запрос на исправление)
    assert mock_ask.call_count == 2


