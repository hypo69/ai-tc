# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin AI Instruments Tests
# =============================================================================
# Description:
#   Тесты для базы данных инструментов ИИ-агента (ai_instruments.db):
#   изолированное хранение, поиск, инкремент вызовов, извлечение из цепочки
#   рассуждений и отделение от базы WikiLLM.
#
# Usage Examples:
#   pytest apps/windows/ai_instruments/tests/test_ai_instruments.py
#
# File: test_ai_instruments.py
# Project: ai-windows-admin
# Package: apps.windows.ai_instruments.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 18:58:00
# =============================================================================

from __future__ import annotations

"""Тесты для изолированной базы данных инструментов ИИ-агента."""

import pytest
from apps.windows.ai_instruments.models import AIInstrument, AIInstrumentCreate
from apps.windows.ai_instruments.service import AIInstrumentsService
from apps.windows.ai_instruments.storage import AIInstrumentsStorage


@pytest.fixture
def mem_storage() -> AIInstrumentsStorage:
    """Фикстура изолированного хранилища инструментов в памяти."""
    return AIInstrumentsStorage(":memory:")


@pytest.fixture
def service(mem_storage: AIInstrumentsStorage) -> AIInstrumentsService:
    """Фикстура сервиса инструментов агента."""
    return AIInstrumentsService(storage=mem_storage)


def test_save_and_retrieve_instrument(mem_storage: AIInstrumentsStorage) -> None:
    """Проверка сохранения и извлечения инструмента из ai_instruments."""
    inst = AIInstrument(
        tool_id="inst_test_spooler",
        name="Restart Print Spooler",
        tool_type="powershell",
        command="Restart-Service -Name Spooler -Force",
        description="Перезапуск службы печати",
        target_entity="service:spooler",
        risk_level="safe",
    )
    saved = mem_storage.save_instrument(inst)
    assert saved.tool_id == "inst_test_spooler"

    retrieved = mem_storage.get_instrument("inst_test_spooler")
    assert retrieved is not None
    assert retrieved.name == "Restart Print Spooler"
    assert retrieved.command == "Restart-Service -Name Spooler -Force"
    assert retrieved.target_entity == "service:spooler"
    assert retrieved.execution_count == 0


def test_list_and_search_instruments(mem_storage: AIInstrumentsStorage) -> None:
    """Проверка фильтрации и поиска инструментов."""
    inst1 = AIInstrument(
        tool_id="inst_net_flush",
        name="Flush DNS Cache",
        tool_type="cmd",
        command="ipconfig /flushdns",
        description="Очистка кэша DNS",
        target_entity="network",
    )
    inst2 = AIInstrument(
        tool_id="inst_kill_proc",
        name="Stop Frozen Process",
        tool_type="powershell",
        command="Stop-Process -Id {pid} -Force",
        description="Завершение процесса",
        target_entity="process",
    )
    mem_storage.save_instrument(inst1)
    mem_storage.save_instrument(inst2)

    all_tools = mem_storage.list_instruments()
    assert len(all_tools) == 2

    cmd_tools = mem_storage.list_instruments(tool_type="cmd")
    assert len(cmd_tools) == 1
    assert cmd_tools[0].tool_id == "inst_net_flush"

    search_res = mem_storage.search_instruments("DNS")
    assert len(search_res) == 1
    assert search_res[0].name == "Flush DNS Cache"


def test_record_execution(mem_storage: AIInstrumentsStorage) -> None:
    """Проверка фиксации выполнения инструмента."""
    inst = AIInstrument(
        tool_id="inst_exec_test",
        name="Test Tool",
        command="echo 1",
    )
    mem_storage.save_instrument(inst)
    ok = mem_storage.record_execution("inst_exec_test")
    assert ok is True

    updated = mem_storage.get_instrument("inst_exec_test")
    assert updated is not None
    assert updated.execution_count == 1
    assert updated.last_executed_at is not None


def test_extract_and_save_from_reasoning(service: AIInstrumentsService) -> None:
    """Проверка извлечения инструментов из текста рассуждений модели."""
    reasoning_text = """
    В ходе анализа процесса обнаружено зависание потоков.
    Рекомендуется выполнить диагностику дескрипторов:
    ```powershell
    Get-Process -Id 1234 | Select-Object -ExpandProperty Handles
    ```
    И если не помогло, перезапустить службу:
    ```powershell
    Restart-Service -Name WbioSrvc -Force
    ```
    """
    tools = service.extract_and_save_from_text(
        text=reasoning_text,
        target_entity="process:svchost.exe",
        title_prefix="Диагностика svchost",
    )
    assert len(tools) == 2
    assert "Handles" in tools[0].command
    assert "WbioSrvc" in tools[1].command
    assert tools[0].target_entity == "process:svchost.exe"


def test_router_endpoints(service: AIInstrumentsService) -> None:
    """Проверка REST API эндпоинтов /api/v1/ai-instruments/* через TestClient."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from apps.windows.api.routers.router_ai_instruments import init_router

    app = FastAPI()
    router = init_router(service=service)
    app.include_router(router)
    client = TestClient(app)

    # 1. Проверка сохранения
    save_resp = client.post(
        "/api/v1/ai-instruments/save",
        json={
            "tool_id": "inst_api_test",
            "name": "API Test Tool",
            "tool_type": "powershell",
            "command": "Get-Date",
            "description": "Тестовый инструмент API",
            "target_entity": "system",
        },
    )
    assert save_resp.status_code == 200
    assert save_resp.json()["success"] is True

    # 2. Проверка получения по ID
    get_resp = client.get("/api/v1/ai-instruments/inst_api_test")
    assert get_resp.status_code == 200
    assert get_resp.json()["item"]["name"] == "API Test Tool"

    # 3. Проверка списка
    list_resp = client.get("/api/v1/ai-instruments/list")
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1

    # 4. Проверка статуса
    status_resp = client.get("/api/v1/ai-instruments/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "ok"

    # 5. Проверка удаления
    del_resp = client.delete("/api/v1/ai-instruments/inst_api_test")
    assert del_resp.status_code == 200
    assert del_resp.json()["success"] is True

    # 6. Проверка конфигурации базы данных
    cfg_resp = client.get("/api/v1/ai-instruments/db/config")
    assert cfg_resp.status_code == 200
    assert "engine" in cfg_resp.json()

    # 7. Проверка check подключения
    check_resp = client.post(
        "/api/v1/ai-instruments/db/check",
        json={"engine": "sqlite", "sqlite_path": ":memory:"},
    )
    assert check_resp.status_code == 200
    assert check_resp.json()["ok"] is True


def test_hostinger_direct_and_sqlite_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверка переключения с недоступного PHP API на резервную базу SQLite без ошибок."""
    storage = AIInstrumentsStorage(
        db_path=":memory:",
        engine="hostinger",
        hostinger_config={
            "connection_type": "php_api",
            "host": "",
            "user": "",
            "php_api_url": "https://127.0.0.1:1/nonexistent.php",
            "connect_timeout": 1,
        },
    )
    assert storage.engine == "sqlite"
    inst = AIInstrument(
        tool_id="inst_fallback_ok",
        name="Fallback Tool",
        command="Get-Process",
    )
    saved = storage.save_instrument(inst)
    assert saved.tool_id == "inst_fallback_ok"
    assert storage.get_instrument("inst_fallback_ok") is not None


def test_seed_default_instruments_catalog(service: AIInstrumentsService) -> None:
    """Проверка заполнения базы полным каталогом инструментов из apps/windows/sdk и .agents/skills."""
    from apps.windows.ai_instruments.default_catalog import DEFAULT_AGENT_INSTRUMENTS

    seeded = service.seed_default_instruments()
    assert len(seeded) == len(DEFAULT_AGENT_INSTRUMENTS)
    assert len(seeded) >= 50

    all_items = service.list_instruments(limit=200)
    assert len(all_items) == len(DEFAULT_AGENT_INSTRUMENTS)

    # Повторный вызов без force не дублирует записи
    second = service.seed_default_instruments(force=False)
    assert second == []


@pytest.mark.asyncio
async def test_register_database_instruments_in_registry(service: AIInstrumentsService, mem_storage: AIInstrumentsStorage) -> None:
    """Проверка загрузки инструментов из ai_instruments в ToolRegistry и их выполнения."""
    from apps.windows.sdk.core.tools.registry import ToolRegistry
    from apps.windows.sdk.core.tools.database_tool import register_database_instruments

    service.seed_default_instruments()
    registry = ToolRegistry()

    loaded_count = register_database_instruments(registry, storage=mem_storage)
    assert loaded_count >= 50
    assert registry.has("inst_powershell_process_tracker")

    tool = registry.get("inst_powershell_process_tracker")
    assert tool is not None
    assert getattr(tool, "is_dynamic", False) is True

    # Проверка вызова инструмента
    res = await tool.execute()
    assert res.status in ("ok", "warn")
    assert res.tool_name == "inst_powershell_process_tracker"






