# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Code Helper - FastAPI REST API Router
# =============================================================================
# Description:
#   FastAPI роутер для автономного микроприложения Code Helper.
#   Предоставляет REST API для управления базой знаний кода, AST-поиска,
#   диагностики и проверки статуса подключения к Hostinger MariaDB.
#
# File: router.py
# Project: ai-windows-admin
# Package: apps.code_helper
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 17:10:00
# =============================================================================

from __future__ import annotations

"""FastAPI REST API роутер для автономного приложения Code Helper."""

import asyncio
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException

from logger import logger
from .models import (
    BuildIndexRequest,
    DiagnoseRequest,
    DiagnosticConclusion,
    IndexStats,
    SearchRequest,
    SymbolSearchRequest,
)
from .rag import CodeHelperRAG

router = APIRouter(prefix="/api/code-helper", tags=["Code Helper RAG"])
_rag_instance: Optional[CodeHelperRAG] = None


def get_rag() -> CodeHelperRAG:
    """Возвращает или инициализирует глобальный экземпляр CodeHelperRAG."""
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = CodeHelperRAG()
    return _rag_instance


def init_router(rag: Optional[CodeHelperRAG] = None) -> APIRouter:
    """Инициализирует роутер с опционально переданным экземпляром CodeHelperRAG."""
    global _rag_instance
    if rag is not None:
        _rag_instance = rag
    return router


@router.get("/status")
async def get_status() -> Dict[str, Any]:
    """Возвращает текущий статус хранилища, движка и базы знаний."""
    rag = get_rag()
    conn_info = await asyncio.to_thread(rag.storage.test_connection)
    indexes = await asyncio.to_thread(rag.storage.list_indexes)
    return {
        "status": "online",
        "app": "code_helper",
        "active_engine": rag.storage.active_engine,
        "database_info": conn_info,
        "total_indexes": len(indexes),
        "indexes": indexes,
    }


@router.post("/db/test")
async def test_database_connection() -> Dict[str, Any]:
    """Выполняет прямое тестирование соединения с MariaDB на Hostinger."""
    rag = get_rag()
    return await asyncio.to_thread(rag.storage.test_connection)


@router.get("/indexes")
async def list_indexes() -> Dict[str, Any]:
    """Возвращает список всех зарегистрированных AST-индексов кодовой базы."""
    rag = get_rag()
    indexes = await asyncio.to_thread(rag.storage.list_indexes)
    return {"indexes": indexes, "total": len(indexes)}


@router.post("/build", response_model=IndexStats)
async def build_index(req: BuildIndexRequest) -> IndexStats:
    """Запускает сканирование и построение индекса в Hostinger MariaDB / SQLite."""
    rag = get_rag()
    try:
        stats = await asyncio.to_thread(
            rag.build_index,
            project_root=req.project_root,
            index_name=req.index_name,
            include_dirs=req.include_dirs,
            include_markdown=req.include_markdown,
        )
        return stats
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error(f"[CodeHelperRouter] Ошибка построения индекса: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/search")
async def search_code(req: SearchRequest) -> Dict[str, Any]:
    """Семантический и ключевой поиск по чанкам кода и документации."""
    rag = get_rag()
    results = await asyncio.to_thread(
        rag.search_code,
        query=req.query,
        index_name=req.index_name,
        top_k=req.top_k,
    )
    return {"results": results, "total_found": len(results)}


@router.post("/symbols")
async def search_symbols(req: SymbolSearchRequest) -> Dict[str, Any]:
    """Поиск классов, функций и методов по AST-таблице символов."""
    rag = get_rag()
    results = await asyncio.to_thread(
        rag.search_symbols,
        symbol_query=req.symbol,
        index_name=req.index_name,
        limit=req.limit,
    )
    return {"results": results, "total_found": len(results)}


@router.post("/diagnose", response_model=DiagnosticConclusion)
async def diagnose_code(req: DiagnoseRequest) -> DiagnosticConclusion:
    """Формирует структурированное диагностическое заключение по вопросу, логам или ошибке."""
    if not req.question.strip() and not req.error_message.strip() and not req.logs:
        raise HTTPException(
            status_code=400,
            detail="Необходимо указать question, logs или error_message для формирования заключения.",
        )
    rag = get_rag()
    return await rag.diagnose(
        question=req.question,
        logs=req.logs,
        error_message=req.error_message,
        index_name=req.index_name,
        top_k=req.top_k,
        use_llm=req.use_llm,
    )
