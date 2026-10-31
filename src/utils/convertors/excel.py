# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin UTILS - Excel Convertor Module
# =============================================================================
# Description:
#   Утилиты конвертации электронных таблиц Excel (.xlsx, .xls) в словари Python,
#   форматированный Markdown и CSV для последующего NLP-анализа и RAG-индексации.
#
# Usage Examples:
#   Python API:
#     from src.utils.convertors.excel import excel2text, excel2dict
#
#     md_tables = excel2text("data/report.xlsx")
#     print(md_tables)
#
# File: excel.py
# Project: ai-windows-admin
# Package: src.utils.convertors
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-20 11:21:00
# =============================================================================

from __future__ import annotations
"""Конвертер файлов Excel (.xlsx, .xls) в структурированный текст и Markdown."""

import io
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

try:
    import openpyxl
except ImportError:
    openpyxl = None  # type: ignore[assignment]

from logger import logger


def excel2dict(
    file_path: Union[str, Path],
    sheet_name: Optional[str] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """Конвертирует таблицы Excel в словарь со списками строк по листам.

    Args:
        file_path: Путь к файлу Excel (.xlsx, .xls).
        sheet_name: Опциональное имя конкретного листа (если None — читаются все).

    Returns:
        Dict[str, List[Dict[str, Any]]]: Словарь, где ключ — имя листа,
        а значение — список словарей {заголовок_колонки: значение_ячейки}.
    """
    if openpyxl is None:
        logger.error("[excel2dict] Библиотека openpyxl не установлена. Выполните: pip install openpyxl")
        return {}

    path = Path(file_path)
    if not path.is_file():
        logger.error(f"[excel2dict] Файл Excel не найден: {path}")
        return {}

    wb = openpyxl.load_workbook(str(path), data_only=True, read_only=True)
    sheets_data: Dict[str, List[Dict[str, Any]]] = {}

    target_sheets = [sheet_name] if sheet_name and sheet_name in wb.sheetnames else wb.sheetnames

    for s_name in target_sheets:
        ws = wb[s_name]
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            sheets_data[s_name] = []
            continue

        # Первая непустая строка принимается за заголовки
        header_row_idx = 0
        while header_row_idx < len(rows) and not any(rows[header_row_idx]):
            header_row_idx += 1

        if header_row_idx >= len(rows):
            sheets_data[s_name] = []
            continue

        raw_headers = rows[header_row_idx]
        headers = [
            str(h).strip() if h is not None and str(h).strip() else f"Колонка_{idx + 1}"
            for idx, h in enumerate(raw_headers)
        ]

        sheet_records: List[Dict[str, Any]] = []
        for row in rows[header_row_idx + 1:]:
            if not any(v is not None and str(v).strip() != "" for v in row):
                continue  # Пропуск пустых строк
            record: Dict[str, Any] = {}
            for col_idx, header in enumerate(headers):
                val = row[col_idx] if col_idx < len(row) else None
                record[header] = val if val is not None else ""
            sheet_records.append(record)

        sheets_data[s_name] = sheet_records

    wb.close()
    return sheets_data


def excel2text(file_path: Union[str, Path]) -> str:
    """Конвертирует все листы Excel в структурированный текст формата Markdown.

    Args:
        file_path: Путь к файлу Excel.

    Returns:
        str: Текстовое представление всех таблиц в формате Markdown.
    """
    data = excel2dict(file_path)
    if not data:
        return ""

    output_lines: List[str] = []
    file_name = Path(file_path).name
    output_lines.append(f"# Таблица Excel: {file_name}\n")

    for sheet_name, records in data.items():
        output_lines.append(f"## Лист: {sheet_name}\n")
        if not records:
            output_lines.append("*(Лист пуст)*\n")
            continue

        headers = list(records[0].keys())
        # Markdown заголовок
        output_lines.append("| " + " | ".join(headers) + " |")
        output_lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

        # Строки
        for rec in records:
            row_vals = [str(rec.get(h, "")).replace("\n", " ").replace("|", "/") for h in headers]
            output_lines.append("| " + " | ".join(row_vals) + " |")

        output_lines.append("")

    return "\n".join(output_lines)

