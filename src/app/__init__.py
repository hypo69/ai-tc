# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin App - Dependency Injection & App Registry
# =============================================================================
# Description:
#   Контейнер внедрения зависимостей (DI) и реестр микроприложений /apps
#   для интеграции в единый сервер и меню администратора.
#
# File: __init__.py
# Project: ai-windows-admin
# Package: src.app
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 14:35:00
# =============================================================================

from __future__ import annotations

from pathlib import Path
import threading
from typing import Any, Callable, Dict, List, Optional

try:
    from logger import logger
except ImportError:
    import logging
    logger = logging.getLogger("app_container")

from src.utils.common import load_json_config


class AppContainer:
    """Контейнер внедрения зависимостей (Dependency Injection Container).

    Управляет синглтонами, фабриками компонентов, конфигурацией и доступом
    к базам данных без использования скрытых глобальных переменных.
    Обеспечивает потокобезопасное разрешение сервисов через RLock.
    """

    def __init__(self, config_path: Optional[Path | str] = None) -> None:
        """Инициализирует контейнер зависимостей.

        Args:
            config_path: Путь к основному файлу конфигурации.
        """
        self._lock = threading.RLock()
        self.config_path = Path(config_path) if config_path else Path("config.json")
        self._config: Dict[str, Any] = load_json_config(self.config_path)
        self._services: Dict[str, Any] = {}
        self._factories: Dict[str, Callable[[], Any]] = {}

    @property
    def config(self) -> Dict[str, Any]:
        """Возвращает текущую загруженную конфигурацию."""
        with self._lock:
            return self._config

    def reload_config(self) -> Dict[str, Any]:
        """Выполняет горячую перезагрузку конфигурации из файла."""
        with self._lock:
            self._config = load_json_config(self.config_path)
            logger.info("[AppContainer] Конфигурация успешно перезагружена.")
            return self._config

    def register_singleton(self, service_name: str, instance: Any) -> None:
        """Регистрирует готовый экземпляр сервиса.

        Args:
            service_name: Идентификатор сервиса.
            instance: Экземпляр сервиса.
        """
        if not service_name or not isinstance(service_name, str):
            raise ValueError("Имя сервиса должно быть непустой строкой.")
        with self._lock:
            self._services[service_name] = instance

    def register_factory(self, service_name: str, factory: Callable[[], Any]) -> None:
        """Регистрирует фабрику для создания сервиса по запросу.

        Args:
            service_name: Идентификатор сервиса.
            factory: Функция-фабрика.
        """
        if not service_name or not isinstance(service_name, str):
            raise ValueError("Имя сервиса должно быть непустой строкой.")
        if not callable(factory):
            raise TypeError("Фабрика сервиса должна быть вызываемым объектом.")
        with self._lock:
            self._factories[service_name] = factory

    def resolve(self, service_name: str) -> Any:
        """Разрешает и возвращает зависимость по имени.

        Args:
            service_name: Идентификатор сервиса.

        Returns:
            Экземпляр сервиса.

        Raises:
            KeyError: Если сервис не зарегистрирован.
        """
        with self._lock:
            if service_name in self._services:
                return self._services[service_name]
            if service_name in self._factories:
                instance = self._factories[service_name]()
                self._services[service_name] = instance
                return instance
        raise KeyError(f"Сервис '{service_name}' не зарегистрирован в контейнере.")


class AppRegistry:
    """Реестр микроприложений экосистемы /apps."""

    def __init__(self, apps_root: Path | str = "apps") -> None:
        """Инициализирует реестр приложений.

        Args:
            apps_root: Корневая директория поиска приложений.
        """
        self._lock = threading.RLock()
        self.apps_root = Path(apps_root)
        self._registered_apps: Dict[str, Dict[str, Any]] = {}

    def discover_and_register_apps(self) -> List[Dict[str, Any]]:
        """Автоматически обнаруживает приложения в директории /apps.

        Returns:
            Список метаданных зарегистрированных приложений.
        """
        with self._lock:
            if not self.apps_root.is_dir():
                return []

            for item in self.apps_root.iterdir():
                if item.is_dir() and not item.name.startswith((".", "_", "~")):
                    manifest_path = item / "manifest.json"
                    app_info = {
                        "id": item.name,
                        "name": item.name.replace("_", " ").title(),
                        "path": str(item),
                        "enabled": True,
                    }
                    if manifest_path.is_file():
                        custom_manifest = load_json_config(manifest_path)
                        if isinstance(custom_manifest, dict):
                            app_info.update(custom_manifest)

                    self._registered_apps[item.name] = app_info

            return list(self._registered_apps.values())

    def get_registered_apps(self) -> List[Dict[str, Any]]:
        """Возвращает список зарегистрированных приложений для меню администратора."""
        with self._lock:
            return list(self._registered_apps.values())


# Глобальные экземпляры по умолчанию
default_container = AppContainer()
default_registry = AppRegistry()
