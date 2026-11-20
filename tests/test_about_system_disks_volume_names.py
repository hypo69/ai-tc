# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Tests - Test About System Disks Volume Names
# =============================================================================
# Description:
#   Модульные тесты проверки обогащения дисков и томов пользовательскими
#   именами (метками томов, volume_name) на панели «О системе» (About System).
#
# File: test_about_system_disks_volume_names.py
# Project: ai-tc
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 12:40:00
# =============================================================================

from __future__ import annotations
"""Тесты валидации отображения имен дисков и меток томов в таблицах вкладки 'О системе'."""

import os
from pathlib import Path
import pytest

from apps.windows.api.routers.about_system.helpers import get_windows_volume_labels
from apps.windows.api.routers.about_system.query_summary import query_system_summary_full
from apps.windows.api.routers.about_system.query_diagnostics import query_disks_wear_from_db
from apps.windows.api.routers.about_system.query_about import query_about_system_from_db
from apps.windows.telemetry.sqlite import TelemetryStorage


def test_get_windows_volume_labels() -> None:
    """Проверяет получение словаря меток дисковых томов."""
    labels = get_windows_volume_labels()
    assert isinstance(labels, dict)
    if os.name == "nt":
        # На любой рабочей Windows-машине должен быть хотя бы диск C:
        assert "C:" in labels
        assert isinstance(labels["C:"], str)
        assert len(labels["C:"]) > 0


@pytest.mark.asyncio
async def test_summary_disks_contain_volume_names() -> None:
    """Проверяет, что каждый логический диск в сводке системы содержит имя тома."""
    storage = TelemetryStorage.get_instance(read_only=True)
    summary = await query_system_summary_full(storage)

    disks = summary.get("disks", [])
    assert isinstance(disks, list)
    assert len(disks) > 0

    c_disk = next((d for d in disks if str(d.get("device", "")).upper().startswith("C")), None)
    assert c_disk is not None
    assert c_disk.get("volume_name") is not None
    assert len(c_disk["volume_name"]) > 0


def test_disks_wear_partitions_contain_volume_names() -> None:
    """Проверяет, что колонка разделов и физические диски в disks_wear содержат имена томов."""
    storage = TelemetryStorage.get_instance(read_only=True)
    wear_data = query_disks_wear_from_db(storage)

    assert wear_data.get("status") == "ok"
    disks_wear = wear_data.get("disks_wear", [])
    assert isinstance(disks_wear, list)
    assert len(disks_wear) > 0

    # Проверяем, что хотя бы у системного диска раздел обогащен именем тома
    has_enriched_partition = False
    for d in disks_wear:
        parts = str(d.get("partitions") or "")
        if "C:" in parts and ("(" in parts or d.get("volume_name")):
            has_enriched_partition = True
            break
    assert has_enriched_partition is True


def test_kpi_storage_contains_volume_name() -> None:
    """Проверяет, что KPI-карточка системного накопителя C: содержит метку тома."""
    storage = TelemetryStorage.get_instance(read_only=True)
    overview = query_about_system_from_db(storage)

    assert overview.storage is not None
    assert overview.storage.volume_name is not None
    assert len(overview.storage.volume_name) > 0
    assert overview.storage.volume_name in overview.storage.drive


def test_frontend_js_renders_volume_name() -> None:
    """Проверяет наличие логики отображения имен томов во фронтенд-модулях."""
    hw_panel_js = Path("apps/windows/api/webgui/tab_about_system/panel_hardware/panel.js").read_text(encoding="utf-8")
    assert "cleanVol" in hw_panel_js
    assert "nameDisplay" in hw_panel_js
    assert "letterDisplay" in hw_panel_js

    ident_panel_js = Path("apps/windows/api/webgui/tab_about_system/panel_identity/panel.js").read_text(encoding="utf-8")
    assert "volBadge" in ident_panel_js or "volume_name" in ident_panel_js
    assert "partsHtml" in ident_panel_js
