# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows SDK - Tool Chains Engine
# =============================================================================
# Description:
#   Исполнительный движок пошагового запуска цепочек инструментов агентом.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.core.tool_chains.engine import ToolChainExecutionEngine
#     engine = ToolChainExecutionEngine()
#     report = await engine.execute_chain(chain_def, user_intent="Тест")
#
# File: engine.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.core.tool_chains
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 17:35:00
# =============================================================================

from __future__ import annotations

"""Движок выполнения цепочек инструментов с защитой SafeOps, динамическим ветвлением и компенсацией."""

import asyncio
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from logger import logger

from apps.windows.contracts.enums import RiskLevel
from apps.windows.sdk.core.atomic_capabilities import WindowsAtomicCapabilitiesRegistry
from apps.windows.sdk.core.atomic_models import AtomicOperationExecutionRequest
from apps.windows.sdk.core.safe_executor import SafeExecutor
from apps.windows.sdk.core.system_restore import WindowsSystemRestoreManager
from apps.windows.sdk.core.tool_chains.models import (
    BranchCondition,
    ChainDefinition,
    ChainRunReport,
    ChainRunStatus,
    ChainStepDefinition,
    ConditionOperator,
    StepExecutionResult,
    StepRunStatus,
)
from apps.windows.sdk.core.tool_chains.storage import ToolChainStorage


class ToolChainExecutionEngine:
    """Оркестратор исполнения цепочек инструментов агентом Windows."""

    def __init__(
        self,
        storage: Optional[ToolChainStorage] = None,
        safe_executor: Optional[SafeExecutor] = None,
        restore_manager: Optional[WindowsSystemRestoreManager] = None,
    ) -> None:
        """Инициализация исполнительного движка цепочек."""
        self._storage = storage or ToolChainStorage()
        self._executor = safe_executor or SafeExecutor()
        self._restore_mgr = restore_manager or WindowsSystemRestoreManager()
        self._atomic_registry = WindowsAtomicCapabilitiesRegistry.get_instance()

    async def execute_chain(
        self,
        chain: ChainDefinition,
        user_intent: str = "",
        dry_run: bool = False,
        create_restore_point: bool = False,
        custom_arguments: Optional[Dict[str, Any]] = None,
    ) -> ChainRunReport:
        """Выполняет полную цепочку инструментов с динамическим ветвлением и протоколированием.

        Args:
            chain: Определение цепочки инструментов.
            user_intent: Исходный запрос пользователя на естественном языке.
            dry_run: Флаг режима симуляции без реального внесения изменений.
            create_restore_point: Принудительное создание точки отката VSS перед стартом.
            custom_arguments: Пользовательские переопределения аргументов шагов.

        Returns:
            ChainRunReport: Итоговый отчёт о выполнении цепочки со всеми доказательствами.
        """
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        start_time_iso = datetime.now().isoformat()
        start_mono = time.monotonic()

        report = ChainRunReport(
            run_id=run_id,
            chain_id=chain.chain_id,
            status=ChainRunStatus.RUNNING,
            user_intent=user_intent or chain.title_ru,
            start_time=start_time_iso,
        )

        # 1. Проверка необходимости создания точки восстановления
        if (chain.requires_restore_point or create_restore_point) and not dry_run:
            try:
                res_point = self._restore_mgr.create_restore_point(
                    description=f"ai-tc ToolChain AutoCheckpoint: {chain.chain_id}"
                )
                if res_point and res_point.get("success"):
                    report.restore_point_created = True
                    report.restore_point_id = str(res_point.get("sequence_number", "VSS_AUTO"))
                    logger.info(f"Создана точка отката {report.restore_point_id} для цепочки {chain.chain_id}")
            except Exception as e:
                logger.warning(f"Не удалось создать точку отката перед запуском цепочки: {e}")

        # 2. Инициализация выполнения шагов
        current_step_id: Optional[str] = chain.initial_step_id
        visited_steps = 0
        max_steps = max(len(chain.steps) * 2, 20)

        # Сохраняем начальное состояние
        self._storage.save_run(report)

        try:
            while current_step_id and visited_steps < max_steps:
                visited_steps += 1
                step_def = chain.steps.get(current_step_id)
                if not step_def:
                    logger.error(f"Шаг {current_step_id} не найден в определении цепочки {chain.chain_id}")
                    break

                # Применение переопределений аргументов
                merged_args = dict(step_def.arguments)
                if custom_arguments:
                    merged_args.update(custom_arguments)

                step_result = await self._execute_step(step_def, merged_args, dry_run)
                report.steps_executed.append(step_result)

                # Обработка сбоя шага
                if step_result.status == StepRunStatus.FAILED and not step_def.allow_failure:
                    logger.warning(f"Шаг {current_step_id} завершился с ошибкой: {step_result.error_message}")
                    if step_def.compensation and not dry_run:
                        logger.info(f"Выполнение компенсации для шага {current_step_id}: {step_def.compensation.description}")
                        comp_res = await self._execute_compensation(step_def.compensation)
                        if comp_res:
                            report.rolled_back = True
                    report.status = ChainRunStatus.FAILED
                    break

                # Вычисление следующего шага на основе условий перехода
                next_step = self._evaluate_branching(step_def, step_result)
                step_result.next_step_decided = next_step
                current_step_id = next_step

            if report.status == ChainRunStatus.RUNNING:
                report.status = ChainRunStatus.COMPLETED

        except Exception as e:
            logger.error(f"Критическая ошибка исполнения цепочки {chain.chain_id}: {e}")
            report.status = ChainRunStatus.FAILED
            report.findings_summary.append(f"Исключение при исполнении: {str(e)}")

        finally:
            report.end_time = datetime.now().isoformat()
            report.total_duration_ms = (time.monotonic() - start_mono) * 1000.0
            self._compile_summary(report)
            self._storage.save_run(report)

        return report

    async def _execute_step(
        self,
        step: ChainStepDefinition,
        arguments: Dict[str, Any],
        dry_run: bool,
    ) -> StepExecutionResult:
        """Выполняет один шаг цепочки инструментов."""
        step_start_iso = datetime.now().isoformat()
        step_start_mono = time.monotonic()

        # Попытка вызова через реестр атомарных операций
        op = self._atomic_registry.get_operation(step.tool_id)
        if op:
            req = AtomicOperationExecutionRequest(
                operation_id=op.id,
                parameters=arguments,
                dry_run=dry_run,
            )
            exec_res = await self._atomic_registry.execute_operation(req)
            duration_ms = (time.monotonic() - step_start_mono) * 1000.0

            is_success = (
                exec_res.status.lower() in ("success", "simulated", "completed", "dry_run_simulated")
                or "simulat" in exec_res.status.lower()
            ) and exec_res.exit_code == 0
            status = StepRunStatus.SUCCESS if is_success else StepRunStatus.FAILED
            err_msg = exec_res.error or (exec_res.message if not is_success else None)

            return StepExecutionResult(
                step_id=step.step_id,
                tool_id=step.tool_id,
                status=status,
                start_time=step_start_iso,
                end_time=datetime.now().isoformat(),
                duration_ms=duration_ms,
                exit_code=exec_res.exit_code,
                stdout=exec_res.stdout,
                stderr=exec_res.stderr or (exec_res.error or ""),
                structured_data=exec_res.model_dump() if hasattr(exec_res, "model_dump") else {},
                error_message=err_msg,
                evidence_collected={"operation_title": op.name_ru, "simulated_changes": exec_res.simulated_changes},
            )

        # Фолбэк на прямой запуск команды через subprocess
        cmd_str = f"{step.tool_id} " + " ".join(f"-{k} {v}" for k, v in arguments.items())
        if dry_run:
            duration_ms = (time.monotonic() - step_start_mono) * 1000.0
            return StepExecutionResult(
                step_id=step.step_id,
                tool_id=step.tool_id,
                status=StepRunStatus.SUCCESS,
                start_time=step_start_iso,
                end_time=datetime.now().isoformat(),
                duration_ms=duration_ms,
                exit_code=0,
                stdout=f"[Dry-Run Simulation] {cmd_str}",
                stderr="",
                structured_data={"simulated": True, "command": cmd_str},
                evidence_collected={"command": cmd_str, "mode": "dry_run"},
            )

        try:
            proc = await asyncio.create_subprocess_shell(
                cmd_str,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=step.timeout_seconds)
            stdout_str = stdout_bytes.decode(errors="replace")
            stderr_str = stderr_bytes.decode(errors="replace")
            duration_ms = (time.monotonic() - step_start_mono) * 1000.0

            status = StepRunStatus.SUCCESS if proc.returncode == 0 else StepRunStatus.FAILED
            return StepExecutionResult(
                step_id=step.step_id,
                tool_id=step.tool_id,
                status=status,
                start_time=step_start_iso,
                end_time=datetime.now().isoformat(),
                duration_ms=duration_ms,
                exit_code=proc.returncode or 0,
                stdout=stdout_str,
                stderr=stderr_str,
                structured_data={"command": cmd_str, "returncode": proc.returncode},
                evidence_collected={"command": cmd_str},
            )
        except Exception as e:
            duration_ms = (time.monotonic() - step_start_mono) * 1000.0
            return StepExecutionResult(
                step_id=step.step_id,
                tool_id=step.tool_id,
                status=StepRunStatus.FAILED,
                start_time=step_start_iso,
                end_time=datetime.now().isoformat(),
                duration_ms=duration_ms,
                exit_code=1,
                stdout="",
                stderr=str(e),
                error_message=str(e),
                evidence_collected={"command": cmd_str},
            )

    async def _execute_compensation(self, compensation: Any) -> bool:
        """Выполняет компенсирующее действие при откате."""
        try:
            req = AtomicOperationExecutionRequest(
                operation_id=compensation.tool_id,
                parameters=compensation.arguments,
                dry_run=False,
            )
            res = await self._atomic_registry.execute_operation(req)
            return res.status in ("success", "simulated", "completed") and res.exit_code == 0
        except Exception as e:
            logger.error(f"Ошибка компенсации {compensation.action_id}: {e}")
            return False

    def _evaluate_branching(
        self,
        step: ChainStepDefinition,
        result: StepExecutionResult,
    ) -> Optional[str]:
        """Оценивает условия динамического ветвления шага."""
        if not step.branch_conditions:
            return step.next_step_id

        for cond in step.branch_conditions:
            if self._check_condition(cond, result):
                return cond.target_step_id

        return step.next_step_id

    def _check_condition(self, cond: BranchCondition, result: StepExecutionResult) -> bool:
        """Проверяет соответствие условия фактическому результату шага."""
        if cond.operator == ConditionOperator.ALWAYS_TRUE:
            return True

        if cond.operator == ConditionOperator.EXIT_CODE_ZERO:
            return result.exit_code == 0

        val: Any = None
        if cond.field_path == "stdout":
            val = result.stdout
        elif cond.field_path == "exit_code":
            val = result.exit_code
        elif cond.field_path.startswith("data."):
            key = cond.field_path.split(".", 1)[1]
            val = result.structured_data.get(key)
        else:
            val = result.structured_data.get(cond.field_path)

        if cond.operator == ConditionOperator.IS_EMPTY:
            return not bool(val)
        if cond.operator == ConditionOperator.IS_NOT_EMPTY:
            return bool(val)
        if cond.operator == ConditionOperator.EQUALS:
            return str(val).strip() == str(cond.expected_value).strip()
        if cond.operator == ConditionOperator.NOT_EQUALS:
            return str(val).strip() != str(cond.expected_value).strip()
        if cond.operator == ConditionOperator.CONTAINS:
            return str(cond.expected_value).lower() in str(val).lower()
        if cond.operator == ConditionOperator.NOT_CONTAINS:
            return str(cond.expected_value).lower() not in str(val).lower()

        return False

    def _compile_summary(self, report: ChainRunReport) -> None:
        """Формирует итоговые выводы и рекомендации на основе собранных фактов."""
        success_count = sum(1 for s in report.steps_executed if s.status == StepRunStatus.SUCCESS)
        total = len(report.steps_executed)

        report.findings_summary.append(
            f"Выполнено шагов: {success_count}/{total} (Общее время: {report.total_duration_ms:.1f} мс)"
        )

        for s in report.steps_executed:
            if s.status == StepRunStatus.SUCCESS and s.stdout:
                snippet = s.stdout.strip()[:80].replace("\n", " ")
                report.findings_summary.append(f"[{s.step_id}] Получены данные: {snippet}...")
            elif s.status == StepRunStatus.FAILED:
                report.findings_summary.append(f"[{s.step_id}] Сбой выполнения: {s.error_message or 'Ненулевой код возврата'}")
                report.root_cause_identified = f"Ошибка на шаге {s.step_id} ({s.tool_id}): {s.error_message}"

