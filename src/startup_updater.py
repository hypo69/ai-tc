# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc CORE - Startup Auto-Updater
# =============================================================================
# Description:
#   Автоматическая проверка и безопасная установка обновлений по Git-тегам
#   при запуске приложения с защитой от бесконечного цикла перезапуска.
#
# Usage Examples:
#   Python API:
#     from src.startup_updater import run_startup_update
#
#     result = run_startup_update(skip=False)
#     if result.should_exit:
#         sys.exit(result.exit_code)
#
# File: startup_updater.py
# Project: ai-tc
# Package: src
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20 22:06:00
# =============================================================================

"""Автоматическая проверка и установка обновлений при старте приложения."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import sys
from typing import Callable, Dict, List, Optional

from header import __root__
from logger import logger
from src.version_manager import UpdateStatus, VersionManager

SKIP_UPDATE_ENV_VAR = 'AITC_SKIP_STARTUP_UPDATE'


@dataclass
class StartupUpdateResult:
    """Результат проверки и применения автообновления при запуске."""

    checked: bool = False
    updated: bool = False
    should_exit: bool = False
    exit_code: int = 0
    from_version: Optional[str] = None
    to_version: Optional[str] = None
    message: str = ''


def _default_restart(cmd: List[str], env: Dict[str, str]) -> int:
    """Перезапускает процесс приложения с обновлённым кодом и возвращает его код выхода."""
    proc = subprocess.run(cmd, env=env)
    return int(proc.returncode)


def run_startup_update(
    repo_path: Optional[Path] = None,
    skip: bool = False,
    argv: Optional[List[str]] = None,
    config_override: Optional[Dict] = None,
    backup_root: Optional[Path] = None,
    restart_fn: Optional[Callable[[List[str], Dict[str, str]], int]] = None,
) -> StartupUpdateResult:
    """Выполняет проверку и безопасное применение обновлений при старте приложения.

    Отказоустойчивость: любые сетевые ошибки, отсутствие тегов или наличие
    незакоммиченных правок в рабочем дереве не прерывают запуск программы.

    Args:
        repo_path: Путь к репозиторию (по умолчанию `__root__`).
        skip: Явный пропуск проверки (например, флаг CLI `--no-update`).
        argv: Аргументы запуска для перезапуска процесса (по умолчанию `sys.argv`).
        config_override: Переопределение параметров секции `updates` (для DI/тестов).
        backup_root: Пользовательская папка для бэкапов (для DI/тестов).
        restart_fn: Функция перезапуска процесса (для DI/тестов).

    Returns:
        StartupUpdateResult: Итог проверки/обновления и флаг необходимости выхода текущего процесса.
    """
    if skip or os.environ.get(SKIP_UPDATE_ENV_VAR) == '1':
        return StartupUpdateResult(checked=False, message='Автообновление пропущено (флаг/переменная окружения)')

    try:
        vm = VersionManager(
            repo_path=repo_path or __root__,
            config=config_override,
            backup_root=backup_root,
        )
        cfg = vm.config
        if not bool(cfg.get('auto_check_on_startup', True)):
            return StartupUpdateResult(checked=False, message='Автопроверка обновлений отключена в config.json')

        timeout_sec = int(cfg.get('startup_timeout_sec', 8))
        check_res = vm.check_updates(timeout=timeout_sec)
        status = check_res.get('status')

        if status == UpdateStatus.NO_RELEASES.value:
            logger.debug('[StartupUpdater] Релизные теги в удалённом репозитории отсутствуют.')
            return StartupUpdateResult(checked=True, message='Релизные теги отсутствуют')

        if status == UpdateStatus.ERROR.value:
            logger.warning(f"[StartupUpdater] Пропуск автообновления (ошибка проверки): {check_res.get('message')}")
            return StartupUpdateResult(checked=True, message=f"Ошибка проверки: {check_res.get('message')}")

        if not check_res.get('is_update_available'):
            logger.info(f"[StartupUpdater] Актуальная версия: {check_res.get('current_version')}")
            return StartupUpdateResult(
                checked=True,
                from_version=check_res.get('current_version'),
                to_version=check_res.get('remote_version'),
                message='Установлена актуальная версия',
            )

        current_ver = check_res.get('current_version')
        remote_ver = check_res.get('remote_version')
        logger.console(f'[UPDATE] Доступно обновление: {current_ver} -> {remote_ver}')

        if not bool(cfg.get('auto_apply_on_startup', True)):
            logger.console('[UPDATE] Автоустановка отключена (выполните: py manage_tools.py update apply)')
            return StartupUpdateResult(
                checked=True,
                from_version=current_ver,
                to_version=remote_ver,
                message='Доступно обновление (автоустановка отключена)',
            )

        clean, _ = vm.is_working_tree_clean()
        if not clean:
            logger.warning(
                f'[StartupUpdater] Найдено обновление {remote_ver}, но рабочее дерево содержит '
                'незакоммиченные изменения. Автоустановка пропущена.'
            )
            return StartupUpdateResult(
                checked=True,
                from_version=current_ver,
                to_version=remote_ver,
                message='Пропущено из-за незакоммиченных изменений',
            )

        logger.console(f'[UPDATE] Установка релиза {remote_ver} (с резервной копией)...')
        apply_res = asyncio.run(vm.update_application(target_tag=remote_ver, auto_backup=True, allow_dirty=False))
        if not apply_res.get('success'):
            logger.warning(f"[StartupUpdater] Не удалось установить обновление {remote_ver}: {apply_res.get('message')}")
            return StartupUpdateResult(
                checked=True,
                from_version=current_ver,
                to_version=remote_ver,
                message=f"Ошибка установки: {apply_res.get('message')}",
            )

        logger.console(f'[UPDATE] Успешно установлена версия {remote_ver}.')
        if not bool(cfg.get('restart_after_update', True)):
            return StartupUpdateResult(
                checked=True,
                updated=True,
                should_exit=False,
                from_version=current_ver,
                to_version=remote_ver,
                message=f'Обновлено до {remote_ver} без перезапуска',
            )

        logger.console(f'[UPDATE] Перезапуск приложения на версии {remote_ver}...')
        child_env = dict(os.environ)
        child_env[SKIP_UPDATE_ENV_VAR] = '1'
        child_cmd = [sys.executable, *(argv if argv is not None else sys.argv)]
        restarter = restart_fn or _default_restart
        exit_code = restarter(child_cmd, child_env)
        return StartupUpdateResult(
            checked=True,
            updated=True,
            should_exit=True,
            exit_code=exit_code,
            from_version=current_ver,
            to_version=remote_ver,
            message=f'Обновлено до {remote_ver} и перезапущено',
        )
    except Exception as ex:
        logger.warning(f'[StartupUpdater] Сбой автообновления при старте (запуск продолжен): {ex}')
        return StartupUpdateResult(checked=False, message=f'Ошибка автообновления: {ex}')
