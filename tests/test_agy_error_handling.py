# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - AGY Provider Error Handling
# =============================================================================
# Description:
#   Модульные тесты для проверки остановки и возврата ошибки клиенту при сбоях
#   провайдера AGY (Error 503 UNAVAILABLE, WS close code 1006, harness crash).
#
# File: test_agy_error_handling.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 11:27:00
# =============================================================================

"""Тесты обработки и возврата ошибок провайдера AGY."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from src.ai.providers.agy.chat import AgyChatBase
from src.ai.orchestration.model_error_hub import classify_model_error, ModelErrorCategory, get_model_errors
from src.ai.orchestration.model_pool_state import get_pool_status


SAMPLE_503_WS1006_ERROR = (
    "Harness process exited unexpectedly (WS close code 1006).\n"
    "Harness stderr:\n"
    "received model response error: Error 503, Message: This model is currently experiencing high demand. "
    "Spikes in demand are usually temporary. Please try again later., Status: UNAVAILABLE, Details: []\n"
    "ERROR: logging before google.Init: E1015 11:07:24.328408 47 stream_handler.go:107] error encountered while "
    "processing planner output: Error 503, Message: This model is currently experiencing high demand. "
    "Spikes in demand are usually temporary. Please try again later., Status: UNAVAILABLE, Details: []"
)


class TestAgyErrorHandling(unittest.IsolatedAsyncioTestCase):
    """Набор тестов для проверки обработки ошибок провайдера AGY."""

    def setUp(self) -> None:
        """Подготовка окружения перед каждым тестом."""
        self.provider = AgyChatBase(model_id="gemini-3.6-flash")

    def test_classify_503_and_ws_errors(self) -> None:
        """Проверка корректной классификации ошибок 503 UNAVAILABLE и сбоев WebSocket."""
        cat_503, code_503 = classify_model_error(SAMPLE_503_WS1006_ERROR)
        self.assertEqual(cat_503, ModelErrorCategory.SERVICE_UNAVAILABLE)
        self.assertEqual(code_503, 503)

        cat_ws, _ = classify_model_error("Harness process exited unexpectedly (WS close code 1006).")
        self.assertEqual(cat_ws, ModelErrorCategory.CONNECTION_ERROR)

    async def test_handle_agy_error_marks_exhausted_and_returns_exception(self) -> None:
        """Проверка, что _handle_agy_error фиксирует модель как исчерпанную и формирует RuntimeError."""
        raw_exc = Exception(SAMPLE_503_WS1006_ERROR)
        err = self.provider._handle_agy_error(raw_exc)

        self.assertIsInstance(err, RuntimeError)
        self.assertIn("503 UNAVAILABLE / High demand", str(err))
        self.assertIn("Harness process exited", str(err))

        # Проверка фиксации в пуле моделей
        pool_status = get_pool_status("agy")
        models = pool_status.get("models", [])
        target_info = next((m for m in models if m.get("model_name") == self.provider.model_id), None)
        self.assertIsNotNone(target_info)
        self.assertEqual(target_info.get("status"), "exhausted")

    async def test_ask_raises_runtime_error_on_503(self) -> None:
        """Проверка, что метод ask прерывается и выбрасывает исключение с ошибкой."""
        mock_agent = MagicMock()
        mock_agent.chat = AsyncMock(side_effect=Exception(SAMPLE_503_WS1006_ERROR))
        mock_agent.is_started = True

        with patch.object(self.provider, "_get_or_create_agent", AsyncMock(return_value=mock_agent)), \
             patch.object(self.provider, "close", AsyncMock()) as mock_close:
            with self.assertRaises(RuntimeError) as ctx:
                await self.provider.ask("Тестовый запрос")

            self.assertIn("503 UNAVAILABLE", str(ctx.exception))
            mock_close.assert_awaited()

    async def test_chat_stream_raises_runtime_error_and_does_not_yield_chunks(self) -> None:
        """Проверка, что метод chat_stream не выдает текст ошибки как токены, а выбрасывает исключение."""
        mock_agent = MagicMock()
        mock_agent.chat = AsyncMock(side_effect=Exception(SAMPLE_503_WS1006_ERROR))
        mock_agent.is_started = True

        with patch.object(self.provider, "_get_or_create_agent", AsyncMock(return_value=mock_agent)), \
             patch.object(self.provider, "close", AsyncMock()) as mock_close:
            chunks = []
            with self.assertRaises(RuntimeError) as ctx:
                async for chunk in self.provider.chat_stream("Тестовый запрос"):
                    chunks.append(chunk)

            self.assertEqual(len(chunks), 0)
            self.assertIn("503 UNAVAILABLE", str(ctx.exception))
            mock_close.assert_awaited()

    async def test_chat_raises_and_history_is_not_corrupted(self) -> None:
        """Проверка, что метод chat не сохраняет ошибку в историю диалога."""
        mock_agent = MagicMock()
        mock_agent.chat = AsyncMock(side_effect=Exception(SAMPLE_503_WS1006_ERROR))
        mock_agent.is_started = True

        with patch.object(self.provider, "_get_or_create_agent", AsyncMock(return_value=mock_agent)), \
             patch.object(self.provider, "close", AsyncMock()):
            with self.assertRaises(RuntimeError):
                await self.provider.chat("Привет")

            # История диалога не должна содержать сообщение об ошибке
            self.assertEqual(len(self.provider.history), 0)

    async def test_retry_config_has_max_retries_zero(self) -> None:
        """Проверка, что LocalAgentConfig настраивается с max_retries=0 для исключения зависания на ретраях."""
        created_configs = []

        class DummyAgent:
            def __init__(self, config):
                created_configs.append(config)
            async def __aenter__(self):
                return self
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        with patch("google.antigravity.Agent", DummyAgent):
            await self.provider._get_or_create_agent("тестовая инструкция")
            self.assertEqual(len(created_configs), 1)
            cfg = created_configs[0]
            self.assertIsNotNone(cfg.retry_config)
            self.assertEqual(cfg.retry_config.api_retry.max_retries, 0)
            self.assertEqual(cfg.retry_config.model_output_retry.max_retries, 0)
            await self.provider.close()

    async def test_unified_chat_model_raises_on_agy_error(self) -> None:
        """Проверка, что UnifiedChatModel прерывает выполнение и выбрасывает ошибку при сбое agy."""
        from src.ai.orchestration.unified_chat import UnifiedChatModel

        model = UnifiedChatModel(provider="agy", model="gemini-3.6-flash")
        mock_agent = MagicMock()
        mock_agent.chat = AsyncMock(side_effect=Exception(SAMPLE_503_WS1006_ERROR))
        mock_agent.is_started = True

        with patch.object(model.agy_model, "_get_or_create_agent", AsyncMock(return_value=mock_agent)), \
             patch.object(model.agy_model, "close", AsyncMock()):
            with self.assertRaises(RuntimeError) as ctx:
                await model.chat("Тест через UnifiedChatModel")
            self.assertIn("503 UNAVAILABLE", str(ctx.exception))


