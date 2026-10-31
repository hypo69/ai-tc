# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - Router Storage
# =============================================================================
# Description:
#   Алиас-роутер параметров хранилища и накопителей (SMART 190 / 194).
#   Соответствует ТЗ v3 пункт 7 (считывание показателей SMART-температуры).
#
# Usage Examples:
#   Python API:
#     from apps.windows.api.routers.router_storage import init_router
#     app.include_router(init_router())
#
# File: router_storage.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-13 15:46:00
# =============================================================================

from __future__ import annotations
"""Алиас-роутер накопителей и SMART параметров хранилища."""

from apps.windows.api.routers.router_storage_load import (
    DiskDriveMetric,
    DiskPartitionMetric,
    StorageSummary,
    StorageLoadResponse,
    _detect_media_type,
    _find_matching_key,
    extract_smart_temperature,
    build_storage_load,
    init_router,
)

__all__ = [
    "DiskDriveMetric",
    "DiskPartitionMetric",
    "StorageSummary",
    "StorageLoadResponse",
    "_detect_media_type",
    "_find_matching_key",
    "extract_smart_temperature",
    "build_storage_load",
    "init_router",
]

