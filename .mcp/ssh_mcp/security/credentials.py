# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Защищённый менеджер учётных данных (Credential Manager)
# =============================================================================
# Description:
#   Разрешение ссылок `credential_ref` в реальные секреты (приватные ключи SSH,
#   пароли, сокеты SSH Agent) без сохранения секретов в базе данных SQLite.
#
#   Зачем нужен этот модуль:
#     1. Отделение конфигурации хостов от секретов (Раздел 6 ТЗ).
#     2. Поддержка префиксов ссылок: `env:VAR_NAME`, `keyfile:/path/to/key`,
#        `ssh_key:name` и память процесса (для изолированных тестов и рантайма).
#
# Usage Examples:
#   Python API:
#     from ssh_mcp.security.credentials import CredentialManager
#     cm = CredentialManager(creds_repo)
#     cm.register_memory_secret("ref-1", "my-secret")
#
# File: credentials.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.security
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:43:00
# =============================================================================

import os
from pathlib import Path
from typing import Dict, Optional
from ..storage.repositories.host_credentials_repo import HostCredentialsRepository


class CredentialManager:
    """Безопасное разрешение ссылок `credential_ref` без хранения паролей в SQLite.

    Attributes:
        repo (HostCredentialsRepository): Репозиторий ссылок на секреты.

    Examples:
        >>> from ssh_mcp.storage.database import DatabaseManager
        >>> db = DatabaseManager(":memory:")
        >>> _ = db.initialize()
        >>> cm = CredentialManager(HostCredentialsRepository(db))
        >>> cm.register_memory_secret("mem:test", "secret_val", "h1")
        True
        >>> cm.resolve_secret("mem:test")
        'secret_val'
    """

    def __init__(self, repo: HostCredentialsRepository) -> None:
        """Инициализация менеджера учётных данных.

        Args:
            repo (HostCredentialsRepository): Репозиторий метаданных секретов.

        Examples:
            >>> db = DatabaseManager(":memory:")
            >>> _ = db.initialize()
            >>> cm = CredentialManager(HostCredentialsRepository(db))
        """
        self.repo = repo
        self._memory_vault: Dict[str, str] = {}

    def register_memory_secret(
        self, credential_ref: str, secret_value: str, host_id: str = "localhost"
    ) -> bool:
        """Регистрация секрета в оперативной памяти процесса и ссылки в БД.

        Пароль сохраняется исключительно в защищённом словаре в памяти,
        а в таблицу `host_credentials` записывается только мета-ссылка.

        Args:
            credential_ref (str): Уникальная ссылка на секрет.
            secret_value (str): Значение секрета.
            host_id (str): Идентификатор узла.

        Returns:
            bool: True при успешной регистрации.

        Examples:
            >>> db = DatabaseManager(":memory:")
            >>> _ = db.initialize()
            >>> cm = CredentialManager(HostCredentialsRepository(db))
            >>> cm.register_memory_secret("ref:1", "topsecret", "srv-1")
            True
        """
        if not credential_ref or not secret_value:
            return False
        self._memory_vault[credential_ref] = secret_value
        self.repo.save_reference(
            credential_ref=credential_ref,
            host_id=host_id,
            storage_provider="memory_vault",
            account_name=credential_ref,
        )
        return True

    def resolve_secret(self, credential_ref: Optional[str] = "") -> str:
        """Разрешение ссылки `credential_ref` в значение секрета или путь к ключу.

        Поддерживаемые форматы `credential_ref`:
        - `mem:...` или ключ, зарегистрированный в `_memory_vault`
        - `env:VAR_NAME` — чтение из переменной окружения `VAR_NAME`
        - `keyfile:/path/to/id_ed25519` — проверенный путь к файлу приватного ключа
        - `ssh_key:name` — поиск ключа в `~/.ssh/<name>` или переменной окружения

        Args:
            credential_ref (Optional[str]): Ссылка на секрет.
                                            Значение по умолчанию: ''.

        Returns:
            str: Разрешённое значение секрета или '', если секрет не найден.

        Examples:
            >>> db = DatabaseManager(":memory:")
            >>> _ = db.initialize()
            >>> cm = CredentialManager(HostCredentialsRepository(db))
            >>> cm.resolve_secret("")
            ''
        """
        if not credential_ref:
            return ""

        if credential_ref in self._memory_vault:
            return self._memory_vault[credential_ref]

        if credential_ref.startswith("env:"):
            env_name = credential_ref.split(":", 1)[1].strip()
            return os.environ.get(env_name, "")

        if credential_ref.startswith("keyfile:"):
            key_path = Path(credential_ref.split(":", 1)[1].strip()).expanduser()
            if key_path.exists() and key_path.is_file():
                return str(key_path.resolve())
            return ""

        if credential_ref.startswith("ssh_key:"):
            key_name = credential_ref.split(":", 1)[1].strip()
            env_override = os.environ.get(f"SSH_KEY_{key_name.upper()}", "")
            if env_override:
                return env_override
            candidate = Path.home() / ".ssh" / key_name
            if candidate.exists():
                return str(candidate.resolve())
            return ""

        return os.environ.get(credential_ref, "")
