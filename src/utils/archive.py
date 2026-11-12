# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin UTILS - Archive Module
# =============================================================================
# Description:
#   Безопасная распаковка архивов (ZIP, TAR, GZ, BZ2) с защитой от Zip Slip / Path Traversal.
#
# Usage Examples:
#   Python API:
#     from src.utils.archive import extract_archive, is_system_file
#
#     files = extract_archive("archive.zip")
#
# File: archive.py
# Project: ai-windows-admin
# Package: src.utils
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 14:38:00
# =============================================================================

from __future__ import annotations

"""Безопасная распаковка архивов с защитой от Zip Slip и Path Traversal."""

from pathlib import Path
import shutil
import tarfile
from typing import List, Optional, Union
import zipfile

from logger import logger

_COPY_CHUNK_SIZE = 64 * 1024  # 64 КБ для потокового копирования без переполнения памяти


def is_system_file(name: str) -> bool:
    """Проверяет, является ли элемент архива служебным системным файлом ОС.

    Args:
        name (str): Относительный путь файла внутри архива.

    Returns:
        bool: True, если файл служебный (__MACOSX, .DS_Store, Thumbs.db, ~$), иначе False.
    """
    parts = Path(name).parts
    for part in parts:
        if part.startswith('__MACOSX') or part.startswith('~$') or part == '.DS_Store' or part == 'Thumbs.db':
            return True
    return False


def _is_safe_target_path(extract_root: Path, target_path: Path) -> bool:
    """Проверяет, что целевой путь строго находится внутри корневой директории распаковки.

    Защищает от уязвимостей Zip Slip / Path Traversal (включая обход префиксов папок).
    """
    try:
        return target_path.resolve().is_relative_to(extract_root.resolve())
    except ValueError:
        return False


def extract_archive(
    archive_path: Union[str, Path],
    extract_to: Optional[Union[str, Path]] = None,
    allowed_extensions: Optional[List[str]] = None,
) -> List[Path]:
    """Безопасно распаковывает архив в целевую директорию с защитой от Zip Slip / Symlink атак.

    Args:
        archive_path (Union[str, Path]): Путь к архивному файлу.
        extract_to (Optional[Union[str, Path]]): Целевая директория распаковки.
        allowed_extensions (Optional[List[str]]): Список разрешенных расширений файлов.

    Returns:
        List[Path]: Список путей к успешно распакованным файлам.
    """
    archive_path = Path(archive_path)
    if not archive_path.is_file():
        logger.error(f'Архивный файл не найден: {archive_path}')
        return []
    if extract_to is None:
        extract_to = archive_path.parent / f'extracted_{archive_path.stem}'
    extract_root = Path(extract_to).resolve()
    extract_root.mkdir(parents=True, exist_ok=True)
    extracted_files: List[Path] = []
    allowed_set = {e.lower() for e in allowed_extensions} if allowed_extensions else None
    ext = archive_path.suffix.lower()
    try:
        if ext == '.zip':
            with zipfile.ZipFile(archive_path, 'r') as zf:
                for member in zf.infolist():
                    if member.is_dir() or is_system_file(member.filename):
                        continue
                    target_path = (extract_root / member.filename).resolve()
                    if not _is_safe_target_path(extract_root, target_path):
                        logger.warning(f'Пропущен небезопасный путь в ZIP-архиве (Zip Slip): {member.filename}')
                        continue
                    if allowed_set is not None and target_path.suffix.lower() not in allowed_set:
                        continue
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member) as source, open(target_path, 'wb') as target:
                        shutil.copyfileobj(source, target, length=_COPY_CHUNK_SIZE)
                    extracted_files.append(target_path)
        elif ext in ['.tar', '.gz', '.tgz', '.bz2']:
            with tarfile.open(archive_path, 'r:*') as tf:
                for member in tf.getmembers():
                    if member.isdir() or is_system_file(member.name):
                        continue
                    # Блокируем символические/жесткие ссылки и специальные файлы устройств в TAR
                    if member.issym() or member.islnk() or member.ischr() or member.isblk() or member.isfifo():
                        logger.warning(f'Пропущен небезопасный тип элемента в TAR-архиве (symlink/device): {member.name}')
                        continue
                    target_path = (extract_root / member.name).resolve()
                    if not _is_safe_target_path(extract_root, target_path):
                        logger.warning(f'Пропущен небезопасный путь в TAR-архиве (Tar Slip): {member.name}')
                        continue
                    if allowed_set is not None and target_path.suffix.lower() not in allowed_set:
                        continue
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    extracted_stream = tf.extractfile(member)
                    if extracted_stream is not None:
                        with extracted_stream as source, open(target_path, 'wb') as target:
                            shutil.copyfileobj(source, target, length=_COPY_CHUNK_SIZE)
                        extracted_files.append(target_path)
        else:
            logger.warning(f'Неподдерживаемый формат архива: {ext}')
    except Exception as ex:
        logger.error(f'Ошибка при распаковке архива {archive_path}', ex)
    return extracted_files
