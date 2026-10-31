# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows API - Settings Router
# =============================================================================
# Description:
#   FastAPI REST API роутер для единого каталога параметров Windows (Control Catalog),
#   конфигурации мониторов/дисплеев, настроек панели задач и шлюза Command Registry.
#
# Usage Examples:
#   Python API:
#     from apps.windows.api.routers.router_settings import router as settings_router
#
# File: router_settings.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 13:00:00
# =============================================================================

from __future__ import annotations
"""REST API маршруты для каталога настроек Windows и управления дисплеями."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from apps.windows.sdk.display.display_config import DisplayConfigManager
from apps.windows.sdk.display.display_models import (
    DisplayItem,
    DisplayOrientation,
    DisplayRotateRequest,
    DisplayRotateResponse,
)
from apps.windows.sdk.shell.taskbar_config import TaskbarConfigManager
from apps.windows.sdk.settings.catalog import WINDOWS_SETTINGS, get_settings_catalog
from apps.windows.sdk.settings.resolver import ResolutionResult, SettingsResolver
from apps.windows.commands.windows_settings import (
    CommandExecutionRequest,
    CommandExecutionResult,
    WindowsSettingsExecutor,
)

router = APIRouter(prefix="/api/v1/settings", tags=["Windows Settings & Control Plane"])

_executor = WindowsSettingsExecutor()
_display_mgr = DisplayConfigManager()
_taskbar_mgr = TaskbarConfigManager()
_resolver = SettingsResolver()


class ConfirmRotationRequest(BaseModel):
    """Запрос на подтверждение ориентации экрана."""
    display_id: str = Field(..., description="Идентификатор дисплея")


class RollbackRequest(BaseModel):
    """Запрос на откат команды."""
    command: str = Field(..., description="Идентификатор команды для отката")


@router.get("/catalog")
async def get_catalog() -> Dict[str, Any]:
    """Возвращает декларативный каталог параметров Windows с резолвом доступности."""
    resolved_catalog: List[Dict[str, Any]] = []

    for cmd_id, meta in WINDOWS_SETTINGS.items():
        res: ResolutionResult = _resolver.resolve(cmd_id)
        item = dict(meta)
        item["status"] = res.status
        item["is_supported"] = res.is_supported
        item["recommended_backend"] = res.recommended_backend
        item["supported_values"] = res.supported_values
        item["reason"] = res.reason
        item["is_win11"] = res.is_win11
        item["build_number"] = res.build_number
        resolved_catalog.append(item)

    return {
        "status": "success",
        "total": len(resolved_catalog),
        "is_win11": _resolver.is_win11,
        "build_number": _resolver.build_number,
        "items": resolved_catalog,
    }


@router.get("/displays", response_model=List[DisplayItem])
async def list_displays() -> List[DisplayItem]:
    """Возвращает список всех подключенных дисплеев и их параметры."""
    return _display_mgr.list_displays()


@router.get("/taskbar")
async def get_taskbar_state() -> Dict[str, Any]:
    """Возвращает текущие параметры панели задач."""
    return {
        "status": "success",
        "state": _taskbar_mgr.get_current_state(),
    }


@router.post("/execute", response_model=CommandExecutionResult)
async def execute_command(req: CommandExecutionRequest) -> CommandExecutionResult:
    """Единый шлюз выполнения команд управления Windows Control Plane."""
    return _executor.execute(req.command, req.params)


@router.post("/display/rotate", response_model=DisplayRotateResponse)
async def rotate_display(req: DisplayRotateRequest) -> DisplayRotateResponse:
    """Поворачивает дисплей с таймером подтверждения и защитой от некорректных режимов."""
    return _display_mgr.rotate_display(
        display_id=req.display_id,
        target_orientation=req.orientation,
        timeout_seconds=req.timeout_seconds,
        auto_rollback=req.auto_rollback,
    )


@router.post("/display/confirm")
async def confirm_display_rotation(req: ConfirmRotationRequest) -> Dict[str, Any]:
    """Подтверждает новую ориентацию дисплея и отменяет таймер отката."""
    ok = _display_mgr.confirm_rotation(req.display_id)
    return {
        "success": ok,
        "display_id": req.display_id,
        "message": "Ориентация успешно подтверждена" if ok else "Активная сессия поворота не найдена",
    }


@router.post("/display/rollback")
async def rollback_display_rotation(req: ConfirmRotationRequest) -> Dict[str, Any]:
    """Принудительно возвращает исходную ориентацию дисплея."""
    ok = _display_mgr.rollback_rotation(req.display_id)
    return {
        "success": ok,
        "display_id": req.display_id,
        "message": "Ориентация успешно возвращена" if ok else "Не удалось выполнить откат",
    }


@router.post("/rollback", response_model=CommandExecutionResult)
async def rollback_last_command(req: RollbackRequest) -> CommandExecutionResult:
    """Откатывает последнее состояние указанной команды."""
    return _executor.rollback(req.command)

