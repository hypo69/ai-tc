# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Root - Header
# =============================================================================
# Description:
#   Определение корневого каталога проекта (__root__) и нормализация системных путей.
#
#   Зачем нужен этот модуль:
#     1. Единый источник истины для импортов: гарантирует корректную загрузку внутренних
#        пакетов (src, apps, logger) независимо от рабочей директории, из которой запущен скрипт.
#     2. Кроссплатформенная нормализация: выравнивает переменные окружения USERPROFILE/HOME
#        и добавляет __root__ в sys.path.
#     3. Поддержка внешних переопределений: считывает переменную AIWINDOWSADMIN_DIR при наличии.
#     4. Определение имени приложения (APP_NAME) и регистрация в окружении.
#
# Usage Examples:
#   Python API:
#     import header
#     from header import __root__, APP_NAME
#
#     config_path = __root__ / "config.json"
#
# File: header.py
# Project: ai-windows-admin
# Package: root
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-27 23:02:00
# =============================================================================

import json
import os
import sys
from pathlib import Path

if 'USERPROFILE' not in os.environ and 'HOME' in os.environ:
    os.environ['USERPROFILE'] = os.environ['HOME']
elif 'HOME' not in os.environ and 'USERPROFILE' in os.environ:
    os.environ['HOME'] = os.environ['USERPROFILE']
elif 'USERPROFILE' not in os.environ and 'HOME' not in os.environ:
    try:
        _home = str(Path.home())
    except Exception:
        _home = str(Path(__file__).resolve().parent)
    os.environ['USERPROFILE'] = _home
    os.environ['HOME'] = _home

#marker_files: list = ['__root__', '.git']
marker_files: list = ['__root__']


def set_project_root(marker_files=marker_files) -> Path:
    """Определяет корневую директорию проекта, начиная с директории текущего файла.

    Поиск выполняется вверх по дереву каталогов до первого каталога, содержащего marker_files.
    Также учитывает переменную окружения AIWINDOWSADMIN_DIR и fallback на %LOCALAPPDATA%/<app_name>.

    Args:
        marker_files (tuple): Имена файлов или директорий-маркеров корня.

    Returns:
        Path: Путь к корню проекта.
    """
    env_dir = os.environ.get('AITC_DIR') or os.environ.get('AI_TC_DIR') or os.environ.get('AIWINDOWSADMIN_DIR', '')
    if env_dir:
        env_path = Path(env_dir).resolve()
        if env_path.exists() and (env_path / 'config.json').exists():
            if str(env_path) not in sys.path:
                sys.path.insert(0, str(env_path))
            return env_path
    __root__: Path
    current_path: Path = Path(__file__).resolve().parent
    __root__ = current_path
    found = False
    for parent in [current_path] + list(current_path.parents):
        if any(((parent / marker).exists() for marker in marker_files)):
            __root__ = parent
            found = True
            break
    if not found:
        local_app_data = os.environ.get('LOCALAPPDATA')
        if local_app_data:
            candidate = Path(local_app_data) / os.environ.get('APP_NAME', 'ai-tc')
            if candidate.exists() and (candidate / 'config.json').exists():
                __root__ = candidate
    if str(__root__) not in sys.path:
        sys.path.insert(0, str(__root__))
    return __root__


__root__: Path = set_project_root()
'__root__ (Path): Path to the root directory of the project'


def _load_app_name(root: Path) -> str:
    """Извлекает имя рабочего каталога приложения из config.json или окружения."""
    if os.environ.get('APP_NAME'):
        return os.environ['APP_NAME']
    cfg = root / 'config.json'
    if cfg.exists():
        try:
            with open(cfg, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('app_name') or data.get('app', {}).get('app_name') or 'ai-tc'
        except Exception:
            pass
    return 'ai-tc'


APP_NAME: str = _load_app_name(__root__)
os.environ['APP_NAME'] = APP_NAME

