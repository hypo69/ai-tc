# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Apps Windows Telemetry Sqlite - Schema Storage
# =============================================================================
# Description:
#   DDL-модуль дисковой подсистемы (консолидирован в hardware_components,
#   sensor_polls, system_snapshots и process_file_events).
#
# File: schema_storage.py
# Project: ai-tc
# Package: apps.windows.telemetry.sqlite
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 05:00:00
# =============================================================================

from __future__ import annotations

"""Консолидированные DDL-кортежи дисковой подсистемы (данные хранятся в 12 базовых таблицах)."""

from typing import Tuple

STORAGE_SCHEMA_DDL: Tuple[str, ...] = ()

STORAGE_INDEX_DDL: Tuple[str, ...] = ()

