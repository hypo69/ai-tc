# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin AI - Pixel RAG Engine
# =============================================================================
# Description:
#   Мультимодальный визуальный RAG-движок для индексации, поиска и сопоставления
#   скриншотов UI, графических диаграмм и визуальных состояний системы.
#
# Usage Examples:
#   Python API:
#     from src.ai.rag.pixel_rag import PixelRAG
#
#     pixel_rag = PixelRAG()
#     pixel_rag.index_image_file("data/screenshots/error1.png", metadata={"app": "cmd.exe"})
#     matches = pixel_rag.search_by_text("ошибка диска", top_k=3)
#
# File: pixel_rag.py
# Project: ai-windows-admin
# Package: src.ai.rag
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 16:55:00
# =============================================================================

from __future__ import annotations
"""Мультимодальный визуальный RAG-движок для UI-скриншотов и графических артефактов."""

import hashlib
import io
import json
import math
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from logger import logger


class PixelRAG:
    """Движок мультимодального индексирования и поиска изображений и скриншотов.

    Attributes:
        storage_dir: Директория хранения индекса и метаданных изображений.
        items: Список проиндексированных графических записей.
    """

    def __init__(self, storage_dir: Optional[Path] = None) -> None:
        """Инициализирует PixelRAG.

        Args:
            storage_dir: Директория для хранения метаданных и индекса.
        """
        self.storage_dir = storage_dir or Path("data/rag/pixel_storage")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.meta_file = self.storage_dir / "pixel_catalog.json"
        self.items: List[Dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        """Загрузка каталога изображений с диска."""
        if self.meta_file.exists():
            try:
                with open(self.meta_file, "r", encoding="utf-8") as f:
                    self.items = json.load(f)
            except Exception as e:
                logger.error(f"[PixelRAG] Ошибка чтения каталога pixel: {e}")
                self.items = []
        else:
            self.items = []

    def _save(self) -> None:
        """Атомарное сохранение каталога изображений на диск."""
        tmp_file = self.meta_file.with_suffix(".json.tmp")
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(self.items, f, ensure_ascii=False, indent=2)
            os.replace(tmp_file, self.meta_file)
        except Exception as e:
            logger.error(f"[PixelRAG] Ошибка сохранения каталога pixel: {e}")
            if tmp_file.exists():
                try:
                    tmp_file.unlink()
                except OSError:
                    pass

    @staticmethod
    def compute_visual_fingerprint(data: bytes) -> Dict[str, Any]:
        """Вычисляет компактный визуальный отпечаток и хэш изображения.

        Args:
            data: Байты графического файла.

        Returns:
            Словарь с хэшем, контрольной суммой и характеристиками.
        """
        sha256 = hashlib.sha256(data).hexdigest()
        size_bytes = len(data)
        # Упрощенный расчет гистограммы байт для сигнатуры
        byte_freq = [0] * 16
        for b in data[:4096]:
            byte_freq[b % 16] += 1
        norm = max(1, max(byte_freq))
        signature = [round(x / norm, 3) for x in byte_freq]

        return {
            "sha256": sha256,
            "size_bytes": size_bytes,
            "signature": signature,
        }

    def index_image_file(
        self,
        file_path: Union[str, Path],
        title: str = "",
        ocr_text: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        filename: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Индексирует локальный файл изображения в PixelRAG.

        Args:
            file_path: Путь к файлу изображения.
            title: Заголовок или описание скриншота.
            ocr_text: Распознанный текст с изображения.
            metadata: Дополнительные пользовательские метаданные.
            filename: Исходное имя файла (опционально).

        Returns:
            Созданная запись каталога.
        """
        p = Path(file_path).resolve()
        if not p.is_file():
            raise FileNotFoundError(f"Файл изображения не найден: {p}")

        data = p.read_bytes()
        fp = self.compute_visual_fingerprint(data)
        item_id = f"img_{fp['sha256'][:16]}"

        # Проверяем, существует ли уже такая запись
        existing = next((item for item in self.items if item["id"] == item_id), None)
        item_data = {
            "id": item_id,
            "filename": filename or p.name,
            "file_path": str(p),
            "title": title or p.stem,
            "ocr_text": ocr_text,
            "size_bytes": fp["size_bytes"],
            "sha256": fp["sha256"],
            "signature": fp["signature"],
            "metadata": metadata or {},
            "indexed_at": time.time(),
        }

        if existing:
            self.items.remove(existing)
        self.items.append(item_data)
        self._save()
        return item_data

    def index_image_bytes(
        self,
        data: bytes,
        filename: str,
        title: str = "",
        ocr_text: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Индексирует байты изображения, сохраняя копию в хранилище.

        Args:
            data: Байты изображения.
            filename: Имя файла.
            title: Описание скриншота.
            ocr_text: Распознанный текст.
            metadata: Дополнительные метаданные.

        Returns:
            Созданная запись каталога.
        """
        fp = self.compute_visual_fingerprint(data)
        item_id = f"img_{fp['sha256'][:16]}"
        safe_filename = Path(filename or "screenshot.png").name
        dest_path = self.storage_dir / f"{item_id}_{safe_filename}"
        dest_path.write_bytes(data)

        return self.index_image_file(
            file_path=dest_path,
            title=title or safe_filename,
            ocr_text=ocr_text,
            metadata=metadata,
            filename=safe_filename,
        )

    def search_by_text(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Поиск скриншотов и изображений по текстовому описанию и OCR-слою.

        Args:
            query: Текстовый поисковый запрос.
            top_k: Максимальное число совпадений.

        Returns:
            Список подходящих записей с релевантностью.
        """
        q_tokens = set(query.lower().split())
        if not q_tokens:
            return []

        scored: List[Tuple[float, Dict[str, Any]]] = []
        for item in self.items:
            content = f"{item.get('title', '')} {item.get('ocr_text', '')} {item.get('filename', '')} {json.dumps(item.get('metadata', {}), ensure_ascii=False)}".lower()
            matches = sum(1 for t in q_tokens if t in content)
            if matches > 0:
                score = matches / len(q_tokens)
                scored.append((score, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        results: List[Dict[str, Any]] = []
        for score, it in scored[:top_k]:
            res = dict(it)
            res["score"] = round(score, 4)
            results.append(res)
        return results

    def search_by_visual(self, data: bytes, top_k: int = 5) -> List[Dict[str, Any]]:
        """Визуальный поиск дубликатов и схожих скриншотов по сигнатуре.

        Args:
            data: Байты искомого изображения.
            top_k: Максимальное число совпадений.

        Returns:
            Список наиболее схожих изображений.
        """
        target_fp = self.compute_visual_fingerprint(data)
        t_sig = target_fp["signature"]

        scored: List[Tuple[float, Dict[str, Any]]] = []
        for item in self.items:
            sig = item.get("signature", [])
            if len(sig) == len(t_sig) and len(sig) > 0:
                # Евклидово расстояние между сигнатурами
                dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(sig, t_sig)))
                sim = max(0.0, 1.0 - (dist / math.sqrt(len(sig))))
                scored.append((sim, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        results: List[Dict[str, Any]] = []
        for score, it in scored[:top_k]:
            res = dict(it)
            res["score"] = round(score, 4)
            results.append(res)
        return results

    def get_status(self) -> Dict[str, Any]:
        """Возвращает метрики и статус хранилища PixelRAG."""
        total_size = sum(item.get("size_bytes", 0) for item in self.items)
        last_updated = max((item.get("indexed_at", 0) for item in self.items), default=0)

        return {
            "total_images": len(self.items),
            "total_chunks": len(self.items),
            "total_size_mb": round(total_size / (1024 * 1024), 3),
            "provider": "PixelRAG / Visual Hash + OCR",
            "last_built_at": last_updated,
            "sources": {
                "images": len(self.items),
                "text_chunks": sum(1 for it in self.items if it.get("ocr_text")),
            },
        }

    def clear(self) -> None:
        """Очищает каталог и сохраненные скриншоты."""
        self.items = []
        self._save()
