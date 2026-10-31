# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Инициализация пакета схем данных SSH MCP Server
# =============================================================================
# Description:
#   Экспорт всех моделей данных Pydantic для удобного импорта компонентами ядра.
#
# File: __init__.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.schemas
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:37:45
# =============================================================================

from .command import CommandDefinition, ParameterSpec
from .diagnostics import DiagnosticPackage
from .execution import ErrorDetail, ExecutionMetrics, StandardMCPResponse, TaskRecord
from .host import ConnectionInfo, HostConfig

__all__ = [
    "CommandDefinition",
    "ConnectionInfo",
    "DiagnosticPackage",
    "ErrorDetail",
    "ExecutionMetrics",
    "HostConfig",
    "ParameterSpec",
    "StandardMCPResponse",
    "TaskRecord",
]
