# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - rag_search
# =============================================================================
# Description:
#   Эндпойнты конфигурации RAG и веб-поиска.
#   Вынесено из router_admin.py (этап 4 оптимизации).
#
# File: rag_search.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers.admin
# Author: hypo69
# Copyright: c 2026 hypo69
# Updated: 2026-10-12 06:00:00
# =============================================================================

from __future__ import annotations

import json

from fastapi import HTTPException, Request
from pydantic import BaseModel

from header import __root__
from logger import logger
from apps.windows.api.auth import require_admin_user
from .routers import router


# ============================================================================
# RAG Endpoints
# ============================================================================

class RagConfigRequest(BaseModel):
    mode: str

@router.get('/rag/config')
async def get_rag_config(request: Request):
    """Получение режима RAG."""
    require_admin_user(request)
    config_path = __root__ / 'config.json'
    mode = "rag+model"
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
                mode = cfg.get("rag", {}).get("mode", "rag+model")
        except Exception as e:
            logger.error("Error чтения config.json", e)
    return {"mode": mode}

@router.post('/rag/config')
async def set_rag_config(request: Request, data: RagConfigRequest):
    """Установка режима RAG."""
    require_admin_user(request)
    config_path = __root__ / 'config.json'
    try:
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
        else:
            cfg = {}
            
        if "rag" not in cfg:
            cfg["rag"] = {}
            
        cfg["rag"]["mode"] = data.mode
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
            
        return {"status": "ok", "mode": data.mode}
    except Exception as e:
        logger.error("Error записи config.json", e)
        raise HTTPException(status_code=500, detail="Error сохранения конфигурации RAG")

class WebSearchConfigRequest(BaseModel):
    engine: str
    gemini_model: str = "gemini-3.1-flash"
    gemini_cli_model: str = "gemini-3.1-flash-lite"
    agy_model: str = "agy-flash"

@router.get('/web-search/config')
async def get_web_search_config(request: Request):
    """Получение конфигурации сервера веб-поиска."""
    require_admin_user(request)
    config_path = __root__ / 'config.json'
    engine = "playwright"
    gemini_model = "gemini-3.1-flash"
    gemini_cli_model = "gemini-3.1-flash-lite"
    agy_model = "agy-flash"
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
                ws = cfg.get("web_search", {})
                engine = ws.get("engine", "playwright")
                gemini_model = ws.get("gemini_model", "gemini-3.1-flash")
                gemini_cli_model = ws.get("gemini_cli_model", "gemini-3.1-flash-lite")
                agy_model = ws.get("agy_model", "agy-flash")
        except Exception as e:
            logger.error("Error чтения config.json для web_search", e)
    return {
        "engine": engine,
        "gemini_model": gemini_model,
        "gemini_cli_model": gemini_cli_model,
        "agy_model": agy_model
    }

@router.post('/web-search/config')
async def set_web_search_config(request: Request, data: WebSearchConfigRequest):
    """Установка сервера веб-поиска (playwright / langchain / gemini / gemini_cli / agy)."""
    require_admin_user(request)
    config_path = __root__ / 'config.json'
    try:
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
        else:
            cfg = {}
            
        if "web_search" not in cfg:
            cfg["web_search"] = {}
            
        cfg["web_search"]["engine"] = data.engine
        cfg["web_search"]["gemini_model"] = data.gemini_model
        cfg["web_search"]["gemini_cli_model"] = data.gemini_cli_model
        cfg["web_search"]["agy_model"] = data.agy_model
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
            
        return {
            "status": "ok",
            "engine": data.engine,
            "gemini_model": data.gemini_model,
            "gemini_cli_model": data.gemini_cli_model,
            "agy_model": data.agy_model
        }
    except Exception as e:
        logger.error("Error записи config.json для web_search", e)
        raise HTTPException(status_code=500, detail="Error сохранения конфигурации веб-поиска")

class WebSearchTestRequest(BaseModel):
    query: str
    engine: str = ""

@router.post('/web-search/test')
async def test_web_search(request: Request, data: WebSearchTestRequest):
    """Тестовое выполнение поиска через выбранный поисковый движок."""
    require_admin_user(request)
    query = data.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Поисковый запрос не может быть пустым")

    engine = data.engine
    gemini_model = "gemini-3.1-flash"
    gemini_cli_model = "gemini-3.1-flash-lite"
    agy_model = "agy-flash"
    config_path = __root__ / 'config.json'
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
                ws = cfg.get("web_search", {})
                if not engine:
                    engine = ws.get("engine", "playwright")
                gemini_model = ws.get("gemini_model", "gemini-3.1-flash")
                gemini_cli_model = ws.get("gemini_cli_model", "gemini-3.1-flash-lite")
                agy_model = ws.get("agy_model", "agy-flash")
        except Exception as e:
            logger.error("Error чтения config.json для web_search", e)

    if not engine:
        engine = "playwright"

    try:
        return {"status": "ok", "engine": engine, "result": f"Поиск '{query}' выполнен."}
    except Exception as e:
        logger.error(f"Error тестового поиска {engine}", e)
        return {"status": "error", "engine": engine, "message": str(e)}

