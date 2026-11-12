# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Клиент SSH MCP Server для оркестратора ai-tc (MCP Client)
# =============================================================================
# Description:
#   Программный клиент для взаимодействия с SSH MCP Server как напрямую через
#   модули `ssh-mcp-core`, так и по протоколу Streamable HTTP / Remote MCP.
#
# File: client.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 14:20:00
# =============================================================================

from typing import Any, Dict, Optional
import httpx

from .bootstrap import SSHMCPRuntime, create_runtime
from .server import build_mcp_server


class SSHMCPClient:
    """Клиент для вызова инструментов SSH MCP Server из оркестратора ai-tc.

    Attributes:
        runtime (SSHMCPRuntime): Локальный рантайм ядра.
        modules (Dict[str, object]): Набор инициализированных модулей инструментов.

    Examples:
        >>> client = SSHMCPClient(create_runtime(db_path=":memory:"))
    """

    def __init__(self, runtime: Optional[SSHMCPRuntime] = False) -> None:  # type: ignore[assignment]
        """Инициализация клиента SSH MCP.

        Args:
            runtime (Optional[SSHMCPRuntime]): Контейнер сервисов ядра.

        Examples:
            >>> c = SSHMCPClient(create_runtime(db_path=":memory:"))
        """
        _mcp, mods, rt = build_mcp_server(runtime)
        self.runtime = rt
        self.modules = mods

    async def invoke_local(
        self, group: str, method_name: str, **kwargs: Any
    ) -> Dict[str, Any]:
        """Прямой вызов метода инструментальной группы в процессе ai-tc.

        Args:
            group (str): Имя группы ('connection', 'execution', 'system', 'services' и др.).
            method_name (str): Имя метода (например, 'system_memory').
            **kwargs (Any): Именованные параметры вызова.

        Returns:
            Dict[str, Any]: Стандартизированный ответ MCP.

        Examples:
            >>> import asyncio
            >>> c = SSHMCPClient(create_runtime(db_path=":memory:"))
            >>> res = asyncio.run(c.invoke_local("system", "system_memory", host_id="localhost"))
            >>> res["success"]
            True
        """
        mod = self.modules.get(group)
        if not mod or not hasattr(mod, method_name):
            return self.runtime.normalizer.failure(
                host=str(kwargs.get("host_id", "localhost")),
                platform="windows",
                operation=f"{group}.{method_name}",
                code="TOOL_NOT_FOUND",
                message=f"Инструмент '{group}.{method_name}' не найден",
            )
        fn = getattr(mod, method_name)
        return await fn(**kwargs)

    @staticmethod
    async def check_remote_health(
        base_url: str, api_token: str, origin: str = "https://127.0.0.1"
    ) -> Dict[str, Any]:
        """Проверка доступности удалённого сервера Remote MCP по HTTP/HTTPS.

        Args:
            base_url (str): Базовый адрес сервера (например, 'http://127.0.0.1:8765').
            api_token (str): Bearer-токен аутентификации.
            origin (str): Заголовок Origin.

        Returns:
            Dict[str, Any]: Ответ эндпоинта `/api/ssh-mcp/health`.

        Examples:
            >>> pass
        """
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Origin": origin,
        }
        client_timeout = httpx.Timeout(connect=5.0, read=15.0, write=10.0, pool=5.0)
        async with httpx.AsyncClient(timeout=client_timeout) as http_client:
            resp = await http_client.get(
                f"{base_url.rstrip('/')}/api/ssh-mcp/health",
                headers=headers,
                timeout=client_timeout,
            )
            return resp.json()
