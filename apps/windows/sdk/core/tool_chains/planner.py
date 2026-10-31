# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows SDK - Tool Chains Planner
# =============================================================================
# Description:
#   Интеллектуальный планировщик цепочек инструментов на базе семантического сопоставления.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.core.tool_chains.planner import ToolChainPlanner
#     planner = ToolChainPlanner()
#     chain = planner.plan_from_intent("Проверь сетевой порт 8001")
#
# File: planner.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.core.tool_chains
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 17:35:00
# =============================================================================

from __future__ import annotations

"""Семантический и эвристический планировщик диагностических цепочек инструментов."""

import re
import uuid
from typing import Any, Dict, List, Optional
from logger import logger

from apps.windows.contracts.enums import CapabilityCategory, ExecutionMethod, PrivilegeLevel, RiskLevel
from apps.windows.sdk.core.atomic_capabilities import WindowsAtomicCapabilitiesRegistry
from apps.windows.sdk.core.system32_catalog import System32Catalog
from apps.windows.sdk.core.tool_chains.catalog import get_builtin_chains
from apps.windows.sdk.core.tool_chains.models import (
    BranchCondition,
    ChainDefinition,
    ChainStepDefinition,
    ConditionOperator,
)


class ToolChainPlanner:
    """Планировщик цепочек инструментов для преобразования симптомов и целей в граф выполнения."""

    def __init__(self) -> None:
        """Инициализация планировщика со связью с системными каталогами."""
        self._atomic_registry = WindowsAtomicCapabilitiesRegistry.get_instance()
        self._system32_catalog = System32Catalog.get_instance()
        self._builtin_chains = get_builtin_chains()

    def plan_from_intent(self, intent: str, max_steps: int = 6) -> ChainDefinition:
        """Формирует цепочку инструментов на основе запроса пользователя.

        Args:
            intent: Пользовательский запрос или симптом на естественном языке.
            max_steps: Максимальное количество шагов в сформированной цепочке.

        Returns:
            ChainDefinition: Скомпилированное определение цепочки инструментов.
        """
        intent_lower = intent.lower()

        # 1. Проверка совпадения с готовыми шаблонами
        if any(w in intent_lower for w in ["порт", "port", "сокет", "socket", "8001", "8080", "listener"]):
            base_chain = self._builtin_chains.get("diag.network.port_availability")
            if base_chain:
                port_match = re.search(r"\b(\d{2,5})\b", intent)
                port_val = int(port_match.group(1)) if port_match else 8001
                customized = self._clone_and_customize(base_chain, {"port": port_val})
                customized.description = f"Цепочка для запроса: '{intent}' (Порт {port_val})"
                return customized

        if any(w in intent_lower for w in ["диск", "ssd", "запис", "write", "i/o", "io", "спайк", "скачк"]):
            base_chain = self._builtin_chains.get("diag.storage.ssd_write_spikes")
            if base_chain:
                return base_chain

        if any(w in intent_lower for w in ["переименуй", "rename", "переименовать", "смени имя", "измени логин"]):
            import getpass
            current_user = getpass.getuser()
            match_new = re.search(r'(?:в|to)\s+["\']?([a-zA-Z0-9_\.-]+)["\']?', intent, re.IGNORECASE)
            new_name = match_new.group(1) if match_new else "NewUser"
            match_old = re.search(r'пользовател[яеей]?\s+["\']?([a-zA-Z0-9_\.-]+)["\']?\s+(?:в|to)', intent, re.IGNORECASE)
            old_name = match_old.group(1) if match_old and match_old.group(1).lower() not in ("текущего", "текущий", "current", "своего") else current_user
            return self._build_user_rename_chain(old_name=old_name, new_name=new_name, original_intent=intent)

        # 2. Динамический синтез цепочки через семантический поиск по операциям
        return self._synthesize_dynamic_chain(intent, max_steps)

    def _build_user_rename_chain(self, old_name: str, new_name: str, original_intent: str) -> ChainDefinition:
        """Формирует строгую, верифицированную цепочку переименования пользователя Windows."""
        return ChainDefinition(
            chain_id=f"admin.user.rename_{old_name}_to_{new_name}",
            title_ru=f"Переименование пользователя: '{old_name}' -> '{new_name}'",
            description=f"Безопасная цепочка переименования: идентификация прав -> проверка учетной записи {old_name} -> переименование -> верификация {new_name}.",
            category=CapabilityCategory.IDENTITY_USERS,
            initial_step_id="verify_current_session",
            requires_restore_point=True,
            steps={
                "verify_current_session": ChainStepDefinition(
                    step_id="verify_current_session",
                    tool_id="whoami.all",
                    name_ru="Проверка текущей сессии и привилегий",
                    description="Идентификация SID текущего пользователя и проверка прав администратора.",
                    arguments={},
                    risk_level=RiskLevel.READ_ONLY,
                    required_privilege=PrivilegeLevel.STANDARD,
                    execution_method=ExecutionMethod.NATIVE_API,
                    next_step_id="check_source_user",
                ),
                "check_source_user": ChainStepDefinition(
                    step_id="check_source_user",
                    tool_id="local_user.get_info",
                    name_ru=f"Проверка существования пользователя '{old_name}'",
                    description=f"Чтение атрибутов учетной записи '{old_name}' перед модификацией.",
                    arguments={"name": old_name},
                    risk_level=RiskLevel.READ_ONLY,
                    required_privilege=PrivilegeLevel.STANDARD,
                    execution_method=ExecutionMethod.POWERSHELL,
                    branch_conditions=[
                        BranchCondition(
                            operator=ConditionOperator.EXIT_CODE_ZERO,
                            target_step_id="execute_rename_user",
                        ),
                    ],
                    next_step_id="execute_rename_user",
                ),
                "execute_rename_user": ChainStepDefinition(
                    step_id="execute_rename_user",
                    tool_id="local_user.rename",
                    name_ru=f"Переименование '{old_name}' -> '{new_name}'",
                    description=f"Вызов Rename-LocalUser для изменения имени sAMAccountName.",
                    arguments={"old_name": old_name, "new_name": new_name},
                    risk_level=RiskLevel.HIGH,
                    required_privilege=PrivilegeLevel.ADMINISTRATOR,
                    execution_method=ExecutionMethod.POWERSHELL,
                    compensation=CompensationAction(
                        action_id="compensate_user_rename",
                        tool_id="local_user.rename",
                        arguments={"old_name": new_name, "new_name": old_name},
                        description=f"Откат: возврат исходного имени пользователя '{old_name}'",
                    ),
                    next_step_id="verify_new_user",
                ),
                "verify_new_user": ChainStepDefinition(
                    step_id="verify_new_user",
                    tool_id="local_user.get_info",
                    name_ru=f"Верификация обновленного пользователя '{new_name}'",
                    description=f"Подтверждение успешного переименования и доступности учетной записи '{new_name}'.",
                    arguments={"name": new_name},
                    risk_level=RiskLevel.READ_ONLY,
                    required_privilege=PrivilegeLevel.STANDARD,
                    execution_method=ExecutionMethod.POWERSHELL,
                    next_step_id=None,
                ),
            },
            metadata={"source_user": old_name, "target_user": new_name, "original_intent": original_intent},
        )

    def _clone_and_customize(self, template: ChainDefinition, override_args: Dict[str, Any]) -> ChainDefinition:
        """Создает копию шаблона с подстановкой специфических аргументов."""
        new_chain_id = f"{template.chain_id}.custom_{uuid.uuid4().hex[:6]}"
        cloned_steps: Dict[str, ChainStepDefinition] = {}

        for s_id, step in template.steps.items():
            new_args = dict(step.arguments)
            for k, v in override_args.items():
                if k in new_args or len(new_args) == 0:
                    new_args[k] = v
            cloned_steps[s_id] = ChainStepDefinition(
                step_id=step.step_id,
                tool_id=step.tool_id,
                name_ru=step.name_ru,
                description=step.description,
                arguments=new_args,
                risk_level=step.risk_level,
                required_privilege=step.required_privilege,
                execution_method=step.execution_method,
                timeout_seconds=step.timeout_seconds,
                preconditions=list(step.preconditions),
                postconditions=list(step.postconditions),
                branch_conditions=list(step.branch_conditions),
                compensation=step.compensation,
                next_step_id=step.next_step_id,
                allow_failure=step.allow_failure,
            )

        return ChainDefinition(
            chain_id=new_chain_id,
            title_ru=f"{template.title_ru} (Параметризованная)",
            description=template.description,
            category=template.category,
            initial_step_id=template.initial_step_id,
            steps=cloned_steps,
            max_execution_time_seconds=template.max_execution_time_seconds,
            requires_restore_point=template.requires_restore_point,
            metadata={"source_template": template.chain_id, "overrides": override_args},
        )

    def _synthesize_dynamic_chain(self, intent: str, max_steps: int) -> ChainDefinition:
        """Динамически формирует граф шагов на основе совпадения ключевых слов с реестром операций."""
        intent_lower = intent.lower()
        matched_ops = []

        all_ops = list(self._atomic_registry._operations.values())
        for op in all_ops:
            score = 0
            if op.utility.lower() in intent_lower:
                score += 5
            for word in op.name_ru.lower().split():
                if len(word) > 3 and word in intent_lower:
                    score += 2
            for word in op.description.lower().split():
                if len(word) > 3 and word in intent_lower:
                    score += 1
            if score > 0:
                matched_ops.append((score, op))

        matched_ops.sort(key=lambda x: x[0], reverse=True)
        selected = [op for _, op in matched_ops[:max_steps]]

        # Если совпадений нет, используем безопасный диагностический триплет по умолчанию
        if not selected:
            selected = [
                self._atomic_registry._operations.get("systeminfo.query"),
                self._atomic_registry._operations.get("tasklist.list"),
                self._atomic_registry._operations.get("wevtutil.system.errors"),
            ]
            selected = [op for op in selected if op is not None]

        steps_dict: Dict[str, ChainStepDefinition] = {}
        for idx, op in enumerate(selected):
            s_id = f"step_{idx + 1}_{op.id.replace('.', '_')}"
            next_id = f"step_{idx + 2}_{selected[idx + 1].id.replace('.', '_')}" if idx + 1 < len(selected) else None

            steps_dict[s_id] = ChainStepDefinition(
                step_id=s_id,
                tool_id=op.id,
                name_ru=op.name_ru,
                description=op.description,
                arguments={},
                risk_level=op.risk_level,
                required_privilege=op.required_privilege,
                execution_method=op.execution_method,
                next_step_id=next_id,
            )

        initial_id = list(steps_dict.keys())[0] if steps_dict else "step_empty"
        chain_id = f"synthesized.chain_{uuid.uuid4().hex[:8]}"

        return ChainDefinition(
            chain_id=chain_id,
            title_ru=f"Цепочка расследования: {intent[:40]}...",
            description=f"Динамически сформированная цепочка проверок для: '{intent}'",
            category=CapabilityCategory.PERFORMANCE_TRACING,
            initial_step_id=initial_id,
            steps=steps_dict,
            requires_restore_point=any(s.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL) for s in steps_dict.values()),
            metadata={"user_intent": intent, "dynamic": True},
        )

