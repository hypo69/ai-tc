# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Modules Sysadmin -   Init  
# =============================================================================
# Description:
#   Windows System Administrator application package.
#
# Usage Examples:
#
#
# File: __init__.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.sysadmin
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 17:35:00
# =============================================================================

"""Windows System Administrator application package."""

from .router import init_router
from .src.state import SystemAdminState, UserSession, SecurityEvent
from .tui import run_sysadmin_dashboard
__all__ = ['init_router', 'SystemAdminState', 'UserSession', 'SecurityEvent', 'run_sysadmin_dashboard']
