# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Tests - System Restore
# =============================================================================
# Description:
#   Юнит-тесты менеджера точек восстановления Windows (WindowsSystemRestoreManager).
#   Проверяют нормализацию параметра RestorePointType для Checkpoint-Computer.
#
# File: test_system_restore.py
# Project: ai-tc
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20 16:48:00
# =============================================================================

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

from apps.windows.sdk.core.system_restore import WindowsSystemRestoreManager


def test_create_restore_point_normalizes_unsupported_type() -> None:
    """Проверяет, что неподдерживаемый Checkpoint-Computer тип WINDOWS_UPDATE приводится к MODIFY_SETTINGS."""
    mgr = WindowsSystemRestoreManager()
    mock_result = MagicMock(spec=subprocess.CompletedProcess)
    mock_result.returncode = 0
    mock_result.stdout = ""
    mock_result.stderr = ""

    with (
        patch.object(mgr, "get_shadow_storage_info", return_value={"available": True, "at_risk_of_eviction": False}),
        patch("apps.windows.sdk.core.system_restore.subprocess.run", return_value=mock_result) as mock_run,
    ):
        res = mgr.create_restore_point(
            description="Подготовка к обновлению Windows 11 26H2",
            restore_point_type="WINDOWS_UPDATE",
        )

    assert res["success"] is True
    assert res["restore_point_type"] == "MODIFY_SETTINGS"
    cmd_args = mock_run.call_args[0][0]
    ps_script = cmd_args[-1]
    assert '-RestorePointType "MODIFY_SETTINGS"' in ps_script
    assert "WINDOWS_UPDATE" not in ps_script


def test_create_restore_point_keeps_valid_type() -> None:
    """Проверяет, что допустимый тип из ValidateSet передается в Checkpoint-Computer без изменений."""
    mgr = WindowsSystemRestoreManager()
    mock_result = MagicMock(spec=subprocess.CompletedProcess)
    mock_result.returncode = 0
    mock_result.stdout = ""
    mock_result.stderr = ""

    with (
        patch.object(mgr, "get_shadow_storage_info", return_value={"available": True, "at_risk_of_eviction": False}),
        patch("apps.windows.sdk.core.system_restore.subprocess.run", return_value=mock_result) as mock_run,
    ):
        res = mgr.create_restore_point(
            description="Установка приложения",
            restore_point_type="APPLICATION_INSTALL",
        )

    assert res["success"] is True
    assert res["restore_point_type"] == "APPLICATION_INSTALL"
    cmd_args = mock_run.call_args[0][0]
    assert '-RestorePointType "APPLICATION_INSTALL"' in cmd_args[-1]
