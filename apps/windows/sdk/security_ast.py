# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows SDK - Security AST & Input Sanity
# =============================================================================
# Description:
#   Статический анализатор синтаксического дерева (AST) и санитизатор аргументов
#   для исполнительного рантайма DynamicToolRunner v2 (Спецификация 14).
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.security_ast import validate_code_security, DynamicToolInputContract
#
#     is_safe, violations = validate_code_security("import os")
#
# File: security_ast.py
# Project: ai-windows-admin
# Package: apps.windows.sdk
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-22 13:30:00
# =============================================================================

from __future__ import annotations

"""Статический анализатор AST и санитизатор входных данных DynamicToolRunner v2."""

import ast
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from pydantic import BaseModel, Field, field_validator

from header import __root__
from logger import logger

# Путь к файлу конфигурации политик безопасности (рядом с модулем, не зависит от CWD)
_CONFIG_PATH = Path(__file__).with_name("security_policy.json")
_LOGS_DIR = __root__ / "apps" / "logs"
_SECURITY_LOG = _LOGS_DIR / "security_violations.log"

# Запрещенные встроенные функции по умолчанию
DEFAULT_DISALLOWED_FUNCTIONS: Set[str] = {
    "eval", "exec", "__import__", "compile",
    "globals", "locals", "getattr", "setattr", "delattr",
}

# Разрешенные внешние и стандартные модули SDK по умолчанию
DEFAULT_ALLOWED_IMPORTS: Set[str] = {
    "tempfile", "subprocess", "json", "re",
    "pathlib", "os.path", "math", "datetime", "logger", "ctypes",
    "hashlib", "asyncio", "typing",
}

# Запрещенные служебные атрибуты (Sandbox Escape) по умолчанию
DEFAULT_DISALLOWED_ATTRIBUTES: Set[str] = {
    "__subclasses__", "__bases__", "__mro__",
    "__code__", "__closure__", "__globals__", "__builtins__",
}

# Опасные командные последовательности и попытки traversal
DEFAULT_DANGEROUS_PATTERNS: List[str] = [
    r";\s*rm",
    r";\s*shutdown",
    r"\|\s*del",
    r"&&\s*format",
    r"\.\./\.\.",
    r"\.\.\\\.\.",
]


def load_security_policy() -> Tuple[Set[str], Set[str], Set[str], List[str]]:
    """Загружает списки ограничений из файла apps/windows/sdk/security_policy.json.

    Returns:
        Tuple[Set[str], Set[str], Set[str], List[str]]: Кортеж из
            (allowed_imports, disallowed_functions, disallowed_attributes, dangerous_patterns).
    """
    allowed_imports = set(DEFAULT_ALLOWED_IMPORTS)
    disallowed_functions = set(DEFAULT_DISALLOWED_FUNCTIONS)
    disallowed_attributes = set(DEFAULT_DISALLOWED_ATTRIBUTES)
    dangerous_patterns = list(DEFAULT_DANGEROUS_PATTERNS)

    if _CONFIG_PATH.exists():
        try:
            data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            if "allowed_imports" in data and isinstance(data["allowed_imports"], list):
                allowed_imports.update(data["allowed_imports"])
            if "disallowed_functions" in data and isinstance(data["disallowed_functions"], list):
                disallowed_functions.update(data["disallowed_functions"])
            if "disallowed_attributes" in data and isinstance(data["disallowed_attributes"], list):
                disallowed_attributes.update(data["disallowed_attributes"])
            if "dangerous_patterns" in data and isinstance(data["dangerous_patterns"], list):
                dangerous_patterns = data["dangerous_patterns"]
        except Exception as exc:
            logger.warning(f"[SecurityAST] Ошибка чтения {_CONFIG_PATH}: {exc}. Используются значения по умолчанию.")

    return allowed_imports, disallowed_functions, disallowed_attributes, dangerous_patterns


class SecurityASTVisitor(ast.NodeVisitor):
    """Статический инспектор синтаксического дерева Python-кода (AST)."""

    def __init__(
        self,
        allowed_imports: Set[str] | None = None,
        disallowed_functions: Set[str] | None = None,
        disallowed_attributes: Set[str] | None = None,
    ) -> None:
        """Инициализирует инспектор AST с заданными политиками."""
        self.violations: List[str] = []
        p_imports, p_funcs, p_attrs, _ = load_security_policy()
        self.allowed_imports = allowed_imports if allowed_imports is not None else p_imports
        self.disallowed_functions = disallowed_functions if disallowed_functions is not None else p_funcs
        self.disallowed_attributes = disallowed_attributes if disallowed_attributes is not None else p_attrs

    def visit_Call(self, node: ast.Call) -> None:
        """Проверка вызовов функций на запрещенные системные имена."""
        if isinstance(node.func, ast.Name):
            if node.func.id in self.disallowed_functions:
                self.violations.append(f"Запрещен вызов встроенной функции '{node.func.id}'")
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        """Проверка прямых импортов (import xxx)."""
        for alias in node.names:
            base_module = alias.name.split(".")[0]
            if alias.name != "os.path" and base_module not in self.allowed_imports:
                self.violations.append(f"Запрещен импорт модуля '{alias.name}'")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Проверка селективных импортов (from xxx import yyy)."""
        if node.module:
            base_module = node.module.split(".")[0]
            if node.module != "os.path" and base_module not in self.allowed_imports:
                self.violations.append(f"Запрещен импорт из модуля '{node.module}'")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        """Защита от обращения к мета-атрибутам классов (Sandbox Escape)."""
        if node.attr in self.disallowed_attributes:
            self.violations.append(f"Запрещен доступ к мета-атрибуту '{node.attr}'")
        self.generic_visit(node)


def log_security_violation(
    violations: List[str],
    author_agent: str = "unknown",
    canonical_key: str = "unknown",
) -> None:
    """Записывает попытку нарушения политик безопасности в системный журнал."""
    try:
        _LOGS_DIR.mkdir(parents=True, exist_ok=True)
        now_str = datetime.now(timezone.utc).isoformat()
        log_entry = (
            f"[{now_str}] AGENT={author_agent} KEY={canonical_key} "
            f"VIOLATIONS={'; '.join(violations)}\n"
        )
        with open(_SECURITY_LOG, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception as exc:
        logger.error(f"[SecurityAST] Не удалось записать в security log: {exc}")


def validate_code_security(
    code_str: str,
    author_agent: str = "agent",
    canonical_key: str = "unknown",
) -> Tuple[bool, List[str]]:
    """Проверяет безопасность динамического кода перед выполнением.

    Args:
        code_str: Строка с исходным кодом Python.
        author_agent: Имя агента, создавшего код.
        canonical_key: Канонический ключ инструмента.

    Returns:
        Tuple[bool, List[str]]: (is_safe, список нарушений).
    """
    if not code_str or not code_str.strip():
        return False, ["Код модуля пуст."]

    try:
        tree = ast.parse(code_str)
    except SyntaxError as e:
        return False, [f"Синтаксическая ошибка в коде: {e}"]

    visitor = SecurityASTVisitor()
    visitor.visit(tree)

    if visitor.violations:
        logger.warning(f"[AST Security] Нарушения безопасности в {canonical_key}: {visitor.violations}")
        log_security_violation(visitor.violations, author_agent=author_agent, canonical_key=canonical_key)
        return False, visitor.violations

    return True, []


class DynamicToolInputContract(BaseModel):
    """Pydantic-контракт для санитизации входных параметров инструмента."""

    tool_id: str = Field(..., description="Уникальный ID инструмента из WikiLLM")
    args: Dict[str, Any] = Field(default_factory=dict, description="Словарь параметров инструмента")

    @field_validator("args")
    @classmethod
    def sanitize_string_args(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Санитизация строк от Shell Injections и выходов из каталогов."""
        _, _, _, dangerous_patterns = load_security_policy()

        for key, val in v.items():
            if isinstance(val, str):
                for pat in dangerous_patterns:
                    if re.search(pat, val, re.IGNORECASE):
                        raise ValueError(f"Обнаружена опасная комбинация в аргументе '{key}': {val}")
        return v


__all__ = [
    "SecurityASTVisitor",
    "load_security_policy",
    "validate_code_security",
    "DynamicToolInputContract",
    "log_security_violation",
]

