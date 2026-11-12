# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Генератор каталога тем оформления (Themes Catalog Builder)
# =============================================================================
# Description:
#   Скрипт сканирования каталогов тем оформления в apps/common/webgui/themes/
#   и атомарной сборки единого манифеста themes_catalog.json.
#
# Examples:
#   py apps/common/webgui/themes/generate_themes_catalog.py
#
# File: generate_themes_catalog.py
# Project: ai-windows-admin
# Package: apps.common.webgui.themes
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 14:31:55
# =============================================================================

from __future__ import annotations
"""Генератор манифеста тем оформления `themes_catalog.json`."""

import json
import os
from pathlib import Path
from typing import Any, Dict, List

from logger import logger

_THEMES_DIR = Path(__file__).resolve().parent
_OUTPUT_CATALOG_FILE = _THEMES_DIR / "themes_catalog.json"


def scan_themes_directory(themes_root: Path = _THEMES_DIR) -> List[Dict[str, Any]]:
    """Сканирует директорию тем и собирает метаданные из каждого theme.json.

    Args:
        themes_root: Корневой путь каталога тем оформления.

    Returns:
        Список словарей с метаданными и токенами найденных тем.
    """
    catalog: List[Dict[str, Any]] = []

    if not themes_root.is_dir():
        return catalog

    for item in sorted(themes_root.iterdir()):
        if not item.is_dir() or item.name.startswith((".", "~", "_")):
            continue

        theme_file = item / "theme.json"
        if not theme_file.is_file():
            continue

        try:
            with open(theme_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "id" in data:
                    catalog.append({
                        "id": data["id"],
                        "name": data.get("name", data["id"]),
                        "nameEn": data.get("nameEn", data.get("name", data["id"])),
                        "category": data.get("category", "dark"),
                        "baseType": data.get("baseType", data.get("category", "dark")),
                        "icon": data.get("icon", "bi-palette"),
                        "iconColor": data.get("iconColor", "text-info"),
                        "description": data.get("description", ""),
                        "tokens": data.get("tokens", None),
                    })
        except Exception as ex:
            logger.warning(f"[ThemesCatalog] Ошибка разбора файла темы {theme_file}: {ex}")

    return catalog


def build_themes_catalog_file(output_path: Path = _OUTPUT_CATALOG_FILE) -> int:
    """Выполняет сканирование директорий тем и атомарно сохраняет themes_catalog.json.

    Args:
        output_path: Путь к целевому файлу каталога.

    Returns:
        Количество сохранённых тем.
    """
    themes = scan_themes_directory(_THEMES_DIR)
    resolved_out = output_path.resolve()
    resolved_out.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = resolved_out.with_suffix(".json.tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(themes, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, resolved_out)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
    return len(themes)


if __name__ == "__main__":
    count = build_themes_catalog_file()
    logger.console(f"Сгенерирован themes_catalog.json: {count} тем записано.")
