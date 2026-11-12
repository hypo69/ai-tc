# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Code Helper - Standalone ASGI Server Runner
# =============================================================================
# Description:
#   Автономный сервер ASGI (FastAPI + Uvicorn) для приложения Code Helper.
#   Позволяет запускать микроприложение изолированно на выделенном порту.
#
# File: server.py
# Project: ai-windows-admin
# Package: apps.code_helper
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 14:28:00
# =============================================================================

from __future__ import annotations

"""Автономный ASGI сервер для микроприложения Code Helper."""

import json
from pathlib import Path
from typing import Any, Dict
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from logger import logger
from .router import init_router


def create_app() -> FastAPI:
    """Создает и настраивает экземпляр FastAPI приложения Code Helper."""
    app = FastAPI(
        title="Code Helper (Codebase RAG)",
        description="Автономная система RAG исходного кода и диагностики с базой MariaDB на Hostinger",
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1",
            "https://127.0.0.1",
            "http://localhost",
            "https://localhost",
        ],
        allow_origin_regex=r"https?://(127\.0\.0\.1|localhost)(:\d+)?",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(init_router())

    @app.get("/")
    async def root_info() -> Dict[str, Any]:
        """Корневой эндпоинт информации о микроприложении."""
        return {
            "app": "code_helper",
            "name": "Code Helper (Codebase RAG)",
            "version": "1.0.0",
            "status": "ready",
            "docs": "/docs",
            "api_prefix": "/api/code-helper",
        }

    return app


def run_standalone_server(host: str = "127.0.0.1", port: int = 8105) -> None:
    """Запуск автономного веб-сервера Uvicorn."""
    import uvicorn

    cfg_path = Path(__file__).parent / "config.json"
    if cfg_path.exists():
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                srv = cfg.get("server", {})
                host = srv.get("host", host)
                port = int(srv.get("port", port))
        except Exception:
            pass

    logger.console(f"Запуск автономного сервера Code Helper на http://{host}:{port}")
    uvicorn.run("apps.code_helper.server:create_app", host=host, port=port, factory=True, log_level="info")
