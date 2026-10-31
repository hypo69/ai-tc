# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Маскирование и очистка секретов в выводах и логах (Secret Redactor)
# =============================================================================
# Description:
#   Автоматическая фильтрация паролей, приватных ключей SSH, Bearer-токенов,
#   API-ключей и строк подключения перед записью в SQLite и возвратом в MCP.
#
#   Зачем нужен этот модуль:
#     1. Гарантия того, что секреты никогда не попадают в журналы аудита,
#        таблицу command_runs или ответы для LLM.
#     2. Рекурсивная очистка как плоских строк, так и вложенных словарей/списков.
#
# Usage Examples:
#   Python API:
#     from ssh_mcp.security.secret_redactor import SecretRedactor
#     redactor = SecretRedactor()
#     clean = redactor.redact_text("password=MySecret123")
#
# File: secret_redactor.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.security
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:42:30
# =============================================================================

import re
from typing import Any, Dict, List


class SecretRedactor:
    """Фильтр для обнаружения и маскирования секретов в тексте и структурах данных.

    Attributes:
        sensitive_keys (set[str]): Набор имён полей словарей, подлежащих маскированию.

    Examples:
        >>> r = SecretRedactor()
        >>> r.redact_text("Authorization: Bearer secret_token_123")
        'Authorization: Bearer ***REDACTED***'
    """

    _PATTERNS: list[tuple[re.Pattern[str], str]] = [
        (
            re.compile(
                r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
                re.MULTILINE,
            ),
            "***REDACTED_PRIVATE_KEY***",
        ),
        (
            re.compile(r"(?i)(bearer\s+)[A-Za-z0-9\-._~+/]+=*"),
            r"\1***REDACTED***",
        ),
        (
            re.compile(
                r"(?i)((?:password|passwd|pwd|secret|api_key|apikey|token|passphrase)\s*[:=]\s*)(['\"]?)([^\s'\";,]+)\2"
            ),
            r"\1***REDACTED***",
        ),
    ]

    def __init__(self) -> None:
        """Инициализация редактора секретов.

        Examples:
            >>> redactor = SecretRedactor()
        """
        self.sensitive_keys: set[str] = {
            "password",
            "passwd",
            "pwd",
            "secret",
            "token",
            "api_key",
            "private_key",
            "passphrase",
            "credential",
            "new_password",
        }

    def redact_text(self, text: str) -> str:
        """Очистка строки от приватных ключей, паролей и токенов.

        Args:
            text (str): Исходная строка.

        Returns:
            str: Строка с замаскированными секретами.

        Examples:
            >>> r = SecretRedactor()
            >>> r.redact_text("user=admin password=supersecret")
            'user=admin password=***REDACTED***'
        """
        if not text:
            return ""
        cleaned = text
        for pattern, replacement in self._PATTERNS:
            cleaned = pattern.sub(replacement, cleaned)
        return cleaned

    def redact_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Рекурсивная очистка словаря параметров или результатов от секретов.

        Args:
            data (Dict[str, Any]): Исходный словарь.

        Returns:
            Dict[str, Any]: Копия словаря с замаскированными секретными значениями.

        Examples:
            >>> r = SecretRedactor()
            >>> r.redact_dict({"username": "root", "password": "123"})
            {'username': 'root', 'password': '***REDACTED***'}
        """
        if not data:
            return {}
        result: Dict[str, Any] = {}
        for key, value in data.items():
            key_lower = str(key).lower()
            if key_lower in self.sensitive_keys or any(s in key_lower for s in ("password", "secret", "private_key", "token")):
                result[key] = "***REDACTED***"
            elif isinstance(value, str):
                result[key] = self.redact_text(value)
            elif isinstance(value, dict):
                result[key] = self.redact_dict(value)
            elif isinstance(value, list):
                result[key] = self._redact_list(value)
            else:
                result[key] = value
        return result

    def _redact_list(self, items: List[Any]) -> List[Any]:
        """Очистка элементов списка от секретов.

        Args:
            items (List[Any]): Исходный список.

        Returns:
            List[Any]: Очищенный список.

        Examples:
            >>> r = SecretRedactor()
            >>> r._redact_list(["password=abc"])
            ['password=***REDACTED***']
        """
        cleaned_list: List[Any] = []
        for item in items:
            if isinstance(item, str):
                cleaned_list.append(self.redact_text(item))
            elif isinstance(item, dict):
                cleaned_list.append(self.redact_dict(item))
            elif isinstance(item, list):
                cleaned_list.append(self._redact_list(item))
            else:
                cleaned_list.append(item)
        return cleaned_list
