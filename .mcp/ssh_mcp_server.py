# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Точка запуска SSH MCP Server из каталога .mcp/ (ssh_mcp_server.py)
# =============================================================================
# Description:
#   Обеспечение совместимости с реестром локальных MCP-серверов AI-TC (`.mcp/`)
#   для бесшовного подключения в Claude Desktop, Cursor, Antigravity и VS Code.
#
#   Зачем нужен этот модуль:
#     1. Единая точка входа в `.mcp/ssh_mcp_server.py`, делегирующая выполнение
#        ядру `.mcp/ssh_mcp/main.py` (`ssh_mcp.main.run_server`).
#     2. Автоматическая нормализация `sys.path` для запуска из любой рабочей папки.
#
# Usage Examples:
#   Python API:
#     from .ssh_mcp_server import main
#     exit_code = main(["--transport", "stdio"])
#
# File: ssh_mcp_server.py
# Project: AI Windows Admin (AI-TC)
# Package: .mcp
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 17:10:00
# =============================================================================

from __future__ import annotations

from pathlib import Path
import sys
from typing import List, Optional

_MCP_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _MCP_DIR.parent
for _path_entry in (str(_MCP_DIR), str(_PROJECT_ROOT)):
    if _path_entry not in sys.path:
        sys.path.insert(0, _path_entry)

from ssh_mcp.main import run_server


def main(argv: Optional[List[str]] = []) -> int:
    """Запуск SSH MCP Server с переданными аргументами командной строки.

    Args:
        argv (Optional[List[str]]): Список аргументов CLI.
                                    Значение по умолчанию: [].

    Returns:
        int: Код завершения процесса.

    Examples:
        >>> callable(main)
        True
    """
    return run_server(argv if argv else [])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
