# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: YouTube MP3 Plugin Unit Tests
# =============================================================================
# Description:
#   Модульные тесты функционала плагина скачивания MP3 с YouTube, валидации URL,
#   проверки системных зависимостей, вызова инструментов ИИ и выполнения действий.
#
# File: test_youtube_mp3.py
# Package: plugins.user-plugins.youtube_mp3.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 18:45:00
# =============================================================================

from __future__ import annotations

"""Модульные тесты плагина youtube_mp3."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from plugins.youtube_mp3.downloader import YouTubeMP3Downloader
from plugins.youtube_mp3.plugin import YouTubeMP3Plugin, plugin


def test_youtube_mp3_plugin_initialization() -> None:
    """Проверяет создание экземпляра плагина и корректность метаданных."""
    plg = plugin()
    assert isinstance(plg, YouTubeMP3Plugin)
    assert plg.name == "youtube_mp3"
    assert plg.category == "media"
    assert plg.scope == "user"
    assert plg.icon == "🎵"

    manifest = plg.get_manifest(lang="ru")
    assert manifest["name"] == "youtube_mp3"
    assert "YouTube MP3" in manifest["title"]
    assert len(manifest["tools"]) == 2
    assert len(manifest["actions"]) == 2
    assert len(manifest["fields"]) == 3


def test_youtube_mp3_environment_check() -> None:
    """Проверяет детектирование yt-dlp и ffmpeg."""
    downloader = YouTubeMP3Downloader()
    env = downloader.is_available()
    assert "yt_dlp_installed" in env
    assert "ffmpeg_available" in env
    assert env["yt_dlp_installed"] is True
    assert env["ffmpeg_available"] is True
    assert env["ready"] is True


def test_youtube_url_validation() -> None:
    """Проверяет валидацию корректных и некорректных ссылок."""
    downloader = YouTubeMP3Downloader()

    # Корректные ссылки
    assert downloader._clean_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert downloader._clean_url("https://youtu.be/dQw4w9WgXcQ")

    # Некорректные ссылки
    with pytest.raises(ValueError, match="не может быть пустым"):
        downloader._clean_url("")

    with pytest.raises(ValueError, match="не является валидным адресом"):
        downloader._clean_url("https://example.com/video")


@pytest.mark.asyncio
async def test_youtube_get_video_info_mock() -> None:
    """Проверяет извлечение метаданных видеоролика с моком yt-dlp."""
    downloader = YouTubeMP3Downloader()

    mock_info = {
        "id": "dQw4w9WgXcQ",
        "title": "Never Gonna Give You Up",
        "uploader": "Rick Astley",
        "duration": 212,
        "thumbnail": "https://img.youtube.com/vi/dQw4w9WgXcQ/0.jpg",
        "view_count": 1500000000,
        "webpage_url": "https://youtu.be/dQw4w9WgXcQ",
    }

    with patch("yt_dlp.YoutubeDL") as mock_ydl_cls:
        instance = MagicMock()
        instance.extract_info.return_value = mock_info
        mock_ydl_cls.return_value.__enter__.return_value = instance

        res = await downloader.get_video_info("https://youtu.be/dQw4w9WgXcQ")
        assert res["id"] == "dQw4w9WgXcQ"
        assert res["title"] == "Never Gonna Give You Up"
        assert res["uploader"] == "Rick Astley"
        assert res["duration_formatted"] == "03:32"


@pytest.mark.asyncio
async def test_youtube_download_mp3_mock(tmp_path: Path) -> None:
    """Проверяет вызов скачивания аудио и конвертации в MP3 с моком yt-dlp."""
    downloader = YouTubeMP3Downloader(download_dir=tmp_path)

    # Создаём фиктивный скачанный MP3 файл
    dummy_mp3 = tmp_path / "Test Track.mp3"
    dummy_mp3.write_bytes(b"MOCK_MP3_CONTENT" * 100)

    mock_info = {
        "title": "Test Track",
        "uploader": "Test Artist",
        "duration": 180,
        "webpage_url": "https://youtu.be/test",
    }

    with patch("yt_dlp.YoutubeDL") as mock_ydl_cls:
        instance = MagicMock()
        instance.extract_info.return_value = mock_info
        mock_ydl_cls.return_value.__enter__.return_value = instance

        res = await downloader.download_mp3(
            url="https://youtu.be/test",
            target_dir=tmp_path,
            quality="192",
        )

        assert res["success"] is True
        assert res["title"] == "Test Track"
        assert res["uploader"] == "Test Artist"
        assert res["quality_kbps"] == "192"
        assert res["file_name"] == "Test Track.mp3"
        assert res["file_size_bytes"] > 0


@pytest.mark.asyncio
async def test_youtube_mp3_plugin_actions_and_tools() -> None:
    """Проверяет исполнение действий и инструментов плагина."""
    plg = plugin()

    # 1. Проверка действия check_environment
    env_res = await plg.execute_action("check_environment")
    assert env_res["status"] == "success"
    assert "details" in env_res

    # 2. Проверка инструмента get_youtube_video_info через мок
    with patch.object(plg.downloader, "get_video_info", return_value={"title": "Mock Video"}):
        tool_res = await plg.execute_tool("get_youtube_video_info", {"url": "https://youtu.be/abc"})
        assert tool_res["title"] == "Mock Video"

    # 3. Проверка обновления конфигурации
    plg.update_config({"default_quality": "320", "download_dir": "data/downloads/custom"})
    assert plg.downloader.default_quality == "320"
