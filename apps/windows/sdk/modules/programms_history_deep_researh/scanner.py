# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin SDK - User Profile Artifact Scanner
# =============================================================================
# Description:
#   Рекурсивный сканер пользовательских профилей для обнаружения артефактов ПО.
#
# File: scanner.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.programms_history_deep_researh
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 14:18:00
# =============================================================================
r"""scanner.py – рекурсивный сканер пользовательских профилей.

Функция `scan_user_profiles` обходит директории `C:\Users\*` (кроме
сервисных аккаунтов) и собирает информацию о потенциальных артефактах
программ: пути к файлам/директориям, расширения, даты изменения.

Возвращаемое значение – список словарей с ключами:
- `path` – абсолютный путь к найденному объекту;
- `is_dir` – `True`, если объект директория;
- `size` – размер в байтах (если файл);
- `mtime` – время последней модификации в UTC ISO‑формате.
"""

import datetime
import os
from typing import Dict, List

_SERVICE_NAMES_LOWER = {"default", "public", "all users", "administrator", "systemprofile"}


def _is_service_account(name: str) -> bool:
    """Определяет, является ли каталог системным сервисным аккаунтом.
    Примеры: `Default`, `Public`, `All Users`, `Administrator`.
    """
    return name.lower() in _SERVICE_NAMES_LOWER


def _append_artifact(artifacts: List[Dict], target_path: str, is_dir: bool) -> None:
    """Добавляет метаданные объекта файловой системы со временем в UTC ISO 8601."""
    try:
        stat = os.stat(target_path)
        mtime_utc = datetime.datetime.fromtimestamp(
            stat.st_mtime, tz=datetime.timezone.utc
        ).isoformat()
        artifacts.append({
            "path": target_path,
            "is_dir": is_dir,
            "size": 0 if is_dir else stat.st_size,
            "mtime": mtime_utc,
        })
    except OSError:
        return


def scan_user_profiles() -> List[Dict]:
    """Рекурсивно сканирует пользовательские каталоги с гарантированным закрытием дескриптора.

    Returns:
        List[Dict]: список найденных артефактов.
    """
    base = r"C:\\Users"
    artifacts: List[Dict] = []
    if not os.path.isdir(base):
        return artifacts
    with os.scandir(base) as entries:
        for entry in entries:
            if not entry.is_dir() or _is_service_account(entry.name):
                continue
            for root, dirs, files in os.walk(entry.path):
                for name in files:
                    _append_artifact(artifacts, os.path.join(root, name), is_dir=False)
                for name in dirs:
                    _append_artifact(artifacts, os.path.join(root, name), is_dir=True)
    return artifacts

