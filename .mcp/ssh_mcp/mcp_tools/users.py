# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: MCP-инструменты управления пользователями и группами
# =============================================================================
# Description:
#   Реализация группы инструментов 4.8 ТЗ:
#   user_list, user_get, user_create, user_modify, user_disable, user_delete,
#   user_groups, user_group_add, user_group_remove. Секреты паролей передаются
#   через `credential_ref` без появления в MCP-ответах и логах.
#
# File: users.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.mcp_tools
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:59:45
# =============================================================================

from typing import Any, Dict
from mcp.server import MCPServer
from ..bootstrap import SSHMCPRuntime
from ..platforms.linux.users import LinuxUserAdapter
from ..platforms.windows.users import WindowsUserAdapter
from ..transports.base import BaseTransport


class UserToolsModule:
    """Модуль инструментов управления пользователями и группами (Раздел 4.8 ТЗ)."""

    def __init__(self, runtime: SSHMCPRuntime) -> None:
        """Инициализация модуля пользователей."""
        self.rt = runtime

    async def user_list(self, host_id: str = "localhost") -> Dict[str, Any]:
        """Список локальных пользователей узла."""
        async def _h(tr: BaseTransport, plat: str, _p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxUserAdapter.user_list(tr)
            return await WindowsUserAdapter.user_list(tr)

        return await self.rt.engine.dispatch(host_id, "user.list", {}, _h)

    async def user_get(self, host_id: str, username: str) -> Dict[str, Any]:
        """Подробные сведения о пользователе."""
        async def _h(tr: BaseTransport, plat: str, p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxUserAdapter.user_get(tr, str(p["username"]))
            return await WindowsUserAdapter.user_get(tr, str(p["username"]))

        return await self.rt.engine.dispatch(host_id, "user.get", {"username": username}, _h)

    async def user_create(
        self,
        host_id: str,
        username: str,
        credential_ref: str,
        description: str = "",
        approval_id: str = "",
    ) -> Dict[str, Any]:
        """Создание пользователя с передачей пароля через защищённую ссылку credential_ref."""
        async def _h(tr: BaseTransport, plat: str, p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxUserAdapter.user_create(
                    tr, self.rt.credential_manager, str(p["username"]), str(p["credential_ref"])
                )
            return await WindowsUserAdapter.user_create(
                tr,
                self.rt.credential_manager,
                str(p["username"]),
                str(p["credential_ref"]),
                str(p.get("description", "")),
            )

        return await self.rt.engine.dispatch(
            host_id,
            "user.create",
            {"username": username, "credential_ref": credential_ref, "description": description},
            _h,
            approval_id=approval_id,
        )

    async def user_modify(
        self,
        host_id: str,
        username: str,
        description: str = "",
        approval_id: str = "",
    ) -> Dict[str, Any]:
        """Модификация учётной записи пользователя."""
        async def _h(tr: BaseTransport, plat: str, p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxUserAdapter.user_modify(tr, str(p["username"]))
            return await WindowsUserAdapter.user_modify(tr, str(p["username"]), str(p.get("description", "")))

        return await self.rt.engine.dispatch(
            host_id,
            "user.modify",
            {"username": username, "description": description},
            _h,
            approval_id=approval_id,
        )

    async def user_disable(
        self, host_id: str, username: str, approval_id: str = ""
    ) -> Dict[str, Any]:
        """Отключение учётной записи пользователя."""
        async def _h(tr: BaseTransport, plat: str, p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxUserAdapter.user_disable(tr, str(p["username"]))
            return await WindowsUserAdapter.user_disable(tr, str(p["username"]))

        return await self.rt.engine.dispatch(
            host_id, "user.disable", {"username": username}, _h, approval_id=approval_id
        )

    async def user_delete(
        self, host_id: str, username: str, approval_id: str = ""
    ) -> Dict[str, Any]:
        """Удаление учётной записи пользователя (уровень риска critical, требует подтверждения)."""
        async def _h(tr: BaseTransport, plat: str, p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxUserAdapter.user_delete(tr, str(p["username"]))
            return await WindowsUserAdapter.user_delete(tr, str(p["username"]))

        return await self.rt.engine.dispatch(
            host_id, "user.delete", {"username": username}, _h, approval_id=approval_id
        )

    async def user_groups(self, host_id: str, username: str) -> Dict[str, Any]:
        """Список групп пользователя."""
        async def _h(tr: BaseTransport, plat: str, p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxUserAdapter.user_groups(tr, str(p["username"]))
            return await WindowsUserAdapter.user_groups(tr, str(p["username"]))

        return await self.rt.engine.dispatch(host_id, "user.groups", {"username": username}, _h)

    async def user_group_add(
        self, host_id: str, username: str, group: str, approval_id: str = ""
    ) -> Dict[str, Any]:
        """Добавление пользователя в группу."""
        async def _h(tr: BaseTransport, plat: str, p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxUserAdapter.user_group_add(tr, str(p["username"]), str(p["group"]))
            return await WindowsUserAdapter.user_group_add(tr, str(p["username"]), str(p["group"]))

        return await self.rt.engine.dispatch(
            host_id,
            "user.group_add",
            {"username": username, "group": group},
            _h,
            approval_id=approval_id,
        )

    async def user_group_remove(
        self, host_id: str, username: str, group: str, approval_id: str = ""
    ) -> Dict[str, Any]:
        """Удаление пользователя из группы."""
        async def _h(tr: BaseTransport, plat: str, p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxUserAdapter.user_group_remove(tr, str(p["username"]), str(p["group"]))
            return await WindowsUserAdapter.user_group_remove(tr, str(p["username"]), str(p["group"]))

        return await self.rt.engine.dispatch(
            host_id,
            "user.group_remove",
            {"username": username, "group": group},
            _h,
            approval_id=approval_id,
        )


def register_user_tools(mcp: MCPServer, runtime: SSHMCPRuntime) -> UserToolsModule:
    """Регистрация 9 инструментов управления пользователями в MCPServer."""
    mod = UserToolsModule(runtime)

    @mcp.tool(name="user_list", description="Список локальных пользователей")
    async def user_list(host_id: str = "localhost") -> Dict[str, Any]:
        return await mod.user_list(host_id)

    @mcp.tool(name="user_get", description="Информация о локальном пользователе")
    async def user_get(host_id: str, username: str) -> Dict[str, Any]:
        return await mod.user_get(host_id, username)

    @mcp.tool(name="user_create", description="Создание пользователя через защищённый credential_ref")
    async def user_create(
        host_id: str,
        username: str,
        credential_ref: str,
        description: str = "",
        approval_id: str = "",
    ) -> Dict[str, Any]:
        return await mod.user_create(host_id, username, credential_ref, description, approval_id)

    @mcp.tool(name="user_modify", description="Изменение учётной записи пользователя")
    async def user_modify(
        host_id: str, username: str, description: str = "", approval_id: str = ""
    ) -> Dict[str, Any]:
        return await mod.user_modify(host_id, username, description, approval_id)

    @mcp.tool(name="user_disable", description="Отключение учётной записи пользователя")
    async def user_disable(host_id: str, username: str, approval_id: str = "") -> Dict[str, Any]:
        return await mod.user_disable(host_id, username, approval_id)

    @mcp.tool(name="user_delete", description="Удаление учётной записи пользователя (critical risk)")
    async def user_delete(host_id: str, username: str, approval_id: str = "") -> Dict[str, Any]:
        return await mod.user_delete(host_id, username, approval_id)

    @mcp.tool(name="user_groups", description="Членство пользователя в группах")
    async def user_groups(host_id: str, username: str) -> Dict[str, Any]:
        return await mod.user_groups(host_id, username)

    @mcp.tool(name="user_group_add", description="Добавление пользователя в группу")
    async def user_group_add(
        host_id: str, username: str, group: str, approval_id: str = ""
    ) -> Dict[str, Any]:
        return await mod.user_group_add(host_id, username, group, approval_id)

    @mcp.tool(name="user_group_remove", description="Удаление пользователя из группы")
    async def user_group_remove(
        host_id: str, username: str, group: str, approval_id: str = ""
    ) -> Dict[str, Any]:
        return await mod.user_group_remove(host_id, username, group, approval_id)

    return mod
