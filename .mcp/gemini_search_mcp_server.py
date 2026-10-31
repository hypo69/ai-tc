# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: MCP-сервер поиска Google Gemini и мониторинга пула ключей (gemini_search_mcp_server.py)
# =============================================================================
# Description:
#   Локальный MCP-сервер (STDIO) на базе MCP Python SDK v2 (`MCPServer`),
#   предоставляющий инструменты поиска через Google Gemini (`UnifiedChatModel`)
#   и инспекции состояния пула API-ключей (`gemini_api_key_state`).
#
#   Зачем нужен этот модуль:
#     1. Выполнение поисковых и аналитических запросов через облачный провайдер
#        Google Gemini с автоматической ротацией API-ключей.
#     2. Мониторинг активного ключа и общего количества доступных ключей в пуле
#        через инструмент `gemini_key_pool_status`.
#
# Usage Examples:
#   Python API:
#     from .gemini_search_mcp_server import gemini_web_search, gemini_key_pool_status
#     status_json = gemini_key_pool_status()
#
# File: gemini_search_mcp_server.py
# Project: AI Windows Admin (AI-TC)
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
from src.ai.gemini.gemini_api_key_state import get_active_key_name, load_api_keys
from src.ai.orchestration.unified_chat import UnifiedChatModel

try:
    from .config_helper import get_config_value
except ImportError:
    from config_helper import get_config_value

mcp = MCPServer("Gemini-Search-Server")

_GEMINI_SEARCH_INSTRUCTION = (
    "Ты — поисковый и аналитический агент Google Gemini. "
    "Предоставь точный, актуальный и структурированный ответ в формате Markdown."
)


def _get_default_gemini_model() -> str:
    """Получение модели Gemini по умолчанию из `config.json`.

    Returns:
        str: Идентификатор модели Gemini.

    Examples:
        >>> len(_get_default_gemini_model()) > 0
        True
    """
    configured = str(
        get_config_value(
            "ai_providers_and_models_configuration.providers.gemini.default_model",
            "",
        )
    ).strip()
    if configured:
        return configured
    fallback = str(
        get_config_value(
            "ai_providers_and_models_configuration.default_model",
            "gemini-3.5-flash-lite",
        )
    ).strip()
    return fallback or "gemini-3.5-flash-lite"


async def _run_gemini_search(query: str, model: Optional[str] = "") -> str:
    """Выполнение поискового запроса через `UnifiedChatModel` (провайдер `gemini`).

    Args:
        query (str): Поисковый запрос пользователя.
        model (Optional[str]): Идентификатор модели Google Gemini.
                               Значение по умолчанию: '' (берется из `config.json`).

    Returns:
        str: Ответ модели в формате Markdown или JSON-строка с описанием ошибки.

    Examples:
        >>> import asyncio
        >>> res = asyncio.run(_run_gemini_search(""))
        >>> "error" in res
        True
    """
    if not query or not query.strip():
        return json.dumps(
            {"status": "error", "message": "Пустой поисковый запрос (query не может быть пустым)"},
            ensure_ascii=False,
        )

    target_model = model.strip() if model and model.strip() else _get_default_gemini_model()
    try:
        chat_model = UnifiedChatModel(
            system_instruction=_GEMINI_SEARCH_INSTRUCTION,
            provider="gemini",
            model=target_model,
        )
        result_markdown = await chat_model.ask(q=query.strip())
        return str(result_markdown) if result_markdown else ""
    except Exception as exc:
        logger.error(f"[gemini_search_mcp_server] Ошибка выполнения поиска: {exc}")
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False)


def _run_key_pool_status() -> str:
    """Формирование JSON-отчета о состоянии пула API-ключей Google Gemini.

    Returns:
        str: JSON-строка со статусом пула (`total_keys`, `active_key_name`, `active_key_masked`).

    Examples:
        >>> data = json.loads(_run_key_pool_status())
        >>> "status" in data
        True
    """
    try:
        keys, names, _states = load_api_keys()
        active_name = get_active_key_name()
        active_key = keys[0] if keys else ""
        masked = f"...{active_key[-6:]}" if len(active_key) >= 6 else "***"
        return json.dumps(
            {
                "status": "ok",
                "total_keys": len(keys),
                "key_names": names,
                "active_key_name": active_name,
                "active_key_masked": masked,
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        logger.error(f"[gemini_search_mcp_server] Ошибка проверки статуса пула ключей: {exc}")
        return json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False)


@mcp.tool(
    name="gemini_web_search",
    description="Выполнить веб-поиск и аналитический запрос через Google Gemini",
)
async def gemini_web_search(query: str, model: Optional[str] = "") -> str:
    """Выполнение поискового запроса через облачный провайдер Google Gemini.

    Args:
        query (str): Поисковый запрос пользователя.
        model (Optional[str]): Идентификатор модели Gemini.
                               Значение по умолчанию: '' (используется модель из `config.json`).

    Returns:
        str: Результат поиска в формате Markdown или JSON-строка с ошибкой.

    Examples:
        >>> import asyncio
        >>> out = asyncio.run(gemini_web_search(""))
        >>> "error" in out
        True
    """
    return await _run_gemini_search(query=query, model=model)


@mcp.tool(
    name="gemini_key_pool_status",
    description="Получить статус пула API-ключей Google Gemini и текущего активного ключа",
)
def gemini_key_pool_status() -> str:
    """Получение статуса пула API-ключей Gemini и маски активного ключа.

    Returns:
        str: JSON-строка с информацией о пуле ключей.

    Examples:
        >>> res = json.loads(gemini_key_pool_status())
        >>> res.get("status") in ("ok", "error")
        True
    """
    return _run_key_pool_status()


def main() -> int:
    """Запуск MCP-сервера поиска Google Gemini в режиме STDIO.

    Returns:
        int: Код завершения (0 — успешно).

    Examples:
        >>> callable(main)
        True
    """
    logger.info("[gemini_search_mcp_server] Запуск Gemini Search MCPServer...")
    mcp.run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
