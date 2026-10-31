# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Installer - Verification Utility
# =============================================================================
# Description:
#   Автоматическая утилита проверки целостности структуры директорий,
#   файлов конфигурации, виртуального окружения и ключевых зависимостей
#   проекта AI Windows Admin (ai-tc).
#
# Usage Examples:
#   CLI:
#     python .agents/skills/project-installer/scripts/verify_installation.py
#     python .agents/skills/project-installer/scripts/verify_installation.py --json
#
# File: verify_installation.py
# Project: ai-windows-admin
# Package: .agents.skills.project-installer.scripts
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 19:10:00
# =============================================================================

from __future__ import annotations
"""Автоматическая утилита проверки целостности установки AI Windows Admin."""

import argparse
import importlib
import json
import os
import platform
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Поиск корневого каталога проекта и добавление в sys.path
_current = Path(__file__).resolve().parent
_found_root: Optional[Path] = None
for parent in [_current] + list(_current.parents):
    if (parent / '__root__').exists() or ((parent / 'header.py').exists() and (parent / 'config.json').exists()):
        _found_root = parent
        break

_root_dir = _found_root if _found_root else Path.cwd().resolve()
if str(_root_dir) not in sys.path:
    sys.path.insert(0, str(_root_dir))

try:
    import header
    from logger import logger
except Exception:
    class _FallbackLogger:
        """Резервный логгер для консольного вывода при отсутствии пакета logger."""
        @staticmethod
        def console(*args: object, **kwargs: object) -> None:
            """Выводит сообщение в стандартный вывод."""
            print(*args, **kwargs)
    logger = _FallbackLogger()


@dataclass
class VerificationResult:
    """Объект данных с результатами проверки целостности установки проекта."""
    is_valid: bool = True
    os_name: str = platform.system()
    project_root: str = ''
    missing_directories: List[str] = field(default_factory=list)
    existing_directories: List[str] = field(default_factory=list)
    missing_files: List[str] = field(default_factory=list)
    existing_files: List[str] = field(default_factory=list)
    venv_status: Dict[str, str] = field(default_factory=dict)
    module_status: Dict[str, str] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class InstallationVerifier:
    """Валидатор целостности файловой структуры и готовности среды AI Windows Admin."""

    REQUIRED_DIRECTORIES: List[str] = [
        'apps', 'src', 'scripts', 'launchers', 'docs', 'tests',
        'install', 'data', 'logger', '.agents'
    ]
    REQUIRED_FILES: List[str] = [
        'header.py', 'config.json', 'requirements.txt', 'INSTALL-INSTRUCTION.md'
    ]
    ALTERNATIVE_FILES: List[Tuple[str, str]] = [
        ('.env', '.env.example')
    ]
    CORE_MODULES: List[str] = [
        'fastapi', 'uvicorn', 'pydantic', 'dotenv', 'cryptography',
        'aiohttp', 'platformdirs', 'psutil'
    ]

    def __init__(self, project_root: Optional[Path] = None):
        """Инициализирует верификатор установки.

        Args:
            project_root: Корневой каталог проекта. Если не передан, определяется автоматически.
        """
        self.root: Path = project_root.resolve() if project_root else _root_dir

    def check_directories(self, result: VerificationResult) -> None:
        """Проверяет наличие обязательных системных каталогов.

        Args:
            result: Объект результатов для наполнения.
        """
        for dir_name in self.REQUIRED_DIRECTORIES:
            dir_path: Path = self.root / dir_name
            if dir_path.is_dir():
                result.existing_directories.append(dir_name)
            else:
                result.missing_directories.append(dir_name)
                result.is_valid = False
                result.errors.append(f"Отсутствует обязательный каталог: {dir_name}")

    def check_files(self, result: VerificationResult) -> None:
        """Проверяет наличие ключевых файлов конфигурации и зависимостей.

        Args:
            result: Объект результатов для наполнения.
        """
        for file_name in self.REQUIRED_FILES:
            file_path: Path = self.root / file_name
            if file_path.is_file():
                result.existing_files.append(file_name)
            else:
                result.missing_files.append(file_name)
                result.is_valid = False
                result.errors.append(f"Отсутствует обязательный файл: {file_name}")

        for primary, fallback in self.ALTERNATIVE_FILES:
            has_primary: bool = (self.root / primary).is_file()
            has_fallback: bool = (self.root / fallback).is_file()
            if has_primary:
                result.existing_files.append(primary)
            elif has_fallback:
                result.existing_files.append(fallback)
                result.warnings.append(f"Файл {primary} отсутствует, используется шаблон {fallback}")
            else:
                result.missing_files.append(primary)
                result.warnings.append(f"Не найдены ни {primary}, ни резервный {fallback}")

    def check_virtual_environment(self, result: VerificationResult) -> Optional[Path]:
        """Проверяет статус и исполняемые файлы виртуального окружения.

        Args:
            result: Объект результатов для наполнения.

        Returns:
            Optional[Path]: Путь к бинарному файлу Python в venv, либо None.
        """
        venv_dir: Path = self.root / 'venv'
        is_windows: bool = platform.system() == 'Windows'
        if is_windows:
            py_exe: Path = venv_dir / 'Scripts' / 'python.exe'
            pip_exe: Path = venv_dir / 'Scripts' / 'pip.exe'
        else:
            py_exe = venv_dir / 'bin' / 'python'
            pip_exe = venv_dir / 'bin' / 'pip'

        if venv_dir.is_dir() and py_exe.is_file():
            result.venv_status['path'] = str(py_exe)
            result.venv_status['pip'] = str(pip_exe) if pip_exe.is_file() else 'not_found'
            result.venv_status['status'] = 'active'
            try:
                proc = subprocess.run([str(py_exe), '--version'], capture_output=True, text=True, timeout=5)
                result.venv_status['version'] = proc.stdout.strip() or proc.stderr.strip()
            except Exception as ex:
                result.venv_status['version_check_error'] = str(ex)
            return py_exe
        else:
            result.venv_status['path'] = 'missing'
            result.venv_status['status'] = 'missing'
            result.warnings.append(f"Виртуальное окружение отсутствует по пути {venv_dir}. Создайте venv.")
            return None

    def check_core_modules(self, result: VerificationResult, python_exe: Optional[Path] = None) -> None:
        """Проверяет возможность импорта базовых библиотек проекта.

        Args:
            result: Объект результатов для наполнения.
            python_exe: Бинарник python в venv (если доступен).
        """
        if python_exe and python_exe.is_file():
            for module_name in self.CORE_MODULES:
                try:
                    proc = subprocess.run(
                        [str(python_exe), '-c', f'import {module_name}'],
                        capture_output=True, text=True, timeout=5
                    )
                    if proc.returncode == 0:
                        result.module_status[module_name] = 'ok'
                    else:
                        result.module_status[module_name] = 'missing'
                        result.warnings.append(f"Модуль '{module_name}' не импортируется в venv: {proc.stderr.strip()[:80]}")
                except Exception as ex:
                    result.module_status[module_name] = f'error: {ex}'
        else:
            for module_name in self.CORE_MODULES:
                try:
                    importlib.import_module(module_name)
                    result.module_status[module_name] = 'ok'
                except ImportError:
                    result.module_status[module_name] = 'missing'
                    result.warnings.append(f"Модуль '{module_name}' не установлен в текущем окружении Python")
                except Exception as ex:
                    result.module_status[module_name] = f'load_error: {type(ex).__name__}'

    def verify_all(self) -> VerificationResult:
        """Выполняет полную проверку директорий, файлов, venv и модулей.

        Returns:
            VerificationResult: Заполненный объект проверки.
        """
        result: VerificationResult = VerificationResult(project_root=str(self.root))
        self.check_directories(result)
        self.check_files(result)
        python_exe: Optional[Path] = self.check_virtual_environment(result)
        self.check_core_modules(result, python_exe)
        return result


def main() -> int:
    """Точка входа CLI для проверки установки.

    Returns:
        int: Код возврата 0 при успешной валидации, 1 при ошибках.
    """
    parser = argparse.ArgumentParser(description="Проверка целостности установки и директорий AI Windows Admin.")
    parser.add_argument('--project-root', type=str, default='', help="Путь к корню проекта AI Windows Admin")
    parser.add_argument('--json', action='store_true', help="Вывод в структурированном формате JSON")
    args = parser.parse_args()

    project_root_path: Optional[Path] = Path(args.project_root) if args.project_root else None
    verifier: InstallationVerifier = InstallationVerifier(project_root_path)
    result: VerificationResult = verifier.verify_all()

    if args.json:
        logger.console(json.dumps(asdict(result), indent=2, ensure_ascii=False))
    else:
        logger.console('=' * 65)
        logger.console('🔍 Проверка целостности установки AI Windows Admin (ai-tc)')
        logger.console('=' * 65)
        logger.console(f'Корень проекта: {result.project_root}')
        logger.console(f'Платформа:      {result.os_name}')
        logger.console(f"Статус:         {('✅ УСПЕШНО (PASSED)' if result.is_valid else '❌ ОШИБКА (FAILED)')}")
        logger.console('-' * 65)
        logger.console(f'Каталоги:       {len(result.existing_directories)} проверено, {len(result.missing_directories)} отсутствует')
        logger.console(f'Файлы:          {len(result.existing_files)} проверено, {len(result.missing_files)} отсутствует')
        logger.console(f"Окружение venv: {result.venv_status.get('status', 'unknown')} ({result.venv_status.get('path', 'N/A')})")

        if result.module_status:
            ok_mods = sum(1 for v in result.module_status.values() if v == 'ok')
            logger.console(f'Модули:         {ok_mods}/{len(result.module_status)} успешно импортированы')

        if result.errors:
            logger.console('\n❌ Ошибки:')
            for err in result.errors:
                logger.console(f'  • {err}')

        if result.warnings:
            logger.console('\n⚠️ Предупреждения:')
            for warn in result.warnings:
                logger.console(f'  • {warn}')
        logger.console('=' * 65)

    return 0 if result.is_valid else 1


if __name__ == '__main__':
    sys.exit(main())
