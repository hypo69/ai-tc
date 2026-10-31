# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Локальный транспорт выполнения команд (Local Transport)
# =============================================================================
# Description:
#   Асинхронное выполнение административных команд на локальном узле (в режиме
#   Remote MCP Agent или при обращении к localhost) с поддержкой PowerShell 7+,
#   Windows PowerShell 5.1, CMD, Bash и POSIX sh.
#
#   Зачем нужен этот модуль:
#     1. Обеспечение работы Remote MCP Server без накладных расходов SSH-петли.
#     2. Строгое экранирование и раздельная передача аргументов для защиты от
#        командных инъекций (Раздел 4.2 ТЗ).
#
# Usage Examples:
#   Python API:
#     from ssh_mcp.transports.local_transport import LocalTransport
#     tr = LocalTransport("local-win", platform_name="windows")
#     await tr.connect()
#
# File: local_transport.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.transports
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:46:00
# =============================================================================

import asyncio
import hashlib
import os
import shlex
import shutil
import socket
import time
from typing import Dict, List, Optional

from .base import BaseTransport, RawExecutionResult


def build_safe_shell_invocation(
    command: str,
    args: List[str],
    shell: str,
    platform_name: str,
    elevate: bool = False,
) -> List[str]:
    """Формирование безопасного массива аргументов запуска оболочки без инъекций.

    Args:
        command (str): Исполняемая команда или тело скрипта.
        args (List[str]): Список отдельных аргументов.
        shell (str): Имя оболочки ('powershell', 'pwsh', 'cmd', 'bash', 'sh', 'default').
        platform_name (str): Целевая платформа ('windows' или 'linux').
        elevate (bool): Требуется ли повышение привилегий (sudo на Linux).

    Returns:
        List[str]: Список аргументов для передачи в subprocess / SSH.

    Examples:
        >>> argv = build_safe_shell_invocation("Get-Date", [], "powershell", "windows")
        >>> argv[0] in ("pwsh", "powershell")
        True
    """
    safe_args = [str(a) for a in args] if args else []

    if platform_name == "windows" or shell in ("powershell", "pwsh", "cmd"):
        if shell == "cmd":
            escaped = " ".join([command] + [f'"{a.replace(chr(34), "")}"' for a in safe_args])
            return ["cmd.exe", "/d", "/s", "/c", escaped]

        ps_bin = "pwsh" if (shell == "pwsh" or shutil.which("pwsh")) else "powershell"
        if safe_args:
            quoted_args = " ".join("'" + a.replace("'", "''") + "'" for a in safe_args)
            full_ps = f"{command} {quoted_args}"
        else:
            full_ps = command
        return [ps_bin, "-NoProfile", "-NonInteractive", "-Command", full_ps]

    shell_bin = "/bin/bash" if shell in ("bash", "default") else "/bin/sh"
    if safe_args:
        quoted_posix = " ".join(shlex.quote(a) for a in safe_args)
        full_sh = f"{command} {quoted_posix}"
    else:
        full_sh = command

    if elevate:
        return ["sudo", "-n", shell_bin, "-c", full_sh]
    return [shell_bin, "-c", full_sh]


class LocalTransport(BaseTransport):
    """Транспорт прямого локального выполнения команд через asyncio.subprocess.

    Attributes:
        host_id (str): Идентификатор узла.
        platform_name (str): Операционная система ('windows' или 'linux').

    Examples:
        >>> tr = LocalTransport("local-node", "windows")
        >>> tr.host_id
        'local-node'
    """

    def __init__(self, host_id: str = "localhost", platform_name: str = "windows") -> None:
        """Инициализация локального транспорта.

        Args:
            host_id (str): Идентификатор локального хоста.
            platform_name (str): Название платформы ('windows' или 'linux').

        Examples:
            >>> tr = LocalTransport("localhost", "windows")
        """
        super().__init__(host_id=host_id)
        self.platform_name = platform_name

    async def connect(self) -> bool:
        """Активация локального транспорта.

        Returns:
            bool: Всегда True для локального узла.

        Examples:
            >>> import asyncio
            >>> tr = LocalTransport()
            >>> asyncio.run(tr.connect())
            True
        """
        self.connected = True
        return True

    async def disconnect(self) -> bool:
        """Деактивация локального транспорта.

        Returns:
            bool: True при успешном отключении.

        Examples:
            >>> import asyncio
            >>> tr = LocalTransport()
            >>> asyncio.run(tr.disconnect())
            True
        """
        self.connected = False
        return True

    async def is_alive(self) -> bool:
        """Проверка готовности локального транспорта.

        Returns:
            bool: Текущее состояние флага `connected`.

        Examples:
            >>> import asyncio
            >>> tr = LocalTransport()
            >>> _ = asyncio.run(tr.connect())
            >>> asyncio.run(tr.is_alive())
            True
        """
        return self.connected

    async def get_fingerprint(self) -> str:
        """Генерация детерминированного SHA-256 отпечатка локального узла.

        Returns:
            str: Строка отпечатка `SHA256:...`.

        Examples:
            >>> import asyncio
            >>> tr = LocalTransport()
            >>> asyncio.run(tr.get_fingerprint()).startswith("SHA256:")
            True
        """
        ident = f"local:{socket.gethostname()}:{self.host_id}".encode("utf-8")
        digest = hashlib.sha256(ident).hexdigest()[:43]
        return f"SHA256:{digest}"

    async def execute_command(
        self,
        command: str,
        args: Optional[List[str]] = [],
        env: Optional[Dict[str, str]] = {},
        shell: str = "default",
        timeout: int = 60,
        elevate: bool = False,
    ) -> RawExecutionResult:
        """Асинхронное выполнение команды на локальной машине с контролем таймаута.

        Args:
            command (str): Исполняемая команда.
            args (Optional[List[str]]): Позиционные аргументы.
                                        Значение по умолчанию: [].
            env (Optional[Dict[str, str]]): Дополнительные переменные окружения.
                                            Значение по умолчанию: {}.
            shell (str): Оболочка ('powershell', 'pwsh', 'cmd', 'bash', 'sh', 'default').
            timeout (int): Таймаут ожидания в секундах.
            elevate (bool): Флаг повышения привилегий.

        Returns:
            RawExecutionResult: Результат выполнения.

        Exceptions:
            TimeoutError: При превышении времени ожидания `timeout`.

        Examples:
            >>> import asyncio
            >>> tr = LocalTransport("localhost", "windows")
            >>> _ = asyncio.run(tr.connect())
            >>> res = asyncio.run(tr.execute_command("Write-Output 'hello'", shell="powershell"))
            >>> res.exit_code
            0
        """
        if not self.connected:
            await self.connect()

        argv = build_safe_shell_invocation(
            command=command,
            args=args if args else [],
            shell=shell,
            platform_name=self.platform_name,
            elevate=elevate,
        )

        merged_env = os.environ.copy()
        if env:
            for k, v in env.items():
                merged_env[str(k)] = str(v)

        started = time.perf_counter()
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=merged_env,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError as exc:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            raise TimeoutError(f"Превышено время выполнения команды ({timeout} с) на узле '{self.host_id}'") from exc

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return RawExecutionResult(
            exit_code=int(proc.returncode or 0),
            stdout=stdout_bytes.decode("utf-8", errors="replace").strip(),
            stderr=stderr_bytes.decode("utf-8", errors="replace").strip(),
            duration_ms=elapsed_ms,
        )
