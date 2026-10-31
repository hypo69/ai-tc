# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Modules System_Checkpoints Tests - Test Restore Point Advisor
# =============================================================================
# Description:
#   Модульные тесты для RestorePointAdvisor (интеллектуальный советник контрольных точек).
#
# Usage Examples:
#   pytest apps/windows/sdk/modules/system_checkpoints/tests/test_restore_point_advisor.py
#
# File: test_restore_point_advisor.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.system_checkpoints.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-16 22:18:00
# =============================================================================

from __future__ import annotations
"""Тестирование логики предварительной оценки, отпечатков и принятия решений RestorePointAdvisor."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from apps.windows.system_checkpoints.core.restore_point_advisor import (
    RestorePointAdvisor,
    RestorePointStateJournal,
)
from apps.windows.system_checkpoints.models import (
    AdvisorDecision,
    CheckpointType,
)


@pytest.fixture
def temp_journal_db():
    """Создание временной базы данных SQLite для тестов журнала состояний."""
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
        db_path = f.name
    yield db_path
    try:
        Path(db_path).unlink(missing_ok=True)
    except Exception:
        pass


@pytest.fixture
def advisor(temp_journal_db):
    """Инициализация тестового экземпляра RestorePointAdvisor с временной БД."""
    adv = RestorePointAdvisor(db_path=temp_journal_db)
    # По умолчанию мокаем готовность к восстановлению
    adv.check_readiness = MagicMock(return_value={
        "can_restore": True,
        "protection_enabled": True,
        "vss_available": True,
        "shadow_usage_percent": 25.0,
        "free_space_gb": 45.5,
        "target_drive": "C:",
        "error_message": None,
    })
    return adv


def test_collect_current_state(advisor):
    """Проверка сбора категорий и формирования хешей отпечатков."""
    state = advisor.collect_current_state(trigger_event="USER_REQUEST")
    assert "composite_fingerprint" in state
    assert len(state["composite_fingerprint"]) == 64  # SHA-256
    assert "category_hashes" in state
    assert "drivers" in state["category_hashes"]
    assert "software" in state["category_hashes"]
    assert "services" in state["category_hashes"]
    assert "updates" in state["category_hashes"]
    assert "boot_config" in state["category_hashes"]
    assert "registry" in state["category_hashes"]
    assert "system_files" in state["category_hashes"]
    assert "user_files" in state["category_hashes"]


def test_evaluate_initial_state(advisor):
    """Проверка первой оценки, когда в журнале еще нет предыдущих точек."""
    result = advisor.evaluate(trigger_event="USER_REQUEST")
    assert result.decision == AdvisorDecision.CREATE
    assert result.questions["q1"]["meaningful_changes"] is True
    assert result.questions["q2"]["is_duplicate"] is False
    assert result.questions["q3"]["can_restore"] is True


def test_evaluate_duplicate_state(advisor):
    """Проверка дедупликации: если отпечаток идентичен предыдущему, решение SKIP."""
    # Записываем первое состояние в журнал
    cur_state = advisor.collect_current_state(trigger_event="USER_REQUEST")
    advisor.journal.save_snapshot(
        trigger_event="USER_REQUEST",
        composite_fingerprint=cur_state["composite_fingerprint"],
        category_fingerprints=cur_state["category_hashes"],
        category_data=cur_state["data"],
        decision="CREATE",
        summary="Начальная точка",
        questions={},
        is_restore_point=True,
    )

    # Повторная оценка с тем же состоянием
    result = advisor.evaluate(trigger_event="USER_REQUEST", current_state=cur_state)
    assert result.decision == AdvisorDecision.SKIP
    assert result.questions["q2"]["is_duplicate"] is True
    assert "пропущено" in result.summary.lower() or "дубликат" in result.summary.lower()


def test_evaluate_driver_change(advisor):
    """Проверка реакции на изменение драйвера: решение CREATE со значимостью HIGH."""
    # Сохраняем исходное состояние
    initial_state = {
        "trigger_event": "USER_REQUEST",
        "composite_fingerprint": "prev_hash_123",
        "category_hashes": {
            "drivers": "hash_drv_1",
            "software": "hash_soft_1",
            "services": "hash_svc_1",
            "updates": "hash_upd_1",
            "boot_config": "hash_boot_1",
            "registry": "hash_reg_1",
            "system_files": "hash_sys_1",
        },
        "data": {
            "drivers": [{"name": "oem1.inf", "class": "Net"}],
            "software": [],
            "services": [],
            "updates": [],
            "boot_config": {},
            "registry": {},
            "system_files": [],
        },
    }
    advisor.journal.save_snapshot(
        trigger_event="USER_REQUEST",
        composite_fingerprint=initial_state["composite_fingerprint"],
        category_fingerprints=initial_state["category_hashes"],
        category_data=initial_state["data"],
        decision="CREATE",
        summary="Точка 1",
        questions={},
        is_restore_point=True,
    )

    # Новое состояние с новым драйвером
    new_state = {
        "trigger_event": "DRIVER_CHANGE",
        "composite_fingerprint": "new_hash_456",
        "category_hashes": {
            **initial_state["category_hashes"],
            "drivers": "hash_drv_new_version",
        },
        "data": {
            **initial_state["data"],
            "drivers": [
                {"name": "oem1.inf", "class": "Net"},
                {"name": "oem2.inf", "class": "Display"},
            ],
        },
    }

    result = advisor.evaluate(trigger_event="DRIVER_CHANGE", current_state=new_state)
    assert result.decision == AdvisorDecision.CREATE
    assert result.questions["q1"]["meaningful_changes"] is True
    assert result.questions["q2"]["is_duplicate"] is False
    assert any(d.category == "drivers" and d.change_type == "ADDED" for d in result.deltas)


def test_evaluate_protection_disabled(advisor):
    """Проверка готовности: если System Protection отключена, решение CLARIFY."""
    advisor.check_readiness = MagicMock(return_value={
        "can_restore": False,
        "protection_enabled": False,
        "vss_available": True,
        "shadow_usage_percent": 0.0,
        "free_space_gb": 10.0,
        "target_drive": "C:",
        "error_message": "Защита системы выключена",
    })
    result = advisor.evaluate(trigger_event="USER_REQUEST")
    assert result.decision == AdvisorDecision.CLARIFY
    assert result.questions["q3"]["can_restore"] is False


def test_execute_smart_restore_skip(advisor):
    """Проверка execute_smart_restore_point: если вердикт SKIP и не force, точка не создается."""
    # Имитируем существующую точку
    cur_state = advisor.collect_current_state(trigger_event="USER_REQUEST")
    advisor.journal.save_snapshot(
        trigger_event="USER_REQUEST",
        composite_fingerprint=cur_state["composite_fingerprint"],
        category_fingerprints=cur_state["category_hashes"],
        category_data=cur_state["data"],
        decision="CREATE",
        summary="Существующая точка",
        questions={},
        is_restore_point=True,
    )

    exec_result = advisor.execute_smart_restore_point(
        title="Тест",
        trigger_event="USER_REQUEST",
        force=False,
    )
    assert exec_result["created"] is False
    assert exec_result["decision"] == "SKIP"


def test_journal_history_retrieval(advisor):
    """Проверка чтения истории из базы данных журнала."""
    cur_state = advisor.collect_current_state()
    advisor.journal.save_snapshot(
        trigger_event="USER_REQUEST",
        composite_fingerprint=cur_state["composite_fingerprint"],
        category_fingerprints=cur_state["category_hashes"],
        category_data=cur_state["data"],
        decision="CREATE",
        summary="Запись истории 1",
        questions={"q1": {"verdict": "Да"}},
        is_restore_point=True,
    )
    history = advisor.journal.get_recent_snapshots(limit=10)
    assert len(history) >= 1
    assert history[0]["decision"] == "CREATE"
    assert "drivers" in history[0]["category_fingerprints"]


def test_default_journal_db_path():
    """Проверка стандартного расположения SQLite базы данных журнала в %ProgramData%."""
    from apps.windows.system_checkpoints.core.restore_point_advisor import get_default_state_journal_db_path
    path = get_default_state_journal_db_path()
    assert "AI-Windows-Admin" in str(path)
    assert "telemetry" in str(path)
    assert "logs" in str(path)
    assert path.name == "state_journal.sqlite"


