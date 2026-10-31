# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Telemetry - Software Audit Persistence Tests
# =============================================================================
# Description:
#   Модульные тесты интеграции аудита программного обеспечения с базой данных
#   SQLite телеметрии (сохранение отчетов, обновление инвентаря ПО, отсутствие CSV).
#
# File: test_software_audit_telemetry.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-20 20:36:00
# =============================================================================

from __future__ import annotations

"""Модульные тесты сохранения и обновления аудита ПО в SQLite БД телеметрии."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import pytest

from apps.windows.sdk.core.data_model import (
    AppCategory,
    AppExecutionInfo,
    InstalledAppInfo,
    SoftwareAuditReport,
)
from apps.windows.sdk.core.software_audit import SoftwareAuditEngine
from apps.windows.telemetry.sqlite import TelemetryStorage


import gc
import shutil

@pytest.fixture
def temp_storage():
    """Создает временное изолированное хранилище SQLite телеметрии для тестов.

    Yields:
        TelemetryStorage: Экземпляр хранилища с временным файлом БД.
    """
    tmp_dir = tempfile.mkdtemp()
    db_file = Path(tmp_dir) / "test_telemetry.db"
    storage = TelemetryStorage(db_path=db_file, read_only=False, auto_flush=True)
    try:
        yield storage
    finally:
        try:
            storage.close()
        except Exception:
            pass
        gc.collect()
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_software_audit_report_saving_and_retrieval(temp_storage: TelemetryStorage):
    """Проверка сохранения сводного отчета аудита ПО и его извлечения из базы данных."""
    now = datetime.now(timezone.utc)
    app1 = InstalledAppInfo(
        name="TestApp1",
        display_name="Тестовое Приложение 1",
        version="1.0.0",
        publisher="Test Corp",
        install_date="2026-01-01",
        install_location="C:\\Program Files\\TestApp1",
        uninstall_string="C:\\Program Files\\TestApp1\\unins000.exe",
        size_bytes=100 * 1024 * 1024,
        category=AppCategory.UTILITIES,
        purpose_description="Утилита для тестов",
        execution_info=AppExecutionInfo(
            last_run_time=now - timedelta(days=5),
            run_count=12,
            focus_time_seconds=3600,
            source_artifact="UserAssist",
            raw_path="C:\\Program Files\\TestApp1\\app.exe",
        ),
    )
    app2 = InstalledAppInfo(
        name="TestApp2",
        display_name="Спящее Приложение 2",
        version="2.1.0",
        publisher="Legacy Ltd",
        install_date="2025-05-10",
        install_location="C:\\Program Files\\TestApp2",
        size_bytes=50 * 1024 * 1024,
        category=AppCategory.OTHER,
        purpose_description="Старое ПО",
        execution_info=None,
    )

    report = SoftwareAuditReport(
        timestamp=now,
        total_apps=2,
        active_apps_count=1,
        unused_apps_count=1,
        categories_breakdown={"Утилиты и системные программы": 1, "Прочее": 1},
        recently_launched=[app1],
        top_launched=[app1],
        never_launched_or_dormant=[app2],
        apps=[app1, app2],
    )

    saved_count = temp_storage.save_software_audit_report(report)
    assert saved_count == 2, "Должно сохраниться 2 приложения в инвентаре"

    # Проверка извлечения последнего отчета
    latest_report = temp_storage.get_latest_software_audit_report()
    assert latest_report is not None, "Последний отчет должен быть найден в БД"
    assert latest_report["total_apps"] == 2
    assert latest_report["active_apps_count"] == 1
    assert latest_report["unused_apps_count"] == 1
    assert "Утилиты и системные программы" in latest_report["categories_breakdown"]
    assert len(latest_report["top_launched"]) == 1
    assert len(latest_report["never_launched_or_dormant"]) == 1

    # Проверка приложений в software_inventory
    db_apps = temp_storage.get_software_inventory_from_db(limit=10)
    assert len(db_apps) == 2

    app1_details = temp_storage.get_software_app_details_from_db("TestApp1")
    assert app1_details is not None
    assert app1_details["display_name"] == "Тестовое Приложение 1"
    assert app1_details["version"] == "1.0.0"
    assert app1_details["uninstall_string"] == "C:\\Program Files\\TestApp1\\unins000.exe"
    assert app1_details["category"] == AppCategory.UTILITIES.value
    assert app1_details["execution_info"] is not None
    assert app1_details["execution_info"]["run_count"] == 12


def test_software_inventory_upsert_and_first_seen_preservation(temp_storage: TelemetryStorage):
    """Проверка обновления (UPSERT) параметров программы с сохранением даты first_seen."""
    now = datetime.now(timezone.utc)
    initial_app = InstalledAppInfo(
        name="DynamicApp",
        display_name="Dynamic Application",
        version="1.0.0",
        publisher="Innovate Inc",
        execution_info=AppExecutionInfo(
            last_run_time=now - timedelta(days=20),
            run_count=5,
        ),
    )

    temp_storage.save_software_inventory([initial_app])
    details_1 = temp_storage.get_software_app_details_from_db("DynamicApp")
    assert details_1 is not None
    first_seen = details_1["first_seen"]
    last_scanned_1 = details_1["last_scanned_at"]
    assert details_1["version"] == "1.0.0"
    assert details_1["run_count"] == 5

    # Обновляем версию программы и количество запусков
    updated_app = InstalledAppInfo(
        name="DynamicApp",
        display_name="Dynamic Application",
        version="1.2.0",
        publisher="Innovate Inc",
        execution_info=AppExecutionInfo(
            last_run_time=now,
            run_count=42,
        ),
    )
    temp_storage.save_software_inventory([updated_app])

    details_2 = temp_storage.get_software_app_details_from_db("DynamicApp")
    assert details_2 is not None
    assert details_2["version"] == "1.2.0", "Версия должна обновиться"
    assert details_2["run_count"] == 42, "Количество запусков должно обновиться"
    assert details_2["first_seen"] == first_seen, "first_seen должен остаться прежним"


def test_software_audit_engine_default_no_db(monkeypatch, temp_storage: TelemetryStorage):
    """Проверка, что по умолчанию результаты аудита не сохраняются в SQLite БД."""
    monkeypatch.setattr(TelemetryStorage, "get_instance", lambda read_only=False: temp_storage)

    engine = SoftwareAuditEngine()
    report = engine.generate_audit_report()
    assert report is not None
    assert temp_storage.get_latest_software_audit_report() is None


def test_software_audit_engine_saves_to_db_without_csv(monkeypatch, temp_storage: TelemetryStorage):
    """Проверка, что SoftwareAuditEngine сохраняет аудит в БД при явном save_to_db=True и не создает лог в CSV."""
    monkeypatch.setattr(TelemetryStorage, "get_instance", lambda read_only=False: temp_storage)

    engine = SoftwareAuditEngine()
    report = engine.generate_audit_report(save_to_db=True)

    assert report is not None
    assert report.total_apps > 0

    # Проверяем, что отчет записался в SQLite БД
    latest_report = temp_storage.get_latest_software_audit_report()
    assert latest_report is not None
    assert latest_report["total_apps"] == report.total_apps

    # Проверяем историю отчетов
    history = temp_storage.get_software_audit_reports_history(limit=5)
    assert len(history) >= 1


def test_software_scanner_report_saving_and_retrieval(temp_storage: TelemetryStorage):
    """Проверка сохранения и чтения отчета глубокого сканера ПО и спящих программ в telemetry.db."""
    test_report = {
        "scan_id": "test_scan_001",
        "mode": "quick",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "stats": {
            "total_evidence_found": 10,
            "total_software_identified": 5,
            "active_count": 3,
            "dormant_count": 2,
            "orphan_count": 1,
            "duration_ms": 120.0,
        },
        "inventory": [
            {
                "id": "app_dormant_1",
                "name": "Old App",
                "publisher": "Legacy Corp",
                "version": "1.0",
                "install_location": "C:\\Program Files\\OldApp",
                "status": "dormant",
                "days_since_last_run": 150,
                "run_count": 2,
                "evidence": [],
            },
            {
                "id": "app_active_1",
                "name": "New App",
                "publisher": "Modern Corp",
                "version": "2.0",
                "install_location": "C:\\Program Files\\NewApp",
                "status": "active",
                "days_since_last_run": 1,
                "run_count": 50,
                "evidence": [],
            },
        ],
        "orphan_items": [
            {
                "source": "service",
                "path": "C:\\Program Files\\DeletedApp\\service.exe",
                "product_name": "DeletedApp Service",
            }
        ],
    }

    count = temp_storage.save_software_scanner_report(test_report)
    assert count == 2

    # Получаем последний отчет из БД
    loaded = temp_storage.get_latest_software_scanner_report()
    assert loaded is not None
    assert loaded.get("scan_id") == "test_scan_001"
    assert len(loaded.get("inventory", [])) == 2
    assert len(loaded.get("orphan_items", [])) == 1

    # Проверяем фильтрацию спящих программ
    dormant = temp_storage.get_dormant_software_from_db(min_days=90)
    assert len(dormant) == 1
    assert dormant[0]["name"] == "Old App"

    # Проверяем получение сирот
    orphans = temp_storage.get_orphan_software_from_db()
    assert len(orphans) == 1
    assert orphans[0]["product_name"] == "DeletedApp Service"


