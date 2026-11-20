# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Screen Capture - Package Init
# =============================================================================
# Description:
#   Экспорт публичных интерфейсов подсистемы экранного захвата (Windows.Graphics.Capture, GDI).
#
# Usage Examples:
#   from apps.windows.vision.screen_capture import ScreenCaptureEngine, DisplayInfo, WindowInfo
#
# File: __init__.py
# Project: ai-windows-admin
# Package: apps.windows.vision.screen_capture
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 02:53:00
# =============================================================================

from __future__ import annotations
"""Подсистема захвата экрана и визуальной диагностики AI-TC."""

from apps.windows.vision.screen_capture.engine import ScreenCaptureEngine
from apps.windows.vision.screen_capture.models import (
    CaptureBackendType,
    CaptureEngineConfig,
    CaptureTargetType,
    CapturedFrame,
    DisplayInfo,
    StreamStatus,
    VisualTelemetryEvent,
    WindowInfo,
)
from apps.windows.vision.screen_capture.screen_diff import ScreenDiffEngine
from apps.windows.vision.screen_capture.visual_intelligence import VisualIntelligenceEngine

__all__ = [
    "ScreenCaptureEngine",
    "CaptureBackendType",
    "CaptureEngineConfig",
    "CaptureTargetType",
    "CapturedFrame",
    "DisplayInfo",
    "StreamStatus",
    "VisualTelemetryEvent",
    "WindowInfo",
    "ScreenDiffEngine",
    "VisualIntelligenceEngine",
]
