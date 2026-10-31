# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: MCP-инструменты системного администрирования (System Admin)
# =============================================================================
# Description:
#   Реализация группы инструментов 4.3 ТЗ:
#   system_info, system_cpu, system_memory, system_disks, system_uptime,
#   system_boot_info, system_environment с автоматической маршрутизацией
#   между WindowsSystemAdapter и LinuxSystemAdapter.
#
# File: system.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.mcp_tools
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:58:30
# =============================================================================

from typing import Any, Dict
from mcp.server import MCPServer
from ..bootstrap import SSHMCPRuntime
from ..platforms.linux.system import LinuxSystemAdapter
from ..platforms.windows.system import WindowsSystemAdapter
from ..transports.base import BaseTransport


class SystemToolsModule:
    """Модуль инструментов мониторинга системы (Раздел 4.3 ТЗ).

    Attributes:
        rt (SSHMCPRuntime): Контейнер сервисов ядра.

    Examples:
        >>> from ssh_mcp.bootstrap import create_runtime
        >>> mod = SystemToolsModule(create_runtime(db_path=":memory:"))
    """

    def __init__(self, runtime: SSHMCPRuntime) -> None:
        """Инициализация модуля системного администрирования."""
        self.rt = runtime

    async def system_info(self, host_id: str = "localhost") -> Dict[str, Any]:
        """Унифицированные сведения об ОС (CIM/WMI на Windows, uname/os-release на Linux)."""
        async def _h(tr: BaseTransport, plat: str, _p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxSystemAdapter.system_info(tr)
            return await WindowsSystemAdapter.system_info(tr)

        return await self.rt.engine.dispatch(host_id, "system.info", {}, _h)

    async def system_cpu(self, host_id: str = "localhost") -> Dict[str, Any]:
        """Метрики процессора и количества ядер."""
        async def _h(tr: BaseTransport, plat: str, _p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxSystemAdapter.system_cpu(tr)
            return await WindowsSystemAdapter.system_cpu(tr)

        return await self.rt.engine.dispatch(host_id, "system.cpu", {}, _h)

    async def system_memory(self, host_id: str = "localhost") -> Dict[str, Any]:
        """Состояние оперативной памяти в МБ (`total_mb`, `used_mb`, `available_mb`)."""
        async def _h(tr: BaseTransport, plat: str, _p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxSystemAdapter.system_memory(tr)
            return await WindowsSystemAdapter.system_memory(tr)

        return await self.rt.engine.dispatch(host_id, "system.memory", {}, _h)

    async def system_disks(self, host_id: str = "localhost") -> Dict[str, Any]:
        """Информация о логических дисках и точках монтирования."""
        async def _h(tr: BaseTransport, plat: str, _p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxSystemAdapter.system_disks(tr)
            return await WindowsSystemAdapter.system_disks(tr)

        return await self.rt.engine.dispatch(host_id, "system.disks", {}, _h)

    async def system_uptime(self, host_id: str = "localhost") -> Dict[str, Any]:
        """Время непрерывной работы системы в секундах."""
        async def _h(tr: BaseTransport, plat: str, _p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxSystemAdapter.system_uptime(tr)
            return await WindowsSystemAdapter.system_uptime(tr)

        return await self.rt.engine.dispatch(host_id, "system.uptime", {}, _h)

    async def system_boot_info(self, host_id: str = "localhost") -> Dict[str, Any]:
        """Сведения о последней загрузке ОС."""
        async def _h(tr: BaseTransport, plat: str, _p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxSystemAdapter.system_boot_info(tr)
            return await WindowsSystemAdapter.system_boot_info(tr)

        return await self.rt.engine.dispatch(host_id, "system.boot_info", {}, _h)

    async def system_environment(self, host_id: str = "localhost") -> Dict[str, Any]:
        """Переменные окружения с автоматической фильтрацией секретов."""
        async def _h(tr: BaseTransport, plat: str, _p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxSystemAdapter.system_environment(tr)
            return await WindowsSystemAdapter.system_environment(tr)

        return await self.rt.engine.dispatch(host_id, "system.environment", {}, _h)


def register_system_tools(mcp: MCPServer, runtime: SSHMCPRuntime) -> SystemToolsModule:
    """Регистрация 7 инструментов системного администрирования в MCPServer."""
    mod = SystemToolsModule(runtime)

    @mcp.tool(name="system_info", description="Получение унифицированных сведений об ОС (Windows/Linux)")
    async def system_info(host_id: str = "localhost") -> Dict[str, Any]:
        return await mod.system_info(host_id)

    @mcp.tool(name="system_cpu", description="Получение загрузки и числа ядер процессора")
    async def system_cpu(host_id: str = "localhost") -> Dict[str, Any]:
        return await mod.system_cpu(host_id)

    @mcp.tool(name="system_memory", description="Получение объёма общей, занятой и доступной памяти в МБ")
    async def system_memory(host_id: str = "localhost") -> Dict[str, Any]:
        return await mod.system_memory(host_id)

    @mcp.tool(name="system_disks", description="Получение списка томов и свободного места на дисках")
    async def system_disks(host_id: str = "localhost") -> Dict[str, Any]:
        return await mod.system_disks(host_id)

    @mcp.tool(name="system_uptime", description="Получение времени непрерывной работы ОС")
    async def system_uptime(host_id: str = "localhost") -> Dict[str, Any]:
        return await mod.system_uptime(host_id)

    @mcp.tool(name="system_boot_info", description="Получение сведений о последней загрузке системы")
    async def system_boot_info(host_id: str = "localhost") -> Dict[str, Any]:
        return await mod.system_boot_info(host_id)

    @mcp.tool(name="system_environment", description="Получение очищенных от секретов переменных окружения")
    async def system_environment(host_id: str = "localhost") -> Dict[str, Any]:
        return await mod.system_environment(host_id)

    return mod
