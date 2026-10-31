# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin AI - Text RAG Engine
# =============================================================================
# Description:
#   Движок текстового и документального RAG на основе эмбеддингов Gemini,
#   FAISS индекса и локального векторного поиска.
#
# Usage Examples:
#   Python API:
#     from src.ai.rag.text_rag import TextRAG
#
#     rag = TextRAG()
#     rag.add_documents([{"id": "doc1", "text": "Текст документа"}])
#     results = rag.search("запрос", top_k=3)
#
# File: text_rag.py
# Project: ai-windows-admin
# Package: src.ai.rag
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-20 14:47:00
# =============================================================================

from __future__ import annotations
"""Движок текстового и документального RAG на основе эмбеддингов и FAISS."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np

from logger import logger


def _get_faiss():
    """Ленивая загрузка модуля faiss."""
    try:
        import faiss
        return faiss
    except ImportError:
        return None


class TextRAG:
    """Движок векторного поиска и семантического извлечения текстовых документов.

    Attributes:
        db_path: Путь к файлу базы/индекса.
        dimension: Размерность векторного пространства.
    """

    def __init__(
        self,
        api_key: str = "",
        db_path: Optional[Path] = None,
        dimension: int = 3072,
    ) -> None:
        """Инициализирует TextRAG.

        Args:
            api_key: Ключ API для генерации эмбеддингов.
            db_path: Путь к файлу индекса (по умолчанию data/rag/text_index).
            dimension: Размерность векторов (по умолчанию 3072 для Gemini).
        """
        self.db_path = db_path or Path("data/rag/text_index")
        self.index_file = self.db_path.with_suffix(".faiss")
        self.meta_file = self.db_path.with_suffix(".json")
        self.dimension = dimension
        self.api_key = api_key
        self.metadatas: List[Dict[str, Any]] = []
        self.index: Any = False

        self.index_file.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def _load(self) -> None:
        """Загрузка сохранённого индекса и метаданных."""
        if self.meta_file.exists():
            try:
                with open(self.meta_file, "r", encoding="utf-8") as f:
                    self.metadatas = json.load(f)
            except Exception as e:
                logger.error(f"[TextRAG] Ошибка чтения метаданных: {e}")
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
                logger.error(f"[TextRAG] Ошибка чтения FAISS индекса, перестроение: {e}")
                self._rebuild_index()
        else:
            self.index = faiss.IndexFlatL2(self.dimension)

    def _rebuild_index(self) -> None:
        """Перестроение FAISS индекса из загруженных метаданных."""
        faiss = _get_faiss()
        if not faiss:
            self.index = False
            return

        self.index = faiss.IndexFlatL2(self.dimension)
        if not self.metadatas:
            return

        valid_items = [
            m for m in self.metadatas
            if isinstance(m, dict) and "vector" in m
            and isinstance(m["vector"], (list, np.ndarray))
            and len(m["vector"]) == self.dimension
        ]
        self.metadatas = valid_items
        if self.metadatas:
            try:
                vectors = np.array([m["vector"] for m in self.metadatas], dtype=np.float32)
                self.index.add(vectors)
            except Exception as e:
                logger.error(f"[TextRAG] Ошибка добавления векторов в FAISS: {e}")

    def _save(self) -> None:
        """Сохранение индекса и метаданных на диск."""
        faiss = _get_faiss()
        try:
            if faiss and self.index:
                faiss.write_index(self.index, str(self.index_file))
            with open(self.meta_file, "w", encoding="utf-8") as f:
                json.dump(self.metadatas, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[TextRAG] Ошибка сохранения индекса: {e}")

    def _embed(self, texts: List[str], task_type: str = "RETRIEVAL_DOCUMENT") -> List[List[float]]:
        """Генерация эмбеддингов для списка строк."""
        if not texts:
            return []

        # Попытка получить через google.genai при наличии ключа
        try:
            from src.ai.gemini.gemini_api_key_state import load_api_keys
            from google import genai
            from google.genai import types

            api_keys, _, _ = load_api_keys(skip_exhausted=False)
            if api_keys:
                client = genai.Client(api_key=api_keys[0])
                response = client.models.embed_content(
                    model="models/gemini-embedding-2",
                    contents=[types.Content(parts=[types.Part.from_text(text=t)]) for t in texts],
                    config=types.EmbedContentConfig(
                        task_type=task_type,
                        output_dimensionality=self.dimension,
                    ),
                )
                embeddings = [e.values for e in response.embeddings]
                if embeddings and all(len(v) == self.dimension for v in embeddings):
                    return embeddings
                logger.warning(
                    f"[TextRAG] Gemini вернул некорректную размерность векторов "
                    f"({len(embeddings[0]) if embeddings else 0} != {self.dimension}), переход на fallback."
                )
        except Exception as e:
            logger.debug(f"[TextRAG] Gemini Embeddings недоступны ({e}), использование детерминированного хэш-эмбеддинга.")

        # Fallback: Детерминированный TF-IDF / хэш-вектор для офлайн-режима
        vectors: List[List[float]] = []
        for text in texts:
            vec = np.zeros(self.dimension, dtype=np.float32)
            words = text.lower().split()
            for w in words:
                h = abs(hash(w)) % self.dimension
                vec[h] += 1.0
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            vectors.append(vec.tolist())
        return vectors

    def add_documents(self, docs: List[Dict[str, Any]], batch_size: int = 50) -> int:
        """Векторизация и добавление документов в RAG-индекс.

        Args:
            docs: Список словарей формата {'id': str, 'text': str, 'meta': dict}.
            batch_size: Размер пачки для обработки.

        Returns:
            Количество успешно добавленных документов.
        """
        if not docs:
            return 0

        for i in range(0, len(docs), batch_size):
            batch = docs[i : i + batch_size]
            texts = [d["text"] for d in batch]
            vectors = self._embed(texts, task_type="RETRIEVAL_DOCUMENT")
            existing_ids = {doc["id"] for doc in batch}
            self.metadatas = [m for m in self.metadatas if m["id"] not in existing_ids]

            for doc, vec in zip(batch, vectors):
                self.metadatas.append({
                    "id": doc["id"],
                    "text": doc["text"],
                    "meta": doc.get("meta", {}),
                    "vector": vec,
                })

            self._rebuild_index()
            self._save()
        return len(docs)

    def delete_document(self, doc_id: str) -> None:
        """Удаление документа из индекса по идентификатору."""
        self.metadatas = [m for m in self.metadatas if m["id"] != doc_id]
        self._rebuild_index()
        self._save()

    def clear(self) -> None:
        """Полная очистка индекса."""
        faiss = _get_faiss()
        self.metadatas = []
        self.index = faiss.IndexFlatL2(self.dimension) if faiss else False
        self._save()

    def search(self, query: str, top_k: int = 5, threshold: float = 0.0) -> List[Dict[str, Any]]:
        """Семантический поиск ближайших документов по косинусному сходству.

        Args:
            query: Поисковый запрос.
            top_k: Максимальное количество результатов.
            threshold: Порог минимального сходства (от 0.0 до 1.0).

        Returns:
            Список найденных документов с оценкой релевантности.
        """
        valid_metadatas = [
            m for m in self.metadatas
            if isinstance(m, dict) and "vector" in m
            and isinstance(m["vector"], (list, np.ndarray))
            and len(m["vector"]) == self.dimension
        ]
        if not valid_metadatas:
            return []

        query_vecs = self._embed([query], task_type="RETRIEVAL_QUERY")
        if not query_vecs:
            return []

        query_vec = np.array(query_vecs[0], dtype=np.float32)
        if query_vec.shape[0] != self.dimension:
            logger.warning(
                f"[TextRAG] Несоответствие размерности вектора запроса ({query_vec.shape[0]}) "
                f"и индекса ({self.dimension}), семантический поиск пропущен."
            )
            return []

        doc_vectors = np.array([m["vector"] for m in valid_metadatas], dtype=np.float32)
        if doc_vectors.ndim != 2 or doc_vectors.shape[1] != query_vec.shape[0]:
            logger.warning(
                f"[TextRAG] Несоответствие размерности векторов документов ({doc_vectors.shape}) "
                f"и вектора запроса ({query_vec.shape}), семантический поиск пропущен."
            )
            return []

        query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-10)
        doc_norms = np.linalg.norm(doc_vectors, axis=1, keepdims=True) + 1e-10
        doc_vectors_normalized = doc_vectors / doc_norms

        actual_k = min(top_k, len(valid_metadatas))
        faiss = _get_faiss()
        results: List[Dict[str, Any]] = []

        if not faiss or not self.index:
            similarities = np.dot(doc_vectors_normalized, query_norm)
            top_indices = np.argsort(similarities)[::-1][:actual_k]
            for idx in top_indices:
                sim = float(similarities[idx])
                if sim >= threshold:
                    meta = valid_metadatas[idx]
                    results.append({
                        "id": meta["id"],
                        "text": meta["text"],
                        "meta": meta.get("meta", {}),
                        "score": round(sim, 4),
                    })
            return results

        temp_index = faiss.IndexFlatL2(self.dimension)
        temp_index.add(doc_vectors_normalized)
        distances, indices = temp_index.search(query_norm.reshape(1, -1), actual_k)
        for i in range(actual_k):
            idx = int(indices[0][i])
            if 0 <= idx < len(valid_metadatas):
                l2_dist = float(distances[0][i])
                cosine_sim = max(0.0, 1.0 - (l2_dist / 2.0))
                if cosine_sim >= threshold:
                    meta = valid_metadatas[idx]
                    results.append({
                        "id": meta["id"],
                        "text": meta["text"],
                        "meta": meta.get("meta", {}),
                        "score": round(cosine_sim, 4),
                    })
        return results

    def count(self) -> int:
        """Возвращает общее количество документов в индексе."""
        return len(self.metadatas)

