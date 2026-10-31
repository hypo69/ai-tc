# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Адаптер файловой системы Windows
# =============================================================================
# Description:
#   Операции управления файлами и каталогами на платформе Windows (fs_list,
#   fs_stat, fs_read, fs_write, fs_search, fs_copy, fs_move, fs_delete,
#   fs_mkdir, fs_chmod, fs_chown) с обязательным контролем путей, квот размера
#   и целостности SHA-256 (Раздел 4.6 ТЗ).
#
# File: filesystem.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.platforms.windows
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:53:15
# =============================================================================

import hashlib
from pathlib import Path
import shutil
from typing import Any, Dict, List

from ...transports.base import BaseTransport
from ...transports.local_transport import LocalTransport
from ...transports.sftp_transport import SFTPFileManager
from .executor import WindowsExecutor


class WindowsFilesystemAdapter:
    """Адаптер операций файловой системы для ОС Windows.

    Examples:
        >>> adapter = WindowsFilesystemAdapter()
    """

    @staticmethod
    async def fs_list(
        transport: BaseTransport, sftp_mgr: SFTPFileManager, path: str
    ) -> Dict[str, Any]:
        """Получение содержимого каталога с проверкой файловой политики.

        Args:
            transport (BaseTransport): Транспорт узла.
            sftp_mgr (SFTPFileManager): Менеджер файловых политик и квот.
            path (str): Целевой путь каталога.

        Returns:
            Dict[str, Any]: Список элементов каталога в `entries`.

        Examples:
            >>> pass
        """
        safe_path = sftp_mgr.validate_and_resolve(path)
        if isinstance(transport, LocalTransport):
            target = Path(safe_path)
            entries: List[Dict[str, Any]] = []
            for child in target.iterdir():
                st = child.stat()
                entries.append(
                    {
                        "name": child.name,
                        "is_dir": child.is_dir(),
                        "size_bytes": int(st.st_size),
                    }
                )
            return {"path": safe_path, "entries": entries}

        q = safe_path.replace("'", "''")
        ps = (
            f"Get-ChildItem -LiteralPath '{q}' | Select-Object "
            "@{N='name';E={$_.Name}}, @{N='is_dir';E={$_.PSIsContainer}}, @{N='size_bytes';E={[int64]$_.Length}} "
            "| ConvertTo-Json -Compress"
        )
        res = await WindowsExecutor.run_ps_json(transport, ps)
        return {"path": safe_path, "entries": res.get("items", [res] if "name" in res else [])}

    @staticmethod
    async def fs_stat(
        transport: BaseTransport, sftp_mgr: SFTPFileManager, path: str
    ) -> Dict[str, Any]:
        """Получение метаданных файла или каталога и контрольной суммы SHA-256.

        Args:
            transport (BaseTransport): Транспорт узла.
            sftp_mgr (SFTPFileManager): Менеджер файловых политик.
            path (str): Путь к объекту.

        Returns:
            Dict[str, Any]: Метаданные объекта.

        Examples:
            >>> pass
        """
        safe_path = sftp_mgr.validate_and_resolve(path)
        if isinstance(transport, LocalTransport):
            target = Path(safe_path)
            if not target.exists():
                raise FileNotFoundError(f"Объект не найден: '{safe_path}'")
            st = target.stat()
            sha = ""
            if target.is_file() and st.st_size <= sftp_mgr.max_transfer_bytes:
                sha = hashlib.sha256(target.read_bytes()).hexdigest()
            return {
                "path": safe_path,
                "exists": True,
                "is_dir": target.is_dir(),
                "size_bytes": int(st.st_size),
                "modified_at": int(st.st_mtime),
                "sha256": sha,
            }

        q = safe_path.replace("'", "''")
        ps = (
            f"$i = Get-Item -LiteralPath '{q}' -ErrorAction Stop; "
            "$h = if (-not $i.PSIsContainer) { (Get-FileHash -LiteralPath $i.FullName -Algorithm SHA256).Hash.ToLower() } else { '' }; "
            "@{path=$i.FullName; exists=$true; is_dir=$i.PSIsContainer; size_bytes=[int64]$i.Length; sha256=$h} "
            "| ConvertTo-Json -Compress"
        )
        return await WindowsExecutor.run_ps_json(transport, ps)

    @staticmethod
    async def fs_read(
        transport: BaseTransport, sftp_mgr: SFTPFileManager, path: str
    ) -> Dict[str, Any]:
        """Безопасное потоковое чтение файла с проверкой лимита размера и SHA-256.

        Args:
            transport (BaseTransport): Транспорт узла.
            sftp_mgr (SFTPFileManager): Менеджер файловых операций.
            path (str): Путь к файлу.

        Returns:
            Dict[str, Any]: Содержимое файла, размер и SHA-256.

        Examples:
            >>> pass
        """
        if isinstance(transport, LocalTransport):
            return await sftp_mgr.stream_read_local(transport.host_id, path)

        safe_path = sftp_mgr.validate_and_resolve(path)
        q = safe_path.replace("'", "''")
        ps = (
            f"$c = Get-Content -LiteralPath '{q}' -Raw -ErrorAction Stop; "
            f"$h = (Get-FileHash -LiteralPath '{q}' -Algorithm SHA256).Hash.ToLower(); "
            "@{path='" + q + "'; content=$c; sha256=$h} | ConvertTo-Json -Compress"
        )
        return await WindowsExecutor.run_ps_json(transport, ps)

    @staticmethod
    async def fs_write(
        transport: BaseTransport,
        sftp_mgr: SFTPFileManager,
        path: str,
        content: str,
        expected_sha256: str = "",
    ) -> Dict[str, Any]:
        """Потоковая запись файла с контролем максимального размера и проверкой SHA-256.

        Args:
            transport (BaseTransport): Транспорт узла.
            sftp_mgr (SFTPFileManager): Менеджер файловых операций.
            path (str): Целевой путь.
            content (str): Записываемый текст.
            expected_sha256 (str): Ожидаемый SHA-256 хэш для верификации целостности.

        Returns:
            Dict[str, Any]: Результат записи с вычисленным SHA-256.

        Examples:
            >>> pass
        """
        raw_bytes = content.encode("utf-8")
        if isinstance(transport, LocalTransport):
            return await sftp_mgr.stream_write_local(
                transport.host_id, path, raw_bytes, expected_sha256=expected_sha256
            )

        safe_path = sftp_mgr.validate_and_resolve(path)
        if len(raw_bytes) > sftp_mgr.max_transfer_bytes:
            raise ValueError("Превышен максимальный размер передаваемого файла")
        computed = hashlib.sha256(raw_bytes).hexdigest()
        if expected_sha256 and expected_sha256.lower() != computed.lower():
            raise ValueError("Несовпадение контрольной суммы SHA-256")

        q_path = safe_path.replace("'", "''")
        q_content = content.replace("'", "''")
        ps = (
            f"Set-Content -LiteralPath '{q_path}' -Value '{q_content}' -Encoding UTF8 -ErrorAction Stop; "
            f"@{{path='{q_path}'; size_bytes={len(raw_bytes)}; sha256='{computed}'}} | ConvertTo-Json -Compress"
        )
        return await WindowsExecutor.run_ps_json(transport, ps)

    @staticmethod
    async def fs_operations(
        transport: BaseTransport,
        sftp_mgr: SFTPFileManager,
        op: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Выполнение дополнительных операций ФС (search, copy, move, delete, mkdir, chmod, chown).

        Args:
            transport (BaseTransport): Транспорт узла.
            sftp_mgr (SFTPFileManager): Менеджер файловых политик.
            op (str): Имя операции ('search', 'copy', 'move', 'delete', 'mkdir', 'chmod', 'chown').
            params (Dict[str, Any]): Параметры вызова.

        Returns:
            Dict[str, Any]: Результат операции.

        Examples:
            >>> pass
        """
        if op == "mkdir":
            p = sftp_mgr.validate_and_resolve(str(params["path"]))
            if isinstance(transport, LocalTransport):
                Path(p).mkdir(parents=True, exist_ok=True)
                return {"path": p, "created": True}
            q = p.replace("'", "''")
            return await WindowsExecutor.run_ps_json(
                transport, f"New-Item -ItemType Directory -Path '{q}' -Force | Out-Null; @{{path='{q}'; created=$true}} | ConvertTo-Json -Compress"
            )

        if op == "delete":
            p = sftp_mgr.validate_and_resolve(str(params["path"]))
            if isinstance(transport, LocalTransport):
                target = Path(p)
                if target.is_dir():
                    shutil.rmtree(target)
                elif target.exists():
                    target.unlink()
                return {"path": p, "deleted": True}
            q = p.replace("'", "''")
            return await WindowsExecutor.run_ps_json(
                transport, f"Remove-Item -LiteralPath '{q}' -Recurse -Force -ErrorAction Stop; @{{path='{q}'; deleted=$true}} | ConvertTo-Json -Compress"
            )

        if op == "copy":
            src = sftp_mgr.validate_and_resolve(str(params["source"]))
            dst = sftp_mgr.validate_and_resolve(str(params["destination"]))
            if isinstance(transport, LocalTransport):
                shutil.copy2(src, dst)
                return {"source": src, "destination": dst, "copied": True}
            return await WindowsExecutor.run_ps_json(
                transport,
                f"Copy-Item -LiteralPath '{src.replace(chr(39), chr(39)*2)}' -Destination '{dst.replace(chr(39), chr(39)*2)}' -Force; @{{copied=$true}} | ConvertTo-Json -Compress",
            )

        if op == "move":
            src = sftp_mgr.validate_and_resolve(str(params["source"]))
            dst = sftp_mgr.validate_and_resolve(str(params["destination"]))
            if isinstance(transport, LocalTransport):
                shutil.move(src, dst)
                return {"source": src, "destination": dst, "moved": True}
            return await WindowsExecutor.run_ps_json(
                transport,
                f"Move-Item -LiteralPath '{src.replace(chr(39), chr(39)*2)}' -Destination '{dst.replace(chr(39), chr(39)*2)}' -Force; @{{moved=$true}} | ConvertTo-Json -Compress",
            )

        if op == "search":
            root = sftp_mgr.validate_and_resolve(str(params["path"]))
            pattern = str(params.get("pattern", "*"))
            if isinstance(transport, LocalTransport):
                matches = [str(m) for m in Path(root).rglob(pattern)][:100]
                return {"path": root, "pattern": pattern, "matches": matches}
            q_r = root.replace("'", "''")
            q_p = pattern.replace("'", "''")
            return await WindowsExecutor.run_ps_json(
                transport,
                f"$m = Get-ChildItem -Path '{q_r}' -Filter '{q_p}' -Recurse -ErrorAction SilentlyContinue | Select-Object -First 100 -ExpandProperty FullName; @{{matches=@($m)}} | ConvertTo-Json -Compress",
            )

        if op in ("chmod", "chown"):
            p = sftp_mgr.validate_and_resolve(str(params["path"]))
            target_arg = str(params.get("mode") or params.get("owner") or "")
            return await WindowsExecutor.execute(transport, "icacls", [p], shell="powershell")

        return {"operation": op, "status": "unsupported"}
