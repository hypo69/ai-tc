# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows -   Main  
# =============================================================================
# Description:
#   Точка входа в AI Windows Diagnostic & Administration Center.
#
# Usage Examples:
#   CLI:
#     python -m apps.windows.__main__
#   Python API:
#     import apps.windows.__main__ as __main__
#
# File: __main__.py
# Project: ai-windows-admin
# Package: apps.windows
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 17:35:00
# =============================================================================

"""Точка входа в AI Windows Diagnostic & Administration Center."""

import sys

if __name__ == '__main__':
    server_flags = {'--host', '--port', '--reload', '--log-level'}
    # Если запуск с флагами сервера или без аргументов - запускаем веб-сервер, иначе CLI
    if len(sys.argv) > 1 and not all(arg.split('=')[0] in server_flags for arg in sys.argv[1:] if arg.startswith('-')):
        from apps.windows.cli import main
        main()
    else:
        from apps.windows.main import main
        main()
