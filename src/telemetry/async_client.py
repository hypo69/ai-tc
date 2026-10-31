# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Telemetry - Async Batch Client
# =============================================================================
# Description:
#   Асинхронный клиент сбора и отправки телеметрии с дельта-фильтрацией
#   (только ключевые и изменившиеся метрики), периодической батч-отправкой
#   и консольным выводом через logger.console().
#
# File: async_client.py
# Project: ai-windows-admin
# Package: src.telemetry
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-13 20:45:00
# =============================================================================

from __future__ import annotations

import asyncio
import time
from typing import Any, Callable, Dict, List, Optional

try:
    from logger import logger
except ImportError:
    import logging
    logger = logging.getLogger("async_telemetry")


class AsyncTelemetryBatchClient:
    """Асинхронный клиент для сбора и отправки телеметрии с батчингом и дельта-сжатием.

    Уменьшает объем передаваемых данных за счет фильтрации неизменных метрик
    и группировки пакетов с отправкой раз в 30 секунд или по достижению лимита.
    """

    KEY_METRICS = {"cpu_percent", "gpu_percent", "memory_used_mb", "disk_free_gb", "errors_count"}

    def __init__(
        self,
        batch_interval_seconds: float = 30.0,
        max_batch_size: int = 50,
        sink_callback: Optional[Callable[[List[Dict[str, Any]]], Any]] = None,
    ) -> None:
        """Инициализирует асинхронный батч-клиент телеметрии.

        Args:
            batch_interval_seconds: Интервал сброса буфера (по умолчанию 30 сек).
            max_batch_size: Максимальный размер пакета перед принудительным сбросом.
            sink_callback: Коллбэк-приемник отправляемых пакетов.
        """
        self.interval = batch_interval_seconds
        self.max_batch_size = max_batch_size
        self.sink = sink_callback
        self._buffer: List[Dict[str, Any]] = []
        self._last_metrics: Dict[str, Any] = {}
        self._lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None
        self._running = False

    def filter_delta_metrics(self, current_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Фильтрует метрики, оставляя только изменившиеся или критически важные.

        Args:
            current_metrics: Текущий срез системных метрик.

        Returns:
            Отфильтрованный сжатый словарь метрик.
        """
        delta = {}
        for key, val in current_metrics.items():
            # Ключевые метрики включаем всегда
            if key in self.KEY_METRICS:
                delta[key] = val
                continue
            # Для остальных метрик фиксируем только изменения
            if key not in self._last_metrics or self._last_metrics[key] != val:
                delta[key] = val

        self._last_metrics.update(current_metrics)
        return delta

    async def enqueue_metrics(self, raw_metrics: Dict[str, Any]) -> None:
        """Добавляет метрики в очередь с дельта-фильтрацией.

        Args:
            raw_metrics: Сырой срез системных показателей.
        """
        filtered = self.filter_delta_metrics(raw_metrics)
        if not filtered:
            return

        payload = {
            "timestamp": time.time(),
            "metrics": filtered,
        }

        async with self._lock:
            self._buffer.append(payload)
            should_flush = len(self._buffer) >= self.max_batch_size

        if should_flush:
            await self.flush()

    async def flush(self) -> List[Dict[str, Any]]:
        """Принудительно сбрасывает накопленный буфер метрик.

        Returns:
            Список отправленных пакетов метрик.
        """
        async with self._lock:
            if not self._buffer:
                return []
            batch_to_send = list(self._buffer)
            self._buffer.clear()

        if self.sink:
            try:
                res = self.sink(batch_to_send)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as err:
                if hasattr(logger, "console"):
                    logger.console(f"⚠️ [Telemetry Batch] Ошибка отправки пакета: {err}")
                else:
                    logger.error(f"[Telemetry Batch] Ошибка отправки пакета: {err}")

        return batch_to_send

    async def start_periodic_worker(self) -> None:
        """Запускает фоновую задачу циклического сброса буфера раз в 30 секунд."""
        self._running = True
        while self._running:
            await asyncio.sleep(self.interval)
            await self.flush()

    def stop_worker(self) -> None:
        """Останавливает циклический рабочий процесс."""
        self._running = False
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()

