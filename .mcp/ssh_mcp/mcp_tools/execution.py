# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: MCP-инструменты выполнения команд (Command Execution)
# =============================================================================
# Description:
#   Реализация группы инструментов 4.2 ТЗ:
#   ssh_execute, ssh_execute_script, ssh_execute_batch, ssh_execute_async,
#   ssh_task_status, ssh_task_cancel с раздельной передачей аргументов.
#
# File: execution.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.mcp_tools
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:58:15
# =============================================================================

from typing import Any, Dict, List, Optional
from mcp.server import MCPServer
from ..bootstrap import SSHMCPRuntime
from ..platforms.base import pack_raw_result
from ..transports.base import BaseTransport


class ExecutionToolsModule:
    """Модуль выполнения команд, скриптов, пакетов и фоновых задач (Раздел 4.2 ТЗ).

    Attributes:
        rt (SSHMCPRuntime): Контейнер сервисов ядра.

    Examples:
        >>> from ssh_mcp.bootstrap import create_runtime
        >>> mod = ExecutionToolsModule(create_runtime(db_path=":memory:"))
    """

    def __init__(self, runtime: SSHMCPRuntime) -> None:
        """Инициализация модуля выполнения команд."""
        self.rt = runtime

    async def ssh_execute(
        self,
        host_id: str,
        command: str,
        args: Optional[List[str]] = [],
        shell: str = "default",
        timeout: int = 60,
        approval_id: str = "",
    ) -> Dict[str, Any]:
        """Безопасное выполнение команды с передачей параметров отдельно от кода."""
        safe_args = list(args) if args else []

        async def _handler(tr: BaseTransport, _plat: str, params: Dict[str, Any]) -> Dict[str, Any]:
            raw = await tr.execute_command(
                command=str(params["command"]),
                args=list(params.get("args", [])),
                shell=str(params.get("shell", "default")),
                timeout=int(params.get("timeout", 60)),
            )
            return pack_raw_result(raw, {"output": raw.stdout, "stderr": raw.stderr})

        return await self.rt.engine.dispatch(
            host_id=host_id,
            command_id="ssh.execute",
            parameters={"command": command, "args": safe_args, "shell": shell, "timeout": timeout},
            handler=_handler,
            approval_id=approval_id,
        )

    async def ssh_execute_script(
        self,
        host_id: str,
        script: str,
        args: Optional[List[str]] = [],
        shell: str = "default",
        timeout: int = 120,
        approval_id: str = "",
    ) -> Dict[str, Any]:
        """Выполнение многострочного скрипта (требует подтверждения high-risk)."""
        safe_args = list(args) if args else []

        async def _handler(tr: BaseTransport, _plat: str, params: Dict[str, Any]) -> Dict[str, Any]:
            raw = await tr.execute_command(
                command=str(params["script"]),
                args=list(params.get("args", [])),
                shell=str(params.get("shell", "default")),
                timeout=int(params.get("timeout", 120)),
                elevate=True,
            )
            return pack_raw_result(raw, {"output": raw.stdout, "stderr": raw.stderr})

        return await self.rt.engine.dispatch(
            host_id=host_id,
            command_id="ssh.execute_script",
            parameters={"script": script, "args": safe_args, "shell": shell, "timeout": timeout},
            handler=_handler,
            approval_id=approval_id,
        )

    async def ssh_execute_batch(
        self,
        host_id: str,
        commands: List[str],
        shell: str = "default",
        timeout: int = 60,
    ) -> Dict[str, Any]:
        """Пакетное последовательное выполнение списка команд."""
        async def _handler(tr: BaseTransport, _plat: str, params: Dict[str, Any]) -> Dict[str, Any]:
            results: List[Dict[str, Any]] = []
            for cmd_item in params["commands"]:
                raw = await tr.execute_command(command=str(cmd_item), shell=shell, timeout=timeout)
                results.append(
                    {
                        "command": str(cmd_item),
                        "exit_code": raw.exit_code,
                        "stdout": raw.stdout,
                        "stderr": raw.stderr,
                    }
                )
            return {"batch_results": results, "count": len(results)}

        return await self.rt.engine.dispatch(
            host_id=host_id,
            command_id="ssh.execute_batch",
            parameters={"commands": commands, "shell": shell, "timeout": timeout},
            handler=_handler,
        )

    async def ssh_execute_async(
        self,
        host_id: str,
        command: str,
        args: Optional[List[str]] = [],
        shell: str = "default",
        timeout: int = 300,
    ) -> Dict[str, Any]:
        """Запуск длительной задачи в фоновом режиме через TaskManager."""
        safe_args = list(args) if args else []

        async def _bg_job() -> Dict[str, Any]:
            return await self.ssh_execute(
                host_id=host_id, command=command, args=safe_args, shell=shell, timeout=timeout
            )

        record = await self.rt.task_manager.submit(host_id, "ssh.execute_async", _bg_job())
        self.rt.audit_logger.log_event(
            host_id, "ssh.execute_async", "medium", "success", {"task_id": record.task_id, "command": command}
        )
        return self.rt.normalizer.success(
            host=host_id,
            platform="windows",
            operation="ssh.execute_async",
            data=record.model_dump(),
        )

    async def ssh_task_status(self, task_id: str) -> Dict[str, Any]:
        """Проверка состояния асинхронной задачи по task_id."""
        status_dict = self.rt.task_manager.get_status(task_id)
        if not status_dict:
            return self.rt.normalizer.failure(
                "localhost", "windows", "ssh.task_status", "TASK_NOT_FOUND", f"Задача '{task_id}' не найдена"
            )
        return self.rt.normalizer.success(
            host=str(status_dict.get("host_id", "localhost")),
            platform="windows",
            operation="ssh.task_status",
            data=status_dict,
        )

    async def ssh_task_cancel(self, task_id: str) -> Dict[str, Any]:
        """Отмена выполняющейся длительной задачи."""
        try:
            cancelled = await self.rt.task_manager.cancel(task_id)
            host_id = str(cancelled.get("host_id", "localhost"))
            self.rt.audit_logger.log_event(host_id, "ssh.task_cancel", "medium", "success", {"task_id": task_id})
            return self.rt.normalizer.success(
                host=host_id,
                platform="windows",
                operation="ssh.task_cancel",
                data=cancelled,
            )
        except KeyError as exc:
            return self.rt.normalizer.failure(
                "localhost", "windows", "ssh.task_cancel", "TASK_NOT_FOUND", str(exc)
            )


def register_execution_tools(mcp: MCPServer, runtime: SSHMCPRuntime) -> ExecutionToolsModule:
    """Регистрация 6 инструментов выполнения команд в MCPServer."""
    mod = ExecutionToolsModule(runtime)

    @mcp.tool(name="ssh_execute", description="Выполнение команды с раздельной передачей параметров")
    async def ssh_execute(
        host_id: str,
        command: str,
        args: List[str] = [],
        shell: str = "default",
        timeout: int = 60,
        approval_id: str = "",
    ) -> Dict[str, Any]:
        return await mod.ssh_execute(host_id, command, args, shell, timeout, approval_id)

    @mcp.tool(name="ssh_execute_script", description="Выполнение административного скрипта (требует подтверждения)")
    async def ssh_execute_script(
        host_id: str,
        script: str,
        args: List[str] = [],
        shell: str = "default",
        timeout: int = 120,
        approval_id: str = "",
    ) -> Dict[str, Any]:
        return await mod.ssh_execute_script(host_id, script, args, shell, timeout, approval_id)

    @mcp.tool(name="ssh_execute_batch", description="Пакетное выполнение списка команд")
    async def ssh_execute_batch(
        host_id: str, commands: List[str], shell: str = "default", timeout: int = 60
    ) -> Dict[str, Any]:
        return await mod.ssh_execute_batch(host_id, commands, shell, timeout)

    @mcp.tool(name="ssh_execute_async", description="Запуск длительной задачи в фоновом режиме")
    async def ssh_execute_async(
        host_id: str, command: str, args: List[str] = [], shell: str = "default", timeout: int = 300
    ) -> Dict[str, Any]:
        return await mod.ssh_execute_async(host_id, command, args, shell, timeout)

    @mcp.tool(name="ssh_task_status", description="Получение состояния фоновой задачи")
    async def ssh_task_status(task_id: str) -> Dict[str, Any]:
        return await mod.ssh_task_status(task_id)

    @mcp.tool(name="ssh_task_cancel", description="Отмена длительной задачи")
    async def ssh_task_cancel(task_id: str) -> Dict[str, Any]:
        return await mod.ssh_task_cancel(task_id)

    return mod
