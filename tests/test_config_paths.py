# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Config Paths
# =============================================================================
# Description:
#   Модульные тесты для проверки конфигурационного параметра app_name ('ai-tc')
#   и корректного восстановления путей к data (%LOCALAPPDATA%), а также
#   к logs и tmp (%APPDATA%).
#
# Usage Examples:
#   CLI:
#     pytest tests/test_config_paths.py -v
#
# File: test_config_paths.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-27 23:07:00
# =============================================================================

"""Модульные тесты конфигурации и путей приложения (`test_config_paths`)."""

import json
import os
from pathlib import Path
import pytest

from header import __root__, APP_NAME
from src.config import app_name, app_dir, data_dir, logs_dir, tmp_dir, global_settings


def test_config_json_contains_app_name() -> None:
    """Проверяет наличие параметра app_name со значением 'ai-tc' / 'ai-tc' в config.json."""
    config_file = __root__ / 'config.json'
    assert config_file.exists(), "Файл config.json должен существовать в корне проекта"

    with open(config_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    assert str(data.get('app_name')).lower() == 'ai-tc', "В корневом уровне config.json должен быть задан 'app_name': 'ai-tc'"
    assert str(data.get('app', {}).get('app_name')).lower() == 'ai-tc', "В блоке 'app' также должен быть задан 'app_name': 'ai-tc'"


def test_header_exports_app_name() -> None:
    """Проверяет экспорт APP_NAME из модуля header и регистрацию в os.environ."""
    assert APP_NAME.lower() == 'ai-tc', f"APP_NAME в header.py должен быть 'ai-tc', получено: {APP_NAME}"
    assert (os.environ.get('APP_NAME') or '').lower() == 'ai-tc', "Переменная окружения APP_NAME должна быть 'ai-tc'"


def test_src_config_exports_and_types() -> None:
    """Проверяет атрибуты путей и имени приложения, экспортируемые из src.config."""
    assert app_name.lower() == 'ai-tc', f"app_name в src.config должен быть 'ai-tc', получено: {app_name}"
    assert isinstance(app_dir, Path), "app_dir должен быть объектом Path"
    assert isinstance(data_dir, Path), "data_dir должен быть объектом Path"
    assert isinstance(logs_dir, Path), "logs_dir должен быть объектом Path"
    assert isinstance(tmp_dir, Path), "tmp_dir должен быть объектом Path"


def test_localappdata_data_path_resolution() -> None:
    """Проверяет, что data_dir указывает на рабочую директорию в %LOCALAPPDATA%."""
    localappdata = os.getenv('LOCALAPPDATA')
    if localappdata:
        expected_root = Path(localappdata) / app_name
        assert app_dir.resolve() == expected_root.resolve(), f"app_dir должен совпадать с {expected_root}"
        assert data_dir.resolve() == (expected_root / 'data').resolve(), f"data_dir должен совпадать с {expected_root / 'data'}"
    assert data_dir.name == 'data', "Каталог данных должен называться 'data'"
    assert data_dir.exists(), "Директория data должна существовать на диске"


def test_appdata_logs_and_tmp_path_resolution() -> None:
    """Проверяет, что logs_dir и tmp_dir разрешаются через %APPDATA% / app_name."""
    appdata = os.getenv('APPDATA')
    if appdata:
        expected_base = Path(appdata) / app_name
        assert logs_dir.resolve() == (expected_base / 'logs').resolve(), f"logs_dir должен быть {expected_base / 'logs'}"
        assert tmp_dir.resolve() == (expected_base / 'tmp').resolve(), f"tmp_dir должен быть {expected_base / 'tmp'}"
    assert logs_dir.name == 'logs', "Каталог логов должен называться 'logs'"
    assert tmp_dir.name == 'tmp', "Каталог временных файлов должен называться 'tmp'"
    assert logs_dir.exists(), "Директория logs_dir должна существовать"
    assert tmp_dir.exists(), "Директория tmp_dir должна существовать"

