# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: MCP-сервер автономного LangChain ReAct-агента (langchain_mcp_server.py)
# =============================================================================
# Description:
#   Локальный MCP-сервер (STDIO) на базе MCP Python SDK v2 (`MCPServer`),
#   предоставляющий внешним ИИ-клиентам доступ к ReAct-агенту (`MediaSearchAgent`)
#   и инструментам `src.ai.agents.tools` (веб-поиск, RAG, вычисление выражений, чтение файлов).
#
#   Зачем нужен этот модуль:
#     1. Интеграция цепочек рассуждений LangChain и локальной базы знаний RAG
#        в любые MCP-совместимые среды (Claude Desktop, Cursor, VS Code, Antigravity).
#     2. Прямое использование верифицированных модулей `src.ai.agents.agent`
#        и `src.ai.agents.tools` без дублирования логики.
#
# Usage Examples:
#   Python API:
#     from .langchain_mcp_server import agent_python_eval, agent_file_read
#     res = agent_python_eval("2 + 2 * 10")
#
# File: langchain_mcp_server.py
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

_CURRENT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _CURRENT_DIR.parent
for _p in (str(_CURRENT_DIR), str(_PROJECT_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mcp.server import MCPServer

from header import __root__
from logger import logger
from src.ai.agents.agent import MediaSearchAgent
from src.ai.agents.tools import file_read, python_eval, rag_search, web_search

mcp = MCPServer("LangChain-AI-Windows-Admin-Agent")
_CONFIG_PATH: Path = __root__ / "config.json"


@mcp.tool(
    name="agent_query",
    description="Выполнить автономный поиск и решение задачи через ReAct-агента LangChain",
)
async def agent_query(query: str) -> str:
    """Выполнение автономного поиска и рассуждений через ReAct-агента `MediaSearchAgent`.

    Args:
        query (str): Текстовый запрос пользователя.

    Returns:
        str: JSON-строка с результатом работы агента (`action`, `data`).

    Examples:
        >>> import asyncio
        >>> res = json.loads(asyncio.run(agent_query("")))
        >>> res.get("action") == "error"
        True
    """
    if not query or not query.strip():
        return json.dumps(
            {"action": "error", "message": "Пустой запрос (query не может быть пустым)"},
            ensure_ascii=False,
        )

    try:
        agent = MediaSearchAgent(config_path=_CONFIG_PATH)
        result = await agent.search(query.strip())
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.error(f"[langchain_mcp_server] Ошибка выполнения agent_query: {exc}")
        return json.dumps({"action": "error", "message": str(exc)}, ensure_ascii=False)


@mcp.tool(
    name="agent_web_search",
    description="Поиск актуальной информации в интернете через поисковый адаптер",
)
async def agent_web_search(query: str) -> str:
    """Поиск актуальной информации в интернете через инструмент `web_search`.

    Args:
        query (str): Поисковый запрос.

    Returns:
        str: Найденная информация или JSON-строка с описанием ошибки.

    Examples:
        >>> import asyncio
        >>> res = asyncio.run(agent_web_search(""))
        >>> "error" in res
        True
    """
    if not query or not query.strip():
        return json.dumps({"error": "Пустой поисковый запрос"}, ensure_ascii=False)

    try:
        if hasattr(web_search, "ainvoke"):
            res = await web_search.ainvoke(query.strip())
            return str(res)
        return str(await web_search(query.strip()))
    except Exception as exc:
        logger.error(f"[langchain_mcp_server] Ошибка выполнения agent_web_search: {exc}")
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


@mcp.tool(
    name="agent_rag_search",
    description="Семантический поиск по локальной базе знаний RAG",
)
async def agent_rag_search(query: str, top_k: int = 5) -> str:
    """Семантический поиск по базе знаний RAG через инструмент `rag_search`.

    Args:
        query (str): Поисковый запрос для векторного/гибридного поиска.
        top_k (int): Максимальное количество возвращаемых фрагментов.
                     Значение по умолчанию: 5.

    Returns:
        str: JSON-строка со списком найденных фрагментов документации.

    Examples:
        >>> import asyncio
        >>> asyncio.run(agent_rag_search(""))
        '[]'
    """
    if not query or not query.strip():
        return json.dumps([], ensure_ascii=False)

    limit = max(1, int(top_k)) if top_k else 5
    try:
        if hasattr(rag_search, "ainvoke"):
            res = await rag_search.ainvoke({"query": query.strip(), "top_k": limit})
            return str(res)
        return str(await rag_search(query=query.strip(), top_k=limit))
    except Exception as exc:
        logger.error(f"[langchain_mcp_server] Ошибка выполнения agent_rag_search: {exc}")
        return json.dumps([], ensure_ascii=False)


@mcp.tool(
    name="agent_python_eval",
    description="Безопасное вычисление математических и строковых выражений на Python",
)
def agent_python_eval(code: str) -> str:
    """Выполнение безопасных математических выражений на Python через `python_eval`.

    Args:
        code (str): Выражение на языке Python для вычисления.

    Returns:
        str: Строковое представление результата или описание ошибки.

    Examples:
        >>> agent_python_eval("abs(-42)")
        '42'
    """
    if not code or not code.strip():
        return "Ошибка: Пустое выражение для вычисления"

    try:
        if hasattr(python_eval, "invoke"):
            return str(python_eval.invoke(code.strip()))
        return str(python_eval(code.strip()))
    except Exception as exc:
        logger.error(f"[langchain_mcp_server] Ошибка выполнения agent_python_eval: {exc}")
        return f"Ошибка: {exc}"


@mcp.tool(
    name="agent_file_read",
    description="Чтение содержимого текстового файла проекта по относительному или абсолютному пути",
)
def agent_file_read(file_path: str) -> str:
    """Чтение текстового файла проекта через инструмент `file_read`.

    Args:
        file_path (str): Относительный или абсолютный путь к файлу.

    Returns:
        str: Содержимое файла (до 10 000 символов) или сообщение об ошибке.

    Examples:
        >>> "ai-tc" in agent_file_read("config.json")
        True
    """
    if not file_path or not file_path.strip():
        return "Ошибка: Не указан путь к файлу"

    try:
        if hasattr(file_read, "invoke"):
            return str(file_read.invoke(file_path.strip()))
        return str(file_read(file_path.strip()))
    except Exception as exc:
        logger.error(f"[langchain_mcp_server] Ошибка чтения файла agent_file_read: {exc}")
        return f"Ошибка: {exc}"


def main() -> int:
    """Запуск LangChain MCPServer в режиме STDIO.

    Returns:
        int: Код завершения (0 — успешно).

    Examples:
        >>> callable(main)
        True
    """
    logger.info("[langchain_mcp_server] Запуск LangChain AI Windows Admin MCPServer...")
    mcp.run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
