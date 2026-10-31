# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Менеджер пула подключений (Connection Manager)
# =============================================================================
# Description:
#   Управление пулом одновременных подключений к узлам Windows и Linux,
#   автоматическое переподключение с ограничением числа попыток
#   (`max_reconnect_attempts`), проверка доступности и получение отпечатков
#   SSH-ключей (Раздел 4.1 ТЗ).
#
#   Зачем нужен этот модуль:
#     1. Переиспользование открытых сессий в Connection Pool без повторного
#        рукопожатия SSH на каждую команду.
#     2. Автоматическое восстановление разорванных соединений (Recovery).
#
# Usage Examples:
#   Python API:
#     from ssh_mcp.core.connection_manager import ConnectionManager
#     conn_mgr = ConnectionManager(hosts_repo, connections_repo, cred_mgr, verifier)
#
# File: connection_manager.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:50:00
# =============================================================================

from datetime import datetime, timezone
import socket
import sys
from typing import Callable, Dict, List, Optional
import uuid

from ..schemas.host import ConnectionInfo, HostConfig
from ..security.credentials import CredentialManager
from ..security.host_verification import HostKeyVerifier
from ..storage.repositories.connections_repo import ConnectionsRepository
from ..storage.repositories.hosts_repo import HostsRepository
from ..transports.base import BaseTransport
from ..transports.local_transport import LocalTransport
from ..transports.remote_mcp_transport import RemoteMCPTransport
from ..transports.ssh_transport import AsyncSSHTransport


class ConnectionManager:
    """Менеджер пула подключений (Connection Pool) для удалённых и локальных узлов.

    Attributes:
        hosts_repo (HostsRepository): Репозиторий инвентаризации узлов.
        connections_repo (ConnectionsRepository): Репозиторий истории подключений.
        credential_manager (CredentialManager): Сервис разрешения секретов.
        host_verifier (HostKeyVerifier): Верификатор SSH-отпечатков.
        max_reconnect_attempts (int): Лимит попыток автоматического переподключения.

    Examples:
        >>> from ssh_mcp.storage.database import DatabaseManager
        >>> from ssh_mcp.storage.repositories import HostsRepository, ConnectionsRepository, HostCredentialsRepository, HostKeysRepository
        >>> db = DatabaseManager(":memory:")
        >>> _ = db.initialize()
        >>> cm = ConnectionManager(
        ...     HostsRepository(db),
        ...     ConnectionsRepository(db),
        ...     CredentialManager(HostCredentialsRepository(db)),
        ...     HostKeyVerifier(HostKeysRepository(db))
        ... )
        >>> cm.list_active_connections()
        []
    """

    def __init__(
        self,
        hosts_repo: HostsRepository,
        connections_repo: ConnectionsRepository,
        credential_manager: CredentialManager,
        host_verifier: HostKeyVerifier,
        connect_timeout: int = 15,
        keepalive_interval: int = 30,
        max_reconnect_attempts: int = 3,
        transport_factory: Optional[Callable[[HostConfig], BaseTransport]] = False,  # type: ignore[assignment]
    ) -> None:
        """Инициализация менеджера подключений.

        Args:
            hosts_repo (HostsRepository): Репозиторий таблицы `hosts`.
            connections_repo (ConnectionsRepository): Репозиторий таблицы `connections`.
            credential_manager (CredentialManager): Менеджер секретов.
            host_verifier (HostKeyVerifier): Верификатор ключей хостов.
            connect_timeout (int): Таймаут подключения в секундах.
            keepalive_interval (int): Интервал keepalive в секундах.
            max_reconnect_attempts (int): Максимальное количество попыток переподключения.
            transport_factory (Optional[Callable[[HostConfig], BaseTransport]]): Кастомная фабрика транспортов.

        Examples:
            >>> pass
        """
        self.hosts_repo = hosts_repo
        self.connections_repo = connections_repo
        self.credential_manager = credential_manager
        self.host_verifier = host_verifier
        self.connect_timeout = connect_timeout
        self.keepalive_interval = keepalive_interval
        self.max_reconnect_attempts = max_reconnect_attempts
        self._transport_factory = transport_factory
        self._pool: Dict[str, BaseTransport] = {}
        self._meta: Dict[str, ConnectionInfo] = {}

    def register_host(self, config: HostConfig) -> bool:
        """Регистрация или обновление конфигурации узла в реестре хостов.

        Args:
            config (HostConfig): Модель конфигурации хоста.

        Returns:
            bool: True при успешной записи.

        Examples:
            >>> pass
        """
        return self.hosts_repo.upsert_host(config)

    def get_host_config(self, host_id: str) -> HostConfig:
        """Получение конфигурации узла (с автоматическим созданием локального профиля для 'localhost').

        Args:
            host_id (str): Идентификатор узла.

        Returns:
            HostConfig: Валидированная конфигурация узла.

        Exceptions:
            KeyError: Если узел не найден или отключён.

        Examples:
            >>> pass
        """
        raw = self.hosts_repo.get_host(host_id)
        if not raw and host_id in ("localhost", "local-win-admin", "127.0.0.1"):
            local_platform = "windows" if sys.platform.startswith("win") else "linux"
            default_local = HostConfig(
                host_id=host_id,
                hostname=socket.gethostname(),
                address="127.0.0.1",
                port=22,
                platform=local_platform,  # type: ignore[arg-type]
                username="local-admin",
                auth_method="agent",
                transport_type="local",
                enabled=True,
            )
            self.hosts_repo.upsert_host(default_local)
            return default_local

        if not raw:
            raise KeyError(f"Узел '{host_id}' не зарегистрирован в каталоге серверов")

        cfg = HostConfig.model_validate(raw)
        if not cfg.enabled:
            raise PermissionError(f"Узел '{host_id}' отключён в конфигурации")
        return cfg

    def _create_transport(self, cfg: HostConfig) -> BaseTransport:
        """Создание экземпляра транспорта в соответствии с конфигурацией узла.

        Args:
            cfg (HostConfig): Конфигурация узла.

        Returns:
            BaseTransport: Экземпляр транспорта (Local, RemoteMCP или AsyncSSH).

        Examples:
            >>> pass
        """
        if self._transport_factory:
            return self._transport_factory(cfg)

        if cfg.transport_type == "local":
            return LocalTransport(host_id=cfg.host_id, platform_name=cfg.platform)

        if cfg.transport_type == "remote_mcp":
            token = self.credential_manager.resolve_secret(cfg.credential_ref)
            return RemoteMCPTransport(
                host_id=cfg.host_id,
                endpoint_url=cfg.remote_mcp_url,
                api_token=token,
            )

        return AsyncSSHTransport(
            host_config=cfg,
            credential_manager=self.credential_manager,
            host_verifier=self.host_verifier,
            connect_timeout=self.connect_timeout,
            keepalive_interval=self.keepalive_interval,
        )

    async def connect(self, host_id: str) -> ConnectionInfo:
        """Установка соединения с узлом и добавление его в пул активных подключений.

        Args:
            host_id (str): Идентификатор узла.

        Returns:
            ConnectionInfo: Метаданные установленного подключения.

        Examples:
            >>> pass
        """
        cfg = self.get_host_config(host_id)
        if host_id in self._pool and await self._pool[host_id].is_alive():
            info = self._meta[host_id]
            info.last_activity_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            self.connections_repo.save_connection(info)
            return info

        transport = self._create_transport(cfg)
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        conn_id = self._meta[host_id].connection_id if host_id in self._meta else f"conn-{uuid.uuid4().hex[:10]}"

        try:
            await transport.connect()
            fp = await transport.get_fingerprint()
            info = ConnectionInfo(
                connection_id=conn_id,
                host_id=host_id,
                status="connected",
                connected_at=now_utc,
                last_activity_at=now_utc,
                fingerprint=fp,
                reconnect_attempts=0,
                last_error="",
            )
            self._pool[host_id] = transport
            self._meta[host_id] = info
            self.connections_repo.save_connection(info)
            return info
        except Exception as exc:
            err_info = ConnectionInfo(
                connection_id=conn_id,
                host_id=host_id,
                status="error",
                connected_at="",
                last_activity_at=now_utc,
                fingerprint="",
                reconnect_attempts=self._meta[host_id].reconnect_attempts if host_id in self._meta else 0,
                last_error=str(exc),
            )
            self._meta[host_id] = err_info
            self.connections_repo.save_connection(err_info)
            raise

    async def disconnect(self, host_id: str) -> ConnectionInfo:
        """Закрытие соединения с узлом и удаление из активного пула.

        Args:
            host_id (str): Идентификатор узла.

        Returns:
            ConnectionInfo: Обновлённые сведения о подключении.

        Examples:
            >>> pass
        """
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if host_id in self._pool:
            await self._pool[host_id].disconnect()
            del self._pool[host_id]

        if host_id in self._meta:
            info = self._meta[host_id]
            info.status = "disconnected"
            info.last_activity_at = now_utc
        else:
            info = ConnectionInfo(
                connection_id=f"conn-{uuid.uuid4().hex[:10]}",
                host_id=host_id,
                status="disconnected",
                last_activity_at=now_utc,
            )
            self._meta[host_id] = info

        self.connections_repo.save_connection(info)
        return info

    async def reconnect(self, host_id: str) -> ConnectionInfo:
        """Переподключение к узлу с контролем лимита попыток `max_reconnect_attempts`.

        Args:
            host_id (str): Идентификатор узла.

        Returns:
            ConnectionInfo: Сведения о восстановленном подключении.

        Exceptions:
            ConnectionError: Если исчерпан лимит попыток переподключения.

        Examples:
            >>> pass
        """
        await self.disconnect(host_id)
        last_exc: Optional[Exception] = False  # type: ignore[assignment]

        for attempt in range(1, self.max_reconnect_attempts + 1):
            try:
                info = await self.connect(host_id)
                info.reconnect_attempts = attempt
                self.connections_repo.save_connection(info)
                return info
            except Exception as exc:
                last_exc = exc
                if host_id in self._meta:
                    self._meta[host_id].reconnect_attempts = attempt
                    self._meta[host_id].status = "reconnecting"
                    self.connections_repo.save_connection(self._meta[host_id])

        if host_id in self._meta:
            self._meta[host_id].status = "error"
            self.connections_repo.save_connection(self._meta[host_id])

        raise ConnectionError(
            f"Не удалось переподключиться к '{host_id}' после {self.max_reconnect_attempts} попыток: {last_exc}"
        )

    async def get_transport(self, host_id: str) -> BaseTransport:
        """Получение живого транспорта из пула (с автоматическим подключением/переподключением).

        Args:
            host_id (str): Идентификатор узла.

        Returns:
            BaseTransport: Активный транспорт узла.

        Examples:
            >>> pass
        """
        if host_id not in self._pool:
            await self.connect(host_id)
            return self._pool[host_id]

        transport = self._pool[host_id]
        if not await transport.is_alive():
            await self.reconnect(host_id)
            return self._pool[host_id]

        return transport

    async def get_status(self, host_id: str) -> ConnectionInfo:
        """Проверка текущего состояния подключения к узлу.

        Args:
            host_id (str): Идентификатор узла.

        Returns:
            ConnectionInfo: Актуальный статус подключения.

        Examples:
            >>> pass
        """
        if host_id in self._pool:
            alive = await self._pool[host_id].is_alive()
            info = self._meta[host_id]
            info.status = "connected" if alive else "disconnected"
            return info

        if host_id in self._meta:
            return self._meta[host_id]

        return ConnectionInfo(
            connection_id="",
            host_id=host_id,
            status="disconnected",
        )

    def list_active_connections(self) -> List[Dict[str, object]]:
        """Получение списка всех подключений в пуле.

        Returns:
            List[Dict[str, object]]: Список словарей ConnectionInfo.

        Examples:
            >>> pass
        """
        return [info.model_dump() for info in self._meta.values()]
