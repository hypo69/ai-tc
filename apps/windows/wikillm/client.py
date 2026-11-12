# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Wikillm - Client & Batch Cache
# =============================================================================
# Description:
#   Асинхронный клиент WikiLLM с локальным SQLite-кешированием (TTL 24ч),
#   пакетными запросами (bulk_query) и отказоустойчивым fallback.
#
# File: client.py
# Project: ai-windows-admin
# Package: apps.windows.wikillm
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 17:29:00
# =============================================================================

from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Union

try:
    from logger import logger
except ImportError:
    import logging
    logger = logging.getLogger("wikillm_client")

from .engine import WikiLLMEngine
from .extractor import ArtifactExtractor
from .models import (
    ArtifactInput,
    ArtifactType,
    KnowledgeEntity,
    LookupLevel,
    ResolutionResult,
)


class WikiLLMClient:
    """Высокопроизводительный асинхронный клиент для взаимодействия с WikiLLM.

    Обеспечивает локальное кэширование запросов на 24 часа, батчинг
    множественных запросов и защиту от сбоев через локальный fallback.
    """

    def __init__(
        self,
        engine: Optional[WikiLLMEngine] = None,
        cache_db_path: Union[str, Path] = "data/wikillm_cache/queries.db",
        cache_ttl_seconds: int = 86400,
    ) -> None:
        """Инициализирует клиент WikiLLM.

        Args:
            engine: Экземпляр WikiLLMEngine (создается при отсутствии).
            cache_db_path: Путь к файлу кэша запросов SQLite.
            cache_ttl_seconds: Время жизни кэша (по умолчанию 24 часа).
        """
        self._engine = engine
        self.cache_ttl = cache_ttl_seconds
        self.cache_path = Path(cache_db_path) if str(cache_db_path) != ":memory:" else ":memory:"
        self._mem_conn: Optional[sqlite3.Connection] = None
        if self.cache_path == ":memory:":
            self._mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
        self._init_cache_storage()

    def _get_engine(self) -> WikiLLMEngine:
        """Ленивая инициализация движка WikiLLM."""
        if self._engine is None:
            self._engine = WikiLLMEngine()
        return self._engine

    @contextmanager
    def _connect_cache(self) -> Generator[sqlite3.Connection, None, None]:
        """Контекстный менеджер соединения со SQLite базой кэша с гарантированным закрытием."""
        if self._mem_conn is not None:
            try:
                yield self._mem_conn
                self._mem_conn.commit()
            except Exception:
                self._mem_conn.rollback()
                raise
        else:
            conn = sqlite3.connect(str(self.cache_path), timeout=15.0, check_same_thread=False)
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.execute("PRAGMA busy_timeout = 15000")
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def _init_cache_storage(self) -> None:
        """Создает таблицу локального кэша запросов."""
        if isinstance(self.cache_path, Path):
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)

        with self._connect_cache() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS query_cache (
                    query_hash TEXT PRIMARY KEY,
                    query_text TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
                """
            )

    def _hash_query(self, query: str) -> str:
        """Вычисляет хэш SHA-256 для строки запроса."""
        return hashlib.sha256(query.strip().lower().encode("utf-8")).hexdigest()

    def _get_cached(self, query: str) -> Optional[ResolutionResult]:
        """Возвращает результат из локального кэша, если срок TTL не истек."""
        q_hash = self._hash_query(query)
        try:
            with self._connect_cache() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT result_json, created_at FROM query_cache WHERE query_hash = ?",
                    (q_hash,),
                )
                row = cursor.fetchone()

            if row:
                res_json, created_at = row
                if time.time() - created_at < self.cache_ttl:
                    data = json.loads(res_json)
                    return ResolutionResult(**data)
        except Exception as err:
            logger.debug(f"[WikiLLMClient] Ошибка чтения кэша: {err}")
        return None

    def _save_cache(self, query: str, result: ResolutionResult) -> None:
        """Сохраняет разрешенный артефакт в локальный SQLite-кэш."""
        q_hash = self._hash_query(query)
        try:
            serialized = (
                result.model_dump_json()
                if hasattr(result, "model_dump_json")
                else result.json()
            )
            with self._connect_cache() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO query_cache (query_hash, query_text, result_json, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (q_hash, query, serialized, time.time()),
                )
        except Exception as err:
            logger.debug(f"[WikiLLMClient] Ошибка сохранения в кэш: {err}")

    async def resolve(
        self,
        query: str,
        artifact: Optional[ArtifactInput] = None,
        use_cache: bool = True,
    ) -> ResolutionResult:
        """Асинхронно разрешает запрос через кэш или движок WikiLLM.

        Args:
            query: Текстовый запрос или код ошибки.
            artifact: Типизированный объект артефакта (опционально).
            use_cache: Использовать ли локальный SQLite кэш.

        Returns:
            Экземпляр ResolutionResult с найденной сущностью.
        """
        if use_cache:
            cached_res = await asyncio.to_thread(self._get_cached, query)
            if cached_res:
                cached_res.cached = True
                return cached_res

        art = artifact
        if art is None:
            extracted = ArtifactExtractor.from_raw_text(query)
            art = extracted[0] if extracted else ArtifactInput(raw_query=query)

        engine = self._get_engine()
        try:
            res = await engine.resolve(art)
            if use_cache:
                await asyncio.to_thread(self._save_cache, query, res)
            return res
        except Exception as exc:
            logger.warning(f"[WikiLLMClient] Ошибка разрешения '{query}': {exc}. Применяем fallback.")
            fallback_res = ResolutionResult(
                canonical_key=f"fallback:{self._hash_query(query)[:8]}",
                lookup_level=LookupLevel.EXACT,
                cached=False,
                entity=KnowledgeEntity(
                    canonical_key=f"fallback:{self._hash_query(query)[:8]}",
                    entity_type=ArtifactType.GENERIC,
                    name=query[:64],
                    summary="Локальный fallback для неизвестного артефакта",
                    category="general",
                    severity="info",
                ),
            )
            if use_cache:
                await asyncio.to_thread(self._save_cache, query, fallback_res)
            return fallback_res

    async def bulk_query(
        self,
        queries: List[str],
        use_cache: bool = True,
    ) -> List[ResolutionResult]:
        """Пакетное (батчированное) параллельное разрешение списка запросов.

        Args:
            queries: Список поисковых строк.
            use_cache: Использовать ли кэширование.

        Returns:
            Список ResolutionResult в порядке исходных запросов.
        """
        sem = asyncio.Semaphore(8)

        async def _bounded_resolve(q: str) -> ResolutionResult:
            async with sem:
                return await self.resolve(q, use_cache=use_cache)

        tasks = [_bounded_resolve(q) for q in queries]
        return await asyncio.gather(*tasks)

    def resolve_sync(self, query: str) -> ResolutionResult:
        """Синхронная обертка над resolve для консольных скриптов."""
        return asyncio.run(self.resolve(query))

