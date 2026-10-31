# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Live File Events ReadDirectoryChangesW
# =============================================================================
# Description:
#   Модульные тесты для проверки службы мониторинга изменений файлов
#   в реальном времени (ReadDirectoryChangesW) и эндпоинтов /api/v1/system/file-audit.
#
# Usage Examples:
#   CLI:
#     pytest tests/test_file_audit_live_events.py
#
# File: test_file_audit_live_events.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-13 14:15:00
# =============================================================================

import os
import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from apps.windows.api.server import create_app
from apps.windows.sdk.modules.sysadmin.src.directory_watcher import (
    DirectoryWatcher,
    get_directory_watcher,
)


@pytest.fixture(scope="module")
def api_client():
    """Фикстура создания тестового клиента FastAPI приложения."""
    app = create_app()
    return TestClient(app)


def test_get_directory_watcher_auto_start():
    """Тест автоматического запуска DirectoryWatcher при получении экземпляра."""
    watcher = get_directory_watcher(auto_start=True)
    assert watcher is not None
    # На платформе Windows поток наблюдения должен быть запущен
    if os.name == 'nt':
        assert watcher._is_running is True
        assert len(watcher.get_watch_dirs()) > 0


def test_live_file_events_endpoint(api_client):
    """Тест эндпоинта /api/v1/system/file-audit/live-events возвращает статус и структуру данных."""
    response = api_client.get("/api/v1/system/file-audit/live-events?limit=30")
    assert response.status_code == 200
    data = response.json()

    assert "watch_dirs" in data
    assert "is_running" in data
    assert "events" in data
    assert isinstance(data["events"], list)
    if os.name == 'nt':
        assert data["is_running"] is True
        assert len(data["watch_dirs"]) > 0


def test_live_file_events_capture():
    """Тест фиксации реальных событий изменения файлов через ReadDirectoryChangesW."""
    if os.name != 'nt':
        pytest.skip("ReadDirectoryChangesW поддерживается только на Windows")

    temp_dir = Path.cwd().resolve()
    watcher = get_directory_watcher(watch_dirs=[str(temp_dir)], auto_start=True)
    assert watcher._is_running is True

    test_file = temp_dir / f"test_event_probe_{int(time.time())}.txt"
    try:
        # Создание файла
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("test live watcher probe")
        time.sleep(0.5)

        # Модификация файла
        with open(test_file, "a", encoding="utf-8") as f:
            f.write(" - updated")
        time.sleep(0.5)

        recent_events = watcher.get_recent_events(limit=50)
        file_paths = [e.path.lower() for e in recent_events]
        assert str(test_file).lower() in file_paths
    finally:
        if test_file.exists():
            try:
                os.remove(test_file)
            except Exception:
                pass

