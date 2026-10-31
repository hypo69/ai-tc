# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Верификация SSH отпечатков серверов (Host Verification)
# =============================================================================
# Description:
#   Обязательная проверка публичных ключей SSH-серверов по базе доверенных
#   ключей `host_keys` и файлу `known_hosts`. Отклоняет неизвестные или
#   изменившиеся ключи в режиме `strict`.
#
#   Зачем нужен этот модуль:
#     1. Защита от подмены SSH-сервера (MITM) согласно разделам 6 и 14 ТЗ.
#     2. Вычисление канонического SHA-256 отпечатка ключа.
#
# Usage Examples:
#   Python API:
#     from ssh_mcp.security.host_verification import HostKeyVerifier
#     verifier = HostKeyVerifier(host_keys_repo, mode="strict")
#     verifier.verify_fingerprint("srv-01", "10.0.0.1", 22, "ssh-ed25519", "SHA256:...")
#
# File: host_verification.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.security
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:43:30
# =============================================================================

import base64
import hashlib
from pathlib import Path
from typing import Dict, Literal
from ..storage.repositories.host_keys_repo import HostKeysRepository


class HostVerificationError(PermissionError):
    """Исключение при отклонении неизвестного или подменённого SSH-ключа хоста."""


class HostKeyVerifier:
    """Контроллер проверки публичных SSH-ключей удалённых узлов.

    Attributes:
        repo (HostKeysRepository): Репозиторий доверенных отпечатков в БД.
        mode (Literal['strict', 'warn']): Режим проверки ('strict' отклоняет неизвестные).
        known_hosts_path (str): Путь к файлу known_hosts.

    Examples:
        >>> from ssh_mcp.storage.database import DatabaseManager
        >>> db = DatabaseManager(":memory:")
        >>> _ = db.initialize()
        >>> v = HostKeyVerifier(HostKeysRepository(db), mode="strict")
        >>> v.trust_host_key("h1", "10.0.0.1", 22, "ssh-ed25519", "SHA256:xyz")
        True
        >>> v.verify_fingerprint("h1", "10.0.0.1", 22, "ssh-ed25519", "SHA256:xyz")
        True
    """

    def __init__(
        self,
        repo: HostKeysRepository,
        mode: Literal["strict", "warn"] = "strict",
        known_hosts_path: str = "./data/known_hosts",
    ) -> None:
        """Инициализация верификатора ключей хостов.

        Args:
            repo (HostKeysRepository): Репозиторий таблицы `host_keys`.
            mode (Literal['strict', 'warn']): Политика верификации.
            known_hosts_path (str): Путь к файлу known_hosts.

        Examples:
            >>> db = DatabaseManager(":memory:")
            >>> _ = db.initialize()
            >>> verifier = HostKeyVerifier(HostKeysRepository(db))
        """
        self.repo = repo
        self.mode: Literal["strict", "warn"] = mode
        self.known_hosts_path = known_hosts_path

    @staticmethod
    def compute_sha256_fingerprint(raw_key_bytes: bytes) -> str:
        """Вычисление отпечатка публичного ключа в формате `SHA256:<base64>`.

        Args:
            raw_key_bytes (bytes): Бинарное представление публичного ключа SSH.

        Returns:
            str: Строка отпечатка `SHA256:...`.

        Examples:
            >>> fp = HostKeyVerifier.compute_sha256_fingerprint(b"test-public-key")
            >>> fp.startswith("SHA256:")
            True
        """
        digest = hashlib.sha256(raw_key_bytes).digest()
        b64 = base64.b64encode(digest).decode("ascii").rstrip("=")
        return f"SHA256:{b64}"

    def trust_host_key(
        self, host_id: str, hostname: str, port: int, key_type: str, fingerprint: str
    ) -> bool:
        """Явная регистрация доверенного SSH-ключа узла в базе данных.

        Args:
            host_id (str): Идентификатор узла.
            hostname (str): Сетевой адрес или имя хоста.
            port (int): Порт SSH.
            key_type (str): Алгоритм ключа.
            fingerprint (str): Отпечаток SHA256.

        Returns:
            bool: True при успешной регистрации.

        Examples:
            >>> db = DatabaseManager(":memory:")
            >>> _ = db.initialize()
            >>> v = HostKeyVerifier(HostKeysRepository(db))
            >>> v.trust_host_key("h1", "10.0.0.1", 22, "ssh-ed25519", "SHA256:111")
            True
        """
        return self.repo.save_host_key(host_id, hostname, port, key_type, fingerprint)

    def verify_fingerprint(
        self, host_id: str, hostname: str, port: int, key_type: str, presented_fingerprint: str
    ) -> bool:
        """Проверка предъявленного сервером отпечатка ключа.

        В режиме `strict`:
        - Если ключ отсутствует в БД и в файле `known_hosts`, выбрасывается `HostVerificationError`.
        - Если предъявленный отпечаток не совпадает с сохранённым (попытка подмены сервера),
          всегда выбрасывается `HostVerificationError`.

        Args:
            host_id (str): Идентификатор узла.
            hostname (str): Имя или IP хоста.
            port (int): Порт SSH.
            key_type (str): Тип ключа.
            presented_fingerprint (str): Предъявленный сервером отпечаток.

        Returns:
            bool: True при успешном подтверждении подлинности ключа.

        Exceptions:
            HostVerificationError: Если ключ неизвестен (в режиме strict) или не совпадает.

        Examples:
            >>> db = DatabaseManager(":memory:")
            >>> _ = db.initialize()
            >>> v = HostKeyVerifier(HostKeysRepository(db), mode="strict")
            >>> _ = v.trust_host_key("h1", "10.0.0.1", 22, "ssh-ed25519", "SHA256:abc")
            >>> v.verify_fingerprint("h1", "10.0.0.1", 22, "ssh-ed25519", "SHA256:abc")
            True
        """
        if not presented_fingerprint:
            raise HostVerificationError("Сервер не предоставил отпечаток публичного ключа SSH")

        stored: Dict[str, object] = self.repo.get_host_key(host_id)
        if stored:
            expected_fp = str(stored.get("fingerprint", ""))
            if expected_fp != presented_fingerprint:
                raise HostVerificationError(
                    f"Обнаружена подмена SSH-ключа для хоста '{host_id}': "
                    f"ожидался '{expected_fp}', получен '{presented_fingerprint}'"
                )
            return True

        if self._check_known_hosts_file(hostname, presented_fingerprint):
            self.repo.save_host_key(host_id, hostname, port, key_type, presented_fingerprint)
            return True

        if self.mode == "strict":
            raise HostVerificationError(
                f"Неизвестный SSH host key для узла '{host_id}' ({hostname}:{port}): "
                f"отпечаток '{presented_fingerprint}' не найден в реестре доверенных ключей"
            )

        self.repo.save_host_key(host_id, hostname, port, key_type, presented_fingerprint)
        return True

    def _check_known_hosts_file(self, hostname: str, presented_fingerprint: str) -> bool:
        """Проверка наличия отпечатка или ключа хоста в файле known_hosts.

        Args:
            hostname (str): Имя или IP-адрес хоста.
            presented_fingerprint (str): Отпечаток SHA256.

        Returns:
            bool: True, если запись найдена и совпадает.

        Examples:
            >>> db = DatabaseManager(":memory:")
            >>> _ = db.initialize()
            >>> v = HostKeyVerifier(HostKeysRepository(db), known_hosts_path="./nonexistent_kh")
            >>> v._check_known_hosts_file("10.0.0.1", "SHA256:abc")
            False
        """
        kh_file = Path(self.known_hosts_path)
        if not kh_file.exists() or not kh_file.is_file():
            return False

        for raw_line in kh_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 3:
                continue
            hosts_part, _key_type, key_body = parts[0], parts[1], parts[2]
            host_tokens = hosts_part.split(",")
            if hostname not in host_tokens:
                continue
            if key_body == presented_fingerprint:
                return True
            try:
                decoded = base64.b64decode(key_body)
                computed = self.compute_sha256_fingerprint(decoded)
                if computed == presented_fingerprint:
                    return True
            except Exception:
                continue
        return False
