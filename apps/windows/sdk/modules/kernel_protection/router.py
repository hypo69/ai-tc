# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Modules Kernel Protection - Router
# =============================================================================
# Description:
#   FastAPI REST API роутер для инвентаризации системных драйверов Windows,
#   мониторинга файловых минифильтров, механизмов защиты ядра и диагностики блокировок.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.kernel_protection.router import router
#
#     app.include_router(router)
#
# File: router.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.kernel_protection
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 14:40:00
# =============================================================================

from __future__ import annotations
"""REST API роутер управления и диагностики драйверов и защиты ядра Windows."""

import asyncio
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from logger import logger

from apps.windows.sdk.modules.kernel_protection.core import (
    DriverCategory,
    DriverInventoryManager,
    KernelProtectionReport,
    KernelSafeOpsManager,
    MinifilterInfo,
    OperationBlockerDetector,
    ProtectionMechanismStatus,
    ProtectionMechanismsAuditor,
    SafeOpsActionRequest,
    SafeOpsActionResult,
    SystemDriverInfo,
    BlockerInvestigationRequest,
    BlockerVerdict,
)
from apps.windows.sdk.modules.kernel_protection.core.ucpd_manager import (
    TaskbarDaExperimentResult,
    UcpdFullStatus,
    UcpdSetStateRequest,
    UcpdSetStateResponse,
    UcpdSystemManager,
)

router = APIRouter(prefix='/api/kernel-protection', tags=['Kernel & Protection Manager'])

_inventory = DriverInventoryManager()
_mechanisms = ProtectionMechanismsAuditor()
_blocker_detector = OperationBlockerDetector()
_safe_ops = KernelSafeOpsManager()
_ucpd_manager = UcpdSystemManager()
_recent_verdicts: List[BlockerVerdict] = []


@router.get('/summary', response_model=KernelProtectionReport)
async def get_summary_report() -> KernelProtectionReport:
    """Получение сводного отчета о системе защиты ядра и драйверах Windows."""
    def _collect():
        mechs = _mechanisms.audit_all_mechanisms()
        minifilters = _inventory.get_active_minifilters()
        sec_drivers = _inventory.get_security_and_filter_drivers()
        all_drivers = _inventory.get_all_system_drivers()

        return KernelProtectionReport(
            total_drivers_count=len(all_drivers),
            security_drivers_count=len(sec_drivers),
            active_minifilters_count=len(minifilters),
            mechanisms=mechs,
            minifilters=minifilters,
            critical_security_drivers=sec_drivers,
            recent_verdicts=_recent_verdicts[-5:]
        )

    return await asyncio.to_thread(_collect)


@router.get('/drivers', response_model=List[SystemDriverInfo])
async def list_system_drivers(
    category: Optional[str] = Query(None, description='Фильтр: security, minifilter, system, third_party, all'),
    q: Optional[str] = Query(None, description='Поисковый запрос по имени или описанию')
) -> List[SystemDriverInfo]:
    """Список системных драйверов с фильтрацией по категории и поиском."""
    def _filter():
        all_drivers = _inventory.get_all_system_drivers()
        res = all_drivers

        if category and category.lower() != 'all':
            cat_low = category.lower()
            res = [d for d in res if d.category.value == cat_low]

        if q:
            query_low = q.lower().strip()
            res = [
                d for d in res
                if query_low in d.name.lower()
                or query_low in d.display_name.lower()
                or query_low in d.purpose_ru.lower()
            ]

        return res

    return await asyncio.to_thread(_filter)


@router.get('/minifilters', response_model=List[MinifilterInfo])
async def list_minifilters() -> List[MinifilterInfo]:
    """Список активных файловых минифильтров Windows с высотами (Altitudes)."""
    return await asyncio.to_thread(_inventory.get_active_minifilters)


@router.get('/mechanisms', response_model=List[ProtectionMechanismStatus])
async def list_protection_mechanisms() -> List[ProtectionMechanismStatus]:
    """Статус механизмов защиты ядра (HVCI, Secure Boot, UCPD, Defender Tamper, WDAC)."""
    return await asyncio.to_thread(_mechanisms.audit_all_mechanisms)


@router.post('/investigate-blocker', response_model=BlockerVerdict)
async def investigate_operation_blocker(req: BlockerInvestigationRequest) -> BlockerVerdict:
    """Диагностика Operation Blocker Detection: поиск причины ошибки Access Denied."""
    if not req.target_path.strip():
        raise HTTPException(status_code=400, detail="Целевой путь (target_path) не может быть пустым.")

    verdict = await asyncio.to_thread(_blocker_detector.investigate_blocker, req)
    _recent_verdicts.append(verdict)
    if len(_recent_verdicts) > 20:
        _recent_verdicts.pop(0)

    return verdict


@router.post('/safe-action', response_model=SafeOpsActionResult)
async def execute_safe_action(req: SafeOpsActionRequest) -> SafeOpsActionResult:
    """Безопасное выполнение контролируемого действия над драйвером защиты (SafeOps)."""
    return await asyncio.to_thread(_safe_ops.execute_action, req)


@router.get('/ucpd/status', response_model=UcpdFullStatus)
async def get_ucpd_detailed_status() -> UcpdFullStatus:
    """Детальный согласованный статус UCPD, драйвера, задачи UcpdVelocity и перезагрузки."""
    return await asyncio.to_thread(_ucpd_manager.get_detailed_status)


@router.post('/ucpd/set-state', response_model=UcpdSetStateResponse)
async def set_ucpd_state(req: UcpdSetStateRequest) -> UcpdSetStateResponse:
    """Управление состоянием UCPD с восстановлением исходной конфигурации и обработкой частичных сбоев."""
    return await asyncio.to_thread(_ucpd_manager.set_state, req)


@router.post('/ucpd/test-taskbarda', response_model=TaskbarDaExperimentResult)
async def run_taskbarda_experiment() -> TaskbarDaExperimentResult:
    """Экспериментальная проверка блокировки параметра TaskbarDa на текущей сборке ОС."""
    return await asyncio.to_thread(_ucpd_manager.test_taskbarda_blocker)


def init_router() -> APIRouter:
    """Инициализатор для авто-подключения роутера через AutoDiscovery."""
    return router
