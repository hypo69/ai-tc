# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin AI Instruments - Command Template Wizard & Parser
# =============================================================================
# Description:
#   Парсер, валидатор и мастер интерактивного конструирования параметризованных
#   команд для языковых моделей (LLM) и агентов Windows.
#   Поддерживает шаблоны вида:
#     net user {user_name} /active:{yes|no}
#     sc.exe config {service_name} start={auto|demand|disabled}
#     taskkill.exe /PID {pid:int} /F
#   Автоматически извлекает параметры, определяет типы (string, enum, int, bool),
#   формирует OpenAPI / JSON Schema для модели и подставляет аргументы.
#
# Usage Examples:
#   Python API:
#     from apps.windows.ai_instruments.command_wizard import CommandTemplateParser
#
#     parser = CommandTemplateParser()
#     parsed = parser.parse("net user {user_name} /active:{yes|no}")
#     cmd = parser.substitute(parsed.normalized_template, {"user_name": "admin", "active": "yes"})
#
# File: command_wizard.py
# Project: ai-windows-admin
# Package: apps.windows.ai_instruments
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 04:53:00
# =============================================================================

from __future__ import annotations

"""Парсер, нормализатор и мастер построения команд для языковых моделей."""

import re
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CommandParameter(BaseModel):
    """Описание отдельного параметра команды."""

    name: str = Field(..., description="Системное имя параметра (идентификатор переменной)")
    param_type: str = Field(default="string", description="Тип параметра: string, enum, integer, number, boolean, filepath")
    options: List[str] = Field(default_factory=list, description="Список допустимых значений для типа enum")
    default: Optional[str] = Field(default=None, description="Значение по умолчанию")
    description: str = Field(default="", description="Описание назначения параметра на русском языке для модели")
    required: bool = Field(default=True, description="Обязателен ли параметр для передачи модели")
    raw_token: str = Field(default="", description="Исходный токен в шаблоне, например {user_name} или {yes|no}")
    flag_prefix: str = Field(default="", description="Префикс флага/ключа, если обнаружен (например /active:, -Name, start=)")


class CommandWizardParsedResult(BaseModel):
    """Результат анализа и парсинга шаблона команды."""

    raw_template: str = Field(..., description="Исходный текст команды")
    normalized_template: str = Field(..., description="Нормализованный шаблон с именованными плейсхолдерами")
    parameters: List[CommandParameter] = Field(default_factory=list, description="Список параметров")
    parameters_schema: Dict[str, Any] = Field(default_factory=dict, description="JSON-схема параметров для LLM")
    sample_command: str = Field(default="", description="Пример команды с подставленными тестовыми значениями")
    suggested_tool_id: str = Field(default="", description="Рекомендуемый tool_id")
    suggested_name: str = Field(default="", description="Рекомендуемое название инструмента")
    suggested_tool_type: str = Field(default="cmd", description="Тип инструмента: powershell, cmd, utility")
    suggested_target_entity: str = Field(default="system", description="Целевая сущность: user, service, process, etc.")
    suggested_risk_level: str = Field(default="safe", description="Уровень риска: safe, caution, danger")
    suggested_tags: List[str] = Field(default_factory=list, description="Теги")


class CommandTemplateParser:
    """Парсер параметризованных командных шаблонов для моделей и агентов."""

    # Матчим плейсхолдеры без пробелов/переносов строк, чтобы не путать со скрипт-блоками PowerShell
    TOKEN_REGEX = re.compile(r"\{([a-zA-Z0-9_\-.:=|,]+)\}")
    # Префикс ключа перед токеном: /active:, -Name , --config=, start=
    FLAG_PREFIX_REGEX = re.compile(r"([/\-]?[a-zA-Z0-9_\-]+[:=]\s*|[/\-][a-zA-Z0-9_\-]+\s+)$")

    @classmethod
    def parse(cls, raw_command: str) -> CommandWizardParsedResult:
        """Выполняет синтаксический анализ шаблона команды и строит схему параметров.

        Args:
            raw_command: Исходная строка шаблона, например:
                net user {user_name} /active:{yes|no}

        Returns:
            CommandWizardParsedResult: Структурированный результат парсинга.
        """
        raw_clean = (raw_command or "").strip()
        if not raw_clean:
            return CommandWizardParsedResult(
                raw_template="",
                normalized_template="",
                parameters=[],
                parameters_schema={"type": "object", "properties": {}, "required": []},
            )

        parameters: List[CommandParameter] = []
        param_names_seen: Dict[str, int] = {}
        normalized_template = raw_clean

        matches = list(cls.TOKEN_REGEX.finditer(raw_clean))

        # Сбор параметров и замена в нормализованном шаблоне
        for idx, match in enumerate(matches):
            raw_token = match.group(0)  # e.g. "{user_name}" or "{yes|no}"
            inner_content = match.group(1).strip()
            token_start = match.start()

            # Анализ префикса перед токеном (например, "/active:" или "start=")
            preceding_text = raw_clean[:token_start]
            prefix_match = cls.FLAG_PREFIX_REGEX.search(preceding_text)
            flag_prefix = prefix_match.group(1) if prefix_match else ""

            param = cls._extract_parameter(
                inner_content=inner_content,
                raw_token=raw_token,
                flag_prefix=flag_prefix,
                index=idx + 1,
                names_seen=param_names_seen,
            )
            parameters.append(param)

            # В нормализованном шаблоне заменяем сырой токен на именованный {param.name}
            expected_placeholder = f"{{{param.name}}}"
            if raw_token != expected_placeholder:
                normalized_template = normalized_template.replace(raw_token, expected_placeholder, 1)

        # Построение JSON-схемы для модели (Function Calling / OpenAPI)
        schema_props: Dict[str, Any] = {}
        required_keys: List[str] = []
        sample_params: Dict[str, Any] = {}

        for p in parameters:
            prop_def: Dict[str, Any] = {
                "type": "string" if p.param_type in ("string", "filepath", "enum") else p.param_type,
                "description": p.description or f"Параметр {p.name}",
            }
            if p.param_type == "enum" and p.options:
                prop_def["enum"] = p.options
            if p.default is not None:
                prop_def["default"] = p.default

            schema_props[p.name] = prop_def
            if p.required:
                required_keys.append(p.name)

            # Генерация тестового значения для образца
            if p.default is not None:
                sample_params[p.name] = p.default
            elif p.options:
                sample_params[p.name] = p.options[0]
            elif p.param_type in ("integer", "number"):
                sample_params[p.name] = "1"
            elif p.param_type == "boolean":
                sample_params[p.name] = "true"
            elif "user" in p.name.lower():
                sample_params[p.name] = "User"
            elif "service" in p.name.lower():
                sample_params[p.name] = "Spooler"
            elif "process" in p.name.lower() or "pid" in p.name.lower():
                sample_params[p.name] = "1234"
            else:
                sample_params[p.name] = f"val_{p.name}"

        parameters_schema = {
            "type": "object",
            "properties": schema_props,
            "required": required_keys,
        }

        # Тестовая подстановка для примера
        sample_cmd = cls.substitute(normalized_template, sample_params)

        # Вывод эвристических рекомендаций по метаданным
        tool_type = cls._detect_tool_type(raw_clean)
        target_entity = cls._detect_target_entity(raw_clean, parameters)
        risk_level = cls._detect_risk_level(raw_clean)
        tool_id = cls._generate_tool_id(raw_clean, target_entity)
        tool_name = cls._generate_tool_name(raw_clean, target_entity, parameters)
        tags = cls._generate_tags(raw_clean, tool_type, target_entity)

        return CommandWizardParsedResult(
            raw_template=raw_clean,
            normalized_template=normalized_template,
            parameters=parameters,
            parameters_schema=parameters_schema,
            sample_command=sample_cmd,
            suggested_tool_id=tool_id,
            suggested_name=tool_name,
            suggested_tool_type=tool_type,
            suggested_target_entity=target_entity,
            suggested_risk_level=risk_level,
            suggested_tags=tags,
        )

    @classmethod
    def substitute(cls, template: str, parameters: Dict[str, Any]) -> str:
        """Подставляет значения параметров в нормализованный командный шаблон.

        Args:
            template: Шаблон команды с плейсхолдерами, например:
                net user {user_name} /active:{active}
            parameters: Словарь подстановок, например:
                {"user_name": "admin", "active": "yes"}

        Returns:
            str: Сформированная команда, готовая к исполнению.
        """
        result = template
        for key, val in parameters.items():
            result = result.replace(f"{{{key}}}", str(val))
        return result

    @classmethod
    def _extract_parameter(
        cls,
        inner_content: str,
        raw_token: str,
        flag_prefix: str,
        index: int,
        names_seen: Dict[str, int],
    ) -> CommandParameter:
        """Извлекает и типизирует параметр из содержимого фигурных скобок."""
        is_enum = "|" in inner_content or ("," in inner_content and not inner_content.startswith("int"))

        options: List[str] = []
        name: str = ""
        param_type: str = "string"
        default: Optional[str] = None
        description: str = ""

        if is_enum:
            param_type = "enum"
            if ":" in inner_content:
                parts = inner_content.split(":", 1)
                name = cls._sanitize_param_name(parts[0])
                enum_body = parts[1]
            else:
                enum_body = inner_content

            split_char = "|" if "|" in enum_body else ","
            options = [opt.strip() for opt in enum_body.split(split_char) if opt.strip()]
            default = options[0] if options else None
        elif ":" in inner_content:
            parts = inner_content.split(":", 1)
            name = cls._sanitize_param_name(parts[0])
            type_hint = parts[1].strip().lower()
            if type_hint in ("int", "integer"):
                param_type = "integer"
            elif type_hint in ("number", "float"):
                param_type = "number"
            elif type_hint in ("bool", "boolean"):
                param_type = "boolean"
            elif type_hint in ("path", "filepath", "file"):
                param_type = "filepath"
            else:
                param_type = "string"
        else:
            if "=" in inner_content:
                parts = inner_content.split("=", 1)
                name = cls._sanitize_param_name(parts[0])
                default = parts[1].strip()
            else:
                name = cls._sanitize_param_name(inner_content)

        # Если имя параметра не задано внутри скобок, берем из префикса
        if not name:
            if flag_prefix:
                clean_flag = re.sub(r"^[/\-]+", "", flag_prefix)
                clean_flag = re.sub(r"[:=\s]+$", "", clean_flag)
                name = cls._sanitize_param_name(clean_flag)
            if not name:
                name = f"param_{index}"

        # Обеспечиваем уникальность имени параметра
        count = names_seen.get(name, 0)
        names_seen[name] = count + 1
        if count > 0:
            name = f"{name}_{count + 1}"

        if not description:
            if is_enum and options:
                opts_str = " | ".join(options)
                description = f"Выбор значения для ключа {flag_prefix or name} ({opts_str})"
            elif flag_prefix:
                description = f"Аргумент системного параметра {flag_prefix.strip()}"
            else:
                description = f"Пользовательский параметр {name}"

        return CommandParameter(
            name=name,
            param_type=param_type,
            options=options,
            default=default,
            description=description,
            required=True,
            raw_token=raw_token,
            flag_prefix=flag_prefix,
        )

    @classmethod
    def _sanitize_param_name(cls, raw: str) -> str:
        """Очищает строку для получения валидного идентификатора переменной."""
        clean = re.sub(r"[^a-zA-Z0-9_]", "_", raw.strip())
        clean = re.sub(r"_+", "_", clean).strip("_").lower()
        return clean or "arg"

    @classmethod
    def _detect_tool_type(cls, cmd: str) -> str:
        """Определяет среду исполнения: powershell, cmd или utility."""
        c = cmd.lower().strip()
        ps_indicators = [
            "get-", "set-", "restart-", "stop-", "start-", "new-", "remove-",
            "select-object", "where-object", "convertto-json", "$", "powershell", "pwsh"
        ]
        if any(ind in c for ind in ps_indicators):
            return "powershell"

        cmd_indicators = [
            "net ", "net.exe", "sc ", "sc.exe", "taskkill", "tasklist",
            "shutdown", "chkdsk", "sfc", "dism", "reg ", "reg.exe",
            "whoami", "ipconfig", "ping", "tracert", "route", "diskpart"
        ]
        if any(c.startswith(ind) or f" {ind}" in c for ind in cmd_indicators):
            return "cmd"

        return "utility"

    @classmethod
    def _detect_target_entity(cls, cmd: str, params: List[CommandParameter]) -> str:
        """Определяет категорию системной сущности."""
        c = cmd.lower()
        param_names = [p.name.lower() for p in params]

        if "user" in c or any("user" in p for p in param_names) or "whoami" in c:
            return "user"
        if "service" in c or "sc.exe" in c or "sc " in c or any("service" in p for p in param_names):
            return "service"
        if "process" in c or "taskkill" in c or "tasklist" in c or any("pid" in p for p in param_names):
            return "process"
        if "netsh" in c or "ipconfig" in c or "firewall" in c or "route" in c or any("ip" in p for p in param_names):
            return "network"
        if "diskpart" in c or "volume" in c or "partition" in c or "chkdsk" in c or "drive" in c:
            return "storage"
        return "system"

    @classmethod
    def _detect_risk_level(cls, cmd: str) -> str:
        """Оценивает уровень риска операции SafeOps."""
        c = cmd.lower()
        danger_markers = ["format", "clean", "delete", "remove", "drop", "wipe", "/f /q", "kill -f"]
        caution_markers = ["stop", "restart", "config", "set", "/active:no", "disable", "shutdown", "taskkill"]

        if any(m in c for m in danger_markers):
            return "danger"
        if any(m in c for m in caution_markers):
            return "caution"
        return "safe"

    @classmethod
    def _generate_tool_id(cls, cmd: str, entity: str) -> str:
        """Генерирует уникальный и понятный идентификатор инструмента."""
        first_word = cmd.split()[0] if cmd.split() else "cmd"
        first_clean = re.sub(r"[^a-zA-Z0-9]", "", first_word).lower()
        uid_part = uuid.uuid4().hex[:6]
        return f"inst_{entity}_{first_clean}_{uid_part}"

    @classmethod
    def _generate_tool_name(cls, cmd: str, entity: str, params: List[CommandParameter]) -> str:
        """Генерирует понятное русскоязычное название команды."""
        first_words = " ".join(cmd.split()[:2])
        param_str = ", ".join(p.name for p in params) if params else "без параметров"
        return f"Команда {first_words} ({entity}): {param_str}"

    @classmethod
    def _generate_tags(cls, cmd: str, tool_type: str, entity: str) -> List[str]:
        """Генерирует теги каталогизации."""
        tags = ["#agent_tool", f"#{tool_type}", f"#{entity}"]
        first_word = cmd.split()[0].replace(".exe", "").lower() if cmd.split() else ""
        if first_word and f"#{first_word}" not in tags:
            tags.append(f"#{first_word}")
        return tags
