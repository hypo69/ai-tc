# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc UTILS - Versioning Module
# =============================================================================
# Description:
#   Утилиты разбора, сравнения, сортировки и инкремента версий по SemVer 2.0.
#
# Usage Examples:
#   Python API:
#     from src.utils.versioning import parse_semver, choose_best_tag, bump_version
#
#     next_tag = bump_version('v1.0.0', part='minor')
#
# File: versioning.py
# Project: ai-tc
# Package: src.utils
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20 21:05:00
# =============================================================================

"""Утилиты разбора, сравнения, сортировки и инкремента версий по SemVer 2.0."""

from functools import cmp_to_key
import re
from typing import List, Optional, Tuple

_SEMVER_RE = re.compile(
    r'^v?(?P<major>0|[1-9]\d*)(?:\.(?P<minor>0|[1-9]\d*))?(?:\.(?P<patch>0|[1-9]\d*))?'
    r'(?:-(?P<prerelease>[0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$'
)
_STRICT_SEMVER_TAG_RE = re.compile(
    r'^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)'
    r'(?:-(?P<prerelease>[0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$'
)


def _parse_version_legacy(v: str) -> List[int]:
    """Разбирает нестандартную строку версии в список целых чисел.

    Args:
        v (str): Строка версии произвольного формата.

    Returns:
        List[int]: Список числовых компонентов версии; `[0, 0, 0]` для пустой строки.
    """
    if not v:
        return [0, 0, 0]
    parts = re.findall(r'(\d+)', v)
    return [int(p) for p in parts]


def parse_semver(v: str) -> Tuple[int, int, int, List[str]]:
    """Разбирает строку версии согласно спецификации SemVer 2.0.

    Args:
        v (str): Строка версии (с опциональным префиксом `v`, пререлизом и build-метаданными).

    Returns:
        Tuple[int, int, int, List[str]]: Кортеж `(major, minor, patch, prerelease)`
            или пустой кортеж `()` для невалидной строки.
    """
    if not v:
        return ()
    m = _SEMVER_RE.match(v.strip())
    if not m:
        return ()
    major = int(m.group('major'))
    minor = int(m.group('minor') or 0)
    patch = int(m.group('patch') or 0)
    prerelease_raw = m.group('prerelease')
    prerelease = prerelease_raw.split('.') if prerelease_raw else []
    return (major, minor, patch, prerelease)


def is_valid_semver_tag(tag: str, prefix: str = 'v') -> bool:
    """Проверяет, соответствует ли тег строгому формату `<prefix>MAJOR.MINOR.PATCH[-prerelease]`.

    Args:
        tag (str): Имя Git-тега (например, `v1.2.3` или `v1.2.3-rc.1`).
        prefix (str): Обязательный префикс тега. По умолчанию `'v'`.

    Returns:
        bool: True, если тег валиден.
    """
    if not tag or (prefix and not tag.startswith(prefix)):
        return False
    body = tag[len(prefix):] if prefix else tag
    return bool(_STRICT_SEMVER_TAG_RE.match(body))


def is_prerelease_tag(tag: str) -> bool:
    """Определяет, является ли тег пререлизом (содержит суффикс `-alpha`, `-beta`, `-rc` и т.п.).

    Args:
        tag (str): Имя тега.

    Returns:
        bool: True для пререлизного тега.
    """
    return '-' in tag.split('+', 1)[0]


def compare_versions(a: str, b: str) -> int:
    """Сравнивает две строки версий с приоритетом SemVer 2.0.

    Args:
        a (str): Первая версия.
        b (str): Вторая версия.

    Returns:
        int: `-1` если `a < b`, `0` если равны, `1` если `a > b`.
    """
    a_parsed = parse_semver(a)
    b_parsed = parse_semver(b)
    if not a_parsed and not b_parsed:
        return 0
    if not a_parsed or not b_parsed:
        pa = _parse_version_legacy(a)
        pb = _parse_version_legacy(b)
        length = max(len(pa), len(pb))
        pa += [0] * (length - len(pa))
        pb += [0] * (length - len(pb))
        if pa < pb:
            return -1
        if pa > pb:
            return 1
        return 0
    for i in range(3):
        if a_parsed[i] < b_parsed[i]:
            return -1
        if a_parsed[i] > b_parsed[i]:
            return 1
    a_pr: List[str] = a_parsed[3]
    b_pr: List[str] = b_parsed[3]
    if not a_pr and not b_pr:
        return 0
    if not a_pr:
        return 1
    if not b_pr:
        return -1
    for ai, bi in zip(a_pr, b_pr):
        if ai == bi:
            continue
        if ai.isdigit() and bi.isdigit():
            diff = int(ai) - int(bi)
            if diff != 0:
                return -1 if diff < 0 else 1
        else:
            return -1 if ai < bi else 1
    if len(a_pr) < len(b_pr):
        return -1
    if len(a_pr) > len(b_pr):
        return 1
    return 0


def sort_tags(tags: List[str], allow_prerelease: bool = False, descending: bool = True, prefix: str = 'v') -> List[str]:
    """Фильтрует и сортирует список SemVer-тегов.

    Args:
        tags (List[str]): Исходный список тегов.
        allow_prerelease (bool): Включать ли пререлизные теги.
        descending (bool): Сортировать по убыванию (новые сначала).
        prefix (str): Ожидаемый префикс тегов.

    Returns:
        List[str]: Отсортированный список валидных тегов без дубликатов.
    """
    unique_valid = list(dict.fromkeys(t for t in tags if is_valid_semver_tag(t, prefix=prefix)))
    if not allow_prerelease:
        unique_valid = [t for t in unique_valid if not is_prerelease_tag(t)]
    return sorted(unique_valid, key=cmp_to_key(compare_versions), reverse=descending)


def choose_best_tag(tags: List[str], allow_prerelease: bool = False, debug: bool = False) -> str:
    """Выбирает наибольшую версию из списка тегов.

    Args:
        tags (List[str]): Список строк версий/тегов.
        allow_prerelease (bool): Разрешить пререлизы. По умолчанию False.
        debug (bool): Выводить отладочную информацию в logger.

    Returns:
        str: Тег с наибольшей версией или пустая строка, если список пуст.
    """
    if not tags:
        return ''
    stable = [t for t in tags if not is_prerelease_tag(t)]
    candidates = stable if stable and not allow_prerelease else tags
    if debug:
        from logger import logger
        logger.debug(f'[versioning.choose_best_tag] candidates={candidates} allow_prerelease={allow_prerelease}')
    best = ''
    for t in candidates:
        if not best or compare_versions(best, t) < 0:
            best = t
    return best


def bump_version(
    current_tag: Optional[str],
    part: str = 'patch',
    prefix: str = 'v',
    prerelease: Optional[str] = None,
) -> str:
    """Вычисляет следующий SemVer-тег на основе текущей версии.

    Args:
        current_tag (Optional[str]): Текущий тег (например, `v1.0.0`) или None для первого релиза.
        part (str): Компонент для инкремента (`major`, `minor`, `patch`).
        prefix (str): Префикс тега. По умолчанию `'v'`.
        prerelease (Optional[str]): Необязательный суффикс пререлиза (например, `rc.1`).

    Returns:
        str: Новая строка тега (например, `v1.0.1` или `v1.1.0-rc.1`).

    Raises:
        ValueError: При неподдерживаемом значении `part`.
    """
    if part not in ('major', 'minor', 'patch'):
        raise ValueError(f"Некорректный тип инкремента версии: {part}. Допустимо: major, minor, patch")
    parsed = parse_semver(current_tag or '')
    if not parsed:
        major, minor, patch = 1, 0, 0
    else:
        major, minor, patch, _ = parsed
        if part == 'major':
            major += 1
            minor = 0
            patch = 0
        elif part == 'minor':
            minor += 1
            patch = 0
        else:
            patch += 1
    suffix = f'-{prerelease.lstrip("-")}' if prerelease else ''
    return f'{prefix}{major}.{minor}.{patch}{suffix}'
