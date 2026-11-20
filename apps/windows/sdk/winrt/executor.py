# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Apps Windows SDK WinRT - Executor
# =============================================================================
# Description:
#   Исполнительный движок взаимодействия с WinRT API через изолированный мост.
#   Обеспечивает неблокирующий асинхронный вызов, кэширование с TTL,
#   таймауты (Fail-Fast) и десериализацию JSON-ответов.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.winrt.executor import WinRTExecutor
#
#     executor = WinRTExecutor()
#     data = await executor.execute_script_async(script_text)
#
# File: executor.py
# Project: ai-tc
# Package: apps.windows.sdk.winrt
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-16 05:40:00
# =============================================================================

from __future__ import annotations
"""Исполнительный движок неблокирующего взаимодействия с WinRT API."""

import asyncio
import json
import os
import subprocess
import time
from typing import Any, Dict, Optional
from logger import logger


class WinRTExecutor:
    """Исполнитель скриптов WinRT с защитой Event Loop, таймаутами и TTL-кэшем."""

    def __init__(self, default_timeout_sec: float = 6.0) -> None:
        """Инициализация исполнителя WinRT.

        Args:
            default_timeout_sec: Таймаут выполнения операции по умолчанию (в секундах).
        """
        self.default_timeout_sec = default_timeout_sec
        self._cache: Dict[str, tuple[float, Any]] = {}

    def is_winrt_supported(self) -> bool:
        """Проверка поддержки Windows Runtime на текущей машине."""
        if os.name != 'nt':
            return False
        return True

    def execute_script_sync(
        self,
        script: str,
        timeout_sec: Optional[float] = None,
        cache_key: Optional[str] = None,
        cache_ttl_sec: float = 0.0,
    ) -> Dict[str, Any]:
        """Синхронное выполнение скрипта WinRT с таймаутом и кэшированием.

        Args:
            script: Код PowerShell для доступа к типам WinRT.
            timeout_sec: Максимальное время ожидания ответа.
            cache_key: Ключ для сохранения результата в TTL-кэше.
            cache_ttl_sec: Время жизни кэша в секундах.

        Returns:
            Десериализованный словарь с результатом или словарь с ошибкой.
        """
        now = time.time()
        if cache_key and cache_key in self._cache:
            cached_time, cached_val = self._cache[cache_key]
            if now - cached_time < cache_ttl_sec:
                return cached_val

        if not self.is_winrt_supported():
            return {"error": "WinRT не поддерживается на данной операционной системе"}

        timeout = timeout_sec or self.default_timeout_sec
        cmd = [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ]

        try:
            completed = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            stdout = completed.stdout.strip()
            if not stdout:
                if completed.returncode != 0:
                    err = completed.stderr.strip() or f"Код возврата {completed.returncode}"
                    logger.debug(f"[WinRTExecutor] Ошибка выполнения: {err}")
                    return {"error": err}
                return {}

            # Ищем границы JSON в выводе (если попал предупреждающий текст)
            idx_start = stdout.find("{")
            idx_end = stdout.rfind("}")
            if idx_start != -1 and idx_end != -1 and idx_end >= idx_start:
                json_str = stdout[idx_start : idx_end + 1]
                data = json.loads(json_str)
            else:
                data = {"raw_output": stdout}

            if cache_key and cache_ttl_sec > 0:
                self._cache[cache_key] = (now, data)
            return data

        except subprocess.TimeoutExpired:
            logger.warning(f"[WinRTExecutor] Превышен таймаут {timeout}с при вызове WinRT API")
            return {"error": f"Превышен таймаут {timeout}с"}
        except Exception as e:
            logger.debug(f"[WinRTExecutor] Исключение при выполнении WinRT скрипта: {e}")
            return {"error": str(e)}

    async def execute_script_async(
        self,
        script: str,
        timeout_sec: Optional[float] = None,
        cache_key: Optional[str] = None,
        cache_ttl_sec: float = 0.0,
    ) -> Dict[str, Any]:
        """Неблокирующий асинхронный вызов WinRT через пул потоков asyncio.

        Args:
            script: Код PowerShell для доступа к типам WinRT.
            timeout_sec: Максимальное время ожидания ответа.
            cache_key: Ключ для сохранения результата в TTL-кэше.
            cache_ttl_sec: Время жизни кэша в секундах.

        Returns:
            Десериализованный словарь с результатом или словарь с ошибкой.
        """
        return await asyncio.to_thread(
            self.execute_script_sync,
            script,
            timeout_sec,
            cache_key,
            cache_ttl_sec,
        )
