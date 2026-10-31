# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - MCP Management
# =============================================================================
# Description:
#   Эндпойнты управления серверами Model Context Protocol (MCP):
#   реестр серверов, сохранение конфигурации в config.json, переключение
#   активности, тестирование соединений и обнаружение инструментов.
#
# File: mcp.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers.admin
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-30 11:15:00
# =============================================================================

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from header import __root__
from logger import logger

admin_mcp_router = APIRouter(prefix="/api/admin/mcp", tags=["mcp"])
mcp_router = APIRouter(prefix="/api/mcp", tags=["mcp"])

_CONFIG_PATH = __root__ / "config.json"

# Предустановленные базовые MCP-серверы при пустой конфигурации
_DEFAULT_SERVERS: List[Dict[str, Any]] = [
    {
        "id": "filesystem",
        "name": "Local Filesystem MCP",
        "description": "Безопасный доступ к чтению и записи локальных файлов проекта",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "."],
        "url": None,
        "env": {},
        "enabled": True,
    },
    {
        "id": "sqlite",
        "name": "SQLite Knowledge DB",
        "description": "Инструменты запросов к локальным базам данных SQLite",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-sqlite", "--db-path", "data/windows_wikillm/knowledge.db"],
        "url": None,
        "env": {},
        "enabled": True,
    },
    {
        "id": "git",
        "name": "Git Repository Tools",
        "description": "Инспекция коммитов, веток, diff и статуса репозитория",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-git", "."],
        "url": None,
        "env": {},
        "enabled": False,
    },
    {
        "id": "fetch",
        "name": "HTTP Fetch & Web Search",
        "description": "Конвертация веб-страниц в чистый Markdown и поиск контента",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-fetch"],
        "url": None,
        "env": {},
        "enabled": True,
    },
]


class MCPServerModel(BaseModel):
    """Схема параметров конфигурации MCP-сервера."""

    id: Optional[str] = Field(default=None, description="Идентификатор сервера")
    name: str = Field(..., description="Отображаемое имя сервера")
    description: Optional[str] = Field(default="", description="Описание назначения сервера")
    transport: str = Field(default="stdio", description="Тип транспорта (stdio, sse, http)")
    command: Optional[str] = Field(default="python", description="Команда запуска для stdio")
    args: List[str] = Field(default_factory=list, description="Аргументы командной строки")
    url: Optional[str] = Field(default=None, description="URL для sse или streamable_http транспорта")
    env: Dict[str, str] = Field(default_factory=dict, description="Переменные окружения")
    enabled: bool = Field(default=True, description="Флаг активности сервера")


def _read_config_servers() -> List[Dict[str, Any]]:
    """Читает реестр серверов MCP из файла config.json."""
    if not _CONFIG_PATH.exists():
        return list(_DEFAULT_SERVERS)

    try:
        data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        langchain_sec = data.get("langchain") or {}
        servers_raw = langchain_sec.get("mcp_servers") or data.get("mcp_servers")
        if not servers_raw:
            return list(_DEFAULT_SERVERS)

        servers: List[Dict[str, Any]] = []
        if isinstance(servers_raw, dict):
            for s_id, cfg in servers_raw.items():
                item = dict(cfg) if isinstance(cfg, dict) else {}
                item["id"] = s_id
                item.setdefault("name", s_id)
                item.setdefault("description", "")
                item.setdefault("transport", "stdio")
                item.setdefault("enabled", True)
                servers.append(item)
        elif isinstance(servers_raw, list):
            servers = [s for s in servers_raw if isinstance(s, dict)]
        return servers or list(_DEFAULT_SERVERS)
    except Exception as exc:
        logger.warning(f"[MCPRouter] Ошибка чтения серверов из {_CONFIG_PATH}: {exc}")
        return list(_DEFAULT_SERVERS)


def _write_config_servers(servers: List[Dict[str, Any]]) -> None:
    """Записывает реестр серверов MCP в config.json."""
    if not _CONFIG_PATH.exists():
        return

    try:
        data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        if "langchain" not in data or not isinstance(data["langchain"], dict):
            data["langchain"] = {}

        servers_dict: Dict[str, Dict[str, Any]] = {}
        for s in servers:
            s_id = s.get("id") or s.get("name", "generic_server").lower().replace(" ", "-")
            servers_dict[s_id] = {
                "name": s.get("name", s_id),
                "description": s.get("description", ""),
                "transport": s.get("transport", "stdio"),
                "command": s.get("command"),
                "args": s.get("args", []),
                "url": s.get("url"),
                "env": s.get("env", {}),
                "enabled": s.get("enabled", True),
            }

        data["langchain"]["mcp_servers"] = servers_dict
        _CONFIG_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info(f"[MCPRouter] Реестр MCP серверов сохранён ({len(servers)} серверов)")
    except Exception as exc:
        logger.error(f"[MCPRouter] Ошибка записи в {_CONFIG_PATH}: {exc}")
        raise HTTPException(status_code=500, detail=f"Ошибка сохранения конфигурации: {exc}")


async def handle_list_servers() -> Dict[str, Any]:
    """Возвращает список зарегистрированных серверов MCP."""
    servers = _read_config_servers()
    return {"servers": servers, "total": len(servers)}


async def handle_get_server(server_id: str) -> Dict[str, Any]:
    """Возвращает метаданные сервера MCP по идентификатору."""
    servers = _read_config_servers()
    for s in servers:
        if s.get("id") == server_id:
            return s
    raise HTTPException(status_code=404, detail=f"MCP сервер '{server_id}' не найден")


async def handle_save_server(server: MCPServerModel) -> Dict[str, Any]:
    """Создает или обновляет конфигурацию MCP-сервера."""
    servers = _read_config_servers()
    s_id = server.id or server.name.lower().replace(" ", "-")
    server_data = server.model_dump()
    server_data["id"] = s_id

    existing_idx = next((i for i, s in enumerate(servers) if s.get("id") == s_id), None)
    if existing_idx is not None:
        servers[existing_idx] = server_data
    else:
        servers.append(server_data)

    _write_config_servers(servers)
    return {"status": "success", "server": server_data}


async def handle_update_server(server_id: str, server: MCPServerModel) -> Dict[str, Any]:
    """Обновляет конфигурацию существующего MCP-сервера."""
    server.id = server_id
    return await handle_save_server(server)


async def handle_delete_server(server_id: str) -> Dict[str, Any]:
    """Удаляет сервер MCP из конфигурации."""
    servers = _read_config_servers()
    new_servers = [s for s in servers if s.get("id") != server_id]
    if len(new_servers) == len(servers):
        raise HTTPException(status_code=404, detail=f"Сервер '{server_id}' не найден")
    _write_config_servers(new_servers)
    return {"status": "success", "deleted": server_id}


async def handle_toggle_server(server_id: str) -> Dict[str, Any]:
    """Переключает статус активности MCP-сервера."""
    servers = _read_config_servers()
    target = None
    for s in servers:
        if s.get("id") == server_id:
            s["enabled"] = not s.get("enabled", True)
            target = s
            break
    if not target:
        raise HTTPException(status_code=404, detail=f"Сервер '{server_id}' не найден")
    _write_config_servers(servers)
    return {"status": "success", "id": server_id, "enabled": target["enabled"]}


async def handle_test_server(server_id: Optional[str] = None, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Тестирует соединение с MCP-сервером и возвращает обнаруженные инструменты."""
    target_cfg = None
    if server_id:
        servers = _read_config_servers()
        for s in servers:
            if s.get("id") == server_id:
                target_cfg = s
                break
    elif data:
        target_cfg = data

    if not target_cfg:
        raise HTTPException(status_code=400, detail="Не указана конфигурация сервера для тестирования")

    s_id = server_id or target_cfg.get("id") or target_cfg.get("name", "test_server")
    try:
        from src.ai.agents.mcp_client import MCPClientManager
        return await MCPClientManager.test_server_connection(target_cfg, s_id)
    except Exception as exc:
        return {
            "status": "error",
            "message": f"Ошибка выполнения теста: {exc}",
            "tools": [],
            "latency_ms": 0,
        }


async def handle_list_tools() -> Dict[str, Any]:
    """Возвращает список всех доступных инструментов от подключенных MCP-серверов."""
    try:
        from src.ai.agents.mcp_client import MCPClientManager
        async with MCPClientManager(str(_CONFIG_PATH)) as mcp:
            tools = await mcp.get_tools()
            tool_list = []
            for t in tools:
                tool_list.append({
                    "name": getattr(t, "name", str(t)),
                    "description": getattr(t, "description", ""),
                    "args_schema": getattr(t, "args", {}),
                })
            return {"tools": tool_list, "total": len(tool_list)}
    except Exception as exc:
        logger.warning(f"[MCPRouter] Ошибка получения MCP-инструментов: {exc}")
        # Запасной список встроенных инструментов
        fallback_tools = [
            {"name": "filesystem_read", "description": "Чтение содержимого файлов проекта", "args_schema": {"path": "str"}},
            {"name": "filesystem_write", "description": "Безопасная запись файлов в рабочую директорию", "args_schema": {"path": "str", "content": "str"}},
            {"name": "sqlite_query", "description": "Выполнение SQL SELECT запросов к базе знаний", "args_schema": {"sql": "str"}},
            {"name": "fetch_url", "description": "Загрузка веб-страницы и конвертация в Markdown", "args_schema": {"url": "str"}},
        ]
        return {"tools": fallback_tools, "total": len(fallback_tools)}


# Регистрация маршрутов на обоих роутерах
for r in (admin_mcp_router, mcp_router):
    r.add_api_route("/servers", handle_list_servers, methods=["GET"], summary="Список MCP серверов")
    r.add_api_route("/servers/{server_id}", handle_get_server, methods=["GET"], summary="Получить MCP сервер")
    r.add_api_route("/servers", handle_save_server, methods=["POST"], summary="Создать MCP сервер")
    r.add_api_route("/servers/{server_id}", handle_update_server, methods=["PUT"], summary="Обновить MCP сервер")
    r.add_api_route("/servers/{server_id}", handle_delete_server, methods=["DELETE"], summary="Удалить MCP сервер")
    r.add_api_route("/servers/{server_id}/toggle", handle_toggle_server, methods=["POST"], summary="Переключить активность MCP сервера")
    r.add_api_route("/servers/{server_id}/test", handle_test_server, methods=["POST"], summary="Тестировать MCP сервер")
    r.add_api_route("/test", handle_test_server, methods=["POST"], summary="Тестировать произвольную конфигурацию MCP")
    r.add_api_route("/tools", handle_list_tools, methods=["GET"], summary="Список MCP инструментов")
