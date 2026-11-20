# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Apps Windows Telemetry - Grouped Telemetry
# =============================================================================
# Description:
#   Прямой экспорт сгруппированной телеметрии из аналитического ядра.
#
# Usage Examples:
#   Python API:
#     from apps.windows.telemetry.grouped_telemetry import GroupedTelemetryBuilder
#
# File: grouped_telemetry.py
# Project: ai-tc
# Package: apps.windows.telemetry
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 05:00:00
# =============================================================================

from __future__ import annotations
"""Экспорт моделей и построителя сгруппированной телеметрии."""

from apps.windows.analytics.grouped_telemetry import (
    TelemetryGroupInfo,
    GroupedTelemetryBuilder,
    GroupDiagnoseRequest,
    GroupDiagnosticResult,
    SynthesisRequest,
    SynthesisDiagnosticResult,
)

__all__ = [
    "TelemetryGroupInfo",
    "GroupedTelemetryBuilder",
    "GroupDiagnoseRequest",
    "GroupDiagnosticResult",
    "SynthesisRequest",
    "SynthesisDiagnosticResult",
]

