# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Транспорт взаимодействия с удалённым MCP-агентом (Remote MCP)
# =============================================================================
# Description:
#   Клиентский транспорт для маршрутизации команд из центрального координатора
#   Local MCP Server на удалённый узел, где установлен Remote MCP Server
#   (Гибридный режим — Раздел 3.3 ТЗ).
#
#   Зачем нужен этот модуль:
#     1. Прозрачное делегирование вызовов удалённому MCP-агенту по HTTPS с
#        аутентификацией Bearer-токеном.
#     2. Единый интерфейс BaseTransport, позволяющий переключать узел между
#        SSH и Remote MCP без изменения бизнес-логики.
#
# Usage Examples:
#   Python API:
#     from ssh_mcp.transports.remote_mcp_transport import RemoteMCPTransport
#     tr = RemoteMCPTransport("remote-win-01", "https://10.0.0.5:8765/mcp", "token")
#
# File: remote_mcp_transport.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.transports
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:47:30
# =============================================================================

import hashlib
import time
from typing import Dict, List, Optional
import httpx

from .base import BaseTransport, RawExecutionResult


class RemoteMCPTransport(BaseTransport):
    """Транспорт гибридного взаимодействия с удалённым MCP-сервером по HTTPS.

    Attributes:
        host_id (str): Идентификатор целевого узла.
        endpoint_url (str): Полный URL удалённого MCP-сервера.
        api_token (str): Bearer-токен аутентификации.
        verify_tls (bool): Признак строгой проверки TLS-сертификата.

    Examples:
        >>> tr = RemoteMCPTransport("srv-remote", "https://127.0.0.1:8765/api/execute", "secret")
        >>> tr.host_id
        'srv-remote'
    """

    def __init__(
        self,
        host_id: str,
        endpoint_url: str,
        api_token: str = "",
        verify_tls: bool = True,
    ) -> None:
        """Инициализация транспорта Remote MCP.

        Args:
            host_id (str): Идентификатор узла.
            endpoint_url (str): URL удалённого агента.
            api_token (str): Токен доступа для заголовка Authorization.
            verify_tls (bool): Проверять ли сертификат сервера.

        Examples:
            >>> tr = RemoteMCPTransport("h1", "https://127.0.0.1:8765")
        """
        super().__init__(host_id=host_id)
        self.endpoint_url = endpoint_url
        self.api_token = api_token
        self.verify_tls = verify_tls

    async def connect(self) -> bool:
        """Проверка конфигурации и перевод транспорта в активное состояние.

        Returns:
            bool: True, если URL и токен валидны.

        Exceptions:
            ConnectionError: Если отсутствует URL или токен.

        Examples:
            >>> import asyncio
            >>> tr = RemoteMCPTransport("h1", "https://127.0.0.1:8765", "tok")
            >>> asyncio.run(tr.connect())
            True
        """
        if not self.endpoint_url:
            raise ConnectionError(f"Не задан URL Remote MCP для узла '{self.host_id}'")
        if not self.api_token:
            raise ConnectionError(f"Не задан токен аутентификации для Remote MCP узла '{self.host_id}'")
        self.connected = True
        return True

    async def disconnect(self) -> bool:
        """Закрытие сессии Remote MCP.

        Returns:
            bool: True.

        Examples:
            >>> import asyncio
            >>> tr = RemoteMCPTransport("h1", "https://127.0.0.1:8765", "tok")
            >>> asyncio.run(tr.disconnect())
            True
        """
        self.connected = False
        return True

    async def is_alive(self) -> bool:
        """Проверка активности транспорта Remote MCP.

        Returns:
            bool: Состояние флага `connected`.

        Examples:
            >>> import asyncio
            >>> tr = RemoteMCPTransport("h1", "https://127.0.0.1:8765", "tok")
            >>> asyncio.run(tr.is_alive())
            False
        """
        return self.connected

    async def get_fingerprint(self) -> str:
        """Вычисление идентификационного SHA-256 отпечатка конечной точки Remote MCP.

        Returns:
            str: Строка `SHA256:...`.

        Examples:
            >>> import asyncio
            >>> tr = RemoteMCPTransport("h1", "https://127.0.0.1:8765", "tok")
            >>> asyncio.run(tr.get_fingerprint()).startswith("SHA256:")
            True
        """
        digest = hashlib.sha256(self.endpoint_url.encode("utf-8")).hexdigest()[:43]
        return f"SHA256:{digest}"

    async def execute_command(
        self,
        command: str,
        args: Optional[List[str]] = [],
        env: Optional[Dict[str, str]] = {},
        shell: str = "default",
        timeout: int = 60,
        elevate: bool = False,
    ) -> RawExecutionResult:
        """Отправка запроса на выполнение команды удалённому MCP-серверу.

        Args:
            command (str): Исполняемая команда.
            args (Optional[List[str]]): Позиционные аргументы.
                                        Значение по умолчанию: [].
            env (Optional[Dict[str, str]]): Переменные окружения.
                                            Значение по умолчанию: {}.
            shell (str): Целевая оболочка.
            timeout (int): Таймаут ожидания ответа в секундах.
            elevate (bool): Флаг повышения привилегий.

        Returns:
            RawExecutionResult: Результат от удалённого агента.

        Examples:
            >>> pass
        """
        if not self.connected:
            await self.connect()

        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Origin": "https://127.0.0.1",
            "Content-Type": "application/json",
        }
        payload = {
            "command": command,
            "args": args if args else [],
            "env": env if env else {},
            "shell": shell,
            "timeout": timeout,
            "elevate": elevate,
        }
        started = time.perf_counter()
        async with httpx.AsyncClient(verify=self.verify_tls, timeout=timeout) as client:
            response = await client.post(self.endpoint_url, json=payload, headers=headers)
            response.raise_for_status()
            body = response.json()

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return RawExecutionResult(
            exit_code=int(body.get("exit_code", 0)),
            stdout=str(body.get("stdout", "")),
            stderr=str(body.get("stderr", "")),
            duration_ms=int(body.get("duration_ms", elapsed_ms)),
        )
