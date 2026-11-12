# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin AI - Adaptive Log RAG
# =============================================================================
# Description:
#   Адаптивный RAG-движок для структурирования, семантического поиска
#   и профилирования системных журналов и событий ОС с интеграцией в WikiLLM.
#
# Usage Examples:
#   Python API:
#     from src.ai.rag.log_rag import LogRAG
#
#     log_rag = LogRAG()
#     results = log_rag.search_chunks(query="DistributedCOM 10016", top_k=5)
#
# File: log_rag.py
# Project: ai-windows-admin
# Package: src.ai.rag
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 18:12:00
# =============================================================================

from __future__ import annotations
"""Адаптивный RAG-движок для журналов событий и интеграции с WikiLLM."""

import collections
import datetime
import hashlib
import json
import math
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from logger import logger
try:
    from apps.windows.wikillm.models import (
        ArtifactType,
        Claim,
        DiagnosticKnowledge,
        KnowledgeEntity,
        KnowledgeSource,
        ResolutionAction,
    )
    from apps.windows.wikillm.storage import WikiStorage
except ImportError:
    from src.ai.wikillm.models import (
        ArtifactType,
        Claim,
        DiagnosticKnowledge,
        KnowledgeEntity,
        KnowledgeSource,
        ResolutionAction,
    )
    from src.ai.wikillm.storage import WikiStorage

_WORD_RE = re.compile(r"\w+")


class LogRAG:
    """Адаптивный RAG-движок для системных логов Windows и диагностических записей.

    Attributes:
        storage_dir: Путь к директории хранения чанков и кэша.
        wiki_storage: Экземпляр хранилища WikiStorage для базы знаний.
    """

    def __init__(
        self,
        storage_dir: Optional[Path] = False,
        max_chunks: int = 2000,
    ) -> None:
        """Инициализирует LogRAG.

        Args:
            storage_dir: Директория хранения индекса.
            max_chunks: Максимальное количество чанков в памяти.
        """
        self.storage_dir = Path(storage_dir) if storage_dir else Path("data/rag/logs_storage")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.max_chunks = max_chunks
        self.chunks: List[Dict[str, Any]] = []

        # Интеграция с базой знаний WikiLLM
        wiki_db_path = self.storage_dir / "wikillm_logs.db"
        self.wiki_storage = WikiStorage(db_path=str(wiki_db_path))
        self._load()

    def _get_chunks_file(self) -> Path:
        return self.storage_dir / "adaptive_log_chunks.json"

    def _load(self) -> None:
        """Загрузка сохраненных чанков логов."""
        c_file = self._get_chunks_file()
        if c_file.exists():
            try:
                with open(c_file, "r", encoding="utf-8") as f:
                    self.chunks = json.load(f)
            except Exception as e:
                logger.error(f"[LogRAG] Ошибка загрузки чанков: {e}")
                self.chunks = []
        else:
            self.chunks = []

    def _save(self) -> None:
        """Атомарное сохранение чанков логов на диск через временный файл."""
        c_file = self._get_chunks_file()
        tmp_file = c_file.with_suffix(".json.tmp")
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(self.chunks[-self.max_chunks :], f, ensure_ascii=False, indent=2)
            os.replace(tmp_file, c_file)
        except Exception as e:
            logger.error(f"[LogRAG] Ошибка сохранения чанков: {e}")
            if tmp_file.exists():
                try:
                    tmp_file.unlink()
                except OSError:
                    pass

    def add_log_chunk(
        self,
        chunk_id: str,
        title: str,
        content: str,
        channel: str = "System",
        provider: str = "",
        event_ids: Optional[List[int]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Добавляет чанк логов в адаптивный индекс и связывает с WikiLLM.

        Args:
            chunk_id: Уникальный идентификатор чанка.
            title: Заголовок фрагмента лога.
            content: Текстовое содержимое лога.
            channel: Канал журнала.
            provider: Источник события.
            event_ids: Список Event ID в данном чанке.
            metadata: Дополнительные метаданные.

        Returns:
            Словарь добавленного чанка.
        """
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        chunk_entry = {
            "id": chunk_id,
            "title": title,
            "content": content,
            "channel": channel,
            "provider": provider,
            "event_ids": event_ids or [],
            "metadata": metadata or {},
            "created_at": now_str,
        }

        # Обновляем или добавляем в список чанков
        existing = next((c for c in self.chunks if c["id"] == chunk_id), None)
        if existing:
            self.chunks.remove(existing)
        self.chunks.append(chunk_entry)
        self._save()

        # Автоматическая связка с WikiLLM SQLite сущностью при наличии Event ID
        if event_ids and provider:
            for eid in event_ids:
                can_key = f"windows_event:{provider}:{eid}"
                ent = self.wiki_storage.get_entity(can_key)
                if not ent:
                    new_ent = KnowledgeEntity(
                        canonical_key=can_key,
                        entity_type=ArtifactType.WINDOWS_EVENT,
                        name=f"Событие {provider} ID {eid}",
                        summary=f"Системное событие из журнала {channel}: {title}",
                        provenance_source=KnowledgeSource.OBSERVED,
                        diagnostic_info=DiagnosticKnowledge(
                            event_id=eid,
                            source_provider=provider,
                            symptoms=[title],
                        ),
                    )
                    self.wiki_storage.save_entity(new_ent)

        return chunk_entry

    def search_chunks(
        self,
        query: str,
        channel: str = "",
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Семантический и ключевой поиск по чанкам логов с TF-IDF ранжированием.

        Args:
            query: Поисковый запрос.
            channel: Фильтр по каналу журнала.
            top_k: Максимальное количество результатов.

        Returns:
            Список наиболее релевантных чанков логов.
        """
        if not self.chunks or not query.strip():
            return []

        q_terms = [t.lower() for t in _WORD_RE.findall(query)]
        if not q_terms:
            return []

        doc_count = len(self.chunks)
        df: collections.Counter[str] = collections.Counter()
        for chunk in self.chunks:
            words = set(_WORD_RE.findall(f"{chunk.get('title', '')} {chunk.get('content', '')}".lower()))
            for term in q_terms:
                if term in words:
                    df[term] += 1

        scored: List[Tuple[float, Dict[str, Any]]] = []
        for chunk in self.chunks:
            if channel and chunk.get("channel", "").lower() != channel.lower():
                continue

            text = f"{chunk.get('title', '')} {chunk.get('content', '')} {chunk.get('provider', '')}".lower()
            tokens = _WORD_RE.findall(text)
            if not tokens:
                continue

            tf = collections.Counter(tokens)
            doc_len = len(tokens)
            score = 0.0

            for term in q_terms:
                count = tf[term]
                if count > 0:
                    idf = math.log((doc_count + 1) / (df[term] + 1)) + 1.0
                    tf_norm = count / doc_len
                    score += tf_norm * idf

            if score > 0:
                scored.append((score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        results: List[Dict[str, Any]] = []
        for s, c in scored[:top_k]:
            item = dict(c)
            item["score"] = round(s, 4)
            results.append(item)
        return results

    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику адаптивного RAG логов."""
        channels = collections.Counter(c.get("channel", "Unknown") for c in self.chunks)
        wiki_stats = self.wiki_storage.get_stats()
        wiki_count = wiki_stats.get("total_entities", 0) if isinstance(wiki_stats, dict) else getattr(wiki_stats, "total_entities", 0)
        return {
            "total_chunks": len(self.chunks),
            "channels": dict(channels),
            "wiki_entities_count": wiki_count,
        }

