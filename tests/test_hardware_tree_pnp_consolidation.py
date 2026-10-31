# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Hardware Tree PnP Consolidation
# =============================================================================
# Description:
#   Модульные тесты для проверки консолидации множественных PnP-устройств
#   (pnp_device) в единую группу «Устройства PnP» в иерархическом дереве оборудования.
#
# File: test_hardware_tree_pnp_consolidation.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Updated: 2026-10-18 08:15:00
# =============================================================================

from unittest.mock import MagicMock
import pytest

from apps.windows.api.routers.about_system.query_diagnostics import (
    _get_hardware_category_priority,
    query_hardware_tree_from_db,
)


def test_hardware_category_priority_for_pnp() -> None:
    """Проверяет приоритет сортировки для категории Устройства PnP."""
    assert _get_hardware_category_priority("Устройства PnP") == 170
    assert _get_hardware_category_priority("pnp_device") == 170
    assert _get_hardware_category_priority("Plug & Play") == 170


def test_query_hardware_tree_consolidates_pnp_devices() -> None:
    """Проверяет, что компоненты с категорией pnp_device объединяются в единую группу."""
    mock_storage = MagicMock()
    mock_storage.get_hardware_components.return_value = [
        {
            "category": "Processor (CPU)",
            "name": "Intel Core i5-10400",
            "properties_json": {"Ядер": 6},
        },
        {
            "category": "pnp_device",
            "name": "VB-Audio Virtual Cable",
            "component_key": "ROOT\\MEDIA\\0000",
            "model": "MEDIA",
            "vendor": "VB-Audio",
            "status": "OK",
            "specs_json": '{"device_id": "ROOT\\\\MEDIA\\\\0000", "device_class": "MEDIA"}',
        },
        {
            "category": "pnp_device",
            "name": "HP LaserJet Printer",
            "component_key": "SWD\\PRINTENUM\\1234",
            "model": "Printer",
            "vendor": "HP",
            "status": "OK",
            "specs_json": '{"device_id": "SWD\\\\PRINTENUM\\\\1234", "device_class": "Printer"}',
        },
        {
            "category": "pnp_device",
            "name": "Problematic Device",
            "component_key": "PCI\\VEN_9999",
            "model": "System",
            "vendor": "Vendor",
            "status": "Problem",
            "specs_json": '{"device_id": "PCI\\\\VEN_9999", "device_class": "System", "status": "Problem"}',
        },
    ]

    result = query_hardware_tree_from_db(mock_storage)

    # Должно быть ровно 2 узла: Процессор и консолидированные Устройства PnP
    assert len(result) == 2
    categories = [node["category"] for node in result]
    assert categories == ["Processor (CPU)", "Устройства PnP"]

    pnp_node = result[1]
    assert pnp_node["name"] == "Plug and Play (3 устройств)"
    assert pnp_node["is_pnp_group"] is True
    assert len(pnp_node["devices"]) == 3
    assert pnp_node["properties"]["Всего PnP-устройств"] == "3 шт."
    assert "1 с предупреждениями" in pnp_node["properties"]["Состояние"]

