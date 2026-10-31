# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry Sqlite - Schema Inventory
# =============================================================================
# Description:
#   DDL-определения инвентаризации и истории изменений оборудования (2 из 12 таблиц):
#   hardware_components, hardware_component_history.
#
# File: schema_inventory.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry.sqlite
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-16 12:55:00
# =============================================================================

from __future__ import annotations

"""DDL-определения единого реестра аппаратных компонентов и истории модернизации железа."""

from typing import Tuple

INVENTORY_SCHEMA_DDL: Tuple[str, ...] = (
    # 4. Единый реестр аппаратных компонентов (CPU, RAM, GPU, Диски, Тома, Сеть, PnP, Аудиты)
    '''
    CREATE TABLE IF NOT EXISTS hardware_components (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        component_key TEXT NOT NULL,
        name TEXT,
        vendor TEXT,
        model TEXT,
        serial_number TEXT,
        status TEXT,
        health_status TEXT,
        temperature_c REAL,
        capacity_bytes INTEGER,
        free_bytes INTEGER,
        first_seen TEXT NOT NULL,
        last_seen TEXT NOT NULL,
        updated_at REAL NOT NULL,
        specs_json TEXT NOT NULL DEFAULT '{}',
        raw_json TEXT,
        UNIQUE(category, component_key)
    );
    ''',
    # 5. Персистентный журнал изменений конфигурации оборудования («было / стало»)
    '''
    CREATE TABLE IF NOT EXISTS hardware_component_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        created_at REAL NOT NULL,
        component_type TEXT NOT NULL,
        change_type TEXT NOT NULL,
        component_name TEXT NOT NULL,
        old_config_json TEXT,
        new_config_json TEXT,
        summary TEXT NOT NULL
    );
    ''',
)

INVENTORY_INDEX_DDL: Tuple[str, ...] = (
    'CREATE INDEX IF NOT EXISTS idx_hw_comp_cat_updated ON hardware_components(category, updated_at DESC);',
    'CREATE INDEX IF NOT EXISTS idx_hw_comp_status ON hardware_components(category, status);',
    'CREATE INDEX IF NOT EXISTS idx_hw_hist_created ON hardware_component_history(created_at DESC);',
    'CREATE INDEX IF NOT EXISTS idx_hw_hist_type ON hardware_component_history(component_type, created_at DESC);',
)

