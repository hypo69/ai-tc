# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Telegram Bot Single-User Auth Adapter
# =============================================================================
# Description:
#   Легковесный адаптер привязки Telegram-аккаунта для однопользовательского
#   режима без использования устаревшей базы данных users.db и UserManager.
#
# File: user_auth.py
# Package: plugins.telegram_bot
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-30 12:55:00
# =============================================================================

from __future__ import annotations

import json
from pathlib import Path
import time
from typing import Any, Dict, Optional

from header import __root__

_AUTH_FILE = __root__ / "data" / "telegram_auth.json"


def _load_state() -> Dict[str, Any]:
    """Загружает локальное состояние привязки Telegram."""
    if _AUTH_FILE.exists():
        try:
            with open(_AUTH_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_state(state: Dict[str, Any]) -> None:
    """Сохраняет локальное состояние привязки Telegram."""
    try:
        _AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_AUTH_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def link_telegram_account(token: str, tg_id: int, tg_username: str) -> bool:
    """Проверяет одноразовый код и привязывает аккаунт Telegram."""
    state = _load_state()
    saved_token = state.get("pending_token")
    expires = state.get("token_expires_at", 0)
    if saved_token and str(saved_token).strip() == str(token).strip() and time.time() < expires:
        state["telegram_id"] = tg_id
        state["telegram_username"] = tg_username
        state.pop("pending_token", None)
        _save_state(state)
        return True
    return False


def get_user_by_telegram_id(tg_id: int) -> Optional[Dict[str, Any]]:
    """Возвращает профиль пользователя, если Telegram ID привязан."""
    state = _load_state()
    if state.get("telegram_id") == tg_id:
        return {"id": 1, "name": state.get("user_name", "Администратор"), "email": "admin@localhost"}
    return None


def get_user_directory(user_id: int = 1, subfolder: str = "", create: bool = True) -> Path:
    """Возвращает локальный каталог для хранения файлов Telegram (audio, dialogs)."""
    base = __root__ / "data" / "telegram"
    if subfolder:
        base = base / subfolder
    if create:
        base.mkdir(parents=True, exist_ok=True)
    return base
