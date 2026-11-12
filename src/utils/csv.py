# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin UTILS - Csv Module
# =============================================================================
# Description:
#   Утилиты чтения, записи и конвертации файлов CSV и JSON.
#
# Usage Examples:
#   Python API:
#     from src.utils.csv import save_csv_file, read_csv_file
#
#     res = save_csv_file([{"a": "1"}], "data.csv")
#
# File: csv.py
# Project: ai-windows-admin
# Package: src.utils
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 14:40:00
# =============================================================================

"""Утилиты чтения, записи и конвертации файлов CSV и JSON."""

import csv
import json
import os
from pathlib import Path
import tempfile
from typing import Dict, List, Union

import pandas as pd

from logger import logger


def save_csv_file(
    data: List[Dict[str, str]],
    file_path: Union[str, Path],
    mode: str = 'a',
    exc_info: bool = True,
) -> bool:
    """Сохраняет список словарей в CSV-файл.

    Args:
        data (List[Dict[str, str]]): Список словарей для сохранения.
        file_path (Union[str, Path]): Путь к CSV-файлу.
        mode (str): Режим записи ('a' — дозапись, 'w' — перезапись). По умолчанию 'a'.
        exc_info (bool): Включать ли стек вызовов в лог при ошибке.

    Raises:
        TypeError: Если входные данные не являются списком словарей.
        ValueError: Если список входных данных пуст.

    Returns:
        bool: True при успешном сохранении, иначе False.
    """
    if not isinstance(data, list):
        raise TypeError('Input data must be a list of dictionaries.')
    if not data:
        raise ValueError('Input data cannot be empty.')
    try:
        target_path = Path(file_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        need_header = (mode == 'w') or (not target_path.exists()) or (target_path.stat().st_size == 0)
        with target_path.open(mode, newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=data[0].keys())
            if need_header:
                writer.writeheader()
            writer.writerows(data)
            file.flush()
        return True
    except Exception:
        logger.error(f'Не удалось сохранить CSV в файл {file_path}', exc_info=exc_info)
        return False


def read_csv_file(file_path: Union[str, Path], exc_info: bool = True) -> List[Dict[str, str]] | None:
    """Читает содержимое CSV-файла в виде списка словарей.

    Args:
        file_path (Union[str, Path]): Путь к CSV-файлу.
        exc_info (bool): Включать ли стек вызовов в лог при ошибке.

    Returns:
        List[Dict[str, str]] | None: Список словарей или None при ошибке.
    """
    try:
        with Path(file_path).open('r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            return list(reader)
    except FileNotFoundError:
        logger.error(f'CSV-файл не найден: {file_path}', exc_info=exc_info)
        return None
    except Exception:
        logger.error(f'Ошибка чтения CSV из файла {file_path}', exc_info=exc_info)
        return None


def read_csv_as_json(
    csv_file_path: Union[str, Path],
    json_file_path: Union[str, Path],
    exc_info: bool = True,
) -> bool:
    """Конвертирует CSV-файл в формат JSON и атомарно сохраняет его на диск.

    Args:
        csv_file_path (Union[str, Path]): Путь к исходному CSV-файлу.
        json_file_path (Union[str, Path]): Путь для сохранения JSON-файла.
        exc_info (bool): Логировать ли трассировку стека при ошибке.

    Returns:
        bool: True при успешной конвертации, иначе False.
    """
    temp_file: Path | None = None
    try:
        data = read_csv_file(csv_file_path, exc_info=exc_info)
        if data is None:
            return False
        target_json = Path(json_file_path)
        target_json.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            'w',
            dir=str(target_json.parent),
            prefix=f'.{target_json.name}.',
            suffix='.tmp',
            delete=False,
            encoding='utf-8',
        ) as f:
            temp_file = Path(f.name)
            json.dump(data, f, indent=4, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_file, target_json)
        return True
    except Exception:
        if temp_file and temp_file.exists():
            try:
                temp_file.unlink()
            except OSError:
                pass
        logger.error(f'Ошибка конвертации CSV в JSON ({json_file_path})', exc_info=exc_info)
        return False


def read_csv_as_dict(csv_file: Union[str, Path]) -> dict | None:
    """Преобразует содержимое CSV-файла в словарь с ключом 'data'.

    Args:
        csv_file (Union[str, Path]): Путь к CSV-файлу.

    Returns:
        dict | None: Словарь представления CSV-данных или None при ошибке.
    """
    try:
        with Path(csv_file).open('r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            return {'data': [row for row in reader]}
    except Exception:
        logger.error('Ошибка чтения CSV в виде словаря', exc_info=True)
        return None


def read_csv_as_ns(file_path: Union[str, Path]) -> List[dict]:
    """Загружает данные CSV в список словарей с помощью Pandas.

    Args:
        file_path (Union[str, Path]): Путь к CSV-файлу.

    Returns:
        List[dict]: Список словарей, представляющих строки CSV.
    """
    try:
        df = pd.read_csv(file_path)
        return df.to_dict(orient='records')
    except FileNotFoundError:
        logger.error(f'CSV-файл не найден: {file_path}', exc_info=True)
        return []
    except Exception:
        logger.error(f'Не удалось загрузить CSV через Pandas из {file_path}', exc_info=True)
        return []
