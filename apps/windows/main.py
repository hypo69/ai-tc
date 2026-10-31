# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows - Main Entry Point
# =============================================================================
# Description:
#   Точка входа для приложения Windows System API (Terminal Controller / TC).
#   Делегирует создание и запуск FastAPI сервера каноническому модулю apps.windows.api.
#
# Usage Examples:
#   CLI:
#     python -m apps.windows.main
#   Python API:
#     from apps.windows.main import create_app
#
#     app = create_app()
#
# File: main.py
# Project: ai-windows-admin
# Package: apps.windows
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 17:35:00
# =============================================================================

from __future__ import annotations
"""Точка входа для приложения Windows System API (Terminal Controller)."""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from apps.windows.api.server import create_app, create_internal_app, load_config, load_tc_config
from apps.windows.api.__main__ import main

__all__ = [
    'create_app',
    'create_internal_app',
    'load_config',
    'load_tc_config',
    'main',
]

if __name__ == '__main__':
    main()

