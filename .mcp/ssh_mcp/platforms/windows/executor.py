# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Исполнитель команд Windows (PowerShell 7+, PS 5.1, CMD)
# =============================================================================
# Description:
#   Безопасный запуск команд и скриптов на платформе Windows через транспортный
#   уровень с поддержкой UAC/привилегий и автоматической конвертацией в JSON.
#
# File: executor.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.platforms.windows
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:52:15
# =============================================================================

from typing import Any, Dict, List, Optional
from ...transports.base import BaseTransport, RawExecutionResult
from ..base import pack_raw_result, safe_parse_json


class WindowsExecutor:
    """Адаптер выполнения команд и PowerShell-скриптов на платформе Windows.

    Examples:
        >>> ex = WindowsExecutor()
    """

    @staticmethod
    async def run_ps_json(
        transport: BaseTransport, ps_script: str, timeout: int = 30
    ) -> Dict[str, Any]:
        """Выполнение выражения PowerShell с конвертацией в JSON и разбором результата.

        Args:
            transport (BaseTransport): Транспорт узла.
            ps_script (str): Скрипт PowerShell.
            timeout (int): Таймаут в секундах.

        Returns:
            Dict[str, Any]: Разобранный результат со служебными метриками.

        Examples:
            >>> pass
        """
        raw: RawExecutionResult = await transport.execute_command(
            command=ps_script,
            shell="powershell",
            timeout=timeout,
        )
        parsed = safe_parse_json(raw.stdout)
        return pack_raw_result(raw, parsed)

    @staticmethod
    async def execute(
        transport: BaseTransport,
        command: str,
        args: Optional[List[str]] = [],
        shell: str = "powershell",
        timeout: int = 60,
    ) -> Dict[str, Any]:
        """Выполнение произвольной команды с раздельной передачей аргументов.

        Args:
            transport (BaseTransport): Транспорт узла.
            command (str): Команда.
            args (Optional[List[str]]): Аргументы.
                                        Значение по умолчанию: [].
            shell (str): Оболочка ('powershell', 'pwsh', 'cmd').
            timeout (int): Таймаут в секундах.

        Returns:
            Dict[str, Any]: Результат выполнения.

        Examples:
            >>> pass
        """
        raw = await transport.execute_command(
            command=command,
            args=args if args else [],
            shell=shell,
            timeout=timeout,
        )
        return pack_raw_result(raw, {"output": raw.stdout, "stderr": raw.stderr})
