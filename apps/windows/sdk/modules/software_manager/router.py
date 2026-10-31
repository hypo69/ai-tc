# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Modules Software_Manager - Router
# =============================================================================
# Description:
#   # Description:
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.software_manager.router import init_router
#
#     res = init_router()
#
# File: router.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.software_manager
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-18 09:30:00
# =============================================================================

from __future__ import annotations
"""FastAPI роутер для управления пакетами WinGet, Microsoft Store и MSI."""

import asyncio
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from logger import logger
from apps.windows.sdk.modules.software_manager.core.manager import SoftwarePackagesManager
from apps.windows.sdk.modules.software_manager.core.models import (
    InstalledPackage,
    PackageActionRequest,
    SoftwareReport,
)

router = APIRouter(prefix='/api/software-manager', tags=['Software & Packages Manager'])
_manager = SoftwarePackagesManager()


@router.get('/summary', response_model=SoftwareReport)
@router.get('/report', response_model=SoftwareReport)
async def get_software_report(refresh: bool = Query(False, description='Принудительно обновить список')) -> SoftwareReport:
    """Сводный отчет об установленном ПО и доступных обновлениях."""
    return await asyncio.to_thread(_manager.generate_report, force_refresh=refresh)


@router.get('/packages', response_model=List[InstalledPackage])
async def list_packages(
    source: Optional[str] = Query(None, description='Фильтр источника (winget, msstore, msi)'),
    refresh: bool = Query(False, description='Принудительно обновить список')
) -> List[InstalledPackage]:
    """Список установленных программ."""
    return await asyncio.to_thread(_manager.list_packages, source=source, force_refresh=refresh)


@router.get('/store', response_model=List[InstalledPackage])
async def list_store_packages() -> List[InstalledPackage]:
    """Список установленных программ Microsoft Store (AppX/MSIX/msstore)."""
    return await asyncio.to_thread(_manager.list_store_packages)


@router.get('/search', response_model=List[InstalledPackage])
async def search_packages(q: str = Query(..., description='Поисковый запрос')) -> List[InstalledPackage]:
    """Поиск пакетов в репозиториях WinGet и Microsoft Store."""
    return await asyncio.to_thread(_manager.search_packages, q)


@router.post('/action')
@router.post('/actions')
async def execute_package_action(payload: PackageActionRequest) -> Dict[str, Any]:
    """Установка, обновление или удаление пакета."""
    return await _manager.execute_package_action(payload)


def init_router() -> APIRouter:
    """Возвращает инициализированный FastAPI роутер."""
    return router


__all__ = ['router', 'init_router']

