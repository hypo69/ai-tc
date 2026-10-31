# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Software Scanner - Policies
# =============================================================================
# Description:
#   Конфигурационные политики и правила сканирования файловой системы, реестра
#   и системных компонентов Windows.
#
# File: policies.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.software_scanner
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 19:20:00
# =============================================================================

from __future__ import annotations
"""Политики и правила обхода системы для Deep Software Scanner."""

from dataclasses import dataclass, field
from typing import List, Set


@dataclass
class ScannerPolicy:
    """Политика выполнения сканирования."""

    # Максимальная глубина рекурсии при обходе директорий
    max_scan_depth: int = 5

    # Максимальное количество файлов для сканирования PE-заголовков в одной директории
    max_files_per_directory: int = 150

    # Расчет SHA-256 хеша для найденных исполняемых файлов (включается по требованию)
    compute_sha256: bool = False

    # Максимальный размер файла для вычисления хеша (байты)
    max_hash_file_size_bytes: int = 50 * 1024 * 1024  # 50 MB

    # Порог неактивности для классификации ПО как "Dormant" (в днях)
    dormant_threshold_days: int = 90

    # Порог активности (в днях)
    active_threshold_days: int = 60

    # Целевые расширения исполняемых файлов и манифестов
    executable_extensions: Set[str] = field(default_factory=lambda: {
        ".exe", ".com", ".scr"
    })

    manifest_extensions: Set[str] = field(default_factory=lambda: {
        ".lnk", ".msi", ".appx", ".msix"
    })

    # Исключаемые системные директории (для снижения нагрузки и предотвращения шума)
    excluded_dir_names: Set[str] = field(default_factory=lambda: {
        "winsxs",
        "system32",
        "syswow64",
        "servicing",
        "$recycle.bin",
        "system volume information",
        "recovery",
        "package cache",
        "msocache",
        "assembly",
        "node_modules",
        ".git",
        "__pycache__",
        ".pytest_cache",
        ".venv",
        "venv",
    })

    # Исключаемые имена служебных учетных записей в C:\Users
    service_account_names: Set[str] = field(default_factory=lambda: {
        "default",
        "default user",
        "all users",
        "public",
        "systemprofile",
        "localservice",
        "networkservice",
    })


__all__ = ["ScannerPolicy"]

