# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - LangGraph Scenarios and DAG Orchestration
# =============================================================================
# Description:
#   Интеграционные и модульные тесты для оркестратора автономных сценариев
#   на базе LangGraph DAG, двухуровневой памяти и интерактивной паузы (Спецификация 15).
#
# Usage Examples:
#   CLI:
#     pytest tests/test_langgraph_scenarios_and_dag.py -v
#
# File: test_langgraph_scenarios_and_dag.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 01:20:00
# =============================================================================

from __future__ import annotations

"""Тесты для оркестратора LangGraph DAG и Human-in-the-loop."""

import pytest
from fastapi.testclient import TestClient

from apps.windows.api.server import create_app
from apps.windows.api.routers.scenarios.dag_orchestrator import (
    DAGNodeStatus,
    DAGNodeType,
    LangGraphScenarioEngine,
    dag_engine,
)


@pytest.fixture
def standalone_engine() -> LangGraphScenarioEngine:
    """Фикстура изолированного движка сценариев."""
    return LangGraphScenarioEngine()


@pytest.fixture(scope="module")
def api_client() -> TestClient:
    """Фикстура клиента REST API."""
    app = create_app()
    return TestClient(app)


def test_dag_structure_and_node_types(standalone_engine: LangGraphScenarioEngine) -> None:
    """Проверяет корректность типов узлов и цветов (PROBE, USER_PROMPT, ACTION, VERDICT)."""
    nodes, edges = standalone_engine.build_standard_dag(
        scenario_id="test_service",
        title="Остановка тестовой службы",
        probe_desc="Проверка состояния службы",
        action_desc="Остановка процесса службы",
        requires_confirmation=True,
    )

    types = [n.type for n in nodes]
    assert types == [
        DAGNodeType.PROBE,
        DAGNodeType.USER_PROMPT,
        DAGNodeType.ACTION,
        DAGNodeType.VERDICT,
    ]

    # Цветовая индикация согласно спецификации 15:
    colors = {n.type: n.color for n in nodes}
    assert colors[DAGNodeType.PROBE] == "#0d6efd"        # Синий
    assert colors[DAGNodeType.USER_PROMPT] == "#ffc107"  # Желтый
    assert colors[DAGNodeType.ACTION] == "#6f42c1"       # Фиолетовый
    assert colors[DAGNodeType.VERDICT] == "#198754"      # Зеленый

    assert len(edges) == 3


def test_dag_human_in_the_loop_approval_flow(standalone_engine: LangGraphScenarioEngine) -> None:
    """Проверяет переход в состояние PAUSED и успешное завершение после санкции администратора (APPROVE)."""
    # 1. Запуск сценария с требованием подтверждения
    session = standalone_engine.start_scenario(
        scenario_id="service_stop_spooler",
        title="Остановка Spooler",
        requires_confirmation=True,
        confirmation_msg="Подтвердите остановку службы 'Spooler' (PID: 2048)",
    )

    assert session.status == "PAUSED_FOR_USER_CONFIRMATION"
    assert session.current_step == "step_2_user_prompt"
    assert session.confirmation_prompt is not None
    assert "Spooler" in session.confirmation_prompt.message

    # Узел PROBE выполнен, USER_PROMPT в паузе
    node_map = {n.id: n for n in session.nodes}
    assert node_map["step_1_probe"].status == DAGNodeStatus.SUCCESS
    assert node_map["step_2_user_prompt"].status == DAGNodeStatus.PAUSED

    # 2. Подтверждение администратора: APPROVE
    resumed = standalone_engine.confirm_scenario(session.session_id, action="approve")
    assert resumed is not None
    assert resumed.status == "COMPLETED"
    assert resumed.current_step == "step_4_verdict"
    assert resumed.confirmation_prompt is None

    updated_map = {n.id: n for n in resumed.nodes}
    assert updated_map["step_2_user_prompt"].status == DAGNodeStatus.SUCCESS
    assert updated_map["step_3_action"].status == DAGNodeStatus.SUCCESS
    assert updated_map["step_4_verdict"].status == DAGNodeStatus.SUCCESS


def test_dag_human_in_the_loop_rejection_flow(standalone_engine: LangGraphScenarioEngine) -> None:
    """Проверяет корректное отклонение действия администратором (REJECT)."""
    session = standalone_engine.start_scenario(
        scenario_id="firewall_block_port",
        title="Блокировка порта 443",
        requires_confirmation=True,
    )
    assert session.status == "PAUSED_FOR_USER_CONFIRMATION"

    rejected = standalone_engine.confirm_scenario(session.session_id, action="reject")
    assert rejected is not None
    assert rejected.status == "REJECTED"

    updated_map = {n.id: n for n in rejected.nodes}
    assert updated_map["step_2_user_prompt"].status == DAGNodeStatus.REJECTED
    assert updated_map["step_3_action"].status == DAGNodeStatus.SKIPPED
    assert updated_map["step_4_verdict"].status == DAGNodeStatus.REJECTED


def test_dag_api_endpoints(api_client: TestClient) -> None:
    """Проверяет REST API эндпоинты управления DAG-сценариями."""
    # 1. Запуск сценария
    payload = {
        "scenario_id": "test_api_dag_cleaner",
        "title": "Очистка временных файлов",
        "requires_confirmation": True,
        "confirmation_msg": "Удалить 500 МБ временных файлов?",
    }
    res_start = api_client.post("/api/v1/scenarios/dag/start", json=payload)
    assert res_start.status_code == 200
    data = res_start.json()
    assert "session_id" in data
    assert data["status"] == "PAUSED_FOR_USER_CONFIRMATION"
    session_id = data["session_id"]

    # 2. Получение снимка сессии
    res_get = api_client.get(f"/api/v1/scenarios/session/{session_id}")
    assert res_get.status_code == 200
    assert res_get.json()["session_id"] == session_id

    # 3. Список сессий
    res_list = api_client.get("/api/v1/scenarios/sessions")
    assert res_list.status_code == 200
    assert any(s["session_id"] == session_id for s in res_list.json())

    # 4. Подтверждение действия администратором
    res_confirm = api_client.post(
        f"/api/v1/scenarios/session/{session_id}/confirm",
        json={"action": "approve"},
    )
    assert res_confirm.status_code == 200
    assert res_confirm.json()["status"] == "COMPLETED"

