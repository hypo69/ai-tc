# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Служба отслеживания изменений и автокоммитов Git (auto_commits.py)
# =============================================================================
# Description:
#   Фоновый сервис и утилита контроля версий для автоматического обнаружения
#   измененных файлов в рабочем дереве репозитория и создания атомарных Git-коммитов.
#
#   Зачем нужен этот модуль:
#     1. Защита от потери правок при автоматизированных изменениях файлов через MCP-агентов.
#     2. Исключение глубокой вложенности (Nesting Limit <= 3) за счет декомпозиции
#        сканирования файловой системы и выполнения команд Git.
#
# Usage Examples:
#   Python API:
#     from .auto_commits import scan_modified_files, commit_if_dirty
#     changed = scan_modified_files({})
#
# File: auto_commits.py
# Project: AI Windows Admin (AI-TC)
# Package: .mcp
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 17:06:00
# =============================================================================

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Optional

_CURRENT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _CURRENT_DIR.parent
for _p in (str(_CURRENT_DIR), str(_PROJECT_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from header import __root__
from logger import logger

try:
    from .config_helper import get_config_value
except ImportError:
    from config_helper import get_config_value

ROOT: Path = __root__
_IGNORED_PARTS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".pytest_cache"}


def git(cmd: str, cwd: Optional[Path] = False) -> subprocess.CompletedProcess[str]:  # type: ignore[assignment]
    """Выполнение команды `git` в корневой директории репозитория.

    Args:
        cmd (str): Строка аргументов команды git (например, `'status --porcelain'`).
        cwd (Optional[Path]): Рабочая директория выполнения.
                              Значение по умолчанию: False (используется `ROOT`).

    Returns:
        subprocess.CompletedProcess[str]: Результат выполнения процесса (`stdout`, `stderr`, `returncode`).

    Examples:
        >>> res = git("status --porcelain")
        >>> res.returncode == 0
        True
    """
    target_cwd = cwd if isinstance(cwd, Path) else ROOT
    args = ["git"] + [part for part in cmd.strip().split() if part]
    return subprocess.run(
        args,
        cwd=target_cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def commit_if_dirty(message: str) -> bool:
    """Проверка наличия незакоммиченных изменений и создание коммита.

    Args:
        message (str): Текст сообщения коммита.

    Returns:
        bool: `True`, если изменения были обнаружены и закоммичены; иначе `False`.

    Examples:
        >>> commit_if_dirty("")
        False
    """
    if not message or not message.strip():
        return False

    git("add -A")
    status = git("status --porcelain")
    if not status.stdout or not status.stdout.strip():
        return False

    commit_res = subprocess.run(
        ["git", "commit", "-m", message.strip()],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if commit_res.returncode == 0:
        logger.info(f"[auto_commits] Закоммичены изменения: {message.strip()}")
        return True
    logger.warning(f"[auto_commits] Не удалось выполнить коммит: {commit_res.stderr.strip()}")
    return False


def _should_track_file(path: Path) -> bool:
    """Проверка, подлежит ли файл отслеживанию автокоммитами.

    Args:
        path (Path): Путь к проверяемому объекту файловой системы.

    Returns:
        bool: `True`, если это обычный файл вне служебных директорий и без префикса `~`.

    Examples:
        >>> _should_track_file(ROOT / ".git" / "config")
        False
    """
    if not path.is_file():
        return False
    if any(part in _IGNORED_PARTS or part.startswith("~") for part in path.parts):
        return False
    return True


def _check_file_mtime(path: Path, last_mtime: Dict[Path, float]) -> bool:
    """Сравнение времени модификации файла с сохраненным состоянием.

    Args:
        path (Path): Путь к файлу.
        last_mtime (Dict[Path, float]): Словарь сохраненных временных меток модификации.

    Returns:
        bool: `True`, если файл был изменен после предыдущей проверки; иначе `False`.

    Examples:
        >>> state = {}
        >>> _check_file_mtime(ROOT / "config.json", state)
        False
    """
    try:
        current_mtime = path.stat().st_mtime
    except OSError:
        return False

    if path not in last_mtime:
        last_mtime[path] = current_mtime
        return False

    if current_mtime != last_mtime[path]:
        logger.info(f"[auto_commits] Обнаружено изменение файла: {path}")
        last_mtime[path] = current_mtime
        return True
    return False


def scan_modified_files(last_mtime: Dict[Path, float], root_dir: Optional[Path] = False) -> bool:  # type: ignore[assignment]
    """Однократный обход дерева проекта для выявления измененных файлов.

    Args:
        last_mtime (Dict[Path, float]): Словарь времени последней модификации файлов.
        root_dir (Optional[Path]): Корневая папка для сканирования.
                                   Значение по умолчанию: False (используется `ROOT`).

    Returns:
        bool: `True`, если хотя бы один отслеживаемый файл изменился; иначе `False`.

    Examples:
        >>> state = {}
        >>> scan_modified_files(state, ROOT / ".mcp")
        False
    """
    target_root = root_dir if isinstance(root_dir, Path) else ROOT
    changed = False
    for file_path in target_root.rglob("*"):
        if not _should_track_file(file_path):
            continue
        if _check_file_mtime(file_path, last_mtime):
            changed = True
    return changed


def main(max_iterations: int = 0) -> int:
    """Основной цикл службы отслеживания изменений файлов.

    Args:
        max_iterations (int): Максимальное число итераций (0 — бесконечный цикл).
                              Значение по умолчанию: 0.

    Returns:
        int: Код завершения (0 — успешно).

    Examples:
        >>> main(max_iterations=1)
        0
    """
    poll_interval = float(get_config_value("mcp.auto_commits.poll_interval_seconds", 5.0) or 5.0)
    logger.info(f"[auto_commits] Запуск службы отслеживания изменений файлов (интервал={poll_interval}с)...")
    last_mtime: Dict[Path, float] = {}
    iteration = 0
    while True:
        if scan_modified_files(last_mtime):
            commit_if_dirty("chore(mcp): auto-commit changes detected by MCP server")
        iteration += 1
        if max_iterations > 0 and iteration >= max_iterations:
            break
        time.sleep(poll_interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
