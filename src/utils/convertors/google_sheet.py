# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin UTILS - Google Sheets Reader Module
# =============================================================================
# Description:
#   Чтение и конвертация Google Таблиц (Google Sheets) и документов Google Диска
#   в структурированный текст и Markdown таблицы.
#   Поддерживает авторизованный доступ через Google API (OAuth2 токены из src/secrets)
#   и экспорт публичных таблиц по URL без авторизации.
#
# Usage Examples:
#   Python API:
#     from src.utils.convertors.google_sheet import read_google_sheet
#
#     md = await read_google_sheet("https://docs.google.com/spreadsheets/d/12345/edit")
#     print(md)
#
# File: google_sheet.py
# Project: ai-windows-admin
# Package: src.utils.convertors
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-17 04:05:00
# =============================================================================

from __future__ import annotations
"""Чтение таблиц Google Sheets и преобразование в Markdown."""

import csv
import io
import re
from typing import Any, Dict, List, Optional
import requests

from logger import logger


def extract_spreadsheet_id(url_or_id: str) -> str:
    """Извлекает ID таблицы Google Sheets из URL или строки идентификатора.

    Args:
        url_or_id: Ссылка на Google Таблицу или чистый ID.

    Returns:
        str: Выделенный spreadsheet_id.
    """
    clean = url_or_id.strip()
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", clean)
    if match:
        return match.group(1)
    if "/" not in clean and len(clean) >= 15:
        return clean
    return clean


def read_google_sheet_public(spreadsheet_id: str, gid: str = "0") -> Optional[str]:
    """Загружает общедоступную Google Таблицу через веб-экспорт CSV и преобразует в Markdown.

    Args:
        spreadsheet_id: Идентификатор таблицы.
        gid: Идентификатор конкретного листа.

    Returns:
        Optional[str]: Markdown-представление таблицы или None при ошибке.
    """
    export_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"
    try:
        resp = requests.get(export_url, timeout=12)
        if resp.status_code == 200 and resp.text:
            reader = csv.reader(io.StringIO(resp.text))
            rows = [r for r in reader if any(cell.strip() for cell in r)]
            if not rows:
                return f"# Google Таблица: {spreadsheet_id}\n\n*(Таблица пуста)*"

            headers = [c if c.strip() else f"Колонка_{idx + 1}" for idx, c in enumerate(rows[0])]
            lines = [
                f"# Google Таблица: {spreadsheet_id}",
                "",
                "| " + " | ".join(headers) + " |",
                "| " + " | ".join(["---"] * len(headers)) + " |",
            ]
            for row in rows[1:]:
                padded = row + [""] * (len(headers) - len(row))
                row_vals = [c.replace("\n", " ").replace("|", "/") for c in padded[:len(headers)]]
                lines.append("| " + " | ".join(row_vals) + " |")

            return "\n".join(lines)
    except Exception as exc:
        logger.debug(f"[google_sheet] Публичный экспорт недоступен для {spreadsheet_id}: {exc}")
    return None


def read_google_sheet_api(spreadsheet_id: str) -> Optional[str]:
    """Читает все листы Google Таблицы через Google Sheets API v4 с учетными данными из пула.

    Args:
        spreadsheet_id: Идентификатор таблицы.

    Returns:
        Optional[str]: Markdown текст всех листов таблицы или None при отсутствии доступа.
    """
    try:
        from src.ai.google_accounts_state import load_account_credentials
        from googleapiclient.discovery import build

        creds = load_account_credentials(scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
        if not creds:
            return None

        service = build("sheets", "v4", credentials=creds)
        meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        title = meta.get("properties", {}).get("title", spreadsheet_id)
        sheets = meta.get("sheets", [])

        lines = [f"# Google Таблица: {title} (ID: {spreadsheet_id})\n"]

        for s in sheets:
            props = s.get("properties", {})
            sheet_title = props.get("title", "Лист 1")
            lines.append(f"## Лист: {sheet_title}\n")

            data = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=sheet_title,
            ).execute()
            values = data.get("values", [])

            if not values:
                lines.append("*(Лист пуст)*\n")
                continue

            raw_headers = values[0]
            headers = [str(c).strip() if str(c).strip() else f"Колонка_{idx + 1}" for idx, c in enumerate(raw_headers)]
            lines.append("| " + " | ".join(headers) + " |")
            lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

            for row in values[1:]:
                padded = row + [""] * (len(headers) - len(row))
                row_vals = [str(c).replace("\n", " ").replace("|", "/") for c in padded[:len(headers)]]
                lines.append("| " + " | ".join(row_vals) + " |")

            lines.append("")

        return "\n".join(lines)
    except Exception as exc:
        logger.warning(f"[google_sheet] Ошибка API при чтении {spreadsheet_id}: {exc}")
        return None


async def read_google_sheet(url_or_id: str) -> str:
    """Универсальное чтение Google Таблицы: сначала через официальный API, затем через экспорт.

    Args:
        url_or_id: Ссылка на Google Sheets или Spreadsheet ID.

    Returns:
        str: Данные таблицы в формате Markdown.
    """
    sid = extract_spreadsheet_id(url_or_id)
    if not sid:
        return f"*(Некорректная ссылка на Google Таблицу: {url_or_id})*"

    # 1. Попытка через Google Sheets API
    api_result = read_google_sheet_api(sid)
    if api_result:
        return api_result

    # 2. Попытка через публичный веб-экспорт CSV
    pub_result = read_google_sheet_public(sid)
    if pub_result:
        return pub_result

    return (
        f"# Google Таблица: {sid}\n\n"
        f"*(Не удалось прочитать таблицу. Проверьте права доступа (доступ по ссылке) "
        f"или настройте авторизацию Google в src/secrets/google_accounts.json)*"
    )

