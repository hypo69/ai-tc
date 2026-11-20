# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Screen Capture - Backends Package
# =============================================================================
# Description:
#   Пакет бэкендов экранного захвата (WGC, DXGI, GDI).
#
# File: __init__.py
# Project: ai-windows-admin
# Package: apps.windows.vision.screen_capture.backends
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 02:49:00
# =============================================================================

from __future__ import annotations
"""Экспорт бэкендов графического захвата."""

from apps.windows.vision.screen_capture.backends.base import BaseCaptureBackend
from apps.windows.vision.screen_capture.backends.gdi_backend import GdiCaptureBackend
from apps.windows.vision.screen_capture.backends.wgc_backend import WgcCaptureBackend

__all__ = [
    "BaseCaptureBackend",
    "GdiCaptureBackend",
    "WgcCaptureBackend",
]
