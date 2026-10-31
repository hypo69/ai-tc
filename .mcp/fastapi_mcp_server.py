# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: MCP-сервер интеграции с центральным FastAPI-сервером (fastapi_mcp_server.py)
# =============================================================================
# Description:
#   Локальный MCP-сервер (STDIO) на базе MCP Python SDK v2 (`MCPServer`),
#   обеспечивающий проксирование запросов от внешних ИИ-клиентов к REST API
#   центрального сервера AI Windows Admin (`config.json`).
#
#   Зачем нужен этот модуль:
#     1. Отправка запросов в чат-роутер (`/api/chat`) и получение метаданных
#        медиатеки (`/api/media`) и торрент-клиента (`/api/torrents`) по протоколу MCP.
#     2. Динамическое определение базового адреса сервера (`get_server_url()`)
#        строго на основе корневого `config.json` без жесткого кодирования портов.
#
# Usage Examples:
#   Python API:
#     from .fastapi_mcp_server import get_base_url, fastapi_chat
#     url = get_base_url()
#
# File: fastapi_mcp_server.py
# Project: AI Windows Admin (AI-TC)
# Package: .mcp
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 17:06:00
# =============================================================================

from __future__ import annotations

import sys
from pathlib import Path

_CURRENT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _CURRENT_DIR.parent
for _p in (str(_CURRENT_DIR), str(_PROJECT_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import httpx
from mcp.server import MCPServer

from logger import logger

try:
    from .config_helper import get_config_value, get_server_url
except ImportError:
    from config_helper import get_config_value, get_server_url

mcp = MCPServer("FastAPI-Media-Client")


def get_base_url() -> str:
    """Получение базового URL FastAPI-сервера из корневого `config.json`.

    Returns:
        str: Базовый URL сервера (например, `'http://127.0.0.1:8001'`) или `''` при ошибке.

    Examples:
        >>> url = get_base_url()
        >>> url.startswith("http")
        True
    """
    url = get_server_url()
    if not url:
        logger.error("[fastapi_mcp_server] Не удалось определить базовый URL сервера из config.json")
        return ""
    return url


def _get_http_timeout(default_seconds: float = 15.0) -> float:
    """Получение таймаута HTTP-запросов из конфигурации.

    Args:
        default_seconds (float): Значение по умолчанию в секундах.
                                 Значение по умолчанию: 15.0.

    Returns:
        float: Таймаут в секундах.

    Examples:
        >>> _get_http_timeout(15.0) > 0
        True
    """
    configured = get_config_value("ai_instruments.runtime.execution_timeout", default_seconds)
    try:
        val = float(configured)
        return val if val > 0 else default_seconds
    except (TypeError, ValueError):
        return default_seconds


@mcp.tool(
    name="fastapi_chat",
    description="Отправка сообщения в центральный чат-роутер FastAPI backend (/api/chat)",
)
async def fastapi_chat(message: str) -> str:
    """Отправка текстового сообщения в чат-роутер FastAPI backend.

    Args:
        message (str): Текст сообщения пользователя для отправки в `/api/chat`.

    Returns:
        str: Текст ответа от сервера или описание ошибки.

    Examples:
        >>> import asyncio
        >>> res = asyncio.run(fastapi_chat(""))
        >>> "Пустое сообщение" in res
        True
    """
    if not message or not message.strip():
        return "Ошибка: Пустое сообщение для отправки в /api/chat"

    base_url = get_base_url()
    if not base_url:
        return "Ошибка: Не настроен адрес сервера в config.json"

    timeout = _get_http_timeout(30.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{base_url}/api/chat",
                json={"message": message.strip()},
            )
            return response.text
    except Exception as exc:
        logger.error(f"[fastapi_mcp_server] Ошибка запроса fastapi_chat: {exc}")
        return f"Ошибка запроса к /api/chat: {exc}"


@mcp.tool(
    name="fastapi_media_list",
    description="Получение списка медиафайлов из медиа-роутера FastAPI (/api/media)",
)
async def fastapi_media_list() -> str:
    """Получение списка медиафайлов из медиа-роутера FastAPI.

    Returns:
        str: JSON-ответ от `/api/media` или описание ошибки соединения.

    Examples:
        >>> callable(fastapi_media_list)
        True
    """
    base_url = get_base_url()
    if not base_url:
        return "Ошибка: Не настроен адрес сервера в config.json"

    timeout = _get_http_timeout(15.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{base_url}/api/media")
            return response.text
    except Exception as exc:
        logger.error(f"[fastapi_mcp_server] Ошибка запроса fastapi_media_list: {exc}")
        return f"Ошибка запроса к /api/media: {exc}"


@mcp.tool(
    name="fastapi_qbittorrent_info",
    description="Получение информации о текущих торрентах из qBittorrent через FastAPI (/api/torrents)",
)
async def fastapi_qbittorrent_info() -> str:
    """Получение информации о текущих торрентах из qBittorrent через FastAPI.

    Returns:
        str: JSON-ответ от `/api/torrents` или описание ошибки соединения.

    Examples:
        >>> callable(fastapi_qbittorrent_info)
        True
    """
    base_url = get_base_url()
    if not base_url:
        return "Ошибка: Не настроен адрес сервера в config.json"

    timeout = _get_http_timeout(15.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{base_url}/api/torrents")
            return response.text
    except Exception as exc:
        logger.error(f"[fastapi_mcp_server] Ошибка запроса fastapi_qbittorrent_info: {exc}")
        return f"Ошибка запроса к /api/torrents: {exc}"


def main() -> int:
    """Запуск FastAPI MCPServer в режиме STDIO.

    Returns:
        int: Код завершения (0 — успешно).

    Examples:
        >>> callable(main)
        True
    """
    base_url = get_base_url()
    if not base_url:
        logger.error("[fastapi_mcp_server] Ошибка получения базового URL из config.json")
        raise RuntimeError("Не удалось получить базовый URL сервера из config.json")
    logger.info(f"[fastapi_mcp_server] Запуск FastAPI MCPServer (target={base_url})...")
    mcp.run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
