# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Modules Task_Scheduler Tests - Test Task Scheduler
# =============================================================================
# Description:
#   # Description:
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.task_scheduler.tests.test_task_scheduler import manager
#
#     res = manager()
#
# File: test_task_scheduler.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.task_scheduler.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 19:05:00
# =============================================================================

from __future__ import annotations
"""Тестирование функциональности модуля планировщика задач Windows."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from apps.windows.sdk.modules.task_scheduler.core.manager import TaskSchedulerManager
from apps.windows.sdk.modules.task_scheduler.core.models import TaskActionRequest
from apps.windows.sdk.modules.task_scheduler.router import init_router


@pytest.fixture
def manager() -> TaskSchedulerManager:
    return TaskSchedulerManager()


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(init_router())
    return TestClient(app)


def test_task_scheduler_report(manager: TaskSchedulerManager):
    """Проверка генерации отчета о заданиях."""
    report = manager.generate_report()
    assert report is not None
    assert report.total_tasks >= 0


@pytest.mark.asyncio
async def test_task_action_simulation(manager: TaskSchedulerManager):
    """Проверка симуляции действия с заданием."""
    req = TaskActionRequest(
        task_path='\\Microsoft\\Windows\\Defrag\\ScheduledDefrag',
        action='run',
        dry_run=True,
        confirmed_by_user=False
    )
    res = await manager.execute_task_action(req)
    assert res['status'] == 'DRY_RUN_SUCCESS'


def test_task_scheduler_endpoints(client: TestClient):
    """Проверка REST эндпоинтов task_scheduler."""
    resp = client.get('/api/task-scheduler/report')
    assert resp.status_code == 200
    data = resp.json()
    assert 'tasks' in data

    resp_tasks = client.get('/api/task-scheduler/tasks')
    assert resp_tasks.status_code == 200


@pytest.mark.asyncio
async def test_com_taskscheduler_in_worker_thread():
    """Проверка доступности COM-интерфейса планировщика в фоновом потоке asyncio.to_thread."""
    import asyncio
    from apps.windows.sdk.win32_ffi.tasksched import TaskSchedulerAPI

    api = TaskSchedulerAPI()
    assert api.is_available is True

    # Вызов сбора задач в фоновом потоке пула
    tasks = await asyncio.to_thread(api.get_all_tasks, max_tasks=10)
    assert isinstance(tasks, list)
    assert len(tasks) > 0


def test_history_status(manager: TaskSchedulerManager):
    """Проверка получения статуса журнала истории планировщика."""
    status = manager.get_history_status()
    assert isinstance(status, dict)
    assert 'enabled' in status
    assert 'channel' in status
    assert status['channel'] == 'Microsoft-Windows-TaskScheduler/Operational'


def test_history_status_endpoints(client: TestClient):
    """Проверка эндпоинтов получения и изменения статуса истории задач."""
    # GET запрос статуса
    resp_get = client.get('/api/task-scheduler/history-status')
    assert resp_get.status_code == 200
    data_get = resp_get.json()
    assert 'enabled' in data_get
    assert data_get['channel'] == 'Microsoft-Windows-TaskScheduler/Operational'

    # Проверка отчета на наличие поля history_enabled
    resp_rep = client.get('/api/task-scheduler/report')
    assert resp_rep.status_code == 200
    assert 'history_enabled' in resp_rep.json()



