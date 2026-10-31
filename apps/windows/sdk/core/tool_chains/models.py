# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows SDK - Tool Chains Models
# =============================================================================
# Description:
#   Модели данных для построения и запуска цепочек инструментов Windows (Tool Chains).
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.core.tool_chains.models import ChainDefinition, ChainStepDefinition
#
# File: models.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.core.tool_chains
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 17:35:00
# =============================================================================

from __future__ import annotations

"""Модели данных для построения, планирования и исполнения цепочек инструментов Windows."""

import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from apps.windows.contracts.enums import CapabilityCategory, ExecutionMethod, PrivilegeLevel, RiskLevel


class ChainRunStatus(str, enum.Enum):
    """Статусы выполнения цепочки инструментов."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"
    CANCELLED = "CANCELLED"
    PAUSED = "PAUSED"


class StepRunStatus(str, enum.Enum):
    """Статусы выполнения отдельного шага цепочки."""
    PENDING = "PENDING"
    SKIPPED = "SKIPPED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    COMPENSATED = "COMPENSATED"


class ConditionOperator(str, enum.Enum):
    """Операторы для проверки условий перехода и ветвления."""
    EQUALS = "EQUALS"
    NOT_EQUALS = "NOT_EQUALS"
    CONTAINS = "CONTAINS"
    NOT_CONTAINS = "NOT_CONTAINS"
    GREATER_THAN = "GREATER_THAN"
    LESS_THAN = "LESS_THAN"
    IS_EMPTY = "IS_EMPTY"
    IS_NOT_EMPTY = "IS_NOT_EMPTY"
    EXIT_CODE_ZERO = "EXIT_CODE_ZERO"
    ALWAYS_TRUE = "ALWAYS_TRUE"


@dataclass
class BranchCondition:
    """Условие динамического перехода к следующему шагу."""
    operator: ConditionOperator = ConditionOperator.ALWAYS_TRUE
    field_path: str = ""
    expected_value: Any = None
    target_step_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Преобразование условия в словарь."""
        return {
            "operator": self.operator.value,
            "field_path": self.field_path,
            "expected_value": self.expected_value,
            "target_step_id": self.target_step_id,
        }


@dataclass
class CompensationAction:
    """Компенсационное действие или процедура отката при сбое шага."""
    action_id: str
    tool_id: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    timeout_seconds: int = 30

    def to_dict(self) -> Dict[str, Any]:
        """Преобразование компенсации в словарь."""
        return {
            "action_id": self.action_id,
            "tool_id": self.tool_id,
            "arguments": self.arguments,
            "description": self.description,
            "timeout_seconds": self.timeout_seconds,
        }


@dataclass
class ChainStepDefinition:
    """Определение отдельного шага цепочки инструментов."""
    step_id: str
    tool_id: str
    name_ru: str
    description: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    risk_level: RiskLevel = RiskLevel.READ_ONLY
    required_privilege: PrivilegeLevel = PrivilegeLevel.STANDARD
    execution_method: ExecutionMethod = ExecutionMethod.CLI
    timeout_seconds: int = 60
    preconditions: List[str] = field(default_factory=list)
    postconditions: List[str] = field(default_factory=list)
    branch_conditions: List[BranchCondition] = field(default_factory=list)
    compensation: Optional[CompensationAction] = None
    next_step_id: Optional[str] = None
    allow_failure: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Преобразование шага в словарь."""
        return {
            "step_id": self.step_id,
            "tool_id": self.tool_id,
            "name_ru": self.name_ru,
            "description": self.description,
            "arguments": self.arguments,
            "risk_level": self.risk_level.value,
            "required_privilege": self.required_privilege.value,
            "execution_method": self.execution_method.value,
            "timeout_seconds": self.timeout_seconds,
            "preconditions": self.preconditions,
            "postconditions": self.postconditions,
            "branch_conditions": [b.to_dict() for b in self.branch_conditions],
            "compensation": self.compensation.to_dict() if self.compensation else None,
            "next_step_id": self.next_step_id,
            "allow_failure": self.allow_failure,
        }


@dataclass
class ChainDefinition:
    """Полное определение диагностической или административной цепочки инструментов."""
    chain_id: str
    title_ru: str
    description: str
    category: CapabilityCategory = CapabilityCategory.PROCESSES
    initial_step_id: str = ""
    steps: Dict[str, ChainStepDefinition] = field(default_factory=dict)
    max_execution_time_seconds: int = 300
    requires_restore_point: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Преобразование цепочки в словарь."""
        return {
            "chain_id": self.chain_id,
            "title_ru": self.title_ru,
            "description": self.description,
            "category": self.category.value,
            "initial_step_id": self.initial_step_id,
            "steps": {k: v.to_dict() for k, v in self.steps.items()},
            "max_execution_time_seconds": self.max_execution_time_seconds,
            "requires_restore_point": self.requires_restore_point,
            "metadata": self.metadata,
        }


@dataclass
class StepExecutionResult:
    """Результат выполнения отдельного шага."""
    step_id: str
    tool_id: str
    status: StepRunStatus
    start_time: str
    end_time: str
    duration_ms: float
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    structured_data: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    evidence_collected: Dict[str, Any] = field(default_factory=dict)
    next_step_decided: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Преобразование результата шага в словарь."""
        return {
            "step_id": self.step_id,
            "tool_id": self.tool_id,
            "status": self.status.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": round(self.duration_ms, 2),
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "structured_data": self.structured_data,
            "error_message": self.error_message,
            "evidence_collected": self.evidence_collected,
            "next_step_decided": self.next_step_decided,
        }


@dataclass
class ChainRunReport:
    """Итоговый отчет о выполнении цепочки инструментов с доказательствами."""
    run_id: str
    chain_id: str
    status: ChainRunStatus
    user_intent: str
    start_time: str
    end_time: Optional[str] = None
    total_duration_ms: float = 0.0
    steps_executed: List[StepExecutionResult] = field(default_factory=list)
    findings_summary: List[str] = field(default_factory=list)
    root_cause_identified: Optional[str] = None
    recommended_remediations: List[str] = field(default_factory=list)
    restore_point_created: bool = False
    restore_point_id: Optional[str] = None
    rolled_back: bool = False
    telemetry_snapshots: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Преобразование отчета выполнения в словарь."""
        return {
            "run_id": self.run_id,
            "chain_id": self.chain_id,
            "status": self.status.value,
            "user_intent": self.user_intent,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "total_duration_ms": round(self.total_duration_ms, 2),
            "steps_executed": [s.to_dict() for s in self.steps_executed],
            "findings_summary": self.findings_summary,
            "root_cause_identified": self.root_cause_identified,
            "recommended_remediations": self.recommended_remediations,
            "restore_point_created": self.restore_point_created,
            "restore_point_id": self.restore_point_id,
            "rolled_back": self.rolled_back,
            "telemetry_snapshots": self.telemetry_snapshots,
        }


class RunChainApiRequest(BaseModel):
    """Pydantic схема запроса на запуск цепочки инструментов."""
    chain_id: Optional[str] = Field(None, description="Идентификатор существующего шаблона цепочки")
    user_intent: Optional[str] = Field(None, description="Запрос пользователя на естественном языке")
    dry_run: bool = Field(False, description="Режим безопасной симуляции Dry-Run")
    custom_arguments: Dict[str, Any] = Field(default_factory=dict, description="Пользовательские аргументы шагов")
    create_restore_point: bool = Field(False, description="Принудительное создание точки восстановления VSS")


class PlanChainApiRequest(BaseModel):
    """Pydantic схема запроса на семантическое планирование цепочки."""
    user_intent: str = Field(..., description="Цель, симптом или задача пользователя")
    max_steps: int = Field(6, description="Максимальное количество шагов цепочки")

