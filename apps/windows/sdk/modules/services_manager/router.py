# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Apps Windows Modules Services_Manager - Router
# =============================================================================
# Description:
#   FastAPI роутер для управления службами Windows, каталога svchost-групп,
#   графа связей и глубокого досье службы на базе SQLite-хранилища.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.services_manager.router import init_router
#
#     res = init_router()
#
# File: router.py
# Project: ai-tc
# Package: apps.windows.sdk.modules.services_manager
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20 16:45:00
# =============================================================================

from __future__ import annotations

"""FastAPI роутер для управления службами Windows и анализа их связей."""

import asyncio
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from apps.windows.sdk.modules.services_manager.core.manager import ServicesManager
from apps.windows.sdk.modules.services_manager.core.models import (
    ServiceActionRequest,
    ServiceDossier,
    ServiceItem,
    ServicesGraphReport,
    ServicesReport,
)

router = APIRouter(prefix='/api/v1/services-manager', tags=['Services Manager'])
_manager = ServicesManager()


@router.get('/summary', response_model=ServicesReport)
@router.get('/report', response_model=ServicesReport)
async def get_services_report() -> ServicesReport:
    """Сводный отчет о службах хоста из SQLite (< 5 мс)."""
    return await asyncio.to_thread(_manager.generate_report)


@router.post('/scan', response_model=ServicesReport)
@router.post('/refresh', response_model=ServicesReport)
async def trigger_services_scan() -> ServicesReport:
    """Принудительный опрос служб Windows с графом связей и сохранением среза в SQLite."""
    return await asyncio.to_thread(_manager.refresh_and_save)


@router.get('/list', response_model=List[ServiceItem])
async def list_services(
    status: Optional[str] = Query(None, description='RUNNING или STOPPED'),
    limit: int = Query(500, ge=1, le=2000, description='Лимит выборки'),
) -> List[ServiceItem]:
    """Список всех служб с фильтрацией по статусу из SQLite (< 5 мс)."""
    return await asyncio.to_thread(_manager.list_services, status, limit)


@router.get('/graph', response_model=ServicesGraphReport)
async def get_services_graph() -> ServicesGraphReport:
    """Глобальный граф связей служб Windows: группы svchost, общие PID, per-user экземпляры."""
    return await asyncio.to_thread(_manager.get_services_graph)


@router.get('/dossier/{service_name}', response_model=ServiceDossier)
async def get_service_dossier(service_name: str) -> ServiceDossier:
    """Глубокое досье службы: SCM, Registry, Process, Network, Event Log, телеметрия и граф связей."""
    dossier = await asyncio.to_thread(_manager.get_service_dossier, service_name)
    if dossier is None:
        raise HTTPException(status_code=404, detail=f"Служба '{service_name}' не найдена в каталоге.")
    return dossier


@router.post('/action')
@router.post('/actions')
async def execute_service_action(payload: ServiceActionRequest) -> Dict[str, Any]:
    """Запуск, остановка или изменение типа автозапуска службы."""
    return await _manager.execute_service_action(payload)


def init_router() -> APIRouter:
    """Возвращает инициализированный FastAPI роутер."""
    return router


__all__ = ['router', 'init_router']
