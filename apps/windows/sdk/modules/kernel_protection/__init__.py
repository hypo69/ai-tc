# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Modules Kernel Protection - Init
# =============================================================================
# Description:
#   Пакет управления и диагностики драйверов ядра Windows, файловых минифильтров
#   и механизмов системной защиты (Kernel & Protection Manager).
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.kernel_protection import (
#         DriverInventoryManager,
#         OperationBlockerDetector,
#         ProtectionMechanismsAuditor,
#         KernelSafeOpsManager,
#         router,
#     )
#
# File: __init__.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.kernel_protection
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 14:40:00
# =============================================================================

from __future__ import annotations
"""Модуль управления драйверами ядра и механизмами защиты Windows."""

from apps.windows.sdk.modules.kernel_protection.core import (
    BlockerCulpritType,
    BlockerFinding,
    BlockerInvestigationRequest,
    BlockerTargetType,
    BlockerVerdict,
    ComponentCriticality,
    DriverCategory,
    DriverInventoryManager,
    KernelProtectionReport,
    KernelSafeOpsManager,
    MinifilterInfo,
    OperationBlockerDetector,
    ProtectionMechanismStatus,
    ProtectionMechanismsAuditor,
    SafeOpsActionRequest,
    SafeOpsActionResult,
    SystemDriverInfo,
)
from apps.windows.sdk.modules.kernel_protection.router import init_router, router

__all__ = [
    'DriverInventoryManager',
    'ProtectionMechanismsAuditor',
    'OperationBlockerDetector',
    'KernelSafeOpsManager',
    'DriverCategory',
    'ComponentCriticality',
    'SystemDriverInfo',
    'MinifilterInfo',
    'ProtectionMechanismStatus',
    'BlockerTargetType',
    'BlockerCulpritType',
    'BlockerFinding',
    'BlockerInvestigationRequest',
    'BlockerVerdict',
    'SafeOpsActionRequest',
    'SafeOpsActionResult',
    'KernelProtectionReport',
    'router',
    'init_router',
]
