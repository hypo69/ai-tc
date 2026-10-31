# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry - Buffer Manager
# =============================================================================
# Description:
#   TelemetryBufferManager: Пакетный буферизованный менеджер записи в SQLite / MariaDB.
#   Оптимизирован для снижения IOPS и высокоскоростного сбора системной телеметрии.
#
# Usage Examples:
#   Python API:
#     from apps.windows.telemetry.telemetry_buffer_manager import TelemetryBufferManager
#
#     mgr = TelemetryBufferManager("telemetry.db", batch_size=500, flush_interval=5.0)
#     mgr.add_event("INSERT INTO run_mru_history ...", ("...",))
#
# File: telemetry_buffer_manager.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-12 23:26:00
# =============================================================================

from __future__ import annotations

import asyncio
from collections import deque
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

try:
    from logger import logger
except ImportError:
    import logging
    logger = logging.getLogger("TelemetryBufferManager")


class TelemetryBufferManager:
    """Пакетный менеджер буферизованной записи телеметрии в SQLite с оптимизацией PRAGMA."""

    def __init__(self, db_path: str, batch_size: int = 500, flush_interval: float = 5.0) -> None:
        """Инициализирует менеджер буфера.

        Args:
            db_path: Путь к файлу базы данных SQLite.
            batch_size: Максимальный размер пакета для немедленного сброса.
            flush_interval: Интервал фонового сброса буфера в секундах.
        """
        self.db_path = db_path
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.buffer: deque[Tuple[str, Tuple[Any, ...]]] = deque()
        self.lock = threading.Lock()
        self.running = False

    def optimize_db_pragmas(self, conn: sqlite3.Connection) -> None:
        """Применяет максимальные оптимизации SQLite PRAGMA.

        Args:
            conn: Активное подключение к базе данных SQLite.
        """
        pragmas = [
            "PRAGMA journal_mode = WAL;",
            "PRAGMA synchronous = NORMAL;",
            "PRAGMA mmap_size = 268435456;",  # 256 MB Memory Mapping
            "PRAGMA temp_store = MEMORY;",
            "PRAGMA cache_size = -64000;",     # 64 MB RAM cache
            "PRAGMA foreign_keys = ON;"
        ]
        cursor = conn.cursor()
        for p in pragmas:
            cursor.execute(p)
        conn.commit()

    def add_event(self, query: str, params: Tuple[Any, ...]) -> None:
        """Добавляет запись в память со сложностью O(1).

        Args:
            query: Параметризованный SQL-запрос.
            params: Кортеж параметров для подстановки.
        """
        with self.lock:
            self.buffer.append((query, params))
            if len(self.buffer) >= self.batch_size:
                self.flush_sync()

    def flush_sync(self) -> None:
        """Сбрасывает накопленный буфер в БД единой транзакцией."""
        with self.lock:
            if not self.buffer:
                return
            items_to_write = list(self.buffer)
            self.buffer.clear()

        if not items_to_write:
            return

        try:
            conn = sqlite3.connect(self.db_path, timeout=10.0)
            self.optimize_db_pragmas(conn)
            cursor = conn.cursor()

            grouped: Dict[str, List[Tuple[Any, ...]]] = {}
            for q, p in items_to_write:
                grouped.setdefault(q, []).append(p)

            conn.execute("BEGIN TRANSACTION;")
            for q, params_list in grouped.items():
                cursor.executemany(q, params_list)
            conn.commit()
            conn.close()
            logger.debug(f"[TelemetryBufferManager] Успешно записано {len(items_to_write)} записей.")
        except Exception as e:
            logger.error(f"[TelemetryBufferManager] Ошибка пакетной записи: {e}")

    async def start_async_flusher(self) -> None:
        """Фоновый асинхронный цикл сброса буфера по таймеру."""
        self.running = True
        while self.running:
            await asyncio.sleep(self.flush_interval)
            await asyncio.to_thread(self.flush_sync)

    def stop(self) -> None:
        """Завершение работы и финальный сброс остатков."""
        self.running = False
        self.flush_sync()

