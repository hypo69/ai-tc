# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Forensics Module - Init
# =============================================================================
# Description:
#   Пакет цифровой криминалистики (Digital Forensics) AI-TC:
#   - Acquisition Layer: сбор артефактов (Prefetch, UserAssist, USBSTOR, EventLogs)
#   - Analysis Layer: супер-таймлайн, корреляция и Chain of Custody (SHA-256)
#   - Intelligence Layer: инцидентные расследования и реконструкция сбоев
#
# Usage Examples:
#   from apps.windows.sdk.modules.forensics import (
#       ForensicAcquisitionEngine,
#       ForensicAnalysisEngine,
#       ForensicIntelligenceEngine,
#   )
#
# File: __init__.py
# Project: ai-tc
# Package: apps.windows.sdk.modules.forensics
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 12:45:00
# =============================================================================

from __future__ import annotations
"""Пакет цифровой криминалистики (Digital Forensics) Windows в AI-TC."""

from .acquisition import ForensicAcquisitionEngine, compute_sha256
from .analysis import ForensicAnalysisEngine
from .intelligence import ForensicIntelligenceEngine
from .models import (
    ChainOfCustodyRecord,
    ExecutionArtifact,
    ForensicSuperTimelineItem,
    IncidentInvestigationReport,
    IncidentInvestigationRequest,
    RebootIncident,
    SecurityLogonEvidence,
    UsbEvidence,
)

__all__ = [
    "ForensicAcquisitionEngine",
    "ForensicAnalysisEngine",
    "ForensicIntelligenceEngine",
    "compute_sha256",
    "ExecutionArtifact",
    "UsbEvidence",
    "RebootIncident",
    "SecurityLogonEvidence",
    "ChainOfCustodyRecord",
    "ForensicSuperTimelineItem",
    "IncidentInvestigationRequest",
    "IncidentInvestigationReport",
]
