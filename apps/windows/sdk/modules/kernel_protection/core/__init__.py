# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Modules Kernel Protection Core - Init
# =============================================================================
# Description:
#   Инициализатор ядра модуля защиты ядра, системных драйверов и анализа блокировок.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.kernel_protection.core import (
#         DriverInventoryManager,
#         ProtectionMechanismsAuditor,
#         OperationBlockerDetector,
#         KernelSafeOpsManager,
#     )
#
# File: __init__.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.kernel_protection.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 14:40:00
# =============================================================================

from __future__ import annotations
"""Ядро подсистемы Kernel Protection & Driver Management."""

from apps.windows.sdk.modules.kernel_protection.core.blocker_detector import OperationBlockerDetector
from apps.windows.sdk.modules.kernel_protection.core.driver_inventory import DriverInventoryManager
from apps.windows.sdk.modules.kernel_protection.core.models import (
    BlockerCulpritType,
    BlockerFinding,
    BlockerInvestigationRequest,
    BlockerTargetType,
    BlockerVerdict,
    ComponentCriticality,
    DriverCategory,
    KernelProtectionReport,
    MinifilterInfo,
    ProtectionMechanismStatus,
    SafeOpsActionRequest,
    SafeOpsActionResult,
    SystemDriverInfo,
)
from apps.windows.sdk.modules.kernel_protection.core.protection_mechanisms import ProtectionMechanismsAuditor
from apps.windows.sdk.modules.kernel_protection.core.safe_ops import KernelSafeOpsManager
from apps.windows.sdk.modules.kernel_protection.core.ucpd_manager import (
    TaskbarDaExperimentResult,
    UcpdDriverState,
    UcpdFullStatus,
    UcpdRebootStatus,
    UcpdSetStateRequest,
    UcpdSetStateResponse,
    UcpdSystemManager,
    UcpdTaskState,
)

__all__ = [
    'DriverInventoryManager',
    'ProtectionMechanismsAuditor',
    'OperationBlockerDetector',
    'KernelSafeOpsManager',
    'UcpdSystemManager',
    'UcpdFullStatus',
    'UcpdDriverState',
    'UcpdTaskState',
    'UcpdRebootStatus',
    'UcpdSetStateRequest',
    'UcpdSetStateResponse',
    'TaskbarDaExperimentResult',
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
]
