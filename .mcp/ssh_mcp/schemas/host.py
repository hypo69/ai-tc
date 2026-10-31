# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Схемы конфигурации и состояния удалённых хостов
# =============================================================================
# Description:
#   Определение Pydantic-моделей для инвентаризации удалённых узлов Windows
#   и Linux, параметров аутентификации и активных SSH-соединений.
#
#   Зачем нужен этот модуль:
#     1. Гарантия безопасности секретов: пароли и приватные ключи никогда не
#        хранятся в схеме узла — используется только ссылка credential_ref.
#     2. Единообразное представление метаданных хоста для всех транспортов.
#
# Usage Examples:
#   Python API:
#     from ssh_mcp.schemas.host import HostConfig
#     host = HostConfig(host_id="srv-01", hostname="srv", address="10.0.0.5",
#                       platform="linux", username="admin", auth_method="key")
#
# File: host.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.schemas
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:36:00
# =============================================================================

from typing import Literal
from pydantic import BaseModel, Field


class HostConfig(BaseModel):
    """Конфигурация удалённого узла.

    Attributes:
        host_id (str): Уникальный идентификатор хоста в реестре.
        hostname (str): Сетевое имя узла.
        address (str): IP-адрес или FQDN для подключения.
        port (int): Сетевой порт SSH (по умолчанию 22).
        platform (Literal['windows', 'linux']): Тип операционной системы.
        username (str): Имя учётной записи для входа.
        auth_method (Literal['key', 'agent', 'password']): Способ аутентификации.
        credential_ref (str): Ссылка на секрет в защищённом хранилище (по умолчанию '').
        enabled (bool): Флаг активности узла.
        transport_type (Literal['ssh', 'local', 'remote_mcp']): Предпочитаемый транспорт.
        remote_mcp_url (str): URL удалённого MCP-сервера (если используется remote_mcp).

    Examples:
        >>> cfg = HostConfig(
        ...     host_id="win-01",
        ...     hostname="win-ws-01",
        ...     address="192.168.1.50",
        ...     platform="windows",
        ...     username="admin",
        ...     auth_method="agent"
        ... )
        >>> cfg.port
        22
    """

    host_id: str
    hostname: str
    address: str
    port: int = Field(default=22, ge=1, le=65535)
    platform: Literal["windows", "linux"]
    username: str
    auth_method: Literal["key", "agent", "password"] = Field(default="key")
    credential_ref: str = Field(default="")
    enabled: bool = Field(default=True)
    transport_type: Literal["ssh", "local", "remote_mcp"] = Field(default="ssh")
    remote_mcp_url: str = Field(default="")


class ConnectionInfo(BaseModel):
    """Сведения об активном или историческом подключении к узлу.

    Attributes:
        connection_id (str): Идентификатор сессии подключения.
        host_id (str): Идентификатор целевого узла.
        status (Literal['connected', 'disconnected', 'reconnecting', 'error']): Статус.
        connected_at (str): Время установки соединения в формате UTC ISO-8601.
        last_activity_at (str): Время последней операции в формате UTC ISO-8601.
        fingerprint (str): SHA-256 отпечаток публичного ключа сервера.
        reconnect_attempts (int): Счётчик выполненных попыток переподключения.
        last_error (str): Описание последней ошибки соединения (если есть).

    Examples:
        >>> info = ConnectionInfo(
        ...     connection_id="conn-1",
        ...     host_id="win-01",
        ...     status="connected"
        ... )
        >>> info.status
        'connected'
    """

    connection_id: str
    host_id: str
    status: Literal["connected", "disconnected", "reconnecting", "error"] = Field(default="disconnected")
    connected_at: str = Field(default="")
    last_activity_at: str = Field(default="")
    fingerprint: str = Field(default="")
    reconnect_attempts: int = Field(default=0)
    last_error: str = Field(default="")
