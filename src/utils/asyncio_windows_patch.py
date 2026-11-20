# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc UTILS - Windows Asyncio Proactor Connection Reset Patch
# =============================================================================
# Description:
#   Устранение известного артефакта ProactorEventLoop в Python на платформе Windows
#   (CPython issue #83413 / ConnectionResetError WinError 10054).
#   Подавляет шум в логах при принудительном сбросе сокета удалённым клиентом
#   (_call_connection_lost) и корректно освобождает дескрипторы сокетов.
#
# Usage Examples:
#   Python API:
#     from src.utils.asyncio_windows_patch import apply_windows_asyncio_patch
#
#     apply_windows_asyncio_patch()
#
# File: asyncio_windows_patch.py
# Project: ai-tc
# Package: src.utils
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-16 05:37:00
# =============================================================================

from __future__ import annotations
"""Модуль подавления артефакта WinError 10054 в asyncio на Windows."""

import sys
from typing import Any, Optional

from logger import logger

_PATCH_APPLIED: bool = False


def apply_windows_asyncio_patch() -> bool:
    """Применяет патч к ProactorEventLoop для подавления WinError 10054.

    На платформе Windows при резком закрытии клиентом HTTP-соединения
    (например, закрытие вкладки, отмена запроса через AbortController),
    вызов _sock.shutdown(socket.SHUT_RDWR) в _call_connection_lost вызывает
    ConnectionResetError: [WinError 10054]. Данная функция перехватывает
    это исключение, предотвращает появление ложного ERROR в логах
    и гарантирует закрытие дескриптора сокета.

    Returns:
        bool: True, если патч успешно применён или уже был применён,
              False, если ОС не Windows или произошла ошибка.
    """
    global _PATCH_APPLIED
    if _PATCH_APPLIED:
        return True

    if sys.platform != "win32":
        return False

    try:
        from asyncio.proactor_events import _ProactorBasePipeTransport

        orig_call_connection_lost = _ProactorBasePipeTransport._call_connection_lost

        def _patched_call_connection_lost(self: Any, exc: Optional[BaseException] = None) -> None:
            """Обертка для безопасного закрытия сокета без выброса WinError 10054."""
            try:
                orig_call_connection_lost(self, exc)
            except (ConnectionResetError, OSError):
                # Если сокет был сброшен клиентом (RST), гарантируем очистку ресурсов
                sock = getattr(self, "_sock", None)
                if sock is not None:
                    try:
                        sock.close()
                    except Exception:
                        pass
                    self._sock = None

                server = getattr(self, "_server", None)
                if server is not None:
                    try:
                        server._detach(self)
                    except Exception:
                        pass
                    self._server = None

                self._called_connection_lost = True

        _ProactorBasePipeTransport._call_connection_lost = _patched_call_connection_lost
        _PATCH_APPLIED = True
        logger.debug("[System Resilience] Патч Windows asyncio WinError 10054 успешно активирован.")
        return True
    except Exception as exc:
        logger.warning(f"[System Resilience] Не удалось применить патч asyncio WinError 10054: {exc}")
        return False
