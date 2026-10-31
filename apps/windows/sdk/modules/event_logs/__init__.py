# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Modules Event_Logs -   Init  
# =============================================================================
# Description:
#   # Description:
#
# Usage Examples:
#
#
# File: __init__.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.event_logs
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 17:35:00
# =============================================================================

"""# Description:"""

from apps.windows.sdk.modules.event_logs.core.manager import EventLogsManager
from apps.windows.sdk.modules.event_logs.core.models import (
    EventLogActionRequest,
    EventLogChannel,
    EventLogEntry,
    EventLogReport,
)
from apps.windows.sdk.modules.event_logs.router import init_router
from apps.windows.sdk.modules.event_logs.tui import EventLogsTUI

__all__ = [
    'EventLogsManager',
    'EventLogsTUI',
    'init_router',
    'EventLogChannel',
    'EventLogEntry',
    'EventLogReport',
    'EventLogActionRequest',
]

