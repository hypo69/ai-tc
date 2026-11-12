# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin User Manager
# =============================================================================
# Description:
#   Менеджер пользователей и изолированных персональных хранилищ платформы.
#   Управляет учетными записями, криптографическим хешированием паролей (scrypt),
#   квотами и каталогами данных (data/users/<id>/).
#
# File: user_manager.py
# Project: ai-windows-admin
# Package: src
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 14:21:00
# =============================================================================

from __future__ import annotations

import base64
from contextlib import contextmanager
import datetime
import hashlib
import hmac
import json
import mimetypes
import os
from pathlib import Path
import secrets
import shutil
import sqlite3
import threading
from typing import Any, Dict, Generator, List, Optional

from logger import logger

_DEFAULT_QUOTA_BYTES = 10 * 1024 * 1024 * 1024  # 10 ГБ по умолчанию
_MAX_IMAGE_PREVIEW_BYTES = 20 * 1024 * 1024     # 20 МБ для превью картинок
_MAX_TEXT_PREVIEW_BYTES = 500 * 1024            # 500 КБ для текстового превью


def _utc_now_iso() -> str:
    """Возвращает текущее время UTC в формате ISO 8601."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def hash_password(password: str) -> str:
    """Хеширует пароль алгоритмом scrypt с уникальной солью (SYSTEM_ENGINEERING § 5.3)."""
    if not password:
        return ""
    if password.startswith("scrypt$"):
        return password
    salt = secrets.token_hex(16)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt.encode("ascii"),
        n=16384,
        r=8,
        p=1,
        dklen=32,
    )
    return f"scrypt${salt}${derived.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Проверяет пароль против сохранённого scrypt-хеша за константное время."""
    if not password or not stored_hash:
        return False
    if not stored_hash.startswith("scrypt$"):
        return hmac.compare_digest(password, stored_hash)
    parts = stored_hash.split("$")
    if len(parts) != 3:
        return False
    _, salt, expected_hex = parts
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt.encode("ascii"),
        n=16384,
        r=8,
        p=1,
        dklen=32,
    )
    return hmac.compare_digest(derived.hex(), expected_hex)


def _format_bytes(size: int) -> str:
    """Форматирует размер в байтах в человекочитаемую строку."""
    if size < 1024:
        return f"{size} B"
    for unit in ["KB", "MB", "GB", "TB"]:
        size_f = size / 1024.0
        if size_f < 1024.0 or unit == "TB":
            return f"{size_f:.1f} {unit}"
        size = int(size_f)
    return f"{size} B"


class UserManager:
    """Менеджер пользователей и персональных хранилищ."""

    def __init__(self, root_dir: Optional[Path] = None) -> None:
        """Инициализация менеджера пользователей.

        Args:
            root_dir: Корневой каталог проекта.
        """
        if root_dir is None:
            root_dir = Path(__file__).resolve().parent.parent
        self.root_dir = root_dir
        self.data_dir = self.root_dir / "data"
        self.users_dir = self.data_dir / "users"
        self.db_path = self.data_dir / "users.db"
        self._lock = threading.RLock()

        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.users_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()
        from src.user_telegram import UserTelegramService
        self._telegram_service = UserTelegramService(self.db_path)

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Открывает соединение с SQLite в режиме WAL и гарантированно закрывает дескриптор."""
        conn = sqlite3.connect(self.db_path, timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=15000;")
        conn.execute("PRAGMA foreign_keys=ON;")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Инициализирует таблицы базы данных и создает администратора по умолчанию."""
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    password_hash TEXT DEFAULT '',
                    role TEXT DEFAULT 'user',
                    is_admin INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    is_email_verified INTEGER DEFAULT 1,
                    telegram_id INTEGER DEFAULT NULL,
                    telegram_username TEXT DEFAULT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id INTEGER PRIMARY KEY,
                    settings_json TEXT DEFAULT '{}',
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users (telegram_id)")

            cursor = conn.execute("SELECT COUNT(*) FROM users")
            count = cursor.fetchone()[0]
            if count == 0:
                now_str = _utc_now_iso()
                conn.execute(
                    """
                    INSERT INTO users (
                        id, email, name, role, is_admin, is_active, is_email_verified, created_at, updated_at
                    ) VALUES (
                        1, 'admin@cli.local', 'Admin', 'admin', 1, 1, 1, ?, ?
                    )
                    """,
                    (now_str, now_str),
                )
                conn.execute(
                    """
                    INSERT INTO user_settings (user_id, settings_json, updated_at)
                    VALUES (1, '{}', ?)
                    """,
                    (now_str,),
                )

        self.ensure_user_storage(1)

    def ensure_user_storage(self, user_id: int) -> Path:
        """Создает и подготавливает изолированный каталог хранилища пользователя."""
        user_path = self.users_dir / str(int(user_id))
        subdirs = ["files", "rag", "profile", "temp"]
        for sub in subdirs:
            (user_path / sub).mkdir(parents=True, exist_ok=True)

        welcome_file = user_path / "files" / "welcome.md"
        if not welcome_file.exists():
            try:
                welcome_content = (
                    f"# Каталог пользователя #{user_id}\n\n"
                    "Персональное хранилище данных пользователя AI Windows Admin.\n\n"
                    "Разделы:\n"
                    "- `files/` — документы и рабочие файлы\n"
                    "- `rag/` — базы знаний и векторные индексы\n"
                    "- `profile/` — настройки и профиль пользователя\n"
                    "- `temp/` — временные файлы сессий\n"
                )
                welcome_file.write_text(welcome_content, encoding="utf-8")
            except Exception as exc:
                logger.debug(f"[UserManager] Не удалось создать welcome.md: {exc}")

        return user_path

    def get_all_users(self, active_only: bool = False) -> List[Dict[str, Any]]:
        """Возвращает список всех зарегистрированных пользователей."""
        query = "SELECT * FROM users"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY id ASC"

        with self._get_connection() as conn:
            rows = conn.execute(query).fetchall()
            return [dict(r) for r in rows]

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Возвращает данные пользователя по его идентификатору."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (int(user_id),)).fetchone()
            return dict(row) if row else None

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Возвращает данные пользователя по адресу электронной почты."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()
            return dict(row) if row else None

    def user_exists(self, email: str) -> bool:
        """Проверяет существование пользователя по адресу электронной почты."""
        return self.get_user_by_email(email) is not None

    def get_user_by_telegram_id(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Возвращает данные пользователя по его Telegram ID."""
        return self._telegram_service.get_user_by_telegram_id(telegram_id)

    def generate_telegram_link_token(self, user_id: int, ttl_seconds: int = 900) -> str:
        """Генерирует одноразовый код для привязки Telegram к аккаунту."""
        return self._telegram_service.generate_link_token(user_id, ttl_seconds)

    def link_telegram_account(self, token: str, telegram_id: int, telegram_username: str = "") -> bool:
        """Привязывает Telegram ID к пользователю по коду."""
        return self._telegram_service.link_account(token, telegram_id, telegram_username)

    def unlink_telegram_account(self, user_id: int) -> bool:
        """Отвязывает Telegram-аккаунт от профиля пользователя."""
        return self._telegram_service.unlink_account(user_id)

    def get_user_directory(self, user_id: int, subfolder: Optional[str] = "", create: bool = True) -> Path:
        """Возвращает изолированную директорию хранилища пользователя или её подпапку с защитой от Path Traversal."""
        base = self.ensure_user_storage(user_id).resolve()
        if subfolder:
            clean_sub = subfolder.replace("\\", "/").strip().lstrip("/")
            target = (base / clean_sub).resolve()
            try:
                target.relative_to(base)
            except ValueError as exc:
                raise ValueError(f"Недопустимая подпапка пользователя: {subfolder}") from exc
            if create:
                target.mkdir(parents=True, exist_ok=True)
            return target
        return base

    def create_user_admin(
        self,
        email: str,
        name: str,
        password: str = "",
        role: str = "user",
        is_admin: int = 0,
        is_active: int = 1,
        is_email_verified: int = 1,
    ) -> Optional[int]:
        """Создает нового пользователя с криптографическим хешированием пароля."""
        now_str = _utc_now_iso()
        email_clean = email.strip().lower()
        pw_hash = hash_password(password) if password else ""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO users (
                        email, name, password_hash, role, is_admin, is_active, is_email_verified, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (email_clean, name.strip(), pw_hash, role, is_admin, is_active, is_email_verified, now_str, now_str),
                )
                user_id = cursor.lastrowid
                conn.execute(
                    "INSERT INTO user_settings (user_id, settings_json, updated_at) VALUES (?, '{}', ?)",
                    (user_id, now_str),
                )

            if user_id:
                self.ensure_user_storage(int(user_id))
            return user_id
        except Exception as exc:
            logger.error(f"[UserManager] Ошибка создания пользователя {email}: {exc}")
            return None

    def update_user(self, user_id: int, **updates: Any) -> bool:
        """Обновляет данные существующего пользователя."""
        if not updates:
            return True
        allowed_fields = {
            "name", "email", "role", "is_admin", "is_active",
            "is_email_verified", "telegram_id", "telegram_username",
        }
        filtered = {k: v for k, v in updates.items() if k in allowed_fields}
        if not filtered:
            return True

        filtered["updated_at"] = _utc_now_iso()
        set_clause = ", ".join(f"{k} = ?" for k in filtered.keys())
        values = list(filtered.values()) + [int(user_id)]

        try:
            with self._get_connection() as conn:
                conn.execute(f"UPDATE users SET {set_clause} WHERE id = ?", values)
            return True
        except Exception as exc:
            logger.error(f"[UserManager] Ошибка обновления пользователя {user_id}: {exc}")
            return False

    def update_user_password(self, user_id: int, password: str) -> bool:
        """Обновляет пароль пользователя с хешированием через scrypt."""
        now_str = _utc_now_iso()
        pw_hash = hash_password(password)
        try:
            with self._get_connection() as conn:
                conn.execute(
                    "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                    (pw_hash, now_str, int(user_id)),
                )
            return True
        except Exception as exc:
            logger.error(f"[UserManager] Ошибка изменения пароля пользователя {user_id}: {exc}")
            return False

    def delete_user(self, user_id: int) -> bool:
        """Удаляет пользователя из базы данных."""
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM user_settings WHERE user_id = ?", (int(user_id),))
                conn.execute("DELETE FROM users WHERE id = ?", (int(user_id),))
            return True
        except Exception as exc:
            logger.error(f"[UserManager] Ошибка удаления пользователя {user_id}: {exc}")
            return False

    def get_user_settings(self, user_id: int) -> Dict[str, Any]:
        """Возвращает настройки пользователя."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT settings_json FROM user_settings WHERE user_id = ?", (int(user_id),)).fetchone()
            if row and row[0]:
                try:
                    return json.loads(row[0])
                except Exception as exc:
                    logger.warning(f"[UserManager] Поврежден JSON настроек пользователя {user_id}: {exc}")
        return {}

    def update_user_settings(self, user_id: int, **settings: Any) -> bool:
        """Атомарно обновляет настройки пользователя в рамках одной транзакции (защита от Lost Update)."""
        now_str = _utc_now_iso()
        try:
            with self._lock, self._get_connection() as conn:
                row = conn.execute(
                    "SELECT settings_json FROM user_settings WHERE user_id = ?",
                    (int(user_id),),
                ).fetchone()
                current: Dict[str, Any] = {}
                if row and row[0]:
                    try:
                        current = json.loads(row[0])
                    except Exception:
                        current = {}
                current.update(settings)
                data_str = json.dumps(current, ensure_ascii=False)
                conn.execute(
                    """
                    INSERT INTO user_settings (user_id, settings_json, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET settings_json = excluded.settings_json, updated_at = excluded.updated_at
                    """,
                    (int(user_id), data_str, now_str),
                )
            return True
        except Exception as exc:
            logger.error(f"[UserManager] Ошибка сохранения настроек {user_id}: {exc}")
            return False

    def get_user_permissions(self, user_id: int) -> Dict[str, Any]:
        """Возвращает права доступа пользователя."""
        user = self.get_user_by_id(user_id)
        is_admin = bool(user and (user.get("is_admin") or user.get("role") == "admin"))
        return {
            "can_access_admin": is_admin,
            "can_manage_users": is_admin,
            "can_view_logs": True,
            "can_edit_prompts": is_admin,
        }

    def get_user_storage_stats(self, user_id: int) -> Dict[str, Any]:
        """Возвращает статистику занятого дискового пространства пользователем."""
        user_path = self.ensure_user_storage(user_id)
        total_size = 0
        total_files = 0
        subfolder_stats: Dict[str, Dict[str, Any]] = {}

        for item in user_path.rglob("*"):
            if item.is_file():
                try:
                    sz = item.stat().st_size
                    total_size += sz
                    total_files += 1

                    rel_parts = item.relative_to(user_path).parts
                    sub = rel_parts[0] if len(rel_parts) > 1 else "root"
                    if sub not in subfolder_stats:
                        subfolder_stats[sub] = {"files": 0, "size": 0}
                    subfolder_stats[sub]["files"] += 1
                    subfolder_stats[sub]["size"] += sz
                except (OSError, PermissionError):
                    pass

        quota_bytes = _DEFAULT_QUOTA_BYTES
        quota_percent = min(100.0, round((total_size / quota_bytes) * 100, 1)) if quota_bytes else 0.0

        return {
            "user_id": user_id,
            "path": str(user_path),
            "files_count": total_files,
            "size_bytes": total_size,
            "size_formatted": _format_bytes(total_size),
            "quota_bytes": quota_bytes,
            "quota_formatted": _format_bytes(quota_bytes),
            "quota_percent": quota_percent,
            "subfolders": subfolder_stats,
        }

    def get_storage_summary(self) -> Dict[str, Any]:
        """Возвращает общую сводную информацию о хранилище всех пользователей."""
        users = self.get_all_users()
        total_users = len(users)
        total_storage = 0
        total_files = 0

        for u in users:
            stats = self.get_user_storage_stats(u["id"])
            total_storage += stats["size_bytes"]
            total_files += stats["files_count"]

        orphaned = self.get_orphaned_user_directories()
        orphaned_bytes = sum(o["size_bytes"] for o in orphaned)

        return {
            "total_users": total_users,
            "total_storage_bytes": total_storage,
            "total_storage_formatted": _format_bytes(total_storage),
            "total_files_count": total_files,
            "orphaned_bytes": orphaned_bytes,
            "orphaned_formatted": _format_bytes(orphaned_bytes),
        }

    def get_orphaned_user_directories(self) -> List[Dict[str, Any]]:
        """Ищет осиротевшие директории в data/users/."""
        if not self.users_dir.exists():
            return []

        active_users = self.get_all_users()
        active_ids = {str(u["id"]) for u in active_users}
        orphaned: List[Dict[str, Any]] = []

        for entry in self.users_dir.iterdir():
            if not entry.is_dir():
                continue
            dir_name = entry.name
            is_valid_user = dir_name in active_ids

            if not is_valid_user:
                total_size = 0
                files_count = 0
                for f in entry.rglob("*"):
                    if f.is_file():
                        try:
                            total_size += f.stat().st_size
                            files_count += 1
                        except (OSError, PermissionError):
                            pass

                try:
                    mtime = entry.stat().st_mtime
                    mod_str = datetime.datetime.fromtimestamp(mtime, tz=datetime.timezone.utc).isoformat()
                except Exception:
                    mod_str = "-"

                reason = (
                    "Каталог не привязан к существующему пользователю"
                    if not dir_name.isdigit()
                    else f"Пользователь #{dir_name} удален из базы данных"
                )

                orphaned.append({
                    "dir_name": dir_name,
                    "full_path": str(entry),
                    "reason": reason,
                    "files_count": files_count,
                    "size_bytes": total_size,
                    "size_formatted": _format_bytes(total_size),
                    "modified_formatted": mod_str,
                })

        return orphaned

    def cleanup_orphaned_user_directories(self, dir_names: Optional[List[str]] = None) -> Dict[str, Any]:
        """Очищает указанные или все осиротевшие каталоги."""
        orphaned = self.get_orphaned_user_directories()
        deleted_count = 0
        freed_bytes = 0

        target_names = set(dir_names) if dir_names else None

        for item in orphaned:
            name = item["dir_name"]
            if target_names is not None and name not in target_names:
                continue

            target_path = (self.users_dir / name).resolve()
            try:
                target_path.relative_to(self.users_dir.resolve())
            except ValueError:
                continue
            if target_path.exists() and target_path.is_dir():
                try:
                    freed_bytes += item["size_bytes"]
                    shutil.rmtree(target_path, ignore_errors=True)
                    deleted_count += 1
                except Exception as exc:
                    logger.error(f"[UserManager] Не удалось удалить {target_path}: {exc}")

        return {
            "status": "ok",
            "deleted_count": deleted_count,
            "freed_bytes": freed_bytes,
            "freed_formatted": _format_bytes(freed_bytes),
        }

    def get_user_directory_tree(
        self,
        user_id: int,
        subfolder: str = "",
        query: str = "",
        extension: str = "",
    ) -> Dict[str, Any]:
        """Возвращает список файлов и директорий пользователя с фильтрацией."""
        user_path = self.ensure_user_storage(user_id).resolve()
        if subfolder:
            clean_sub = subfolder.replace("\\", "/").strip().lstrip("/")
            base_scan = (user_path / clean_sub).resolve()
            try:
                base_scan.relative_to(user_path)
            except ValueError:
                base_scan = user_path
        else:
            base_scan = user_path

        if not base_scan.exists():
            return {
                "status": "ok",
                "total_items": 0,
                "total_size_bytes": 0,
                "total_size_formatted": "0 B",
                "items": [],
            }

        items: List[Dict[str, Any]] = []
        total_size = 0
        q_lower = query.strip().lower()
        ext_clean = extension.strip().lower().lstrip(".")

        for entry in base_scan.rglob("*"):
            rel = entry.relative_to(user_path).as_posix()
            name = entry.name
            is_dir = entry.is_dir()

            rel_parts = entry.relative_to(user_path).parts
            sub = rel_parts[0] if len(rel_parts) > 1 or is_dir else "root"

            if q_lower and q_lower not in name.lower() and q_lower not in rel.lower():
                continue

            entry_ext = entry.suffix.lstrip(".").lower()
            if ext_clean and not is_dir and entry_ext != ext_clean:
                continue

            sz = 0
            if not is_dir:
                try:
                    sz = entry.stat().st_size
                    total_size += sz
                except (OSError, PermissionError):
                    pass

            try:
                mod_str = datetime.datetime.fromtimestamp(
                    entry.stat().st_mtime, tz=datetime.timezone.utc
                ).isoformat()
            except Exception:
                mod_str = "-"

            items.append({
                "name": name,
                "relative_path": rel,
                "subfolder": sub,
                "is_dir": is_dir,
                "size_bytes": sz,
                "size_formatted": _format_bytes(sz) if not is_dir else "-",
                "modified_formatted": mod_str,
                "extension": entry_ext,
            })

        items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))

        return {
            "status": "ok",
            "total_items": len(items),
            "total_size_bytes": total_size,
            "total_size_formatted": _format_bytes(total_size),
            "items": items,
        }

    def resolve_safe_user_file_path(self, user_id: int, relative_path: str) -> Optional[Path]:
        """Безопасно разрешает путь к файлу внутри хранилища пользователя без path traversal."""
        user_path = (self.users_dir / str(int(user_id))).resolve()
        clean_rel = relative_path.replace("\\", "/").strip().lstrip("/")
        target = (user_path / clean_rel).resolve()
        try:
            target.relative_to(user_path)
            return target
        except ValueError:
            return None

    def get_file_preview(self, user_id: int, relative_path: str) -> Dict[str, Any]:
        """Возвращает данные для предпросмотра файла с потоковым ограничением памяти."""
        target = self.resolve_safe_user_file_path(user_id, relative_path)
        if not target or not target.exists() or not target.is_file():
            return {
                "status": "error",
                "message": "Файл не найден",
                "relative_path": relative_path,
                "content": "",
            }

        size = target.stat().st_size
        mime, _ = mimetypes.guess_type(str(target))
        ext = target.suffix.lstrip(".").lower()
        is_image = bool(mime and mime.startswith("image/"))

        content = ""
        if is_image:
            if size > _MAX_IMAGE_PREVIEW_BYTES:
                content = "Изображение слишком велико для предпросмотра (>20 МБ)"
            else:
                try:
                    with target.open("rb") as f:
                        data = f.read(_MAX_IMAGE_PREVIEW_BYTES)
                    encoded = base64.b64encode(data).decode("ascii")
                    content = f"data:{mime};base64,{encoded}"
                except Exception as exc:
                    content = f"Ошибка чтения изображения: {exc}"
        else:
            try:
                with target.open("rb") as f:
                    raw = f.read(_MAX_TEXT_PREVIEW_BYTES)
                content = raw.decode("utf-8", errors="replace")
            except Exception as exc:
                content = f"Ошибка чтения файла: {exc}"

        return {
            "status": "ok",
            "relative_path": relative_path,
            "size_bytes": size,
            "size_formatted": _format_bytes(size),
            "mime_type": mime or "application/octet-stream",
            "extension": ext,
            "is_image": is_image,
            "content": content,
        }

    def delete_user_file(self, user_id: int, relative_path: str) -> bool:
        """Безопасно удаляет файл или папку пользователя."""
        target = self.resolve_safe_user_file_path(user_id, relative_path)
        if not target or not target.exists():
            return False

        try:
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
            return True
        except Exception as exc:
            logger.error(f"[UserManager] Ошибка удаления {target}: {exc}")
            return False


# Глобальный синглтон менеджера пользователей
user_manager = UserManager()

__all__ = ["UserManager", "user_manager", "hash_password", "verify_password"]
