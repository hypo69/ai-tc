# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: YouTube MP3 Plugin Package Initialization
# =============================================================================
# Description:
#   Экспортирует класс плагина YouTubeMP3Plugin, загрузчик и фабричную функцию.
#
# File: __init__.py
# Package: plugins.youtube_mp3
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 18:43:00
# =============================================================================

from __future__ import annotations

"""Пакет плагина YouTube MP3 Downloader."""

from plugins.youtube_mp3.downloader import YouTubeMP3Downloader
from plugins.youtube_mp3.plugin import YouTubeMP3Plugin, plugin

__all__ = [
    "YouTubeMP3Plugin",
    "YouTubeMP3Downloader",
    "plugin",
]
