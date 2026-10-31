# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Core Tools -   Init  
# =============================================================================
# Description:
#   Пакет инструментов и реестра подсистемы Windows.
#
# Usage Examples:
#
#
# File: __init__.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.core.tools
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 18:56:00
# =============================================================================

"""Пакет инструментов и реестра подсистемы Windows."""

from apps.windows.sdk.core.tools.base import BaseTool, ToolExecutionResult
from apps.windows.sdk.core.tools.dynamic_factory import (
    CreateCustomToolMetaTool,
    DynamicSynthesizedTool,
    DynamicToolFactory,
    to_ascii_slug,
)
from apps.windows.sdk.core.tools.database_tool import (
    DatabaseInstrumentTool,
    register_database_instruments,
)
from apps.windows.sdk.core.tools.net_user_tool import NetUserTool
from apps.windows.sdk.core.tools.registry import ToolRegistry
from apps.windows.sdk.core.tools.system_tools import (
    SafePowerShellProbeTool,
    WindowsCollectorTool,
    register_system_tools,
)

__all__ = [
    'BaseTool',
    'ToolExecutionResult',
    'ToolRegistry',
    'WindowsCollectorTool',
    'SafePowerShellProbeTool',
    'NetUserTool',
    'register_system_tools',
    'DynamicToolFactory',
    'DynamicSynthesizedTool',
    'CreateCustomToolMetaTool',
    'to_ascii_slug',
    'DatabaseInstrumentTool',
    'register_database_instruments',
]
