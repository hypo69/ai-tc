# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI Assistant UTILS - Document & PDF Extractor
# =============================================================================
# Description:
#   Универсальный модуль извлечения текста из документов (PDF, DOCX, TXT).
#
# File: pdf_extractor.py
# Package: src.utils
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 14:40:00
# =============================================================================

from __future__ import annotations

"""Модуль безопасного извлечения текста из документов PDF и других форматов."""

import asyncio
from pathlib import Path
from typing import Optional, Union

from logger import logger
from src.utils.pdf import extract_pdf_text

_MAX_DOCUMENT_BYTES = 50 * 1024 * 1024  # 50 МБ лимит для защиты от OOM


async def extract_document_text(file_path: Union[str, Path]) -> str:
    """Асинхронно извлекает текст из документа (PDF, текстовых файлов, docx) без блокировки Event Loop.

    Args:
        file_path (Union[str, Path]): Путь к файлу.

    Returns:
        str: Извлечённый текст или пустая строка при ошибке.
    """
    path = Path(file_path)
    if not path.is_file():
        logger.warning(f"[extract_document_text] Файл не существует: {path}")
        return ""

    try:
        if path.stat().st_size > _MAX_DOCUMENT_BYTES:
            logger.warning(f"[extract_document_text] Файл превышает допустимый размер (50 МБ): {path}")
            return ""
    except OSError:
        return ""

    ext = path.suffix.lower()
    try:
        if ext == ".pdf":
            text = await asyncio.to_thread(extract_pdf_text, path)
            return text or ""
        elif ext in (".txt", ".md", ".json", ".csv"):
            return await asyncio.to_thread(path.read_text, encoding="utf-8", errors="ignore")
        elif ext == ".docx":
            from src.utils.docx import extract_docx_text
            text = await asyncio.to_thread(extract_docx_text, path, True)
            return text or ""
        else:
            return await asyncio.to_thread(path.read_text, encoding="utf-8", errors="ignore")
    except Exception as exc:
        logger.error(f"[extract_document_text] Ошибка извлечения текста из {path.name}: {exc}")
        return ""


__all__ = ["extract_pdf_text", "extract_document_text"]
