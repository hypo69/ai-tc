# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Пакет серверов Model Context Protocol (.mcp)
# =============================================================================
# Description:
#   Инициализация пакета локальных и гибридных MCP-серверов платформы
#   AI Windows Admin (ai-tc).
#
#   Зачем нужен этот модуль:
#     1. Экспорт вспомогательных функций конфигурации (config_helper) для всех
#        MCP-серверов каталога `.mcp/`.
#     2. Гарантированная регистрация корня проекта (`__root__`) и `.mcp` в
#        `sys.path` при импорте любого модуля из `.mcp`.
#
# Usage Examples:
#   Python API:
#     from config_helper import get_project_root, get_server_url
#     root = get_project_root()
#
# File: __init__.py
# Project: AI Windows Admin (ai-tc)
# Package: .mcp
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 17:11:15
# =============================================================================

from __future__ import annotations

from pathlib import Path
import sys

_MCP_DIR = Path(__file__).resolve().parent
if str(_MCP_DIR) not in sys.path:
    sys.path.insert(0, str(_MCP_DIR))

try:
    from .config_helper import (
        get_certs_dir,
        get_config_value,
        get_data_dir,
        get_env_var,
        get_project_root,
        get_server_url,
        is_port_open,
        load_config,
    )
except ImportError:
    from config_helper import (  # type: ignore[no-redef]
        get_certs_dir,
        get_config_value,
        get_data_dir,
        get_env_var,
        get_project_root,
        get_server_url,
        is_port_open,
        load_config,
    )

__all__ = [
    "get_certs_dir",
    "get_config_value",
    "get_data_dir",
    "get_env_var",
    "get_project_root",
    "get_server_url",
    "is_port_open",
    "load_config",
]
