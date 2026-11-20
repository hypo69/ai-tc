# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Instruments Tests - Command Template Wizard
# =============================================================================
# Description:
#   Модульные тесты TDD для парсера и мастера построения шаблонов команд
#   для языковых моделей (apps/windows/ai_instruments/command_wizard.py).
#
# File: test_command_wizard.py
# Project: ai-windows-admin
# Package: apps.windows.ai_instruments.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 12:45:00
# =============================================================================

from __future__ import annotations

"""TDD тесты мастера и парсера шаблонов команд для моделей."""

import pytest
from apps.windows.ai_instruments.command_wizard import (
    CommandParameter,
    CommandTemplateParser,
    CommandWizardParsedResult,
)


def test_parse_net_user_active_command() -> None:
    """Проверяет парсинг целевой команды: net user {user_name} /active:{yes|no}."""
    raw = "net user {user_name} /active:{yes|no}"
    result: CommandWizardParsedResult = CommandTemplateParser.parse(raw)

    assert result.raw_template == raw
    assert result.normalized_template == "net user {user_name} /active:{active}"
    assert len(result.parameters) == 2

    # Параметр 1: user_name
    p1: CommandParameter = result.parameters[0]
    assert p1.name == "user_name"
    assert p1.param_type == "string"
    assert p1.required is True

    # Параметр 2: active (извлечен из /active:{yes|no})
    p2: CommandParameter = result.parameters[1]
    assert p2.name == "active"
    assert p2.param_type == "enum"
    assert p2.options == ["yes", "no"]
    assert p2.default == "yes"
    assert p2.flag_prefix == "/active:"

    # Проверка схемы для модели
    schema = result.parameters_schema
    assert schema["type"] == "object"
    assert "user_name" in schema["properties"]
    assert "active" in schema["properties"]
    assert schema["properties"]["active"]["enum"] == ["yes", "no"]
    assert set(schema["required"]) == {"user_name", "active"}

    # Проверка метаданных
    assert result.suggested_tool_type == "cmd"
    assert result.suggested_target_entity == "user"


def test_substitute_parameters() -> None:
    """Проверяет подстановку значений в нормализованный шаблон."""
    raw = "net user {user_name} /active:{yes|no}"
    result = CommandTemplateParser.parse(raw)

    substituted = CommandTemplateParser.substitute(
        result.normalized_template,
        {"user_name": "Administrator", "active": "no"},
    )
    assert substituted == "net user Administrator /active:no"


def test_parse_net_user_passwordreq_command() -> None:
    """Проверяет парсинг команды net user {username} /passwordreq:{yes|no}."""
    raw = "net user {username} /passwordreq:{yes|no}"
    result = CommandTemplateParser.parse(raw)

    assert result.normalized_template == "net user {username} /passwordreq:{passwordreq}"
    assert len(result.parameters) == 2
    assert result.parameters[0].name == "username"
    assert result.parameters[1].name == "passwordreq"
    assert result.parameters[1].options == ["yes", "no"]

    cmd = CommandTemplateParser.substitute(
        result.normalized_template,
        {"username": "testuser", "passwordreq": "no"},
    )
    assert cmd == "net user testuser /passwordreq:no"


def test_parse_net_user_multi_param_command() -> None:
    """Проверяет парсинг команды с несколькими переменными параметрами net user."""
    raw = "net user {username} /active:{yes|no} /passwordreq:{yes|no} /passwordchg:{yes|no}"
    result = CommandTemplateParser.parse(raw)

    assert result.normalized_template == "net user {username} /active:{active} /passwordreq:{passwordreq} /passwordchg:{passwordchg}"
    assert len(result.parameters) == 4
    names = [p.name for p in result.parameters]
    assert names == ["username", "active", "passwordreq", "passwordchg"]

    cmd = CommandTemplateParser.substitute(
        result.normalized_template,
        {"username": "dev_user", "active": "yes", "passwordreq": "no", "passwordchg": "yes"},
    )
    assert cmd == "net user dev_user /active:yes /passwordreq:no /passwordchg:yes"



def test_parse_service_config_enum() -> None:
    """Проверяет команду с несколькими вариантами выбора."""
    raw = "sc.exe config {service_name} start={auto|demand|disabled}"
    result = CommandTemplateParser.parse(raw)

    assert result.normalized_template == "sc.exe config {service_name} start={start}"
    assert len(result.parameters) == 2

    p_start = result.parameters[1]
    assert p_start.name == "start"
    assert p_start.param_type == "enum"
    assert p_start.options == ["auto", "demand", "disabled"]
    assert result.suggested_target_entity == "service"


def test_parse_typed_parameters() -> None:
    """Проверяет типизированные спецификаторы: int, bool, filepath."""
    raw = "taskkill.exe /PID {pid:int} /F"
    result = CommandTemplateParser.parse(raw)

    assert len(result.parameters) == 1
    p = result.parameters[0]
    assert p.name == "pid"
    assert p.param_type == "integer"
    assert result.suggested_target_entity == "process"


def test_parse_powershell_template() -> None:
    """Проверяет корректное распознавание команд PowerShell."""
    raw = "Get-Service -Name {name} | Where-Object {Status -eq '{status:Running|Stopped}'}"
    result = CommandTemplateParser.parse(raw)

    assert result.suggested_tool_type == "powershell"
    assert any(p.name == "name" for p in result.parameters)
    assert any(p.name == "status" for p in result.parameters)


def test_empty_and_whitespace_command() -> None:
    """Проверяет обработку пустых и невалидных входных строк."""
    result = CommandTemplateParser.parse("   ")
    assert result.raw_template == ""
    assert result.parameters == []
    assert result.parameters_schema["properties"] == {}


def test_wizard_router_endpoints() -> None:
    """Проверяет работу FastAPI роутера мастера команд через TestClient."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from apps.windows.ai_instruments.storage import AIInstrumentsStorage
    from apps.windows.ai_instruments.service import AIInstrumentsService
    from apps.windows.api.routers.router_ai_instruments import init_router

    storage = AIInstrumentsStorage(db_path=":memory:", engine="sqlite")
    service = AIInstrumentsService(storage=storage)
    router = init_router(service=service)

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    # 1. Тест /wizard/parse
    res_parse = client.post(
        "/api/v1/ai-instruments/wizard/parse",
        json={"command": "net user {user_name} /active:{yes|no}"},
    )
    assert res_parse.status_code == 200
    data = res_parse.json()
    assert data["status"] == "ok"
    assert data["result"]["normalized_template"] == "net user {user_name} /active:{active}"
    assert len(data["result"]["parameters"]) == 2

    # 2. Тест /wizard/build
    res_build = client.post(
        "/api/v1/ai-instruments/wizard/build",
        json={
            "template": data["result"]["normalized_template"],
            "parameters": {"user_name": "Ivan", "active": "yes"},
        },
    )
    assert res_build.status_code == 200
    build_data = res_build.json()
    assert build_data["status"] == "ok"
    assert build_data["command"] == "net user Ivan /active:yes"

