# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Dynamic Tool Runner v2 & Lifecycle
# =============================================================================
# Description:
#   Тесты валидационного контура DynamicToolRunner v2 (AST, санитизация),
#   жизненного цикла процедурной памяти WikiLLM и дедупликации (Спецификации 14 и 16).
#
# Usage Examples:
#   CLI:
#     pytest tests/test_dynamic_tool_runner_v2_and_lifecycle.py -v
#
# File: test_dynamic_tool_runner_v2_and_lifecycle.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 01:20:00
# =============================================================================

from __future__ import annotations

"""Тесты для DynamicToolRunner v2, AST-проверки и жизненного цикла WikiLLM."""

import os
from pathlib import Path
import pytest

from apps.windows.sdk.dynamic_runner import DynamicToolRunner
from apps.windows.sdk.security_ast import (
    DynamicToolInputContract,
    SecurityASTVisitor,
    load_security_policy,
    validate_code_security,
)
from apps.windows.wikillm.procedural_service import ProceduralWikiLLMService
from apps.windows.wikillm.storage import WikiStorage


@pytest.fixture
def mem_storage() -> WikiStorage:
    """Фикстура изолированного хранилища в памяти."""
    return WikiStorage(db_path=":memory:")


@pytest.fixture
def procedural_service(mem_storage: WikiStorage) -> ProceduralWikiLLMService:
    """Фикстура сервиса процедурной памяти."""
    return ProceduralWikiLLMService(storage=mem_storage)


def test_ast_security_allowed_code() -> None:
    """Проверяет, что безопасный код успешно проходит AST-проверку."""
    safe_code = (
        "import json\n"
        "import pathlib\n"
        "from os.path import exists\n"
        "def run(text: str) -> dict:\n"
        "    return {'status': 'ok', 'length': len(text)}\n"
    )
    is_safe, violations = validate_code_security(safe_code)
    assert is_safe is True
    assert violations == []


def test_ast_security_disallowed_functions() -> None:
    """Проверяет блокировку запрещенных встроенных функций (eval, exec, __import__)."""
    bad_codes = [
        "def run(): return eval('1+1')",
        "def run(): exec('a = 5')",
        "def run(): return compile('x=1', 'test', 'exec')",
    ]
    for code in bad_codes:
        is_safe, violations = validate_code_security(code, canonical_key="test:disallowed_fn")
        assert is_safe is False
        assert any("Запрещен вызов" in v for v in violations)


def test_ast_security_disallowed_imports() -> None:
    """Проверяет блокировку неразрешенных внешних модулей (например, socket, requests)."""
    bad_import_1 = "import socket\ndef run(): pass"
    bad_import_2 = "from urllib.request import urlopen\ndef run(): pass"

    is_safe_1, v1 = validate_code_security(bad_import_1, canonical_key="test:import_socket")
    assert is_safe_1 is False
    assert any("Запрещен импорт модуля 'socket'" in v for v in v1)

    is_safe_2, v2 = validate_code_security(bad_import_2, canonical_key="test:import_urllib")
    assert is_safe_2 is False
    assert any("Запрещен импорт из модуля 'urllib.request'" in v for v in v2)


def test_ast_security_sandbox_escape_attributes() -> None:
    """Проверяет защиту от обращения к мета-атрибутам классов (Sandbox Escape)."""
    escape_code = (
        "def run():\n"
        "    return ().__class__.__bases__[0].__subclasses__()\n"
    )
    is_safe, violations = validate_code_security(escape_code, canonical_key="test:sandbox_escape")
    assert is_safe is False
    assert any("Запрещен доступ к мета-атрибуту" in v for v in violations)


def test_input_contract_sanitization() -> None:
    """Проверяет Pydantic-санитизацию опасных комбинаций в аргументах."""
    # Валидные аргументы
    valid = DynamicToolInputContract(tool_id="tool_1", args={"name": "Alice", "count": 10})
    assert valid.args["name"] == "Alice"

    # Опасный аргумент с инъекцией удаления файла
    with pytest.raises(ValueError, match="опасная комбинация"):
        DynamicToolInputContract(tool_id="tool_1", args={"cmd": "test; rm -rf /"})

    # Опасный аргумент с directory traversal
    with pytest.raises(ValueError, match="опасная комбинация"):
        DynamicToolInputContract(tool_id="tool_1", args={"path": "../../windows/system32"})


def test_dynamic_tool_runner_v2_security_blocking() -> None:
    """Проверяет интеграцию заслона безопасности в DynamicToolRunner v2."""
    malicious_code = "import socket\ndef run(): return socket.gethostname()"
    res = DynamicToolRunner.execute_code(
        code_str=malicious_code,
        entry_point="run",
        tool_id="malicious_tool",
    )
    assert res["status"] == "security_violation"
    assert "Код отклонен AST-анализатором" in res["message"]
    assert any("socket" in err for err in res["errors"])

    # Проверка отклонения по опасным аргументам
    safe_code = "def run(query: str): return {'q': query}"
    res_arg = DynamicToolRunner.execute_code(
        code_str=safe_code,
        entry_point="run",
        args={"query": "test; shutdown /s /t 0"},
        tool_id="shutdown_tool",
    )
    assert res_arg["status"] == "security_violation"
    assert "Аргументы отклонены" in res_arg["message"]


def test_wikillm_tool_lifecycle_metrics_and_quarantine(mem_storage: WikiStorage) -> None:
    """Проверяет жизненный цикл инструмента: версионирование, метрики и отправку в карантин."""
    tool_record = {
        "tool_id": "tool_flaky",
        "canonical_key": "procedural:flaky_tool",
        "title": "Нестабильный модуль",
        "code_payload": "def run(): return {'ok': True}",
        "status": "active",
        "version": "1.0.0",
        "compatibility": {"min_win_build": 19041, "powershell_version": "5.1+"},
    }
    saved = mem_storage.save_procedural_tool(tool_record)
    assert saved["status"] == "active"
    assert saved["version"] == "1.0.0"
    assert saved["compatibility"]["min_win_build"] == 19041

    # 1. Успешный запуск
    mem_storage.update_procedural_tool_metrics("tool_flaky", success=True, duration_ms=12.5)
    t1 = mem_storage.get_procedural_tool("tool_flaky")
    assert t1["execution_metrics"]["total_calls"] == 1
    assert t1["execution_metrics"]["success_rate"] == 1.0
    assert t1["execution_metrics"]["avg_duration_ms"] == 12.5
    assert t1["status"] == "active"

    # 2. Ошибка 1 и Ошибка 2 (consecutive_failures <= 2)
    mem_storage.update_procedural_tool_metrics("tool_flaky", success=False, duration_ms=5.0)
    mem_storage.update_procedural_tool_metrics("tool_flaky", success=False, duration_ms=6.0)
    t2 = mem_storage.get_procedural_tool("tool_flaky")
    assert t2["execution_metrics"]["consecutive_failures"] == 2
    assert t2["status"] == "active"

    # 3. Ошибка 3 (>2 неудачных запусков подряд -> Quarantined!)
    mem_storage.update_procedural_tool_metrics("tool_flaky", success=False, duration_ms=4.0)
    t3 = mem_storage.get_procedural_tool("tool_flaky")
    assert t3["execution_metrics"]["consecutive_failures"] == 3
    assert t3["status"] == "quarantined"


def test_wikillm_deduplication(procedural_service: ProceduralWikiLLMService, mem_storage: WikiStorage) -> None:
    """Проверяет автоматическую дедупликацию процедурной памяти при сходстве > 0.92."""
    # 1. Создаем и сохраняем первоначальный инструмент
    tool_orig = {
        "tool_id": "tool_get_tcp_connections",
        "canonical_key": "procedural:get_active_tcp_connections",
        "title": "Получение списка активных TCP соединений",
        "code_payload": "def run(): return {'connections': []}",
        "status": "active",
        "version": "1.0.0",
        "execution_count": 5,
    }
    mem_storage.save_procedural_tool(tool_orig)

    # 2. Похожий запрос: "получение списка активных tcp соединений"
    res = procedural_service.synthesize_and_execute(
        intent="Получение списка активных TCP соединений",
        args={},
    )
    assert res["status"] == "success"
    assert res["cache_hit"] is True
    assert res.get("deduplicated") is True
    assert res["tool"]["tool_id"] == "tool_get_tcp_connections"

