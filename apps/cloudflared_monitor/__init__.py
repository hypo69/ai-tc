# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Cloudflared Monitor Package
# =============================================================================
# Description:
#   Модуль мониторинга, супервизии и диагностики Cloudflare Tunnel.
#
# File: __init__.py
# Project: ai-windows-admin
# Package: apps.cloudflared_monitor
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-30 14:00:00
# =============================================================================

"""Пакет монитора и диспетчера Cloudflare Tunnel."""

from __future__ import annotations

from .router import get_state, init_router, router
from .src.state import CloudflaredState

__all__ = [
    "CloudflaredState",
    "get_state",
    "init_router",
    "router",
]
