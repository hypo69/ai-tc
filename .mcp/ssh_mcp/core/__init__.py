# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Инициализация пакета ядра управления (ssh-mcp-core)
# =============================================================================
# Description:
#   Экспорт всех сервисов уровня управления (Management Layer):
#   ConnectionManager, CommandRegistry, ExecutionEngine, TaskManager,
#   PermissionManager, ApprovalManager и ResultNormalizer.
#
# File: __init__.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:51:15
# =============================================================================

from .approval_manager import ApprovalManager, ApprovalRequiredException
from .command_registry import CommandRegistry, CommandValidationError
from .connection_manager import ConnectionManager
from .execution_engine import ExecutionEngine
from .permission_manager import PermissionManager
from .result_normalizer import ResultNormalizer
from .task_manager import TaskManager

__all__ = [
    "ApprovalManager",
    "ApprovalRequiredException",
    "CommandRegistry",
    "CommandValidationError",
    "ConnectionManager",
    "ExecutionEngine",
    "PermissionManager",
    "ResultNormalizer",
    "TaskManager",
]
