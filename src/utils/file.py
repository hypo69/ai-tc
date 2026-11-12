# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin UTILS - File Module
# =============================================================================
# Description:
#   Операции с файловой системой и утилиты для работы с текстовыми файлами.
#
# Usage Examples:
#   CLI:
#     python -m src.utils.file
#   Python API:
#     from src.utils.file import save_text_file
#
#     res = save_text_file("text", "output.txt")
#
# File: file.py
# Project: ai-windows-admin
# Package: src.utils
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 14:38:00
# =============================================================================

"""Операции с файловой системой и утилиты для работы с текстовыми файлами.

Предоставляет функции для безопасного чтения, атомарной записи и поиска файлов.
"""

import fnmatch
import json
import os
from pathlib import Path
import tempfile
from typing import Generator, Optional, Union

from logger import logger
from src.utils.printer import pprint as print


def save_text_file(
    data: str | list[str] | dict,
    file_path: Union[str, Path],
    mode: str = 'w',
    exc_info: bool = True,
) -> bool:
    """Сохраняет данные в текстовый файл (атомарно при полной перезаписи mode='w').

    Args:
        data (str | list[str] | dict): Данные для записи (строка, список строк или словарь).
        file_path (str | Path): Путь к сохраняемому файлу.
        mode (str, optional): Режим записи ('w' для перезаписи, 'a' для дозаписи). По умолчанию 'w'.
        exc_info (bool, optional): Логировать ли трассировку стека при ошибке. По умолчанию True.

    Returns:
        bool: True при успешном сохранении, иначе False.
    """
    temp_file: Optional[Path] = None
    try:
        target_path = Path(file_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if mode == 'w':
            with tempfile.NamedTemporaryFile(
                'w',
                dir=str(target_path.parent),
                prefix=f'.{target_path.name}.',
                suffix='.tmp',
                delete=False,
                encoding='utf-8',
            ) as file:
                temp_file = Path(file.name)
                if isinstance(data, list):
                    file.writelines((f'{line}\n' for line in data))
                elif isinstance(data, dict):
                    json.dump(data, file, ensure_ascii=False, indent=4)
                else:
                    file.write(str(data))
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp_file, target_path)
        else:
            with target_path.open(mode, encoding='utf-8') as file:
                if isinstance(data, list):
                    file.writelines((f'{line}\n' for line in data))
                elif isinstance(data, dict):
                    json.dump(data, file, ensure_ascii=False, indent=4)
                else:
                    file.write(str(data))
                file.flush()
        return True
    except Exception as ex:
        if temp_file and temp_file.exists():
            try:
                temp_file.unlink()
            except OSError:
                pass
        logger.error(f'Не удалось сохранить файл {file_path}.', ex, exc_info=exc_info)
        return False


def read_text_file(
    file_path: Union[str, Path],
    as_list: bool = False,
    extensions: Optional[list[str]] = None,
    exc_info: bool = True,
) -> Union[str, list[str], None]:
    """Читает содержимое текстового файла или всех файлов в директории.

    Args:
        file_path (str | Path): Путь к файлу или директории.
        as_list (bool, optional): Если True, возвращает список строк. По умолчанию False.
        extensions (list[str], optional): Список расширений для фильтрации при чтении директории.
        exc_info (bool, optional): Логировать ли трассировку стека при ошибке. По умолчанию True.

    Returns:
        str | list[str] | None: Содержимое файла (строка или список строк), либо None при ошибке.
    """
    try:
        path = Path(file_path)
        if path.is_file():
            with path.open('r', encoding='utf-8') as f:
                return f.readlines() if as_list else f.read()
        elif path.is_dir():
            files = [p for p in path.rglob('*') if p.is_file() and (not extensions or p.suffix in extensions)]
            contents = [read_text_file(p, as_list, exc_info=exc_info) for p in files]
            return (
                [item for sublist in contents if isinstance(sublist, list) for item in sublist]
                if as_list
                else '\n'.join(filter(None, (c for c in contents if isinstance(c, str))))
            )
        else:
            logger.warning(f"Путь '{file_path}' не существует или не является файлом/директорией.")
            return None
    except Exception as ex:
        logger.error(f'Не удалось прочитать файл {file_path}.', ex, exc_info=exc_info)
        return None


def get_filenames(
    directory: Union[str, Path],
    extensions: Union[str, list[str]] = '*',
    exc_info: bool = True,
) -> list[str]:
    """Возвращает список имен файлов в директории с опциональной фильтрацией по расширению.

    Args:
        directory (str | Path): Директория для поиска.
        extensions (str | list[str], optional): Расширения для фильтрации. По умолчанию '*'.
        exc_info (bool, optional): Логировать ли исключения. По умолчанию True.

    Returns:
        list[str]: Список имен найденных файлов.
    """
    try:
        path = Path(directory)
        if isinstance(extensions, str):
            extensions = [extensions] if extensions != '*' else []
        extensions = [ext if ext.startswith('.') else f'.{ext}' for ext in extensions]
        return [file.name for file in path.iterdir() if file.is_file() and (not extensions or file.suffix in extensions)]
    except Exception as ex:
        logger.warning(f"Не удалось получить список файлов в '{directory}'.", ex, exc_info=exc_info)
        return []


def recursively_yield_file_path(
    root_dir: Union[str, Path],
    patterns: Union[str, list[str]] = '*',
    exc_info: bool = True,
) -> Generator[Path, None, None]:
    """Рекурсивно генерирует пути к файлам, соответствующим заданным шаблонам.

    Args:
        root_dir (str | Path): Корневая директория поиска.
        patterns (str | list[str]): Шаблоны имен файлов.
        exc_info (bool, optional): Логировать ли исключения. По умолчанию True.

    Yields:
        Path: Пути к найденным файлам.
    """
    try:
        patterns = [patterns] if isinstance(patterns, str) else patterns
        for pattern in patterns:
            yield from Path(root_dir).rglob(pattern)
    except Exception as ex:
        logger.error(f"Ошибка рекурсивного поиска файлов в '{root_dir}'.", ex, exc_info=exc_info)


def recursively_get_file_path(
    root_dir: Union[str, Path],
    patterns: Union[str, list[str]] = '*',
    exc_info: bool = True,
) -> list[Path]:
    """Рекурсивно возвращает список путей к файлам по заданным шаблонам.

    Args:
        root_dir (str | Path): Корневая директория поиска.
        patterns (str | list[str]): Шаблоны фильтрации файлов.
        exc_info (bool, optional): Логировать ли исключения. По умолчанию True.

    Returns:
        list[Path]: Список путей к найденным файлам.
    """
    try:
        file_paths: list[Path] = []
        patterns = [patterns] if isinstance(patterns, str) else patterns
        for pattern in patterns:
            file_paths.extend(Path(root_dir).rglob(pattern))
        return file_paths
    except Exception as ex:
        logger.error(f"Ошибка поиска файлов в '{root_dir}'.", ex, exc_info=exc_info)
        return []


# Алиас для обратной совместимости
recursively_get_files = recursively_get_file_path


def recursively_read_text_files(
    root_dir: str | Path,
    patterns: str | list[str],
    as_list: bool = False,
    exc_info: bool = True,
) -> list[str]:
    """Рекурсивно читает текстовые файлы из корневой директории по шаблонам имен.

    Args:
        root_dir (str | Path): Путь к корневой директории поиска.
        patterns (str | list[str]): Шаблон или список шаблонов имен файлов (например, '*.txt').
        as_list (bool, optional): Если True, возвращает содержимое в виде списка строк.
        exc_info (bool, optional): Логировать ли исключения в предупреждениях.

    Returns:
        list[str]: Список содержимого файлов (или список всех строк при as_list=True).
    """
    matches: list[str] = []
    root_path = Path(root_dir)
    if not root_path.is_dir():
        logger.debug(f"Корневая директория '{root_path}' не существует или не является папкой.")
        return []
    logger.console(f'Поиск в директории: {root_path}')
    if isinstance(patterns, str):
        patterns = [patterns]
    for root, _, files in os.walk(root_path):
        for filename in files:
            if any((fnmatch.fnmatch(filename, pattern) for pattern in patterns)):
                file_path = Path(root) / filename
                try:
                    with file_path.open('r', encoding='utf-8') as file:
                        if as_list:
                            matches.extend(file.readlines())
                        else:
                            matches.append(file.read())
                except Exception:
                    logger.warning(f"Не удалось прочитать файл '{file_path}'.", exc_info=exc_info)
    return matches


def get_directory_names(directory: str | Path, exc_info: bool = True) -> list[str]:
    """Возвращает имена всех поддиректорий в указанной директории.

    Args:
        directory (str | Path): Путь к анализируемой директории.
        exc_info (bool, optional): Логировать ли трассировку при ошибке. По умолчанию True.

    Returns:
        list[str]: Список имен поддиректорий (пустой список при ошибке).
    """
    try:
        return [entry.name for entry in Path(directory).iterdir() if entry.is_dir()]
    except Exception as ex:
        if exc_info:
            logger.warning(f"Не удалось получить список поддиректорий из '{directory}'.", ex, exc_info=exc_info)
        return []


def read_files_content(
    root_dir: Union[str, Path],
    patterns: Union[str, list[str]],
    as_list: bool = False,
    exc_info: bool = True,
) -> list[str]:
    """Читает содержимое всех файлов, соответствующих шаблонам.

    Args:
        root_dir (str | Path): Корневая директория поиска.
        patterns (str | list[str]): Шаблоны имен файлов.
        as_list (bool, optional): Возвращать ли содержимое как список строк.

    Returns:
        list[str]: Список содержимого найденных файлов.
    """
    content: list[str] = []
    for file_path in recursively_get_file_path(root_dir, patterns, exc_info):
        if not file_path.is_file():
            continue
        file_content = read_text_file(file_path, as_list, exc_info=exc_info)
        if file_content:
            content.extend(file_content if isinstance(file_content, list) else [file_content])
    return content


def remove_bom(file_path: Union[str, Path]) -> None:
    """Атомарно удаляет маркер UTF-8 BOM из текстового файла.

    Args:
        file_path (str | Path): Путь к обрабатываемому файлу.
    """
    path = Path(file_path)
    try:
        content = path.read_text(encoding='utf-8')
        if '\ufeff' in content:
            cleaned = content.replace('\ufeff', '')
            save_text_file(cleaned, path, mode='w')
    except Exception as ex:
        logger.error(f"Не удалось удалить BOM из файла '{file_path}'.", ex)


def traverse_and_clean(directory: Union[str, Path]) -> None:
    """Рекурсивно обходит директорию и удаляет BOM из всех Python-файлов.

    Args:
        directory (str | Path): Корневая директория для обработки.
    """
    for file in recursively_get_file_path(directory, '*.py'):
        if file.is_file():
            remove_bom(file)


def main() -> None:
    """Точка входа для очистки маркера BOM в Python-файлах проекта."""
    root_dir = Path('..', 'src')
    logger.info(f'Запуск очистки BOM в {root_dir}')
    traverse_and_clean(root_dir)


if __name__ == '__main__':
    main()
