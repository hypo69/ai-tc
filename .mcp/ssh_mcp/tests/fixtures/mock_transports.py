# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Тестовые фикстуры и эмуляторы транспортов SSH MCP Server
# =============================================================================
# Description:
#   Предоставление контролируемых эмуляторов SSH-транспорта для тестирования
#   Windows и Linux адаптеров, обрыва связи, таймаутов, неверных ключей и
#   подмены сервера (MITM).
#
# File: mock_transports.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.tests.fixtures
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 17:07:00
# =============================================================================

import asyncio
from typing import Dict, List, Optional
from ...schemas.host import HostConfig
from ...security.host_verification import HostKeyVerifier
from ...transports.base import BaseTransport, RawExecutionResult


class FakeTransport(BaseTransport):
    """Управляемый тестовый транспорт для эмуляции Windows и Linux SSH-узлов.

    Attributes:
        host_config (HostConfig): Конфигурация узла.
        verifier (HostKeyVerifier): Верификатор ключей хостов.
        presented_fingerprint (str): Предъявляемый сервером отпечаток ключа.
        fail_connect_times (int): Сколько раз подряд выбрасывать ошибку при connect().
        drop_once_on_execute (bool): Сбросить ли соединение при первом вызове execute_command().
        simulate_timeout (bool): Эмулировать ли истечение таймаута команды.

    Examples:
        >>> pass
    """

    def __init__(
        self,
        host_config: HostConfig,
        verifier: HostKeyVerifier,
        presented_fingerprint: str = "SHA256:trusted-default-fp",
        fail_connect_times: int = 0,
        drop_once_on_execute: bool = False,
        simulate_timeout: bool = False,
        auth_valid: bool = True,
    ) -> None:
        """Инициализация тестового транспорта."""
        super().__init__(host_id=host_config.host_id)
        self.host_config = host_config
        self.verifier = verifier
        self.presented_fingerprint = presented_fingerprint
        self.fail_connect_times = fail_connect_times
        self.drop_once_on_execute = drop_once_on_execute
        self.simulate_timeout = simulate_timeout
        self.auth_valid = auth_valid

    async def connect(self) -> bool:
        """Эмуляция подключения с проверкой SSH-ключей и отпечатка сервера."""
        if not self.auth_valid:
            self.connected = False
            raise ConnectionError("Permission denied (publickey,password): неверный SSH-ключ")

        if self.fail_connect_times > 0:
            self.fail_connect_times -= 1
            self.connected = False
            raise ConnectionError("Симуляция временного сбоя сети при подключении")

        self.verifier.verify_fingerprint(
            host_id=self.host_id,
            hostname=self.host_config.address,
            port=self.host_config.port,
            key_type="ssh-ed25519",
            presented_fingerprint=self.presented_fingerprint,
        )
        self.connected = True
        return True

    async def disconnect(self) -> bool:
        """Отключение тестового транспорта."""
        self.connected = False
        return True

    async def is_alive(self) -> bool:
        """Проверка состояния тестового транспорта."""
        return self.connected

    async def get_fingerprint(self) -> str:
        """Возврат отпечатка сервера."""
        return self.presented_fingerprint

    async def execute_command(
        self,
        command: str,
        args: Optional[List[str]] = [],
        env: Optional[Dict[str, str]] = {},
        shell: str = "default",
        timeout: int = 60,
        elevate: bool = False,
    ) -> RawExecutionResult:
        """Эмуляция выполнения команд для Windows (PowerShell) и Linux (Bash)."""
        if self.drop_once_on_execute:
            self.drop_once_on_execute = False
            self.connected = False
            raise ConnectionError("Потеря соединения во время выполнения команды")

        if self.simulate_timeout:
            await asyncio.sleep(0.05)
            raise TimeoutError(f"Истекло время выполнения команды ({timeout} с)")

        if "sleep" in command:
            await asyncio.sleep(5.0)

        if self.host_config.platform == "linux":
            if "/proc/meminfo" in command:
                return RawExecutionResult(
                    exit_code=0,
                    stdout="MemTotal:       16777216 kB\nMemFree:         4194304 kB\nMemAvailable:    8388608 kB",
                    stderr="",
                    duration_ms=12,
                )
            if "nproc" in command:
                return RawExecutionResult(exit_code=0, stdout="8", stderr="", duration_ms=5)
            if "hostname && uname" in command:
                return RawExecutionResult(
                    exit_code=0,
                    stdout=f"{self.host_config.hostname}\nLinux 6.8.0-generic\nx86_64",
                    stderr="",
                    duration_ms=8,
                )
            if "df -PT" in command:
                return RawExecutionResult(
                    exit_code=0,
                    stdout="Filesystem Type 1048576-blocks Used Available Capacity Mounted on\n/dev/sda1 ext4 100000M 40000M 60000M 40% /",
                    stderr="",
                    duration_ms=9,
                )
            if "systemctl" in command or "service" in command:
                return RawExecutionResult(
                    exit_code=0,
                    stdout="sshd.service loaded active running OpenSSH Daemon",
                    stderr="",
                    duration_ms=14,
                )
            return RawExecutionResult(
                exit_code=0,
                stdout=f"linux-exec:{command}",
                stderr="",
                duration_ms=10,
            )

        # Эмуляция ответов PowerShell JSON для Windows SSH-узла
        if "Win32_OperatingSystem" in command and "TotalVisibleMemorySize" in command:
            return RawExecutionResult(
                exit_code=0,
                stdout='{"total_mb":32768,"used_mb":16384,"available_mb":16384}',
                stderr="",
                duration_ms=18,
            )
        if "Win32_OperatingSystem" in command:
            return RawExecutionResult(
                exit_code=0,
                stdout='{"hostname":"win-srv-01","os_name":"Microsoft Windows Server 2025","version":"10.0.26100","architecture":"64-bit"}',
                stderr="",
                duration_ms=15,
            )
        if "Restart-Service" in command or "Stop-Service" in command or "Start-Service" in command:
            return RawExecutionResult(
                exit_code=0,
                stdout='{"service_name":"Spooler","status":"Running"}',
                stderr="",
                duration_ms=25,
            )
        return RawExecutionResult(
            exit_code=0,
            stdout='{"status":"ok","shell":"powershell"}',
            stderr="",
            duration_ms=11,
        )
