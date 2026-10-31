# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows SDK - Tool Chains Package
# =============================================================================
# Description:
#   Пакет оркестрации и исполнения цепочек инструментов агентом Windows.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.core.tool_chains import ToolChainExecutionEngine, ToolChainPlanner
#
# File: __init__.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.core.tool_chains
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 17:35:00
# =============================================================================

from __future__ import annotations

"""Пакет построения, семантического планирования и исполнения цепочек инструментов."""

from apps.windows.sdk.core.tool_chains.models import (
    BranchCondition,
    ChainDefinition,
    ChainRunReport,
    ChainRunStatus,
    ChainStepDefinition,
    CompensationAction,
    ConditionOperator,
    StepExecutionResult,
    StepRunStatus,
)
from apps.windows.sdk.core.tool_chains.catalog import get_builtin_chains
from apps.windows.sdk.core.tool_chains.storage import ToolChainStorage
from apps.windows.sdk.core.tool_chains.planner import ToolChainPlanner
from apps.windows.sdk.core.tool_chains.engine import ToolChainExecutionEngine
from apps.windows.sdk.core.tool_chains.router import router

__all__ = [
    "BranchCondition",
    "ChainDefinition",
    "ChainRunReport",
    "ChainRunStatus",
    "ChainStepDefinition",
    "CompensationAction",
    "ConditionOperator",
    "StepExecutionResult",
    "StepRunStatus",
    "get_builtin_chains",
    "ToolChainStorage",
    "ToolChainPlanner",
    "ToolChainExecutionEngine",
    "router",
]

