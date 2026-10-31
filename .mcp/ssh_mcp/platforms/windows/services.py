# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Адаптер управления службами Windows (SCM / PowerShell)
# =============================================================================
# Description:
#   Управление системными службами Windows (service_list, service_status,
#   service_start, service_stop, service_restart, service_enable,
#   service_disable) согласно разделу 4.5 ТЗ.
#
# File: services.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.platforms.windows
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:53:00
# =============================================================================

from typing import Any, Dict
from ...transports.base import BaseTransport
from .executor import WindowsExecutor


class WindowsServiceAdapter:
    """Адаптер управления службами Windows через Service Control Manager / PowerShell.

    Examples:
        >>> adapter = WindowsServiceAdapter()
    """

    @staticmethod
    def _quote(name: str) -> str:
        """Безопасное экранирование имени службы для PowerShell.

        Args:
            name (str): Имя службы.

        Returns:
            str: Экранированная строка.

        Examples:
            >>> WindowsServiceAdapter._quote("Spooler")
            'Spooler'
        """
        return str(name).replace("'", "''")

    @staticmethod
    async def service_list(transport: BaseTransport, limit: int = 50) -> Dict[str, Any]:
        """Получение списка служб Windows и их текущего статуса.

        Args:
            transport (BaseTransport): Активный транспорт узла.
            limit (int): Максимальное количество возвращаемых служб.

        Returns:
            Dict[str, Any]: Список служб в ключе `services`.

        Examples:
            >>> pass
        """
        ps = (
            f"Get-Service | Select-Object -First {int(limit)} "
            "@{N='name';E={$_.Name}}, @{N='display_name';E={$_.DisplayName}}, "
            "@{N='status';E={$_.Status.ToString()}}, @{N='start_type';E={$_.StartType.ToString()}} "
            "| ConvertTo-Json -Compress"
        )
        res = await WindowsExecutor.run_ps_json(transport, ps)
        items = res.get("items", [res] if "name" in res else [])
        res["services"] = items
        return res

    @staticmethod
    async def service_status(transport: BaseTransport, service_name: str) -> Dict[str, Any]:
        """Получение статуса конкретной службы Windows.

        Args:
            transport (BaseTransport): Активный транспорт.
            service_name (str): Системное имя службы.

        Returns:
            Dict[str, Any]: Состояние службы (`name`, `status`, `start_type`).

        Examples:
            >>> pass
        """
        q = WindowsServiceAdapter._quote(service_name)
        ps = (
            f"$s = Get-Service -Name '{q}' -ErrorAction Stop; "
            "@{name=$s.Name; display_name=$s.DisplayName; status=$s.Status.ToString(); "
            "start_type=$s.StartType.ToString()} | ConvertTo-Json -Compress"
        )
        return await WindowsExecutor.run_ps_json(transport, ps)

    @staticmethod
    async def service_start(transport: BaseTransport, service_name: str) -> Dict[str, Any]:
        """Запуск службы Windows.

        Args:
            transport (BaseTransport): Активный транспорт.
            service_name (str): Имя службы.

        Returns:
            Dict[str, Any]: Статус после запуска.

        Examples:
            >>> pass
        """
        q = WindowsServiceAdapter._quote(service_name)
        ps = f"Start-Service -Name '{q}' -ErrorAction Stop; @{{service_name='{q}'; status='Running'}} | ConvertTo-Json -Compress"
        return await WindowsExecutor.run_ps_json(transport, ps)

    @staticmethod
    async def service_stop(transport: BaseTransport, service_name: str) -> Dict[str, Any]:
        """Остановка службы Windows.

        Args:
            transport (BaseTransport): Активный транспорт.
            service_name (str): Имя службы.

        Returns:
            Dict[str, Any]: Статус после остановки.

        Examples:
            >>> pass
        """
        q = WindowsServiceAdapter._quote(service_name)
        ps = f"Stop-Service -Name '{q}' -Force -ErrorAction Stop; @{{service_name='{q}'; status='Stopped'}} | ConvertTo-Json -Compress"
        return await WindowsExecutor.run_ps_json(transport, ps)

    @staticmethod
    async def service_restart(transport: BaseTransport, service_name: str) -> Dict[str, Any]:
        """Перезапуск службы Windows.

        Args:
            transport (BaseTransport): Активный транспорт.
            service_name (str): Имя службы.

        Returns:
            Dict[str, Any]: Статус после перезапуска.

        Examples:
            >>> pass
        """
        q = WindowsServiceAdapter._quote(service_name)
        ps = f"Restart-Service -Name '{q}' -Force -ErrorAction Stop; @{{service_name='{q}'; status='Running'}} | ConvertTo-Json -Compress"
        return await WindowsExecutor.run_ps_json(transport, ps)

    @staticmethod
    async def service_enable(transport: BaseTransport, service_name: str) -> Dict[str, Any]:
        """Включение автоматического запуска службы Windows.

        Args:
            transport (BaseTransport): Активный транспорт.
            service_name (str): Имя службы.

        Returns:
            Dict[str, Any]: Подтверждение изменения StartupType на Automatic.

        Examples:
            >>> pass
        """
        q = WindowsServiceAdapter._quote(service_name)
        ps = f"Set-Service -Name '{q}' -StartupType Automatic -ErrorAction Stop; @{{service_name='{q}'; start_type='Automatic'}} | ConvertTo-Json -Compress"
        return await WindowsExecutor.run_ps_json(transport, ps)

    @staticmethod
    async def service_disable(transport: BaseTransport, service_name: str) -> Dict[str, Any]:
        """Отключение автозапуска службы Windows (StartupType = Disabled).

        Args:
            transport (BaseTransport): Активный транспорт.
            service_name (str): Имя службы.

        Returns:
            Dict[str, Any]: Подтверждение изменения StartupType на Disabled.

        Examples:
            >>> pass
        """
        q = WindowsServiceAdapter._quote(service_name)
        ps = f"Set-Service -Name '{q}' -StartupType Disabled -ErrorAction Stop; @{{service_name='{q}'; start_type='Disabled'}} | ConvertTo-Json -Compress"
        return await WindowsExecutor.run_ps_json(transport, ps)
