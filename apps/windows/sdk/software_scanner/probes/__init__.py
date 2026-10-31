# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Software Scanner - Probes Package
# =============================================================================
# Description:
#   Пакет специализированных зондов сбора данных для Deep Software Scanner.
#
# File: __init__.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.software_scanner.probes
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 19:20:00
# =============================================================================

from __future__ import annotations
"""Пакет специализированных зондов (probes) сбора следов программ."""

from apps.windows.sdk.software_scanner.probes.registry_probe import RegistryProbe
from apps.windows.sdk.software_scanner.probes.filesystem_probe import FilesystemProbe
from apps.windows.sdk.software_scanner.probes.services_probe import ServicesProbe
from apps.windows.sdk.software_scanner.probes.tasks_probe import TasksProbe
from apps.windows.sdk.software_scanner.probes.packages_probe import PackagesProbe
from apps.windows.sdk.software_scanner.probes.execution_evidence import ExecutionEvidenceProbe

__all__ = [
    "RegistryProbe",
    "FilesystemProbe",
    "ServicesProbe",
    "TasksProbe",
    "PackagesProbe",
    "ExecutionEvidenceProbe",
]

