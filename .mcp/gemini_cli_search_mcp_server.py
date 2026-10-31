# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: MCP-сервер поиска через Google Gemini CLI (gemini_cli_search_mcp_server.py)
# =============================================================================
# Description:
#   Локальный MCP-сервер (STDIO) на базе MCP Python SDK v2 (`MCPServer`),
#   выполняющий поисковые и аналитические запросы через терминальный агент
#   Google Gemini CLI (`UnifiedChatModel` с провайдером `gemini_cli`).
#
#   Зачем нужен этот модуль:
#     1. Предоставление легковесного CLI-поиска внешним ИИ-клиентам по протоколу MCP.
#     2. Маршрутизация вызовов через стандартный фасад `UnifiedChatModel`
#        с получением модели по умолчанию из `config.json`.
#
# Usage Examples:
#   Python API:
#     from .gemini_cli_search_mcp_server import gemini_cli_web_search
#     res = await gemini_cli_web_search(query="PowerShell Get-WinEvent filter examples")
#
# File: gemini_cli_search_mcp_server.py
# Project: AI Windows Admin (ai-tc)
# Package: .mcp
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 17:06:00
# =============================================================================

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

_CURRENT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _CURRENT_DIR.parent
for _p in (str(_CURRENT_DIR), str(_PROJECT_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mcp.server import MCPServer

from logger import logger
from src.ai.orchestration.unified_chat import UnifiedChatModel

try:
    from .config_helper import get_config_value
except ImportError:
    from config_helper import get_config_value

mcp = MCPServer("Gemini-CLI-Search-Server")

_CLI_SYSTEM_INSTRUCTION = (
    "Ты — поисковый ассистент Google Gemini CLI. "
    "Найди точную техническую информацию по запросу и верни структурированный ответ в формате Markdown."
)


def _get_default_gemini_cli_model() -> str:
    """Получение модели Gemini CLI по умолчанию из `config.json`.

    Returns:
        str: Идентификатор модели из конфигурации.

    Examples:
        >>> len(_get_default_gemini_cli_model()) > 0
        True
    """
    configured = str(
        get_config_value(
            "ai_providers_and_models_configuration.providers.gemini_cli.default_model",
            "gemini-2.5-flash",
        )
    ).strip()
    return configured or "gemini-2.5-flash"


async def _run_gemini_cli_search(query: str, model: Optional[str] = "") -> str:
    """Выполнение поискового запроса через `UnifiedChatModel` (провайдер `gemini_cli`).

    Args:
        query (str): Поисковый запрос пользователя.
        model (Optional[str]): Идентификатор модели Gemini CLI.
                               Значение по умолчанию: '' (берется из `config.json`).

    Returns:
        str: Ответ модели в формате Markdown или JSON-строка с ошибкой.

    Examples:
        >>> import asyncio
        >>> res = asyncio.run(_run_gemini_cli_search(""))
        >>> "error" in res
        True
    """
    if not query or not query.strip():
        return json.dumps(
            {"status": "error", "message": "Пустой поисковый запрос (query не может быть пустым)"},
            ensure_ascii=False,
        )

    target_model = model.strip() if model and model.strip() else _get_default_gemini_cli_model()
    try:
        chat_model = UnifiedChatModel(
            system_instruction=_CLI_SYSTEM_INSTRUCTION,
            provider="gemini_cli",
            model=target_model,
        )
        result_markdown = await chat_model.ask(q=query.strip())
        return str(result_markdown) if result_markdown else ""
    except Exception as exc:
        logger.error(f"[gemini_cli_search_mcp_server] Ошибка выполнения поиска: {exc}")
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False)


@mcp.tool(
    name="gemini_cli_web_search",
    description="Выполнить веб-поиск через локальный терминальный агент Google Gemini CLI",
)
async def gemini_cli_web_search(query: str, model: Optional[str] = "") -> str:
    """Выполнение веб-поиска через локальный терминальный агент Google Gemini CLI.

    Args:
        query (str): Поисковый запрос пользователя.
        model (Optional[str]): Идентификатор модели Gemini CLI.
                               Значение по умолчанию: '' (используется модель из `config.json`).

    Returns:
        str: Результат поиска в формате Markdown или JSON-строка с описанием ошибки.

    Examples:
        >>> import asyncio
        >>> out = asyncio.run(gemini_cli_web_search(""))
        >>> "error" in out
        True
    """
    return await _run_gemini_cli_search(query=query, model=model)


def main() -> int:
    """Запуск MCP-сервера поиска Google Gemini CLI в режиме STDIO.

    Returns:
        int: Код завершения (0 — успешно).

    Examples:
        >>> callable(main)
        True
    """
    logger.info("[gemini_cli_search_mcp_server] Запуск Gemini CLI Search MCPServer...")
    mcp.run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
