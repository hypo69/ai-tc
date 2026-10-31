# -*- coding: utf-8 -*-
# =============================================================================
# Файл: utils/git_finder.py
# Описание: Утилита для поиска каталогов .git в проекте с использованием безопасного
#            выполнения команд (run_safe) и режима dry‑run.
# =============================================================================
# Updated: 2026-10-22 03:40:05
# =============================================================================

"""hypo69 docblock
Модуль предоставляет функцию ``find_git_folders`` для рекурсивного поиска
директорий ``.git`` в указанном пути. Реализация использует
``utils.command_validator.run_safe`` – тем самым встроен механизм dry‑run и
логирование через ``logger.console``.
"""

from __future__ import annotations

import os
from typing import List

from utils.command_validator import run_safe


def _build_ps_command(root: str) -> str:
    """Сформировать PowerShell‑команду для поиска ``.git``.

    Пример команды:
        Get-ChildItem -Path "C:\path" -Recurse -Directory |
        Where-Object { $_.PSIsContainer -and $_.Name -eq '.git' }
    """
    # Обрамляем путь кавычками, безопасно экранируя обратные слеши.
    escaped_root = root.replace('"', '\"')
    return (
        f"Get-ChildItem -Path \"{escaped_root}\" -Recurse -Directory | "
        "Where-Object { $_.PSIsContainer -and $_.Name -eq '.git' }"
    )


def find_git_folders(root: str = '.', dry_run: bool = True) -> List[str]:
    """Найти все каталоги ``.git`` начиная с ``root``.

    Args:
        root: Путь, откуда начинается поиск. По умолчанию текущий каталог.
        dry_run: Если ``True``, выполняет только проверку синтаксиса и
                 наличие PowerShell‑cmdlet (WhatIf). При ``False`` – реальное
                 выполнение и возврат списка найденных путей.

    Returns:
        list[str]: Список полных путей к найденным ``.git`` директориям.
    """
    # Приводим к абсолютному пути для надёжности.
    abs_root = os.path.abspath(root)
    ps_cmd = _build_ps_command(abs_root)

    result = run_safe(ps_cmd, dry_run=dry_run)
    if result["returncode"] != 0:
        # Ошибка уже залогирована внутри run_safe, но возвращаем пустой список.
        return []

    if dry_run:
        # В режиме dry‑run реальный вывод отсутствует – просто сообщаем, что
        # проверка прошла.
        return []

    # Разбираем вывод PowerShell – каждая строка содержит путь к .git каталогу.
    lines = [line.strip() for line in result["output"].splitlines() if line.strip()]
    return lines


# Пример самостоятельного использования (можно закомментировать в продакшене)
if __name__ == "__main__":
    folders = find_git_folders(dry_run=False)
    from logger import logger
    logger.console(f"Найдено .git каталогов: {len(folders)}")
    for f in folders:
        logger.console(f"- {f}")

