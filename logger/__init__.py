# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Logger - Init
# =============================================================================
# Description:
#   Инициализация пакета централизованного логирования logger.
#
# File: __init__.py
# Project: ai-tc
# Package: logger
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 05:00:00
# =============================================================================

"""Пакет централизованного логирования ai-tc."""

from .logger import (
    CONSOLE_LEVEL,
    Logger,
    logger,
    JsonFormatter,
    get_uvicorn_log_config,
    get_subsystem_logger,
    set_trace_context,
    get_trace_context,
    clear_trace_context,
    trace_context,
)
