# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Software Scanner - Scope
# =============================================================================
# Description:
#   Определение областей и путей поиска установленного ПО, пользовательских
#   профилей, общих директорий и логических дисков Windows.
#
# File: scope.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.software_scanner
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 19:20:00
# =============================================================================

from __future__ import annotations
"""Определение областей поиска программного обеспечения в Windows."""

import os
import sys
from pathlib import Path
from typing import List, Set
from logger import logger
from apps.windows.sdk.software_scanner.policies import ScannerPolicy


class ScannerScope:
    """Менеджер областей поиска и корней файловой системы."""

    def __init__(self, policy: ScannerPolicy | None = None) -> None:
        self.policy = policy or ScannerPolicy()

    def get_system_install_roots(self) -> List[str]:
        """Получить стандартные системные каталоги установки."""
        roots: List[str] = []
        env_vars = [
            "ProgramFiles",
            "ProgramFiles(x86)",
            "ProgramW6432",
            "ProgramData",
            "CommonProgramFiles",
            "CommonProgramFiles(x86)",
        ]
        for var in env_vars:
            val = os.environ.get(var)
            if val and os.path.isdir(val):
                p = os.path.abspath(val)
                if p not in roots:
                    roots.append(p)
        return roots

    def get_user_app_roots(self) -> List[str]:
        """Получить каталоги приложений текущего и найденных пользователей."""
        roots: List[str] = []

        # Каталоги текущего пользователя
        current_env = [
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs"),
            os.environ.get("LOCALAPPDATA", ""),
            os.environ.get("APPDATA", ""),
            os.path.join(os.environ.get("USERPROFILE", ""), "Desktop"),
            os.path.join(os.environ.get("USERPROFILE", ""), "Downloads"),
        ]
        for path in current_env:
            if path and os.path.isdir(path):
                p = os.path.abspath(path)
                if p not in roots:
                    roots.append(p)

        # Все профили пользователей в C:\Users
        users_dir = r"C:\Users"
        if os.path.isdir(users_dir):
            try:
                for entry in os.scandir(users_dir):
                    if entry.is_dir() and entry.name.lower() not in self.policy.service_account_names:
                        appdata_local = os.path.join(entry.path, "AppData", "Local", "Programs")
                        if os.path.isdir(appdata_local) and appdata_local not in roots:
                            roots.append(appdata_local)
            except OSError as ex:
                logger.debug(f"[ScannerScope] Ошибка обхода {users_dir}: {ex}")

        return roots

    def get_additional_drive_roots(self) -> List[str]:
        """Получить корни дополнительных локальных дисков (D:\\, E:\\ и т.д.)."""
        roots: List[str] = []
        if sys.platform.startswith("win"):
            import string
            for letter in string.ascii_uppercase:
                if letter == "C":
                    continue
                drive_path = f"{letter}:\\"
                if os.path.isdir(drive_path):
                    # Проверяем типовые папки Apps, Tools, Portable, Games
                    common_subfolders = ["Apps", "Tools", "Portable", "Programs", "Games", "Soft"]
                    for sub in common_subfolders:
                        sub_path = os.path.join(drive_path, sub)
                        if os.path.isdir(sub_path):
                            roots.append(sub_path)
                    if not roots:
                        roots.append(drive_path)
        return roots

    def get_all_scan_roots(self, include_drives: bool = True) -> List[str]:
        """Получить полный объединенный список корней для глубокого сканирования."""
        all_roots: List[str] = []
        all_roots.extend(self.get_system_install_roots())
        all_roots.extend(self.get_user_app_roots())
        if include_drives:
            all_roots.extend(self.get_additional_drive_roots())
        
        # Удаляем дубликаты с сохранением порядка
        seen: Set[str] = set()
        unique_roots: List[str] = []
        for r in all_roots:
            norm = os.path.normpath(r).lower()
            if norm not in seen:
                seen.add(norm)
                unique_roots.append(r)
        return unique_roots

    def is_excluded_dir(self, dir_name: str) -> bool:
        """Проверить, исключена ли папка политикой сканирования."""
        return dir_name.lower() in self.policy.excluded_dir_names

    @staticmethod
    def is_reparse_point(path: str) -> bool:
        """Проверить, является ли путь точкой повторной обработки (junction / symlink)."""
        try:
            p = Path(path)
            return p.is_symlink()
        except OSError:
            return False


__all__ = ["ScannerScope"]

