# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows SDK - Tool Chains Tests
# =============================================================================
# Description:
#   Модульные тесты для подсистемы цепочек инструментов Windows (Tool Chains).
#
# Usage Examples:
#   pytest apps/windows/sdk/core/tool_chains/tests/test_tool_chains.py
#
# File: test_tool_chains.py
# Package: apps.windows.sdk.core.tool_chains.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 17:35:00
# =============================================================================

from __future__ import annotations

import tempfile
import pytest
from apps.windows.contracts.enums import CapabilityCategory, ExecutionMethod, PrivilegeLevel, RiskLevel
from apps.windows.sdk.core.tool_chains.catalog import get_builtin_chains
from apps.windows.sdk.core.tool_chains.engine import ToolChainExecutionEngine
from apps.windows.sdk.core.tool_chains.models import (
    BranchCondition,
    ChainDefinition,
    ChainRunStatus,
    ChainStepDefinition,
    ConditionOperator,
    StepRunStatus,
)
from apps.windows.sdk.core.tool_chains.planner import ToolChainPlanner
from apps.windows.sdk.core.tool_chains.storage import ToolChainStorage


@pytest.fixture
def temp_storage():
    """Фикстура изолированного хранилища SQLite во временном файле."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    storage = ToolChainStorage(db_path=db_path)
    return storage


def test_storage_save_and_retrieve_definition(temp_storage):
    """Проверка сохранения и извлечения шаблона цепочки из SQLite."""
    chains = get_builtin_chains()
    sample_chain = list(chains.values())[0]

    assert temp_storage.save_definition(sample_chain) is True
    retrieved = temp_storage.get_definition(sample_chain.chain_id)
    assert retrieved is not None
    assert retrieved["chain_id"] == sample_chain.chain_id
    assert len(retrieved["steps"]) == len(sample_chain.steps)

    defs_list = temp_storage.list_definitions()
    assert len(defs_list) >= 1
    assert any(d["chain_id"] == sample_chain.chain_id for d in defs_list)


def test_planner_intent_matching():
    """Проверка сопоставления пользовательских намерений со встроенными шаблонами."""
    planner = ToolChainPlanner()

    # Проверка намерения проверки порта
    port_chain = planner.plan_from_intent("Проверь, почему сервис не отвечает на порту 9090")
    assert "port" in port_chain.chain_id or "network" in port_chain.chain_id
    assert port_chain.steps["check_tcp_listener"].arguments.get("port") == 9090

    # Проверка намерения SSD скачков записи
    ssd_chain = planner.plan_from_intent("Выясни причину резких скачков записи на SSD")
    assert "ssd_write_spikes" in ssd_chain.chain_id
    assert len(ssd_chain.steps) >= 3

    # Проверка динамического синтеза
    dyn_chain = planner.plan_from_intent("Диагностика драйвера графического адаптера и монитора")
    assert dyn_chain.chain_id.startswith("synthesized.")
    assert len(dyn_chain.steps) >= 1


@pytest.mark.asyncio
async def test_execution_engine_dry_run(temp_storage):
    """Проверка пошагового исполнения цепочки в режиме Dry-Run."""
    engine = ToolChainExecutionEngine(storage=temp_storage)
    chains = get_builtin_chains()
    port_chain = chains["diag.network.port_availability"]

    report = await engine.execute_chain(
        chain=port_chain,
        user_intent="Тестовый прогон проверки порта 8001",
        dry_run=True,
    )

    assert report.status in (ChainRunStatus.COMPLETED, ChainRunStatus.RUNNING)
    assert len(report.steps_executed) >= 1
    assert report.total_duration_ms >= 0.0
    assert report.run_id.startswith("run_")

    # Проверяем, что запуск сохранился в базе данных
    saved_run = temp_storage.get_run(report.run_id)
    assert saved_run is not None
    assert saved_run["run_id"] == report.run_id


@pytest.mark.asyncio
async def test_branching_conditions_evaluation(temp_storage):
    """Проверка корректности работы динамического ветвления шагов."""
    engine = ToolChainExecutionEngine(storage=temp_storage)

    # Создаем простую цепочку с ветвлением
    test_chain = ChainDefinition(
        chain_id="test.branching.chain",
        title_ru="Тестовая цепочка с условием ветвления",
        description="Тест ветвления",
        category=CapabilityCategory.PROCESSES,
        initial_step_id="step_a",
        steps={
            "step_a": ChainStepDefinition(
                step_id="step_a",
                tool_id="systeminfo.query",
                name_ru="Шаг А",
                description="Первый шаг",
                branch_conditions=[
                    BranchCondition(
                        operator=ConditionOperator.EXIT_CODE_ZERO,
                        target_step_id="step_success",
                    ),
                    BranchCondition(
                        operator=ConditionOperator.ALWAYS_TRUE,
                        target_step_id="step_fallback",
                    ),
                ],
                next_step_id="step_fallback",
            ),
            "step_success": ChainStepDefinition(
                step_id="step_success",
                tool_id="tasklist.list",
                name_ru="Шаг успеха",
                description="Ветка успеха",
                next_step_id=None,
            ),
            "step_fallback": ChainStepDefinition(
                step_id="step_fallback",
                tool_id="netstat.connections",
                name_ru="Шаг фолбэка",
                description="Ветка фолбэка",
                next_step_id=None,
            ),
        },
    )

    report = await engine.execute_chain(test_chain, dry_run=True)
    assert report.status == ChainRunStatus.COMPLETED
    executed_ids = [s.step_id for s in report.steps_executed]
    assert "step_a" in executed_ids
    assert "step_success" in executed_ids
    assert "step_fallback" not in executed_ids

