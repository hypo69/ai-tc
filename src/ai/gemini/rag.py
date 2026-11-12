# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin AI - Rag Module
# =============================================================================
# Description:
#   Векторный индекс RAG на базе Gemini Embedding API и FAISS с потокобезопасностью
#   и атомарным сохранением данных.
#
# Usage Examples:
#   Python API:
#     from src.ai.gemini.rag import GeminiRAG
#
#     service = GeminiRAG()
#     result = service.add_documents([])
#     print(result)
#
# File: rag.py
# Project: ai-windows-admin
# Package: src.ai.gemini
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 14:43:00
# =============================================================================

"""Векторный индекс RAG на базе Gemini Embedding API и FAISS.

Предоставляет возможности векторизации документов, хранения в индексе FAISS
и семантического поиска ближайших соседей.
"""

import json
import os
from pathlib import Path
import random
import tempfile
import threading
import time
from typing import Dict, List

from google import genai
from google.genai import types
import numpy as np

from logger import logger

_EMBED_MODEL = 'models/gemini-embedding-2'
_EMBED_DIM = 3072


def _get_faiss():
    """Выполняет ленивую загрузку модуля faiss."""
    try:
        import faiss
        return faiss
    except ImportError:
        return None


class GeminiRAG:
    """Векторный индекс RAG с использованием Gemini Embedding API и FAISS.

    Обеспечивает векторизацию документов, атомарное сохранение индекса FAISS и метаданных,
    а также семантический поиск ближайших соседей с потокобезопасной синхронизацией.
    """

    def __init__(self, api_key: str = '', db_path: Path = Path('.')) -> None:
        """Инициализирует индекс RAG.

        Args:
            api_key (str): API-ключ Gemini.
            db_path (Path): Базовый путь к файлам индекса (.faiss и .json).
        """
        self._lock = threading.RLock()
        self.db_path = Path(db_path)
        self.index_file = self.db_path.with_suffix('.faiss')
        self.meta_file = self.db_path.with_suffix('.json')
        self.dimension = _EMBED_DIM
        self.api_key = api_key
        self.client = False
        if api_key:
            try:
                self.client = genai.Client(api_key=api_key)
            except Exception as e:
                logger.error(f'[GeminiRAG] Ошибка инициализации genai.Client: {e}')
        self.index_file.parent.mkdir(parents=True, exist_ok=True)
        self.metadatas: List[Dict] = []
        self._load()

    def _load(self) -> None:
        """Загружает индекс FAISS и метаданные документов с диска."""
        with self._lock:
            if self.meta_file.exists():
                try:
                    with open(self.meta_file, 'r', encoding='utf-8') as f:
                        self.metadatas = json.load(f)
                except Exception as e:
                    logger.error('Ошибка чтения метаданных пользователя', e)
                    self.metadatas = []
            else:
                self.metadatas = []
            faiss = _get_faiss()
            if not faiss:
                self.index = False
                return
            if self.index_file.exists() and self.metadatas:
                try:
                    self.index = faiss.read_index(str(self.index_file))
                except Exception as e:
                    logger.error('Ошибка чтения FAISS индекса, пересоздаем', e)
                    self._rebuild_index()
            else:
                self.index = faiss.IndexFlatL2(self.dimension)

    def _rebuild_index(self) -> None:
        """Перестраивает индекс FAISS из metadatas с проверкой размерности векторов."""
        with self._lock:
            faiss = _get_faiss()
            if not faiss:
                self.index = False
                return
            self.index = faiss.IndexFlatL2(self.dimension)
            if not self.metadatas:
                return
            valid_items = [
                m
                for m in self.metadatas
                if isinstance(m, dict)
                and 'vector' in m
                and isinstance(m['vector'], (list, np.ndarray))
                and (len(m['vector']) == self.dimension)
            ]
            if len(valid_items) != len(self.metadatas):
                logger.warning(
                    f"[GeminiRAG] Отфильтровано {len(self.metadatas) - len(valid_items)} записей без корректного поля 'vector'"
                )
                self.metadatas = valid_items
                self._save()
            if self.metadatas:
                try:
                    vectors = np.array([m['vector'] for m in self.metadatas], dtype=np.float32)
                    self.index.add(vectors)
                except Exception as e:
                    logger.error('Ошибка при добавлении векторов в FAISS индекс', e)

    def _save(self) -> None:
        """Атомарно сохраняет индекс FAISS и JSON-метаданные на диск."""
        with self._lock:
            faiss = _get_faiss()
            temp_meta: Path | None = None
            temp_faiss: Path | None = None
            try:
                self.meta_file.parent.mkdir(parents=True, exist_ok=True)
                if faiss and self.index:
                    temp_faiss = self.index_file.with_suffix('.faiss.tmp')
                    faiss.write_index(self.index, str(temp_faiss))
                    os.replace(temp_faiss, self.index_file)
                with tempfile.NamedTemporaryFile(
                    'w',
                    dir=str(self.meta_file.parent),
                    prefix=f'.{self.meta_file.name}.',
                    suffix='.tmp',
                    delete=False,
                    encoding='utf-8',
                ) as f:
                    temp_meta = Path(f.name)
                    json.dump(self.metadatas, f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(temp_meta, self.meta_file)
            except Exception as e:
                for tmp in (temp_meta, temp_faiss):
                    if tmp and tmp.exists():
                        try:
                            tmp.unlink()
                        except OSError:
                            pass
                logger.error('Ошибка сохранения FAISS индекса/метаданных', e)

    def _embed(self, texts: List[str], task_type: str = 'RETRIEVAL_DOCUMENT') -> List[List[float]]:
        """Получает эмбеддинги для списка текстов через Gemini API с Exponential Backoff + Jitter и ротацией ключей."""
        from src.ai.gemini.gemini_api_key_state import load_api_keys, mark_exhausted

        start_idx = random.randint(0, 100)
        max_retries = 10
        for attempt in range(max_retries):
            api_keys, key_names, _ = load_api_keys(skip_exhausted=False)
            if not api_keys:
                raise RuntimeError('Нет доступных ключей API Gemini')
            key_idx = (start_idx + attempt) % len(api_keys)
            current_key = api_keys[key_idx]
            current_name = key_names[key_idx]
            client = genai.Client(api_key=current_key)
            try:
                response = client.models.embed_content(
                    model=_EMBED_MODEL,
                    contents=[types.Content(parts=[types.Part.from_text(text=t)]) for t in texts],
                    config=types.EmbedContentConfig(task_type=task_type),
                )
                return [e.values for e in response.embeddings]
            except Exception as e:
                from src.config import is_debug_mode
                if is_debug_mode():
                    logger.critical(f'[DEBUG MODE] Ошибка получения эмбеддингов Gemini RAG ({current_name}): {e}')
                    raise e
                err_str = str(e)
                if '429' in err_str or 'RESOURCE_EXHAUSTED' in err_str:
                    delay = min(60.0, 2.0 * (2 ** min(attempt, 4))) + random.uniform(0.5, 2.0)
                    logger.warning(f'Превышен лимит (429) для ключа {current_name}. Переключаемся и ждем {delay:.1f} сек...')
                    time.sleep(delay)
                    continue
                elif '400' in err_str or 'INVALID_ARGUMENT' in err_str or 'API_KEY_INVALID' in err_str:
                    logger.warning(f'Неверный ключ API (400) для {current_name}. Пропускаем...')
                    mark_exhausted(current_name)
                    continue
                raise e
        raise RuntimeError('Превышено количество попыток запроса эмбеддингов из-за ограничений скорости (429)')

    def add_documents(self, docs: List[dict], batch_size: int = 50) -> int:
        """Векторизует и сохраняет документы в индекс.

        Args:
            docs (List[dict]): Список документов с ключами 'id', 'text', 'meta'.
            batch_size (int): Размер пакета векторизации.

        Returns:
            int: Количество добавленных документов.
        """
        if not docs:
            return 0
        for i in range(0, len(docs), batch_size):
            batch = docs[i : i + batch_size]
            texts = [d['text'] for d in batch]
            try:
                vectors = self._embed(texts, task_type='RETRIEVAL_DOCUMENT')
            except Exception as e:
                logger.error(f'Ошибка получения эмбеддингов для батча: {e}')
                raise e
            with self._lock:
                existing_ids = {doc['id'] for doc in batch}
                self.metadatas = [m for m in self.metadatas if m.get('id') not in existing_ids]
                for doc, vec in zip(batch, vectors):
                    self.metadatas.append({
                        'id': doc['id'],
                        'text': doc['text'],
                        'meta': doc.get('meta', {}),
                        'vector': vec,
                    })
                self._rebuild_index()
                self._save()
            if i + batch_size < len(docs):
                time.sleep(1.0)
        return len(docs)

    def delete_document(self, doc_id: str) -> None:
        """Удаляет документ из индекса по идентификатору."""
        with self._lock:
            self.metadatas = [m for m in self.metadatas if m.get('id') != doc_id]
            self._rebuild_index()
            self._save()

    def clear(self) -> None:
        """Полностью очищает индекс и метаданные."""
        with self._lock:
            faiss = _get_faiss()
            self.metadatas = []
            self.index = faiss.IndexFlatL2(self.dimension) if faiss else False
            self._save()

    def search(self, query: str, top_k: int = 5, threshold: float = 0.0) -> List[dict]:
        """Выполняет семантический поиск ближайших документов по косинусному сходству."""
        with self._lock:
            valid_metadatas = [
                m
                for m in self.metadatas
                if isinstance(m, dict)
                and 'vector' in m
                and isinstance(m['vector'], (list, np.ndarray))
                and (len(m['vector']) == self.dimension)
            ]
        if not valid_metadatas:
            return []
        try:
            query_vec = np.array(self._embed([query], task_type='RETRIEVAL_QUERY')[0], dtype=np.float32)
        except Exception as e:
            logger.error('Ошибка векторизации поискового запроса', e)
            return []
        query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-10)
        doc_vectors = np.array([m['vector'] for m in valid_metadatas], dtype=np.float32)
        doc_norms = np.linalg.norm(doc_vectors, axis=1, keepdims=True) + 1e-10
        doc_vectors_normalized = doc_vectors / doc_norms
        actual_k = min(top_k, len(valid_metadatas))
        faiss = _get_faiss()
        if not faiss:
            similarities = np.dot(doc_vectors_normalized, query_norm)
            top_indices = np.argsort(similarities)[::-1][:actual_k]
            results: List[dict] = []
            for idx in top_indices:
                sim = float(similarities[idx])
                if sim >= threshold:
                    meta = valid_metadatas[idx]
                    results.append({
                        'id': meta['id'],
                        'text': meta['text'],
                        'meta': meta.get('meta', {}),
                        'score': round(sim, 4),
                    })
            return results
        temp_index = faiss.IndexFlatL2(self.dimension)
        temp_index.add(doc_vectors_normalized)
        distances, indices = temp_index.search(query_norm.reshape(1, -1), actual_k)
        results = []
        for i in range(actual_k):
            idx = int(indices[0][i])
            if 0 <= idx < len(valid_metadatas):
                l2_dist = float(distances[0][i])
                cosine_sim = 1.0 - l2_dist / 2.0
                if cosine_sim >= threshold:
                    meta = valid_metadatas[idx]
                    results.append({
                        'id': meta['id'],
                        'text': meta['text'],
                        'meta': meta.get('meta', {}),
                        'score': round(cosine_sim, 4),
                    })
        return results

    def count(self) -> int:
        """Возвращает количество документов в индексе."""
        with self._lock:
            return len(self.metadatas)
