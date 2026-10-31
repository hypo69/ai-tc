# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Tshark - Init
# =============================================================================
# Description:
#   Инициализация пакета TShark и экспорт основных компонентов сетевого анализа.
#
# Usage Examples:
#   Python API:
#     from apps.tshark import TSharkWrapper, TrafficAnalyzer, AIDetector
#
#     wrapper = TSharkWrapper()
#
# File: __init__.py
# Project: ai-windows-admin
# Package: apps.tshark
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-20 13:22:00
# =============================================================================

from __future__ import annotations
"""Пакет TShark: обертка над утилитой Wireshark TShark и анализатор сетевого трафика."""

from .ai_detector import AIDetector
from .analyzer import TrafficAnalyzer
from .models import (
    AnomalyReport,
    CaptureFilter,
    NetworkInterface,
    PacketSummary,
    TrafficStats,
)
from .wrapper import TSharkWrapper

__all__ = [
    "AIDetector",
    "AnomalyReport",
    "CaptureFilter",
    "NetworkInterface",
    "PacketSummary",
    "TSharkWrapper",
    "TrafficAnalyzer",
    "TrafficStats",
]

