# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Modules Process_Manager -   Init  
# =============================================================================
# Description:
#   # Description:
#
# Usage Examples:
#
#
# File: __init__.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.process_manager
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 00:59:00
# =============================================================================

"""Модуль управления процессами, глубокого аудита и отслеживания жизненного цикла Windows."""

from apps.windows.sdk.modules.process_manager.core.manager import ProcessManager
from apps.windows.sdk.modules.process_manager.core.models import (
    ProcessItem,
    ProcessKillRequest,
    ProcessReport,
)
from apps.windows.sdk.modules.process_manager.core.process_auditor import (
    ProcessAuditor,
    ProcessAuditSample,
    ProcessCpuAudit,
    ProcessIoAudit,
    ProcessMemoryAudit,
    ProcessNetworkAudit,
)
from apps.windows.sdk.modules.process_manager.core.lifecycle_tracker import (
    ProcessLifecycleDelta,
    ProcessLifecycleTracker,
    ProcessSessionRecord,
)
from apps.windows.sdk.modules.process_manager.core.correlation_engine import (
    IncidentEvent,
    IncidentTimeline,
    IncidentTimelineBuilder,
)
from apps.windows.sdk.modules.process_manager.router import init_router
from apps.windows.sdk.modules.process_manager.tui import ProcessManagerTUI

__all__ = [
    'ProcessManager',
    'ProcessManagerTUI',
    'ProcessAuditor',
    'ProcessAuditSample',
    'ProcessCpuAudit',
    'ProcessMemoryAudit',
    'ProcessIoAudit',
    'ProcessNetworkAudit',
    'ProcessSessionRecord',
    'ProcessLifecycleDelta',
    'ProcessLifecycleTracker',
    'IncidentEvent',
    'IncidentTimeline',
    'IncidentTimelineBuilder',
    'init_router',
    'ProcessItem',
    'ProcessReport',
    'ProcessKillRequest',
]

