# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Diagnostics Developer Advice
# =============================================================================
# Description:
#   Тесты генерации, валидации и сохранения советов разработчику (developer_advice)
#   в универсальном модальном окне ИИ-ассистента и базе знаний WikiLLM.
#
# File: test_diagnostics_developer_advice.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-18 23:53:00
# =============================================================================

from __future__ import annotations

import pytest
from apps.windows.api.diagnostics_prompt_manager import DEFAULT_PROMPTS, prompt_manager
from apps.windows.api.routers.router_diagnostics import (
    DiagnosticExplainResponse,
    _format_json_response_to_dialogue,
)
from apps.windows.wikillm.router import (
    ApproveKnowledgeRequest,
    approve_knowledge,
    get_engine,
)


def test_prompt_templates_contain_developer_advice() -> None:
    """Проверка присутствия поля developer_advice в системных промптах."""
    for key in ("software", "process", "generic", "panel-process-manager-dispetcher-protsessov-i-prilozhen"):
        tmpl = DEFAULT_PROMPTS.get(key)
        assert tmpl is not None, f"Шаблон '{key}' должен быть зарегистрирован"
        assert "developer_advice" in tmpl["prompt_template"], f"В шаблоне '{key}' должно быть поле developer_advice"
        assert "developer_advice" in tmpl["system_instruction"], f"В системной инструкции '{key}' должно быть указание на developer_advice"


def test_diagnostic_explain_response_model() -> None:
    """Проверка структуры модели DiagnosticExplainResponse с полем developer_advice."""
    resp = DiagnosticExplainResponse(
        summary="WinRT Intellisense Desktop - Other Languages",
        developer="Microsoft Corporation",
        category="Системные компоненты",
        security_verdict="Абсолютно легитимное ПО",
        performance_impact="Минимальное",
        recommendation="Оставить",
        action_steps=["Не удалять"],
        developer_advice="WinRT API Intellisense XML схемы. Пример PowerShell:\n```powershell\nGet-AppxPackage *Intellisense*\n```",
    )
    assert resp.developer_advice is not None
    assert "Get-AppxPackage" in resp.developer_advice


def test_format_diagnostic_text_includes_developer_advice() -> None:
    """Проверка, что функция форматирования текстового отчета включает блок советов разработчику."""
    data = {
        "summary": "Тестовый компонент",
        "developer": "Microsoft",
        "category": "SDK",
        "security_verdict": "Безопасно",
        "performance_impact": "Низкое",
        "recommendation": "Оставить",
        "action_steps": ["Шаг 1"],
        "developer_advice": "Используйте Windows SDK Headers и WMI класс Win32_Product.",
    }
    import json
    formatted = _format_json_response_to_dialogue(json.dumps(data, ensure_ascii=False))
    assert "Советы разработчику:" in formatted
    assert "Win32_Product" in formatted


@pytest.mark.asyncio
async def test_wikillm_approve_and_cache_preserves_developer_advice() -> None:
    """Проверка сохранения советов разработчика в WikiLLM и их извлечения."""
    dev_advice_text = (
        "Интерфейс WinRT Windows.ApplicationModel.Resources. "
        "Скрипт автоматизации PowerShell:\n```powershell\nGet-Command -Module Microsoft.PowerShell.Core\n```"
    )
    req = ApproveKnowledgeRequest(
        canonical_key="software:winrt-intellisense-test",
        table_type="software",
        title="WinRT Intellisense Desktop - Test",
        subtitle="Microsoft Corporation",
        summary="Официальный компонент WinRT автодополнения кода",
        category="Разработка",
        security_verdict="Легитимное ПО",
        performance_impact="Низкое",
        recommendation="Оставить",
        action_steps=["Не предпринимать действий по удалению"],
        developer_advice=dev_advice_text,
    )

    result = await approve_knowledge(req)
    assert result["success"] is True

    # Проверяем, что знание сохранилось в storage и claim содержит developer_advice
    engine = get_engine()
    entity = engine.storage.get_entity("software:winrt-intellisense-test")
    assert entity is not None
    found_dev_claim = False
    for claim in entity.claims:
        if "Советы разработчику:" in claim.statement and "Windows.ApplicationModel.Resources" in claim.statement:
            found_dev_claim = True
            break
    assert found_dev_claim, "Советы разработчику должны сохраняться в утверждениях (claims) сущности WikiLLM"

