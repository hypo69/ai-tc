# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Software Scanner - Root Package
# =============================================================================
# Description:
#   Комплексный пакет глубокого сканирования установленного и спящего ПО,
#   остатков удаленных программ, артефактов запусков и системных регистраций.
#
# File: __init__.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.software_scanner
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 19:20:00
# =============================================================================

from __future__ import annotations
"""Комплексный пакет Deep Software Scanner для Windows SDK."""

from apps.windows.sdk.software_scanner.models import (
    ScanMode,
    EvidenceType,
    SoftwareStatus,
    ConfidenceLevel,
    EvidenceItem,
    SoftwareInventoryCard,
    ScanErrorItem,
    ScanStats,
    ScanReport,
)
from apps.windows.sdk.software_scanner.policies import ScannerPolicy
from apps.windows.sdk.software_scanner.scope import ScannerScope
from apps.windows.sdk.software_scanner.metadata_extractor import PEMetadataExtractor
from apps.windows.sdk.software_scanner.orphan_detector import OrphanDetector
from apps.windows.sdk.software_scanner.correlator import EvidenceCorrelator
from apps.windows.sdk.software_scanner.controller import DeepSoftwareScanner
from apps.windows.sdk.software_scanner.report import ReportFormatter
from apps.windows.sdk.software_scanner.router import router

__all__ = [
    "ScanMode",
    "EvidenceType",
    "SoftwareStatus",
    "ConfidenceLevel",
    "EvidenceItem",
    "SoftwareInventoryCard",
    "ScanErrorItem",
    "ScanStats",
    "ScanReport",
    "ScannerPolicy",
    "ScannerScope",
    "PEMetadataExtractor",
    "OrphanDetector",
    "EvidenceCorrelator",
    "DeepSoftwareScanner",
    "ReportFormatter",
    "router",
]

