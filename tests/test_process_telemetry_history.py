# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Process Deep Telemetry & History
# =============================================================================
# Description:
#   Юнит-тесты REST эндпоинта глубокой телеметрии жизненного цикла процесса
#   (GET /api/v1/telemetry/processes/{pid}/deep-history), включая накопленные
#   ресурсы диска, памяти, процессора, сети и датчиков приватности (микрофон, камера).
#
# File: test_process_telemetry_history.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 12:55:00
# =============================================================================

from __future__ import annotations

import os
from unittest.mock import MagicMock
import pytest
from apps.windows.telemetry.models import ProcessPrivacySensorInfo
from apps.windows.api.routers.router_telemetry import (
    _get_process_camera_mic_status,
    _get_gui_resources,
    _evaluate_process_suspicion,
    get_process_deep_history,
)


@pytest.mark.asyncio
async def test_get_process_deep_history_current_pid() -> None:
    """Тест получения полной телеметрии и жизненного цикла для текущего процесса."""
    current_pid = os.getpid()
    response = await get_process_deep_history(current_pid)

    assert response.pid == current_pid
    assert "python" in response.process_name.lower()
    assert response.uptime_seconds >= 0.0
    assert response.start_time != ""
    assert response.user_name is not None

    # Проверка накопленных ресурсов памяти
    assert response.memory_working_set_mb > 0.0
    assert response.memory_peak_working_set_mb >= response.memory_working_set_mb or response.memory_peak_working_set_mb > 0.0

    # Проверка накопленных ресурсов ввода-вывода (диск)
    assert response.disk_read_bytes_total >= 0
    assert response.disk_write_bytes_total >= 0
    assert response.disk_read_mb_total >= 0.0

    # Проверка процессора
    assert response.cpu_total_time_sec >= 0.0
    assert response.thread_count >= 1

    # Проверка датчиков конфиденциальности (микрофон и камера)
    assert response.microphone is not None
    assert isinstance(response.microphone.is_active_now, bool)
    assert response.camera is not None
    assert isinstance(response.camera.is_active_now, bool)

    # Проверка сетевых сокетов
    assert isinstance(response.sockets, list)

    # Проверка оценки подозрительности
    assert response.suspicion_score >= 0
    assert response.suspicion_level in ['SAFE', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
    assert isinstance(response.suspicion_triggers, list)


def test_get_process_camera_mic_status_safe() -> None:
    """Проверка безопасного опроса датчиков камеры и микрофона через ConsentStore."""
    mic, cam = _get_process_camera_mic_status("explorer.exe")
    assert mic is not None
    assert cam is not None
    assert isinstance(mic.is_active_now, bool)
    assert isinstance(cam.is_active_now, bool)


def test_get_gui_resources_safe() -> None:
    """Проверка безопасного опроса GDI и USER объектов Win32."""
    gdi, user = _get_gui_resources(os.getpid())
    assert gdi >= 0
    assert user >= 0


def test_evaluate_process_suspicion_multi_powershell() -> None:
    """Проверка выявления шторма процессов PowerShell у подозрительного процесса."""
    mock_proc = MagicMock()
    # Имитируем 4 запущенных дочерних powershell процесса
    child1 = MagicMock()
    child1.name.return_value = 'powershell.exe'
    child2 = MagicMock()
    child2.name.return_value = 'powershell.exe'
    child3 = MagicMock()
    child3.name.return_value = 'pwsh.exe'
    child4 = MagicMock()
    child4.name.return_value = 'powershell.exe'
    mock_proc.children.return_value = [child1, child2, child3, child4]

    score, level, ps_count, susp_count, triggers = _evaluate_process_suspicion(
        proc=mock_proc,
        proc_name='malicious_agent.exe',
        cmd_line='C:\\malicious_agent.exe -w hidden',
        parent_name='cmd.exe',
        mic_status=ProcessPrivacySensorInfo(is_active_now=False),
        cam_status=ProcessPrivacySensorInfo(is_active_now=False),
        user_objects=1,
        gdi_objects=1,
    )

    assert ps_count == 4
    assert susp_count == 4
    assert score >= 65  # 40 (за 4 powershell) + 25 (за -w hidden)
    assert level in ['HIGH', 'CRITICAL']
    assert any('PowerShell' in t for t in triggers)
    assert any('скрытом окне' in t for t in triggers)


def test_evaluate_process_suspicion_office_spawn() -> None:
    """Проверка выявления запуска шелла из офисного приложения (Word / Excel)."""
    score, level, ps_count, susp_count, triggers = _evaluate_process_suspicion(
        proc=None,
        proc_name='powershell.exe',
        cmd_line='powershell.exe -enc SQBYAFgA -ExecutionPolicy Bypass',
        parent_name='winword.exe',
        mic_status=ProcessPrivacySensorInfo(is_active_now=False),
        cam_status=ProcessPrivacySensorInfo(is_active_now=False),
        user_objects=0,
        gdi_objects=0,
    )

    assert score >= 80
    assert level == 'CRITICAL'
    assert any('офисное приложение' in t for t in triggers)
    assert any('Base64' in t for t in triggers)

