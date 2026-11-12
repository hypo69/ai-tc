# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Telegram Channel RAG Message Ingestion & Web Scraping
# =============================================================================
# Description:
#   Collects Telegram messages from public channel web previews or exported
#   JSON archives, normalizes text content, and constructs message permalinks.
#
# File: collector.py
# Project: ai-breadboard
# Package: plugins.telegram_channel_rag
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 14:39:30
# =============================================================================

"""Модуль сбора и разбора сообщений публичных Telegram-каналов и JSON-экспортов."""

from __future__ import annotations

import json
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import urllib.error
import urllib.parse
import urllib.request
from bs4 import BeautifulSoup

from logger import logger

# Максимальный размер JSON-экспорта для загрузки в память (50 МБ)
MAX_EXPORT_JSON_BYTES: int = 50 * 1024 * 1024
DEFAULT_HTTP_TIMEOUT_SEC: int = 15
MAX_HTTP_RETRIES: int = 3


class TelegramMessageCollector:
    """Собирает и извлекает структурированные сообщения из веб-превью каналов или файлов экспорта.

    Attributes:
        channel_username (str): Целевое имя пользователя канала (например, 'canozrimb').
        headers (Dict[str, str]): HTTP-заголовки для парсинга веб-превью.
    """

    def __init__(self, channel_username: str = "canozrimb") -> None:
        """Инициализирует сборщик сообщений Telegram.

        Args:
            channel_username (str): Имя канала или группы (без @ или со ссылкой).
        """
        self.channel_username = self._clean_username(channel_username)
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
        }

    def _clean_username(self, raw_input: str) -> str:
        """Очищает имя канала от URL-префиксов и опасных символов."""
        s = (raw_input or "").strip()
        s = re.sub(r"^https?://t\.me/(s/)?", "", s)
        s = s.lstrip("@").rstrip("/")
        clean = re.sub(r"[^a-zA-Z0-9_]", "", s.split("/")[0])
        return clean

    def build_message_url(self, message_id: Union[int, str]) -> str:
        """Формирует прямую ссылку на сообщение в Telegram."""
        return f"https://t.me/{self.channel_username}/{message_id}"

    def _fetch_html_with_retry(self, url: str) -> str:
        """Загружает HTML-страницу с таймаутом и Exponential Backoff + Jitter."""
        last_err: Optional[Exception] = None
        for attempt in range(MAX_HTTP_RETRIES):
            try:
                req = urllib.request.Request(url, headers=self.headers)
                with urllib.request.urlopen(req, timeout=DEFAULT_HTTP_TIMEOUT_SEC) as response:
                    return response.read().decode("utf-8", errors="replace")
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_err = exc
                if attempt < MAX_HTTP_RETRIES - 1:
                    delay = min(10.0, (0.5 * (2 ** attempt)) + random.uniform(0.0, 0.4))
                    time.sleep(delay)
        if last_err:
            raise last_err
        return ""

    def fetch_from_web_preview(self, max_messages: int = 500) -> List[Dict[str, Any]]:
        """Собирает публичные сообщения из веб-превью канала Telegram (`t.me/s/<channel>`)."""
        results: List[Dict[str, Any]] = []
        seen_ids = set()
        if not self.channel_username:
            return results
        base_url = f"https://t.me/s/{self.channel_username}"
        current_url = base_url

        try:
            while current_url and len(results) < max_messages:
                html_content = self._fetch_html_with_retry(current_url)

                soup = BeautifulSoup(html_content, "html.parser")
                message_elements = soup.find_all("div", class_=re.compile(r"tgme_widget_message"))

                if not message_elements:
                    break

                batch_msgs: List[Dict[str, Any]] = []
                for el in message_elements:
                    data_post = el.get("data-post", "")
                    if "/" not in data_post:
                        continue
                    try:
                        msg_id = int(data_post.split("/")[-1])
                    except ValueError:
                        continue

                    if msg_id in seen_ids:
                        continue
                    seen_ids.add(msg_id)

                    # Extract author
                    author_el = el.find("div", class_="tgme_widget_message_owner_name")
                    author = author_el.get_text(strip=True) if author_el else self.channel_username

                    # Extract datetime
                    time_el = el.find("time")
                    timestamp_str = time_el.get("datetime", "") if time_el else ""

                    # Extract text content
                    text_el = el.find("div", class_="tgme_widget_message_text")
                    text = text_el.get_text(separator="\n", strip=True) if text_el else ""

                    # Check for media captions or photo/video indicators if text is empty
                    if not text:
                        photo_el = el.find("a", class_="tgme_widget_message_photo_wrap")
                        video_el = el.find("video")
                        doc_el = el.find("div", class_="tgme_widget_message_document_title")
                        if doc_el:
                            text = f"[Document: {doc_el.get_text(strip=True)}]"
                        elif photo_el:
                            text = "[Photo Attachment]"
                        elif video_el:
                            text = "[Video Attachment]"

                    if not text.strip():
                        continue

                    url = self.build_message_url(msg_id)

                    batch_msgs.append({
                        "id": msg_id,
                        "channel": self.channel_username,
                        "author": author,
                        "timestamp": timestamp_str,
                        "text": text,
                        "url": url,
                        "source": "web_preview",
                    })

                if not batch_msgs:
                    break

                results.extend(batch_msgs)

                # Pagination backwards if needed
                prev_link = soup.find("link", rel="prev")
                if prev_link and prev_link.get("href"):
                    next_href = prev_link.get("href")
                    if next_href.startswith("/"):
                        current_url = f"https://t.me{next_href}"
                    else:
                        current_url = next_href
                else:
                    break

            logger.info(f"Fetched {len(results)} messages from Telegram channel preview: {self.channel_username}")
        except Exception as exc:
            logger.error(f"Error scraping Telegram channel preview for {self.channel_username}: {exc}")

        return results[:max_messages]

    def parse_export_json(self, export_file_path: Union[Path, str]) -> List[Dict[str, Any]]:
        """Parse exported Telegram Desktop chat history (result.json).

        Args:
            export_file_path (Union[Path, str]): Path to the result.json export file.

        Returns:
            List[Dict[str, Any]]: List of structured message dictionaries.
        """
        p = Path(export_file_path)
        if not p.exists():
            logger.error(f"Файл экспорта Telegram не найден: {p}")
            return []

        try:
            if p.stat().st_size > MAX_EXPORT_JSON_BYTES:
                logger.error(f"Файл экспорта {p.name} превышает лимит размера ({MAX_EXPORT_JSON_BYTES} байт)")
                return []
            data = json.loads(p.read_text(encoding="utf-8"))
            raw_messages = data.get("messages", [])
            results: List[Dict[str, Any]] = []

            for msg in raw_messages:
                if msg.get("type") != "message":
                    continue

                msg_id = msg.get("id")
                if not msg_id:
                    continue

                author = msg.get("from") or self.channel_username
                date_str = msg.get("date", "")
                
                # Text can be a string or a list of mixed text/link objects
                text_raw = msg.get("text", "")
                if isinstance(text_raw, list):
                    text_parts = []
                    for chunk in text_raw:
                        if isinstance(chunk, str):
                            text_parts.append(chunk)
                        elif isinstance(chunk, dict) and "text" in chunk:
                            text_parts.append(chunk["text"])
                    text = "".join(text_parts).strip()
                else:
                    text = str(text_raw).strip()

                if not text:
                    if msg.get("media_type"):
                        text = f"[{msg.get('media_type').capitalize()} Attachment]"
                    elif msg.get("file"):
                        text = f"[File: {msg.get('file')}]"
                    elif msg.get("photo"):
                        text = "[Photo Attachment]"

                if not text.strip():
                    continue

                url = self.build_message_url(msg_id)

                results.append({
                    "id": msg_id,
                    "channel": self.channel_username,
                    "author": author,
                    "timestamp": date_str,
                    "text": text,
                    "url": url,
                    "source": "json_export",
                })

            logger.info(f"Parsed {len(results)} messages from Telegram export file {p.name}")
            return results
        except Exception as exc:
            logger.error(f"Failed to parse Telegram JSON export: {exc}")
            return []
