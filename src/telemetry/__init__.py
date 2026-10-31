# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Telemetry - Async Batch Client Package
# =============================================================================
# Description:
#   Асинхронный клиент и пакет пакетной передачи телеметрии с дельта-фильтрацией.
#
# File: __init__.py
# Project: ai-windows-admin
# Package: src.telemetry
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-13 20:45:00
# =============================================================================

from .async_client import AsyncTelemetryBatchClient

__all__ = ["AsyncTelemetryBatchClient"]

