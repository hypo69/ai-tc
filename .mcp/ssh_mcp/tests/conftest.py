# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Конфигурация тестового окружения pytest для .mcp/ssh_mcp
# =============================================================================
# Description:
#   Автоматическое добавление каталога `.mcp` и корня проекта в `sys.path`
#   при запуске pytest из любой рабочей директории.
#
# File: conftest.py
# Project: AI Windows Admin (ai-tc)
# Package: .mcp.ssh_mcp.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 17:10:00
# =============================================================================

from pathlib import Path
import sys

_MCP_DIR = Path(__file__).resolve().parent.parent.parent
_PROJECT_ROOT = _MCP_DIR.parent

for _entry in (str(_MCP_DIR), str(_PROJECT_ROOT)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)
