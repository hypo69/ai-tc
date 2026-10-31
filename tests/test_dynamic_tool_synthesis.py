# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Dynamic Tool Synthesis & Procedural WikiLLM
# =============================================================================
# Description:
#   Интеграционные и модульные тесты для динамического синтеза инструментов
#   и процедурной памяти WikiLLM (v2.2 / Спецификация 13).
#
# Usage Examples:
#   CLI:
#     pytest tests/test_dynamic_tool_synthesis.py -v
#
# File: test_dynamic_tool_synthesis.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-14 03:33:00
# =============================================================================

from __future__ import annotations

"""Тесты для динамического синтеза инструментов и процедурной памяти WikiLLM."""

import pytest
from fastapi.testclient import TestClient

from apps.windows.api.server import create_app
from apps.windows.sdk.dynamic_runner import DynamicToolRunner
from apps.windows.wikillm.procedural_service import ProceduralWikiLLMService
from apps.windows.wikillm.storage import WikiStorage


@pytest.fixture
def mem_storage() -> WikiStorage:
    """Фикстура изолированного хранилища в памяти."""
    return WikiStorage(db_path=":memory:")


@pytest.fixture
def procedural_service(mem_storage: WikiStorage) -> ProceduralWikiLLMService:
    """Фикстура сервиса процедурной памяти на базе памяти."""
    return ProceduralWikiLLMService(storage=mem_storage)


@pytest.fixture(scope="module")
def api_client() -> TestClient:
    """Фикстура TestClient для тестирования REST API."""
    app = create_app()
    return TestClient(app)


def test_wikillm_procedural_storage_crud(mem_storage: WikiStorage) -> None:
    """Проверяет CRUD операции с таблицей wikillm_procedural_tools."""
    tool_data = {
        "tool_id": "tool_test_print",
        "canonical_key": "procedural:test_print",
        "title": "Тестовая печать",
        "description": "Печать тестового документа",
        "language": "python",
        "entry_point": "run",
        "input_schema": {"type": "object", "properties": {"msg": {"type": "string"}}},
        "code_payload": "def run(msg: str) -> dict:\n    return {'printed': msg}\n",
        "author_agent": "gemini-2.5-flash",
        "execution_count": 0,
        "is_verified": True,
        "tags": ["#print", "#test"],
    }

    # 1. Сохранение
    saved = mem_storage.save_procedural_tool(tool_data)
    assert saved["tool_id"] == "tool_test_print"
    assert saved["canonical_key"] == "procedural:test_print"
    assert saved["is_verified"] is True
    assert "#print" in saved["tags"]

    # 2. Получение по ID и ключу
    by_id = mem_storage.get_procedural_tool("tool_test_print")
    assert by_id is not None
    assert by_id["title"] == "Тестовая печать"

    by_key = mem_storage.get_procedural_tool_by_key("procedural:test_print")
    assert by_key is not None
    assert by_key["tool_id"] == "tool_test_print"

    # 3. Поиск по тексту и тегу
    found_text = mem_storage.search_procedural_tools(query="печать")
    assert len(found_text) == 1
    assert found_text[0]["tool_id"] == "tool_test_print"

    found_tag = mem_storage.search_procedural_tools(tags=["#print"])
    assert len(found_tag) == 1

    # 4. Инкремент выполнения
    inc_ok = mem_storage.increment_procedural_tool_execution("tool_test_print")
    assert inc_ok is True
    updated = mem_storage.get_procedural_tool("tool_test_print")
    assert updated["execution_count"] == 1

    # 5. Удаление
    del_ok = mem_storage.delete_procedural_tool("tool_test_print")
    assert del_ok is True
    assert mem_storage.get_procedural_tool("tool_test_print") is None


def test_dynamic_tool_runner_sync_execution() -> None:
    """Проверяет успешное выполнение валидной синхронной функции через DynamicToolRunner."""
    code = (
        "def compute_hash(text: str, salt: str = '') -> dict:\n"
        "    import hashlib\n"
        "    val = f'{text}_{salt}'.encode('utf-8')\n"
        "    return {'digest': hashlib.sha256(val).hexdigest(), 'length': len(val)}\n"
    )

    res = DynamicToolRunner.execute_code(
        code_str=code,
        entry_point="compute_hash",
        args={"text": "hello", "salt": "123"},
        tool_id="test_hasher",
    )

    assert res["status"] == "success"
    assert "digest" in res["output"]
    assert res["output"]["length"] == 9


def test_dynamic_tool_runner_async_execution() -> None:
    """Проверяет исполнение асинхронных корутин через DynamicToolRunner."""
    code = (
        "import asyncio\n"
        "async def async_job(step: int) -> dict:\n"
        "    await asyncio.sleep(0.01)\n"
        "    return {'async_step': step * 2}\n"
    )

    res = DynamicToolRunner.execute_code(
        code_str=code,
        entry_point="async_job",
        args={"step": 5},
        tool_id="test_async",
    )

    assert res["status"] == "success"
    assert res["output"]["async_step"] == 10


def test_dynamic_tool_runner_error_handling() -> None:
    """Проверяет корректный перехват синтаксических ошибок и исключений во время выполнения."""
    # 1. Синтаксическая ошибка
    bad_syntax = "def broken(\n  return 123"
    res_syntax = DynamicToolRunner.execute_code(code_str=bad_syntax, entry_point="broken")
    assert res_syntax["status"] == "error"
    assert "error" in res_syntax

    # 2. Неверная точка входа
    good_code = "def actual_fn(): return {'ok': True}"
    res_no_entry = DynamicToolRunner.execute_code(code_str=good_code, entry_point="missing_fn")
    assert res_no_entry["status"] == "error"
    assert "не найдена" in res_no_entry["error"]

    # 3. Исключение во время работы
    div_zero_code = "def boom(a: int) -> dict:\n    return {'res': a / 0}"
    res_div = DynamicToolRunner.execute_code(code_str=div_zero_code, entry_point="boom", args={"a": 10})
    assert res_div["status"] == "error"
    assert "division by zero" in res_div["error"].lower()


def test_procedural_service_self_learning_cycle(procedural_service: ProceduralWikiLLMService) -> None:
    """Проверяет цикл самообучения: Cache Miss -> Синтез -> Сохранение -> Cache Hit."""
    intent = "format_user_badge"
    args = {"username": "admin", "role": "root"}

    # 1. Первый вызов (Cache Miss)
    first_res = procedural_service.synthesize_and_execute(intent=intent, args=args)
    assert first_res["status"] == "success"
    assert first_res["cache_hit"] is False
    assert first_res["synthesized"] is True
    tool_id = first_res["tool"]["tool_id"]

    # 2. Второй вызов (Cache Hit - извлечение из процедурной памяти WikiLLM)
    second_res = procedural_service.synthesize_and_execute(intent=intent, args=args)
    assert second_res["status"] == "success"
    assert second_res["cache_hit"] is True
    assert second_res["tool"]["tool_id"] == tool_id
    assert second_res["execution"]["status"] == "success"


def test_api_procedural_tools_endpoints(api_client: TestClient) -> None:
    """Проверяет эндпоинты REST API для работы с процедурной памятью и инструментами."""
    # 1. Сохранение нового инструмента
    tool_payload = {
        "tool_id": "tool_api_disk_calc",
        "canonical_key": "procedural:disk_calc",
        "title": "Калькулятор диска",
        "description": "Расчет занятого пространства",
        "language": "python",
        "entry_point": "calc",
        "input_schema": {"type": "object", "properties": {"used": {"type": "int"}, "total": {"type": "int"}}},
        "code_payload": "def calc(used: int, total: int) -> dict:\n    return {'pct': round(used / total * 100, 1)}\n",
        "author_agent": "gemini",
        "tags": ["#storage", "#calc"],
    }

    res_save = api_client.post("/api/v1/procedural-tools/save", json=tool_payload)
    assert res_save.status_code == 200
    assert res_save.json()["status"] == "ok"

    # 2. Получение списка
    res_list = api_client.get("/api/v1/procedural-tools")
    assert res_list.status_code == 200
    items = res_list.json()["items"]
    assert any(i["tool_id"] == "tool_api_disk_calc" for i in items)

    # 3. Выполнение инструмента
    res_exec = api_client.post(
        "/api/v1/procedural-tools/execute",
        json={"tool_id": "tool_api_disk_calc", "args": {"used": 25, "total": 100}},
    )
    assert res_exec.status_code == 200
    assert res_exec.json()["result"]["pct"] == 25.0

    # 4. Lookup
    res_lookup = api_client.post(
        "/api/v1/procedural-tools/lookup",
        json={"query": "procedural:disk_calc"},
    )
    assert res_lookup.status_code == 200
    assert res_lookup.json()["found"] is True

    # 5. Synthesize and Run
    res_syn = api_client.post(
        "/api/v1/procedural-tools/synthesize-and-run",
        json={"intent": "calculate_uptime", "args": {"days": 10}},
    )
    assert res_syn.status_code == 200
    assert res_syn.json()["status"] == "success"

    # 6. Удаление
    res_del = api_client.delete("/api/v1/procedural-tools/tool_api_disk_calc")
    assert res_del.status_code == 200
    assert res_del.json()["deleted"] is True

