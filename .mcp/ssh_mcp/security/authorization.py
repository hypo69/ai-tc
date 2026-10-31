# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Авторизация и контроль файловых политик (Authorization)
# =============================================================================
# Description:
#   Контроль прав доступа на уровне хостов, категорий команд, повышения
#   привилегий (UAC / sudo) и защита от обхода каталогов (Path Traversal).
#
#   Зачем нужен этот модуль:
#     1. Гарантия того, что операции выполняются строго в рамках разрешённой
#        политики узла и файловой песочницы.
#     2. Явное разделение стандартного режима и контролируемого повышения
#        привилегий (sudo / Administrator).
#
# Usage Examples:
#   Python API:
#     from ssh_mcp.security.authorization import PathPolicyValidator
#     PathPolicyValidator.validate_path("/var/log/syslog", ["/var/log"])
#
# File: authorization.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.security
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:44:30
# =============================================================================

import posixpath
import re
from typing import List


class AuthorizationError(PermissionError):
    """Исключение при нарушении политики прав доступа или файловой безопасности."""


class PathPolicyValidator:
    """Контроллер проверки путей файловой системы и защиты от выхода за разрешённые каталоги.

    Examples:
        >>> PathPolicyValidator.validate_path("/var/log/app.log", ["/var/log"])
        '/var/log/app.log'
    """

    @staticmethod
    def validate_path(target_path: str, allowed_roots: List[str] = []) -> str:
        """Проверка пути на отсутствие Path Traversal (`..`, null-байты) и вхождение в белый список.

        Args:
            target_path (str): Проверяемый путь к файлу или каталогу.
            allowed_roots (List[str]): Список разрешённых корневых каталогов (пустой список — все без '..').

        Returns:
            str: Нормализованный безопасный путь.

        Exceptions:
            AuthorizationError: При обнаружении '..' или выходе за пределы `allowed_roots`.

        Examples:
            >>> PathPolicyValidator.validate_path("/opt/app/config.yaml", ["/opt/app"])
            '/opt/app/config.yaml'
        """
        if not target_path or "\x00" in target_path:
            raise AuthorizationError("Путь к файлу пуст или содержит недопустимые нулевые байты")

        raw_segments = re.split(r"[\\/]+", target_path.strip())
        if ".." in raw_segments:
            raise AuthorizationError(
                f"Обнаружена попытка обхода каталогов (Path Traversal) в пути: '{target_path}'"
            )

        normalized_target = PathPolicyValidator._normalize_generic(target_path)

        if allowed_roots:
            matched = False
            for root in allowed_roots:
                norm_root = PathPolicyValidator._normalize_generic(root).rstrip("/")
                if normalized_target == norm_root or normalized_target.startswith(norm_root + "/"):
                    matched = True
                    break
            if not matched:
                raise AuthorizationError(
                    f"Путь '{target_path}' выходит за пределы разрешённых каталогов политики: {allowed_roots}"
                )

        return target_path

    @staticmethod
    def _normalize_generic(path_str: str) -> str:
        """Унифицированная нормализация слешей и регистра диска для сравнения путей.

        Args:
            path_str (str): Исходная строка пути.

        Returns:
            str: Нормализованный путь с прямыми слешами.

        Examples:
            >>> PathPolicyValidator._normalize_generic("C:\\\\Temp\\\\file.txt")
            'c:/temp/file.txt'
        """
        replaced = path_str.replace("\\", "/")
        norm = posixpath.normpath(replaced)
        if len(norm) >= 2 and norm[1] == ":":
            norm = norm.lower()
        return norm
