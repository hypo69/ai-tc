# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - UniversalLangChainAgent
# =============================================================================
# Description:
#   Модульные тесты для UniversalLangChainAgent: проверка наличия и активации
#   LangGraph-адаптера, генерации Pydantic-схем StructuredTool, потокового
#   вывода SSE-событий и резервного перехода на прямой ReAct-цикл.
#
# Usage Examples:
#   CLI:
#     pytest tests/test_universal_langchain_agent.py -v
#
# File: test_universal_langchain_agent.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-11 23:39:00
# =============================================================================

from __future__ import annotations

"""Тесты LangGraph-адаптера и ReAct-цикла UniversalLangChainAgent."""

from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

from apps.windows.sdk.core.universal_langchain_agent import UniversalLangChainAgent


def test_langgraph_and_langchain_dependencies_available() -> None:
    """Проверяет доступность пакетов langgraph и langchain_google_genai в текущем окружении."""
    from langgraph.prebuilt import create_react_agent
    from langchain_core.tools import StructuredTool
    from langchain_google_genai import ChatGoogleGenerativeAI

    assert callable(create_react_agent)
    assert StructuredTool is not None
    assert ChatGoogleGenerativeAI is not None


def test_build_langchain_tools_generates_valid_schemas() -> None:
    """Проверяет построение StructuredTool и Pydantic-схем из реестра ToolRegistry."""
    agent = UniversalLangChainAgent(model_name="gemini-2.5-flash")
    tools, name_map = agent._build_langchain_tools()

    assert len(tools) >= 4
    names = {t.name for t in tools}
    assert "windows_collector" in names
    assert "create_custom_tool" in names
    assert name_map["windows_collector"] == "windows_collector"

    wc_tool = next(t for t in tools if t.name == "windows_collector")
    schema = wc_tool.args_schema.model_json_schema()
    assert "collector_name" in schema.get("properties", {})
    assert "collector_name" in schema.get("required", [])


@pytest.mark.asyncio
async def test_stream_solve_uses_native_langgraph_when_available() -> None:
    """Проверяет активацию и потоковое исполнение нативного графа LangGraph в stream_solve."""
    agent = UniversalLangChainAgent(model_name="gemini-2.5-flash")
    fake_llm = MagicMock()

    tool_call_msg = MagicMock()
    tool_call_msg.tool_calls = [{"name": "windows_collector", "args": {"collector_name": "services"}}]
    tool_call_msg.type = "ai"

    tool_result_msg = MagicMock()
    tool_result_msg.tool_calls = []
    tool_result_msg.type = "tool"
    tool_result_msg.name = "windows_collector"
    tool_result_msg.content = '{"services": ["wuauserv"]}'

    final_ai_msg = MagicMock()
    final_ai_msg.tool_calls = []
    final_ai_msg.type = "ai"
    final_ai_msg.content = (
        "### Итог\nСлужба обновлений активна.\n\n"
        '```action\n{"action_id": "check_svc", "title": "Проверить", "description": "Опрос", "execution_command": "Get-Service wuauserv"}\n```'
    )

    async def fake_astream(*args: Any, **kwargs: Any):
        yield {"agent": {"messages": [tool_call_msg]}}
        yield {"tools": {"messages": [tool_result_msg]}}
        yield {"agent": {"messages": [final_ai_msg]}}

    fake_graph = MagicMock()
    fake_graph.astream = fake_astream

    with (
        patch.object(agent, "_init_llm", return_value=fake_llm),
        patch("langgraph.prebuilt.create_react_agent", return_value=fake_graph) as mock_factory,
    ):
        events: List[Dict[str, Any]] = []
        async for ev in agent.stream_solve("Проверь службу обновлений"):
            events.append(ev)

    assert mock_factory.called
    ev_types = [e["type"] for e in events]
    assert "tool_call" in ev_types
    assert "tool_result" in ev_types
    assert "token" in ev_types
    assert "action" in ev_types
    assert events[-1]["type"] == "status"
    assert "завершено" in events[-1]["text"].lower()


@pytest.mark.asyncio
async def test_stream_solve_falls_back_to_direct_react_on_langgraph_error() -> None:
    """Проверяет резервный переход на прямой ReAct при ошибке LangGraph-адаптера."""
    agent = UniversalLangChainAgent(model_name="gemini-2.5-flash")

    async def fake_llm_astream(prompt: str):
        chunk = MagicMock()
        chunk.content = (
            "### Диагностика\n"
            "Проверка выполнена напрямую через резервный ReAct-цикл без вызова инструментов, "
            "все параметры системы находятся в штатном состоянии."
        )
        yield chunk

    fake_llm = MagicMock()
    fake_llm.astream = fake_llm_astream

    fake_graph = MagicMock()
    fake_graph.astream = MagicMock(side_effect=RuntimeError("simulated langgraph error"))

    with (
        patch.object(agent, "_init_llm", return_value=fake_llm),
        patch("langgraph.prebuilt.create_react_agent", return_value=fake_graph),
    ):
        events: List[Dict[str, Any]] = []
        async for ev in agent.stream_solve("Тест fallback"):
            events.append(ev)

    tokens = "".join(e["chunk"] for e in events if e.get("type") == "token")
    assert "резервный ReAct-цикл" in tokens
