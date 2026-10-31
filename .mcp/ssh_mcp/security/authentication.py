# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Аутентификация и защита транспорта Remote MCP
# =============================================================================
# Description:
#   Проверка Bearer-токенов, заголовка Origin и настроек TLS для удалённого
#   режима работы (Remote MCP Server по протоколу Streamable HTTP).
#
#   Зачем нужен этот модуль:
#     1. Защита административного HTTP-интерфейса от несанкционированного
#        доступа и DNS-rebinding / CSRF атак (Разделы 6, 10, 11 ТЗ).
#     2. Запрет открытия неаутентифицированного интерфейса на 0.0.0.0.
#
# Usage Examples:
#   Python API:
#     from ssh_mcp.security.authentication import RemoteMCPAuthenticator
#     auth = RemoteMCPAuthenticator(expected_token="secret", allowed_origins=["https://127.0.0.1"])
#     auth.verify_request(authorization_header="Bearer secret", origin="https://127.0.0.1")
#
# File: authentication.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.security
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:44:00
# =============================================================================

import hmac
from typing import List, Optional


class AuthenticationError(PermissionError):
    """Исключение при отказе в аутентификации к Remote MCP Server."""


class RemoteMCPAuthenticator:
    """Аутентификатор запросов к удалённому MCP-серверу (Streamable HTTP).

    Attributes:
        expected_token (str): Ожидаемый секретный токен доступа.
        allowed_origins (List[str]): Список доверенных заголовков Origin.

    Examples:
        >>> auth = RemoteMCPAuthenticator(expected_token="tok-123", allowed_origins=["https://127.0.0.1"])
        >>> auth.verify_request("Bearer tok-123", "https://127.0.0.1")
        True
    """

    def __init__(
        self, expected_token: str, allowed_origins: Optional[List[str]] = []
    ) -> None:
        """Инициализация аутентификатора Remote MCP.

        Args:
            expected_token (str): Секретный токен для проверки заголовка Authorization.
            allowed_origins (Optional[List[str]]): Разрешённые значения Origin.
                                                   Значение по умолчанию: [].

        Examples:
            >>> auth = RemoteMCPAuthenticator("my_token")
        """
        self.expected_token = expected_token
        self.allowed_origins: List[str] = allowed_origins if allowed_origins else [
            "http://127.0.0.1",
            "https://127.0.0.1",
        ]

    def verify_request(
        self, authorization_header: str = "", origin: str = ""
    ) -> bool:
        """Проверка заголовков Authorization (Bearer) и Origin.

        Args:
            authorization_header (str): Значение HTTP-заголовка Authorization.
            origin (str): Значение HTTP-заголовка Origin (если передан клиентом).

        Returns:
            bool: True при успешной проверке подлинности и источника запроса.

        Exceptions:
            AuthenticationError: При неверном токене, отсутствии заголовка или запрещённом Origin.

        Examples:
            >>> auth = RemoteMCPAuthenticator("secret-1", ["https://localhost"])
            >>> auth.verify_request("Bearer secret-1", "https://localhost")
            True
        """
        if not self.expected_token:
            raise AuthenticationError("Токен аутентификации Remote MCP не настроен на сервере")

        if not authorization_header or not authorization_header.startswith("Bearer "):
            raise AuthenticationError("Отсутствует или некорректен заголовок Authorization Bearer")

        provided_token = authorization_header[len("Bearer "):].strip()
        if not hmac.compare_digest(provided_token.encode("utf-8"), self.expected_token.encode("utf-8")):
            raise AuthenticationError("Недействительный токен доступа к Remote MCP Server")

        if origin and "*" not in self.allowed_origins:
            if origin not in self.allowed_origins:
                raise AuthenticationError(f"Запрещённый заголовок Origin: '{origin}'")

        return True

    @staticmethod
    def validate_network_binding(host: str, tls_enabled: bool, has_token: bool) -> bool:
        """Проверка безопасности сетевой привязки удалённого сервера.

        Запрещает привязку к внешним интерфейсам (например, `0.0.0.0`) без
        одновременного включения TLS и токена аутентификации (Раздел 11 ТЗ).

        Args:
            host (str): Сетевой адрес привязки.
            tls_enabled (bool): Включён ли TLS.
            has_token (bool): Задан ли непустой токен аутентификации.

        Returns:
            bool: True, если конфигурация безопасна.

        Exceptions:
            AuthenticationError: При попытке небезопасной публикации на внешнем интерфейсе.

        Examples:
            >>> RemoteMCPAuthenticator.validate_network_binding("127.0.0.1", False, True)
            True
        """
        is_loopback = host in ("127.0.0.1", "localhost", "::1")
        if not is_loopback and (not tls_enabled or not has_token):
            raise AuthenticationError(
                f"Запрещена привязка Remote MCP к '{host}' без включённого TLS и аутентификации"
            )
        return True
