# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Wikillm -   Main  
# =============================================================================
# Description:
#   Точка входа для вызова модуля через py -m src.ai.wikillm.
#
# Usage Examples:
#   CLI:
#     python -m src.ai.wikillm.__main__
#   Python API:
#     import src.ai.wikillm.__main__ as __main__
#
# File: __main__.py
# Project: ai-windows-admin
# Package: src.ai.wikillm
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 17:35:00
# =============================================================================

"""Точка входа для вызова модуля через py -m src.ai.wikillm."""

from .cli import main

if __name__ == "__main__":
    main()

