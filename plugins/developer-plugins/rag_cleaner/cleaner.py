# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: RAG Document Cleaner Core
# =============================================================================
# Description:
#   Очищает, нормализует и разбивает разнородные документы (PDF, DOCX, HTML, CSV,
#   JSON, TXT, архивы) на семантические фрагменты для индексации в RAG.
#
# File: cleaner.py
# Project: ai-breadboard
# Package: plugins.rag_cleaner
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 14:39:00
# =============================================================================

from __future__ import annotations
"""Ядро очистки и разбиения документов на чанки для RAG."""

import json
import os
from pathlib import Path
import re
from typing import Any, Dict, Generator, List, Optional, Union

from logger import logger
from src.utils.archive import extract_archive
from src.utils.convertors.html2text import html2text
from src.utils.convertors.unicode import decode_unicode_escape
from src.utils.csv import read_csv_as_dict
from src.utils.docx import extract_docx_text
from src.utils.file import read_text_file
from src.utils.jjson import j_loads
from src.utils.pdf_extractor import extract_pdf_text

# Максимальный размер обрабатываемого файла (50 МБ)
MAX_CLEANER_FILE_BYTES: int = 50 * 1024 * 1024
_ARCHIVE_EXTS: frozenset[str] = frozenset({".zip", ".tar", ".gz", ".tgz", ".bz2"})


class RAGDocumentCleanerCore:
    """Ядро нормализации текста и семантического разбиения документов для RAG."""

    def __init__(self, min_chunk_len: int = 20, max_chunk_len: int = 1500) -> None:
        """Инициализирует параметры размеров чанков."""
        self.min_chunk_len = min_chunk_len
        self.max_chunk_len = max_chunk_len

    def sanitize_text(self, text: str) -> str:
        """Очищает текст от управляющих спецсимволов, переносов слов и лишних пустых строк."""
        if not text:
            return ""
        try:
            text = str(decode_unicode_escape(text))
        except Exception:
            pass
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def chunk_markdown(self, text: str, source: str) -> List[Dict[str, Any]]:
        """Разбивает очищенный текст на логические фрагменты заданной длины."""
        chunks: List[Dict[str, Any]] = []
        if not text:
            return chunks
        sections = re.split(r'\n(?=#{1,4}\s)', text)
        for sec in sections:
            sec_clean = sec.strip()
            if len(sec_clean) < self.min_chunk_len:
                continue
            if len(sec_clean) <= self.max_chunk_len:
                chunks.append({"content": sec_clean, "source": source, "length": len(sec_clean)})
            else:
                paragraphs = sec_clean.split("\n\n")
                buf = ""
                for p in paragraphs:
                    if len(buf) + len(p) + 2 <= self.max_chunk_len:
                        buf = f"{buf}\n\n{p}".strip()
                    else:
                        if len(buf) >= self.min_chunk_len:
                            chunks.append({"content": buf, "source": source, "length": len(buf)})
                        buf = p.strip()
                if len(buf) >= self.min_chunk_len:
                    chunks.append({"content": buf, "source": source, "length": len(buf)})
        return chunks

    def process_file(self, file_path: Union[str, Path]) -> Generator[Dict[str, Any], None, None]:
        """Обрабатывает одиночный файл или архив и генерирует чанки для RAG."""
        path = Path(file_path)
        if not path.is_file():
            logger.error(f"Файл не найден: {path}")
            return
        try:
            if path.stat().st_size > MAX_CLEANER_FILE_BYTES:
                logger.warning(f"Файл {path.name} превышает лимит размера ({MAX_CLEANER_FILE_BYTES} байт), пропуск.")
                return
        except OSError:
            return

        ext = path.suffix.lower()
        try:
            if ext in _ARCHIVE_EXTS:
                extracted = extract_archive(path)
                for sub_file in extracted:
                    yield from self.process_file(sub_file)
                return

            raw_text: Optional[str] = None
            doc_type = ext.replace(".", "")
            if ext == ".docx":
                raw_text = extract_docx_text(path, as_markdown=True)
            elif ext == ".pdf":
                raw_text = extract_pdf_text(path)
            elif ext in (".html", ".htm"):
                content = read_text_file(path)
                if content:
                    raw_text = html2text(str(content))
            elif ext == ".csv":
                rows = read_csv_as_dict(path)
                if rows:
                    raw_text = "\n".join([json.dumps(r, ensure_ascii=False) for r in rows])
            elif ext == ".json":
                data = j_loads(path)
                if data:
                    raw_text = json.dumps(data, ensure_ascii=False, indent=2)
            elif ext in (".txt", ".md", ".log", ".rst"):
                content = read_text_file(path)
                if content:
                    raw_text = str(content)

            if raw_text:
                cleaned = self.sanitize_text(raw_text)
                for chunk in self.chunk_markdown(cleaned, str(path)):
                    chunk["doc_type"] = doc_type
                    yield chunk
        except Exception as ex:
            logger.error(f"Ошибка при обработке файла {path}: {ex}")

    def process_target(self, target_path: Union[str, Path]) -> List[Dict[str, Any]]:
        """Обрабатывает файл или рекурсивно все файлы в директории."""
        target = Path(target_path)
        all_chunks: List[Dict[str, Any]] = []
        if target.is_file():
            all_chunks.extend(list(self.process_file(target)))
        elif target.is_dir():
            for p in target.rglob("*"):
                if p.is_file():
                    all_chunks.extend(list(self.process_file(p)))
        return all_chunks
