# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Utils - Common Helpers
# =============================================================================
# Description:
#   Общие вспомогательные функции (чтение конфигурации, вывод в консоль
#   через logger.console, форматирование и безопасная работа с JSON).
#
# File: common.py
# Project: ai-windows-admin
# Package: src.utils
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-13 20:42:00
# =============================================================================

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Union

try:
    from logger import logger
except ImportError:
    import logging
    logger = logging.getLogger("utils_common")


def console_log(message: str) -> None:
    """Выводит информационное сообщение исключительно в консоль без записи в лог-файл.

    Args:
        message: Текст сообщения для отображения пользователю.
    """
    if hasattr(logger, "console"):
        logger.console(message)
    else:
        logger.info(message)


def load_json_config(
    file_path: Union[str, Path],
    default: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Безопасно считывает JSON-конфигурацию с обработкой ошибок и возвратом значений по умолчанию.

    Args:
        file_path: Путь к файлу конфигурации.
        default: Резервный словарь, если файл отсутствует или поврежден.

    Returns:
        Словарь параметров конфигурации.
    """
    path = Path(file_path)
    fallback = default if default is not None else {}
    if not path.is_file():
        return fallback

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else fallback
    except Exception as err:
        logger.warning(f"[CommonUtils] Не удалось распарсить JSON {path}: {err}")
        return fallback


def save_json_file(
    file_path: Union[str, Path],
    data: Any,
    indent: int = 2,
    ensure_ascii: bool = False,
) -> bool:
    """Безопасно сохраняет данные в JSON файл с созданием директорий при необходимости.

    Args:
        file_path: Целевой путь к файлу.
        data: Данные для сериализации.
        indent: Отступ форматирования JSON.
        ensure_ascii: Экранировать ли не-ASCII символы.

    Returns:
        True при успешном сохранении, иначе False.
    """
    try:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii)
        return True
    except Exception as err:
        logger.error(f"[CommonUtils] Ошибка записи JSON {file_path}: {err}")
        return False


def get_utc_timestamp_iso() -> str:
    """Возвращает текущую временную метку UTC в формате ISO 8601.

    Returns:
        Строка вида 'YYYY-MM-DDTHH:MM:SS.mmmmmmZ'.
    """
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

