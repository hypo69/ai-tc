# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Telemetry - Async Batch Client Package
# =============================================================================
# Description:
#   Асинхронный клиент и пакет пакетной передачи телеметрии с дельта-фильтрацией.
#
# File: __init__.py
# Project: ai-tc
# Package: src.telemetry
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 05:00:00
# =============================================================================

from .async_client import AsyncTelemetryBatchClient

__all__ = ["AsyncTelemetryBatchClient"]

