# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Model Manager Provider Status Check
# =============================================================================
# Description:
#   Тесты механизма проверки активности провайдеров (is_provider_enabled)
#   в модуле ModelManager и предотвращения сетевых обращений к неактивным сервисам.
#
# File: test_model_manager_provider_status.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 16:48:00
# =============================================================================

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from src.ai.orchestration.model_manager import (
    actualize_all_models,
    get_available_models,
    is_provider_enabled,
)
from src.config import is_provider_enabled as config_is_provider_enabled


def test_is_provider_enabled_matches_config() -> None:
    """Проверяет соответствие статуса активности провайдеров текущей конфигурации."""
    # Согласно config.json, foundry и ollama отключены (enabled: false)
    assert not is_provider_enabled("foundry"), "Foundry должен быть отключен согласно config.json"
    assert not is_provider_enabled("ollama"), "Ollama должна быть отключена согласно config.json"
    assert is_provider_enabled("gemini"), "Gemini должен быть активен согласно config.json"

    # Проверка через функцию src.config
    assert not config_is_provider_enabled("foundry")
    assert not config_is_provider_enabled("ollama")
    assert config_is_provider_enabled("gemini")


def test_get_available_models_skips_network_for_disabled_providers() -> None:
    """Проверяет, что для отключенных провайдеров не выполняются сетевые HTTP-запросы."""
    with patch("requests.get") as mock_get:
        # Для неактивного foundry
        foundry_models = get_available_models("foundry", force_refresh=True)
        assert foundry_models == [], "Отключенный провайдер должен возвращать пустой список моделей"

        # Для неактивного ollama
        ollama_models = get_available_models("ollama", force_refresh=True)
        assert ollama_models == [], "Отключенный провайдер должен возвращать пустой список моделей"

        # Убеждаемся, что сетевые запросы к отключенным серверам вообще не вызывались
        mock_get.assert_not_called()


@pytest.mark.asyncio
async def test_actualize_all_models_skips_disabled_providers() -> None:
    """Проверяет, что фоновая актуализация пропускает отключенных провайдеров без сетевых вызовов."""
    with patch("requests.get") as mock_get:
        pool = await actualize_all_models(force_refresh=True)
        assert isinstance(pool, dict)
        assert "foundry" in pool
        assert pool["foundry"] == []
        assert "ollama" in pool
        assert pool["ollama"] == []
        mock_get.assert_not_called()

