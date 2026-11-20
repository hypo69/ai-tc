# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Apps Windows Modules Backup_Manager -   Main  
# =============================================================================
# Description:
#   CLI запуск TUI дашборда Windows Backup Manager.
#
# Usage Examples:
#   CLI:
#     python -m apps.windows.sdk.modules.backup_manager.__main__
#   Python API:
#     from apps.windows.sdk.modules.backup_manager.__main__ import main
#
#     res = main()
#
# File: __main__.py
# Project: ai-tc
# Package: apps.windows.sdk.modules.backup_manager
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 05:00:00
# =============================================================================

"""CLI запуск TUI дашборда Windows Backup Manager."""

import sys
from apps.windows.sdk.modules.backup_manager.tui import BackupManagerTUI

def main() -> None:
    tui = BackupManagerTUI()
    tui.render_dashboard()
if __name__ == '__main__':
    main()
