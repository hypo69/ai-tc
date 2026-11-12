# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Common File Editor - FastAPI Router
# =============================================================================
# Description:
#   REST API маршрутизатор универсального редактора файлов Rust + WebAssembly.
#   Обслуживает скомпилированный бинарный модуль .wasm, каталог всех типов
#   файлов VS Code, чтение/сохранение файлов (текст, Base64, Hex-патчи),
#   форматирование и вычисление построчного Unified Diff.
#
# File: router.py
# Project: ai-windows-admin
# Package: apps.common.file_editor
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 14:31:30
# =============================================================================

from __future__ import annotations
"""FastAPI роутер модуля редактора файлов `/api/v1/file-editor`."""

import asyncio
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from logger import logger
from apps.common.file_editor.catalog import SupportedFileCatalog
from apps.common.file_editor.models import (
    FileDiffRequest,
    FileFormatRequest,
    FileSaveRequest,
)
from apps.common.file_editor.service import FileEditorService
from apps.common.file_editor.wasm_compiler import ensure_wasm_binary

router = APIRouter(prefix="/api/v1/file-editor", tags=["Common Wasm File Editor"])
_editor_service = FileEditorService()


@router.get("/catalog", summary="Каталог всех поддерживаемых типов файлов VS Code")
async def get_supported_files_catalog() -> Dict[str, Any]:
    """Возвращает полный список дескрипторов типов файлов и режимов редактирования."""
    items = SupportedFileCatalog.list_all()
    return {
        "status": "ok",
        "total_types": len(items),
        "items": items,
    }


@router.get("/wasm", summary="Бинарный модуль ядра Rust + WebAssembly")
async def get_wasm_core_binary() -> FileResponse:
    """Отдаёт скомпилированный бинарный модуль `file_editor_core.wasm` для браузера."""
    wasm_path = await asyncio.to_thread(ensure_wasm_binary)
    return FileResponse(
        path=str(wasm_path),
        media_type="application/wasm",
        filename="file_editor_core.wasm",
    )


@router.get("/read", summary="Чтение любого типа файла для Wasm-редактора")
async def read_file_for_editor(
    rel_path: str = Query(..., description="Относительный путь к файлу в рабочей области"),
    workspace_id: Optional[str] = Query(default=None, description="Идентификатор рабочей области"),
) -> Dict[str, Any]:
    """Считывает текстовое и бинарное представление файла вместе с дескриптором режима VS Code."""
    try:
        return await asyncio.to_thread(_editor_service.read_file, rel_path=rel_path, workspace_id=workspace_id)
    except FileNotFoundError as fnf:
        raise HTTPException(status_code=404, detail=str(fnf))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        logger.error(f"[FileEditorRouter] Ошибка чтения файла {rel_path}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/save", summary="Сохранение файла (текст, Base64 или побайтовые Hex-патчи)")
async def save_file_from_editor(req: FileSaveRequest) -> Dict[str, Any]:
    """Записывает изменения файла на диск и при необходимости фиксирует коммит в Git."""
    try:
        return await asyncio.to_thread(_editor_service.save_file, req)
    except FileNotFoundError as fnf:
        raise HTTPException(status_code=404, detail=str(fnf))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        logger.error(f"[FileEditorRouter] Ошибка сохранения файла {req.rel_path}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/format", summary="Форматирование и валидация синтаксиса буфера")
async def format_editor_buffer(req: FileFormatRequest) -> Dict[str, Any]:
    """Форматирует буфер редактора (JSON, XML, SVG, CSV, TSV, .ipynb, код)."""
    try:
        return await asyncio.to_thread(_editor_service.format_buffer, req)
    except Exception as exc:
        logger.error(f"[FileEditorRouter] Ошибка форматирования: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/diff", summary="Построчное сравнение (Unified Diff) с версией на диске")
async def diff_editor_buffer(req: FileDiffRequest) -> Dict[str, Any]:
    """Возвращает Unified Diff между текущим буфером редактора и файлом в рабочей области."""
    try:
        return await asyncio.to_thread(_editor_service.compute_diff, req)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        logger.error(f"[FileEditorRouter] Ошибка расчёта diff: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
