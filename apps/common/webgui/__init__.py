# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Common WebGUI - Package Init
# =============================================================================
# Description:
#   Общие веб-решения, стили, темы, i18n и универсальные компоненты UI
#   для приложений экосистемы AI Windows Admin.
#
# File: __init__.py
# Project: ai-windows-admin
# Package: apps.common.webgui
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-03 14:41:44
# =============================================================================

from __future__ import annotations

from pathlib import Path
from apps.common.webgui.static_files import SmartMultiDirStaticFiles

COMMON_WEBGUI_DIR = Path(__file__).resolve().parent


def get_common_webgui_dir() -> Path:
    """Возвращает абсолютный путь к каталогу общих ассетов WebGUI."""
    return COMMON_WEBGUI_DIR


__all__ = [
    'COMMON_WEBGUI_DIR',
    'SmartMultiDirStaticFiles',
    'get_common_webgui_dir',
]

