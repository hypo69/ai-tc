# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin CORE - Config Module
# =============================================================================
# Description:
#   Модуль основной системы (`config`).
#   Определяет глобальные параметры конфигурации, загрузку config.json,
#   разрешение рабочих путей (%LOCALAPPDATA%/<app_name>/data) и путей к логам
#   и временным файлам (%APPDATA%/<app_name>/logs, %APPDATA%/<app_name>/tmp).
#
# Usage Examples:
#   Python API:
#     from src.config import app_name, app_dir, data_dir, logs_dir, tmp_dir
#     from src.config import is_app_enabled
#
#     print(app_name, data_dir, logs_dir, tmp_dir)
#
# File: config.py
# Project: ai-windows-admin
# Package: src
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 16:43:00
# =============================================================================

"""Модуль основной системы (`config`)."""

import os
from pathlib import Path
from types import SimpleNamespace
from src.utils.jjson import j_loads_ns
from header import __root__
from logger import logger

_cfg_env = os.getenv('AITC_CONFIG') or os.getenv('AI_TC_CONFIG') or os.getenv('AIWINDOWSADMIN_CONFIG') or os.getenv('CONFIG_FILE')
if _cfg_env:
    _cfg_path = Path(_cfg_env)
    if _cfg_path.is_absolute() and _cfg_path.exists():
        CONFIG_FILE = _cfg_path
    elif (__root__ / _cfg_env).exists():
        CONFIG_FILE = __root__ / _cfg_env
    elif (__root__ / 'apps' / 'windows' / _cfg_path.name).exists():
        CONFIG_FILE = __root__ / 'apps' / 'windows' / _cfg_path.name
    elif (__root__ / 'config' / _cfg_path.name).exists():
        CONFIG_FILE = __root__ / 'config' / _cfg_path.name
    else:
        CONFIG_FILE = __root__ / 'config.json'
else:
    CONFIG_FILE = __root__ / 'config.json'

if not CONFIG_FILE.exists() and (__root__ / 'config.json').exists():
    CONFIG_FILE = __root__ / 'config.json'

global_settings = j_loads_ns(CONFIG_FILE)

# Название рабочей директории и приложения
app_name: str = (
    getattr(global_settings, 'app_name', None)
    or getattr(getattr(global_settings, 'app', None), 'app_name', None)
    or os.getenv('APP_NAME')
    or 'ai-tc'
)
APP_NAME: str = app_name
os.environ['APP_NAME'] = APP_NAME

# Базовые системные пути окружения
localappdata_base: str = os.getenv('LOCALAPPDATA') or str(Path.home() / 'AppData' / 'Local')
appdata_base: str = os.getenv('APPDATA') or str(Path.home() / 'AppData' / 'Roaming')

# Рабочая директория: %LOCALAPPDATA% / app_name
app_dir: Path = Path(localappdata_base) / APP_NAME
if not app_dir.exists() and __root__.exists():
    app_dir = __root__
APP_DIR: Path = app_dir

# Внутренний путь к хранилищу данных data
data_dir: Path = app_dir / 'data' if (app_dir / 'data').exists() else (__root__ / 'data')
DATA_DIR: Path = data_dir

# Пути к логам и временным файлам tmp: %APPDATA% / app_name / logs и tmp
appdata_dir: Path = Path(appdata_base) / APP_NAME
logs_dir: Path = appdata_dir / 'logs'
tmp_dir: Path = appdata_dir / 'tmp'
LOGS_DIR: Path = logs_dir
TMP_DIR: Path = tmp_dir

# Автоматическое создание служебных каталогов
for _dir in (data_dir, logs_dir, tmp_dir):
    try:
        _dir.mkdir(parents=True, exist_ok=True)
    except Exception as _e:
        logger.warning(f"Не удалось создать служебный каталог {_dir}: {_e}")

server_cfg = getattr(global_settings, 'server', SimpleNamespace())

# Читаем единую конфигурацию ai_providers_and_models_configuration
ai_cfg_section = getattr(global_settings, 'ai_providers_and_models_configuration', None)
if ai_cfg_section is None:
    ai_cfg_section = getattr(global_settings, 'ai', SimpleNamespace())
ai_cfg = ai_cfg_section
tts_cfg = getattr(global_settings, 'tts', SimpleNamespace())
logging_cfg = getattr(global_settings, 'logging', SimpleNamespace())
pprint_cfg = getattr(global_settings, 'pprint', getattr(global_settings, 'printer', SimpleNamespace()))
printer_cfg = pprint_cfg
storage_cfg = getattr(global_settings, 'storage', SimpleNamespace())

# Устанавливаем значение по умолчанию, если users_dir не задан
if not getattr(storage_cfg, 'users_dir', None):
    storage_cfg.users_dir = str(data_dir / 'users')
raw_dir = getattr(storage_cfg, 'users_dir', None)
if isinstance(raw_dir, str):
    if '%APPDATA%' in raw_dir:
        appdata_path = os.getenv('APPDATA')
        if not appdata_path:
            raise RuntimeError('Переменная окружения APPDATA не установлена')
        resolved_dir = raw_dir.replace('%APPDATA%', appdata_path)
        storage_cfg.users_dir = resolved_dir
        logger.info(f'Resolved users_dir to {resolved_dir}')
    elif '%LOCALAPPDATA%' in raw_dir:
        localappdata_path = os.getenv('LOCALAPPDATA')
        if not localappdata_path:
            raise RuntimeError('Переменная окружения LOCALAPPDATA не установлена')
        resolved_dir = raw_dir.replace('%LOCALAPPDATA%', localappdata_path)
        storage_cfg.users_dir = resolved_dir
        logger.info(f'Resolved users_dir to {resolved_dir}')

    if not getattr(storage_cfg, 'users_dir', None):
        storage_cfg.users_dir = str(data_dir / 'users')
        logger.info(f'Default users_dir set to {storage_cfg.users_dir}')

plugins_cfg = getattr(global_settings, 'plugins', SimpleNamespace())
schedulers_cfg = getattr(global_settings, 'schedulers', getattr(global_settings, 'scheduler', SimpleNamespace()))
apps_cfg = getattr(global_settings, 'apps', SimpleNamespace())


def is_app_enabled(target_app_name: str) -> bool:
    """Проверяет, активно ли приложение согласно текущей конфигурации.

    Args:
        target_app_name (str): Идентификатор приложения (например, 'wikipedia_research', 'network_terminal').

    Returns:
        bool: True, если приложение разрешено и не находится в списке отключенных; иначе False.
    """
    apps_section = getattr(global_settings, 'apps', None)
    if not apps_section:
        return True
    enabled = getattr(apps_section, 'enabled', None)
    disabled = getattr(apps_section, 'disabled', None)
    if disabled is not None:
        disabled_list = list(disabled) if hasattr(disabled, '__iter__') and (not isinstance(disabled, str)) else [disabled]
        if target_app_name in disabled_list:
            return False
    if enabled is not None:
        enabled_list = list(enabled) if hasattr(enabled, '__iter__') and (not isinstance(enabled, str)) else [enabled]
        if len(enabled_list) > 0:
            return target_app_name in enabled_list
    return True


def is_provider_enabled(provider_name: str) -> bool:
    """Проверяет, активен (enabled) ли AI-провайдер согласно текущей конфигурации.

    Args:
        provider_name (str): Имя провайдера (например, 'gemini', 'foundry', 'ollama', 'hf', 'onnx', 'openai').

    Returns:
        bool: True, если провайдер включен (enabled == True); иначе False.
    """
    prov = (provider_name or '').lower().strip()
    if not prov:
        return False
    providers = getattr(ai_cfg, 'providers', None)
    if providers is not None:
        prov_obj = getattr(providers, prov, None) if not isinstance(providers, dict) else providers.get(prov)
        if prov_obj is not None:
            enabled = getattr(prov_obj, 'enabled', None) if not isinstance(prov_obj, dict) else prov_obj.get('enabled')
            if enabled is not None:
                return bool(enabled)
    # По умолчанию встроенные облачные клиенты включены, если не отключены явно
    if prov in ('gemini', 'gemini_cli', 'agy'):
        return True
    return False


def is_debug_mode() -> bool:
    """Проверяет, активен ли режим отладки (DEBUG / DEV).

    Режим отладки считается активным, если:
    - переменная окружения DEBUG установлена в ('1', 'true', 'yes', 'on', 'dev', 'debug')
    - переменная окружения MODE установлена в ('DEV', 'DEBUG')
    - в server_cfg параметр debug == True или mode == 'DEV'/'DEBUG'
    (Исключается при запуске юнит-тестов под pytest).

    Returns:
        bool: True, если активен режим DEBUG, иначе False.
    """
    if os.getenv('PYTEST_CURRENT_TEST'):
        return False
    env_debug = os.getenv('DEBUG', '').strip().lower()
    if env_debug in ('0', 'false', 'no', 'off', 'prod', 'production'):
        return False
    if env_debug in ('1', 'true', 'yes', 'on', 'dev', 'debug'):
        return True
    env_mode = os.getenv('MODE', '').strip().upper()
    if env_mode in ('PROD', 'PRODUCTION'):
        return False
    if env_mode in ('DEV', 'DEBUG'):
        return True
    if getattr(server_cfg, 'debug', False) is True:
        return True
    if str(getattr(server_cfg, 'mode', '')).upper() in ('DEV', 'DEBUG'):
        return True
    return False


from src.utils.ports import load_ports_config, PORTS_FILE
ports_cfg = load_ports_config(PORTS_FILE)

