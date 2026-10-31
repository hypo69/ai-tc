# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - SafeOps Executor
# =============================================================================
# Description:
#   FastAPI REST эндпоинты для симуляции (Dry-Run), валидации и безопасного
#   выполнения корректирующих действий (Action Launchers) по протоколу SafeOps.
#
# Usage Examples:
#   Python API:
#     from apps.windows.api.routers.router_safe_ops import router
#
# File: router_safe_ops.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-13 13:42:00
# =============================================================================

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from logger import logger
from apps.windows.contracts.enums import ActionType, RiskLevel
from apps.windows.contracts.audit import RemediationAction
from apps.windows.sdk.core.safe_executor import SafeExecutor

__root__ = Path(__file__).resolve().parents[3]


# -----------------------------------------------------------------------------
# DTO Models
# -----------------------------------------------------------------------------

class SafeOpsActionDTO(BaseModel):
    """Модель передачи данных действия (Action Launcher)."""
    action_id: str = Field(..., description="Уникальный идентификатор действия")
    action_type: str = Field(default="custom_command", description="Тип действия из перечисления ActionType")
    title: str = Field(..., description="Человекочитаемое название действия")
    description: str = Field(default="", description="Описание назначения и последствий действия")
    target: str = Field(default="", description="Целевой объект (путь к файлу, имя службы, PID, имя задачи)")
    risk: str = Field(default="caution", description="Уровень риска: safe, caution, critical")
    releasable_bytes: int = Field(default=0, ge=0, description="Оцениваемый освобождаемый объем в байтах")
    dry_run_command: str = Field(default="", description="Команда для симуляции или dry-run режима")
    execution_command: str = Field(default="", description="Команда для применения исправления")
    requires_reboot: bool = Field(default=False, description="Флаг необходимости перезагрузки ОС")
    requires_elevation: bool = Field(default=True, description="Требуются ли права администратора")


class SafeOpsSimulateRequest(BaseModel):
    """Запрос на симуляцию (Dry-Run) действия."""
    action: SafeOpsActionDTO = Field(..., description="Действие для симуляции")


class SafeOpsSimulateResponse(BaseModel):
    """Результат симуляции действия."""
    action_id: str = Field(description="ID действия")
    target: str = Field(description="Целевой объект")
    risk: str = Field(description="Уровень риска")
    simulated: bool = Field(default=True, description="Флаг симуляции")
    safe_to_execute: bool = Field(default=True, description="Безопасно ли действие к запуску")
    would_delete_files_count: int = Field(default=0, description="Количество удаляемых файлов")
    releasable_bytes: int = Field(default=0, description="Освобождаемый объем в байтах")
    releasable_mb: float = Field(default=0.0, description="Освобождаемый объем в мегабайтах")
    command: str = Field(default="", description="Симулируемая команда")
    details: List[str] = Field(default_factory=list, description="Детали симуляции")
    error: Optional[str] = Field(default=None, description="Сообщение об ошибке симуляции")


class SafeOpsExecuteRequest(BaseModel):
    """Запрос на выполнение действия с контролем риска."""
    action: SafeOpsActionDTO = Field(..., description="Действие для выполнения")
    confirmed_by_user: bool = Field(default=False, description="Явное подтверждение пользователя для действий caution/critical")
    operator: Optional[str] = Field(default="tc_admin", description="Идентификатор оператора или системы")


class SafeOpsExecuteResponse(BaseModel):
    """Результат выполнения действия SafeOps."""
    action_id: str = Field(description="ID действия")
    status: str = Field(description="Статус: 'ok' или 'error'")
    executed: bool = Field(description="Было ли действие фактически выполнено")
    success: bool = Field(description="Успешно ли завершилось действие")
    message: str = Field(description="Пользовательское сообщение о результате")
    error_message: Optional[str] = Field(default=None, description="Текст ошибки при сбое")
    releasable_bytes: int = Field(default=0, description="Освобожденный объем в байтах")
    executed_at: str = Field(description="Время выполнения операции (ISO 8601)")


class SafeOpsAuditItem(BaseModel):
    """Запись журнала аудита SafeOps."""
    id: str = Field(description="Уникальный ID записи аудита")
    action_id: str = Field(description="ID действия")
    action_type: str = Field(description="Тип действия")
    title: str = Field(description="Название действия")
    target: str = Field(description="Целевой объект")
    risk: str = Field(description="Уровень риска")
    status: str = Field(description="Статус: ok, blocked, error")
    timestamp: str = Field(description="Время фиксации")
    operator: str = Field(description="Оператор")
    message: str = Field(description="Сообщение аудита")


class SafeOpsCatalogResponse(BaseModel):
    """Каталог поддерживаемых типов операций и политик SafeOps."""
    supported_types: List[str] = Field(description="Список поддерживаемых типов действий")
    risk_levels: List[str] = Field(description="Список уровней риска")
    policy: Dict[str, Any] = Field(description="Политика безопасности и правила подтверждения")


class SafeOpsValidateRequest(BaseModel):
    """Запрос на валидацию действия."""
    action: SafeOpsActionDTO = Field(..., description="Действие для валидации")


class SafeOpsValidateResponse(BaseModel):
    """Результат валидации действия."""
    valid: bool = Field(description="Валидно ли действие")
    action_id: str = Field(description="ID действия")
    normalized_type: str = Field(description="Нормализованный тип действия")
    normalized_risk: str = Field(description="Нормализованный уровень риска")
    requires_user_confirmation: bool = Field(description="Требует ли подтверждения пользователя")
    issues: List[str] = Field(default_factory=list, description="Список замечаний или ошибок")


# -----------------------------------------------------------------------------
# Router & Internal State
# -----------------------------------------------------------------------------

router = APIRouter(prefix="/api/v1/safeops", tags=["SafeOps Execution Engine"])

_audit_history: List[SafeOpsAuditItem] = []
MAX_AUDIT_HISTORY = 100


def _parse_action(dto: SafeOpsActionDTO) -> RemediationAction:
    """Преобразует DTO в доменную модель RemediationAction с валидацией Enum."""
    try:
        act_type = ActionType(dto.action_type)
    except Exception:
        act_type = ActionType.CUSTOM_COMMAND

    try:
        r_level = RiskLevel(dto.risk.lower())
    except Exception:
        r_level = RiskLevel.CAUTION

    return RemediationAction(
        action_id=dto.action_id,
        action_type=act_type,
        title=dto.title or dto.action_id,
        description=dto.description,
        target=dto.target,
        risk=r_level,
        releasable_bytes=dto.releasable_bytes,
        dry_run_command=dto.dry_run_command,
        execution_command=dto.execution_command,
        requires_reboot=dto.requires_reboot,
        requires_elevation=dto.requires_elevation,
    )


def _record_audit(
    action: RemediationAction,
    status: str,
    operator: str,
    message: str,
) -> None:
    """Фиксирует запись в кольцевом журнале аудита SafeOps."""
    global _audit_history
    entry = SafeOpsAuditItem(
        id=str(uuid.uuid4())[:8],
        action_id=action.action_id,
        action_type=action.action_type.value if hasattr(action.action_type, "value") else str(action.action_type),
        title=action.title,
        target=action.target,
        risk=action.risk.value if hasattr(action.risk, "value") else str(action.risk),
        status=status,
        timestamp=datetime.now(timezone.utc).isoformat(),
        operator=operator or "system",
        message=message,
    )
    _audit_history.insert(0, entry)
    if len(_audit_history) > MAX_AUDIT_HISTORY:
        _audit_history.pop()


# -----------------------------------------------------------------------------
# REST Endpoints
# -----------------------------------------------------------------------------

@router.get("/actions", response_model=SafeOpsCatalogResponse)
async def get_safeops_catalog() -> SafeOpsCatalogResponse:
    """Возвращает каталог поддерживаемых типов операций, уровней риска и политик SafeOps."""
    return SafeOpsCatalogResponse(
        supported_types=[e.value for e in ActionType],
        risk_levels=[e.value for e in RiskLevel],
        policy={
            "safe": "Выполняется сразу без обязательного интерактивного подтверждения",
            "caution": "Требует обязательного подтверждения оператором (confirmed_by_user=True)",
            "critical": "Требует строгого подтверждения оператором и повышенных привилегий",
            "simulation": "Поддерживается предварительный Dry-Run расчет освобождаемого пространства",
            "audit": "Все действия протоколируются в защищенном журнале аудита",
        },
    )


@router.post("/simulate", response_model=SafeOpsSimulateResponse)
async def simulate_safeops_action(req: SafeOpsSimulateRequest) -> SafeOpsSimulateResponse:
    """Выполняет предварительную симуляцию (Dry-Run) корректирующего действия."""
    action = _parse_action(req.action)
    executor = SafeExecutor()

    try:
        sim_data = await asyncio.to_thread(executor.simulate, action)
        return SafeOpsSimulateResponse(
            action_id=action.action_id,
            target=action.target,
            risk=action.risk.value if hasattr(action.risk, "value") else str(action.risk),
            simulated=True,
            safe_to_execute=sim_data.get("safe_to_execute", True),
            would_delete_files_count=sim_data.get("would_delete_files_count", 0),
            releasable_bytes=sim_data.get("releasable_bytes", 0),
            releasable_mb=sim_data.get("releasable_mb", 0.0),
            command=sim_data.get("command", ""),
            details=sim_data.get("details", []),
            error=sim_data.get("error"),
        )
    except Exception as exc:
        logger.error(f"[SafeOps] Ошибка симуляции действия {action.action_id}: {exc}", exc_info=True)
        return SafeOpsSimulateResponse(
            action_id=action.action_id,
            target=action.target,
            risk=action.risk.value if hasattr(action.risk, "value") else str(action.risk),
            simulated=True,
            safe_to_execute=False,
            error=str(exc),
        )


@router.post("/execute", response_model=SafeOpsExecuteResponse)
async def execute_safeops_action(req: SafeOpsExecuteRequest) -> SafeOpsExecuteResponse:
    """Безопасно выполняет корректирующее действие с проверкой уровня риска и прав."""
    action = _parse_action(req.action)
    executor = SafeExecutor()
    now_iso = datetime.now(timezone.utc).isoformat()
    operator_name = req.operator or "tc_admin"

    # Предохранитель SafeOps: блокировка рискованных операций без явного подтверждения
    is_risky = action.risk in (RiskLevel.CAUTION, RiskLevel.CRITICAL)
    if is_risky and not req.confirmed_by_user:
        msg = f"Действие уровня '{action.risk.value}' требует явного подтверждения пользователя."
        logger.warning(f"[SafeOps] Блокировка неподтвержденного действия: {action.action_id}")
        _record_audit(action, "blocked", operator_name, msg)
        return SafeOpsExecuteResponse(
            action_id=action.action_id,
            status="error",
            executed=False,
            success=False,
            message=msg,
            error_message=msg,
            releasable_bytes=0,
            executed_at=now_iso,
        )

    # Исполнение через SafeExecutor
    try:
        res_action = await asyncio.to_thread(executor.execute, action, req.confirmed_by_user)
        if res_action.success:
            succ_msg = f"Действие '{res_action.title}' успешно выполнено."
            logger.info(f"[SafeOps] {succ_msg} (ID: {res_action.action_id})")
            _record_audit(res_action, "ok", operator_name, succ_msg)
            return SafeOpsExecuteResponse(
                action_id=res_action.action_id,
                status="ok",
                executed=res_action.executed,
                success=True,
                message=succ_msg,
                releasable_bytes=res_action.releasable_bytes,
                executed_at=now_iso,
            )
        else:
            err_msg = res_action.error_message or "Сбой при выполнении системного действия."
            logger.warning(f"[SafeOps] Ошибка исполнения {res_action.action_id}: {err_msg}")
            _record_audit(res_action, "error", operator_name, err_msg)
            return SafeOpsExecuteResponse(
                action_id=res_action.action_id,
                status="error",
                executed=res_action.executed,
                success=False,
                message=err_msg,
                error_message=err_msg,
                releasable_bytes=0,
                executed_at=now_iso,
            )
    except Exception as exc:
        err_msg = f"Исключение при выполнении SafeOps: {exc}"
        logger.error(f"[SafeOps] {err_msg}", exc_info=True)
        _record_audit(action, "error", operator_name, err_msg)
        return SafeOpsExecuteResponse(
            action_id=action.action_id,
            status="error",
            executed=True,
            success=False,
            message=err_msg,
            error_message=str(exc),
            releasable_bytes=0,
            executed_at=now_iso,
        )


@router.get("/history", response_model=List[SafeOpsAuditItem])
async def get_safeops_history(
    limit: int = Query(default=20, ge=1, le=100, description="Количество записей журнала")
) -> List[SafeOpsAuditItem]:
    """Возвращает историю выполненных и заблокированных действий SafeOps."""
    return _audit_history[:limit]


@router.post("/validate", response_model=SafeOpsValidateResponse)
async def validate_safeops_action(req: SafeOpsValidateRequest) -> SafeOpsValidateResponse:
    """Валидирует параметры действия перед представлением в UI."""
    issues: List[str] = []
    dto = req.action

    if not dto.action_id or not dto.action_id.strip():
        issues.append("action_id не может быть пустым")

    if not dto.title or not dto.title.strip():
        issues.append("title не может быть пустым")

    try:
        act_type = ActionType(dto.action_type)
        norm_type = act_type.value
    except Exception:
        norm_type = ActionType.CUSTOM_COMMAND.value
        issues.append(f"Неизвестный action_type '{dto.action_type}', будет использован 'custom_command'")

    try:
        r_level = RiskLevel(dto.risk.lower())
        norm_risk = r_level.value
    except Exception:
        norm_risk = RiskLevel.CAUTION.value
        issues.append(f"Неизвестный risk '{dto.risk}', будет использован 'caution'")

    requires_confirm = norm_risk in (RiskLevel.CAUTION.value, RiskLevel.CRITICAL.value)

    return SafeOpsValidateResponse(
        valid=len([i for i in issues if "не может быть пустым" in i]) == 0,
        action_id=dto.action_id,
        normalized_type=norm_type,
        normalized_risk=norm_risk,
        requires_user_confirmation=requires_confirm,
        issues=issues,
    )


def init_router() -> APIRouter:
    """Фабричная функция инициализации роутера SafeOps."""
    return router

