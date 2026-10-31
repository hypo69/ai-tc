# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Центральный конвейер выполнения команд (Execution Engine)
# =============================================================================
# Description:
#   Оркестрация полного жизненного цикла каждого MCP-запроса согласно
#   диаграмме Раздела 5 ТЗ:
#   Validate Parameters -> Resolve Command Registry -> Check Host Permissions ->
#   Check Privilege Level -> Operation Risk / Approval -> Execute (с контролем
#   семафора параллелизма и авто-реконнектом) -> Collect Result -> Audit Log ->
#   Return MCP Response.
#
#   Зачем нужен этот модуль:
#     1. Гарантия того, что все 10 функциональных модулей проходят единый
#        защитный контур безопасности и журналирования.
#     2. Ограничение максимального параллелизма (`max_parallel_commands`).
#
# Usage Examples:
#   Python API:
#     from ssh_mcp.core.execution_engine import ExecutionEngine
#     resp = await engine.dispatch("srv-01", "system.memory", {}, handler_fn)
#
# File: execution_engine.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:51:00
# =============================================================================

import asyncio
import time
from typing import Any, Awaitable, Callable, Dict, Optional

from ..security.audit import AuditLogger
from ..security.authorization import AuthorizationError
from ..security.host_verification import HostVerificationError
from ..storage.repositories.command_runs_repo import CommandRunsRepository
from ..transports.base import BaseTransport, RawExecutionResult
from .approval_manager import ApprovalManager, ApprovalRequiredException
from .command_registry import CommandRegistry, CommandValidationError
from .connection_manager import ConnectionManager
from .permission_manager import PermissionManager
from .result_normalizer import ResultNormalizer


class ExecutionEngine:
    """Центральный конвейер контроля, выполнения и аудита операций SSH MCP Server.

    Attributes:
        registry (CommandRegistry): Реестр команд.
        connection_manager (ConnectionManager): Менеджер пула подключений.
        permission_manager (PermissionManager): Менеджер прав доступа.
        approval_manager (ApprovalManager): Менеджер подтверждений опасных операций.
        audit_logger (AuditLogger): Служба журнала аудита.
        normalizer (ResultNormalizer): Формирователь стандартного ответа MCP.
        runs_repo (CommandRunsRepository): Репозиторий истории запусков команд.

    Examples:
        >>> pass
    """

    def __init__(
        self,
        registry: CommandRegistry,
        connection_manager: ConnectionManager,
        permission_manager: PermissionManager,
        approval_manager: ApprovalManager,
        audit_logger: AuditLogger,
        normalizer: ResultNormalizer,
        runs_repo: CommandRunsRepository,
        max_parallel_commands: int = 10,
    ) -> None:
        """Инициализация конвейера выполнения.

        Args:
            registry (CommandRegistry): Реестр команд.
            connection_manager (ConnectionManager): Менеджер подключений.
            permission_manager (PermissionManager): Менеджер разрешений.
            approval_manager (ApprovalManager): Менеджер подтверждений.
            audit_logger (AuditLogger): Служба аудита.
            normalizer (ResultNormalizer): Нормализатор ответов.
            runs_repo (CommandRunsRepository): Репозиторий таблицы `command_runs`.
            max_parallel_commands (int): Лимит одновременных операций.

        Examples:
            >>> pass
        """
        self.registry = registry
        self.connection_manager = connection_manager
        self.permission_manager = permission_manager
        self.approval_manager = approval_manager
        self.audit_logger = audit_logger
        self.normalizer = normalizer
        self.runs_repo = runs_repo
        self._semaphore = asyncio.Semaphore(max(1, max_parallel_commands))

    async def dispatch(
        self,
        host_id: str,
        command_id: str,
        parameters: Optional[Dict[str, Any]] = {},
        handler: Optional[Callable[[BaseTransport, str, Dict[str, Any]], Awaitable[Dict[str, Any]]]] = False,  # type: ignore[assignment]
        approval_id: str = "",
        actor: str = "ai-agent",
    ) -> Dict[str, Any]:
        """Выполнение операции через полный жизненный цикл безопасности и аудита.

        Args:
            host_id (str): Идентификатор целевого узла.
            command_id (str): Идентификатор команды в Command Registry.
            parameters (Optional[Dict[str, Any]]): Входные аргументы вызова.
                                                   Значение по умолчанию: {}.
            handler (Optional[Callable]): Асинхронная функция адаптера платформы.
            approval_id (str): Идентификатор подтверждения (для high/critical операций).
            actor (str): Инициатор операции.

        Returns:
            Dict[str, Any]: Стандартизированный словарь ответа MCP.

        Examples:
            >>> pass
        """
        started = time.perf_counter()
        raw_params = dict(parameters) if parameters else {}
        platform_name = "windows"

        try:
            host_cfg = self.connection_manager.get_host_config(host_id)
            platform_name = host_cfg.platform
        except KeyError as exc:
            self.audit_logger.log_event(host_id, command_id, "low", "denied", {"error": str(exc)}, actor)
            return self.normalizer.failure(host_id, platform_name, command_id, "HOST_NOT_FOUND", str(exc))
        except PermissionError as exc:
            self.audit_logger.log_event(host_id, command_id, "low", "denied", {"error": str(exc)}, actor)
            return self.normalizer.failure(host_id, platform_name, command_id, "HOST_DISABLED", str(exc))

        # 1. Разрешение команды и валидация параметров в Command Registry
        try:
            cmd_def = self.registry.resolve(command_id)
            validated_params = self.registry.validate_parameters(command_id, raw_params)
        except CommandValidationError as exc:
            self.audit_logger.log_event(host_id, command_id, "low", "denied", {"params": raw_params, "error": str(exc)}, actor)
            return self.normalizer.failure(
                host_id, platform_name, command_id, "COMMAND_VALIDATION_ERROR", str(exc)
            )

        # 2. Проверка прав хоста и уровня привилегий
        try:
            self.permission_manager.check_access(host_id, cmd_def)
        except AuthorizationError as exc:
            self.audit_logger.log_event(
                host_id, command_id, cmd_def.risk_level, "denied", {"params": validated_params, "error": str(exc)}, actor
            )
            return self.normalizer.failure(
                host_id, platform_name, command_id, "ACCESS_DENIED", str(exc)
            )

        # 3. Оценка риска и проверка подтверждения (Approval Manager)
        effective_approval_id = approval_id or str(raw_params.get("approval_id", ""))
        try:
            self.approval_manager.verify_or_request(
                host_id=host_id,
                command=cmd_def,
                parameters=validated_params,
                approval_id=effective_approval_id,
                actor=actor,
            )
        except ApprovalRequiredException as exc:
            self.audit_logger.log_event(
                host_id,
                command_id,
                cmd_def.risk_level,
                "approval_required",
                {"approval_id": exc.approval_id, "params": validated_params},
                actor,
            )
            return self.normalizer.failure(
                host=host_id,
                platform=platform_name,
                operation=command_id,
                code="APPROVAL_REQUIRED",
                message=str(exc),
                extra_error={"approval_id": exc.approval_id, "risk_level": exc.risk_level},
            )

        # 4. Выполнение операции с ограничением параллелизма и поддержкой авто-реконнекта
        async with self._semaphore:
            try:
                transport = await self.connection_manager.get_transport(host_id)
                result_payload = await self._execute_with_recovery(
                    host_id=host_id,
                    transport=transport,
                    platform_name=platform_name,
                    validated_params=validated_params,
                    handler=handler,
                )
            except HostVerificationError as exc:
                elapsed = int((time.perf_counter() - started) * 1000)
                self.audit_logger.log_event(host_id, command_id, cmd_def.risk_level, "denied", {"error": str(exc)}, actor)
                return self.normalizer.failure(
                    host_id, platform_name, command_id, "HOST_KEY_VERIFICATION_FAILED", str(exc), duration_ms=elapsed
                )
            except AuthorizationError as exc:
                elapsed = int((time.perf_counter() - started) * 1000)
                self.audit_logger.log_event(host_id, command_id, cmd_def.risk_level, "denied", {"error": str(exc)}, actor)
                return self.normalizer.failure(
                    host_id, platform_name, command_id, "ACCESS_DENIED", str(exc), duration_ms=elapsed
                )
            except TimeoutError as exc:
                elapsed = int((time.perf_counter() - started) * 1000)
                self.runs_repo.record_run(host_id, command_id, validated_params, 124, elapsed, "", str(exc), False)
                self.audit_logger.log_event(host_id, command_id, cmd_def.risk_level, "failed", {"error": str(exc)}, actor)
                return self.normalizer.failure(
                    host_id, platform_name, command_id, "EXECUTION_TIMEOUT", str(exc), duration_ms=elapsed, exit_code=124
                )
            except ConnectionError as exc:
                elapsed = int((time.perf_counter() - started) * 1000)
                self.runs_repo.record_run(host_id, command_id, validated_params, 255, elapsed, "", str(exc), False)
                self.audit_logger.log_event(host_id, command_id, cmd_def.risk_level, "failed", {"error": str(exc)}, actor)
                return self.normalizer.failure(
                    host_id, platform_name, command_id, "CONNECTION_ERROR", str(exc), duration_ms=elapsed, exit_code=255
                )
            except Exception as exc:
                elapsed = int((time.perf_counter() - started) * 1000)
                self.runs_repo.record_run(host_id, command_id, validated_params, 1, elapsed, "", str(exc), False)
                self.audit_logger.log_event(host_id, command_id, cmd_def.risk_level, "failed", {"error": str(exc)}, actor)
                return self.normalizer.failure(
                    host_id, platform_name, command_id, "EXECUTION_FAILED", str(exc), duration_ms=elapsed
                )

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        exit_code = int(result_payload.pop("_exit_code", 0))
        stdout_str = str(result_payload.pop("_stdout", ""))
        stderr_str = str(result_payload.pop("_stderr", ""))
        duration_val = int(result_payload.pop("_duration_ms", elapsed_ms))

        safe_params = self.audit_logger.redactor.redact_dict(validated_params)
        self.runs_repo.record_run(
            host_id=host_id,
            command_id=command_id,
            parameters=safe_params,
            exit_code=exit_code,
            duration_ms=duration_val,
            stdout=self.audit_logger.redactor.redact_text(stdout_str),
            stderr=self.audit_logger.redactor.redact_text(stderr_str),
            success=(exit_code == 0),
        )

        if cmd_def.audit:
            self.audit_logger.log_event(
                host_id=host_id,
                operation=command_id,
                risk_level=cmd_def.risk_level,
                status="success" if exit_code == 0 else "failed",
                details={"params": safe_params, "exit_code": exit_code},
                actor=actor,
            )

        if exit_code != 0:
            return self.normalizer.failure(
                host=host_id,
                platform=platform_name,
                operation=command_id,
                code="NON_ZERO_EXIT_CODE",
                message=stderr_str or f"Команда завершилась с кодом {exit_code}",
                duration_ms=duration_val,
                exit_code=exit_code,
                stdout=stdout_str,
                stderr=stderr_str,
            )

        return self.normalizer.success(
            host=host_id,
            platform=platform_name,
            operation=command_id,
            data=result_payload,
            duration_ms=duration_val,
            exit_code=exit_code,
            stdout=stdout_str,
            stderr=stderr_str,
        )

    async def _execute_with_recovery(
        self,
        host_id: str,
        transport: BaseTransport,
        platform_name: str,
        validated_params: Dict[str, Any],
        handler: Optional[Callable[[BaseTransport, str, Dict[str, Any]], Awaitable[Dict[str, Any]]]],
    ) -> Dict[str, Any]:
        """Выполнение обработчика с автоматическим восстановлением соединения при обрыве.

        Args:
            host_id (str): Идентификатор узла.
            transport (BaseTransport): Текущий транспорт.
            platform_name (str): Платформа узла.
            validated_params (Dict[str, Any]): Проверенные параметры.
            handler (Optional[Callable]): Обработчик операции.

        Returns:
            Dict[str, Any]: Словарь данных результата.

        Examples:
            >>> pass
        """
        if not handler:
            raw_res: RawExecutionResult = await transport.execute_command(
                command=str(validated_params.get("command", "")),
                args=list(validated_params.get("args", [])),
                env=dict(validated_params.get("env", {})),
                shell=str(validated_params.get("shell", "default")),
                timeout=int(validated_params.get("timeout", 60)),
                elevate=bool(validated_params.get("elevate", False)),
            )
            return {
                "output": raw_res.stdout,
                "_exit_code": raw_res.exit_code,
                "_stdout": raw_res.stdout,
                "_stderr": raw_res.stderr,
                "_duration_ms": raw_res.duration_ms,
            }

        try:
            return await handler(transport, platform_name, validated_params)
        except ConnectionError:
            await self.connection_manager.reconnect(host_id)
            recovered_transport = await self.connection_manager.get_transport(host_id)
            return await handler(recovered_transport, platform_name, validated_params)
