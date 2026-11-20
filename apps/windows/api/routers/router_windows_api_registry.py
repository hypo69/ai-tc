# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Windows API Registry - Router
# =============================================================================
# Description:
#   FastAPI REST API роутер для реестра системных API Windows, 6 подсистем
#   Platform Layer, проверки Python-привязок и диспетчера рекомендаций.
#
# Usage Examples:
#   from apps.windows.api.routers.router_windows_api_registry import router
#
# File: router_windows_api_registry.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 02:58:00
# =============================================================================

from __future__ import annotations
"""Маршрутизатор REST API для реестра и диспетчера Windows API."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from apps.windows.api_registry import (
    ApiFamily,
    ApiRecommendationQuery,
    ApiRecommendationResult,
    PlatformSubsystem,
    RegistryFilterConfig,
    WindowsApiEntry,
    get_api_registry_service,
)

router = APIRouter(prefix="/api/v1/windows-api", tags=["Windows API Registry & Platform Layer"])

_service = get_api_registry_service()


class ProbeExecutionRequest(BaseModel):
    """Запрос на выполнение проверочного зонда API."""
    api_id: str = Field(..., description="Идентификатор API из каталога")


@router.get("/catalog", response_model=List[WindowsApiEntry], summary="Каталог Windows API")
async def get_catalog(
    subsystem: Optional[PlatformSubsystem] = Query(None, description="Фильтр по подсистеме платформы"),
    family: Optional[ApiFamily] = Query(None, description="Фильтр по семейству API (Win32, WinRT, COM...)"),
    zero_dependency: bool = Query(False, description="Только нативные API без сторонних pip-пакетов"),
    query: Optional[str] = Query(None, description="Поисковая строка по названию, DLL или функциям"),
) -> List[WindowsApiEntry]:
    """Возвращает структурированный каталог системных API с фильтрацией."""
    return _service.get_catalog(
        subsystem=subsystem,
        family=family,
        zero_dependency_only=zero_dependency,
        search_query=query,
    )


@router.get("/entry/{api_id}", response_model=WindowsApiEntry, summary="Карточка конкретного API")
async def get_api_entry(api_id: str) -> WindowsApiEntry:
    """Возвращает полную спецификацию и сниппеты для указанного API."""
    entry = _service.get_entry(api_id)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Системный API с идентификатором '{api_id}' не найден",
        )
    return entry


@router.get("/subsystems", summary="Сводка по 6 подсистемам платформы")
async def get_subsystems() -> Dict[str, Dict[str, Any]]:
    """Возвращает метрики и структуру 6 платформенных направлений AI-TC."""
    return _service.get_subsystems()


@router.get("/bindings-status", summary="Статус Python bindings в окружении")
async def get_bindings_status() -> Dict[str, Dict[str, Any]]:
    """Проверяет доступность ctypes, pywin32, comtypes, winsdk/winrt, psutil, wmi."""
    return _service.get_bindings_status()


@router.post("/recommend", response_model=ApiRecommendationResult, summary="Умный подбор API под задачу")
async def recommend_api(query: ApiRecommendationQuery) -> ApiRecommendationResult:
    """Интеллектуально подбирает оптимальный системный интерфейс под задачу пользователя."""
    return _service.recommend(query)


@router.post("/execute-probe", summary="Запуск безопасного нативного зонда")
async def execute_probe(req: ProbeExecutionRequest) -> Dict[str, Any]:
    """Выполняет тестовый вызов нативной Win32 функции через ctypes."""
    return _service.execute_probe(req.api_id)


@router.get("/settings", response_model=RegistryFilterConfig, summary="Текущие настройки диспетчера")
async def get_settings() -> RegistryFilterConfig:
    """Возвращает настройки фильтрации и рекомендательного движка."""
    return _service.get_settings()


@router.post("/settings", response_model=RegistryFilterConfig, summary="Обновление настроек диспетчера")
async def update_settings(cfg: RegistryFilterConfig) -> RegistryFilterConfig:
    """Сохраняет обновленные настройки диспетчера."""
    return _service.update_settings(cfg)
