# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Базовый интерфейс транспорта выполнения (Base Transport)
# =============================================================================
# Description:
#   Определение абстрактного контракта Transport Layer для унифицированного
#   взаимодействия с удалёнными и локальными узлами через SSH, SFTP, локальный
#   исполнитель и Remote MCP HTTP.
#
#   Зачем нужен этот модуль:
#     1. Полная отвязка уровня управления и MCP-инструментов от способа
#        физической доставки команды (Раздел 2 ТЗ).
#     2. Защита от инъекций в командную строку за счёт раздельной передачи
#        исполняемого кода и параметров.
#
# Usage Examples:
#   Python API:
#     from ssh_mcp.transports.base import BaseTransport, RawExecutionResult
#
# File: base.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.transports
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:45:30
# =============================================================================

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RawExecutionResult(BaseModel):
    """Сырой результат выполнения команды на уровне транспорта.

    Attributes:
        exit_code (int): Код возврата процесса.
        stdout (str): Стандартный поток вывода.
        stderr (str): Поток ошибок.
        duration_ms (int): Время выполнения в миллисекундах.

    Examples:
        >>> res = RawExecutionResult(exit_code=0, stdout="ok", stderr="", duration_ms=12)
        >>> res.exit_code
        0
    """

    exit_code: int = Field(default=0)
    stdout: str = Field(default="")
    stderr: str = Field(default="")
    duration_ms: int = Field(default=0, ge=0)


class BaseTransport(ABC):
    """Абстрактный базовый класс для всех транспортов (SSH, Local, Remote MCP).

    Attributes:
        host_id (str): Идентификатор целевого узла.
        connected (bool): Текущее состояние соединения.
    """

    def __init__(self, host_id: str) -> None:
        """Инициализация базового транспорта.

        Args:
            host_id (str): Идентификатор обслуживаемого узла.

        Examples:
            >>> # Наследуется конкретными транспортами
            >>> pass
        """
        self.host_id: str = host_id
        self.connected: bool = False

    @abstractmethod
    async def connect(self) -> bool:
        """Установка соединения с целевым узлом.

        Returns:
            bool: True при успешном подключении.
        """

    @abstractmethod
    async def disconnect(self) -> bool:
        """Корректное закрытие соединения с целевым узлом.

        Returns:
            bool: True при успешном отключении.
        """

    @abstractmethod
    async def is_alive(self) -> bool:
        """Проверка активности транспортного канала.

        Returns:
            bool: True, если соединение активно и готово к работе.
        """

    @abstractmethod
    async def execute_command(
        self,
        command: str,
        args: Optional[List[str]] = [],
        env: Optional[Dict[str, str]] = {},
        shell: str = "default",
        timeout: int = 60,
        elevate: bool = False,
    ) -> RawExecutionResult:
        """Выполнение команды с раздельной безопасной передачей параметров.

        Args:
            command (str): Исполняемая команда или скрипт.
            args (Optional[List[str]]): Позиционные аргументы (отдельно от кода).
                                        Значение по умолчанию: [].
            env (Optional[Dict[str, str]]): Переменные окружения.
                                            Значение по умолчанию: {}.
            shell (str): Целевая оболочка ('powershell', 'pwsh', 'cmd', 'bash', 'sh').
            timeout (int): Таймаут выполнения в секундах.
            elevate (bool): Флаг контролируемого повышения привилегий (sudo / UAC).

        Returns:
            RawExecutionResult: Потоки stdout/stderr, код возврата и длительность.
        """

    @abstractmethod
    async def get_fingerprint(self) -> str:
        """Получение криптографического отпечатка узла.

        Returns:
            str: Строка отпечатка `SHA256:...`.
        """
