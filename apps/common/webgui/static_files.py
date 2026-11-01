# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Common WebGUI Static Files Handler
# =============================================================================
# Description:
#   Универсальный статический обработчик FastAPI для объединения нескольких
#   каталогов WebGUI с поддержкой динамического приоритета по Referer
#   и каскадного поиска в общем репозитории apps/common/webgui.
#
# File: static_files.py
# Project: ai-windows-admin
# Package: apps.common.webgui
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 12:03:00
# =============================================================================

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response


class SmartMultiDirStaticFiles(StaticFiles):
    """Статический файловый обработчик с объединением каталогов.

    Позволяет прозрачно раздавать статические ассеты из каталога конкретного
    приложения с автоматическим fallback на общий каталог apps/common/webgui.
    """

    def __init__(self, *directories: Path | str, **kwargs: Any) -> None:
        """Инициализация обработчика со списком директорий.

        Args:
            *directories: Пути к директориям в порядке приоритета.
            **kwargs: Дополнительные параметры для Starlette StaticFiles.
        """
        valid_dirs = [Path(d).resolve() for d in directories if d]
        first_dir = valid_dirs[0] if valid_dirs else Path(".")
        super().__init__(directory=str(first_dir), **kwargs)
        self.directories: list[Path] = valid_dirs

    def lookup_path(self, path: str) -> tuple[str, Optional[os.stat_result]]:
        """Поиск файла по цепочке директорий в заданном порядке.

        Args:
            path: Относительный путь к запрашиваемому файлу.

        Returns:
            tuple[str, Optional[os.stat_result]]: Полный путь к файлу и его stat,
            либо пустая строка и None в случае отсутствия файла.
        """
        for directory in self.directories:
            if not directory.exists():
                continue
            full_path = os.path.realpath(os.path.join(directory, path))
            if os.path.commonpath([full_path, str(directory)]) == str(directory):
                try:
                    return full_path, os.stat(full_path)
                except (FileNotFoundError, NotADirectoryError):
                    continue
        return "", None

    async def get_response(self, path: str, scope: Any) -> Response:
        """Формирует HTTP-ответ со статическим файлом.

        Args:
            path: Запрашиваемый путь к файлу.
            scope: ASGI scope запроса.

        Returns:
            Response: Ответ со статическим файлом.
        """
        response = await super().get_response(path, scope)

        lower_path = path.lower()
        if lower_path.endswith((".js", ".mjs", ".css", ".html", ".json")):
            response.headers["Cache-Control"] = "no-cache"

        return response

