# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Tests - Telemetry Paths Verification
# =============================================================================
# Description:
#   Тестирование строгого соответствия путей подсистемы телеметрии:
#   все данные, база данных telemetry.db и логи телеметрии должны располагаться
#   в %PROGRAMDATA% / <app_name> / 'telemetry' / ...
#
# File: test_telemetry_paths.py
# Project: ai-tc
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 04:41:30
# =============================================================================

from pathlib import Path
import os
import pytest

from apps.windows.telemetry.init_db import get_default_telemetry_db_path
from apps.windows.telemetry.telemetry_config import (
    TelemetryConfigManager,
    get_default_telemetry_config_path,
)
from apps.common.csv_logger import get_apps_log_dir
from apps.windows.analytics.aggregator import TelemetryAggregator
from apps.windows.sdk.modules.taskbar.core.history_manager import get_telemetry_db_path as get_taskbar_db_path
from apps.windows.sdk.modules.window_control_plane.history import get_default_telemetry_db_path as get_wcp_db_path


def test_telemetry_init_db_path() -> None:
    """Проверка пути по умолчанию к базе данных telemetry.db в init_db."""
    programdata = os.environ.get("ProgramData") or os.environ.get("ALLUSERSPROFILE") or "C:\\ProgramData"
    app_name = os.environ.get("APP_NAME") or "ai-tc"
    expected_db_path = Path(programdata) / app_name / "telemetry" / "telemetry.db"

    db_path = get_default_telemetry_db_path()
    assert Path(db_path) == expected_db_path


def test_telemetry_config_paths() -> None:
    """Проверка путей базы данных, конфигурации и хранилища в TelemetryConfigManager."""
    programdata = os.environ.get("ProgramData") or os.environ.get("ALLUSERSPROFILE") or "C:\\ProgramData"
    app_name = os.environ.get("APP_NAME") or "ai-tc"
    expected_base_dir = Path(programdata) / app_name / "telemetry"

    mgr = TelemetryConfigManager()
    data_path = mgr.get_data_path()
    db_path = mgr.get_db_path()
    cfg_path = get_default_telemetry_config_path()

    assert Path(data_path) == expected_base_dir
    assert Path(db_path) == expected_base_dir / "telemetry.db"
    assert Path(cfg_path) == expected_base_dir / "config.json"


def test_apps_log_dir_path() -> None:
    """Проверка стандартного каталога логов телеметрии через get_apps_log_dir."""
    programdata = os.environ.get("ProgramData") or os.environ.get("ALLUSERSPROFILE") or "C:\\ProgramData"
    app_name = os.environ.get("APP_NAME") or "ai-tc"
    expected_log_dir = Path(programdata) / app_name / "telemetry" / "logs"

    log_dir = get_apps_log_dir()
    assert Path(log_dir) == expected_log_dir


def test_telemetry_aggregator_log_dir() -> None:
    """Проверка директории логов по умолчанию в TelemetryAggregator."""
    programdata = os.environ.get("ProgramData") or os.environ.get("ALLUSERSPROFILE") or "C:\\ProgramData"
    app_name = os.environ.get("APP_NAME") or "ai-tc"
    expected_log_dir = Path(programdata) / app_name / "telemetry" / "logs"

    agg_log_dir = TelemetryAggregator._get_default_log_dir()
    assert Path(agg_log_dir) == expected_log_dir


def test_sdk_history_managers_telemetry_db_path() -> None:
    """Проверка путей к telemetry.db в модулях SDK (Taskbar и Window Control Plane)."""
    programdata = os.environ.get("ProgramData") or os.environ.get("ALLUSERSPROFILE") or "C:\\ProgramData"
    app_name = os.environ.get("APP_NAME") or "ai-tc"
    expected_db_path = Path(programdata) / app_name / "telemetry" / "telemetry.db"

    taskbar_db = get_taskbar_db_path()
    wcp_db = get_wcp_db_path()

    assert Path(taskbar_db) == expected_db_path
    assert Path(wcp_db) == expected_db_path

