# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Single-User Settings
# =============================================================================
# Description:
#   Модуль управления пользовательскими настройками в однопользовательском режиме.
#   Обеспечивает потокобезопасное хранение и обновление конфигураций моделей,
#   избранных моделей и системных инструкций в data/user_settings.json.
#
# File: user_settings.py
# Package: src
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-15 18:55:00
# =============================================================================

from __future__ import annotations

import json
import os
from pathlib import Path
import threading
from typing import Any, Dict

from header import __root__

_SETTINGS_FILE = __root__ / "data" / "user_settings.json"
_SETTINGS_LOCK = threading.RLock()


def get_user_settings(user_id: int = 1) -> Dict[str, Any]:
    """Возвращает пользовательские настройки из локального файла.

    Args:
        user_id (int): Идентификатор пользователя (зарезервирован, по умолчанию 1).

    Returns:
        Dict[str, Any]: Словарь пользовательских настроек.
    """
    with _SETTINGS_LOCK:
        if _SETTINGS_FILE.exists():
            try:
                with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception:
                pass
        return {}


def update_user_settings(user_id: int = 1, **settings: Any) -> bool:
    """Обновляет пользовательские настройки и атомарно сохраняет их на диск.

    Args:
        user_id (int): Идентификатор пользователя (зарезервирован, по умолчанию 1).
        **settings: Пары ключ-значение для обновления.

    Returns:
        bool: True в случае успешной записи, иначе False.
    """
    with _SETTINGS_LOCK:
        current = get_user_settings(user_id)
        current.update(settings)
        try:
            _SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = _SETTINGS_FILE.with_suffix(".json.tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(current, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, _SETTINGS_FILE)
            return True
        except Exception:
            return False


__all__ = ["get_user_settings", "update_user_settings"]
