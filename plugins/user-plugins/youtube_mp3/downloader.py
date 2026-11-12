# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: YouTube MP3 Downloader Engine
# =============================================================================
# Description:
#   Движок загрузки и конвертации аудиодорожек YouTube в формат MP3
#   с использованием библиотеки yt-dlp и утилиты ffmpeg.
#
# File: downloader.py
# Package: plugins.user-plugins.youtube_mp3
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 16:45:00
# =============================================================================

from __future__ import annotations

"""Модуль взаимодействия с yt-dlp для загрузки аудио и метаданных YouTube."""

import asyncio
from pathlib import Path
import re
import shutil
from typing import Any, Dict, Optional

from header import __root__
from logger import logger

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

_YOUTUBE_HOST_RE = re.compile(r"(youtube\.com|youtu\.be)", re.IGNORECASE)


class YouTubeMP3Downloader:
    """Сервис загрузки аудиопотоков YouTube и конвертации в формат MP3."""

    def __init__(self, download_dir: Optional[Path] = None, default_quality: str = "192") -> None:
        """Инициализирует загрузчик.

        Args:
            download_dir (Optional[Path]): Каталог для сохранения аудиофайлов.
            default_quality (str): Битрейт MP3 по умолчанию ('128', '192', '256', '320').
        """
        self.download_dir = download_dir or (__root__ / "data" / "downloads" / "music")
        self.default_quality = str(default_quality)
        self.download_dir.mkdir(parents=True, exist_ok=True)

    def is_available(self) -> Dict[str, Any]:
        """Проверяет доступность библиотеки yt-dlp и системного ffmpeg.

        Returns:
            Dict[str, Any]: Словарь со статусами компонентов.
        """
        ffmpeg_bin = shutil.which("ffmpeg")
        return {
            "yt_dlp_installed": yt_dlp is not None,
            "ffmpeg_available": ffmpeg_bin is not None,
            "ffmpeg_path": ffmpeg_bin,
            "ready": (yt_dlp is not None and ffmpeg_bin is not None),
        }

    def _clean_url(self, url: str) -> str:
        """Валидирует и нормализует ссылку YouTube."""
        clean = (url or "").strip()
        if not clean:
            raise ValueError("URL видео не может быть пустым.")
        if not _YOUTUBE_HOST_RE.search(clean):
            raise ValueError(f"Ссылка не является валидным адресом YouTube: '{clean}'")
        return clean

    def _extract_info_sync(self, url: str) -> Dict[str, Any]:
        """Синхронно извлекает метаданные видео без скачивания потока."""
        if yt_dlp is None:
            raise RuntimeError("Библиотека yt-dlp не установлена.")

        clean_url = self._clean_url(url)
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "skip_download": True,
            "socket_timeout": 15,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(clean_url, download=False)
            if not info:
                raise RuntimeError("Не удалось получить метаданные видео.")

            return {
                "id": info.get("id", ""),
                "title": info.get("title", "Unknown Title"),
                "uploader": info.get("uploader", "Unknown Artist"),
                "duration": info.get("duration", 0),
                "duration_formatted": self._format_duration(info.get("duration", 0)),
                "thumbnail": info.get("thumbnail", ""),
                "view_count": info.get("view_count", 0),
                "webpage_url": info.get("webpage_url", clean_url),
            }

    async def get_video_info(self, url: str) -> Dict[str, Any]:
        """Асинхронно получает метаданные видеоролика."""
        return await asyncio.to_thread(self._extract_info_sync, url)

    def _download_mp3_sync(
        self,
        url: str,
        target_dir: Optional[Path] = None,
        quality: Optional[str] = None,
        embed_metadata: bool = True,
    ) -> Dict[str, Any]:
        """Синхронно скачивает аудиопоток и преобразует в MP3."""
        if yt_dlp is None:
            raise RuntimeError("Библиотека yt-dlp не установлена.")

        out_dir = target_dir or self.download_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        kbps = str(quality or self.default_quality)
        clean_url = self._clean_url(url)

        # Шаблон пути сохранения
        out_tmpl = str(out_dir / "%(title)s.%(ext)s")

        postprocessors: list[dict[str, Any]] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": kbps,
            }
        ]
        if embed_metadata:
            postprocessors.append({"key": "FFmpegMetadata", "add_metadata": True})

        ydl_opts: Dict[str, Any] = {
            "format": "bestaudio/best",
            "outtmpl": out_tmpl,
            "postprocessors": postprocessors,
            "quiet": True,
            "no_warnings": True,
            "windowsfilenames": True,
            "socket_timeout": 20,
        }

        ffmpeg_bin = shutil.which("ffmpeg")
        if ffmpeg_bin:
            ydl_opts["ffmpeg_location"] = str(Path(ffmpeg_bin).parent)

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info(f"[YouTubeMP3] Запуск загрузки аудио: {clean_url} (качество: {kbps}k)")
            info = ydl.extract_info(clean_url, download=True)
            if not info:
                raise RuntimeError("Ошибка извлечения данных при загрузке.")

            title = info.get("title", "audio")
            # Находим итоговый сохранённый MP3 файл
            # yt-dlp заменяет запрещённые символы в имени
            expected_mp3 = out_dir / f"{title}.mp3"
            actual_file: Optional[Path] = None

            if expected_mp3.exists():
                actual_file = expected_mp3
            else:
                # Поиск свежего mp3 файла в директории выгрузки
                mp3_files = sorted(out_dir.glob("*.mp3"), key=lambda p: p.stat().st_mtime, reverse=True)
                if mp3_files:
                    actual_file = mp3_files[0]

            file_path_str = str(actual_file) if actual_file else ""
            file_size_bytes = actual_file.stat().st_size if actual_file and actual_file.exists() else 0

            return {
                "success": True,
                "title": title,
                "uploader": info.get("uploader", "Unknown Artist"),
                "duration": info.get("duration", 0),
                "duration_formatted": self._format_duration(info.get("duration", 0)),
                "quality_kbps": kbps,
                "file_path": file_path_str,
                "file_name": actual_file.name if actual_file else "",
                "file_size_bytes": file_size_bytes,
                "file_size_mb": round(file_size_bytes / (1024 * 1024), 2),
                "webpage_url": info.get("webpage_url", clean_url),
            }

    async def download_mp3(
        self,
        url: str,
        target_dir: Optional[Path] = None,
        quality: Optional[str] = None,
        embed_metadata: bool = True,
    ) -> Dict[str, Any]:
        """Асинхронно скачивает YouTube видео в виде аудиофайла MP3."""
        return await asyncio.to_thread(
            self._download_mp3_sync,
            url=url,
            target_dir=target_dir,
            quality=quality,
            embed_metadata=embed_metadata,
        )

    @staticmethod
    def _format_duration(seconds: int) -> str:
        """Форматирует длительность в формат ММ:СС или ЧЧ:ММ:СС."""
        if not seconds:
            return "00:00"
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"
