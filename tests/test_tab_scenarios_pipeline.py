"""
=============================================================================
Модуль тестирования: Пайплайн вкладки сценариев (tab_scenarios)
=============================================================================
Описание:
  Проверка интеграции вкладки tab_scenarios с API UniversalLangChainAgent:
  - Генерация 3 динамических вопросов (/api/v1/diagnostics/suggest-questions)
  - Потоковый диалог через SSE (/api/v1/diagnostics/chat)
  - Интерактивное безопасное исполнение PowerShell (/api/v1/diagnostics/execute-powershell)

Файл: tests/test_tab_scenarios_pipeline.py
Автор: hypo69
Updated: 2026-10-22 03:50:00
=============================================================================
"""

import pytest
from fastapi.testclient import TestClient
from apps.windows.api.server import app


@pytest.fixture
def client():
    """Тестовый клиент FastAPI приложения."""
    return TestClient(app)


def test_tab_scenarios_suggest_questions(client):
    """
    Проверяет успешное получение 3 актуальных диагностических вопросов хоста
    для вкладки tab_scenarios (контекст panel-scenarios).
    """
    response = client.post(
        "/api/v1/diagnostics/suggest-questions",
        json={
            "table_type": "scenarios",
            "panel_id": "panel-scenarios",
            "title": "Сценарии тестирования и автоматизации",
            "subtitle": "Интерактивная диагностика и решение задач хоста",
            "force_refresh": False,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "questions" in data
    assert isinstance(data["questions"], list)
    assert len(data["questions"]) == 3
    for q in data["questions"]:
        assert isinstance(q, str)
        assert len(q.strip()) > 0


def test_tab_scenarios_chat_stream_headers(client):
    """
    Проверяет, что запрос к /api/v1/diagnostics/chat для вкладки tab_scenarios
    возвращает потоковый SSE-ответ с заголовком text/event-stream.
    """
    response = client.post(
        "/api/v1/diagnostics/chat",
        json={
            "prompt": "Оцени свободное место на дисках",
            "stream": True,
            "table_type": "scenarios",
            "panel_id": "panel-scenarios",
            "context": {
                "title": "Сценарии тестирования и автоматизации",
                "tab_id": "tab_scenarios",
            },
        },
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")


def test_tab_scenarios_execute_powershell_endpoint(client):
    """
    Проверяет безопасное исполнение тестовой команды PowerShell на хосте.
    """
    response = client.post(
        "/api/v1/diagnostics/execute-powershell",
        json={
            "command": "Write-Output 'Pipelined Tab Scenarios OK'",
            "timeout_sec": 15,
            "shell": "powershell",
            "as_admin": False,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data.get("success") is True
    assert "Pipelined Tab Scenarios OK" in data.get("stdout", "")

