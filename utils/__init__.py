# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Utils Proxy
# =============================================================================
# Description:
#   Реэкспорт модуля общих функций из src.utils.common.
#
# File: __init__.py
# Project: ai-tc
# Package: utils
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 05:00:00
# =============================================================================

from src.utils.common import console_log, load_json_config, save_json_file, get_utc_timestamp_iso

__all__ = ["console_log", "load_json_config", "save_json_file", "get_utc_timestamp_iso"]

