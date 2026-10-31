# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Modules System_Checkpoints - Router
# =============================================================================
# Description:
#   FastAPI маршрутизатор для управления контрольными точками и средами восстановления Windows.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.system_checkpoints.router import NativeRestorePointCreateRequest
#
#     service = NativeRestorePointCreateRequest()
#
# File: router.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.system_checkpoints
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-16 22:17:00
# =============================================================================

from __future__ import annotations
"""FastAPI маршрутизатор для управления контрольными точками и средами восстановления Windows."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from apps.windows.system_checkpoints.models import (
    AdvisorTrigger,
    CheckpointCreateRequest,
    CheckpointType,
    SmartRestorePointCreateRequest,
    WimImageCreateRequest,
    WinREActionRequest,
)
from apps.windows.system_checkpoints.core.checkpoint_coordinator import CheckpointCoordinator
from apps.windows.system_checkpoints.core.image_manager import SystemImageManager
from apps.windows.system_checkpoints.core.winre_manager import WinREManager
from apps.windows.system_checkpoints.core.freshness_auditor import FreshnessAuditor
from apps.windows.system_checkpoints.core.restore_point_advisor import RestorePointAdvisor
from apps.windows.api.auth import require_admin_user

router = APIRouter(prefix="/api/v1/windows-checkpoints", tags=["windows-checkpoints"])

_coordinator = CheckpointCoordinator()
_image_mgr = _coordinator.image_manager
_winre_mgr = _coordinator.winre_manager
_freshness_auditor = _coordinator.freshness_auditor
_advisor = _coordinator.advisor


@router.get("/health")
async def get_checkpoints_health() -> Dict[str, Any]:
    """Сводный отчет готовности всех трех механизмов восстановления (Health Score 0-100)."""
    return _coordinator.get_comprehensive_health()


@router.get("/freshness")
async def get_image_freshness() -> Dict[str, Any]:
    """Детальный отчет актуальности образов восстановления и метрик дрейфа (System Drift)."""
    report = _coordinator.get_freshness_report()
    return report.to_dict()


@router.get("/catalog")
async def get_checkpoint_catalog() -> List[Dict[str, Any]]:
    """Получение списка всех сохраненных контрольных точек системы."""
    records = _coordinator.load_catalog()
    return [r.to_dict() for r in records]


@router.post("/catalog")
async def create_system_checkpoint(request: Request, req: CheckpointCreateRequest) -> Dict[str, Any]:
    """Создание новой контрольной точки системы (Базовая, После настройки, Перед обновлением и т.д.)."""
    require_admin_user(request)
    return _coordinator.create_checkpoint(req)


@router.delete("/catalog/{checkpoint_id}")
async def delete_system_checkpoint(request: Request, checkpoint_id: str) -> Dict[str, Any]:
    """Удаление контрольной точки из каталога."""
    require_admin_user(request)
    deleted = _coordinator.delete_checkpoint(checkpoint_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Контрольная точка с указанным ID не найдена")
    return {"success": True, "checkpoint_id": checkpoint_id, "message": "Контрольная точка удалена"}


@router.get("/images")
async def list_recovery_images() -> List[Dict[str, Any]]:
    """Поиск и инвентаризация системных WIM-образов на дисках."""
    images = _image_mgr.scan_recovery_images()
    return [img.to_dict() for img in images]


@router.post("/images/create-baseline")
async def create_baseline_image(request: Request, req: WimImageCreateRequest, dry_run: bool = False) -> Dict[str, Any]:
    """Создание базового эталонного WIM-образа чистой системы через DISM."""
    require_admin_user(request)
    res = _image_mgr.create_baseline_image(
        source_drive=req.source_drive,
        destination_dir=req.destination_dir,
        image_name=req.image_name,
        description=req.description,
        dry_run=dry_run,
    )
    return res


@router.post("/images/create-periodic")
async def create_periodic_image(request: Request, req: WimImageCreateRequest, dry_run: bool = False) -> Dict[str, Any]:
    """Создание периодической контрольной точки / версионированного WIM-образа."""
    require_admin_user(request)
    res = _image_mgr.create_periodic_checkpoint(
        source_drive=req.source_drive,
        destination_dir=req.destination_dir,
        image_name=req.image_name,
        description=req.description,
        append_if_exists=req.append_if_exists,
        dry_run=dry_run,
    )
    return res


@router.get("/winre/status")
async def get_winre_status() -> Dict[str, Any]:
    """Диагностика статуса среды восстановления Windows RE (reagentc /info)."""
    status = _winre_mgr.get_status()
    return status.to_dict()


@router.post("/winre/action")
async def execute_winre_action(request: Request, req: WinREActionRequest) -> Dict[str, Any]:
    """Управление средой восстановления Windows RE (enable, disable, set_path)."""
    require_admin_user(request)
    action = req.action.lower()
    if action == "enable":
        return _winre_mgr.enable()
    elif action == "disable":
        return _winre_mgr.disable()
    elif action == "set_path":
        if not req.custom_path:
            raise HTTPException(status_code=400, detail="Параметр custom_path обязателен для set_path")
        return _winre_mgr.set_reimage_path(req.custom_path)
    else:
        raise HTTPException(status_code=400, detail=f"Неизвестное действие: {req.action}")


@router.get("/restore-points")
async def list_native_restore_points() -> List[Dict[str, Any]]:
    """Список нативных точек восстановления Windows (System Restore / VSS)."""
    sr_mgr = _coordinator._get_restore_manager()
    if not sr_mgr:
        return []
    return sr_mgr.list_restore_points()


class NativeRestorePointCreateRequest(BaseModel):
    """Модель создания нативной точки восстановления."""
    title: str = Field(..., description="Название точки восстановления")
    checkpoint_type: CheckpointType = Field(default=CheckpointType.PERIODIC, description="Категория точки")


@router.post("/restore-points")
async def create_native_restore_point(request: Request, req: NativeRestorePointCreateRequest) -> Dict[str, Any]:
    """Создание нативной точки восстановления Windows."""
    require_admin_user(request)
    chk_req = CheckpointCreateRequest(
        checkpoint_type=req.checkpoint_type,
        title=req.title,
        create_restore_point=True,
        create_wim_image=False,
    )
    return _coordinator.create_checkpoint(chk_req)


# --- Эндпоинты умного советника (Smart Restore Point Advisor) ---

@router.get("/advisor/evaluate")
async def evaluate_restore_need(trigger: str = "USER_REQUEST") -> Dict[str, Any]:
    """Предварительная интеллектуальная оценка целесообразности создания точки восстановления.

    Отвечает на три вопроса:
    1. Есть ли смысл создавать точку?
    2. Не дублирует ли она предыдущую?
    3. Достаточно ли данных и условий для восстановления?
    """
    eval_res = _advisor.evaluate(trigger_event=trigger)
    return eval_res.to_dict()


@router.post("/advisor/create-smart")
async def create_smart_restore_point(request: Request, req: SmartRestorePointCreateRequest) -> Dict[str, Any]:
    """Создание точки восстановления с предварительной проверкой состояния и дедупликацией."""
    require_admin_user(request)
    return _advisor.execute_smart_restore_point(
        title=req.title,
        trigger_event=req.trigger.value,
        force=req.force,
        checkpoint_type=req.checkpoint_type,
    )


@router.get("/advisor/journal")
async def get_smart_restore_journal(limit: int = 50) -> List[Dict[str, Any]]:
    """Получение журнала срезов состояний, отпечатков и зафиксированных дельт."""
    return _advisor.journal.get_recent_snapshots(limit=limit)


@router.get("/advisor/readiness")
async def get_restore_readiness() -> Dict[str, Any]:
    """Проверка условий готовности системы к созданию точек (VSS, защита диска, квоты)."""
    return _advisor.check_readiness()


class ExplainRequest(BaseModel):
    """Запрос на генерацию русскоязычного пояснения решения."""
    trigger: str = "USER_REQUEST"


@router.post("/advisor/explain")
async def explain_advisor_decision(req: ExplainRequest) -> Dict[str, Any]:
    """Генерация детального объяснения решения советника на естественном языке."""
    eval_res = _advisor.evaluate(trigger_event=req.trigger)
    explanation = _advisor.explain_with_ai(eval_res)
    return {
        "decision": eval_res.decision.value,
        "summary": eval_res.summary,
        "explanation": explanation,
        "evaluation": eval_res.to_dict(),
    }


def init_router(app: Optional[Any] = None, state: Optional[Any] = None) -> APIRouter:
    """Фабричная функция инициализации роутера."""
    return router


__all__ = ["router", "init_router"]

