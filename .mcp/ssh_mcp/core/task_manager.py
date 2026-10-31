# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Менеджер асинхронных длительных задач (Task Manager)
# =============================================================================
# Description:
#   Запуск, отслеживание статуса и принудительная отмена фоновых административных
#   задач (`ssh_execute_async`, `ssh_task_status`, `ssh_task_cancel`) с
#   синхронизацией состояния в таблице `tasks` (Раздел 4.2 ТЗ).
#
# Usage Examples:
#   Python API:
#     from ssh_mcp.core.task_manager import TaskManager
#     tm = TaskManager(tasks_repo)
#     task_id = await tm.submit_task("srv-01", "ssh.execute_async", coro)
#
# File: task_manager.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 17:10:00
# =============================================================================

import asyncio
from datetime import datetime, timezone
from typing import Any, Coroutine, Dict
import uuid

from ..schemas.execution import TaskRecord
from ..storage.repositories.tasks_repo import TasksRepository


class TaskManager:
    """Диспетчер длительных асинхронных задач SSH MCP Server.

    Attributes:
        repo (TasksRepository): Репозиторий таблицы `tasks`.

    Examples:
        >>> from ssh_mcp.storage.database import DatabaseManager
        >>> db = DatabaseManager(":memory:")
        >>> _ = db.initialize()
        >>> tm = TaskManager(TasksRepository(db))
        >>> tm.get_status("unknown")
        {}
    """

    def __init__(self, repo: TasksRepository) -> None:
        """Инициализация менеджера фоновых задач.

        Args:
            repo (TasksRepository): Репозиторий таблицы `tasks`.

        Examples:
            >>> db = DatabaseManager(":memory:")
            >>> _ = db.initialize()
            >>> tm = TaskManager(TasksRepository(db))
        """
        self.repo = repo
        self._running_tasks: Dict[str, asyncio.Task[Any]] = {}
        self._records: Dict[str, TaskRecord] = {}

    async def submit(
        self,
        host_id: str,
        command_id: str,
        coro: Coroutine[Any, Any, Dict[str, Any]],
    ) -> TaskRecord:
        """Регистрация и запуск фоновой асинхронной задачи.

        Args:
            host_id (str): Идентификатор целевого узла.
            command_id (str): Идентификатор команды.
            coro (Coroutine[Any, Any, Dict[str, Any]]): Корутина выполнения операции.

        Returns:
            TaskRecord: Запись запущенной задачи.

        Examples:
            >>> import asyncio
            >>> db = DatabaseManager(":memory:")
            >>> _ = db.initialize()
            >>> tm = TaskManager(TasksRepository(db))
            >>> async def sample(): return {"ok": True}
            >>> rec = asyncio.run(tm.submit("h1", "ssh.execute_async", sample()))
            >>> rec.task_id.startswith("tsk-")
            True
        """
        task_id = f"tsk-{uuid.uuid4().hex[:10]}"
        record = TaskRecord(
            task_id=task_id,
            host_id=host_id,
            command_id=command_id,
            status="running",
        )
        self._records[task_id] = record
        self.repo.save_task(record)

        async def _runner() -> None:
            try:
                res = await coro
                record.status = "completed"
                record.result = res if isinstance(res, dict) else {"output": str(res)}
            except asyncio.CancelledError:
                coro.close()
                record.status = "cancelled"
                record.result = {"cancelled": True}
            except Exception as exc:
                record.status = "failed"
                record.result = {"error": str(exc)}
            finally:
                record.completed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                self.repo.save_task(record)

        bg_task = asyncio.create_task(_runner())
        self._running_tasks[task_id] = bg_task
        await asyncio.sleep(0)
        return record

    def get_status(self, task_id: str) -> Dict[str, Any]:
        """Получение текущего состояния задачи.

        Args:
            task_id (str): Идентификатор задачи.

        Returns:
            Dict[str, Any]: Словарь метаданных и результата задачи или {}.

        Examples:
            >>> db = DatabaseManager(":memory:")
            >>> _ = db.initialize()
            >>> tm = TaskManager(TasksRepository(db))
            >>> tm.get_status("missing")
            {}
        """
        if task_id in self._records:
            return self._records[task_id].model_dump()
        return self.repo.get_task(task_id)

    async def cancel(self, task_id: str) -> Dict[str, Any]:
        """Принудительная отмена выполняющейся задачи.

        Args:
            task_id (str): Идентификатор задачи.

        Returns:
            Dict[str, Any]: Обновлённая запись задачи.

        Exceptions:
            KeyError: Если задача с указанным `task_id` не найдена.

        Examples:
            >>> pass
        """
        if task_id not in self._records and not self.repo.get_task(task_id):
            raise KeyError(f"Задача '{task_id}' не найдена")

        if task_id in self._running_tasks:
            bg = self._running_tasks[task_id]
            if not bg.done():
                bg.cancel()
                try:
                    await bg
                except asyncio.CancelledError:
                    pass

        if task_id in self._records:
            rec = self._records[task_id]
            rec.status = "cancelled"
            rec.completed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            self.repo.save_task(rec)
            return rec.model_dump()

        db_rec = self.repo.get_task(task_id)
        return db_rec
