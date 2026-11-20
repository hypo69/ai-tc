# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Tests - AI Ecosystem Tab & APIs Integration
# =============================================================================
# Description:
#   Тесты доступности и целостности консолидированной панели «Экосистема ИИ»
#   (tab-ai-ecosystem), включая статические ассеты, эндпойнты агентов (/api/v1/agents),
#   навыков (/api/v1/skills) и MCP-серверов (/api/v1/mcp, /api/v1/admin/mcp).
#
# File: test_ai_ecosystem_tab.py
# Project: ai-tc
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20 16:45:00
# =============================================================================

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from apps.windows.api.server import create_app


@pytest.fixture(scope="module")
def api_client():
    """Фикстура TestClient для FastAPI сервиса."""
    app = create_app()
    return TestClient(app)


def test_ai_ecosystem_tab_assets_exist(api_client: TestClient):
    """Проверка отдачи HTML и JS для консолидированной вкладки tab_ai_ecosystem."""
    # HTML
    res_html = api_client.get("/html/tab_ai_ecosystem/index.html")
    assert res_html.status_code == 200, f"HTML tab_ai_ecosystem недоступен: {res_html.status_code}"
    html_text = res_html.text
    assert 'id="ai-agents-embed-container"' in html_text
    assert 'id="ai-skills-embed-container"' in html_text
    assert 'id="ai-mcp-embed-container"' in html_text

    # JS
    res_js = api_client.get("/html/tab_ai_ecosystem/main.js")
    assert res_js.status_code == 200, f"JS tab_ai_ecosystem недоступен: {res_js.status_code}"
    assert "initAiEcosystemTab" in res_js.text


def test_ai_agents_api_endpoints(api_client: TestClient):
    """Проверка REST API эндпойнтов управления агентами (/api/v1/agents)."""
    # 1. Список агентов и наличие релевантного sandbox_default_query у каждого агента
    res = api_client.get("/api/v1/agents")
    assert res.status_code == 200
    data = res.json()
    assert "agents" in data
    assert isinstance(data["agents"], list)
    assert len(data["agents"]) > 0
    for agent in data["agents"]:
        default_query = agent.get("sandbox_default_query")
        assert isinstance(default_query, str) and len(default_query.strip()) > 10, (
            f"У агента {agent.get('id')} отсутствует релевантный sandbox_default_query"
        )

    # 1.1 Тестовый запуск агента в Sandbox с параметром test_message (проверяем вызов реального исполнителя)
    sample_agent = data["agents"][0]
    mock_exec_result = {
        "status": "success",
        "agent_id": sample_agent["id"],
        "model": "gemini-3.5-flash-lite",
        "tools_count": len(sample_agent.get("tools", [])),
        "duration_ms": 420,
        "steps": [
            {"step": 1, "type": "tool_init", "content": "Инициализация агента"},
            {"step": 2, "type": "action", "content": "Вызов инструмента windows_services_list({})"},
            {"step": 3, "type": "finish", "content": "Ответ сформирован"},
        ],
        "response": "Диагностический отчёт: CPU 12%, RAM 45%, службы в норме.",
        "output": "Диагностический отчёт: CPU 12%, RAM 45%, службы в норме.",
    }
    with patch(
        "apps.windows.api.routers.router_agents.execute_agent_sandbox",
        new=AsyncMock(return_value=mock_exec_result),
    ) as mock_exec:
        res_test = api_client.post(
            "/api/v1/agents/test",
            json={
                "agent_id": sample_agent["id"],
                "test_message": sample_agent["sandbox_default_query"],
            },
        )
        assert res_test.status_code == 200
        test_data = res_test.json()
        assert test_data.get("status") == "success"
        assert test_data.get("duration_ms") == 420
        assert isinstance(test_data.get("steps"), list) and len(test_data["steps"]) == 3
        assert "Диагностический отчёт" in test_data.get("response", "")
        mock_exec.assert_awaited_once()

    # 1.2 Проверка клиентского скрипта песочницы на предзаполнение поля ввода
    res_sandbox_js = api_client.get("/html/tab_agents/panel_sandbox/panel.js")
    assert res_sandbox_js.status_code == 200
    assert "getRelevantSandboxQuery" in res_sandbox_js.text
    assert "input.value = relevantQuery" in res_sandbox_js.text

    # 2. Инструменты агентов
    res_tools = api_client.get("/api/v1/agents/tools")
    assert res_tools.status_code == 200
    assert "tools" in res_tools.json()

    # 3. Провайдеры моделей
    res_prov = api_client.get("/api/v1/agents/providers")
    assert res_prov.status_code == 200
    assert "providers" in res_prov.json()


def test_ai_skills_api_endpoints(api_client: TestClient):
    """Проверка REST API эндпойнта каталога навыков (/api/v1/skills)."""
    res = api_client.get("/api/v1/skills")
    assert res.status_code == 200, f"/api/v1/skills вернул {res.status_code}"
    data = res.json()
    assert "skills" in data
    assert isinstance(data["skills"], list)
    assert len(data["skills"]) > 0


def test_mcp_servers_api_endpoints(api_client: TestClient):
    """Проверка REST API эндпойнтов управления MCP-серверами."""
    # 1. /api/v1/mcp/servers
    res_mcp = api_client.get("/api/v1/mcp/servers")
    assert res_mcp.status_code == 200
    data_mcp = res_mcp.json()
    assert "servers" in data_mcp
    assert len(data_mcp["servers"]) > 0

    # 2. /api/v1/admin/mcp/servers
    res_admin_mcp = api_client.get("/api/v1/admin/mcp/servers")
    assert res_admin_mcp.status_code == 200
    assert "servers" in res_admin_mcp.json()

    # 3. /api/v1/admin/mcp/tools
    res_mcp_tools = api_client.get("/api/v1/admin/mcp/tools")
    assert res_mcp_tools.status_code == 200
    assert "tools" in res_mcp_tools.json()
