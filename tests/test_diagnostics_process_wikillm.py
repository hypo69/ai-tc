# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Diagnostics Process WikiLLM & Telemetry
# =============================================================================
# Description:
#   Тесты обновленной логики WikiLLM для процессов:
#   1. Проверка сохранения в базе знаний ТОЛЬКО общих данных (без PID и динамических метрик).
#   2. Проверка сбора расширенной телеметрии (expanded runtime telemetry JSON).
#   3. Проверка режима анализа текущего потребления и состояния ресурсов моделью.
#
# File: test_diagnostics_process_wikillm.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 13:10:00
# =============================================================================

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.windows.api.routers.router_diagnostics import (
    DiagnosticExplainRequest,
    _collect_expanded_process_telemetry,
    init_router,
)
from apps.windows.wikillm.router import (
    ApproveKnowledgeRequest,
    approve_knowledge,
    get_engine,
)
from src.ai.gemini.generative_ai import GoogleGenerativeAI


@pytest.fixture
def api_client() -> TestClient:
    """Фикстура тестового клиента FastAPI с роутером универсальной диагностики."""
    app = FastAPI()
    router = init_router()
    app.include_router(router)
    return TestClient(app)


@pytest.mark.asyncio
async def test_collect_expanded_process_telemetry_with_metadata() -> None:
    """Проверка сбора расширенной телеметрии процесса из метаданных и deep-history."""
    req = DiagnosticExplainRequest(
        table_type="process",
        title="chrome.exe [PID: 4321]",
        subtitle="Google Chrome",
        metadata={
            "pid": 4321,
            "cpu_percent": 3.5,
            "memory_working_set_mb": 240.5,
            "memory_private_bytes_mb": 180.2,
            "handles_count": 850,
            "thread_count": 24,
            "active_sockets": 6,
        },
    )

    with patch("apps.windows.api.routers.router_telemetry.get_process_deep_history", new_callable=AsyncMock) as mock_deep:
        mock_deep.return_value = {
            "pid": 4321,
            "process_name": "chrome.exe",
            "cpu_percent": 3.5,
            "memory_working_set_mb": 240.5,
            "memory_private_bytes_mb": 180.2,
            "memory_peak_working_set_mb": 310.0,
            "memory_page_faults_total": 45000,
            "handles_count": 850,
            "thread_count": 24,
            "active_sockets_count": 6,
        }

        res = await _collect_expanded_process_telemetry(req, "process:chrome.exe")
        assert res is not None
        assert res["pid"] == 4321
        assert res["process_name"] == "chrome.exe"
        assert res["cpu_percent"] == 3.5
        assert res["memory_working_set_mb"] == 240.5
        assert res["handles_count"] == 850
        assert res["thread_count"] == 24
        assert res["active_sockets_count"] == 6


@pytest.mark.asyncio
async def test_approve_process_stores_only_general_data() -> None:
    """Проверка, что одобрение процесса сохраняет в WikiLLM ТОЛЬКО общие данные, очищая PID."""
    req = ApproveKnowledgeRequest(
        canonical_key="process:chrome.exe",
        title="chrome.exe [PID: 8899]",
        developer="Google LLC",
        category="Веб-браузеры",
        summary="Высокое потребление памяти 512 МБ процессом PID 8899",
        general_summary="Популярный веб-браузер на движке Chromium, разработанный Google.",
        performance_impact="CPU 85%, RAM 512 MB, Handles 1200",
        security_verdict="Легитимное приложение",
        recommendation="Штатная работа",
        developer_advice="Используйте chrome://inspect для отладки",
        table_type="process",
    )

    resp = await approve_knowledge(req)
    assert resp["success"] is True
    assert "process:chrome.exe" in resp["canonical_key"]

    # Проверяем сущность в хранилище WikiLLM
    engine = get_engine()
    entity = engine.storage.get_entity("process:chrome.exe")
    assert entity is not None

    # В summary должны быть общие данные из general_summary, а не временные PID/МБ
    assert entity.summary == "Популярный веб-браузер на движке Chromium, разработанный Google."
    assert "PID 8899" not in entity.summary
    assert "PID 8899" not in entity.name

    # В claims фиксируется штатный общий профиль, а не сиюминутные скачки
    perf_claims = [c.statement for c in entity.claims if "Штатный профиль приложения" in c.statement]
    assert len(perf_claims) > 0
    assert not any("CPU 85%" in c.statement for c in entity.claims)

    # developer_advice сохранен в claims
    advice_claims = [c.statement for c in entity.claims if "chrome://inspect" in c.statement]
    assert len(advice_claims) > 0


@pytest.mark.asyncio
async def test_explain_process_cache_only_returns_general_data(api_client: TestClient) -> None:
    """Проверка: cache_only=True возвращает общие данные из базы знаний без вызова модели."""
    # Предварительно одобряем общее знание
    approve_req = ApproveKnowledgeRequest(
        canonical_key="process:procmon.exe",
        title="procmon.exe",
        developer="Sysinternals / Microsoft",
        category="Системный мониторинг",
        summary="Утилита мониторинга файловой системы и реестра от Sysinternals.",
        general_summary="Утилита мониторинга файловой системы и реестра от Sysinternals.",
        performance_impact="Штатный профиль",
        security_verdict="Доверенное ПО",
        recommendation="Использовать фильтрацию событий",
        table_type="process",
    )
    await approve_knowledge(approve_req)

    payload = {
        "table_type": "process",
        "title": "procmon.exe [PID: 5544]",
        "subtitle": "Process Monitor",
        "cache_only": True,
    }

    resp = api_client.post("/api/v1/diagnostics/explain", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["source"] == "wikillm"
    assert data["has_wikillm_general_data"] is True
    assert data["summary"] == "Утилита мониторинга файловой системы и реестра от Sysinternals."


@pytest.mark.asyncio
async def test_explain_process_when_wikillm_exists_invokes_model_for_resource_analysis(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверка: если общие данные есть в WikiLLM, модель вызывается для анализа live-параметров."""
    approve_req = ApproveKnowledgeRequest(
        canonical_key="process:customapp.exe",
        title="customapp.exe",
        developer="Test Vendor",
        category="Утилиты",
        summary="Общее назначение фонового сервиса customapp.",
        general_summary="Общее назначение фонового сервиса customapp.",
        performance_impact="Штатный профиль",
        security_verdict="Доверенное",
        recommendation="Оставить",
        table_type="process",
    )
    await approve_knowledge(approve_req)

    mock_model_response = json.dumps({
        "summary": "Анализ ресурсов: повышенное количество дескрипторов (2100) и активная нагрузка на ЦП (15.2%).",
        "developer": "Test Vendor",
        "category": "Утилиты",
        "performance_impact": "ЦП: 15.2%, Память: 450 МБ, Дескрипторы: 2100.",
        "security_verdict": "Легитимный процесс.",
        "recommendation": "Проверить возможную утечку дескрипторов (handles leak).",
        "action_steps": ["Мониторинг дескрипторов через Performance Monitor"],
    })

    recorded_prompt = {}

    async def mock_ask(self, prompt, **kwargs):
        recorded_prompt["text"] = prompt
        recorded_prompt["instruction"] = getattr(self, "system_instruction", "")
        return mock_model_response

    monkeypatch.setattr(GoogleGenerativeAI, "ask", mock_ask)

    payload = {
        "table_type": "process",
        "title": "customapp.exe [PID: 9000]",
        "subtitle": "Custom App",
        "metadata": {
            "pid": 9000,
            "cpu_percent": 15.2,
            "memory_working_set_mb": 450.0,
            "memory_private_bytes_mb": 380.0,
            "handles_count": 2100,
            "thread_count": 48,
        },
        "model": "gemini-3.1-flash-lite",
        "provider": "gemini",
        "cache_only": False,
    }

    resp = api_client.post("/api/v1/diagnostics/explain", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["source"] == "wikillm_resource_analysis"
    assert data["has_wikillm_general_data"] is True
    assert data["general_summary"] == "Общее назначение фонового сервиса customapp."
    assert "Анализ ресурсов: повышенное количество дескрипторов" in data["summary"]
    assert data["telemetry_data"] is not None
    assert data["telemetry_data"]["pid"] == 9000

    # Проверяем, что промпт для модели содержал секцию телеметрии и требование анализировать только ресурсы
    assert "[ОБЩИЕ ДАННЫЕ ПРОЦЕССА ИЗ БАЗЫ ЗНАНИЙ WIKILLM]" in recorded_prompt["text"]
    assert "[АКТУАЛЬНАЯ ТЕЛЕМЕТРИЯ ТЕКУЩЕГО ИНСТАНСА ПРОЦЕССА" in recorded_prompt["text"]
    assert "НЕ ОПИСЫВАЙ заново, что это за программа" in recorded_prompt["instruction"]


@pytest.mark.asyncio
async def test_explain_process_when_not_in_wikillm_fetches_full_prompt_and_auto_saves_to_wikillm(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверка Уровня 2: если процесса нет в WikiLLM, модель получает полный промпт, а общеописательная часть автоматически сохраняется."""
    import time
    unique_proc = f"novelhelper_{int(time.time()*1000)}.exe"
    payload = {
        "table_type": "process",
        "title": f"Помощник системы ({unique_proc})",
        "subtitle": "novelhelper",
        "metadata": {
            "pid": 7788,
            "cpu_percent": 1.2,
            "memory_working_set_mb": 115.0,
            "handles_count": 450,
            "thread_count": 8,
        },
        "model": "gemini-3.1-flash-lite",
        "provider": "gemini",
        "cache_only": False,
    }

    mock_response = json.dumps({
        "general_summary": "Интерактивная утилита подсказок и вспомогательных команд для операционной системы Windows.",
        "summary": "Анализ текущего потребления и состояния ресурсов: штатная фоновая работа процесса (PID 7788), низкая нагрузка на CPU 1.2%.",
        "developer": "Modern Software Corp",
        "category": "Системные утилиты",
        "performance_impact": "ЦП: 1.2%, Память: 115 МБ, Handles: 450.",
        "security_verdict": "Легитимный системный помощник, доверенная сессия.",
        "recommendation": "Процесс не требует вмешательства.",
        "action_steps": ["Оставить в фоновом режиме"],
    })

    recorded = {}

    async def mock_ask(self, prompt, **kwargs):
        recorded["prompt"] = prompt
        recorded["instruction"] = getattr(self, "system_instruction", "")
        return mock_response

    monkeypatch.setattr(GoogleGenerativeAI, "ask", mock_ask)

    resp = api_client.post("/api/v1/diagnostics/explain", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["has_wikillm_general_data"] is True
    assert data["general_summary"] == "Интерактивная утилита подсказок и вспомогательных команд для операционной системы Windows."
    assert "Анализ текущего потребления и состояния ресурсов" in data["summary"]
    assert data["canonical_key"] == f"process:{unique_proc}"

    # Проверяем, что промпт содержал оба уровня требований
    assert "УРОВЕНЬ 1. ОБЩЕОПИСАТЕЛЬНАЯ СПРАВОЧНАЯ ИНФОРМАЦИЯ О ПРОГРАММЕ" in recorded["prompt"]
    assert "УРОВЕНЬ 2. АНАЛИЗ ТЕКУЩЕГО ПОТРЕБЛЕНИЯ И СОСТОЯНИЯ РЕСУРСОВ" in recorded["prompt"]

    # Проверяем, что в базе знаний WikiLLM автоматически появилась верифицированная запись!
    engine = get_engine()
    entity = engine.storage.get_entity(f"process:{unique_proc}")
    assert entity is not None
    assert entity.summary == "Интерактивная утилита подсказок и вспомогательных команд для операционной системы Windows."
    assert entity.category == "Системные утилиты"

    # Проверяем, что следующий вызов с cache_only=True мгновенно находит запись в WikiLLM!
    cache_resp = api_client.post("/api/v1/diagnostics/explain", json={
        "table_type": "process",
        "title": f"Помощник системы ({unique_proc}) [PID: 9999]",
        "cache_only": True
    })
    assert cache_resp.status_code == 200
    cdata = cache_resp.json()
    assert cdata["source"] == "wikillm"
    assert cdata["is_verified"] is True
    assert cdata["summary"] == "Интерактивная утилита подсказок и вспомогательных команд для операционной системы Windows."
