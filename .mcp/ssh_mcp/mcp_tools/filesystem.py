# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: MCP-инструменты файловой системы (Filesystem Management)
# =============================================================================
# Description:
#   Реализация группы инструментов 4.6 ТЗ:
#   fs_list, fs_stat, fs_read, fs_write, fs_search, fs_copy, fs_move,
#   fs_delete, fs_mkdir, fs_chmod, fs_chown с контролем путей, размера и SHA-256.
#
# File: filesystem.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.mcp_tools
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:59:15
# =============================================================================

from typing import Any, Dict
from mcp.server import MCPServer
from ..bootstrap import SSHMCPRuntime
from ..platforms.linux.filesystem import LinuxFilesystemAdapter
from ..platforms.windows.filesystem import WindowsFilesystemAdapter
from ..transports.base import BaseTransport


class FilesystemToolsModule:
    """Модуль инструментов управления файловой системой и SFTP (Раздел 4.6 ТЗ)."""

    def __init__(self, runtime: SSHMCPRuntime) -> None:
        """Инициализация файлового модуля."""
        self.rt = runtime

    async def fs_list(self, host_id: str, path: str) -> Dict[str, Any]:
        """Содержимое каталога."""
        async def _h(tr: BaseTransport, plat: str, p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxFilesystemAdapter.fs_list(tr, self.rt.sftp_manager, str(p["path"]))
            return await WindowsFilesystemAdapter.fs_list(tr, self.rt.sftp_manager, str(p["path"]))

        return await self.rt.engine.dispatch(host_id, "fs.list", {"path": path}, _h)

    async def fs_stat(self, host_id: str, path: str) -> Dict[str, Any]:
        """Метаданные и контрольная сумма SHA-256 файла."""
        async def _h(tr: BaseTransport, plat: str, p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxFilesystemAdapter.fs_stat(tr, self.rt.sftp_manager, str(p["path"]))
            return await WindowsFilesystemAdapter.fs_stat(tr, self.rt.sftp_manager, str(p["path"]))

        return await self.rt.engine.dispatch(host_id, "fs.stat", {"path": path}, _h)

    async def fs_read(self, host_id: str, path: str) -> Dict[str, Any]:
        """Потоковое чтение файла с проверкой лимита размера и SHA-256."""
        async def _h(tr: BaseTransport, plat: str, p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxFilesystemAdapter.fs_read(tr, self.rt.sftp_manager, str(p["path"]))
            return await WindowsFilesystemAdapter.fs_read(tr, self.rt.sftp_manager, str(p["path"]))

        return await self.rt.engine.dispatch(host_id, "fs.read", {"path": path}, _h)

    async def fs_write(
        self, host_id: str, path: str, content: str, expected_sha256: str = ""
    ) -> Dict[str, Any]:
        """Потоковая запись файла с контролем SHA-256."""
        async def _h(tr: BaseTransport, plat: str, p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxFilesystemAdapter.fs_write(
                    tr, self.rt.sftp_manager, str(p["path"]), str(p["content"]), str(p.get("expected_sha256", ""))
                )
            return await WindowsFilesystemAdapter.fs_write(
                tr, self.rt.sftp_manager, str(p["path"]), str(p["content"]), str(p.get("expected_sha256", ""))
            )

        return await self.rt.engine.dispatch(
            host_id,
            "fs.write",
            {"path": path, "content": content, "expected_sha256": expected_sha256},
            _h,
        )

    async def fs_search(self, host_id: str, path: str, pattern: str) -> Dict[str, Any]:
        """Поиск файлов в каталоге."""
        async def _h(tr: BaseTransport, plat: str, p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxFilesystemAdapter.fs_operations(tr, self.rt.sftp_manager, "search", p)
            return await WindowsFilesystemAdapter.fs_operations(tr, self.rt.sftp_manager, "search", p)

        return await self.rt.engine.dispatch(
            host_id, "fs.search", {"path": path, "pattern": pattern}, _h
        )

    async def fs_copy(self, host_id: str, source: str, destination: str) -> Dict[str, Any]:
        """Копирование файла или каталога."""
        async def _h(tr: BaseTransport, plat: str, p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxFilesystemAdapter.fs_operations(tr, self.rt.sftp_manager, "copy", p)
            return await WindowsFilesystemAdapter.fs_operations(tr, self.rt.sftp_manager, "copy", p)

        return await self.rt.engine.dispatch(
            host_id, "fs.copy", {"source": source, "destination": destination}, _h
        )

    async def fs_move(self, host_id: str, source: str, destination: str) -> Dict[str, Any]:
        """Перемещение или переименование файла."""
        async def _h(tr: BaseTransport, plat: str, p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxFilesystemAdapter.fs_operations(tr, self.rt.sftp_manager, "move", p)
            return await WindowsFilesystemAdapter.fs_operations(tr, self.rt.sftp_manager, "move", p)

        return await self.rt.engine.dispatch(
            host_id, "fs.move", {"source": source, "destination": destination}, _h
        )

    async def fs_delete(
        self, host_id: str, path: str, approval_id: str = ""
    ) -> Dict[str, Any]:
        """Удаление файла или каталога (требует подтверждения high-risk)."""
        async def _h(tr: BaseTransport, plat: str, p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxFilesystemAdapter.fs_operations(tr, self.rt.sftp_manager, "delete", p)
            return await WindowsFilesystemAdapter.fs_operations(tr, self.rt.sftp_manager, "delete", p)

        return await self.rt.engine.dispatch(
            host_id, "fs.delete", {"path": path}, _h, approval_id=approval_id
        )

    async def fs_mkdir(self, host_id: str, path: str) -> Dict[str, Any]:
        """Создание каталога."""
        async def _h(tr: BaseTransport, plat: str, p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxFilesystemAdapter.fs_operations(tr, self.rt.sftp_manager, "mkdir", p)
            return await WindowsFilesystemAdapter.fs_operations(tr, self.rt.sftp_manager, "mkdir", p)

        return await self.rt.engine.dispatch(host_id, "fs.mkdir", {"path": path}, _h)

    async def fs_chmod(
        self, host_id: str, path: str, mode: str, approval_id: str = ""
    ) -> Dict[str, Any]:
        """Изменение прав доступа к файлу (требует подтверждения)."""
        async def _h(tr: BaseTransport, plat: str, p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxFilesystemAdapter.fs_operations(tr, self.rt.sftp_manager, "chmod", p)
            return await WindowsFilesystemAdapter.fs_operations(tr, self.rt.sftp_manager, "chmod", p)

        return await self.rt.engine.dispatch(
            host_id, "fs.chmod", {"path": path, "mode": mode}, _h, approval_id=approval_id
        )

    async def fs_chown(
        self, host_id: str, path: str, owner: str, approval_id: str = ""
    ) -> Dict[str, Any]:
        """Изменение владельца файла (требует подтверждения)."""
        async def _h(tr: BaseTransport, plat: str, p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxFilesystemAdapter.fs_operations(tr, self.rt.sftp_manager, "chown", p)
            return await WindowsFilesystemAdapter.fs_operations(tr, self.rt.sftp_manager, "chown", p)

        return await self.rt.engine.dispatch(
            host_id, "fs.chown", {"path": path, "owner": owner}, _h, approval_id=approval_id
        )


def register_filesystem_tools(mcp: MCPServer, runtime: SSHMCPRuntime) -> FilesystemToolsModule:
    """Регистрация 11 файловых инструментов в MCPServer."""
    mod = FilesystemToolsModule(runtime)

    @mcp.tool(name="fs_list", description="Получение списка файлов и папок в каталоге")
    async def fs_list(host_id: str, path: str) -> Dict[str, Any]:
        return await mod.fs_list(host_id, path)

    @mcp.tool(name="fs_stat", description="Получение метаданных файла и контрольной суммы SHA-256")
    async def fs_stat(host_id: str, path: str) -> Dict[str, Any]:
        return await mod.fs_stat(host_id, path)

    @mcp.tool(name="fs_read", description="Потоковое чтение файла с проверкой SHA-256 и квот размера")
    async def fs_read(host_id: str, path: str) -> Dict[str, Any]:
        return await mod.fs_read(host_id, path)

    @mcp.tool(name="fs_write", description="Потоковая запись файла с контролем целостности SHA-256")
    async def fs_write(
        host_id: str, path: str, content: str, expected_sha256: str = ""
    ) -> Dict[str, Any]:
        return await mod.fs_write(host_id, path, content, expected_sha256)

    @mcp.tool(name="fs_search", description="Поиск файлов по маске в указанном каталоге")
    async def fs_search(host_id: str, path: str, pattern: str) -> Dict[str, Any]:
        return await mod.fs_search(host_id, path, pattern)

    @mcp.tool(name="fs_copy", description="Копирование файла или каталога")
    async def fs_copy(host_id: str, source: str, destination: str) -> Dict[str, Any]:
        return await mod.fs_copy(host_id, source, destination)

    @mcp.tool(name="fs_move", description="Перемещение или переименование файла")
    async def fs_move(host_id: str, source: str, destination: str) -> Dict[str, Any]:
        return await mod.fs_move(host_id, source, destination)

    @mcp.tool(name="fs_delete", description="Удаление файла или каталога (требует подтверждения)")
    async def fs_delete(host_id: str, path: str, approval_id: str = "") -> Dict[str, Any]:
        return await mod.fs_delete(host_id, path, approval_id)

    @mcp.tool(name="fs_mkdir", description="Создание нового каталога")
    async def fs_mkdir(host_id: str, path: str) -> Dict[str, Any]:
        return await mod.fs_mkdir(host_id, path)

    @mcp.tool(name="fs_chmod", description="Изменение прав доступа к файлу или каталогу")
    async def fs_chmod(host_id: str, path: str, mode: str, approval_id: str = "") -> Dict[str, Any]:
        return await mod.fs_chmod(host_id, path, mode, approval_id)

    @mcp.tool(name="fs_chown", description="Изменение владельца файла или каталога")
    async def fs_chown(host_id: str, path: str, owner: str, approval_id: str = "") -> Dict[str, Any]:
        return await mod.fs_chown(host_id, path, owner, approval_id)

    return mod
