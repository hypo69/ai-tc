# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin AI - Unified RAG Router
# =============================================================================
# Description:
#   FastAPI REST API роутер для унифицированного RAG, Pixel RAG и базы знаний.
#
# Usage Examples:
#   Python API:
#     from src.ai.rag.router import init_router
#
#     router = init_router()
#
# File: router.py
# Project: ai-windows-admin
# Package: src.ai.rag
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 17:33:00
# =============================================================================

from __future__ import annotations
"""FastAPI REST API роутер для RAG, Pixel RAG, Codebase RAG и Unified Knowledge Hub."""

import asyncio
import base64
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from logger import logger
from .codebase_rag import CodeDiagnosticConclusion
from .unified_hub import UnifiedKnowledgeHub
from .text_rag import TextRAG
from .pixel_rag import PixelRAG

router = APIRouter(prefix="/api/rag", tags=["Unified RAG & Knowledge Hub"])
_hub_instance: Any = False
_MAX_UPLOAD_IMAGE_BYTES = 25 * 1024 * 1024


def get_hub() -> UnifiedKnowledgeHub:
    """Возвращает или инициализирует глобальный экземпляр UnifiedKnowledgeHub."""
    global _hub_instance
    if not _hub_instance:
        _hub_instance = UnifiedKnowledgeHub()
    return _hub_instance


class RagSearchRequest(BaseModel):
    """Схема запроса поиска по RAG."""
    query: str = Field(..., description="Поисковый запрос")
    top_k: int = Field(default=5, ge=1, le=50, description="Максимум результатов")
    threshold: float = Field(default=0.0, ge=0.0, le=1.0, description="Порог схожести")


class PixelSearchRequest(BaseModel):
    """Схема запроса поиска по Pixel RAG."""
    query: str = Field(..., description="Текстовый запрос или описание")
    top_k: int = Field(default=5, ge=1, le=50, description="Максимум результатов")


class UnifiedResolveRequest(BaseModel):
    """Схема сквозного разрешения артефакта через Unified Knowledge Hub."""
    query: str = Field(..., description="Код ошибки, команда, симптом или запрос")
    image_base64: Optional[str] = Field(default="", description="Опциональный скриншот в base64")
    sync_gemini: bool = Field(default=True, description="Вызывать ли Gemini при отсутствии в кэше")
    top_k: int = Field(default=5, description="Лимит связанных сниппетов")


class CodebaseBuildRequest(BaseModel):
    """Схема запроса на построение AST-индекса кодовой базы."""
    project_root: str = Field(default=".", description="Корневой каталог проекта")
    index_name: str = Field(default="codebase", description="Имя создаваемого индекса")
    include_dirs: List[str] = Field(default_factory=list, description="Опциональный фильтр поддиректорий")
    include_markdown: bool = Field(default=True, description="Индексировать ли документацию .md")


class CodebaseSearchRequest(BaseModel):
    """Схема запроса гибридного поиска по чанкам кода."""
    query: str = Field(..., description="Поисковый запрос, ошибка или фрагмент лога")
    index_name: str = Field(default="codebase", description="Имя целевого индекса")
    top_k: int = Field(default=5, ge=1, le=50, description="Лимит возвращаемых фрагментов")


class CodebaseSymbolRequest(BaseModel):
    """Схема запроса поиска по таблице AST-символов."""
    symbol: str = Field(..., description="Имя или префикс функции/класса/метода")
    index_name: str = Field(default="codebase", description="Имя целевого индекса")
    limit: int = Field(default=10, ge=1, le=100, description="Лимит результатов")


class CodebaseDiagnoseRequest(BaseModel):
    """Схема запроса диагностики вопроса, логов или ошибки по базе знаний о коде."""
    question: str = Field(default="", description="Вопрос по коду или архитектуре")
    logs: List[str] = Field(default_factory=list, description="Список строк логов или событий")
    error_message: str = Field(default="", description="Сообщение об ошибке или Traceback")
    index_name: str = Field(default="codebase", description="Имя индекса кодовой базы")
    top_k: int = Field(default=6, ge=1, le=25, description="Количество фрагментов кода для контекста")
    use_llm: bool = Field(default=True, description="Синтезировать ли заключение через LLM при доступности")


@router.get("/status")
async def get_rag_status() -> Dict[str, Any]:
    """Возвращает метрики и статус глобального индекса RAG."""
    hub = get_hub()
    metrics = await asyncio.to_thread(hub.get_metrics)
    text_count = metrics["text_rag"]["total_documents"]
    pixel_count = metrics["pixel_rag"]["total_images"]
    log_count = metrics["log_rag"]["total_chunks"]

    return {
        "total_documents": text_count,
        "total_chunks": text_count + pixel_count + log_count,
        "total_size_mb": metrics["pixel_rag"]["total_size_mb"],
        "provider": "Gemini Embedding-2 / FAISS / WikiLLM",
        "last_built_at": metrics["pixel_rag"]["last_built_at"],
        "sources": {
            "global_docs": text_count,
            "images": pixel_count,
            "log_chunks": log_count,
            "wiki_entities": metrics["wikillm"]["total_entities"],
        },
    }


@router.post("/search")
async def search_rag(req: RagSearchRequest) -> Dict[str, Any]:
    """Выполняет поиск по текстовому RAG-индексу."""
    hub = get_hub()
    results = await asyncio.to_thread(hub.text_rag.search, req.query, req.top_k, req.threshold)
    return {"results": results, "total_found": len(results)}


@router.get("/pixel/status")
async def get_pixel_rag_status() -> Dict[str, Any]:
    """Возвращает статус и метрики хранилища Pixel RAG."""
    hub = get_hub()
    return await asyncio.to_thread(hub.pixel_rag.get_status)


@router.post("/pixel/index")
async def index_pixel_images(files: List[UploadFile] = File(...)) -> Dict[str, Any]:
    """Индексирует загруженные изображения в Pixel RAG."""
    hub = get_hub()
    indexed_results: List[Dict[str, Any]] = []

    for file in files:
        try:
            content = await file.read(_MAX_UPLOAD_IMAGE_BYTES + 1)
            if len(content) > _MAX_UPLOAD_IMAGE_BYTES:
                logger.warning(f"[Router RAG] Файл {file.filename} превышает лимит {_MAX_UPLOAD_IMAGE_BYTES} байт")
                continue
            item = await asyncio.to_thread(
                hub.pixel_rag.index_image_bytes,
                content,
                file.filename or "screenshot.png",
                file.filename or "UI Screenshot",
            )
            indexed_results.append(item)
        except Exception as e:
            logger.error(f"[Router RAG] Ошибка индексации изображения {file.filename}: {e}")

    return {
        "status": "ok",
        "indexed_count": len(indexed_results),
        "results": indexed_results,
    }


@router.post("/pixel/search")
async def search_pixel_rag(req: PixelSearchRequest) -> Dict[str, Any]:
    """Выполняет поиск по скриншотам и OCR в Pixel RAG."""
    hub = get_hub()
    results = await asyncio.to_thread(hub.pixel_rag.search_by_text, req.query, req.top_k)
    return {"results": results, "total_found": len(results)}


@router.post("/unified/resolve")
async def unified_resolve(req: UnifiedResolveRequest) -> Dict[str, Any]:
    """Выполняет сквозное разрешение через Unified Knowledge Hub (WikiLLM + Text + Pixel + Log)."""
    hub = get_hub()
    img_bytes: bytes = b""
    if req.image_base64:
        try:
            img_bytes = base64.b64decode(req.image_base64)
        except Exception as e:
            logger.debug(f"[Router RAG] Не удалось декодировать image_base64: {e}")

    return await hub.resolve_query(
        query=req.query,
        image_bytes=img_bytes,
        sync_gemini=req.sync_gemini,
        top_k=req.top_k,
    )


@router.get("/codebase/indexes")
async def list_codebase_indexes() -> Dict[str, Any]:
    """Возвращает список всех построенных AST-индексов кодовой базы."""
    hub = get_hub()
    indexes = await asyncio.to_thread(hub.codebase_rag.list_indexes)
    return {"indexes": indexes, "total": len(indexes)}


@router.post("/codebase/build")
async def build_codebase_index(req: CodebaseBuildRequest) -> Dict[str, Any]:
    """Строит или перестраивает AST и векторный индекс кодовой базы и документации."""
    hub = get_hub()
    try:
        stats = await asyncio.to_thread(
            hub.codebase_rag.build_index,
            project_root=req.project_root,
            index_name=req.index_name,
            include_dirs=req.include_dirs,
            include_markdown=req.include_markdown,
        )
        return {"status": "ok", "result": stats}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error(f"[Router RAG] Ошибка сборки индекса кода: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/codebase/search")
async def search_codebase(req: CodebaseSearchRequest) -> Dict[str, Any]:
    """Выполняет гибридный поиск по чанкам исходного кода и документации."""
    hub = get_hub()
    results = await asyncio.to_thread(
        hub.codebase_rag.search_code,
        query=req.query,
        index_name=req.index_name,
        top_k=req.top_k,
    )
    return {"results": results, "total_found": len(results)}


@router.post("/codebase/symbols")
async def search_codebase_symbols(req: CodebaseSymbolRequest) -> Dict[str, Any]:
    """Выполняет поиск функций, классов и методов по таблице AST-символов."""
    hub = get_hub()
    results = await asyncio.to_thread(
        hub.codebase_rag.search_symbols,
        symbol_query=req.symbol,
        index_name=req.index_name,
        limit=req.limit,
    )
    return {"results": results, "total_found": len(results)}


@router.post("/codebase/diagnose", response_model=CodeDiagnosticConclusion)
async def diagnose_codebase(req: CodebaseDiagnoseRequest) -> CodeDiagnosticConclusion:
    """Формирует структурированное заключение по вопросу, списку логов или ошибке на основе базы знаний о коде."""
    if not req.question.strip() and not req.error_message.strip() and not req.logs:
        raise HTTPException(
            status_code=400,
            detail="Необходимо указать question, logs или error_message для формирования заключения.",
        )
    hub = get_hub()
    return await hub.diagnose_code(
        question=req.question,
        logs=req.logs,
        error_message=req.error_message,
        index_name=req.index_name,
        top_k=req.top_k,
        use_llm=req.use_llm,
    )


@router.get("/metrics")
async def get_all_metrics() -> Dict[str, Any]:
    """Возвращает подробные метрики всех слоев знаний."""
    hub = get_hub()
    return await asyncio.to_thread(hub.get_metrics)


def init_router(hub: Optional[UnifiedKnowledgeHub] = False) -> APIRouter:
    """Инициализирует роутер с опциональным хабом."""
    global _hub_instance
    if hub:
        _hub_instance = hub
    return router

