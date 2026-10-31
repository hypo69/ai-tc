# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Modules Software_Manager -   Init  
# =============================================================================
# Description:
#   # Description:
#
# Usage Examples:
#
#
# File: __init__.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.software_manager
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 17:35:00
# =============================================================================

"""# Description:"""

from apps.windows.sdk.modules.software_manager.core.manager import SoftwarePackagesManager
from apps.windows.sdk.modules.software_manager.core.models import (
    InstalledPackage,
    PackageActionRequest,
    SoftwareReport,
)
from apps.windows.sdk.modules.software_manager.router import init_router
from apps.windows.sdk.modules.software_manager.tui import SoftwareManagerTUI

__all__ = [
    'SoftwarePackagesManager',
    'SoftwareManagerTUI',
    'init_router',
    'InstalledPackage',
    'PackageActionRequest',
    'SoftwareReport',
]

