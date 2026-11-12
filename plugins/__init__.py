# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Dynamic Plugin Loader and Registry
# =============================================================================
# Description:
#   Discovers, dynamically imports, initializes, and manages all extension plugins
#   in the AI Breadboard environment with configuration and environment overrides.
#
# File: __init__.py
# Project: ai-breadboard
# Package: plugins
# Author: hypo69
# Updated: 2026-11-10 14:37:00
# Copyright: © 2026 hypo69
# =============================================================================

"""Динамический загрузчик и реестр модульных плагинов системы.

Обеспечивает автоматическое обнаружение, импорт и инициализацию экземпляров BasePlugin
из поддиректорий plugins/ (system-plugins, developer-plugins, user-plugins), проверку
флагов активности в конфигурации и управление жизненным циклом.
"""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from header import __root__
from logger import logger
from src.config import global_settings
from plugins.base import BasePlugin

# Расширение __path__ для корректного импорта из подпапок категорий плагинов
_plugins_dir: Path = __root__ / "plugins"
if _plugins_dir.exists() and _plugins_dir.is_dir():
    for _sub in _plugins_dir.iterdir():
        if _sub.is_dir() and not _sub.name.startswith(("_", ".")):
            if str(_sub) not in __path__:
                __path__.append(str(_sub))

__all__ = ["BasePlugin", "load_plugins"]


def _discover_plugin_directories(plugins_dir: Path) -> List[Tuple[Path, str]]:
    """Обнаруживает все директории плагинов в корне plugins/ и подпапках категорий.

    Args:
        plugins_dir (Path): Корневая директория плагинов.

    Returns:
        List[Tuple[Path, str]]: Список кортежей (путь к плагину, скоуп/категория).
    """
    discovered: List[Tuple[Path, str]] = []
    if not plugins_dir.exists() or not plugins_dir.is_dir():
        return discovered

    for item in plugins_dir.iterdir():
        if not item.is_dir() or item.name.startswith(("_", ".")):
            continue

        # Прямая директория плагина в корне plugins/
        if (item / "__init__.py").exists():
            discovered.append((item, "user"))
        else:
            # Поддиректория категории (developer-plugins, system-plugins, user-plugins)
            cat_name = item.name.lower()
            if "developer" in cat_name:
                category = "developer"
            elif "system" in cat_name:
                category = "system"
            elif "user" in cat_name:
                category = "user"
            else:
                category = "user"

            for sub_item in item.iterdir():
                if (
                    sub_item.is_dir()
                    and not sub_item.name.startswith(("_", "."))
                    and (sub_item / "__init__.py").exists()
                ):
                    discovered.append((sub_item, category))

    return discovered


def _parse_plugins_config(plugins_cfg: Any) -> tuple[Optional[set[str]], set[str], Dict[str, Any]]:
    """Парсинг секции конфигурации плагинов (списки enabled/disabled, плоский список или словарь).

    Args:
        plugins_cfg (Any): Данные конфигурации плагинов из config.json.

    Returns:
        tuple[Optional[set[str]], set[str], Dict[str, Any]]:
            Кортеж из (множество включенных плагинов или None, множество отключенных, словарь индивидуальных настроек).
    """
    enabled_set: Optional[set[str]] = None
    disabled_set: set[str] = set()
    plugin_configs: Dict[str, Any] = {}

    if isinstance(plugins_cfg, list):
        enabled_set = {str(item).strip().lower() for item in plugins_cfg if item}
    elif isinstance(plugins_cfg, dict):
        has_enabled_key = "enabled" in plugins_cfg and isinstance(plugins_cfg["enabled"], list)
        has_disabled_key = "disabled" in plugins_cfg and isinstance(plugins_cfg["disabled"], list)

        if has_enabled_key:
            enabled_set = {str(item).strip().lower() for item in plugins_cfg["enabled"] if item}
        if has_disabled_key:
            disabled_set = {str(item).strip().lower() for item in plugins_cfg["disabled"] if item}

        for k, v in plugins_cfg.items():
            if k not in ("enabled", "disabled") and isinstance(v, dict):
                plugin_configs[k.strip().lower()] = v
    return enabled_set, disabled_set, plugin_configs


def load_plugins(ai_model: Any = None, include_disabled: bool = False) -> Dict[str, BasePlugin]:
    """Обнаружение, загрузка и инициализация плагинов в директории plugins.

    Args:
        ai_model (Any): Опциональный экземпляр модели ИИ для внедрения в плагины.
        include_disabled (bool): Если True, в результирующий словарь включаются также
            отключенные плагины со статусом enabled=False (необходимо для отображения
            в WebGUI и управления через интерфейс).

    Returns:
        Dict[str, BasePlugin]: Словарь соответствия имен плагинов их инициализированным экземплярам.
    """
    plugins_dir: Path = __root__ / "plugins"
    plugins: Dict[str, BasePlugin] = {}

    if not plugins_dir.exists() or not plugins_dir.is_dir():
        logger.warning(f"Директория плагинов не найдена по пути {plugins_dir}")
        return plugins

    disabled_env_raw = os.getenv("DISABLED_PLUGINS", "")
    disabled_env = {
        name.strip().lower()
        for name in disabled_env_raw.replace(",", " ").split()
        if name.strip()
    }

    cfg_env = os.getenv("AIBREADBOARD_CONFIG") or os.getenv("CONFIG_FILE")
    active_path: Optional[Path] = None
    if cfg_env:
        p = Path(cfg_env)
        active_path = p if p.is_absolute() else (__root__ / cfg_env)

    if not active_path or not active_path.exists():
        if (__root__ / "config_tc.json").exists() and not (__root__ / "config.json").exists():
            active_path = __root__ / "config_tc.json"
        else:
            active_path = __root__ / "config.json"

    raw_plugins_cfg: Any = {}
    if active_path and active_path.exists():
        try:
            with open(active_path, "r", encoding="utf-8") as f:
                root_cfg = json.load(f)
                raw_plugins_cfg = root_cfg.get("plugins", {})
        except Exception as e:
            logger.error(f"Ошибка чтения конфигурации плагинов из {active_path}: {e}")
    else:
        raw_plugins_cfg = getattr(global_settings, "plugins", {})
        if hasattr(raw_plugins_cfg, "__dict__"):
            raw_plugins_cfg = dict(raw_plugins_cfg.__dict__)

    if hasattr(raw_plugins_cfg, "__dict__"):
        raw_plugins_cfg = dict(raw_plugins_cfg.__dict__)

    enabled_set, disabled_set, plugin_configs = _parse_plugins_config(raw_plugins_cfg)

    for item, cat in _discover_plugin_directories(plugins_dir):
        plugin_key = item.name.lower()
        plugin_mod_name = f"plugins.{item.name}"

        try:
            module = importlib.import_module(plugin_mod_name)
            if not hasattr(module, "plugin") or not callable(module.plugin):
                logger.debug(f"Модуль {plugin_mod_name} не предоставляет вызываемую фабрику 'plugin'.")
                continue

            instance: BasePlugin = module.plugin(ai_model=ai_model)
            if not isinstance(instance, BasePlugin):
                logger.warning(
                    f"Фабрика {plugin_mod_name}.plugin() вернула объект типа {type(instance)}, ожидался BasePlugin."
                )
                continue

            # Установка области видимости (scope)
            instance.scope = cat
            aliases = {instance.name.lower(), plugin_key}
            plugin_specific_cfg = (
                plugin_configs.get(instance.name.lower()) or plugin_configs.get(plugin_key) or {}
            )

            # Вычисление статуса активности плагина
            is_enabled = True
            if aliases.intersection(disabled_env):
                is_enabled = False
            elif aliases.intersection(disabled_set):
                is_enabled = False
            elif enabled_set is not None:
                is_enabled = bool(aliases.intersection(enabled_set))

            if isinstance(plugin_specific_cfg, dict) and plugin_specific_cfg.get("enabled") is False:
                is_enabled = False

            local_cfg_path = item / "config.json"
            if local_cfg_path.exists():
                try:
                    with open(local_cfg_path, "r", encoding="utf-8") as lf:
                        local_data = json.load(lf)
                        if local_data.get("enabled") is False or local_data.get("active") is False:
                            is_enabled = False
                except Exception:
                    pass

            instance.enabled = is_enabled

            # Если include_disabled=False, отсекаем отключенные плагины
            if not include_disabled and not is_enabled:
                logger.debug(f"Плагин '{instance.name}' отключен в конфигурации (пропуск загрузки).")
                continue

            # Объединение настроек из конфигурации
            if isinstance(plugin_specific_cfg, dict) and "config" in plugin_specific_cfg:
                instance.update_config(plugin_specific_cfg["config"])

            plugins[instance.name] = instance
            logger.info(
                f"Зарегистрирован плагин: '{instance.name}' (v{instance.version}, scope={instance.scope}, enabled={instance.enabled})"
            )

        except Exception as exc:
            logger.error(f"Не удалось загрузить плагин из '{item.name}': {exc}", exc_info=True)

    return plugins
