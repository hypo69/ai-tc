# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Конфигурация системы SSH MCP Server
# =============================================================================
# Description:
#   Загрузка, валидация и предоставление параметров настройки для гибридного
#   сервера удалённого администрирования SSH MCP Server.
#
#   Зачем нужен этот модуль:
#     1. Централизованное управление конфигурацией (Configuration Over Hardcode)
#        из YAML-файлов и переменных окружения.
#     2. Строгая типизация настроек подключения, ограничений параллелизма,
#        политик безопасности и хранилища SQLite.
#
#   Режимы работы:
#     - 'local': локальный MCP-сервер (STDIO) с пулом SSH-соединений.
#     - 'remote': удалённый MCP-агент (Streamable HTTP + TLS).
#     - 'hybrid': совмещённый режим координатора и локального/удалённого узла.
#
# Usage Examples:
#   Python API:
#     from ssh_mcp.config import load_settings
#     settings = load_settings("./ssh_mcp/config/settings.yaml")
#     logger.console(settings.server.mode)
#
# File: config.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:35:00
# =============================================================================

from pathlib import Path
from typing import Any, Dict, Literal, Optional
import os

from pydantic import BaseModel, Field
import yaml


class ApplicationSettings(BaseModel):
    """Параметры метаданных приложения.

    Attributes:
        name (str): Название сервиса.
        version (str): Версия релиза.
    """

    name: str = Field(default="SSH MCP Server")
    version: str = Field(default="1.0.0")


class LocalTransportSettings(BaseModel):
    """Настройки локального транспорта MCP.

    Attributes:
        transport (Literal['stdio']): Тип локального транспорта.
    """

    transport: Literal["stdio"] = Field(default="stdio")


class RemoteTransportSettings(BaseModel):
    """Настройки удалённого транспорта MCP.

    Attributes:
        transport (Literal['streamable-http']): Протокол удалённого транспорта.
        host (str): Сетевой интерфейс привязки (по умолчанию 127.0.0.1).
        port (int): Сетевой порт HTTP/TLS сервера.
        tls (bool): Признак обязательного использования TLS.
        cert_file (str): Путь к сертификату TLS.
        key_file (str): Путь к приватному ключу TLS.
        allowed_origins (list[str]): Разрешённые заголовки Origin.
    """

    transport: Literal["streamable-http"] = Field(default="streamable-http")
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8765)
    tls: bool = Field(default=True)
    cert_file: str = Field(default="")
    key_file: str = Field(default="")
    allowed_origins: list[str] = Field(default_factory=lambda: ["http://127.0.0.1", "https://127.0.0.1"])


class ServerSettings(BaseModel):
    """Конфигурация режимов работы MCP-сервера.

    Attributes:
        mode (Literal['local', 'remote', 'hybrid']): Рабочий режим сервера.
        local (LocalTransportSettings): Конфигурация STDIO.
        remote (RemoteTransportSettings): Конфигурация Streamable HTTP.
    """

    mode: Literal["local", "remote", "hybrid"] = Field(default="hybrid")
    local: LocalTransportSettings = Field(default_factory=LocalTransportSettings)
    remote: RemoteTransportSettings = Field(default_factory=RemoteTransportSettings)


class SSHSettings(BaseModel):
    """Параметры протокола SSH и пула подключений.

    Attributes:
        default_port (int): Стандартный порт SSH.
        connect_timeout (int): Таймаут установки соединения в секундах.
        command_timeout (int): Таймаут выполнения команды в секундах.
        keepalive_interval (int): Интервал отправки пакетов keepalive в секундах.
        max_reconnect_attempts (int): Максимальное число попыток переподключения.
        host_key_verification (Literal['strict', 'warn']): Режим проверки ключей хостов.
        known_hosts_path (str): Путь к файлу доверенных отпечатков known_hosts.
    """

    default_port: int = Field(default=22)
    connect_timeout: int = Field(default=15)
    command_timeout: int = Field(default=60)
    keepalive_interval: int = Field(default=30)
    max_reconnect_attempts: int = Field(default=3)
    host_key_verification: Literal["strict", "warn"] = Field(default="strict")
    known_hosts_path: str = Field(default="./data/known_hosts")


class ExecutionSettings(BaseModel):
    """Ограничения вычислительного движка и передаваемых данных.

    Attributes:
        max_parallel_commands (int): Лимит одновременных команд.
        max_output_size_mb (int): Максимальный размер текстового вывода в МБ.
        max_execution_time (int): Предельное время выполнения задачи в секундах.
        max_file_transfer_mb (int): Лимит размера передаваемого по SFTP файла в МБ.
        allowed_paths (list[str]): Разрешённые базовые каталоги для файловых операций.
    """

    max_parallel_commands: int = Field(default=10)
    max_output_size_mb: int = Field(default=10)
    max_execution_time: int = Field(default=3600)
    max_file_transfer_mb: int = Field(default=100)
    allowed_paths: list[str] = Field(default_factory=list)


class SecuritySettings(BaseModel):
    """Параметры безопасности, привилегий и подтверждений.

    Attributes:
        default_privilege (Literal['standard', 'administrator']): Уровень привилегий.
        audit_enabled (bool): Включение журналирования всех операций.
        approval_required_for_high_risk (bool): Требовать подтверждение для high-risk.
        approval_required_for_critical (bool): Требовать подтверждение для critical.
        api_token_env (str): Имя переменной окружения с токеном для Remote MCP.
    """

    default_privilege: Literal["standard", "administrator"] = Field(default="administrator")
    audit_enabled: bool = Field(default=True)
    approval_required_for_high_risk: bool = Field(default=True)
    approval_required_for_critical: bool = Field(default=True)
    api_token_env: str = Field(default="SSH_MCP_API_TOKEN")


class StorageSettings(BaseModel):
    """Конфигурация хранилища данных.

    Attributes:
        backend (Literal['sqlite', 'postgresql', 'mariadb']): Тип СУБД.
        path (str): Путь к файлу SQLite или строка подключения.
    """

    backend: Literal["sqlite", "postgresql", "mariadb"] = Field(default="sqlite")
    path: str = Field(default="./data/ssh_mcp.db")


class LoggingSettings(BaseModel):
    """Параметры логирования и аудита.

    Attributes:
        level (str): Уровень детализации логов.
        audit (bool): Признак ведения отдельного аудиторского следа.
    """

    level: str = Field(default="INFO")
    audit: bool = Field(default=True)


class AppSettings(BaseModel):
    """Корневая модель конфигурации SSH MCP Server.

    Attributes:
        application (ApplicationSettings): Метаданные приложения.
        server (ServerSettings): Параметры режимов и транспортов.
        ssh (SSHSettings): Настройки SSH.
        execution (ExecutionSettings): Квоты и лимиты выполнения.
        security (SecuritySettings): Политики безопасности и подтверждений.
        storage (StorageSettings): Настройки базы данных.
        logging (LoggingSettings): Параметры логирования.

    Examples:
        >>> settings = AppSettings()
        >>> settings.server.mode
        'hybrid'
    """

    application: ApplicationSettings = Field(default_factory=ApplicationSettings)
    server: ServerSettings = Field(default_factory=ServerSettings)
    ssh: SSHSettings = Field(default_factory=SSHSettings)
    execution: ExecutionSettings = Field(default_factory=ExecutionSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)


def load_settings(config_path: Optional[str] = "") -> AppSettings:
    """Загрузка конфигурации из YAML-файла с поддержкой переменных окружения.

    Args:
        config_path (Optional[str]): Путь к файлу settings.yaml.
                                     Значение по умолчанию: ''.

    Returns:
        AppSettings: Валидированный объект конфигурации.

    Exceptions:
        ValueError: Если содержимое YAML-файла имеет некорректный формат.

    Examples:
        >>> cfg = load_settings()
        >>> cfg.ssh.default_port
        22
    """
    resolved_path = config_path or os.environ.get("SSH_MCP_CONFIG", "")
    if not resolved_path:
        default_candidate = Path(__file__).parent / "config" / "settings.yaml"
        if default_candidate.exists():
            resolved_path = str(default_candidate)

    raw_data: Dict[str, Any] = {}
    if resolved_path and Path(resolved_path).exists():
        content = Path(resolved_path).read_text(encoding="utf-8")
        loaded = yaml.safe_load(content)
        if isinstance(loaded, dict):
            raw_data = loaded

    settings = AppSettings.model_validate(raw_data)

    env_db_path = os.environ.get("SSH_MCP_DB_PATH", "")
    if env_db_path:
        settings.storage.path = env_db_path

    env_mode = os.environ.get("SSH_MCP_MODE", "")
    if env_mode in ("local", "remote", "hybrid"):
        settings.server.mode = env_mode  # type: ignore[assignment]

    return settings
