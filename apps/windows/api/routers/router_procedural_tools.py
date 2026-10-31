# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows API - Router Procedural Tools
# =============================================================================
# Description:
#   REST API эндпоинты для управления динамическими инструментами и процедурной
#   памятью WikiLLM (Self-Evolving Agent & Dynamic Tool Synthesis).
#
# Usage Examples:
#   Python API:
#     from apps.windows.api.routers.router_procedural_tools import init_router
#
#     router = init_router()
#
# File: router_procedural_tools.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-14 03:33:00
# =============================================================================

from __future__ import annotations

"""REST API эндпоинты для процедурной памяти WikiLLM и выполнения динамических инструментов."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from logger import logger
from apps.windows.wikillm.procedural_service import ProceduralWikiLLMService


class SaveProceduralToolRequest(BaseModel):
    """Схема запроса на сохранение инструмента."""
    tool_id: Optional[str] = Field(None, description="Идентификатор инструмента")
    canonical_key: Optional[str] = Field(None, description="Канонический ключ (например 'procedural:print_doc')")
    title: str = Field(..., description="Название инструмента")
    description: str = Field(..., description="Описание назначения инструмента")
    language: str = Field("python", description="Язык программирования")
    entry_point: str = Field("run", description="Имя точки входа")
    input_schema: Dict[str, Any] = Field(default_factory=dict, description="JSON-схема параметров")
    code_payload: str = Field(..., description="Исходный код модуля")
    author_agent: str = Field("gemini", description="Агент-автор")
    tags: List[str] = Field(default_factory=lambda: ["#procedural"], description="Теги")


class ExecuteProceduralToolRequest(BaseModel):
    """Схема запроса на выполнение инструмента."""
    tool_id: str = Field(..., description="ID инструмента или canonical_key")
    args: Dict[str, Any] = Field(default_factory=dict, description="Входные параметры")


class LookupProceduralToolRequest(BaseModel):
    """Схема запроса на поиск инструмента."""
    query: str = Field(..., description="Поисковый запрос или ключ")
    tags: Optional[List[str]] = Field(None, description="Список тегов для фильтрации")


class SynthesizeAndRunRequest(BaseModel):
    """Схема запроса на динамический синтез и выполнение."""
    intent: str = Field(..., description="Намерение или задача (например 'print_report')")
    args: Dict[str, Any] = Field(default_factory=dict, description="Аргументы")
    tags: Optional[List[str]] = Field(None, description="Теги для классификации")
    author_agent: str = Field("gemini-2.5-flash", description="Агент-автор")


def init_router(service: Optional[ProceduralWikiLLMService] = None) -> APIRouter:
    """Инициализирует и возвращает FastAPI APIRouter для процедурных инструментов.

    Args:
        service: Экземпляр сервиса процедурной памяти или None.

    Returns:
        APIRouter: Сконфигурированный роутер.
    """
    router = APIRouter(prefix="/api/v1/procedural-tools", tags=["procedural-tools"])
    srv = service or ProceduralWikiLLMService()

    @router.get("", response_model=Dict[str, Any])
    async def list_procedural_tools(
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
    ) -> Dict[str, Any]:
        """Возвращает каталог процедурных модулей из WikiLLM."""
        tools = srv.list_tools(limit=limit, offset=offset)
        return {"status": "ok", "total": len(tools), "items": tools}

    @router.get("/{tool_id}", response_model=Dict[str, Any])
    async def get_procedural_tool(tool_id: str) -> Dict[str, Any]:
        """Возвращает информацию о процедурном инструменте по ID."""
        tool = srv.get_tool(tool_id)
        if not tool:
            raise HTTPException(status_code=404, detail=f"Инструмент '{tool_id}' не найден")
        return {"status": "ok", "item": tool}

    @router.post("/save", response_model=Dict[str, Any])
    async def save_procedural_tool(payload: SaveProceduralToolRequest) -> Dict[str, Any]:
        """Сохраняет процедурный модуль в базу данных WikiLLM."""
        try:
            saved = srv.save_tool(payload.model_dump())
            return {"status": "ok", "item": saved}
        except Exception as ex:
            logger.error(f"[router_procedural_tools] Ошибка сохранения инструмента: {ex}")
            raise HTTPException(status_code=500, detail=str(ex))

    @router.post("/execute", response_model=Dict[str, Any])
    async def execute_procedural_tool(payload: ExecuteProceduralToolRequest) -> Dict[str, Any]:
        """Исполняет зарегистрированный в WikiLLM инструмент через DynamicToolRunner."""
        res = srv.execute_tool(payload.tool_id, payload.args)
        if res.get("status") == "error":
            raise HTTPException(status_code=400, detail=res.get("error", "Ошибка исполнения"))
        return {"status": "ok", "result": res.get("output")}

    @router.post("/lookup", response_model=Dict[str, Any])
    async def lookup_procedural_tool(payload: LookupProceduralToolRequest) -> Dict[str, Any]:
        """Ищет инструмент в процедурной памяти по каноническому ключу или тегам."""
        found = srv.lookup_tool(payload.query, payload.tags)
        return {"status": "ok", "found": found is not None, "item": found}

    @router.post("/synthesize-and-run", response_model=Dict[str, Any])
    async def synthesize_and_run(payload: SynthesizeAndRunRequest) -> Dict[str, Any]:
        """Выполняет полный цикл самообучения (поиск в WikiLLM -> синтез -> песочница -> сохранение)."""
        res = srv.synthesize_and_execute(
            intent=payload.intent,
            args=payload.args,
            tags=payload.tags,
            author_agent=payload.author_agent,
        )
        return res

    @router.delete("/{tool_id}", response_model=Dict[str, Any])
    async def delete_procedural_tool(tool_id: str) -> Dict[str, Any]:
        """Удаляет инструмент из процедурной памяти."""
        success = srv.delete_tool(tool_id)
        if not success:
            raise HTTPException(status_code=404, detail="Инструмент не найден для удаления")
        return {"status": "ok", "deleted": True}

    return router


__all__ = ["init_router"]

