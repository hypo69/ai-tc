# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Apps Windows API - Database Manager Router
# =============================================================================
# Description:
#   FastAPI REST API роутер для управления базами данных (SQLite и Hostinger MariaDB):
#   - Обзор параметров, метрик и структуры таблиц (/overview);
#   - Прямой ввод и выполнение SQL команд: SELECT, INSERT, UPDATE, DELETE (/query);
#   - Сжатие и оптимизация хранилища (/compress);
#   - Экспорт таблиц и баз данных в SQL, JSON, CSV (/export);
#   - Управление бэкапами: создание с ZIP-сжатием, листинг, восстановление и удаление (/backup, /backups, /restore).
#
# File: router_db_manager.py
# Project: ai-tc
# Package: apps.windows.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-19 17:25:00
# =============================================================================

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

try:
    from logger import logger
except ImportError:
    import logging
    logger = logging.getLogger("router_db_manager")

from apps.windows.db.db_manager_service import DBManagerService


# ------------------------------------------------------------------------------
# Pydantic Schemas
# ------------------------------------------------------------------------------

class QueryRequestSchema(BaseModel):
    """Схема запроса выполнения произвольного SQL запроса."""
    target_id: str = Field(default="sqlite:knowledge", description="Идентификатор целевой базы")
    sql: str = Field(..., description="Текст SQL запроса (SELECT, INSERT, UPDATE, DELETE и др.)")
    params: Optional[Dict[str, Any]] = Field(default=None, description="Параметры подстановки")
    max_rows: int = Field(default=200, ge=1, le=5000, description="Максимальное число возвращаемых строк")


class CompressRequestSchema(BaseModel):
    """Схема запроса на сжатие и оптимизацию базы."""
    target_id: str = Field(default="sqlite:knowledge", description="Целевая база")
    action: str = Field(default="vacuum", description="Действие: vacuum, optimize, wal_checkpoint")
    table_name: Optional[str] = Field(default=None, description="Имя конкретной таблицы")


class ExportRequestSchema(BaseModel):
    """Схема запроса на экспорт базы/таблицы."""
    target_id: str = Field(default="hostinger:tool_chains", description="Целевая база (Hostinger или SQLite)")
    table_name: Optional[str] = Field(default="all", description="Имя таблицы или 'all'")
    export_format: str = Field(default="sql", description="Формат экспорта: sql, json, csv")


class BackupRequestSchema(BaseModel):
    """Схема запроса создания резервной копии."""
    target_id: str = Field(default="sqlite:knowledge", description="Целевая база")
    compress_zip: bool = Field(default=True, description="Сжимать в zip-архив")


class RestoreRequestSchema(BaseModel):
    """Схема запроса восстановления из резервной копии."""
    backup_name: str = Field(..., description="Имя файла бэкапа")
    target_id: Optional[str] = Field(default=None, description="Целевая база для восстановления")


# ------------------------------------------------------------------------------
# Router Initialization
# ------------------------------------------------------------------------------

router = APIRouter(
    prefix="/api/v1/db-manager",
    tags=["Database Workbench & Hosting Management"]
)

_service: Optional[DBManagerService] = None


def get_db_manager_service() -> DBManagerService:
    """Возвращает синглтон сервиса управления базами данных."""
    global _service
    if _service is None:
        _service = DBManagerService()
    return _service


def init_router(service: Optional[DBManagerService] = None) -> APIRouter:
    """Фабричная функция инициализации роутера."""
    global _service
    if service is not None:
        _service = service
    return router


# ------------------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------------------

@router.get("/overview")
async def get_databases_overview() -> Dict[str, Any]:
    """Возвращает параметры, статус подключения, размер и таблицы всех настроенных баз."""
    srv = get_db_manager_service()
    try:
        return srv.get_overview()
    except Exception as ex:
        logger.error(f"[DBManagerRouter] Ошибка получения сводки: {ex}")
        raise HTTPException(status_code=500, detail=str(ex))


@router.post("/query")
async def execute_sql_query(req: QueryRequestSchema) -> Dict[str, Any]:
    """Выполняет прямой SQL запрос (SELECT, INSERT, UPDATE, DELETE и др.) на выбранной базе."""
    srv = get_db_manager_service()
    result = srv.execute_query(
        target_id=req.target_id,
        sql=req.sql,
        params=req.params,
        max_rows=req.max_rows,
    )
    return result


@router.post("/compress")
async def compress_database(req: CompressRequestSchema) -> Dict[str, Any]:
    """Выполняет сжатие хранилища SQLite (VACUUM) или оптимизацию таблиц MariaDB на Hostinger."""
    srv = get_db_manager_service()
    result = srv.compress_database(
        target_id=req.target_id,
        action=req.action,
        table_name=req.table_name,
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Ошибка сжатия базы"))
    return result


@router.post("/export")
async def export_database(req: ExportRequestSchema) -> Dict[str, Any]:
    """Экспортирует таблицы и данные из баз на хостинге или SQLite в SQL дамп, JSON или CSV."""
    srv = get_db_manager_service()
    result = srv.export_database(
        target_id=req.target_id,
        table_name=req.table_name,
        export_format=req.export_format,
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Ошибка экспорта базы"))
    return result


@router.post("/backup")
async def create_backup(req: BackupRequestSchema) -> Dict[str, Any]:
    """Создает резервную копию базы данных с опциональным ZIP сжатием."""
    srv = get_db_manager_service()
    result = srv.create_backup(
        target_id=req.target_id,
        compress_zip=req.compress_zip,
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Ошибка создания резервной копии"))
    return result


@router.get("/backups")
async def list_backups() -> Dict[str, Any]:
    """Возвращает список всех сохраненных резервных копий."""
    srv = get_db_manager_service()
    backups = srv.list_backups()
    return {"success": True, "count": len(backups), "backups": backups}


@router.post("/restore")
async def restore_backup(req: RestoreRequestSchema) -> Dict[str, Any]:
    """Восстанавливает выбранную базу данных из резервной копии."""
    srv = get_db_manager_service()
    result = srv.restore_backup(
        backup_name=req.backup_name,
        target_id=req.target_id,
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Ошибка восстановления"))
    return result


@router.delete("/backups/{filename}")
async def delete_backup(filename: str) -> Dict[str, Any]:
    """Удаляет файл резервной копии."""
    srv = get_db_manager_service()
    result = srv.delete_backup(filename)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "Бэкап не найден"))
    return result


@router.get("/download/{filename}")
async def download_file(filename: str):
    """Предоставляет скачивание файла бэкапа или экспорта."""
    srv = get_db_manager_service()
    safe_name = Path(filename).name

    # Ищем в бэкапах или экспортах
    candidate_paths = [
        srv.backups_dir / safe_name,
        srv.exports_dir / safe_name,
    ]
    for p in candidate_paths:
        if p.exists() and p.is_file():
            return FileResponse(
                path=str(p),
                filename=safe_name,
                media_type="application/octet-stream",
            )

    raise HTTPException(status_code=404, detail=f"Файл {safe_name} не найден")
