# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Modules Kernel Protection - Tests
# =============================================================================
# Description:
#   Комплексные модульные тесты подсистемы инвентаризации драйверов,
#   файловых минифильтров, механизмов защиты ядра и Operation Blocker Detection.
#
# Usage Examples:
#   pytest apps/windows/sdk/modules/kernel_protection/tests/test_kernel_protection.py -v
#
# File: test_kernel_protection.py
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

from apps.windows.sdk.modules.kernel_protection.core.models import (
    BlockerCulpritType,
    BlockerInvestigationRequest,
    BlockerTargetType,
    ComponentCriticality,
    DriverCategory,
    SafeOpsActionRequest,
)
from apps.windows.sdk.modules.kernel_protection.core.driver_inventory import (
    DriverInventoryManager,
    resolve_altitude_group,
    KNOWN_PROTECTION_DRIVERS,
)
from apps.windows.sdk.modules.kernel_protection.core.protection_mechanisms import (
    ProtectionMechanismsAuditor,
)
from apps.windows.sdk.modules.kernel_protection.core.blocker_detector import (
    OperationBlockerDetector,
)
from apps.windows.sdk.modules.kernel_protection.core.safe_ops import (
    KernelSafeOpsManager,
)
from apps.windows.sdk.modules.kernel_protection.router import router


@pytest.fixture
def api_client():
    """Тестовый клиент FastAPI для роутера kernel-protection."""
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_altitude_group_resolution():
    """Проверка правильности сопоставления высот фильтров с категориями Microsoft."""
    assert "Anti-Virus" in resolve_altitude_group("328010")
    assert "Activity Monitor" in resolve_altitude_group("405000")
    assert "System Recovery" in resolve_altitude_group("180451")
    assert "Security Enhancer" in resolve_altitude_group("160100")
    assert "Неопределенная" in resolve_altitude_group("invalid_alt")


def test_known_protection_drivers_catalog():
    """Проверка наличия ключевых системных драйверов в каталоге."""
    assert "ucpd" in KNOWN_PROTECTION_DRIVERS
    assert "wdfilter" in KNOWN_PROTECTION_DRIVERS
    assert "wdboot" in KNOWN_PROTECTION_DRIVERS
    assert "luafv" in KNOWN_PROTECTION_DRIVERS
    assert "bindflt" in KNOWN_PROTECTION_DRIVERS
    assert "cldflt" in KNOWN_PROTECTION_DRIVERS

    # WdFilter должен быть критическим
    assert KNOWN_PROTECTION_DRIVERS["wdfilter"]["criticality"] == ComponentCriticality.CRITICAL
    assert KNOWN_PROTECTION_DRIVERS["wdfilter"]["can_disable"] is False

    # UCPD разрешен к контролируемой деактивации SafeOps
    assert KNOWN_PROTECTION_DRIVERS["ucpd"]["criticality"] == ComponentCriticality.MEDIUM
    assert KNOWN_PROTECTION_DRIVERS["ucpd"]["can_disable"] is True


def test_protection_mechanisms_auditor():
    """Проверка сбора статусов системных механизмов защиты."""
    auditor = ProtectionMechanismsAuditor()
    mechanisms = auditor.audit_all_mechanisms()

    mech_ids = {m.id for m in mechanisms}
    assert "hvci" in mech_ids
    assert "secure_boot" in mech_ids
    assert "ucpd" in mech_ids
    assert "tamper_protection" in mech_ids
    assert "smart_app_control" in mech_ids
    assert "uac_luafv" in mech_ids

    for m in mechanisms:
        assert m.name
        assert m.status_label
        assert m.description_ru


def test_blocker_detection_ucpd():
    """Проверка детектора блокировок при попытке изменения UserChoice (UCPD)."""
    detector = OperationBlockerDetector()
    req = BlockerInvestigationRequest(
        target_type=BlockerTargetType.REGISTRY_KEY,
        target_path=r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice",
        operation="modify"
    )
    verdict = detector.investigate_blocker(req)

    assert verdict.investigated_at
    assert len(verdict.findings) >= 5
    # Если ucpd активен в системе или замокан
    if verdict.is_blocked and verdict.likely_culprit == BlockerCulpritType.UCPD:
        assert "ucpd.sys" in verdict.summary_ru.lower() or "ucpd" in verdict.summary_ru.lower()
        assert len(verdict.remediation_steps_ru) > 0


def test_blocker_detection_tamper_protection():
    """Проверка детектора блокировок для Defender Tamper Protection."""
    detector = OperationBlockerDetector()
    req = BlockerInvestigationRequest(
        target_type=BlockerTargetType.REGISTRY_KEY,
        target_path=r"HKLM\SOFTWARE\Microsoft\Windows Defender\Features",
        operation="modify"
    )
    verdict = detector.investigate_blocker(req)
    assert verdict.investigated_at
    assert len(verdict.findings) >= 5


def test_safe_ops_critical_driver_protection():
    """Проверка запрета отключения критических драйверов ядра (WdFilter)."""
    safe_ops = KernelSafeOpsManager()
    req = SafeOpsActionRequest(
        action="disable",
        component_name="wdfilter",
        confirm_risk=True
    )
    res = safe_ops.execute_action(req)

    # Должен заблокировать операцию
    assert res.success is False
    assert "CRITICAL" in res.message or "критический" in res.message


def test_safe_ops_unconfirmed_risk():
    """Проверка требования флага confirm_risk для UCPD."""
    safe_ops = KernelSafeOpsManager()
    req = SafeOpsActionRequest(
        action="disable_ucpd",
        component_name="ucpd",
        confirm_risk=False
    )
    res = safe_ops.execute_action(req)
    assert res.success is False
    assert "confirm_risk" in res.message


def test_api_summary_endpoint(api_client):
    """Проверка REST эндпоинта /api/kernel-protection/summary."""
    response = api_client.get("/api/kernel-protection/summary")
    assert response.status_code == 200
    data = response.json()
    assert "total_drivers_count" in data
    assert "mechanisms" in data
    assert "minifilters" in data
    assert isinstance(data["mechanisms"], list)
    assert isinstance(data["minifilters"], list)


def test_api_investigate_blocker_endpoint(api_client):
    """Проверка REST эндпоинта расследования блокировок."""
    payload = {
        "target_type": "registry_key",
        "target_path": r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced\TaskbarDa",
        "operation": "modify"
    }
    response = api_client.post("/api/kernel-protection/investigate-blocker", json=payload)
    assert response.status_code == 200
    verdict = response.json()
    assert "is_blocked" in verdict
    assert "likely_culprit" in verdict
    assert "summary_ru" in verdict
    assert "remediation_steps_ru" in verdict
