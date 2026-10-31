# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Центральный реестр команд (Command Registry)
# =============================================================================
# Description:
#   Регистрация, хранение, поиск и строгая валидация параметров всех
#   административных операций SSH MCP Server. Ни одна операция не выполняется
#   в обход Command Registry (Раздел 5 ТЗ).
#
#   Зачем нужен этот модуль:
#     1. Декларативный контроль допустимых операций, их категорий, уровня
#        привилегий и уровня риска (low, medium, high, critical).
#     2. Загрузка предустановленных команд из YAML (`windows.yaml`, `linux.yaml`)
#        и синхронизация с таблицей `commands` в SQLite.
#
# Usage Examples:
#   Python API:
#     from ssh_mcp.core.command_registry import CommandRegistry
#     reg = CommandRegistry(commands_repo)
#     reg.load_default_catalog()
#
# File: command_registry.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:48:30
# =============================================================================

from pathlib import Path
import re
from typing import Any, Dict, List, Optional
import yaml

from ..schemas.command import CommandDefinition, ParameterSpec
from ..storage.repositories.commands_repo import CommandsRepository


class CommandValidationError(ValueError):
    """Исключение при отсутствии команды в реестре или невалидных параметрах вызова."""


class CommandRegistry:
    """Центральный реестр доступных административных команд и их контрактов.

    Attributes:
        repo (Optional[CommandsRepository]): Репозиторий синхронизации с БД.

    Examples:
        >>> reg = CommandRegistry()
        >>> reg.load_builtin_defaults()
        True
        >>> cmd = reg.resolve("windows.service.restart")
        >>> cmd.risk_level
        'high'
    """

    def __init__(self, repo: Optional[CommandsRepository] = False) -> None:  # type: ignore[assignment]
        """Инициализация реестра команд.

        Args:
            repo (Optional[CommandsRepository]): Репозиторий таблицы `commands`.

        Examples:
            >>> reg = CommandRegistry()
        """
        self.repo = repo
        self._commands: Dict[str, CommandDefinition] = {}

    def register(self, cmd: CommandDefinition) -> bool:
        """Регистрация команды в оперативном каталоге и сохранение в БД.

        Args:
            cmd (CommandDefinition): Определение команды.

        Returns:
            bool: True при успешной регистрации.

        Examples:
            >>> reg = CommandRegistry()
            >>> c = CommandDefinition(id="test.op", name="Test", platform="any", category="system")
            >>> reg.register(c)
            True
        """
        self._commands[cmd.id] = cmd
        if self.repo:
            self.repo.upsert_command(cmd)
        return True

    def resolve(self, command_id: str) -> CommandDefinition:
        """Разрешение команды по идентификатору.

        Args:
            command_id (str): Идентификатор команды в реестре.

        Returns:
            CommandDefinition: Найденное определение команды.

        Exceptions:
            CommandValidationError: Если команда не зарегистрирована (запрещена).

        Examples:
            >>> reg = CommandRegistry()
            >>> _ = reg.load_builtin_defaults()
            >>> reg.resolve("system.info").category
            'system'
        """
        if not command_id or command_id not in self._commands:
            raise CommandValidationError(
                f"Команда '{command_id}' отсутствует в Command Registry или запрещена политикой"
            )
        return self._commands[command_id]

    def validate_parameters(
        self, command_id: str, provided_params: Optional[Dict[str, Any]] = {}
    ) -> Dict[str, Any]:
        """Строгая проверка входных параметров команды по спецификации Command Registry.

        Args:
            command_id (str): Идентификатор команды.
            provided_params (Optional[Dict[str, Any]]): Словарь переданных аргументов.
                                                        Значение по умолчанию: {}.

        Returns:
            Dict[str, Any]: Проверенный и дополненный значениями по умолчанию словарь параметров.

        Exceptions:
            CommandValidationError: При отсутствии обязательного параметра или неверном типе.

        Examples:
            >>> reg = CommandRegistry()
            >>> _ = reg.load_builtin_defaults()
            >>> reg.validate_parameters("windows.service.restart", {"service_name": "Spooler"})
            {'service_name': 'Spooler'}
        """
        cmd = self.resolve(command_id)
        params = dict(provided_params) if provided_params else {}
        validated: Dict[str, Any] = {}

        for param_name, spec in cmd.parameters.items():
            if param_name not in params or params[param_name] == "":
                if spec.required:
                    raise CommandValidationError(
                        f"Обязательный параметр '{param_name}' не передан для команды '{command_id}'"
                    )
                validated[param_name] = spec.default
                continue

            val = params[param_name]
            self._check_type(command_id, param_name, val, spec)
            validated[param_name] = val

        for extra_k, extra_v in params.items():
            if extra_k not in validated:
                validated[extra_k] = extra_v

        return validated

    @staticmethod
    def _check_type(command_id: str, param_name: str, val: Any, spec: ParameterSpec) -> bool:
        """Проверка соответствия типа и регулярного выражения параметра.

        Args:
            command_id (str): Идентификатор команды.
            param_name (str): Имя параметра.
            val (Any): Значение параметра.
            spec (ParameterSpec): Спецификация параметра.

        Returns:
            bool: True при успешной проверке.

        Exceptions:
            CommandValidationError: При несовпадении типа или шаблона.

        Examples:
            >>> s = ParameterSpec(type="integer", required=True)
            >>> CommandRegistry._check_type("cmd", "pid", 100, s)
            True
        """
        type_map = {
            "string": str,
            "integer": int,
            "boolean": bool,
            "float": (int, float),
            "list": list,
            "dict": dict,
        }
        expected_py_type = type_map.get(spec.type, str)
        if spec.type == "integer" and isinstance(val, bool):
            raise CommandValidationError(
                f"Параметр '{param_name}' команды '{command_id}' должен быть integer, получен boolean"
            )
        if not isinstance(val, expected_py_type):
            raise CommandValidationError(
                f"Параметр '{param_name}' команды '{command_id}' должен иметь тип '{spec.type}'"
            )
        if spec.pattern and isinstance(val, str):
            if not re.match(spec.pattern, val):
                raise CommandValidationError(
                    f"Параметр '{param_name}' команды '{command_id}' не соответствует шаблону '{spec.pattern}'"
                )
        return True

    def load_from_yaml_dir(self, directory_path: Optional[str] = "") -> int:
        """Загрузка команд из YAML-файлов каталога `registry/commands`.

        Args:
            directory_path (Optional[str]): Путь к директории с YAML-файлами.
                                            Значение по умолчанию: ''.

        Returns:
            int: Количество загруженных команд.

        Examples:
            >>> reg = CommandRegistry()
            >>> reg.load_from_yaml_dir() >= 20
            True
        """
        target_dir = (
            Path(directory_path)
            if directory_path
            else Path(__file__).parent.parent / "registry" / "commands"
        )
        count = 0
        if target_dir.exists() and target_dir.is_dir():
            for yaml_file in sorted(target_dir.glob("*.yaml")):
                raw = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
                if isinstance(raw, dict) and isinstance(raw.get("commands"), list):
                    for item in raw["commands"]:
                        cmd_def = CommandDefinition.model_validate(item)
                        self.register(cmd_def)
                        count += 1
        return count

    def load_builtin_defaults(self) -> bool:
        """Загрузка полного набора кроссплатформенных и платформенных команд для всех 10 модулей.

        Returns:
            bool: True после загрузки каталога.

        Examples:
            >>> reg = CommandRegistry()
            >>> reg.load_builtin_defaults()
            True
        """
        self.load_from_yaml_dir()

        universal_specs: List[Dict[str, Any]] = [
            # 4.2 Выполнение команд
            {"id": "ssh.execute", "name": "Выполнение команды", "category": "execution", "privilege": "standard", "risk_level": "medium", "requires_confirmation": False, "parameters": {"command": {"type": "string", "required": True}}},
            {"id": "ssh.execute_script", "name": "Выполнение скрипта", "category": "execution", "privilege": "administrator", "risk_level": "high", "requires_confirmation": True, "parameters": {"script": {"type": "string", "required": True}}},
            {"id": "ssh.execute_batch", "name": "Пакетное выполнение", "category": "execution", "privilege": "standard", "risk_level": "medium", "requires_confirmation": False, "parameters": {"commands": {"type": "list", "required": True}}},
            {"id": "ssh.execute_async", "name": "Асинхронная задача", "category": "execution", "privilege": "standard", "risk_level": "medium", "requires_confirmation": False, "parameters": {"command": {"type": "string", "required": True}}},
            # 4.3 Системное администрирование
            {"id": "system.info", "name": "Системная информация", "category": "system", "privilege": "standard", "risk_level": "low"},
            {"id": "system.cpu", "name": "Метрики процессора", "category": "system", "privilege": "standard", "risk_level": "low"},
            {"id": "system.memory", "name": "Метрики памяти", "category": "system", "privilege": "standard", "risk_level": "low"},
            {"id": "system.disks", "name": "Диски и тома", "category": "system", "privilege": "standard", "risk_level": "low"},
            {"id": "system.uptime", "name": "Время работы системы", "category": "system", "privilege": "standard", "risk_level": "low"},
            {"id": "system.boot_info", "name": "Сведения о загрузке", "category": "system", "privilege": "standard", "risk_level": "low"},
            {"id": "system.environment", "name": "Переменные окружения", "category": "system", "privilege": "standard", "risk_level": "low"},
            # 4.4 Управление процессами
            {"id": "process.list", "name": "Список процессов", "category": "processes", "privilege": "standard", "risk_level": "low"},
            {"id": "process.get", "name": "Детали процесса", "category": "processes", "privilege": "standard", "risk_level": "low", "parameters": {"pid": {"type": "integer", "required": True}}},
            {"id": "process.start", "name": "Запуск процесса", "category": "processes", "privilege": "standard", "risk_level": "medium", "parameters": {"executable": {"type": "string", "required": True}}},
            {"id": "process.stop", "name": "Завершение процесса", "category": "processes", "privilege": "administrator", "risk_level": "high", "requires_confirmation": True, "parameters": {"pid": {"type": "integer", "required": True}}},
            {"id": "process.tree", "name": "Дерево процессов", "category": "processes", "privilege": "standard", "risk_level": "low"},
            {"id": "process.resource_usage", "name": "Потребление ресурсов процессами", "category": "processes", "privilege": "standard", "risk_level": "low"},
            # 4.5 Управление службами
            {"id": "service.list", "name": "Список служб", "category": "services", "privilege": "standard", "risk_level": "low"},
            {"id": "service.status", "name": "Статус службы", "category": "services", "privilege": "standard", "risk_level": "low", "parameters": {"service_name": {"type": "string", "required": True}}},
            {"id": "service.start", "name": "Запуск службы", "category": "services", "privilege": "administrator", "risk_level": "medium", "parameters": {"service_name": {"type": "string", "required": True}}},
            {"id": "service.stop", "name": "Остановка службы", "category": "services", "privilege": "administrator", "risk_level": "high", "requires_confirmation": True, "parameters": {"service_name": {"type": "string", "required": True}}},
            {"id": "service.restart", "name": "Перезапуск службы", "category": "services", "privilege": "administrator", "risk_level": "high", "requires_confirmation": True, "parameters": {"service_name": {"type": "string", "required": True}}},
            {"id": "service.enable", "name": "Включение службы", "category": "services", "privilege": "administrator", "risk_level": "high", "requires_confirmation": True, "parameters": {"service_name": {"type": "string", "required": True}}},
            {"id": "service.disable", "name": "Отключение службы", "category": "services", "privilege": "administrator", "risk_level": "high", "requires_confirmation": True, "parameters": {"service_name": {"type": "string", "required": True}}},
            # 4.6 Файловая система
            {"id": "fs.list", "name": "Содержимое каталога", "category": "filesystem", "privilege": "standard", "risk_level": "low", "parameters": {"path": {"type": "string", "required": True}}},
            {"id": "fs.stat", "name": "Метаданные файла", "category": "filesystem", "privilege": "standard", "risk_level": "low", "parameters": {"path": {"type": "string", "required": True}}},
            {"id": "fs.read", "name": "Чтение файла", "category": "filesystem", "privilege": "standard", "risk_level": "low", "parameters": {"path": {"type": "string", "required": True}}},
            {"id": "fs.write", "name": "Запись файла", "category": "filesystem", "privilege": "standard", "risk_level": "medium", "parameters": {"path": {"type": "string", "required": True}, "content": {"type": "string", "required": True}}},
            {"id": "fs.search", "name": "Поиск файлов", "category": "filesystem", "privilege": "standard", "risk_level": "low", "parameters": {"path": {"type": "string", "required": True}, "pattern": {"type": "string", "required": True}}},
            {"id": "fs.copy", "name": "Копирование файла", "category": "filesystem", "privilege": "standard", "risk_level": "medium", "parameters": {"source": {"type": "string", "required": True}, "destination": {"type": "string", "required": True}}},
            {"id": "fs.move", "name": "Перемещение файла", "category": "filesystem", "privilege": "standard", "risk_level": "medium", "parameters": {"source": {"type": "string", "required": True}, "destination": {"type": "string", "required": True}}},
            {"id": "fs.delete", "name": "Удаление файла", "category": "filesystem", "privilege": "administrator", "risk_level": "high", "requires_confirmation": True, "parameters": {"path": {"type": "string", "required": True}}},
            {"id": "fs.mkdir", "name": "Создание каталога", "category": "filesystem", "privilege": "standard", "risk_level": "low", "parameters": {"path": {"type": "string", "required": True}}},
            {"id": "fs.chmod", "name": "Изменение прав доступа", "category": "filesystem", "privilege": "administrator", "risk_level": "high", "requires_confirmation": True, "parameters": {"path": {"type": "string", "required": True}, "mode": {"type": "string", "required": True}}},
            {"id": "fs.chown", "name": "Изменение владельца", "category": "filesystem", "privilege": "administrator", "risk_level": "high", "requires_confirmation": True, "parameters": {"path": {"type": "string", "required": True}, "owner": {"type": "string", "required": True}}},
            # 4.7 Сеть
            {"id": "network.interfaces", "name": "Сетевые интерфейсы", "category": "network", "privilege": "standard", "risk_level": "low"},
            {"id": "network.routes", "name": "Таблица маршрутизации", "category": "network", "privilege": "standard", "risk_level": "low"},
            {"id": "network.connections", "name": "Активные сетевые соединения", "category": "network", "privilege": "standard", "risk_level": "low"},
            {"id": "network.dns", "name": "Настройки DNS", "category": "network", "privilege": "standard", "risk_level": "low"},
            {"id": "network.ping", "name": "Проверка доступности (ICMP/TCP)", "category": "network", "privilege": "standard", "risk_level": "low", "parameters": {"target": {"type": "string", "required": True}}},
            {"id": "network.port_check", "name": "Проверка TCP-порта", "category": "network", "privilege": "standard", "risk_level": "low", "parameters": {"target": {"type": "string", "required": True}, "port": {"type": "integer", "required": True}}},
            {"id": "network.firewall_status", "name": "Статус межсетевого экрана", "category": "network", "privilege": "standard", "risk_level": "low"},
            # 4.8 Пользователи и группы
            {"id": "user.list", "name": "Список пользователей", "category": "users", "privilege": "standard", "risk_level": "low"},
            {"id": "user.get", "name": "Сведения о пользователе", "category": "users", "privilege": "standard", "risk_level": "low", "parameters": {"username": {"type": "string", "required": True}}},
            {"id": "user.create", "name": "Создание пользователя", "category": "users", "privilege": "administrator", "risk_level": "high", "requires_confirmation": True, "parameters": {"username": {"type": "string", "required": True}, "credential_ref": {"type": "string", "required": True}}},
            {"id": "user.modify", "name": "Изменение пользователя", "category": "users", "privilege": "administrator", "risk_level": "high", "requires_confirmation": True, "parameters": {"username": {"type": "string", "required": True}}},
            {"id": "user.disable", "name": "Отключение пользователя", "category": "users", "privilege": "administrator", "risk_level": "high", "requires_confirmation": True, "parameters": {"username": {"type": "string", "required": True}}},
            {"id": "user.delete", "name": "Удаление пользователя", "category": "users", "privilege": "administrator", "risk_level": "critical", "requires_confirmation": True, "parameters": {"username": {"type": "string", "required": True}}},
            {"id": "user.groups", "name": "Группы пользователя", "category": "users", "privilege": "standard", "risk_level": "low", "parameters": {"username": {"type": "string", "required": True}}},
            {"id": "user.group_add", "name": "Добавление пользователя в группу", "category": "users", "privilege": "administrator", "risk_level": "high", "requires_confirmation": True, "parameters": {"username": {"type": "string", "required": True}, "group": {"type": "string", "required": True}}},
            {"id": "user.group_remove", "name": "Удаление пользователя из группы", "category": "users", "privilege": "administrator", "risk_level": "high", "requires_confirmation": True, "parameters": {"username": {"type": "string", "required": True}, "group": {"type": "string", "required": True}}},
            # 4.9 Журналы и события
            {"id": "logs.list", "name": "Список системных журналов", "category": "logs", "privilege": "standard", "risk_level": "low"},
            {"id": "logs.read", "name": "Чтение журнала событий", "category": "logs", "privilege": "standard", "risk_level": "low", "parameters": {"log_name": {"type": "string", "required": True}}},
            {"id": "logs.search", "name": "Поиск в журналах", "category": "logs", "privilege": "standard", "risk_level": "low", "parameters": {"log_name": {"type": "string", "required": True}, "query": {"type": "string", "required": True}}},
            {"id": "logs.export", "name": "Экспорт журнала", "category": "logs", "privilege": "standard", "risk_level": "low", "parameters": {"log_name": {"type": "string", "required": True}}},
            {"id": "logs.recent_errors", "name": "Последние ошибки системы", "category": "logs", "privilege": "standard", "risk_level": "low"},
            # 4.10 Диагностика и телеметрия
            {"id": "diagnostics.collect", "name": "Полный сбор диагностического пакета", "category": "diagnostics", "privilege": "standard", "risk_level": "low"},
            {"id": "diagnostics.hardware", "name": "Диагностика оборудования", "category": "diagnostics", "privilege": "standard", "risk_level": "low"},
            {"id": "diagnostics.os", "name": "Диагностика ОС", "category": "diagnostics", "privilege": "standard", "risk_level": "low"},
            {"id": "diagnostics.storage", "name": "Диагностика накопителей", "category": "diagnostics", "privilege": "standard", "risk_level": "low"},
            {"id": "diagnostics.network", "name": "Диагностика сети", "category": "diagnostics", "privilege": "standard", "risk_level": "low"},
            {"id": "diagnostics.services", "name": "Диагностика служб", "category": "diagnostics", "privilege": "standard", "risk_level": "low"},
            {"id": "diagnostics.export", "name": "Экспорт пакета телеметрии", "category": "diagnostics", "privilege": "standard", "risk_level": "low"},
        ]

        for spec in universal_specs:
            cmd = CommandDefinition.model_validate(spec)
            self.register(cmd)
        return True
