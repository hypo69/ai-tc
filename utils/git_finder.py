# -*- coding: utf-8 -*-
# =============================================================================
# Файл: utils/git_finder.py
# Описание: Утилита для поиска каталогов .git в проекте с использованием безопасного
#            выполнения команд (run_safe), валидации путей и режима dry‑run.
# =============================================================================
# Updated: 2026-11-10 14:36:10
# =============================================================================

"""hypo69 docblock
Модуль предоставляет функцию ``find_git_folders`` для рекурсивного поиска
директорий ``.git`` в указанном пути. Реализация использует
``utils.command_validator.run_safe`` с защитой от инъекций в пути и режимом dry‑run.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from utils.command_validator import run_safe


def _build_ps_command(root: str) -> str:
    """Формирует безопасную PowerShell‑команду для поиска ``.git``.

    Args:
        root: Абсолютный путь к корневой директории поиска.

    Returns:
        Строка команды PowerShell с экранированием одинарных кавычек.
    """
    escaped_root = root.replace("'", "''")
    return (
        f"Get-ChildItem -LiteralPath '{escaped_root}' -Recurse -Directory -Force -ErrorAction SilentlyContinue | "
        "Where-Object { $_.PSIsContainer -and $_.Name -eq '.git' } | "
        "Select-Object -ExpandProperty FullName"
    )


def find_git_folders(root: str = ".", dry_run: bool = True) -> List[str]:
    """Находит все каталоги ``.git`` начиная с ``root``.

    Args:
        root: Путь, откуда начинается поиск. По умолчанию текущий каталог.
        dry_run: Если ``True``, выполняет только проверку синтаксиса (dry-run).
                 При ``False`` — реальное выполнение и возврат списка найденных путей.

    Returns:
        list[str]: Список полных путей к найденным ``.git`` директориям.
    """
    if not root or "\x00" in root:
        return []
    resolved_root = Path(root).resolve()
    if not resolved_root.exists() or not resolved_root.is_dir():
        return []

    ps_cmd = _build_ps_command(str(resolved_root))
    result = run_safe(ps_cmd, dry_run=dry_run)
    if result["returncode"] != 0 or dry_run:
        return []

    lines = [line.strip() for line in result["output"].splitlines() if line.strip()]
    return lines


# Пример самостоятельного использования (можно закомментировать в продакшене)
if __name__ == "__main__":
    folders = find_git_folders(dry_run=False)
    from logger import logger
    logger.console(f"Найдено .git каталогов: {len(folders)}")
    for f in folders:
        logger.console(f"- {f}")
