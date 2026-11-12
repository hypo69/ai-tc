# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Modules Kernel Protection - UCPD Tests
# =============================================================================
# Description:
#   Комплексные тесты системного менеджера UCPD (User Choice Protection Driver):
#   согласованность состояния, восстановление исходного типа старта, обработка
#   частичных сбоев задачи планировщика и экспериментальная проверка TaskbarDa.
#
# Usage Examples:
#   pytest apps/windows/sdk/modules/kernel_protection/tests/test_ucpd_manager.py -v
#
# File: test_ucpd_manager.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.kernel_protection.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 14:40:00
# =============================================================================

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from apps.windows.sdk.modules.kernel_protection.core.ucpd_manager import (
    UcpdDriverState,
    UcpdFullStatus,
    UcpdRebootStatus,
    UcpdSetStateRequest,
    UcpdSetStateResponse,
    UcpdSystemManager,
    UcpdTaskState,
)
from apps.windows.sdk.modules.kernel_protection.router import router


@pytest.fixture
def ucpd_client():
    """Тестовый клиент FastAPI для роутера UCPD."""
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_ucpd_detailed_status_structure():
    """Проверка сбора согласованного статуса UCPD."""
    mgr = UcpdSystemManager()
    status = mgr.get_detailed_status()

    assert isinstance(status, UcpdFullStatus)
    assert status.overall_state in ("enabled", "disabled", "partially_disabled", "reboot_pending")
    assert status.status_label_ru
    assert status.driver.start_type in (1, 2, 3, 4)
    assert status.driver.start_type_name in ("system", "auto", "manual", "disabled")
    assert isinstance(status.driver.is_running, bool)
    assert isinstance(status.task.exists, bool)
    assert isinstance(status.reboot.reboot_required, bool)


def test_reboot_required_detection():
    """Проверка логики определения требования перезагрузки."""
    mgr = UcpdSystemManager()

    # Сценарий: в реестре Disabled (4), но драйвер все еще Running в ядре
    with patch.object(mgr, '_inspect_driver', return_value=UcpdDriverState(
        start_type=4,
        start_type_name="disabled",
        is_running=True,
        altitude="385250.5",
        instances_count=2
    )):
        with patch.object(mgr, '_inspect_scheduled_task', return_value=UcpdTaskState(
            task_name="UCPD velocity",
            task_path=r"\Microsoft\Windows\AppxDeploymentClient\\",
            exists=True,
            state="Disabled",
            is_enabled=False
        )):
            st = mgr.get_detailed_status()
            assert st.reboot.reboot_required is True
            assert "перезагрузка" in st.reboot.reason_ru.lower()
            assert st.overall_state == "reboot_pending"


def test_security_warning_on_unconfirmed_disable():
    """Проверка запрета отключения UCPD без явного подтверждения риска."""
    mgr = UcpdSystemManager()
    req = UcpdSetStateRequest(
        target_state="disabled",
        manage_scheduled_task=True,
        confirm_security_risk=False
    )
    res = mgr.set_state(req)
    assert res.success is False
    assert "confirm_security_risk" in res.message or "предупреждение" in res.message.lower()


def test_restoration_of_original_start_type():
    """Проверка восстановления исходного типа запуска (start=system или start=auto), а не безусловного system."""
    mgr = UcpdSystemManager()

    # Мокаем исходную конфигурацию, где original_start_type был 1 (system)
    mock_backup = {
        "original_start_type": 1,
        "original_start_name": "system",
        "user_intent": "disabled"
    }

    with patch.object(mgr, '_load_backup_config', return_value=mock_backup):
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            req = UcpdSetStateRequest(
                target_state="enabled",
                manage_scheduled_task=True,
                confirm_security_risk=False
            )
            res = mgr.set_state(req)

            # Проверяем, что sc.exe был вызван именно с start= system
            calls = mock_run.call_args_list
            sc_calls = [c[0][0] for c in calls if len(c[0]) > 0 and c[0][0][0] == "sc.exe"]
            assert len(sc_calls) > 0
            assert "system" in sc_calls[0]


def test_partial_success_when_task_fails():
    """Проверка возврата частичного результата, если служба изменена, а задача сбойнула (п. 4)."""
    mgr = UcpdSystemManager()

    def mock_subprocess(cmd, **kwargs):
        if cmd[0] == "sc.exe":
            return MagicMock(returncode=0, stdout="SUCCESS", stderr="")
        elif cmd[0] == "schtasks.exe":
            return MagicMock(returncode=1, stdout="", stderr="Access is denied")
        return MagicMock(returncode=0, stdout="", stderr="")

    with patch('subprocess.run', side_effect=mock_subprocess):
        with patch.object(mgr, '_find_ucpd_task_name', return_value="UCPD velocity"):
            req = UcpdSetStateRequest(
                target_state="disabled",
                manage_scheduled_task=True,
                confirm_security_risk=True
            )
            res = mgr.set_state(req)

            assert res.success is True
            assert res.partial_success is True
            assert len(res.warnings) > 0
            assert "частичный" in res.message.lower()


def test_taskbarda_experiment():
    """Проверка выполнения эксперимента с TaskbarDa."""
    mgr = UcpdSystemManager()
    res = mgr.test_taskbarda_blocker()

    assert res.tested_at
    assert isinstance(res.is_blocked, bool)
    assert res.conclusion_ru


def test_api_ucpd_endpoints(ucpd_client):
    """Проверка REST API эндпоинтов UCPD."""
    # GET status
    resp = ucpd_client.get("/api/kernel-protection/ucpd/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "overall_state" in data
    assert "driver" in data
    assert "task" in data

    # POST test-taskbarda
    resp_exp = ucpd_client.post("/api/kernel-protection/ucpd/test-taskbarda")
    assert resp_exp.status_code == 200
    exp_data = resp_exp.json()
    assert "is_blocked" in exp_data
    assert "conclusion_ru" in exp_data
