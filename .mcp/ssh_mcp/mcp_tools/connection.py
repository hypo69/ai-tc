# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: MCP-инструменты управления подключениями (Connection Management)
# =============================================================================
# Description:
#   Реализация группы инструментов 4.1 ТЗ:
#   ssh_connect, ssh_disconnect, ssh_reconnect, ssh_connection_status,
#   ssh_list_connections, ssh_test_connection, ssh_host_fingerprint.
#
# File: connection.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.mcp_tools
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:58:00
# =============================================================================

import time
from typing import Any, Dict
from mcp.server import MCPServer
from ..bootstrap import SSHMCPRuntime
from ..security.host_verification import HostVerificationError


class ConnectionToolsModule:
    """Модуль инструментов управления SSH-подключениями (Раздел 4.1 ТЗ).

    Attributes:
        rt (SSHMCPRuntime): Контейнер сервисов ядра.

    Examples:
        >>> from ssh_mcp.bootstrap import create_runtime
        >>> mod = ConnectionToolsModule(create_runtime(db_path=":memory:"))
    """

    def __init__(self, runtime: SSHMCPRuntime) -> None:
        """Инициализация модуля подключений.

        Args:
            runtime (SSHMCPRuntime): Контейнер сервисов ядра.

        Examples:
            >>> pass
        """
        self.rt = runtime

    async def ssh_connect(self, host_id: str = "localhost") -> Dict[str, Any]:
        """Создание подключения к узлу и добавление в Connection Pool."""
        started = time.perf_counter()
        try:
            cfg = self.rt.connection_manager.get_host_config(host_id)
            info = await self.rt.connection_manager.connect(host_id)
            self.rt.audit_logger.log_event(host_id, "ssh.connect", "low", "success", info.model_dump())
            return self.rt.normalizer.success(
                host=host_id,
                platform=cfg.platform,
                operation="ssh.connect",
                data=info.model_dump(),
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
        except HostVerificationError as exc:
            self.rt.audit_logger.log_event(host_id, "ssh.connect", "high", "denied", {"error": str(exc)})
            return self.rt.normalizer.failure(
                host_id, "windows", "ssh.connect", "HOST_KEY_VERIFICATION_FAILED", str(exc)
            )
        except Exception as exc:
            self.rt.audit_logger.log_event(host_id, "ssh.connect", "low", "failed", {"error": str(exc)})
            return self.rt.normalizer.failure(
                host_id, "windows", "ssh.connect", "CONNECTION_FAILED", str(exc)
            )

    async def ssh_disconnect(self, host_id: str = "localhost") -> Dict[str, Any]:
        """Закрытие активного подключения к узлу."""
        info = await self.rt.connection_manager.disconnect(host_id)
        self.rt.audit_logger.log_event(host_id, "ssh.disconnect", "low", "success", info.model_dump())
        return self.rt.normalizer.success(
            host=host_id,
            platform="windows",
            operation="ssh.disconnect",
            data=info.model_dump(),
        )

    async def ssh_reconnect(self, host_id: str = "localhost") -> Dict[str, Any]:
        """Повторное подключение к узлу с контролем лимита попыток."""
        try:
            info = await self.rt.connection_manager.reconnect(host_id)
            return self.rt.normalizer.success(
                host=host_id,
                platform="windows",
                operation="ssh.reconnect",
                data=info.model_dump(),
            )
        except Exception as exc:
            return self.rt.normalizer.failure(
                host_id, "windows", "ssh.reconnect", "RECONNECT_FAILED", str(exc)
            )

    async def ssh_connection_status(self, host_id: str = "localhost") -> Dict[str, Any]:
        """Проверка состояния подключения к узлу."""
        info = await self.rt.connection_manager.get_status(host_id)
        return self.rt.normalizer.success(
            host=host_id,
            platform="windows",
            operation="ssh.connection_status",
            data=info.model_dump(),
        )

    async def ssh_list_connections(self) -> Dict[str, Any]:
        """Получение списка всех активных и зарегистрированных подключений."""
        conns = self.rt.connection_manager.list_active_connections()
        return self.rt.normalizer.success(
            host="localhost",
            platform="windows",
            operation="ssh.list_connections",
            data={"connections": conns, "count": len(conns)},
        )

    async def ssh_test_connection(self, host_id: str = "localhost") -> Dict[str, Any]:
        """Проверка доступности и работоспособности подключения к узлу."""
        started = time.perf_counter()
        try:
            tr = await self.rt.connection_manager.get_transport(host_id)
            alive = await tr.is_alive()
            elapsed = int((time.perf_counter() - started) * 1000)
            return self.rt.normalizer.success(
                host=host_id,
                platform="windows",
                operation="ssh.test_connection",
                data={"reachable": alive, "latency_ms": elapsed},
                duration_ms=elapsed,
            )
        except Exception as exc:
            return self.rt.normalizer.failure(
                host_id, "windows", "ssh.test_connection", "UNREACHABLE", str(exc)
            )

    async def ssh_host_fingerprint(self, host_id: str = "localhost") -> Dict[str, Any]:
        """Получение криптографического отпечатка SSH-ключа узла."""
        try:
            tr = await self.rt.connection_manager.get_transport(host_id)
            fp = await tr.get_fingerprint()
            return self.rt.normalizer.success(
                host=host_id,
                platform="windows",
                operation="ssh.host_fingerprint",
                data={"host_id": host_id, "fingerprint": fp},
            )
        except Exception as exc:
            return self.rt.normalizer.failure(
                host_id, "windows", "ssh.host_fingerprint", "FINGERPRINT_ERROR", str(exc)
            )


def register_connection_tools(mcp: MCPServer, runtime: SSHMCPRuntime) -> ConnectionToolsModule:
    """Регистрация 7 инструментов управления подключениями в MCPServer.

    Args:
        mcp (MCPServer): Экземпляр сервера MCP v2.
        runtime (SSHMCPRuntime): Контейнер сервисов ядра.

    Returns:
        ConnectionToolsModule: Зарегистрированный модуль.

    Examples:
        >>> pass
    """
    mod = ConnectionToolsModule(runtime)

    @mcp.tool(name="ssh_connect", description="Создание SSH-подключения к удалённому или локальному узлу")
    async def ssh_connect(host_id: str = "localhost") -> Dict[str, Any]:
        return await mod.ssh_connect(host_id)

    @mcp.tool(name="ssh_disconnect", description="Закрытие активного SSH-подключения к узлу")
    async def ssh_disconnect(host_id: str = "localhost") -> Dict[str, Any]:
        return await mod.ssh_disconnect(host_id)

    @mcp.tool(name="ssh_reconnect", description="Повторное подключение к узлу с ограничением попыток")
    async def ssh_reconnect(host_id: str = "localhost") -> Dict[str, Any]:
        return await mod.ssh_reconnect(host_id)

    @mcp.tool(name="ssh_connection_status", description="Проверка состояния подключения к узлу")
    async def ssh_connection_status(host_id: str = "localhost") -> Dict[str, Any]:
        return await mod.ssh_connection_status(host_id)

    @mcp.tool(name="ssh_list_connections", description="Список всех активных подключений в пуле")
    async def ssh_list_connections() -> Dict[str, Any]:
        return await mod.ssh_list_connections()

    @mcp.tool(name="ssh_test_connection", description="Проверка доступности и отклика узла")
    async def ssh_test_connection(host_id: str = "localhost") -> Dict[str, Any]:
        return await mod.ssh_test_connection(host_id)

    @mcp.tool(name="ssh_host_fingerprint", description="Получение SHA-256 отпечатка ключа SSH-сервера")
    async def ssh_host_fingerprint(host_id: str = "localhost") -> Dict[str, Any]:
        return await mod.ssh_host_fingerprint(host_id)

    return mod
