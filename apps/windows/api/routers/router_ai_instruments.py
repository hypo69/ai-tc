# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows API - Router AI Instruments
# =============================================================================
# Description:
#   REST API эндпоинты для изолированной базы данных инструментов ИИ-агента
#   (ai_instruments.db). Обеспечивает сохранение скриптов PowerShell/CMD/утилит,
#   пагинацию каталога инструментов, выполнение и извлечение из цепочки рассуждений.
#
# Usage Examples:
#   Python API:
#     from apps.windows.api.routers.router_ai_instruments import init_router
#
#     router = init_router()
#
# File: router_ai_instruments.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 14:20:00
# =============================================================================

from __future__ import annotations

"""REST API эндпоинты для базы инструментов ИИ-агента (ai_instruments.db)."""

import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from logger import logger
from apps.windows.ai_instruments.models import (
    AIInstrument,
    AIInstrumentCreate,
    AIInstrumentExecuteRequest,
)
from apps.windows.ai_instruments.service import AIInstrumentsService
from apps.windows.ai_instruments.storage import AIInstrumentsStorage


class InstrumentsDbConfigRequest(BaseModel):
    """Схема конфигурации базы данных инструментов."""
    engine: str = Field(default="sqlite", description="Движок: sqlite или mariadb/hostinger")
    sqlite_path: str = Field(default="data/ai_instruments/ai_instruments.db", description="Путь к файлу SQLite")
    connection_type: str = Field(default="direct", description="Тип соединения: direct или php_api")
    host: str = Field(default="srv1502.hstgr.io", description="Хост сервера")
    port: int = Field(default=3306, description="Порт")
    database: str = Field(default="u177424397_comp_knowledge", description="Имя БД")
    user: str = Field(default="u177424397_davidka", description="Пользователь")
    password: str = Field(default="@Davidka#1969", description="Пароль")
    table_name: str = Field(default="ai_instruments", description="Имя таблицы")
    php_api_url: str = Field(default="https://srv1502.hstgr.io/wikillm_hostinger.php", description="URL PHP API")
    php_api_key: str = Field(default="", description="Ключ API")
    connect_timeout: int = Field(default=10, description="Таймаут подключения")


class ExtractAdviceRequest(BaseModel):
    """Схема запроса на извлечение инструментов из текста советов."""

    text: str = Field(..., description="Текст советов разработчику или ответ модели")
    target_entity: Optional[str] = Field(default="", description="Связанная сущность системы")
    title_prefix: Optional[str] = Field(default="Инструмент агента", description="Префикс названия")


class InstrumentsRuntimeConfigRequest(BaseModel):
    """Схема параметров выполнения инструментов в цепочке размышлений."""
    execution_timeout: int = Field(default=15, description="Таймаут выполнения команды (сек)")
    elevate_powershell: bool = Field(default=True, description="Запуск PowerShell с повышенными правами")
    safe_ops_enabled: bool = Field(default=True, description="Безопасный режим SafeOps")
    auto_extract_from_reasoning: bool = Field(default=True, description="Автоизвлечение из рассуждений модели")
    title_prefix: str = Field(default="Инструмент агента", description="Префикс названий создаваемых инструментов")


def init_router(service: Optional[AIInstrumentsService] = None) -> APIRouter:
    """Инициализирует и возвращает FastAPI APIRouter для инструментов ИИ-агента.

    Args:
        service: Экземпляр сервиса AIInstrumentsService или None.

    Returns:
        APIRouter: Сконфигурированный роутер.
    """
    router = APIRouter(prefix="/api/v1/ai-instruments", tags=["ai-instruments"])

    # Если сервис не передан явно — загружаем настройки из apps/windows/api/config.json
    if service is None:
        import json

        cfg_path = Path("apps/windows/api/config.json")
        engine = "sqlite"
        db_path = "data/ai_instruments/ai_instruments.db"
        hostinger_cfg = {}

        if cfg_path.exists():
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    app_cfg = json.load(f)
                    inst_cfg = app_cfg.get("ai_instruments") or {}
                    engine = inst_cfg.get("engine", "sqlite")
                    db_path = inst_cfg.get("sqlite", {}).get("path", db_path)
                    hostinger_cfg = inst_cfg.get("hostinger", {})
            except Exception as ex:
                logger.warning(f"[RouterAIInstruments] Ошибка чтения config.json: {ex}")

        storage = AIInstrumentsStorage(
            db_path=db_path,
            engine=engine,
            hostinger_config=hostinger_cfg,
        )
        srv = AIInstrumentsService(storage=storage)
        try:
            srv.seed_default_instruments()
        except Exception as ex:
            logger.warning(f"[RouterAIInstruments] Ошибка начальной инициализации каталога инструментов: {ex}")
    else:
        srv = service

    @router.get("/status", response_model=Dict[str, Any])
    async def get_database_status() -> Dict[str, Any]:
        """Возвращает статус базы данных инструментов ai_instruments.db."""
        stats = srv.storage.get_stats()
        return {"status": "ok", "stats": stats}

    @router.get("/list", response_model=Dict[str, Any])
    async def list_instruments(
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
        tool_type: Optional[str] = Query(None, description="Фильтр по типу: powershell, cmd, utility"),
        target_entity: Optional[str] = Query(None, description="Фильтр по сущности: process, service"),
    ) -> Dict[str, Any]:
        """Возвращает список инструментов из ai_instruments.db."""
        items = srv.list_instruments(
            limit=limit,
            offset=offset,
            tool_type=tool_type,
            target_entity=target_entity,
        )
        return {
            "status": "ok",
            "total": len(items),
            "items": [it.model_dump() for it in items],
        }

    @router.get("/search", response_model=Dict[str, Any])
    async def search_instruments(
        q: str = Query(..., min_length=1, description="Поисковая строка"),
        limit: int = Query(20, ge=1, le=100),
    ) -> Dict[str, Any]:
        """Выполняет полнотекстовый поиск по инструментам агента."""
        results = srv.search_instruments(query=q, limit=limit)
        return {
            "status": "ok",
            "count": len(results),
            "items": [it.model_dump() for it in results],
        }

    @router.get("/export/csv")
    async def export_instruments_csv(
        tool_type: Optional[str] = Query(None, description="Фильтр по типу: powershell, cmd, utility"),
        target_entity: Optional[str] = Query(None, description="Фильтр по сущности: process, service"),
    ) -> Response:
        """Экспортирует каталог инструментов агента в формат CSV через src.utils.csv.save_csv_file."""
        fd, tmp_path = tempfile.mkstemp(suffix=".csv", prefix="ai_instruments_export_")
        os.close(fd)
        try:
            srv.export_to_csv(
                file_path=tmp_path,
                tool_type=tool_type,
                target_entity=target_entity,
            )
            content = Path(tmp_path).read_bytes()
            return Response(
                content=content,
                media_type="text/csv; charset=utf-8",
                headers={
                    "Content-Disposition": 'attachment; filename="ai_instruments_catalog.csv"',
                },
            )
        except Exception as ex:
            logger.error(f"[RouterAIInstruments] Ошибка экспорта CSV: {ex}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Ошибка экспорта каталога в CSV: {ex}")
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass

    @router.post("/import/csv", response_model=Dict[str, Any])
    async def import_instruments_csv(request: Request) -> Dict[str, Any]:
        """Импортирует инструменты агента из CSV-файла через src.utils.csv.read_csv_file."""
        content_type = (request.headers.get("content-type") or "").lower()
        fd, tmp_path = tempfile.mkstemp(suffix=".csv", prefix="ai_instruments_import_")
        os.close(fd)
        try:
            if "multipart/form-data" in content_type:
                form = await request.form()
                upload = form.get("file")
                if upload is None or not hasattr(upload, "read"):
                    raise HTTPException(status_code=400, detail="В форме отсутствует CSV-файл ('file')")
                raw_bytes = await upload.read()
                if not raw_bytes:
                    raise HTTPException(status_code=400, detail="Загруженный CSV-файл пуст")
                Path(tmp_path).write_bytes(raw_bytes)
            else:
                body = await request.json()
                file_path_str = (body.get("file_path") or "").strip() if isinstance(body, dict) else ""
                csv_content = (body.get("csv_content") or "") if isinstance(body, dict) else ""
                if file_path_str:
                    src_path = Path(file_path_str)
                    if not src_path.exists():
                        raise HTTPException(status_code=404, detail=f"CSV-файл не найден: {file_path_str}")
                    imported = srv.import_from_csv(src_path)
                    return {
                        "status": "ok",
                        "success": True,
                        "imported_count": len(imported),
                        "items": [it.model_dump() for it in imported],
                    }
                if not csv_content or not csv_content.strip():
                    raise HTTPException(status_code=400, detail="Содержимое CSV ('csv_content') не может быть пустым")
                Path(tmp_path).write_text(csv_content, encoding="utf-8")

            imported_items = srv.import_from_csv(tmp_path)
            return {
                "status": "ok",
                "success": True,
                "imported_count": len(imported_items),
                "items": [it.model_dump() for it in imported_items],
            }
        except HTTPException:
            raise
        except Exception as ex:
            logger.error(f"[RouterAIInstruments] Ошибка импорта CSV: {ex}", exc_info=True)
            raise HTTPException(status_code=400, detail=f"Ошибка импорта инструментов из CSV: {ex}")
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass

    @router.get("/{tool_id}", response_model=Dict[str, Any])
    async def get_instrument_by_id(tool_id: str) -> Dict[str, Any]:
        """Возвращает инструмент по уникальному ID."""
        item = srv.get_instrument(tool_id)
        if not item:
            raise HTTPException(status_code=404, detail=f"Инструмент '{tool_id}' не найден в ai_instruments.db")
        return {"status": "ok", "item": item.model_dump()}

    @router.post("/save", response_model=Dict[str, Any])
    async def save_instrument(payload: AIInstrumentCreate) -> Dict[str, Any]:
        """Сохраняет инструмент в базу данных ai_instruments.db."""
        if not payload.name or not payload.command:
            raise HTTPException(status_code=400, detail="Название инструмента и команда не могут быть пустыми")

        saved = srv.save_instrument(payload)
        return {
            "status": "ok",
            "success": True,
            "tool_id": saved.tool_id,
            "item": saved.model_dump(),
        }

    @router.delete("/{tool_id}", response_model=Dict[str, Any])
    async def delete_instrument(tool_id: str) -> Dict[str, Any]:
        """Удаляет инструмент из базы данных ai_instruments.db."""
        ok = srv.delete_instrument(tool_id)
        if not ok:
            raise HTTPException(status_code=404, detail=f"Инструмент '{tool_id}' не найден")
        return {"status": "ok", "success": True, "tool_id": tool_id}

    @router.post("/execute", response_model=Dict[str, Any])
    async def execute_instrument(payload: AIInstrumentExecuteRequest) -> Dict[str, Any]:
        """Выполняет инструмент из базы ai_instruments.db."""
        res = srv.execute_instrument(
            tool_id=payload.tool_id,
            parameters=payload.parameters,
            timeout_sec=payload.timeout_sec,
            as_admin=payload.as_admin,
        )
        return res

    @router.post("/extract-from-advice", response_model=Dict[str, Any])
    async def extract_from_advice(payload: ExtractAdviceRequest) -> Dict[str, Any]:
        """Извлекает PowerShell скрипты из текста и сохраняет их в ai_instruments.db."""
        saved_items = srv.extract_and_save_from_text(
            text=payload.text,
            target_entity=payload.target_entity or "",
            title_prefix=payload.title_prefix or "Инструмент агента",
        )
        return {
            "status": "ok",
            "extracted_count": len(saved_items),
            "items": [it.model_dump() for it in saved_items],
        }

    @router.get("/db/config", response_model=Dict[str, Any])
    async def get_instruments_db_configuration() -> Dict[str, Any]:
        """Возвращает текущую конфигурацию подключения к базе инструментов."""
        import json
        from pathlib import Path
        cfg_path = Path("apps/windows/api/config.json")
        conf = {}
        if cfg_path.exists():
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    conf = json.load(f).get("ai_instruments", {})
            except Exception:
                pass
        engine = conf.get("engine", srv.storage.engine)
        sq_path = conf.get("sqlite", {}).get("path", str(srv.storage.db_path))
        host_cfg = conf.get("hostinger", srv.storage.hostinger_config)
        return {
            "status": "ok",
            "engine": engine,
            "sqlite": {"path": sq_path},
            "hostinger": host_cfg,
        }

    @router.post("/db/config", response_model=Dict[str, Any])
    async def save_instruments_db_configuration(req: InstrumentsDbConfigRequest) -> Dict[str, Any]:
        """Сохраняет конфигурацию подключения к базе инструментов и переключает хранилище."""
        import json
        from pathlib import Path

        new_inst_cfg = {
            "description": "Изолированная база данных инструментов ИИ-агента (ai_instruments.db)",
            "engine": req.engine.lower(),
            "sqlite": {
                "path": req.sqlite_path
            },
            "hostinger": {
                "connection_type": req.connection_type,
                "host": req.host,
                "port": req.port,
                "user": req.user,
                "password": req.password,
                "database": req.database,
                "table_name": req.table_name,
                "php_api_url": req.php_api_url,
                "php_api_key": req.php_api_key,
                "connect_timeout": req.connect_timeout,
            }
        }

        # Сохраняем в apps/windows/api/config.json
        cfg_paths = [Path("apps/windows/api/config.json"), Path("config.json")]
        for p in cfg_paths:
            if p.exists():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        c = json.load(f)
                    c["ai_instruments"] = new_inst_cfg
                    with open(p, "w", encoding="utf-8") as f:
                        json.dump(c, f, ensure_ascii=False, indent=2)
                        f.write("\n")
                except Exception as ex:
                    logger.warning(f"[RouterAIInstruments] Ошибка записи {p}: {ex}")

        # Переподключаем storage сервиса
        new_storage = AIInstrumentsStorage(
            db_path=req.sqlite_path,
            engine=req.engine.lower(),
            hostinger_config=new_inst_cfg["hostinger"],
        )
        srv.storage = new_storage
        try:
            srv.seed_default_instruments()
        except Exception as ex:
            logger.warning(f"[RouterAIInstruments] Ошибка синхронизации инструментов после смены БД: {ex}")

        return {
            "status": "ok",
            "success": True,
            "message": "Конфигурация базы инструментов успешно сохранена",
            "config": new_inst_cfg,
        }

    @router.post("/db/check", response_model=Dict[str, Any])
    async def check_instruments_db_connection(req: Optional[InstrumentsDbConfigRequest] = None) -> Dict[str, Any]:
        """Проверяет подключение к базе инструментов (SQLite или Hostinger) и наличие таблицы ai_instruments."""
        engine = req.engine.lower() if req else srv.storage.engine
        if engine == "sqlite":
            p = req.sqlite_path if req else str(srv.storage.db_path)
            try:
                temp_storage = AIInstrumentsStorage(db_path=p, engine="sqlite")
                stats = temp_storage.get_stats()
                return {
                    "ok": True,
                    "connected": True,
                    "engine": "sqlite",
                    "path": p,
                    "table": "ai_instruments",
                    "count": stats["total_instruments"],
                    "message": f"Локальная база ai_instruments.db доступна ({stats['total_instruments']} инструментов).",
                }
            except Exception as ex:
                return {
                    "ok": False,
                    "connected": False,
                    "engine": "sqlite",
                    "error": str(ex),
                    "message": f"Ошибка доступа к файлу SQLite: {ex}",
                }

        # Hostinger (Direct TCP MariaDB или PHP API)
        h_cfg = req.model_dump() if req else dict(srv.storage.hostinger_config)
        try:
            temp_storage = AIInstrumentsStorage(
                db_path=":memory:",
                engine="sqlite",
                hostinger_config=h_cfg,
            )
            temp_storage.engine = "hostinger"
            temp_storage._execute_remote(
                "execute",
                """
                CREATE TABLE IF NOT EXISTS ai_instruments (
                    tool_id VARCHAR(255) PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    tool_type VARCHAR(50) NOT NULL DEFAULT 'powershell',
                    command LONGTEXT NOT NULL,
                    description MEDIUMTEXT,
                    target_entity VARCHAR(255) DEFAULT '',
                    parameters_schema_json LONGTEXT,
                    risk_level VARCHAR(50) NOT NULL DEFAULT 'safe',
                    author_agent VARCHAR(100) NOT NULL DEFAULT 'reasoning_chain',
                    tags_json LONGTEXT,
                    execution_count INT NOT NULL DEFAULT 0,
                    last_executed_at VARCHAR(100),
                    created_at VARCHAR(100) NOT NULL,
                    updated_at VARCHAR(100) NOT NULL,
                    INDEX idx_ai_inst_target (target_entity),
                    INDEX idx_ai_inst_type (tool_type)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """,
                [],
            )
            return temp_storage.check_remote_connection()
        except Exception as ex:
            return {
                "ok": False,
                "connected": False,
                "engine": "hostinger",
                "error": str(ex),
                "message": f"Ошибка соединения с Hostinger: {ex}",
            }

    @router.post("/db/init-tables", response_model=Dict[str, Any])
    async def init_instruments_tables() -> Dict[str, Any]:
        """Инициализирует пустую таблицу ai_instruments в активной базе данных."""
        try:
            if srv.storage.engine in ("sqlite", "memory"):
                srv.storage._init_sqlite_db()
            else:
                srv.storage._init_remote_db()
            return {
                "ok": True,
                "success": True,
                "message": "Таблица ai_instruments успешно инициализирована",
            }
        except Exception as ex:
            raise HTTPException(status_code=500, detail=f"Ошибка инициализации таблицы: {ex}")

    _runtime_mem_cache: Dict[str, Any] = {}

    @router.get("/runtime/config", response_model=Dict[str, Any])
    async def get_instruments_runtime_configuration() -> Dict[str, Any]:
        """Возвращает параметры выполнения инструментов в цепочке размышлений."""
        import json
        import time
        from pathlib import Path
        cfg_paths = [Path("apps/windows/api/config.json"), Path("config.json")]
        runtime_cfg = {
            "execution_timeout": 15,
            "elevate_powershell": True,
            "safe_ops_enabled": True,
            "auto_extract_from_reasoning": True,
            "title_prefix": "Инструмент агента",
        }
        if _runtime_mem_cache:
            runtime_cfg.update(_runtime_mem_cache)

        for cfg_path in cfg_paths:
            if not cfg_path.exists():
                continue
            for _ in range(3):
                try:
                    with open(cfg_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    ai_inst = data.get("ai_instruments") or {}
                    c = ai_inst.get("runtime") or {}
                    if c:
                        runtime_cfg.update(c)
                        _runtime_mem_cache.update(c)
                        break
                except Exception as ex:
                    await asyncio.sleep(0.05)
                    continue

        return {"status": "ok", "runtime": runtime_cfg}

    @router.post("/runtime/config", response_model=Dict[str, Any])
    async def save_instruments_runtime_configuration(req: InstrumentsRuntimeConfigRequest) -> Dict[str, Any]:
        """Сохраняет параметры выполнения инструментов в цепочке размышлений."""
        import json
        from pathlib import Path
        cfg_paths = [Path("apps/windows/api/config.json"), Path("config.json")]
        runtime_data = req.model_dump()
        _runtime_mem_cache.update(runtime_data)

        for p in cfg_paths:
            if not p.exists():
                continue
            for _ in range(3):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        c = json.load(f)
                    if "ai_instruments" not in c:
                        c["ai_instruments"] = {}
                    c["ai_instruments"]["runtime"] = runtime_data
                    with open(p, "w", encoding="utf-8") as f:
                        json.dump(c, f, ensure_ascii=False, indent=2)
                        f.write("\n")
                    break
                except Exception as ex:
                    await asyncio.sleep(0.05)
                    continue

        return {
            "status": "ok",
            "success": True,
            "message": "Параметры выполнения инструментов в цепочке размышлений успешно сохранены",
            "runtime": runtime_data,
        }

    return router

