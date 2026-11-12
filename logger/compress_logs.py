# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Logger - Compress Logs
# =============================================================================
# Description:
#   Утилита для сжатия лог-файлов путём объединения повторяющихся строк.
#
# Usage Examples:
#   CLI:
#     python -m logger.compress_logs
#   Python API:
#     from logger.compress_logs import compress_lines
#
#     res = compress_lines(lines)
#
# File: compress_logs.py
# Project: ai-windows-admin
# Package: logger
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 14:35:30
# =============================================================================

"""Утилита для сжатия файлов журналов и консолидации повторяющихся строк в формат `[Nx]`."""

import os
import sys
from collections import Counter
from pathlib import Path
from typing import List, Optional, Tuple


def compress_lines(lines: List[str], min_repeat: int = 2) -> List[str]:
    """Сжимает повторяющиеся строки в формат `[Nx] текст`.

    Args:
        lines (List[str]): Исходный список строк для сжатия.
        min_repeat (int): Минимальное число повторений для добавления префикса `[Nx]`.

    Returns:
        List[str]: Список сжатых строк.
    """
    counter = Counter(lines)
    result: List[str] = []
    for line, count in counter.items():
        stripped = line.strip()
        if not stripped:
            continue
        if count >= min_repeat:
            result.append(f'[{count}x] {stripped}')
        else:
            result.append(stripped)
    return result


def compress_log_file(
    input_path: Path,
    output_path: Optional[Path] = None,
    min_repeat: int = 2,
) -> Tuple[int, int]:
    """Сжимает файл журнала и атомарно записывает результат на диск.

    Args:
        input_path (Path): Путь к входному файлу лога.
        output_path (Optional[Path]): Путь к выходному файлу (по умолчанию `.compressed.log`).
        min_repeat (int): Минимальное количество повторений для сжатия.

    Returns:
        Tuple[int, int]: Кортеж `(исходное_число_строк, сжатое_число_строк)`.
    """
    with open(input_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    if not lines:
        return (0, 0)
    original_count = len(lines)
    compressed = compress_lines(lines, min_repeat)
    if output_path is None:
        output_path = input_path.with_suffix('.compressed.log')
    resolved_out = output_path.resolve()
    tmp_path = resolved_out.with_name(f'.{resolved_out.name}.tmp')
    try:
        with open(tmp_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(compressed))
            if compressed:
                f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, resolved_out)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
    return (original_count, len(compressed))


def main() -> None:
    """Точка входа CLI для пакетного сжатия логов."""
    from logger import logger
    logs_dir = Path(__file__).resolve().parent.parent.parent / 'tmp' / 'logs'
    if not logs_dir.exists():
        logger.error(f'Директория логов не найдена: {logs_dir}')
        return
    log_files = list(logs_dir.glob('*.log'))
    if not log_files:
        logger.info('Файлы логов для сжатия не найдены')
        return
    logger.info(f'Найдено файлов для сжатия: {len(log_files)}')
    for log_file in log_files:
        original, compressed = compress_log_file(log_file)
        if original > 0:
            compression_pct = 100 - compressed * 100 // original
            logger.info(f'{log_file.name}: {original} -> {compressed} строк (сжатие {compression_pct}%)')
        else:
            logger.info(f'{log_file.name}: пустой файл')


if __name__ == '__main__':
    main()