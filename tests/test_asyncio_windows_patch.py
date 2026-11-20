# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Tests - Asyncio Windows Patch Unit Tests
# =============================================================================
# Description:
#   Модульные тесты для проверки подавления ошибки WinError 10054 (ConnectionResetError)
#   в asyncio ProactorEventLoop на платформе Windows.
#
# Usage Examples:
#   CLI:
#     pytest tests/test_asyncio_windows_patch.py -v
#
# File: test_asyncio_windows_patch.py
# Project: ai-tc
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-16 05:38:00
# =============================================================================

from __future__ import annotations
"""Модульные тесты для asyncio_windows_patch."""

import sys
from unittest.mock import MagicMock, patch
import pytest

from src.utils.asyncio_windows_patch import apply_windows_asyncio_patch


def test_apply_windows_asyncio_patch_idempotence() -> None:
    """Проверяет идемпотентность и успешность применения патча на Windows."""
    res1 = apply_windows_asyncio_patch()
    res2 = apply_windows_asyncio_patch()

    if sys.platform == "win32":
        assert res1 is True
        assert res2 is True
    else:
        assert res1 is False
        assert res2 is False


def test_apply_windows_asyncio_patch_non_win32() -> None:
    """Проверяет корректный пропуск патча на платформах отличных от win32."""
    with patch("src.utils.asyncio_windows_patch.sys.platform", "linux"):
        with patch("src.utils.asyncio_windows_patch._PATCH_APPLIED", False):
            result = apply_windows_asyncio_patch()
            assert result is False


def test_patched_connection_lost_handles_reset_error() -> None:
    """Проверяет перехват ConnectionResetError и очистку ресурсов сокета."""
    if sys.platform != "win32":
        pytest.skip("Тест специфичен для Windows ProactorEventLoop")

    from asyncio.proactor_events import _ProactorBasePipeTransport

    # Создаем фиктивный транспорт
    dummy_transport = MagicMock()
    dummy_transport._called_connection_lost = False
    dummy_sock = MagicMock()
    dummy_server = MagicMock()
    dummy_transport._sock = dummy_sock
    dummy_transport._server = dummy_server

    # Эмулируем вызов патченного метода, когда базовый выбрасывает ConnectionResetError
    with patch(
        "asyncio.proactor_events._ProactorBasePipeTransport._call_connection_lost",
        side_effect=ConnectionResetError(10054, "Удаленный хост принудительно разорвал существующее подключение"),
    ):
        with patch("src.utils.asyncio_windows_patch._PATCH_APPLIED", False):
            apply_windows_asyncio_patch()

            # Вызываем пропатченный метод
            _ProactorBasePipeTransport._call_connection_lost(dummy_transport, None)

            # Проверяем, что исключение не всплыло, а ресурсы очищены
            dummy_sock.close.assert_called_once()
            assert dummy_transport._sock is None
            dummy_server._detach.assert_called_once_with(dummy_transport)
            assert dummy_transport._server is None
            assert dummy_transport._called_connection_lost is True
