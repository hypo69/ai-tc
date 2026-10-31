# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: MCP-сервер управления жизненным циклом Uvicorn/Unicorn (unicorn_mcp_server.py)
# =============================================================================
# Description:
#   Локальный MCP-сервер (STDIO) на базе MCP Python SDK v2 (`MCPServer`) для
#   запуска, остановки и мониторинга фонового сервера FastAPI/Uvicorn (`Run-Unicorn.ps1`).
#
#   Зачем нужен этот модуль:
#     1. Дистанционное управление процессом ASGI-сервера из ИИ-ассистентов.
#     2. Кроссплатформенный контроль статуса процесса и сетевого порта,
#        настроенного в корневом `config.json`.
#
# Usage Examples:
#   Python API:
#     from .unicorn_mcp_server import unicorn_status
#     status_text = await unicorn_status()
#
# File: unicorn_mcp_server.py
# Project: AI Windows Admin (AI-TC)
# Package: .mcp
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 17:06:00
# =============================================================================

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_CURRENT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _CURRENT_DIR.parent
for _p in (str(_CURRENT_DIR), str(_PROJECT_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mcp.server import MCPServer

from header import __root__
from logger import logger

try:
    from .config_helper import get_config_value, is_port_open
except ImportError:
    from config_helper import get_config_value, is_port_open

mcp = MCPServer("Unicorn-Manager")


def _resolve_unicorn_script() -> Path:
    """Определение пути к PowerShell-скрипту запуска `Run-Unicorn.ps1`.

    Returns:
        Path: Путь к файлу скрипта.

    Examples:
        >>> isinstance(_resolve_unicorn_script(), Path)
        True
    """
    candidate = __root__ / "launchers" / "Run-Unicorn.ps1"
    if candidate.exists():
        return candidate
    return __root__ / "Run-Unicorn.ps1"


@mcp.tool(
    name="unicorn_start",
    description="Запуск фонового сервиса Run-Unicorn.ps1 (FastAPI/Uvicorn сервер)",
)
async def unicorn_start() -> str:
    """Запуск сервиса `Run-Unicorn.ps1` в фоновом режиме.

    Returns:
        str: Сообщение о результате запуска процесса.

    Examples:
        >>> callable(unicorn_start)
        True
    """
    script_path = _resolve_unicorn_script()
    if not script_path.exists():
        return f"Ошибка: Файл скрипта не найден: {script_path}"

    try:
        shell_exe = "pwsh" if sys.platform != "win32" else "powershell"
        subprocess.Popen(
            [
                shell_exe,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script_path),
            ],
            cwd=str(__root__),
        )
        logger.info(f"[unicorn_mcp_server] Запущен процесс {script_path}")
        return "Сервис Unicorn успешно запущен в фоновом режиме."
    except Exception as exc:
        logger.error(f"[unicorn_mcp_server] Ошибка запуска unicorn_start: {exc}")
        return f"Ошибка при запуске Unicorn: {exc}"


@mcp.tool(
    name="unicorn_stop",
    description="Остановка запущенных процессов Uvicorn/Unicorn",
)
async def unicorn_stop() -> str:
    """Остановка активных процессов `uvicorn`.

    Returns:
        str: Отчет о выполнении команды остановки.

    Examples:
        >>> callable(unicorn_stop)
        True
    """
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/IM", "uvicorn.exe", "/T"],
                capture_output=True,
                text=True,
                check=False,
            )
        else:
            subprocess.run(
                ["pkill", "-f", "uvicorn"],
                capture_output=True,
                text=True,
                check=False,
            )
        logger.info("[unicorn_mcp_server] Выполнена команда остановки процессов uvicorn")
        return "Команда остановки процесса Unicorn выполнена."
    except Exception as exc:
        logger.error(f"[unicorn_mcp_server] Ошибка остановки unicorn_stop: {exc}")
        return f"Ошибка при остановке Unicorn: {exc}"


@mcp.tool(
    name="unicorn_status",
    description="Проверка текущего статуса работы процесса Unicorn (uvicorn) и сетевого порта",
)
async def unicorn_status() -> str:
    """Проверка текущего статуса работы процесса Unicorn (`uvicorn`) и TCP-порта сервера.

    Returns:
        str: Текстовый отчет о состоянии процесса и порта.

    Examples:
        >>> import asyncio
        >>> res = asyncio.run(unicorn_status())
        >>> "Unicorn" in res
        True
    """
    try:
        port = int(get_config_value("server.port", 0) or 0)
        port_active = is_port_open(port=port, timeout=0.5) if port > 0 else False

        process_running = False
        if sys.platform == "win32":
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq uvicorn.exe"],
                capture_output=True,
                text=True,
                check=False,
            )
            process_running = "uvicorn.exe" in (result.stdout or "")
        else:
            result = subprocess.run(
                ["pgrep", "-f", "uvicorn"],
                capture_output=True,
                text=True,
                check=False,
            )
            process_running = result.returncode == 0

        if process_running or port_active:
            return f"Сервис Unicorn активен и работает (процесс={process_running}, порт {port} открыт={port_active})."
        return f"Сервис Unicorn не запущен (порт {port} закрыт)."
    except Exception as exc:
        logger.error(f"[unicorn_mcp_server] Ошибка проверки статуса unicorn_status: {exc}")
        return f"Ошибка проверки статуса: {exc}"


def main() -> int:
    """Запуск Unicorn MCPServer в режиме STDIO.

    Returns:
        int: Код завершения (0 — успешно).

    Examples:
        >>> callable(main)
        True
    """
    logger.info("[unicorn_mcp_server] Запуск Unicorn MCPServer...")
    mcp.run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
