# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Apps Windows Modules System_Checkpoints Core -   Init  
# =============================================================================
# Description:
#   Ядро управления контрольными точками и средами восстановления Windows.
#
# Usage Examples:
#
#
# File: __init__.py
# Project: ai-tc
# Package: apps.windows.sdk.modules.system_checkpoints.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 05:00:00
# =============================================================================

"""Ядро управления контрольными точками и средами восстановления Windows."""

from apps.windows.system_checkpoints.core.winre_manager import WinREManager
from apps.windows.system_checkpoints.core.image_manager import SystemImageManager
from apps.windows.system_checkpoints.core.freshness_auditor import FreshnessAuditor
from apps.windows.system_checkpoints.core.checkpoint_coordinator import CheckpointCoordinator

__all__ = [
    "WinREManager",
    "SystemImageManager",
    "FreshnessAuditor",
    "CheckpointCoordinator",
]

