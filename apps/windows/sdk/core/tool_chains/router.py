# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows SDK - Tool Chains Router
# =============================================================================
# Description:
#   FastAPI REST API роутер для планирования и запуска цепочек инструментов Windows.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.core.tool_chains.router import router as toolchains_router
#
# File: router.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.core.tool_chains
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 17:35:00
# =============================================================================

from __future__ import annotations

"""FastAPI REST API маршрутизатор для планирования и запуска цепочек инструментов."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from logger import logger

from apps.windows.sdk.core.tool_chains.catalog import get_builtin_chains
from apps.windows.sdk.core.tool_chains.engine import ToolChainExecutionEngine
from apps.windows.sdk.core.tool_chains.models import (
    PlanChainApiRequest,
    RunChainApiRequest,
)
from apps.windows.sdk.core.tool_chains.planner import ToolChainPlanner
from apps.windows.sdk.core.tool_chains.storage import ToolChainStorage

router = APIRouter(prefix="/api/v1/toolchains", tags=["Windows Tool Chains"])

_storage = ToolChainStorage()
_engine = ToolChainExecutionEngine(storage=_storage)
_planner = ToolChainPlanner()

# Автоматическая регистрация встроенных шаблонов при инициализации
for builtin_chain in get_builtin_chains().values():
    _storage.save_definition(builtin_chain)


@router.get("/templates", summary="Список доступных шаблонов цепочек")
def list_chain_templates() -> List[Dict[str, Any]]:
    """Возвращает список всех зарегистрированных шаблонов диагностических цепочек."""
    return _storage.list_definitions()


@router.get("/templates/{chain_id}", summary="Получение шаблона цепочки по ID")
def get_chain_template(chain_id: str) -> Dict[str, Any]:
    """Возвращает детальную схему цепочки инструментов с графом шагов."""
    definition = _storage.get_definition(chain_id)
    if not definition:
        raise HTTPException(status_code=404, detail=f"Шаблон цепочки '{chain_id}' не найден")
    return definition


@router.post("/plan", summary="Семантическое планирование цепочки из запроса")
def plan_chain(request: PlanChainApiRequest) -> Dict[str, Any]:
    """Преобразует пользовательский симптом или задачу в структурированный граф шагов."""
    try:
        chain_def = _planner.plan_from_intent(request.user_intent, max_steps=request.max_steps)
        return chain_def.to_dict()
    except Exception as e:
        logger.error(f"Ошибка планирования цепочки: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка планирования цепочки: {str(e)}")


@router.post("/run", summary="Запуск цепочки инструментов")
async def run_tool_chain(request: RunChainApiRequest) -> Dict[str, Any]:
    """Запускает выполнение цепочки инструментов (по ID или синтезирует по намерению)."""
    try:
        if request.chain_id:
            raw_def = _storage.get_definition(request.chain_id)
            if not raw_def:
                builtin = get_builtin_chains().get(request.chain_id)
                if builtin:
                    chain_def = builtin
                else:
                    raise HTTPException(status_code=404, detail=f"Цепочка '{request.chain_id}' не найдена")
            else:
                from apps.windows.contracts.enums import CapabilityCategory
                from apps.windows.sdk.core.tool_chains.models import ChainDefinition, ChainStepDefinition
                # Восстановление ChainDefinition из JSON
                steps_dict = {}
                for s_id, s_data in raw_def.get("steps", {}).items():
                    steps_dict[s_id] = ChainStepDefinition(
                        step_id=s_data["step_id"],
                        tool_id=s_data["tool_id"],
                        name_ru=s_data.get("name_ru", s_id),
                        description=s_data.get("description", ""),
                        arguments=s_data.get("arguments", {}),
                        next_step_id=s_data.get("next_step_id"),
                    )
                chain_def = ChainDefinition(
                    chain_id=raw_def["chain_id"],
                    title_ru=raw_def["title_ru"],
                    description=raw_def.get("description", ""),
                    category=CapabilityCategory(raw_def.get("category", "general")),
                    initial_step_id=raw_def["initial_step_id"],
                    steps=steps_dict,
                )
        elif request.user_intent:
            chain_def = _planner.plan_from_intent(request.user_intent)
        else:
            raise HTTPException(status_code=400, detail="Необходимо указать 'chain_id' или 'user_intent'")

        report = await _engine.execute_chain(
            chain=chain_def,
            user_intent=request.user_intent or chain_def.title_ru,
            dry_run=request.dry_run,
            create_restore_point=request.create_restore_point,
            custom_arguments=request.custom_arguments,
        )
        return report.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка исполнения цепочки инструментов: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка исполнения: {str(e)}")


@router.get("/runs", summary="Список недавних запусков цепочек")
def list_recent_runs(limit: int = Query(20, ge=1, le=100)) -> List[Dict[str, Any]]:
    """Возвращает историю запусков цепочек с их статусами."""
    return _storage.list_recent_runs(limit=limit)


@router.get("/runs/{run_id}", summary="Получение полного отчёта о запуске")
def get_run_report(run_id: str) -> Dict[str, Any]:
    """Возвращает подробный отчет о запуске с таймлайном каждого шага и доказательствами."""
    report = _storage.get_run(run_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Отчет о запуске '{run_id}' не найден")
    return report

