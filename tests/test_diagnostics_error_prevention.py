# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Diagnostics Error Prevention
# =============================================================================
# Description:
#   Тесты предотвращения сохранения ошибок языковых моделей и потоковых сбоев
#   в локальную базу знаний WikiLLM при автообогащении и интерактивном диалоге.
#
# File: test_diagnostics_error_prevention.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-18 23:05:00
# =============================================================================

from __future__ import annotations

import pytest
from fastapi import HTTPException
from apps.windows.api.routers.router_diagnostics import (
    DiagnosticExecuteCommandRequest,
    _enrich_wikillm_qa,
    _is_model_error,
    _is_stream_chunk_error,
    init_router,
)
from apps.windows.sdk.modules.backup_manager.core.file_history_manager import FileHistoryManager
from apps.windows.wikillm.router import (
    ApproveKnowledgeRequest,
    approve_knowledge,
)


def test_is_model_error_detection() -> None:
    """Проверка корректности обнаружения различных типов ошибок модели и провайдера."""
    # Ошибки стриминга и провайдеров
    assert _is_model_error("Streaming error: 503 Service Unavailable. {'message': 'error'}")
    assert _is_model_error("Model error: 429 ResourceExhausted: Quota exceeded")
    assert _is_model_error("Error: Все API ключи исчерпаны.")
    assert _is_model_error('{"error": {"code": 503, "message": "This model is currently experiencing high demand."}}')
    assert _is_model_error("Service Unavailable")
    assert _is_model_error("503 Service Unavailable")
    assert _is_model_error("Harness process exited unexpectedly")

    # Слишком короткие или пустые ответы
    assert _is_model_error("")
    assert _is_model_error("   ")
    assert _is_model_error("Короткий текст")
    assert _is_model_error(None)

    # Валидный экспертный ответ модели не должен определяться как ошибка
    valid_answer = (
        "Программа Wireshark является легитимным сетевым анализатором пакетов. "
        "Риски стабильности минимальны, так как фоновые службы по умолчанию не активны."
    )
    assert not _is_model_error(valid_answer)


def test_enrich_wikillm_rejects_model_errors() -> None:
    """Проверка, что _enrich_wikillm_qa гарантированно отклоняет сообщения об ошибках."""
    # Ошибка со стриминга 503 (как на скриншоте пользователя)
    stream_err = (
        "Streaming error: 503 Service Unavailable. "
        "{'message': '{\\n  \"error\": {\\n    \"code\": 503,\\n    \"message\": \"This model is currently experiencing high demand.\",\\n    \"status\": \"UNAVAILABLE\"\\n  }\\n}\\n', 'status': 'Service Unavailable'}"
    )
    result = _enrich_wikillm_qa(
        canonical_key="software:test-error-app",
        table_type="software",
        title="Test App",
        subtitle="C:\\Program Files\\Test\\app.exe",
        question="Каковы риски стабильности?",
        answer=stream_err,
        model_name="gemini-3.1-flash-lite",
    )
    assert result is False, "Ошибка стриминга не должна записываться в WikiLLM"

    # Ошибка исчерпания ключей
    exhausted_err = "Error: Все API ключи исчерпаны.\n[DEV Детали по ключам]:\n- GEMINI_API_KEY_1: 429 Quota exceeded"
    result_ex = _enrich_wikillm_qa(
        canonical_key="software:test-error-app",
        table_type="software",
        title="Test App",
        subtitle="C:\\Program Files\\Test\\app.exe",
        question="Безопасно ли отключить?",
        answer=exhausted_err,
        model_name="gemini",
    )
    assert result_ex is False, "Сообщение об исчерпании ключей не должно записываться в WikiLLM"


@pytest.mark.asyncio
async def test_approve_endpoint_rejects_model_errors() -> None:
    """Проверка, что эндпоинт /approve блокирует сохранение ошибок с кодом HTTP 400."""
    stream_err = (
        "Streaming error: 503 Service Unavailable. "
        "This model is currently experiencing high demand."
    )
    req = ApproveKnowledgeRequest(
        canonical_key="software:test-app",
        table_type="software",
        title="Test App",
        summary=stream_err,
        recommendation="Повторить позже",
    )
    with pytest.raises(HTTPException) as exc_info:
        await approve_knowledge(req)

    assert exc_info.value.status_code == 400
    assert "Нельзя зафиксировать в базе знаний WikiLLM сообщение об ошибке" in exc_info.value.detail


def test_is_stream_chunk_error_does_not_reject_valid_tokens() -> None:
    """Проверка, что короткие валидные токены стрима (например, '### Анали') не блокируются."""
    assert not _is_stream_chunk_error("### Анали")
    assert not _is_stream_chunk_error("з процесса:")
    assert not _is_stream_chunk_error("Да")
    assert not _is_stream_chunk_error("1. Рекомендация")
    assert not _is_stream_chunk_error(None)
    assert not _is_stream_chunk_error("")

    # Настоящие ошибки должны блокироваться
    assert _is_stream_chunk_error("Streaming error: 503 Service Unavailable")
    assert _is_stream_chunk_error("Model error: Quota exceeded")
    assert _is_stream_chunk_error("ResourceExhausted: 429 Too many requests")
    assert _is_stream_chunk_error("Все API ключи исчерпаны")
    assert _is_stream_chunk_error('{"error": {"code": 503, "message": "Service Unavailable"}}')


def test_file_history_manager_service_status_handles_oem_encoding() -> None:
    """Проверка, что опрос sc.exe для службы fhsvc не падает с UnicodeDecodeError."""
    manager = FileHistoryManager()
    state, start_type = manager.get_service_status()
    assert state is not None
    assert isinstance(start_type, str)
    assert start_type != ""


@pytest.mark.asyncio
async def test_diagnostic_execute_powershell_endpoint() -> None:
    """Проверка эндпоинта выполнения команд PowerShell из модального окна AI."""
    router = init_router()

    # Находим обработчик маршрута /execute-powershell
    handler = None
    for route in router.routes:
        if getattr(route, "path", None) == "/api/v1/diagnostics/execute-powershell":
            handler = route.endpoint
            break

    assert handler is not None, "Эндпоинт /execute-powershell должен быть зарегистрирован"

    # 1. Успешное выполнение команды
    req = DiagnosticExecuteCommandRequest(command="Write-Output 'AI Admin Test'")
    resp = await handler(req)
    assert resp.success is True
    assert resp.returncode == 0
    assert "AI Admin Test" in resp.stdout
    assert resp.execution_time_ms >= 0

    # 2. Обработка ошибки выполнения команды с ненулевым кодом выхода
    req_err = DiagnosticExecuteCommandRequest(command="throw 'Test Error from PowerShell'")
    resp_err = await handler(req_err)
    assert resp_err.success is False
    assert resp_err.returncode != 0
    assert "Test Error from PowerShell" in resp_err.stderr

    # 3. Успешное выполнение команды через cmd.exe
    req_cmd = DiagnosticExecuteCommandRequest(command="echo CMD Test Output", shell="cmd")
    resp_cmd = await handler(req_cmd)
    assert resp_cmd.success is True
    assert resp_cmd.returncode == 0
    assert "CMD Test Output" in resp_cmd.stdout

    # 4. Валидация пустой команды
    with pytest.raises(HTTPException) as exc_info:
        await handler(DiagnosticExecuteCommandRequest(command="   "))
    assert exc_info.value.status_code == 400


