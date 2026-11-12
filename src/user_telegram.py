# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin User Telegram Link Service
# =============================================================================
# Description:
#   Сервис привязки Telegram-аккаунтов к локальным пользователям платформы.
#   Генерирует одноразовые токены верификации, выполняет валидацию и связывание
#   Telegram ID с учетными записями в SQLite.
#
# File: user_telegram.py
# Project: ai-windows-admin
# Package: src
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 14:21:00
# =============================================================================

from __future__ import annotations

from contextlib import contextmanager
import datetime
from pathlib import Path
import secrets
import sqlite3
from typing import Any, Dict, Generator, Optional

from logger import logger


def _utc_now() -> datetime.datetime:
    """Возвращает текущее время UTC."""
    return datetime.datetime.now(datetime.timezone.utc)


class UserTelegramService:
    """Сервис генерации кодов и привязки Telegram-аккаунтов к пользователям."""

    def __init__(self, db_path: Path) -> None:
        """Инициализация сервиса с указанием пути к базе данных пользователей."""
        self.db_path = db_path
        self._init_tables()

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Создает соединение с SQLite в режиме WAL и гарантированно закрывает его."""
        conn = sqlite3.connect(self.db_path, timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=15000;")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_tables(self) -> None:
        """Создает таблицу токенов привязки, если она еще не создана."""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS telegram_link_tokens (
                        token TEXT PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        expires_at TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                    )
                    """
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_tg_tokens_user ON telegram_link_tokens (user_id)")
        except Exception as exc:
            logger.error(f"[UserTelegramService] Ошибка инициализации таблицы токенов: {exc}")

    def get_user_by_telegram_id(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Ищет активного пользователя по его Telegram ID."""
        try:
            with self._get_connection() as conn:
                row = conn.execute(
                    "SELECT * FROM users WHERE telegram_id = ? AND is_active = 1",
                    (int(telegram_id),),
                ).fetchone()
                return dict(row) if row else None
        except Exception as exc:
            logger.error(f"[UserTelegramService] Ошибка поиска по Telegram ID {telegram_id}: {exc}")
            return None

    def generate_link_token(self, user_id: int, ttl_seconds: int = 900) -> str:
        """Генерирует уникальный 8-значный код привязки для пользователя."""
        token = secrets.token_hex(4).upper()
        now = _utc_now()
        expires = now + datetime.timedelta(seconds=ttl_seconds)
        now_str = now.isoformat()
        exp_str = expires.isoformat()

        with self._get_connection() as conn:
            conn.execute("DELETE FROM telegram_link_tokens WHERE user_id = ?", (int(user_id),))
            conn.execute(
                "INSERT INTO telegram_link_tokens (token, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
                (token, int(user_id), exp_str, now_str),
            )

        logger.info(f"[UserTelegramService] Сгенерирован код привязки Telegram для пользователя #{user_id}: {token}")
        return token

    def link_account(self, token: str, telegram_id: int, telegram_username: str = "") -> bool:
        """Привязывает Telegram ID к пользователю по действительному токену."""
        clean_token = token.strip().upper()
        now_str = _utc_now().isoformat()

        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT user_id, expires_at FROM telegram_link_tokens WHERE token = ?",
                (clean_token,),
            ).fetchone()
            if not row:
                logger.warning(f"[UserTelegramService] Код привязки {clean_token} не найден")
                return False

            user_id = row["user_id"]
            expires_at = str(row["expires_at"])
            if expires_at < now_str:
                conn.execute("DELETE FROM telegram_link_tokens WHERE token = ?", (clean_token,))
                logger.warning(f"[UserTelegramService] Код привязки {clean_token} просрочен")
                return False

            conn.execute(
                "UPDATE users SET telegram_id = NULL, telegram_username = NULL WHERE telegram_id = ?",
                (int(telegram_id),),
            )
            conn.execute(
                "UPDATE users SET telegram_id = ?, telegram_username = ?, updated_at = ? WHERE id = ?",
                (int(telegram_id), str(telegram_username or ""), now_str, int(user_id)),
            )
            conn.execute("DELETE FROM telegram_link_tokens WHERE token = ?", (clean_token,))

        logger.info(f"[UserTelegramService] Telegram ID {telegram_id} успешно привязан к пользователю #{user_id}")
        return True

    def unlink_account(self, user_id: int) -> bool:
        """Отвязывает Telegram от профиля пользователя."""
        now_str = _utc_now().isoformat()
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE users SET telegram_id = NULL, telegram_username = NULL, updated_at = ? WHERE id = ?",
                (now_str, int(user_id)),
            )
            conn.execute("DELETE FROM telegram_link_tokens WHERE user_id = ?", (int(user_id),))

        logger.info(f"[UserTelegramService] Telegram отвязан от пользователя #{user_id}")
        return True
