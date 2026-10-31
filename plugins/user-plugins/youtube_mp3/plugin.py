# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: YouTube MP3 Downloader Modular Plugin
# =============================================================================
# Description:
#   Модульный плагин скачивания и конвертации аудиодорожек YouTube в формат MP3
#   с поддержкой инструментов вызова функций ИИ (LLM Function Calling) и действий UI.
#
# File: plugin.py
# Package: plugins.user-plugins.youtube_mp3
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 18:46:00
# =============================================================================

from __future__ import annotations

"""Модульный плагин YouTube MP3 Downloader для AI Assistant."""

import json
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

from header import __root__
from logger import logger
from plugins.base import BasePlugin
from plugins.youtube_mp3.downloader import YouTubeMP3Downloader


class YouTubeMP3Plugin(BasePlugin):
    """Модульный плагин загрузки аудиодорожек YouTube в формате MP3."""

    name: str = "youtube_mp3"
    title: str = "YouTube MP3 Downloader"
    title_i18n: Dict[str, str] = {
        "ru": "YouTube MP3 Загрузчик",
        "en": "YouTube MP3 Downloader",
        "he": "מוריד MP3 מיוטיוב",
    }
    version: str = "1.0.0"
    description: str = (
        "Загрузка аудиодорожек с YouTube в формате MP3 с автоконвертацией через yt-dlp и ffmpeg."
    )
    description_i18n: Dict[str, str] = {
        "ru": "Загрузка аудиодорожек с YouTube в формате MP3 с автоконвертацией через yt-dlp и ffmpeg.",
        "en": "Download YouTube audio tracks in MP3 format with automated yt-dlp & ffmpeg extraction.",
        "he": "הורדת רצועות אודיו מיוטיוב בפורמט MP3 עם המרה אוטומטית באמצעות yt-dlp ו-ffmpeg.",
    }
    icon: str = "🎵"
    category: str = "media"
    enabled: bool = True
    is_system: bool = False
    scope: str = "user"

    def __init__(self, ai_model: Any = None, config: Optional[Dict[str, Any]] = None) -> None:
        """Инициализирует плагин YouTube MP3."""
        cfg = self._load_default_config()
        if config:
            cfg.update(config)
        super().__init__(ai_model=ai_model, config=cfg)

        download_path = self._resolve_download_dir(self.config.get("download_dir"))
        self.downloader = YouTubeMP3Downloader(
            download_dir=download_path,
            default_quality=str(self.config.get("default_quality", "192")),
        )

    def _resolve_download_dir(self, raw_path: Optional[str]) -> Path:
        """Определяет абсолютный путь к папке сохранения аудио."""
        if not raw_path:
            return __root__ / "data" / "downloads" / "music"
        p = Path(raw_path)
        return p if p.is_absolute() else (__root__ / p)

    def _load_default_config(self) -> Dict[str, Any]:
        """Загружает параметры конфигурации по умолчанию."""
        cfg_file = Path(__file__).parent / "config.json"
        if cfg_file.exists():
            try:
                return json.loads(cfg_file.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning(f"[YouTubeMP3Plugin] Ошибка чтения config.json: {exc}")
        return {
            "download_dir": "data/downloads/music",
            "default_quality": "192",
            "embed_metadata": True,
        }

    def update_config(self, new_config: Dict[str, Any]) -> None:
        """Обновляет параметры конфигурации плагина."""
        super().update_config(new_config)
        download_path = self._resolve_download_dir(self.config.get("download_dir"))
        self.downloader.download_dir = download_path
        self.downloader.default_quality = str(self.config.get("default_quality", "192"))
        download_path.mkdir(parents=True, exist_ok=True)

    def get_config_fields(self) -> List[Dict[str, Any]]:
        """Возвращает спецификацию полей настроек для модального окна WebGUI."""
        return [
            {
                "id": "download_dir",
                "label": "Папка сохранения аудио (MP3)",
                "type": "text",
                "default": "data/downloads/music",
                "description": "Относительный или абсолютный путь к каталогу сохранения музыки.",
            },
            {
                "id": "default_quality",
                "label": "Битрейт MP3 по умолчанию (kbps)",
                "type": "select",
                "default": "192",
                "options": [
                    {"value": "128", "label": "128 kbps (Стандартное)"},
                    {"value": "192", "label": "192 kbps (Оптимальное, рекомендовано)"},
                    {"value": "256", "label": "256 kbps (Высокое)"},
                    {"value": "320", "label": "320 kbps (Максимальное качество)"},
                ],
                "description": "Целевой битрейт при конвертации аудиопотока.",
            },
            {
                "id": "embed_metadata",
                "label": "Вшивать метаданные и обложку",
                "type": "boolean",
                "default": True,
                "description": "Добавлять название трека, исполнителя и метатеги в MP3 файл.",
            },
        ]

    def get_tools(self) -> List[Dict[str, Any]]:
        """Возвращает список инструментов для вызова ИИ-агентами."""
        return [
            {
                "name": "download_youtube_mp3",
                "description": (
                    "Скачивает видео с YouTube, извлекает аудиодорожку и сохраняет в формате MP3. "
                    "Возвращает локальный путь к сохранённому файлу, длительность и название трека."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "Полная ссылка на видео YouTube (youtube.com/watch?v=... или youtu.be/...)",
                        },
                        "quality": {
                            "type": "string",
                            "enum": ["128", "192", "256", "320"],
                            "description": "Желаемый битрейт в kbps (по умолчанию 192)",
                        },
                    },
                    "required": ["url"],
                },
            },
            {
                "name": "get_youtube_video_info",
                "description": "Получает метаданные видео YouTube (название, автор, длительность, обложка) без скачивания.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "Ссылка на видео YouTube",
                        }
                    },
                    "required": ["url"],
                },
            },
        ]

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Выполняет вызов зарегистрированного инструмента ИИ."""
        url = arguments.get("url", "")
        if tool_name == "download_youtube_mp3":
            quality = arguments.get("quality", self.config.get("default_quality", "192"))
            embed_meta = bool(self.config.get("embed_metadata", True))
            return await self.downloader.download_mp3(
                url=url,
                quality=str(quality),
                embed_metadata=embed_meta,
            )
        elif tool_name == "get_youtube_video_info":
            return await self.downloader.get_video_info(url=url)
        raise ValueError(f"Неизвестный инструмент: {tool_name}")

    def get_actions(self) -> List[Dict[str, Any]]:
        """Возвращает быстрые действия плагина для отображения в карточке WebGUI."""
        return [
            {
                "id": "check_environment",
                "title": "Проверить yt-dlp и ffmpeg",
                "title_en": "Check Environment",
                "description": "Проверить установку библиотеки yt-dlp и доступность системного ffmpeg.",
                "icon": "bi-check2-circle",
                "variant": "outline-primary",
            },
            {
                "id": "download_audio",
                "title": "Скачать MP3 по ссылке",
                "title_en": "Download MP3 from URL",
                "description": "Скачать трек с YouTube в папку музыки.",
                "icon": "bi-cloud-arrow-down-fill",
                "variant": "primary",
            },
        ]

    async def execute_action(
        self, action_id: str, payload: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Выполняет выбранное действие плагина из веб-интерфейса."""
        params = payload or {}
        if action_id == "check_environment":
            status = self.downloader.is_available()
            msg = (
                "Все компоненты (yt-dlp и ffmpeg) готовы к работе."
                if status["ready"]
                else "Внимание: один из компонентов отсутствует."
            )
            return {"status": "success", "message": msg, "details": status}

        elif action_id == "download_audio":
            url = params.get("url", "")
            if not url:
                raise ValueError("Для скачивания необходимо указать параметр 'url'.")
            quality = str(params.get("quality", self.config.get("default_quality", "192")))
            res = await self.downloader.download_mp3(url=url, quality=quality)
            return {
                "status": "success",
                "message": f"Трек '{res.get('title')}' успешно скачан ({res.get('file_size_mb')} МБ).",
                "result": res,
            }

        raise ValueError(f"Неизвестное действие: {action_id}")

    async def handle(
        self, message: str, **kwargs: Any
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Обрабатывает входящее текстовое сообщение или URL для скачивания.

        Args:
            message (str): Входящее сообщение или ссылка на видео YouTube.
            **kwargs (Any): Дополнительные параметры контекста.

        Yields:
            Dict[str, Any]: События обработки и статус завершения.
        """
        yield {"status": "start", "plugin": self.name}
        yield {
            "status": "complete",
            "text": f"YouTube MP3 Downloader готов к загрузке аудио по запросу: {message}",
        }


def plugin(ai_model: Any = None, config: Optional[Dict[str, Any]] = None) -> YouTubeMP3Plugin:
    """Фабричная функция создания экземпляра плагина."""
    return YouTubeMP3Plugin(ai_model=ai_model, config=config)

