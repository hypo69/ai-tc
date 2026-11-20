# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Инициализация пакета платформ (platforms)
# =============================================================================
# Description:
#   Экспорт вспомогательных функций и пакетов адаптеров Windows и Linux.
#
# File: __init__.py
# Project: ai-tc (ai-tc)
# Package: ssh_mcp.platforms
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 05:00:00
# =============================================================================

from .base import pack_raw_result, safe_parse_json

__all__ = ["pack_raw_result", "safe_parse_json"]
