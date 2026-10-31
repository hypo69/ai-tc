# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Модульная точка входа пакета (`python -m ssh_mcp`)
# =============================================================================
# Description:
#   Обеспечение запуска сервера командой `python -m ssh_mcp` согласно
#   разделу 12 Технического задания.
#
# File: __main__.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 17:02:15
# =============================================================================

import sys
from .main import run_server

if __name__ == "__main__":
    raise SystemExit(run_server(sys.argv[1:]))
