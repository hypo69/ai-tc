# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Асинхронный SSH-транспорт на базе AsyncSSH (SSH Transport)
# =============================================================================
# Description:
#   Установка и обслуживание защищённых SSH-соединений с удалёнными серверами
#   Windows и Linux с использованием библиотеки AsyncSSH, проверкой host key
#   через HostKeyVerifier и поддержкой ключей, SSH Agent и паролей.
#
#   Зачем нужен этот модуль:
#     1. Надёжный неблокирующий SSH-транспорт (Разделы 4.1, 6, 10 ТЗ).
#     2. Обязательная проверка отпечатка публичного ключа сервера до выполнения
#        любых команд.
#
# Usage Examples:
#   Python API:
#     from ssh_mcp.transports.ssh_transport import AsyncSSHTransport
#     tr = AsyncSSHTransport(host_config, credential_manager, host_verifier)
#     await tr.connect()
#
# File: ssh_transport.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.transports
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:46:30
# =============================================================================

import asyncio
import shlex
import time
from typing import Any, Dict, List, Optional
import asyncssh

from ..schemas.host import HostConfig
from ..security.credentials import CredentialManager
from ..security.host_verification import HostKeyVerifier
from .base import BaseTransport, RawExecutionResult
from .local_transport import build_safe_shell_invocation


class AsyncSSHTransport(BaseTransport):
    """Транспорт удалённого управления по протоколу SSH на базе AsyncSSH.

    Attributes:
        host_config (HostConfig): Конфигурация удалённого узла.
        credential_manager (CredentialManager): Менеджер разрешения секретов.
        host_verifier (HostKeyVerifier): Верификатор SSH-отпечатков.
        connect_timeout (int): Таймаут подключения в секундах.
        keepalive_interval (int): Интервал keepalive в секундах.

    Examples:
        >>> from ssh_mcp.schemas.host import HostConfig
        >>> cfg = HostConfig(host_id="srv1", hostname="srv1", address="10.0.0.1", platform="linux", username="admin")
    """

    def __init__(
        self,
        host_config: HostConfig,
        credential_manager: CredentialManager,
        host_verifier: HostKeyVerifier,
        connect_timeout: int = 15,
        keepalive_interval: int = 30,
    ) -> None:
        """Инициализация экземпляра SSH-транспорта.

        Args:
            host_config (HostConfig): Параметры подключения к узлу.
            credential_manager (CredentialManager): Сервис получения ключей/паролей.
            host_verifier (HostKeyVerifier): Сервис проверки known_hosts / host_keys.
            connect_timeout (int): Таймаут установки соединения в секундах.
            keepalive_interval (int): Интервал пакетов keepalive в секундах.

        Examples:
            >>> pass
        """
        super().__init__(host_id=host_config.host_id)
        self.host_config = host_config
        self.credential_manager = credential_manager
        self.host_verifier = host_verifier
        self.connect_timeout = connect_timeout
        self.keepalive_interval = keepalive_interval
        self._conn: Any = False
        self._fingerprint: str = ""

    async def connect(self) -> bool:
        """Установка SSH-соединения с проверкой публичного ключа сервера.

        Returns:
            bool: True при успешном подключении и верификации ключа.

        Exceptions:
            HostVerificationError: Если отпечаток сервера неизвестен или подменён.
            ConnectionError: При ошибке аутентификации или недоступности сети.

        Examples:
            >>> pass
        """
        connect_kwargs: Dict[str, Any] = {
            "host": self.host_config.address,
            "port": self.host_config.port,
            "username": self.host_config.username,
            "known_hosts": None,
            "keepalive_interval": self.keepalive_interval,
        }

        secret = self.credential_manager.resolve_secret(self.host_config.credential_ref)
        if self.host_config.auth_method == "key":
            if not secret:
                raise ConnectionError(
                    f"Не найден SSH-ключ по ссылке '{self.host_config.credential_ref}' для узла '{self.host_id}'"
                )
            connect_kwargs["client_keys"] = [secret]
        elif self.host_config.auth_method == "password":
            if not secret:
                raise ConnectionError(
                    f"Не найден пароль по ссылке '{self.host_config.credential_ref}' для узла '{self.host_id}'"
                )
            connect_kwargs["password"] = secret

        try:
            conn = await asyncio.wait_for(
                asyncssh.connect(**connect_kwargs),
                timeout=self.connect_timeout,
            )
        except Exception as exc:
            self.connected = False
            raise ConnectionError(f"Ошибка подключения SSH к '{self.host_id}': {exc}") from exc

        server_key = conn.get_server_host_key()
        if not server_key:
            conn.close()
            raise ConnectionError(f"Сервер '{self.host_id}' не вернул публичный ключ")

        raw_key = server_key.encode_ssh_public()
        key_type = server_key.get_algorithm()
        fp = self.host_verifier.compute_sha256_fingerprint(raw_key)

        try:
            self.host_verifier.verify_fingerprint(
                host_id=self.host_id,
                hostname=self.host_config.address,
                port=self.host_config.port,
                key_type=key_type,
                presented_fingerprint=fp,
            )
        except Exception:
            conn.close()
            self.connected = False
            raise

        self._conn = conn
        self._fingerprint = fp
        self.connected = True
        return True

    async def disconnect(self) -> bool:
        """Закрытие активного SSH-соединения.

        Returns:
            bool: True после закрытия соединения.

        Examples:
            >>> pass
        """
        if self._conn:
            self._conn.close()
            await self._conn.wait_closed()
            self._conn = False
        self.connected = False
        return True

    async def is_alive(self) -> bool:
        """Проверка активности SSH-соединения.

        Returns:
            bool: True, если соединение открыто.

        Examples:
            >>> pass
        """
        if not self.connected or not self._conn:
            return False
        is_closing = getattr(self._conn, "is_closing", lambda: False)
        if callable(is_closing) and is_closing():
            self.connected = False
            return False
        return True

    async def get_fingerprint(self) -> str:
        """Получение SHA-256 отпечатка ключа подключённого SSH-сервера.

        Returns:
            str: Строка отпечатка `SHA256:...`.

        Examples:
            >>> pass
        """
        return self._fingerprint

    def get_raw_connection(self) -> Any:
        """Предоставление базового объекта соединения AsyncSSH для SFTP-клиента.

        Returns:
            Any: Активный объект соединения AsyncSSH или False.

        Examples:
            >>> pass
        """
        return self._conn

    async def execute_command(
        self,
        command: str,
        args: Optional[List[str]] = [],
        env: Optional[Dict[str, str]] = {},
        shell: str = "default",
        timeout: int = 60,
        elevate: bool = False,
    ) -> RawExecutionResult:
        """Выполнение команды через SSH-канал с контролем времени выполнения.

        Args:
            command (str): Исполняемая команда.
            args (Optional[List[str]]): Отдельные позиционные аргументы.
                                        Значение по умолчанию: [].
            env (Optional[Dict[str, str]]): Переменные окружения.
                                            Значение по умолчанию: {}.
            shell (str): Оболочка ('powershell', 'pwsh', 'cmd', 'bash', 'sh', 'default').
            timeout (int): Таймаут выполнения в секундах.
            elevate (bool): Флаг повышения привилегий.

        Returns:
            RawExecutionResult: Результат выполнения команды.

        Exceptions:
            ConnectionError: Если соединение не установлено или разорвано во время команды.
            TimeoutError: При превышении `timeout` секунд.

        Examples:
            >>> pass
        """
        if not await self.is_alive():
            raise ConnectionError(f"SSH-соединение с узлом '{self.host_id}' не активно")

        argv = build_safe_shell_invocation(
            command=command,
            args=args if args else [],
            shell=shell,
            platform_name=self.host_config.platform,
            elevate=elevate,
        )

        if self.host_config.platform == "windows":
            cmd_line = " ".join(
                f'"{part}"' if " " in part and not part.startswith('"') else part for part in argv
            )
        else:
            cmd_line = " ".join(shlex.quote(part) for part in argv)

        started = time.perf_counter()
        try:
            proc_res = await asyncio.wait_for(
                self._conn.run(cmd_line, env=env if env else {}, check=False),
                timeout=timeout,
            )
        except asyncio.TimeoutError as exc:
            raise TimeoutError(
                f"Истекло время ожидания команды ({timeout} с) на SSH-узле '{self.host_id}'"
            ) from exc
        except Exception as exc:
            self.connected = False
            raise ConnectionError(f"Потеря соединения во время выполнения команды на '{self.host_id}': {exc}") from exc

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return RawExecutionResult(
            exit_code=int(proc_res.exit_status or 0),
            stdout=str(proc_res.stdout or "").strip(),
            stderr=str(proc_res.stderr or "").strip(),
            duration_ms=elapsed_ms,
        )
