# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Logger - Init
# =============================================================================
# Description:
#   Инициализация пакета централизованного логирования logger.
#
# File: __init__.py
# Project: ai-windows-admin
# Package: logger
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-27 23:32:00
# =============================================================================

"""Пакет централизованного логирования AI-Windows-Admin."""

from .logger import (
    CONSOLE_LEVEL,
    Logger,
    logger,
    JsonFormatter,
    get_uvicorn_log_config,
    get_subsystem_logger,
)
