# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api - Router Software
# =============================================================================
# Description:
#   Реализует вспомогательные функции для работы с программным обеспечением.
#   В частности, исправлена функция ``_find_matching_folder``.
#
# File: router_software.py
# Project: ai-windows-admin
# Package: apps.windows.api
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-14 03:09:00
# =============================================================================

"""Router, включающий утилиту поиска соответствующей папки и эндпоинты ИИ ПО.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter
from logger import logger
from apps.windows.api.routers.tab_software_scanner.router_software_ai import router as software_ai_router

router = APIRouter(tags=["Software Utilities"])
router.include_router(software_ai_router)


def _find_matching_folder(app_entry: dict, folders: List[Path]) -> Optional[Path]:
    """Ищет папку, имя которой соответствует полю ``folder`` записи ``app_entry``.

    Если соответствующая папка не найдена, функция логирует отладочное сообщение
    и возвращает ``None``.
    """
    target_name = app_entry.get("folder", "").lower()
    for folder in folders:
        try:
            if folder.name.lower() == target_name:
                return folder
        except Exception:
            continue
    logger.debug("Не найдено соответствующей папки для записи %s", app_entry)
    return None


def init_router() -> APIRouter:
    """Возвращает инициализированный роутер программного обеспечения."""
    return router

__all__ = ["router", "init_router", "_find_matching_folder"]

