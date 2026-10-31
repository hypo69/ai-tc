# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Project Installer & Prerequisites
# =============================================================================
# Description:
#   Модульные тесты для проверки готовности проекта к установке:
#   наличия requirements.txt, .env.example, профилей зависимостей,
#   корректности установочных путей и работоспособности утилиты
#   валидации verify_installation.py.
#
# Usage Examples:
#   CLI:
#     pytest tests/test_project_installer.py -v
#
# File: test_project_installer.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 19:10:00
# =============================================================================

"""Тесты готовности проекта к установке и навыка project-installer."""

import os
from pathlib import Path
import pytest

from header import __root__
from scripts.cli.paths import get_paths


def test_requirements_files_presence() -> None:
    """Проверяет наличие основного requirements.txt и профилей установки в install/req/."""
    main_req = __root__ / 'requirements.txt'
    assert main_req.is_file(), "Файл requirements.txt должен существовать в корне проекта"

    content = main_req.read_text(encoding='utf-8')
    assert 'fastapi' in content, "requirements.txt должен содержать fastapi"
    assert 'uvicorn' in content, "requirements.txt должен содержать uvicorn"
    assert 'pydantic' in content, "requirements.txt должен содержать pydantic"
    assert 'google-genai' in content, "requirements.txt должен содержать google-genai"

    # Проверка профилей в install/req
    req_dir = __root__ / 'install' / 'req'
    assert req_dir.is_dir(), "Директория install/req должна существовать"
    assert (req_dir / 'requirements-core.txt').is_file()
    assert (req_dir / 'requirements-ai.txt').is_file()
    assert (req_dir / 'requirements-test.txt').is_file()
    assert (req_dir / 'requirements-docs.txt').is_file()


def test_env_example_contains_mandatory_keys() -> None:
    """Проверяет шаблон .env.example на наличие ключевых переменных конфигурации."""
    env_example = __root__ / '.env.example'
    assert env_example.is_file(), "Файл .env.example должен присутствовать в корне"

    content = env_example.read_text(encoding='utf-8')
    mandatory_keys = [
        'APP_NAME',
        'GEMINI_API_KEY',
        'JWT_SECRET',
        'ADMIN_PASSWORD',
        'MARIADB_HOST',
        'SSL_CERT_FILE',
    ]
    for key in mandatory_keys:
        assert key in content, f"Ключ {key} должен быть объявлен в .env.example"


def test_installation_paths_resolution() -> None:
    """Проверяет пути установщика в модуле scripts/cli/paths.py."""
    paths = get_paths()
    assert paths.project_root.resolve() == __root__.resolve()
    assert paths.requirements_main.name == 'requirements.txt'
    assert paths.requirements_main.exists()
    assert paths.secrets_dir == __root__ / 'src' / 'secrets'
    assert paths.config_file.exists()


def test_install_instruction_presence() -> None:
    """Проверяет наличие инструкций по установке в корне и в навыке."""
    root_instruction = __root__ / 'INSTALL-INSTRUCTION.md'
    skill_instruction = __root__ / '.agents' / 'skills' / 'project-installer' / 'INSTALL-INSTRUCTION.md'
    skill_def = __root__ / '.agents' / 'skills' / 'project-installer' / 'SKILL.md'

    assert root_instruction.is_file(), "INSTALL-INSTRUCTION.md должен существовать в корне проекта"
    assert skill_instruction.is_file(), "INSTALL-INSTRUCTION.md должен существовать в папке навыка"
    assert skill_def.is_file(), "SKILL.md должен существовать в папке навыка"


def test_verification_script_passes() -> None:
    """Проверяет выполнение утилиты InstallationVerifier."""
    import importlib.util
    verifier_path = __root__ / '.agents' / 'skills' / 'project-installer' / 'scripts' / 'verify_installation.py'
    assert verifier_path.is_file(), "Скрипт verify_installation.py должен существовать"

    spec = importlib.util.spec_from_file_location("verify_installation", str(verifier_path))
    assert spec and spec.loader
    import sys
    mod = importlib.util.module_from_spec(spec)
    sys.modules["verify_installation"] = mod
    spec.loader.exec_module(mod)
    verifier = mod.InstallationVerifier(project_root=__root__)
    result = verifier.verify_all()

    assert result.is_valid is True, f"Проверка установки должна быть успешной, ошибки: {result.errors}"
    assert len(result.missing_directories) == 0, f"Отсутствующие каталоги: {result.missing_directories}"
    assert len(result.missing_files) == 0, f"Отсутствующие файлы: {result.missing_files}"
