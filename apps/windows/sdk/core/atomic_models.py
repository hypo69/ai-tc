# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Core - Atomic Models
# =============================================================================
# Description:
#   Модели атомарных операций Windows (Фасад contracts).
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.core.atomic_models import AtomicOperation, CapabilityCategory
#
# File: atomic_models.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 17:35:00
# =============================================================================

from __future__ import annotations
"""Модели атомарных операций и категорий возможностей Windows."""

from apps.windows.contracts.enums import (
    RiskLevel,
    PrivilegeLevel,
    ExecutionMethod,
    HttpMethod,
    CapabilityCategory,
)
from apps.windows.contracts.audit import (
    AtomicOperation,
    ExecutionRequest,
    ExecutionResult,
    AtomicOperationExecutionRequest,
    AtomicOperationExecutionResult,
)

__all__ = [
    "RiskLevel",
    "PrivilegeLevel",
    "ExecutionMethod",
    "HttpMethod",
    "CapabilityCategory",
    "AtomicOperation",
    "ExecutionRequest",
    "ExecutionResult",
    "AtomicOperationExecutionRequest",
    "AtomicOperationExecutionResult",
]

