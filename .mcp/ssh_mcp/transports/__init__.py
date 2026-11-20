# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Инициализация пакета транспортов (transports)
# =============================================================================
# Description:
#   Экспорт базового интерфейса и реализаций транспортов SSH, SFTP, Local и
#   Remote MCP.
#
# File: __init__.py
# Project: ai-tc (ai-tc)
# Package: ssh_mcp.transports
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 05:00:00
# =============================================================================

from .base import BaseTransport, RawExecutionResult
from .local_transport import LocalTransport, build_safe_shell_invocation
from .remote_mcp_transport import RemoteMCPTransport
from .sftp_transport import SFTPFileManager
from .ssh_transport import AsyncSSHTransport

__all__ = [
    "AsyncSSHTransport",
    "BaseTransport",
    "LocalTransport",
    "RawExecutionResult",
    "RemoteMCPTransport",
    "SFTPFileManager",
    "build_safe_shell_invocation",
]
