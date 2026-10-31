# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Точка входа запуска SSH MCP Server (main.py)
# =============================================================================
# Description:
#   Запуск SSH MCP Server в режиме STDIO (Local MCP) или Streamable HTTP
#   (Remote MCP / Hybrid). Поддерживает команду `python -m ssh_mcp`.
#
# File: main.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 17:02:00
# =============================================================================

import argparse
import os
from typing import List, Optional
import uvicorn

from .bootstrap import create_runtime
from .security.authentication import RemoteMCPAuthenticator
from .server import build_mcp_server, build_remote_http_app

try:
    from logger import logger
except ImportError:
    import logging

    logger = logging.getLogger("ssh_mcp")


def parse_cli_args(argv: Optional[List[str]] = []) -> argparse.Namespace:
    """Разбор аргументов командной строки запуска SSH MCP Server.

    Args:
        argv (Optional[List[str]]): Список аргументов CLI.
                                    Значение по умолчанию: [].

    Returns:
        argparse.Namespace: Разобранные параметры запуска.

    Examples:
        >>> ns = parse_cli_args(["--transport", "stdio"])
        >>> ns.transport
        'stdio'
    """
    parser = argparse.ArgumentParser(description="SSH MCP Server (Windows + Linux Full Admin)")
    parser.add_argument(
        "--config",
        type=str,
        default="",
        help="Путь к файлу конфигурации settings.yaml",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
        help="Протокол транспорта MCP (stdio или streamable-http)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="",
        help="Адрес привязки для режима streamable-http (по умолчанию 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="Порт для режима streamable-http (по умолчанию 8765)",
    )
    return parser.parse_args(argv if argv else [])


def run_server(argv: Optional[List[str]] = []) -> int:
    """Инициализация и запуск сервера в выбранном транспортном режиме.

    Args:
        argv (Optional[List[str]]): Аргументы командной строки.

    Returns:
        int: Код завершения (0 — успех).

    Examples:
        >>> pass
    """
    args = parse_cli_args(argv)
    runtime = create_runtime(config_path=args.config)

    if args.transport == "streamable-http":
        host = args.host or runtime.settings.server.remote.host
        port = args.port if args.port > 0 else runtime.settings.server.remote.port
        token = os.environ.get(runtime.settings.security.api_token_env, "")
        RemoteMCPAuthenticator.validate_network_binding(
            host=host,
            tls_enabled=runtime.settings.server.remote.tls,
            has_token=bool(token),
        )
        app = build_remote_http_app(runtime, expected_token=token)
        uvicorn.run(app, host=host, port=port)
        return 0

    mcp_server, _mods, _rt = build_mcp_server(runtime)
    mcp_server.run(transport="stdio")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(run_server(sys.argv[1:]))
