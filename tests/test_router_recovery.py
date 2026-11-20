# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Router Recovery
# =============================================================================
# Description:
#   Юнит-тесты REST эндпоинтов модуля восстановления файлов R-Studio
#   (GET /api/v1/recovery/status, POST /api/v1/recovery/launch).
#
# File: test_router_recovery.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20 16:45:00
# =============================================================================

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from fastapi import HTTPException

from apps.windows.api.routers.router_recovery import (
    _find_recovery_executable,
    get_recovery_status,
    launch_recovery_tool,
)


@pytest.mark.asyncio
async def test_recovery_status_file_not_found() -> None:
    """Проверка статуса при отсутствии исполняемого файла R-Studio на диске."""
    with patch('apps.windows.api.routers.router_recovery._find_recovery_executable', return_value=(None, r'bin\R-Studio_Technician_9.5.191810_Portable\R-Studio_9.5.exe')):
        resp = await get_recovery_status()

    assert resp.tool.exists is False
    assert resp.tool.path is None
    assert 'bin' in resp.tool.relative_path
    assert resp.tool.size_bytes == 0


@pytest.mark.asyncio
async def test_recovery_status_file_exists(tmp_path: Path) -> None:
    """Проверка корректного сбора атрибутов файла R-Studio при его наличии."""
    fake_exe = tmp_path / "R-Studio_9.5.exe"
    fake_exe.write_bytes(b"MOCK_EXE_BYTES" * 100)

    with patch('apps.windows.api.routers.router_recovery._find_recovery_executable', return_value=(fake_exe, str(fake_exe))):
        resp = await get_recovery_status()

    assert resp.tool.exists is True
    assert resp.tool.path == str(fake_exe)
    assert resp.tool.size_bytes > 0
    assert resp.tool.modified_time is not None


@pytest.mark.asyncio
async def test_recovery_launch_not_found_raises_404() -> None:
    """Проверка возбуждения 404 с понятным сообщением при попытке запуска отсутствующего файла."""
    with patch('apps.windows.api.routers.router_recovery._find_recovery_executable', return_value=(None, r'bin\R-Studio_9.5.exe')):
        with pytest.raises(HTTPException) as exc_info:
            await launch_recovery_tool()

    assert exc_info.value.status_code == 404
    assert 'Исполняемый файл R-Studio не найден' in exc_info.value.detail


@pytest.mark.asyncio
async def test_recovery_launch_success(tmp_path: Path) -> None:
    """Проверка успешного запуска исполняемого файла R-Studio в неблокирующем режиме."""
    fake_exe = tmp_path / "R-Studio_9.5.exe"
    fake_exe.write_bytes(b"MOCK_EXE")

    mock_proc = MagicMock()
    mock_proc.pid = 4321

    with patch('apps.windows.api.routers.router_recovery._find_recovery_executable', return_value=(fake_exe, str(fake_exe))), \
         patch('subprocess.Popen', return_value=mock_proc):
        resp = await launch_recovery_tool()

    assert resp.success is True
    assert resp.pid == 4321
    assert 'успешно запущена' in resp.message
