# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Utils Proxy - Common
# =============================================================================
# Description:
#   Реэкспорт модуля общих функций из src.utils.common.
#
# File: common.py
# Project: ai-windows-admin
# Package: utils
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 14:36:00
# =============================================================================

"""Прокси-модуль общих утилит, реэкспортирующий функции из `src.utils.common`."""

from src.utils.common import console_log, load_json_config, save_json_file, get_utc_timestamp_iso

__all__ = ["console_log", "load_json_config", "save_json_file", "get_utc_timestamp_iso"]
