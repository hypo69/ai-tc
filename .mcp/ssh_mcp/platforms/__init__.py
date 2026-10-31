# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Инициализация пакета платформ (platforms)
# =============================================================================
# Description:
#   Экспорт вспомогательных функций и пакетов адаптеров Windows и Linux.
#
# File: __init__.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.platforms
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:56:40
# =============================================================================

from .base import pack_raw_result, safe_parse_json

__all__ = ["pack_raw_result", "safe_parse_json"]
