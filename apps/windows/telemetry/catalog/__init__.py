# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry Catalog - Package Root
# =============================================================================
# Description:
#   Каталог событий Windows, реестр провайдеров и Sysmon слои.
#
# Usage Examples:
#   Python API:
#     from apps.windows.telemetry.catalog.event_catalog import WindowsEventCatalog
#
# File: __init__.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry.catalog
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 17:35:00
# =============================================================================

from __future__ import annotations
"""Каталог событийных журналов и реестр провайдеров ETW/Sysmon."""

from apps.windows.telemetry.catalog.event_catalog import WindowsEventCatalog

__all__ = [
    "WindowsEventCatalog",
]

