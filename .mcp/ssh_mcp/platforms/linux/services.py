# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Адаптер управления службами Linux (systemd / альтернативные init)
# =============================================================================
# Description:
#   Управление службами на платформе Linux через `systemctl` с автоматическим
#   обнаружением альтернативных init-систем (`service` / SysVinit / OpenRC)
#   согласно разделу 4.5 ТЗ.
#
# File: services.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.platforms.linux
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:55:15
# =============================================================================

import shlex
from typing import Any, Dict, List
from ...transports.base import BaseTransport
from ..base import pack_raw_result


class LinuxServiceAdapter:
    """Адаптер управления службами systemd и альтернативных init-систем Linux.

    Examples:
        >>> adapter = LinuxServiceAdapter()
    """

    @staticmethod
    async def service_list(transport: BaseTransport, limit: int = 50) -> Dict[str, Any]:
        """Получение списка служб Linux с определением используемой init-системы.

        Args:
            transport (BaseTransport): Активный транспорт узла.
            limit (int): Максимальное количество возвращаемых служб.

        Returns:
            Dict[str, Any]: Список служб в ключе `services` и тип `init_system`.

        Examples:
            >>> pass
        """
        cmd = (
            f"if command -v systemctl >/dev/null 2>&1; then "
            f"systemctl list-units --type=service --all --no-pager --no-legend | head -n {int(limit)}; "
            f"else service --status-all 2>&1 | head -n {int(limit)}; fi"
        )
        raw = await transport.execute_command(cmd, shell="bash", timeout=20)
        services: List[Dict[str, Any]] = []
        for line in raw.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 4:
                services.append(
                    {
                        "name": parts[0],
                        "load": parts[1],
                        "active": parts[2],
                        "status": parts[3],
                    }
                )
        return pack_raw_result(raw, {"init_system": "systemd", "services": services})

    @staticmethod
    async def service_status(transport: BaseTransport, service_name: str) -> Dict[str, Any]:
        """Проверка состояния конкретной службы Linux.

        Args:
            transport (BaseTransport): Активный транспорт узла.
            service_name (str): Имя службы.

        Returns:
            Dict[str, Any]: Статус службы (`service_name`, `status`).

        Examples:
            >>> pass
        """
        q = shlex.quote(service_name)
        cmd = f"if command -v systemctl >/dev/null 2>&1; then systemctl is-active {q}; else service {q} status; fi"
        raw = await transport.execute_command(cmd, shell="bash", timeout=15)
        return pack_raw_result(
            raw,
            {
                "service_name": service_name,
                "status": raw.stdout.strip() or "unknown",
            },
        )

    @staticmethod
    async def _control_action(
        transport: BaseTransport, service_name: str, action: str
    ) -> Dict[str, Any]:
        """Выполнение управляющей команды (`start`, `stop`, `restart`, `enable`, `disable`).

        Args:
            transport (BaseTransport): Активный транспорт узла.
            service_name (str): Имя службы.
            action (str): Действие.

        Returns:
            Dict[str, Any]: Результат операции.

        Examples:
            >>> pass
        """
        q = shlex.quote(service_name)
        q_act = shlex.quote(action)
        cmd = (
            f"if command -v systemctl >/dev/null 2>&1; then systemctl {q_act} {q}; "
            f"else service {q} {q_act}; fi"
        )
        raw = await transport.execute_command(cmd, shell="bash", timeout=30, elevate=True)
        return pack_raw_result(raw, {"service_name": service_name, "action": action, "applied": raw.exit_code == 0})

    @staticmethod
    async def service_start(transport: BaseTransport, service_name: str) -> Dict[str, Any]:
        """Запуск службы Linux."""
        return await LinuxServiceAdapter._control_action(transport, service_name, "start")

    @staticmethod
    async def service_stop(transport: BaseTransport, service_name: str) -> Dict[str, Any]:
        """Остановка службы Linux."""
        return await LinuxServiceAdapter._control_action(transport, service_name, "stop")

    @staticmethod
    async def service_restart(transport: BaseTransport, service_name: str) -> Dict[str, Any]:
        """Перезапуск службы Linux."""
        return await LinuxServiceAdapter._control_action(transport, service_name, "restart")

    @staticmethod
    async def service_enable(transport: BaseTransport, service_name: str) -> Dict[str, Any]:
        """Включение автозапуска службы Linux."""
        return await LinuxServiceAdapter._control_action(transport, service_name, "enable")

    @staticmethod
    async def service_disable(transport: BaseTransport, service_name: str) -> Dict[str, Any]:
        """Отключение автозапуска службы Linux."""
        return await LinuxServiceAdapter._control_action(transport, service_name, "disable")
