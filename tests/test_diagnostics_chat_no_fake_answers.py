# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Diagnostics Chat No Fake Answers
# =============================================================================
# Description:
#   Тесты для эндпоинта /api/v1/diagnostics/chat:
#   - потоковая передача через ai.chat_stream (без устаревшего ask_stream);
#   - категорический запрет подстановки фейковых заглушек при сбое модели;
#   - корректная трансляция ошибки клиенту без записи в WikiLLM;
#   - обогащение названия сущности из метаданных при получении хэша в качестве заголовка.
#
# Usage Examples:
#   pytest tests/test_diagnostics_chat_no_fake_answers.py
#
# File: test_diagnostics_chat_no_fake_answers.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 19:55:00
# =============================================================================

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch, MagicMock

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


def test_chat_streaming_success_uses_chat_stream(api_client: TestClient) -> None:
    """Проверяет, что при стриминге вызывается chat_stream и отдаются фрагменты SSE."""
    async def fake_stream(prompt, **kwargs):
        yield "Ответ "
        yield "на вопрос "
        yield "о PWA."

    with patch("src.ai.gemini.generative_ai.GoogleGenerativeAI.chat_stream", side_effect=fake_stream):
        res = api_client.post("/api/v1/diagnostics/chat", json={
            "table_type": "software",
            "title": "Google Drive PWA",
            "subtitle": "Chrome App",
            "question": "Почему PWA считается отдельным приложением?",
            "stream": True,
            "provider": "gemini",
            "enrich_wikillm": False
        })

        assert res.status_code == 200
        text = res.text
        assert "data: " in text
        assert "Ответ " in text
        assert "на вопрос " in text
        assert "[DONE]" in text
        # Проверяем отсутствие фейковых заглушек
        assert "Экспертное заключение по сущности" not in text


def test_chat_streaming_error_yields_error_event_without_fake_canned_text(api_client: TestClient) -> None:
    """Проверяет, что при сбое стриминга модели НЕ возвращается заглушка, а отдается SSE с ошибкой."""
    async def broken_stream(prompt, **kwargs):
        raise RuntimeError("Quota exhausted or connection reset")
        yield "Never"

    with patch("src.ai.gemini.generative_ai.GoogleGenerativeAI.chat_stream", side_effect=broken_stream):
        res = api_client.post("/api/v1/diagnostics/chat", json={
            "table_type": "software",
            "title": "1a929d788c433ca314abe4a9b704e2d1",
            "question": "Как ограничить установку PWA?",
            "stream": True,
            "provider": "gemini",
            "enrich_wikillm": True
        })

        assert res.status_code == 200
        text = res.text
        # В ответе ДОЛЖНА быть ошибка
        assert '"error"' in text
        assert "Quota exhausted" in text
        # И КАТЕГОРИЧЕСКИ НЕ ДОЛЖНО БЫТЬ фейкового ответа
        assert "Экспертное заключение по сущности" not in text
        assert "выполняет стандартные задачи подсистемы" not in text


def test_chat_non_streaming_error_returns_error_json_without_fake_answer(api_client: TestClient) -> None:
    """Проверяет, что в не-стриминговом режиме ошибка возвращается в JSON без эвристического текста."""
    with patch("src.ai.gemini.generative_ai.GoogleGenerativeAI.ask", new_callable=AsyncMock) as mock_ask:
        mock_ask.side_effect = TimeoutError("Server timeout")

        res = api_client.post("/api/v1/diagnostics/chat", json={
            "table_type": "process",
            "title": "explorer.exe",
            "question": "Безопасен ли процесс?",
            "stream": False,
            "provider": "gemini",
            "enrich_wikillm": True
        })

        assert res.status_code == 200
        data = res.json()
        assert data.get("status") == "error"
        assert "error" in data
        assert "Server timeout" in data["error"]["message"]
        assert "Экспертный ответ по" not in data.get("answer", "")


def test_chat_force_refresh_bypasses_wikillm_cache(api_client: TestClient) -> None:
    """Проверяет, что при force_refresh=True кэш WikiLLM игнорируется и запрос уходит модели."""
    mock_entity = MagicMock()
    mock_claim = MagicMock()
    mock_claim.verified = True
    mock_claim.statement = "Вопрос: Как настроить политики?\nОтвет: Старый кэшированный ответ"
    mock_entity.claims = [mock_claim]
    mock_entity.name = "Chrome"
    mock_entity.category = "software"
    mock_entity.summary = "Google Chrome"

    async def fresh_stream(prompt, **kwargs):
        yield "Свежий ответ модели из LLM"

    with patch("apps.windows.wikillm.router.get_engine") as mock_get_engine, \
         patch("src.ai.gemini.generative_ai.GoogleGenerativeAI.chat_stream", side_effect=fresh_stream):
        mock_storage = MagicMock()
        mock_storage.get_entity.return_value = mock_entity
        mock_get_engine.return_value.storage = mock_storage

        # 1. Запрос с force_refresh=True должен обойти старый кэш
        res = api_client.post("/api/v1/diagnostics/chat", json={
            "table_type": "software",
            "title": "Chrome",
            "question": "Как настроить политики?",
            "stream": True,
            "force_refresh": True,
            "enrich_wikillm": False
        })

        assert res.status_code == 200
        assert "Свежий ответ модели из LLM" in res.text
        assert "Старый кэшированный ответ" not in res.text


def test_explain_incorporates_custom_question_into_prompt(api_client: TestClient) -> None:
    """Проверяет, что в explain_table_item переданный вопрос подмешивается в итоговый промпт."""
    captured_prompts = []

    async def mock_ask(prompt, **kwargs):
        captured_prompts.append(prompt)
        return json.dumps({
            "summary": "Анализ завершен",
            "developer": "Vendor",
            "category": "software",
            "security_verdict": "Безопасно",
            "performance_impact": "Норма",
            "recommendation": "Оставить",
            "action_steps": ["Шаг 1"]
        })

    with patch("src.ai.gemini.generative_ai.GoogleGenerativeAI.ask", side_effect=mock_ask):
        res = api_client.post("/api/v1/diagnostics/explain", json={
            "table_type": "software",
            "title": "CustomApp",
            "question": "Каковы сетевые риски этого приложения?",
            "web_search": False,
            "force_refresh": True
        })

        assert res.status_code == 200
        assert len(captured_prompts) == 1
        assert "Каковы сетевые риски этого приложения?" in captured_prompts[0]


def test_chat_converts_json_response_to_dialogue_format(api_client: TestClient) -> None:
    """Проверяет, что если модель вернула сырой JSON, он автоматически конвертируется в структурированный диалог."""
    json_response = json.dumps({
        "summary": "PWA-приложение сервиса Google Drive",
        "developer": "Google LLC",
        "category": "Веб-приложение",
        "security_verdict": "Низкий уровень риска, легитимно",
        "performance_impact": "Незначительное влияние на процессор и память",
        "recommendation": "Ограничить установку через групповые политики Chrome WebAppInstallForceList",
        "action_steps": [
            "Открыть редактор локальной групповой политики gpedit.msc",
            "Настроить политику ExtensionInstallBlocklist для браузера Chrome"
        ]
    })

    with patch("src.ai.gemini.generative_ai.GoogleGenerativeAI.ask", new_callable=AsyncMock) as mock_ask:
        mock_ask.return_value = json_response

        res = api_client.post("/api/v1/diagnostics/chat", json={
            "table_type": "software",
            "title": "Google Drive PWA",
            "question": "Как ограничить установку через GPO?",
            "stream": False,
            "force_refresh": True,
            "enrich_wikillm": False
        })

        assert res.status_code == 200
        data = res.json()
        assert data.get("status") == "ok"
        ans = data.get("answer", "")
        # Ответ не должен быть сырым JSON
        assert ans.startswith("{") is False
        # Ответ должен быть преобразован в человекочитаемый диалог
        assert "📌 **Назначение:** PWA-приложение сервиса Google Drive" in ans
        assert "🏢 **Разработчик:** Google LLC (Веб-приложение)" in ans
        assert "🛡️ **Безопасность:** Низкий уровень риска, легитимно" in ans
        assert "💡 **Рекомендация эксперта:** Ограничить установку" in ans
        assert "📋 **Рекомендуемые действия:**" in ans
        assert "• Открыть редактор локальной групповой политики gpedit.msc" in ans


def test_chat_converts_nested_analysis_report_json_to_dialogue(api_client: TestClient) -> None:
    """Проверяет, что сложный вложенный JSON ответа модели с analysis_report и technical_assessment конвертируется в диалог."""
    raw_model_reply = """``json
{
  "analysis_report": {
    "entity": "MsMpEng.exe",
    "pid": 5496,
    "issue_summary": "Аномальное количество потоков (1) для процесса Microsoft Defender.",
    "technical_assessment": "### Аналитический отчет: Состояние процесса MsMpEng.exe (PID 5496)\\n\\nШтатный процесс MsMpEng.exe спроектирован как многопоточная архитектура.\\n\\n1. Suspended State: поток может быть заблокирован.\\n2. Ошибка отображения: API не имеет прав доступа к Debug-информации.",
    "recommendation": "Выполнить проверку целостности sfc /scannow и перезапустить WinDefend"
  }
}
```"""

    with patch("src.ai.gemini.generative_ai.GoogleGenerativeAI.ask", new_callable=AsyncMock) as mock_ask:
        mock_ask.return_value = raw_model_reply

        res = api_client.post("/api/v1/diagnostics/chat", json={
            "table_type": "process",
            "title": "MsMpEng.exe",
            "question": "Почему MsMpEng.exe с PID 5496 ограничен одним потоком исполнения?",
            "stream": False,
            "force_refresh": True,
            "enrich_wikillm": False
        })

        assert res.status_code == 200
        data = res.json()
        assert data.get("status") == "ok"
        ans = data.get("answer", "")
        # Проверяем, что ответ не содержит сырой JSON и скобки схемы
        assert ans.startswith("{") is False
        assert '"analysis_report"' not in ans
        # Проверяем, что извлечены все ключевые блоки
        assert "🔍 **Сущность:** MsMpEng.exe (PID: 5496)" in ans
        assert "⚠️ **Суть проблемы:** Аномальное количество потоков (1) для процесса Microsoft Defender." in ans
        assert "### Аналитический отчет: Состояние процесса MsMpEng.exe (PID 5496)" in ans
        assert "Штатный процесс MsMpEng.exe спроектирован как многопоточная архитектура." in ans
        assert "💡 **Рекомендация эксперта:** Выполнить проверку целостности sfc /scannow и перезапустить WinDefend" in ans


def test_chat_removes_introductory_greetings_and_expert_preambles(api_client: TestClient) -> None:
    """Проверяет, что ритуальные приветствия и самопрезентации эксперта полностью удаляются из ответа модели."""
    from apps.windows.api.routers.router_diagnostics import clean_chat_greetings

    sample1 = (
        "Приветствую. Как эксперт по системному администрированию и безопасности Windows, я провел анализ "
        "установленного пакета Python 3.14.7 (Freethreaded) на вашей рабочей станции.\n\n"
        "Данный программный продукт является экспериментальной сборкой с поддержкой PEP 703 (free-threading)."
    )
    cleaned1 = clean_chat_greetings(sample1)
    assert not cleaned1.startswith("Приветствую")
    assert "Как эксперт по" not in cleaned1
    assert "я провел анализ" not in cleaned1
    assert cleaned1.startswith("Данный программный продукт является экспериментальной сборкой")

    sample2 = (
        "Приветствую. Как эксперт по системному администрированию Windows, я проанализировал представленные данные. "
        "Ситуация с отображением `msiexec.exe` в качестве источника исполнения и управление путями для экспериментальных сборок Python "
        "требует разъяснения ряда технических нюансов работы установщика Windows (Windows Installer)."
    )
    cleaned2 = clean_chat_greetings(sample2)
    assert not cleaned2.startswith("Приветствую")
    assert "Как эксперт по" not in cleaned2
    assert "я проанализировал" not in cleaned2
    assert cleaned2.startswith("Ситуация с отображением `msiexec.exe`")

    sample3 = (
        "Здравствуйте. Как системный инженер, я проанализировал представленные данные по установке Python 3.14.7 Freethreaded Interpreter.\n\n"
        "Для безопасного использования сборки рекомендуется изоляция виртуального окружения."
    )
    cleaned3 = clean_chat_greetings(sample3)
    assert not cleaned3.startswith("Здравствуйте")
    assert "Как системный инженер" not in cleaned3
    assert cleaned3.startswith("Для безопасного использования сборки")

    # Проверка через REST API эндпоинт /api/v1/diagnostics/chat
    with patch("src.ai.gemini.generative_ai.GoogleGenerativeAI.ask", new_callable=AsyncMock) as mock_ask:
        mock_ask.return_value = sample2

        res = api_client.post("/api/v1/diagnostics/chat", json={
            "table_type": "software",
            "title": "Python 3.14.7",
            "question": "Почему запись в реестре указывает на msiexec.exe как основной путь исполнения?",
            "stream": False,
            "force_refresh": True,
            "enrich_wikillm": False
        })

        assert res.status_code == 200
        data = res.json()
        ans = data.get("answer", "")
        assert "Приветствую" not in ans
        assert "Как эксперт" not in ans
        assert ans.startswith("Ситуация с отображением `msiexec.exe`")






