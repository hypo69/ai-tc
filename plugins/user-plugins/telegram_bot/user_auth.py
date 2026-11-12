# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Telegram Bot Single-User Auth Adapter
# =============================================================================
# Description:
#   Легковесный адаптер привязки Telegram-аккаунта и хранения выбранной рабочей
#   области пользователя для однопользовательского режима с потокобезопасной
#   атомарной записью и защитой от Path Traversal.
#
# File: user_auth.py
# Package: plugins.telegram_bot
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 16:45:00
# =============================================================================

from __future__ import annotations

import hmac
import json
import os
from pathlib import Path
import threading
import time
from typing import Any, Dict, List, Optional

from header import __root__

_AUTH_FILE = __root__ / "data" / "telegram_auth.json"
_AUTH_LOCK = threading.RLock()


def _load_state() -> Dict[str, Any]:
    """Загружает локальное состояние привязки Telegram."""
    with _AUTH_LOCK:
        if _AUTH_FILE.exists():
            try:
                with open(_AUTH_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data if isinstance(data, dict) else {}
            except Exception:
                pass
        return {}


def _save_state(state: Dict[str, Any]) -> None:
    """Атомарно сохраняет локальное состояние привязки Telegram."""
    with _AUTH_LOCK:
        try:
            _AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = _AUTH_FILE.with_suffix(".json.tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, _AUTH_FILE)
        except Exception:
            pass


def link_telegram_account(token: str, tg_id: int, tg_username: str) -> bool:
    """Проверяет одноразовый код и привязывает аккаунт Telegram."""
    with _AUTH_LOCK:
        state = _load_state()
        saved_token = str(state.get("pending_token") or "").strip()
        given_token = str(token or "").strip()
        expires = float(state.get("token_expires_at") or 0)
        if saved_token and hmac.compare_digest(saved_token, given_token) and time.time() < expires:
            state["telegram_id"] = tg_id
            state["telegram_username"] = tg_username
            state.pop("pending_token", None)
            _save_state(state)
            return True
        return False


def get_user_by_telegram_id(tg_id: int, admin_ids: Optional[List[int]] = None) -> Optional[Dict[str, Any]]:
    """Возвращает профиль пользователя, если Telegram ID привязан или находится в списке администраторов."""
    state = _load_state()
    admins = set(state.get("admin_telegram_ids") or [])
    if admin_ids:
        admins.update(admin_ids)
    if state.get("telegram_id") == tg_id or tg_id in admins:
        return {"id": 1, "name": state.get("user_name", "Администратор"), "email": "admin@localhost"}
    return None


def get_user_workspace(tg_id: int) -> Optional[str]:
    """Возвращает идентификатор активной рабочей области для пользователя Telegram."""
    state = _load_state()
    user_ws_map = state.get("user_workspaces")
    if isinstance(user_ws_map, dict) and str(tg_id) in user_ws_map:
        return str(user_ws_map[str(tg_id)])
    selected = state.get("selected_workspace")
    return str(selected) if selected else None


def set_user_workspace(tg_id: int, workspace_id: str) -> None:
    """Сохраняет выбранную рабочую область для пользователя Telegram."""
    with _AUTH_LOCK:
        state = _load_state()
        if "user_workspaces" not in state or not isinstance(state["user_workspaces"], dict):
            state["user_workspaces"] = {}
        clean_id = str(workspace_id).strip()
        state["user_workspaces"][str(tg_id)] = clean_id
        state["selected_workspace"] = clean_id
        _save_state(state)


def get_user_directory(user_id: int = 1, subfolder: str = "", create: bool = True) -> Path:
    """Возвращает локальный каталог для хранения файлов Telegram (audio, dialogs) с защитой от Path Traversal."""
    base = (__root__ / "data" / "telegram").resolve()
    target = base
    if subfolder:
        clean_sub = Path(subfolder).name
        target = (base / clean_sub).resolve()
        target.relative_to(base)
    if create:
        target.mkdir(parents=True, exist_ok=True)
    return target
