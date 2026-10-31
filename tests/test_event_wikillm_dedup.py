# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Event WikiLLM Deduplication
# =============================================================================
# Description:
#   Тестирование дедупликации одинаковых событий аудита Windows (Event ID 4624),
#   нормализации канонических ключей и кэширования в WikiLLM.
#
# File: test_event_wikillm_dedup.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-20 19:50:00
# =============================================================================

"""Тесты дедупликации событий аудита безопасности в WikiLLM."""

import pytest
from apps.windows.wikillm.normalizer import CanonicalKeyNormalizer
from apps.windows.api.routers.router_diagnostics import (
    DiagnosticExplainRequest,
    DiagnosticSuggestQuestionsRequest,
    init_router,
    _QUESTIONS_CACHE,
)
from fastapi.testclient import TestClient


def test_event_logon_key_normalization() -> None:
    """Проверка сведения различных записей Event ID 4624 с динамическими таймстемпами к единому ключу."""
    events = [
        "2026-10-20 13:19:51\t4624\tSuccessful Logon\tSYSTEM\tDELL-VOSTRO$\tSubjectUserSid: S-1-5-18 | SubjectUserName: DELL-VOSTRO$ | SubjectDomainName: WORKGROUP | SubjectLogonId: 0x3e7 | TargetUserSid: S-1-5-18 | TargetUser",
        "2026-10-20 13:19:45\t4624\tSuccessful Logon\tSYSTEM\tDELL-VOSTRO$\tSubjectUserSid: S-1-5-18 | SubjectUserName: DELL-VOSTRO$ | SubjectDomainName: WORKGROUP | SubjectLogonId: 0x3e7 | TargetUserSid: S-1-5-18 | TargetUser",
        "2026-10-20 13:06:01\t4624\tSuccessful Logon\tSYSTEM\tDELL-VOSTRO$",
        "2026-10-20 12:16:23\t4624\tSuccessful Logon\tSYSTEM\tDELL-VOSTRO$",
        "Событие аудита: #4624 - Successful Logon",
        "4624 Successful Logon",
    ]

    keys = [CanonicalKeyNormalizer.compute_key_from_parts("security_event", ev) for ev in events]
    # Все должны свестись к стабильному каноническому ключу
    assert all(k == "security_event:4624_-_successful_logon" for k in keys)


@pytest.mark.asyncio
async def test_explain_4624_cache_hit_without_model() -> None:
    """Проверка мгновенного ответа из WikiLLM для событий 4624 без обращения к модели."""
    from apps.windows.wikillm.router import get_engine
    engine = get_engine()
    entity = engine.storage.get_entity("security_event:4624_-_successful_logon")
    assert entity is not None, "Сущность security_event:4624_-_successful_logon должна присутствовать в базе знаний"

    router = init_router()
    # Тестируем вызов explain для события с таймстемпом
    req = DiagnosticExplainRequest(
        table_type="security_event",
        panel_id="panel-winadmin-audit",
        title="2026-10-20 13:19:51\t4624\tSuccessful Logon\tSYSTEM\tDELL-VOSTRO$",
        subtitle="Время: 2026-10-20 13:19:51 | Целевой аккаунт: SYSTEM",
        cache_only=True,
    )
    # Находим endpoint explain
    for route in router.routes:
        if route.path == "/api/v1/diagnostics/explain" and "POST" in route.methods:
            explain_func = route.endpoint
            res = await explain_func(req)
            assert res.source == "wikillm"
            assert res.is_verified is True
            assert "SYSTEM" in res.summary
            assert res.canonical_key == "security_event:4624_-_successful_logon"
            break


@pytest.mark.asyncio
async def test_quick_questions_caching() -> None:
    """Проверка кэширования быстрых вопросов для предотвращения повторных обращений к LLM."""
    router = init_router()
    key = "security_event:4624_-_successful_logon"
    _QUESTIONS_CACHE[key] = ["Вопрос 1", "Вопрос 2", "Вопрос 3"]

    req = DiagnosticSuggestQuestionsRequest(
        table_type="security_event",
        panel_id="panel-winadmin-audit",
        title="2026-10-20 13:19:45\t4624\tSuccessful Logon\tSYSTEM\tDELL-VOSTRO$",
        subtitle="Целевой аккаунт: SYSTEM",
    )

    for route in router.routes:
        if route.path == "/api/v1/diagnostics/quick-questions" and "POST" in route.methods:
            qq_func = route.endpoint
            res = await qq_func(req)
            assert res.source == "wikillm_cache"
            assert res.questions == ["Вопрос 1", "Вопрос 2", "Вопрос 3"]
            assert res.canonical_key == key
            break

