# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Адаптер файловой системы Linux
# =============================================================================
# Description:
#   Выполнение файловых операций на платформе Linux (fs_list, fs_stat, fs_read,
#   fs_write, fs_search, fs_copy, fs_move, fs_delete, fs_mkdir, fs_chmod,
#   fs_chown) с проверкой SHA-256 и квот размера (Раздел 4.6 ТЗ).
#
# File: filesystem.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.platforms.linux
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:55:30
# =============================================================================

import hashlib
import shlex
from typing import Any, Dict, List

from ...transports.base import BaseTransport
from ...transports.sftp_transport import SFTPFileManager
from ..base import pack_raw_result


class LinuxFilesystemAdapter:
    """Адаптер управления файловой системой на узлах Linux.

    Examples:
        >>> adapter = LinuxFilesystemAdapter()
    """

    @staticmethod
    async def fs_list(
        transport: BaseTransport, sftp_mgr: SFTPFileManager, path: str
    ) -> Dict[str, Any]:
        """Получение списка файлов каталога на узле Linux.

        Args:
            transport (BaseTransport): Транспорт узла.
            sftp_mgr (SFTPFileManager): Менеджер файловых политик.
            path (str): Целевой каталог.

        Returns:
            Dict[str, Any]: Элементы каталога в `entries`.

        Examples:
            >>> pass
        """
        safe_path = sftp_mgr.validate_and_resolve(path)
        q = shlex.quote(safe_path)
        raw = await transport.execute_command(f"ls -1p {q}", shell="bash", timeout=15)
        entries: List[Dict[str, Any]] = []
        for ln in raw.stdout.splitlines():
            name = ln.strip()
            if name:
                entries.append({"name": name.rstrip("/"), "is_dir": name.endswith("/")})
        return pack_raw_result(raw, {"path": safe_path, "entries": entries})

    @staticmethod
    async def fs_stat(
        transport: BaseTransport, sftp_mgr: SFTPFileManager, path: str
    ) -> Dict[str, Any]:
        """Получение метаданных файла и SHA-256 на узле Linux.

        Args:
            transport (BaseTransport): Транспорт узла.
            sftp_mgr (SFTPFileManager): Менеджер файловых политик.
            path (str): Путь к объекту.

        Returns:
            Dict[str, Any]: Размер, права и SHA-256.

        Examples:
            >>> pass
        """
        safe_path = sftp_mgr.validate_and_resolve(path)
        q = shlex.quote(safe_path)
        raw = await transport.execute_command(
            f"stat -c '%s %a %F' {q} && (sha256sum {q} 2>/dev/null | awk '{{print $1}}' || true)",
            shell="bash",
            timeout=15,
        )
        lines = raw.stdout.splitlines()
        meta_parts = lines[0].split(None, 2) if lines else ["0", "644", "regular file"]
        sha = lines[1].strip() if len(lines) > 1 else ""
        return pack_raw_result(
            raw,
            {
                "path": safe_path,
                "size_bytes": int(meta_parts[0]) if meta_parts[0].isdigit() else 0,
                "mode": meta_parts[1] if len(meta_parts) > 1 else "",
                "type": meta_parts[2] if len(meta_parts) > 2 else "",
                "sha256": sha,
            },
        )

    @staticmethod
    async def fs_read(
        transport: BaseTransport, sftp_mgr: SFTPFileManager, path: str
    ) -> Dict[str, Any]:
        """Чтение файла на узле Linux с проверкой SHA-256.

        Args:
            transport (BaseTransport): Транспорт узла.
            sftp_mgr (SFTPFileManager): Менеджер файловых политик.
            path (str): Путь к файлу.

        Returns:
            Dict[str, Any]: Содержимое и SHA-256.

        Examples:
            >>> pass
        """
        safe_path = sftp_mgr.validate_and_resolve(path)
        q = shlex.quote(safe_path)
        raw = await transport.execute_command(f"cat {q}", shell="bash", timeout=30)
        data_bytes = raw.stdout.encode("utf-8")
        if len(data_bytes) > sftp_mgr.max_transfer_bytes:
            raise ValueError("Размер файла превышает допустимый лимит передачи")
        sha = hashlib.sha256(data_bytes).hexdigest()
        return pack_raw_result(
            raw,
            {"path": safe_path, "size_bytes": len(data_bytes), "sha256": sha, "content": raw.stdout},
        )

    @staticmethod
    async def fs_write(
        transport: BaseTransport,
        sftp_mgr: SFTPFileManager,
        path: str,
        content: str,
        expected_sha256: str = "",
    ) -> Dict[str, Any]:
        """Запись файла на узле Linux с верификацией SHA-256.

        Args:
            transport (BaseTransport): Транспорт узла.
            sftp_mgr (SFTPFileManager): Менеджер файловых политик.
            path (str): Целевой путь.
            content (str): Записываемое содержимое.
            expected_sha256 (str): Ожидаемый SHA-256.

        Returns:
            Dict[str, Any]: Статус записи и контрольная сумма.

        Examples:
            >>> pass
        """
        safe_path = sftp_mgr.validate_and_resolve(path)
        raw_bytes = content.encode("utf-8")
        if len(raw_bytes) > sftp_mgr.max_transfer_bytes:
            raise ValueError("Превышен максимальный размер передаваемого файла")
        computed = hashlib.sha256(raw_bytes).hexdigest()
        if expected_sha256 and expected_sha256.lower() != computed.lower():
            raise ValueError("Контрольная сумма SHA-256 не совпадает")

        q_path = shlex.quote(safe_path)
        q_content = shlex.quote(content)
        raw = await transport.execute_command(
            f"printf '%s' {q_content} > {q_path}", shell="bash", timeout=30
        )
        return pack_raw_result(
            raw, {"path": safe_path, "size_bytes": len(raw_bytes), "sha256": computed}
        )

    @staticmethod
    async def fs_operations(
        transport: BaseTransport,
        sftp_mgr: SFTPFileManager,
        op: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Дополнительные операции ФС Linux (mkdir, delete, copy, move, search, chmod, chown).

        Args:
            transport (BaseTransport): Транспорт узла.
            sftp_mgr (SFTPFileManager): Менеджер файловых политик.
            op (str): Имя операции.
            params (Dict[str, Any]): Параметры вызова.

        Returns:
            Dict[str, Any]: Результат выполнения.

        Examples:
            >>> pass
        """
        if op == "mkdir":
            p = shlex.quote(sftp_mgr.validate_and_resolve(str(params["path"])))
            raw = await transport.execute_command(f"mkdir -p {p}", shell="bash")
            return pack_raw_result(raw, {"created": raw.exit_code == 0})

        if op == "delete":
            p = shlex.quote(sftp_mgr.validate_and_resolve(str(params["path"])))
            raw = await transport.execute_command(f"rm -rf {p}", shell="bash", elevate=True)
            return pack_raw_result(raw, {"deleted": raw.exit_code == 0})

        if op == "copy":
            src = shlex.quote(sftp_mgr.validate_and_resolve(str(params["source"])))
            dst = shlex.quote(sftp_mgr.validate_and_resolve(str(params["destination"])))
            raw = await transport.execute_command(f"cp -r {src} {dst}", shell="bash")
            return pack_raw_result(raw, {"copied": raw.exit_code == 0})

        if op == "move":
            src = shlex.quote(sftp_mgr.validate_and_resolve(str(params["source"])))
            dst = shlex.quote(sftp_mgr.validate_and_resolve(str(params["destination"])))
            raw = await transport.execute_command(f"mv {src} {dst}", shell="bash")
            return pack_raw_result(raw, {"moved": raw.exit_code == 0})

        if op == "search":
            root = shlex.quote(sftp_mgr.validate_and_resolve(str(params["path"])))
            pat = shlex.quote(str(params.get("pattern", "*")))
            raw = await transport.execute_command(f"find {root} -name {pat} | head -n 100", shell="bash")
            return pack_raw_result(raw, {"matches": [ln.strip() for ln in raw.stdout.splitlines() if ln.strip()]})

        if op == "chmod":
            p = shlex.quote(sftp_mgr.validate_and_resolve(str(params["path"])))
            mode = shlex.quote(str(params["mode"]))
            raw = await transport.execute_command(f"chmod {mode} {p}", shell="bash", elevate=True)
            return pack_raw_result(raw, {"mode_applied": mode})

        if op == "chown":
            p = shlex.quote(sftp_mgr.validate_and_resolve(str(params["path"])))
            owner = shlex.quote(str(params["owner"]))
            raw = await transport.execute_command(f"chown {owner} {p}", shell="bash", elevate=True)
            return pack_raw_result(raw, {"owner_applied": owner})

        return {"operation": op, "status": "unsupported"}
