# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows DB - System Knowledge Paths
# =============================================================================
# Description:
#   Динамическое разрешение путей к базе данных системных подсказок WikiLLM
#   (%ProgramData%\{app_name}\windows\knowledge.db / knowelege.db)
#   на основе настроек из конфигурационных файлов config.json.
#
# Usage Examples:
#   Python API:
#     from apps.windows.db.paths import resolve_system_knowledge_db_path
#
#     db_path = resolve_system_knowledge_db_path()
#     print(f"Путь к базе знаний: {db_path}")
#
# File: paths.py
# Project: ai-windows-admin
# Package: apps.windows.db
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 17:15:00
# =============================================================================

from __future__ import annotations

"""Модуль динамического разрешения путей к базе данных системных подсказок WikiLLM."""

import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


def get_config_search_paths() -> list[Path]:
    """Возвращает список путей для поиска файлов конфигурации проекта.

    Returns:
        list[Path]: Список существующих или потенциальных файлов конфигурации.
    """
    candidates = [
        Path("apps/windows/api/config.json"),
        Path("config.json"),
        Path("apps/windows/wikillm/config.json"),
    ]
    return [p for p in candidates if p.is_file()]


def load_merged_system_config() -> Dict[str, Any]:
    """Считывает и объединяет параметры конфигурации из доступных config.json.

    Returns:
        Dict[str, Any]: Объединенный словарь параметров конфигурации.
    """
    merged: Dict[str, Any] = {}
    for cfg_path in get_config_search_paths():
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    merged.update(data)
        except Exception as ex:
            logger.debug(f"[Paths] Ошибка чтения {cfg_path}: {ex}")
    return merged


def get_dynamic_path_config() -> Dict[str, str]:
    """Извлекает базовые переменные путей из конфигурации или системного окружения.

    Динамические параметры:
      - programdata: путь к директории %ProgramData% (настраивается в config.json: paths.programdata)
      - app_name: имя приложения/подсистемы (настраивается в config.json: paths.app_name или app_name)
      - template: шаблон пути к базе системных подсказок

    Returns:
        Dict[str, str]: Словарь с параметрами 'programdata', 'app_name', 'template'.
    """
    cfg = load_merged_system_config()
    paths_cfg = cfg.get("paths", {})

    # 1. Разрешение programdata
    raw_programdata = paths_cfg.get("programdata") or os.environ.get("ProgramData") or os.environ.get("ALLUSERSPROFILE") or "C:/ProgramData"
    expanded_programdata = os.path.expandvars(str(raw_programdata)).replace("\\", "/")

    # 2. Разрешение app_name
    app_name = (
        paths_cfg.get("app_name")
        or cfg.get("app_name")
        or cfg.get("app", {}).get("app_name")
        or os.environ.get("APP_NAME")
        or "ai-tc"
    )

    # 3. Шаблон пути к базе знаний подсказок
    db_template = (
        paths_cfg.get("system_knowledge_db")
        or cfg.get("database", {}).get("sqlite", {}).get("path")
        or cfg.get("wikillm", {}).get("db_path")
        or "%ProgramData%/{app_name}/windows/knowledge.db"
    )

    return {
        "programdata": expanded_programdata,
        "app_name": str(app_name),
        "template": str(db_template),
    }


def resolve_system_knowledge_db_path(raw_path: Optional[str] = None) -> Path:
    """Разрешает динамический путь к файлу базы данных подсказок по системе.

    Выполняет подстановку динамических переменных:
      - %ProgramData% / {programdata}
      - {app_name} / %APP_NAME%
      - любых других системных переменных среды через expandvars.

    Также поддерживает поиск файла с вариативным именем (knowledge.db / knowelege.db)
    и автоматическое копирование исходных данных из data/windows_wikillm/knowledge.db
    при первичном создании целевого файла в %ProgramData%.

    Args:
        raw_path: Явно переданный путь или шаблон (опционально).

    Returns:
        Path: Абсолютный разрешенный путь к файлу базы данных SQLite.
    """
    dyn_cfg = get_dynamic_path_config()
    template = raw_path if (raw_path and str(raw_path).strip()) else dyn_cfg["template"]

    # Подстановка динамических параметров
    resolved_str = template.replace("{programdata}", dyn_cfg["programdata"])
    resolved_str = resolved_str.replace("{app_name}", dyn_cfg["app_name"])
    resolved_str = resolved_str.replace("%ProgramData%", dyn_cfg["programdata"])
    resolved_str = resolved_str.replace("%programdata%", dyn_cfg["programdata"])
    resolved_str = resolved_str.replace("%APP_NAME%", dyn_cfg["app_name"])
    resolved_str = resolved_str.replace("%app_name%", dyn_cfg["app_name"])
    resolved_str = os.path.expandvars(resolved_str)

    target_path = Path(resolved_str).resolve()

    # Если файл уже существует по целевому пути
    if target_path.is_file():
        return target_path

    # Проверка альтернативного написания (knowelege.db vs knowledge.db) в той же директории
    parent_dir = target_path.parent
    if parent_dir.is_dir():
        alt_names = ["knowledge.db", "knowelege.db"]
        for alt in alt_names:
            candidate = parent_dir / alt
            if candidate.is_file():
                return candidate

    # Автоматическое создание целевой директории
    try:
        parent_dir.mkdir(parents=True, exist_ok=True)
    except Exception as ex:
        logger.warning(f"[Paths] Не удалось создать директорию {parent_dir}: {ex}")

    # Первичная миграция: если целевой файл отсутствует, но есть исходный файл в data/
    legacy_candidates = [
        Path("data/windows_wikillm/knowledge.db"),
        Path("data/windows_wikillm/knowelege.db"),
        Path("data/wikillm.db"),
    ]
    for leg in legacy_candidates:
        if leg.is_file():
            try:
                shutil.copy2(leg, target_path)
                logger.info(f"[Paths] Скопирована исходная база подсказок: {leg} -> {target_path}")
                break
            except Exception as ex:
                logger.warning(f"[Paths] Ошибка копирования {leg} -> {target_path}: {ex}")

    return target_path
