# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Modules System_Checkpoints -   Init  
# =============================================================================
# Description:
#   Пакет управления контрольными точками системы и образами восстановления Windows.
#
# Usage Examples:
#
#
# File: __init__.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.system_checkpoints
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-16 22:21:00
# =============================================================================

"""Пакет управления контрольными точками системы и образами восстановления Windows."""

from apps.windows.system_checkpoints.models import (
    AdvisorDecision,
    AdvisorEvaluationResult,
    AdvisorTrigger,
    CategoryDelta,
    CategoryFingerprint,
    CategoryImportance,
    CheckpointCreateRequest,
    CheckpointType,
    FreshnessLevel,
    FreshnessReport,
    RecoveryMechanism,
    SmartRestorePointCreateRequest,
    SystemCheckpointRecord,
    SystemDriftMetrics,
    SystemImageMetadata,
    WimImageCreateRequest,
    WinREActionRequest,
    WinREStatus,
)
from apps.windows.system_checkpoints.core.winre_manager import WinREManager
from apps.windows.system_checkpoints.core.image_manager import SystemImageManager
from apps.windows.system_checkpoints.core.freshness_auditor import FreshnessAuditor
from apps.windows.system_checkpoints.core.checkpoint_coordinator import CheckpointCoordinator
from apps.windows.system_checkpoints.core.restore_point_advisor import (
    RestorePointAdvisor,
    RestorePointStateJournal,
    get_default_state_journal_db_path,
)
from apps.windows.system_checkpoints.router import router, init_router

__all__ = [
    "CheckpointType",
    "RecoveryMechanism",
    "FreshnessLevel",
    "SystemDriftMetrics",
    "FreshnessReport",
    "WinREStatus",
    "SystemImageMetadata",
    "SystemCheckpointRecord",
    "CheckpointCreateRequest",
    "WimImageCreateRequest",
    "WinREActionRequest",
    "AdvisorDecision",
    "AdvisorEvaluationResult",
    "AdvisorTrigger",
    "CategoryDelta",
    "CategoryFingerprint",
    "CategoryImportance",
    "SmartRestorePointCreateRequest",
    "WinREManager",
    "SystemImageManager",
    "FreshnessAuditor",
    "CheckpointCoordinator",
    "RestorePointAdvisor",
    "RestorePointStateJournal",
    "get_default_state_journal_db_path",
    "router",
    "init_router",
]

