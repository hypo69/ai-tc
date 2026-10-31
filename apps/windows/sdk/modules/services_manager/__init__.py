# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Modules Services_Manager -   Init  
# =============================================================================
# Description:
#   # Description:
#
# Usage Examples:
#
#
# File: __init__.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.services_manager
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 17:35:00
# =============================================================================

"""# Description:"""

from apps.windows.sdk.modules.services_manager.core.manager import ServicesManager
from apps.windows.sdk.modules.services_manager.core.models import (
    ServiceActionRequest,
    ServiceItem,
    ServicesReport,
)
from apps.windows.sdk.modules.services_manager.router import init_router
from apps.windows.sdk.modules.services_manager.tui import ServicesManagerTUI

__all__ = [
    'ServicesManager',
    'ServicesManagerTUI',
    'init_router',
    'ServiceItem',
    'ServicesReport',
    'ServiceActionRequest',
]

