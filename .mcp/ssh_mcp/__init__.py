# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Корневой пакет универсального сервера SSH MCP Server
# =============================================================================
# Description:
#   Экспорт основных публичных компонентов системы удалённого администрирования
#   Windows и Linux по протоколам SSH и Model Context Protocol (MCP v2).
#
# File: __init__.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 17:02:30
# =============================================================================

from .bootstrap import SSHMCPRuntime, create_runtime
from .client import SSHMCPClient
from .config import AppSettings, load_settings
from .server import build_mcp_server, build_remote_http_app

__all__ = [
    "AppSettings",
    "SSHMCPClient",
    "SSHMCPRuntime",
    "build_mcp_server",
    "build_remote_http_app",
    "create_runtime",
    "load_settings",
]
