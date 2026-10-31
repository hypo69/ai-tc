# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Исполнитель команд Linux (Bash / POSIX sh / sudo)
# =============================================================================
# Description:
#   Безопасный запуск команд и скриптов на узлах Linux с раздельным
#   экранированием аргументов и поддержкой контролируемого повышения
#   привилегий через `sudo -n`.
#
# File: executor.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.platforms.linux
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:54:30
# =============================================================================

from typing import Any, Dict, List, Optional
from ...transports.base import BaseTransport, RawExecutionResult
from ..base import pack_raw_result, safe_parse_json


class LinuxExecutor:
    """Адаптер выполнения команд Bash и POSIX Shell на платформе Linux.

    Examples:
        >>> ex = LinuxExecutor()
    """

    @staticmethod
    async def run_bash(
        transport: BaseTransport,
        script: str,
        args: Optional[List[str]] = [],
        timeout: int = 30,
        elevate: bool = False,
    ) -> Dict[str, Any]:
        """Выполнение команды или скрипта Bash с упаковкой результата.

        Args:
            transport (BaseTransport): Активный транспорт узла.
            script (str): Команда или скрипт.
            args (Optional[List[str]]): Позиционные аргументы.
                                        Значение по умолчанию: [].
            timeout (int): Таймаут ожидания в секундах.
            elevate (bool): Признак запуска с привилегиями sudo.

        Returns:
            Dict[str, Any]: Разобранный результат выполнения.

        Examples:
            >>> pass
        """
        raw: RawExecutionResult = await transport.execute_command(
            command=script,
            args=args if args else [],
            shell="bash",
            timeout=timeout,
            elevate=elevate,
        )
        parsed = safe_parse_json(raw.stdout)
        return pack_raw_result(raw, parsed)
