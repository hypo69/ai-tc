# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Test Process Activity Readonly
# =============================================================================
# Description:
#   Тесты на проверку строгого режима Read-Only для метода get_active_instances
#   в ProcessActivityEngine: метод не должен инициировать сбор процессов или
#   запись в SQLite при запросах от веб-интерфейса.
#
# File: test_process_activity_readonly.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-16 15:12:00
# =============================================================================

from unittest.mock import MagicMock, patch
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.windows.sdk.core.process_activity_engine import ProcessActivityEngine
from apps.windows.api.routers.router_process_activity import init_router


def test_get_active_instances_does_not_call_sync_processes():
    """Проверяет, что get_active_instances не вызывает sync_processes и работает строго на чтение."""
    engine = ProcessActivityEngine.get_instance()

    with patch.object(engine, "sync_processes") as mock_sync:
        res = engine.get_active_instances(limit=10)
        assert isinstance(res, list)
        mock_sync.assert_not_called()


def test_get_active_instances_returns_valid_instances():
    """Проверяет, что get_active_instances успешно выполняется без ошибок схемы SQLite."""
    engine = ProcessActivityEngine.get_instance()
    instances = engine.get_active_instances(limit=5)
    assert isinstance(instances, list)
    for inst in instances:
        assert hasattr(inst, "instance_id")
        assert inst.instance_id is not None
        assert isinstance(inst.instance_id, (str, int))


def test_router_process_activity_endpoints():
    """Проверяет доступность эндпоинтов активных процессов, top-processes и file-watcher/events."""
    app = FastAPI()
    router = init_router()
    app.include_router(router)
    client = TestClient(app)

    # 1. Активные инстансы процессов
    res_active = client.get("/api/v1/telemetry/instances/active?limit=10")
    assert res_active.status_code == 200
    assert isinstance(res_active.json(), list)

    # 2. Системный топ-процессов
    res_top = client.get("/api/v1/system/top-processes?limit=10")
    assert res_top.status_code == 200
    assert isinstance(res_top.json(), list)

    # 3. Живые события файловой активности
    res_files = client.get("/api/v1/system/file-watcher/events?limit=10")
    assert res_files.status_code == 200
    assert isinstance(res_files.json(), list)

