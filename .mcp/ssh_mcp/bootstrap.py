# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Контейнер инициализации зависимостей (Bootstrap Container)
# =============================================================================
# Description:
#   Явное внедрение зависимостей (Explicit DI) без скрытого глобального
#   состояния. Связывает конфигурацию, SQLite-репозитории, менеджер секретов,
#   верификатор ключей, реестр команд и центральный конвейер ExecutionEngine.
#
#   Зачем нужен этот модуль:
#     1. Соблюдение инженерного стандарта Explicit DI (Раздел 2.3 ENGINEERING.md).
#     2. Обеспечение разделения на `ssh-mcp-core`, `ssh-mcp-server` и
#        `ssh-mcp-agent` (Раздел 17 ТЗ).
#
# Usage Examples:
#   Python API:
#     from ssh_mcp.bootstrap import create_runtime
#     runtime = create_runtime()
#
# File: bootstrap.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:57:00
# =============================================================================

from pathlib import Path
from typing import Callable, Optional
import yaml

from .config import AppSettings, load_settings
from .core.approval_manager import ApprovalManager
from .core.command_registry import CommandRegistry
from .core.connection_manager import ConnectionManager
from .core.execution_engine import ExecutionEngine
from .core.permission_manager import PermissionManager
from .core.result_normalizer import ResultNormalizer
from .core.task_manager import TaskManager
from .schemas.host import HostConfig
from .security.audit import AuditLogger
from .security.credentials import CredentialManager
from .security.host_verification import HostKeyVerifier
from .security.secret_redactor import SecretRedactor
from .storage.database import DatabaseManager
from .storage.repositories import (
    ApprovalsRepository,
    AuditLogRepository,
    CommandRunsRepository,
    CommandsRepository,
    ConnectionsRepository,
    DiagnosticsRepository,
    FileTransfersRepository,
    HostCredentialsRepository,
    HostKeysRepository,
    HostsRepository,
    PermissionsRepository,
    TasksRepository,
)
from .transports.base import BaseTransport
from .transports.sftp_transport import SFTPFileManager


class SSHMCPRuntime:
    """Единый контейнер сервисов `ssh-mcp-core` с явным внедрением зависимостей.

    Attributes:
        settings (AppSettings): Конфигурация приложения.
        db (DatabaseManager): Менеджер базы данных.
        redactor (SecretRedactor): Сервис очистки секретов.
        normalizer (ResultNormalizer): Формирователь стандартного ответа MCP.
        credential_manager (CredentialManager): Менеджер секретов.
        host_verifier (HostKeyVerifier): Верификатор ключей хостов.
        audit_logger (AuditLogger): Служба журнала аудита.
        registry (CommandRegistry): Реестр команд.
        permission_manager (PermissionManager): Менеджер разрешений.
        approval_manager (ApprovalManager): Менеджер подтверждений.
        connection_manager (ConnectionManager): Менеджер подключений.
        task_manager (TaskManager): Менеджер фоновых задач.
        sftp_manager (SFTPFileManager): Менеджер файловых передач и политик.
        diagnostics_repo (DiagnosticsRepository): Репозиторий диагностических отчётов.
        engine (ExecutionEngine): Центральный конвейер выполнения команд.

    Examples:
        >>> rt = create_runtime(db_path=":memory:")
        >>> rt.settings.server.mode
        'hybrid'
    """

    def __init__(
        self,
        settings: AppSettings,
        db: DatabaseManager,
        transport_factory: Optional[Callable[[HostConfig], BaseTransport]] = False,  # type: ignore[assignment]
    ) -> None:
        """Инициализация всех подсистем ядра SSH MCP Server.

        Args:
            settings (AppSettings): Настройки приложения.
            db (DatabaseManager): Инициализированный менеджер БД.
            transport_factory (Optional[Callable]): Фабрика транспортов (для тестов/кастомизации).

        Examples:
            >>> pass
        """
        self.settings = settings
        self.db = db

        # Репозитории 12 таблиц
        self.hosts_repo = HostsRepository(db)
        self.creds_repo = HostCredentialsRepository(db)
        self.host_keys_repo = HostKeysRepository(db)
        self.connections_repo = ConnectionsRepository(db)
        self.commands_repo = CommandsRepository(db)
        self.runs_repo = CommandRunsRepository(db)
        self.tasks_repo = TasksRepository(db)
        self.permissions_repo = PermissionsRepository(db)
        self.approvals_repo = ApprovalsRepository(db)
        self.audit_repo = AuditLogRepository(db)
        self.diagnostics_repo = DiagnosticsRepository(db)
        self.transfers_repo = FileTransfersRepository(db)

        # Слой безопасности
        self.redactor = SecretRedactor()
        self.normalizer = ResultNormalizer(
            self.redactor, max_output_size_mb=settings.execution.max_output_size_mb
        )
        self.credential_manager = CredentialManager(self.creds_repo)
        self.host_verifier = HostKeyVerifier(
            self.host_keys_repo,
            mode=settings.ssh.host_key_verification,
            known_hosts_path=settings.ssh.known_hosts_path,
        )
        self.audit_logger = AuditLogger(
            self.audit_repo,
            self.redactor,
            enabled=settings.security.audit_enabled,
        )

        # Слой управления
        self.registry = CommandRegistry(self.commands_repo)
        self.registry.load_builtin_defaults()

        self.permission_manager = PermissionManager(
            self.permissions_repo,
            default_privilege=settings.security.default_privilege,
        )
        self.approval_manager = ApprovalManager(
            self.approvals_repo,
            require_for_high=settings.security.approval_required_for_high_risk,
            require_for_critical=settings.security.approval_required_for_critical,
        )
        self.connection_manager = ConnectionManager(
            hosts_repo=self.hosts_repo,
            connections_repo=self.connections_repo,
            credential_manager=self.credential_manager,
            host_verifier=self.host_verifier,
            connect_timeout=settings.ssh.connect_timeout,
            keepalive_interval=settings.ssh.keepalive_interval,
            max_reconnect_attempts=settings.ssh.max_reconnect_attempts,
            transport_factory=transport_factory,
        )
        self.task_manager = TaskManager(self.tasks_repo)
        self.sftp_manager = SFTPFileManager(
            allowed_roots=settings.execution.allowed_paths,
            max_transfer_mb=settings.execution.max_file_transfer_mb,
            transfers_repo=self.transfers_repo,
        )

        self.engine = ExecutionEngine(
            registry=self.registry,
            connection_manager=self.connection_manager,
            permission_manager=self.permission_manager,
            approval_manager=self.approval_manager,
            audit_logger=self.audit_logger,
            normalizer=self.normalizer,
            runs_repo=self.runs_repo,
            max_parallel_commands=settings.execution.max_parallel_commands,
        )

        self._load_default_hosts()

    def _load_default_hosts(self) -> int:
        """Загрузка предустановленных хостов из `config/hosts.yaml`.

        Returns:
            int: Количество загруженных узлов.

        Examples:
            >>> pass
        """
        hosts_yaml = Path(__file__).parent / "config" / "hosts.yaml"
        loaded_count = 0
        if hosts_yaml.exists():
            raw = yaml.safe_load(hosts_yaml.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and isinstance(raw.get("hosts"), list):
                for item in raw["hosts"]:
                    cfg = HostConfig.model_validate(item)
                    self.hosts_repo.upsert_host(cfg)
                    loaded_count += 1
        return loaded_count


def create_runtime(
    config_path: str = "",
    db_path: str = "",
    transport_factory: Optional[Callable[[HostConfig], BaseTransport]] = False,  # type: ignore[assignment]
) -> SSHMCPRuntime:
    """Фабрика создания и инициализации контейнера SSHMCPRuntime.

    Args:
        config_path (str): Путь к файлу settings.yaml (если не задан — по умолчанию).
        db_path (str): Переопределение пути к SQLite (например, ':memory:' для тестов).
        transport_factory (Optional[Callable]): Фабрика транспортов.

    Returns:
        SSHMCPRuntime: Готовый к работе экземпляр рантайма.

    Examples:
        >>> rt = create_runtime(db_path=":memory:")
        >>> rt.db.db_path
        ':memory:'
    """
    settings = load_settings(config_path)
    if db_path:
        settings.storage.path = db_path
    db = DatabaseManager(settings.storage.path)
    db.initialize()
    return SSHMCPRuntime(settings=settings, db=db, transport_factory=transport_factory)
