# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Scripts CLI - Test Command
# =============================================================================
# Description:
#   Команда запуска тестового набора pytest через единый CLI manage_tools.py.
#
# File: test_cmd.py
# Project: ai-windows-admin
# Package: scripts.cli.commands
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-13 20:46:00
# =============================================================================

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

try:
    from logger import logger
except ImportError:
    import logging
    logger = logging.getLogger("cli_test_command")


def register_test_parser(subparsers: argparse._SubParsersAction) -> None:
    """Регистрирует подпарсер для команды 'test' в manage_tools.py.

    Args:
        subparsers: Группа подпарсеров argparse.
    """
    test_parser = subparsers.add_parser(
        "test",
        help="Запуск модульных и интеграционных тестов через pytest",
        description="Запускает pytest для проверки работоспособности подсистем проекта.",
    )
    test_parser.add_argument(
        "path",
        nargs="?",
        default="tests",
        help="Путь к директории или конкретному файлу тестов (по умолчанию 'tests')",
    )
    test_parser.add_argument(
        "--cov",
        action="store_true",
        help="Сформировать отчет о покрытии кода тестами",
    )
    test_parser.add_argument(
        "-k",
        "--filter",
        dest="keyword",
        help="Фильтрация тестов по ключевому выражению (-k)",
    )


def run_test_command(args: argparse.Namespace) -> int:
    """Выполняет команду запуска тестов.

    Args:
        args: Аргументы командной строки.

    Returns:
        Код завершения pytest (0 при успехе).
    """
    cmd = [sys.executable, "-m", "pytest", args.path]
    if getattr(args, "cov", False):
        cmd.extend(["--cov", "--cov-report=term-missing"])
    if getattr(args, "keyword", None):
        cmd.extend(["-k", args.keyword])

    if hasattr(logger, "console"):
        logger.console(f"🧪 [Test Runner] Запуск команды: {' '.join(cmd)}")
    else:
        logger.info(f"[Test Runner] Запуск: {' '.join(cmd)}")

    res = subprocess.run(cmd)
    return res.returncode

