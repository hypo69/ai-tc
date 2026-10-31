# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Инициализация пакета MCP-инструментов (mcp_tools)
# =============================================================================
# Description:
#   Централизованная регистрация всех 10 функциональных модулей (72 инструмента)
#   в экземпляре MCPServer v2.
#
# File: __init__.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.mcp_tools
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 17:00:30
# =============================================================================

from typing import Dict
from mcp.server import MCPServer
from ..bootstrap import SSHMCPRuntime
from .connection import ConnectionToolsModule, register_connection_tools
from .diagnostics import DiagnosticsToolsModule, register_diagnostics_tools
from .execution import ExecutionToolsModule, register_execution_tools
from .filesystem import FilesystemToolsModule, register_filesystem_tools
from .logs import LogsToolsModule, register_logs_tools
from .network import NetworkToolsModule, register_network_tools
from .processes import ProcessToolsModule, register_process_tools
from .services import ServiceToolsModule, register_service_tools
from .system import SystemToolsModule, register_system_tools
from .users import UserToolsModule, register_user_tools


def register_all_tools(mcp: MCPServer, runtime: SSHMCPRuntime) -> Dict[str, object]:
    """Регистрация всех 10 функциональных групп инструментов в MCPServer.

    Args:
        mcp (MCPServer): Экземпляр MCPServer v2.
        runtime (SSHMCPRuntime): Контейнер сервисов ядра.

    Returns:
        Dict[str, object]: Словарь инициализированных модулей инструментов.

    Examples:
        >>> from mcp.server import MCPServer
        >>> from ssh_mcp.bootstrap import create_runtime
        >>> srv = MCPServer("test")
        >>> mods = register_all_tools(srv, create_runtime(db_path=":memory:"))
        >>> len(mods)
        10
    """
    return {
        "connection": register_connection_tools(mcp, runtime),
        "execution": register_execution_tools(mcp, runtime),
        "system": register_system_tools(mcp, runtime),
        "processes": register_process_tools(mcp, runtime),
        "services": register_service_tools(mcp, runtime),
        "filesystem": register_filesystem_tools(mcp, runtime),
        "network": register_network_tools(mcp, runtime),
        "users": register_user_tools(mcp, runtime),
        "logs": register_logs_tools(mcp, runtime),
        "diagnostics": register_diagnostics_tools(mcp, runtime),
    }


__all__ = [
    "ConnectionToolsModule",
    "DiagnosticsToolsModule",
    "ExecutionToolsModule",
    "FilesystemToolsModule",
    "LogsToolsModule",
    "NetworkToolsModule",
    "ProcessToolsModule",
    "ServiceToolsModule",
    "SystemToolsModule",
    "UserToolsModule",
    "register_all_tools",
]
