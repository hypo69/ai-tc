# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Tests - AI Ecosystem Tab & APIs Integration
# =============================================================================
# Description:
#   Тесты доступности и целостности консолидированной панели «Экосистема ИИ»
#   (tab-ai-ecosystem), включая статические ассеты, эндпойнты агентов (/api/agents),
#   навыков (/api/skills) и MCP-серверов (/api/mcp, /api/admin/mcp).
#
# File: test_ai_ecosystem_tab.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-30 11:15:00
# =============================================================================

from __future__ import annotations

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
    """Проверка REST API эндпойнтов управления агентами (/api/agents)."""
    # 1. Список агентов
    res = api_client.get("/api/agents")
    assert res.status_code == 200
    data = res.json()
    assert "agents" in data
    assert isinstance(data["agents"], list)
    assert len(data["agents"]) > 0

    # 2. Инструменты агентов
    res_tools = api_client.get("/api/agents/tools")
    assert res_tools.status_code == 200
    assert "tools" in res_tools.json()

    # 3. Провайдеры моделей
    res_prov = api_client.get("/api/agents/providers")
    assert res_prov.status_code == 200
    assert "providers" in res_prov.json()


def test_ai_skills_api_endpoints(api_client: TestClient):
    """Проверка REST API эндпойнта каталога навыков (/api/skills)."""
    res = api_client.get("/api/skills")
    assert res.status_code == 200, f"/api/skills вернул {res.status_code}"
    data = res.json()
    assert "skills" in data
    assert isinstance(data["skills"], list)
    assert len(data["skills"]) > 0


def test_mcp_servers_api_endpoints(api_client: TestClient):
    """Проверка REST API эндпойнтов управления MCP-серверами."""
    # 1. /api/mcp/servers
    res_mcp = api_client.get("/api/mcp/servers")
    assert res_mcp.status_code == 200
    data_mcp = res_mcp.json()
    assert "servers" in data_mcp
    assert len(data_mcp["servers"]) > 0

    # 2. /api/admin/mcp/servers
    res_admin_mcp = api_client.get("/api/admin/mcp/servers")
    assert res_admin_mcp.status_code == 200
    assert "servers" in res_admin_mcp.json()

    # 3. /api/admin/mcp/tools
    res_mcp_tools = api_client.get("/api/admin/mcp/tools")
    assert res_mcp_tools.status_code == 200
    assert "tools" in res_mcp_tools.json()
