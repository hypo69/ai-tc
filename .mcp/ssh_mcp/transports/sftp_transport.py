# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Потоковый SFTP-транспорт с контролем SHA-256 и лимитов размера
# =============================================================================
# Description:
#   Передача, чтение, запись и инспекция файлов через SFTP (или локальную ФС
#   для локального транспорта) с проверкой файловых политик (PathPolicyValidator),
#   ограничением максимального размера и проверкой целостности SHA-256.
#
#   Зачем нужен этот модуль:
#     1. Выполнение требований раздела 4.6 ТЗ (потоковая передача, SHA-256,
#        квоты размера, защита от выхода за разрешённые каталоги).
#     2. Автоматическая фиксация каждой передачи в таблице `file_transfers`.
#
# Usage Examples:
#   Python API:
#     from ssh_mcp.transports.sftp_transport import SFTPFileManager
#     mgr = SFTPFileManager(allowed_roots=["/var/log"], max_transfer_mb=50)
#
# File: sftp_transport.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.transports
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:47:00
# =============================================================================

import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..security.authorization import AuthorizationError, PathPolicyValidator
from ..storage.repositories.file_transfers_repo import FileTransfersRepository


class SFTPFileManager:
    """Менеджер безопасной потоковой передачи и чтения/записи файлов с контролем SHA-256.

    Attributes:
        allowed_roots (List[str]): Список разрешённых корневых каталогов.
        max_transfer_bytes (int): Максимальный допустимый размер файла в байтах.
        transfers_repo (Optional[FileTransfersRepository]): Репозиторий журналирования передач.

    Examples:
        >>> mgr = SFTPFileManager(allowed_roots=[], max_transfer_mb=10)
        >>> mgr.max_transfer_bytes == 10 * 1024 * 1024
        True
    """

    CHUNK_SIZE: int = 65536

    def __init__(
        self,
        allowed_roots: Optional[List[str]] = [],
        max_transfer_mb: int = 100,
        transfers_repo: Optional[FileTransfersRepository] = False,  # type: ignore[assignment]
    ) -> None:
        """Инициализация файлового менеджера SFTP.

        Args:
            allowed_roots (Optional[List[str]]): Белый список базовых путей.
                                                 Значение по умолчанию: [].
            max_transfer_mb (int): Лимит передаваемого файла в мегабайтах.
            transfers_repo (Optional[FileTransfersRepository]): Репозиторий таблицы file_transfers.

        Examples:
            >>> mgr = SFTPFileManager(max_transfer_mb=25)
        """
        self.allowed_roots: List[str] = allowed_roots if allowed_roots else []
        self.max_transfer_bytes: int = max(1, max_transfer_mb) * 1024 * 1024
        self.transfers_repo = transfers_repo

    def validate_and_resolve(self, path_str: str) -> str:
        """Проверка пути по файловой политике безопасности.

        Args:
            path_str (str): Путь к файлу или каталогу.

        Returns:
            str: Проверенный путь.

        Exceptions:
            AuthorizationError: При попытке обхода каталога или нарушении политики.

        Examples:
            >>> mgr = SFTPFileManager(allowed_roots=["/tmp"])
            >>> mgr.validate_and_resolve("/tmp/data.txt")
            '/tmp/data.txt'
        """
        return PathPolicyValidator.validate_path(path_str, self.allowed_roots)

    async def stream_write_local(
        self, host_id: str, destination_path: str, content_bytes: bytes, expected_sha256: str = ""
    ) -> Dict[str, Any]:
        """Потоковая запись данных в файл с проверкой лимита размера и SHA-256.

        Args:
            host_id (str): Идентификатор узла.
            destination_path (str): Целевой путь записи.
            content_bytes (bytes): Содержимое для записи.
            expected_sha256 (str): Ожидаемый SHA-256 хэш (если задан — проверяется до записи).

        Returns:
            Dict[str, Any]: Метаданные записанного файла (size_bytes, sha256, path).

        Exceptions:
            ValueError: При превышении лимита размера или несовпадении SHA-256.
            AuthorizationError: При нарушении файловой политики.

        Examples:
            >>> import asyncio, tempfile
            >>> mgr = SFTPFileManager(max_transfer_mb=1)
            >>> with tempfile.NamedTemporaryFile(delete=False) as tf:
            ...     p = tf.name
            >>> res = asyncio.run(mgr.stream_write_local("localhost", p, b"hello world"))
            >>> res["size_bytes"]
            11
        """
        safe_dest = self.validate_and_resolve(destination_path)
        size_bytes = len(content_bytes)
        if size_bytes > self.max_transfer_bytes:
            raise ValueError(
                f"Размер файла ({size_bytes} байт) превышает установленный лимит ({self.max_transfer_bytes} байт)"
            )

        hasher = hashlib.sha256()
        hasher.update(content_bytes)
        computed_sha256 = hasher.hexdigest()

        if expected_sha256 and expected_sha256.lower() != computed_sha256.lower():
            raise ValueError(
                f"Нарушение целостности SHA-256: ожидался '{expected_sha256}', вычислен '{computed_sha256}'"
            )

        dest_obj = Path(safe_dest)
        dest_obj.parent.mkdir(parents=True, exist_ok=True)
        with dest_obj.open("wb") as fh:
            for offset in range(0, size_bytes, self.CHUNK_SIZE):
                fh.write(content_bytes[offset : offset + self.CHUNK_SIZE])

        if self.transfers_repo:
            self.transfers_repo.record_transfer(
                host_id=host_id,
                direction="write",
                source_path="memory_stream",
                destination_path=safe_dest,
                size_bytes=size_bytes,
                sha256=computed_sha256,
                status="completed",
            )

        return {
            "path": safe_dest,
            "size_bytes": size_bytes,
            "sha256": computed_sha256,
        }

    async def stream_read_local(self, host_id: str, source_path: str) -> Dict[str, Any]:
        """Потоковое чтение файла с проверкой лимита размера и вычислением SHA-256.

        Args:
            host_id (str): Идентификатор узла.
            source_path (str): Путь к читаемому файлу.

        Returns:
            Dict[str, Any]: Словарь с содержимым файла, размером и хэшем SHA-256.

        Exceptions:
            FileNotFoundError: Если файл не существует.
            ValueError: Если размер файла превышает `max_transfer_bytes`.

        Examples:
            >>> import asyncio, tempfile
            >>> mgr = SFTPFileManager(max_transfer_mb=1)
            >>> with tempfile.NamedTemporaryFile(delete=False) as tf:
            ...     _ = tf.write(b"abc")
            ...     p = tf.name
            >>> res = asyncio.run(mgr.stream_read_local("localhost", p))
            >>> res["content"]
            'abc'
        """
        safe_src = self.validate_and_resolve(source_path)
        src_obj = Path(safe_src)
        if not src_obj.exists() or not src_obj.is_file():
            raise FileNotFoundError(f"Файл не найден: '{safe_src}'")

        stat_size = src_obj.stat().st_size
        if stat_size > self.max_transfer_bytes:
            raise ValueError(
                f"Размер файла ({stat_size} байт) превышает лимит чтения ({self.max_transfer_bytes} байт)"
            )

        hasher = hashlib.sha256()
        chunks: List[bytes] = []
        with src_obj.open("rb") as fh:
            while True:
                block = fh.read(self.CHUNK_SIZE)
                if not block:
                    break
                hasher.update(block)
                chunks.append(block)

        raw_bytes = b"".join(chunks)
        sha256_hex = hasher.hexdigest()

        if self.transfers_repo:
            self.transfers_repo.record_transfer(
                host_id=host_id,
                direction="read",
                source_path=safe_src,
                destination_path="memory_stream",
                size_bytes=len(raw_bytes),
                sha256=sha256_hex,
                status="completed",
            )

        return {
            "path": safe_src,
            "size_bytes": len(raw_bytes),
            "sha256": sha256_hex,
            "content": raw_bytes.decode("utf-8", errors="replace"),
        }
