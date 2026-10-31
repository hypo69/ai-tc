# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: MCP-инструменты диагностики и телеметрии (Diagnostic & Telemetry)
# =============================================================================
# Description:
#   Реализация группы инструментов 4.10 ТЗ:
#   diagnostics_collect, diagnostics_hardware, diagnostics_os,
#   diagnostics_storage, diagnostics_network, diagnostics_services,
#   diagnostics_export.
#   Формирует структурированный диагностический пакет DiagnosticPackage,
#   сохраняет его в таблицу `diagnostics` SQLite и подготавливает данные для
#   RAG и исторической корреляции ai-tc (Раздел 4.10 и 15 ТЗ).
#
# File: diagnostics.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.mcp_tools
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 17:00:15
# =============================================================================

from typing import Any, Dict
import uuid
from mcp.server import MCPServer

from ..bootstrap import SSHMCPRuntime
from ..platforms.linux.network import LinuxNetworkAdapter
from ..platforms.linux.services import LinuxServiceAdapter
from ..platforms.linux.system import LinuxSystemAdapter
from ..platforms.windows.network import WindowsNetworkAdapter
from ..platforms.windows.services import WindowsServiceAdapter
from ..platforms.windows.system import WindowsSystemAdapter
from ..schemas.diagnostics import DiagnosticPackage
from ..transports.base import BaseTransport


class DiagnosticsToolsModule:
    """Модуль сбора диагностической телеметрии и интеграции с БД/RAG ai-tc (Раздел 4.10 ТЗ)."""

    def __init__(self, runtime: SSHMCPRuntime) -> None:
        """Инициализация модуля диагностики."""
        self.rt = runtime

    async def diagnostics_os(self, host_id: str = "localhost") -> Dict[str, Any]:
        """Диагностический срез операционной системы и аптайма."""
        async def _h(tr: BaseTransport, plat: str, _p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                info = await LinuxSystemAdapter.system_info(tr)
                up = await LinuxSystemAdapter.system_uptime(tr)
            else:
                info = await WindowsSystemAdapter.system_info(tr)
                up = await WindowsSystemAdapter.system_uptime(tr)
            return {"os": info, "uptime_seconds": up.get("uptime_seconds", 0)}

        return await self.rt.engine.dispatch(host_id, "diagnostics.os", {}, _h)

    async def diagnostics_hardware(self, host_id: str = "localhost") -> Dict[str, Any]:
        """Диагностический срез оборудования (CPU и оперативная память)."""
        async def _h(tr: BaseTransport, plat: str, _p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                cpu = await LinuxSystemAdapter.system_cpu(tr)
                mem = await LinuxSystemAdapter.system_memory(tr)
            else:
                cpu = await WindowsSystemAdapter.system_cpu(tr)
                mem = await WindowsSystemAdapter.system_memory(tr)
            return {"cpu": cpu, "memory": mem}

        return await self.rt.engine.dispatch(host_id, "diagnostics.hardware", {}, _h)

    async def diagnostics_storage(self, host_id: str = "localhost") -> Dict[str, Any]:
        """Диагностика дисковой подсистемы и свободного места."""
        async def _h(tr: BaseTransport, plat: str, _p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxSystemAdapter.system_disks(tr)
            return await WindowsSystemAdapter.system_disks(tr)

        return await self.rt.engine.dispatch(host_id, "diagnostics.storage", {}, _h)

    async def diagnostics_network(self, host_id: str = "localhost") -> Dict[str, Any]:
        """Диагностика сетевых интерфейсов и активных сокетов."""
        async def _h(tr: BaseTransport, plat: str, _p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                ifaces = await LinuxNetworkAdapter.network_interfaces(tr)
                dns = await LinuxNetworkAdapter.network_dns(tr)
            else:
                ifaces = await WindowsNetworkAdapter.network_interfaces(tr)
                dns = await WindowsNetworkAdapter.network_dns(tr)
            return {"interfaces": ifaces.get("interfaces", []), "dns": dns.get("dns_servers", [])}

        return await self.rt.engine.dispatch(host_id, "diagnostics.network", {}, _h)

    async def diagnostics_services(self, host_id: str = "localhost") -> Dict[str, Any]:
        """Диагностика состояния системных служб."""
        async def _h(tr: BaseTransport, plat: str, _p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                return await LinuxServiceAdapter.service_list(tr, limit=25)
            return await WindowsServiceAdapter.service_list(tr, limit=25)

        return await self.rt.engine.dispatch(host_id, "diagnostics.services", {}, _h)

    async def diagnostics_collect(self, host_id: str = "localhost") -> Dict[str, Any]:
        """Полный сбор диагностического пакета узла с расчётом Health Score и записью в SQLite."""
        async def _h(tr: BaseTransport, plat: str, _p: Dict[str, Any]) -> Dict[str, Any]:
            if plat == "linux":
                os_d = await LinuxSystemAdapter.system_info(tr)
                cpu_d = await LinuxSystemAdapter.system_cpu(tr)
                mem_d = await LinuxSystemAdapter.system_memory(tr)
                dsk_d = await LinuxSystemAdapter.system_disks(tr)
                net_d = await LinuxNetworkAdapter.network_interfaces(tr)
                srv_d = await LinuxServiceAdapter.service_list(tr, limit=15)
            else:
                os_d = await WindowsSystemAdapter.system_info(tr)
                cpu_d = await WindowsSystemAdapter.system_cpu(tr)
                mem_d = await WindowsSystemAdapter.system_memory(tr)
                dsk_d = await WindowsSystemAdapter.system_disks(tr)
                net_d = await WindowsNetworkAdapter.network_interfaces(tr)
                srv_d = await WindowsServiceAdapter.service_list(tr, limit=15)

            total_mb = max(1, int(mem_d.get("total_mb", 1)))
            used_mb = int(mem_d.get("used_mb", 0))
            mem_ratio = used_mb / total_mb
            score = 100
            if mem_ratio > 0.90:
                score -= 20
            elif mem_ratio > 0.80:
                score -= 10

            pkg = DiagnosticPackage(
                report_id=f"diag-{uuid.uuid4().hex[:10]}",
                host_id=host_id,
                platform=plat,
                os_info={k: v for k, v in os_d.items() if not k.startswith("_")},
                hardware={
                    "cpu": {k: v for k, v in cpu_d.items() if not k.startswith("_")},
                    "memory": {k: v for k, v in mem_d.items() if not k.startswith("_")},
                },
                storage=list(dsk_d.get("disks", [])),
                network={"interfaces": list(net_d.get("interfaces", []))},
                services=list(srv_d.get("services", [])),
                health_score=score,
            )
            self.rt.diagnostics_repo.save_report(pkg)
            return pkg.model_dump()

        return await self.rt.engine.dispatch(host_id, "diagnostics.collect", {}, _h)

    async def diagnostics_export(self, host_id: str = "localhost") -> Dict[str, Any]:
        """Экспорт последнего диагностического пакета из SQLite для RAG-индексации."""
        latest = self.rt.diagnostics_repo.get_latest_report(host_id)
        if not latest:
            return await self.diagnostics_collect(host_id)
        return self.rt.normalizer.success(
            host=host_id,
            platform=str(latest.get("platform", "windows")),
            operation="diagnostics.export",
            data=dict(latest.get("payload", {})),  # type: ignore[arg-type]
        )


def register_diagnostics_tools(mcp: MCPServer, runtime: SSHMCPRuntime) -> DiagnosticsToolsModule:
    """Регистрация 7 инструментов диагностики и телеметрии в MCPServer."""
    mod = DiagnosticsToolsModule(runtime)

    @mcp.tool(name="diagnostics_collect", description="Сбор полного диагностического пакета и сохранение в SQLite")
    async def diagnostics_collect(host_id: str = "localhost") -> Dict[str, Any]:
        return await mod.diagnostics_collect(host_id)

    @mcp.tool(name="diagnostics_hardware", description="Диагностика процессора и памяти")
    async def diagnostics_hardware(host_id: str = "localhost") -> Dict[str, Any]:
        return await mod.diagnostics_hardware(host_id)

    @mcp.tool(name="diagnostics_os", description="Диагностика версии ОС и аптайма")
    async def diagnostics_os(host_id: str = "localhost") -> Dict[str, Any]:
        return await mod.diagnostics_os(host_id)

    @mcp.tool(name="diagnostics_storage", description="Диагностика дисковых томов")
    async def diagnostics_storage(host_id: str = "localhost") -> Dict[str, Any]:
        return await mod.diagnostics_storage(host_id)

    @mcp.tool(name="diagnostics_network", description="Диагностика сетевых интерфейсов и DNS")
    async def diagnostics_network(host_id: str = "localhost") -> Dict[str, Any]:
        return await mod.diagnostics_network(host_id)

    @mcp.tool(name="diagnostics_services", description="Диагностическая сводка служб")
    async def diagnostics_services(host_id: str = "localhost") -> Dict[str, Any]:
        return await mod.diagnostics_services(host_id)

    @mcp.tool(name="diagnostics_export", description="Экспорт диагностического пакета из SQLite для RAG")
    async def diagnostics_export(host_id: str = "localhost") -> Dict[str, Any]:
        return await mod.diagnostics_export(host_id)

    return mod
