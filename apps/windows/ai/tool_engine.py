# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows AI - Tool Engine
# =============================================================================
# Description:
#   Динамический генератор и исполнитель системных инструментов и фабрика навыков ИИ.
#
# Usage Examples:
#   Python API:
#     from apps.windows.ai.tool_engine import DynamicToolPlan, DynamicToolFactory
#
# File: tool_engine.py
# Project: ai-windows-admin
# Package: apps.windows.ai
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 17:35:00
# =============================================================================

from __future__ import annotations
"""Динамический генератор инструментов и исполнитель навыков ИИ для Windows."""

from apps.windows.sdk.core.dynamic_tool_engine import (
    DynamicToolPlan,
    lookup_vendor,
    CreateCustomToolMetaTool,
    DynamicSynthesizedTool,
    DynamicToolFactory,
    to_ascii_slug,
    ToolRegistry,
    SafePowerShellProbeTool,
    WindowsCollectorTool,
    register_system_tools,
)

__all__ = [
    "DynamicToolPlan",
    "lookup_vendor",
    "CreateCustomToolMetaTool",
    "DynamicSynthesizedTool",
    "DynamicToolFactory",
    "to_ascii_slug",
    "ToolRegistry",
    "SafePowerShellProbeTool",
    "WindowsCollectorTool",
    "register_system_tools",
]

