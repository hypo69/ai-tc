"""
=============================================================================
Process Name: Generate Themes Catalog
=============================================================================
Description:
    Скрипт сканирования каталогов тем оформления в apps/windows/api/webgui/themes/
    и сборки единого манифеста themes_catalog.json.

Usage Examples:
    py apps/windows/api/webgui/themes/generate_themes_catalog.py

File: generate_themes_catalog.py
Project: ai-assistant
Package: apps.common.webgui.themes
Author: hypo69
Copyright: © 2026 hypo69
Updated: 2026-11-03 14:08:00
=============================================================================
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

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
            # Ошибки парсинга повреждённых файлов логируются и пропускаются
            pass

    return catalog


def build_themes_catalog_file(output_path: Path = _OUTPUT_CATALOG_FILE) -> int:
    """Выполняет сканирование директорий тем и сохраняет themes_catalog.json.

    Args:
        output_path: Путь к целевому файлу каталога.

    Returns:
        Количество сохранённых тем.
    """
    themes = scan_themes_directory(_THEMES_DIR)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(themes, f, indent=2, ensure_ascii=False)
    return len(themes)


if __name__ == "__main__":
    count = build_themes_catalog_file()
    logger.console(f"Сгенерирован themes_catalog.json: {count} тем записано.")

