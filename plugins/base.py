# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Base Plugin Interface Definition
# =============================================================================
# Description:
#   Предоставляет базовый абстрактный класс для всех модульных плагинов платформы,
#   определяющий жизненный цикл, метаданные, действия и обработку сообщений.
#
# File: base.py
# Project: ai-breadboard
# Package: plugins
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 14:37:10
# =============================================================================

"""Модуль базового интерфейса модульной системы плагинов.

Определяет абстрактный класс BasePlugin, от которого наследуются все плагины
для управления жизненным циклом, конфигурацией, выполнением действий и маршрутизацией ИИ.
"""

from __future__ import annotations

import abc
import inspect
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

from logger import logger


class BasePlugin(abc.ABC):
    """Абстрактный базовый класс для всех системных и пользовательских плагинов.

    Attributes:
        name (str): Уникальный машиночитаемый идентификатор плагина.
        title (str): Отображаемый заголовок плагина.
        version (str): Семантическая версия плагина.
        description (str): Краткое описание назначения плагина.
        icon (str): Эмодзи или иконка плагина.
        category (str): Функциональная категория ('communication', 'media', 'tools' и др.).
        enabled (bool): Текущий статус активности плагина.
        ai_model (Any): Опциональный экземпляр ИИ-модели.
        config (Dict[str, Any]): Словарь конфигурации времени выполнения.
    """

    name: str = "base_plugin"
    title: str = "Base Plugin"
    title_i18n: Dict[str, str] = {}
    version: str = "1.0.0"
    description: str = "Base plugin interface."
    description_i18n: Dict[str, str] = {}
    icon: str = "🧩"
    category: str = "general"
    enabled: bool = True
    is_system: bool = True
    scope: str = "system"  # 'system', 'developer' или 'user'

    def __init__(self, ai_model: Any = None, config: Optional[Dict[str, Any]] = None) -> None:
        """Инициализирует экземпляр плагина.

        Args:
            ai_model (Any): Опциональный экземпляр языковой модели.
            config (Optional[Dict[str, Any]]): Начальные переопределения конфигурации.
        """
        self.ai_model: Any = ai_model
        self.config: Dict[str, Any] = config or {}
        self.is_running: bool = False

    def get_title(self, lang: Optional[str] = "en") -> str:
        """Возвращает локализованный заголовок для запрошенного языка.

        Args:
            lang (Optional[str]): Код языка (например, 'ru', 'en').

        Returns:
            str: Локализованный заголовок или заголовок по умолчанию.
        """
        if not lang:
            return self.title
        lang_key = lang.strip().lower().split("-")[0].split("_")[0]
        if self.title_i18n and lang_key in self.title_i18n and self.title_i18n[lang_key]:
            return self.title_i18n[lang_key]
        if self.title_i18n and "en" in self.title_i18n and self.title_i18n["en"]:
            return self.title_i18n["en"]
        return self.title

    def get_description(self, lang: Optional[str] = "en") -> str:
        """Возвращает локализованное описание для запрошенного языка.

        Args:
            lang (Optional[str]): Код языка (например, 'ru', 'en').

        Returns:
            str: Локализованное описание или описание по умолчанию.
        """
        if not lang:
            return self.description
        lang_key = lang.strip().lower().split("-")[0].split("_")[0]
        if self.description_i18n and lang_key in self.description_i18n and self.description_i18n[lang_key]:
            return self.description_i18n[lang_key]
        if self.description_i18n and "en" in self.description_i18n and self.description_i18n["en"]:
            return self.description_i18n["en"]
        return self.description

    def get_manifest(self, lang: Optional[str] = None) -> Dict[str, Any]:
        """Возвращает схему манифеста и метаданные плагина.

        Args:
            lang (Optional[str]): Опциональный код языка для локализации метаданных.

        Returns:
            Dict[str, Any]: Словарь с метаданными, статусом, действиями, инструментами и полями настроек.
        """
        resolved_title = self.get_title(lang) if lang else self.title
        resolved_desc = self.get_description(lang) if lang else self.description
        return {
            "name": self.name,
            "title": resolved_title,
            "title_i18n": dict(self.title_i18n) if self.title_i18n else {"en": self.title},
            "version": self.version,
            "description": resolved_desc,
            "description_i18n": dict(self.description_i18n) if self.description_i18n else {"en": self.description},
            "icon": self.icon,
            "category": self.category,
            "enabled": self.enabled,
            "is_system": getattr(self, "is_system", True),
            "scope": getattr(self, "scope", "system" if getattr(self, "is_system", True) else "user"),
            "is_running": self.is_running,
            "actions": self.get_actions() if not inspect.iscoroutinefunction(self.get_actions) else [],
            "tools": self.get_tools() if not inspect.iscoroutinefunction(self.get_tools) else [],
            "fields": self.get_config_fields() if not inspect.iscoroutinefunction(self.get_config_fields) else [],
            "config": self.config,
        }

    def get_tools(self) -> List[Dict[str, Any]]:
        """Возвращает список деклараций инструментов для вызова функций LLM."""
        return []

    def get_actions(self) -> List[Dict[str, Any]]:
        """Возвращает список доступных административных действий для WebGUI."""
        return []

    def get_config_fields(self) -> List[Dict[str, Any]]:
        """Возвращает спецификации полей конфигурации для WebGUI."""
        return []

    def get_router(self) -> Optional[Any]:
        """Возвращает опциональный экземпляр FastAPI APIRouter плагина."""
        return None

    def update_config(self, new_config: Dict[str, Any]) -> None:
        """Обновляет словарь конфигурации времени выполнения."""
        self.config.update(new_config)
        logger.info(f"Конфигурация плагина '{self.name}' обновлена.")

    async def start(self) -> None:
        """Запускает фоновые обработчики и сервисы плагина."""
        self.is_running = True
        logger.info(f"Плагин '{self.name}' запущен.")

    async def stop(self) -> None:
        """Останавливает фоновые обработчики и освобождает ресурсы."""
        self.is_running = False
        logger.info(f"Плагин '{self.name}' остановлен.")

    async def health_check(self) -> Dict[str, Any]:
        """Выполняет проверку состояния здоровья плагина со строгой меткой времени UTC ISO 8601."""
        return {
            "name": self.name,
            "enabled": self.enabled,
            "is_running": self.is_running,
            "status": "healthy" if self.enabled else "disabled",
            "last_check": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    async def execute_action(self, action_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Выполняет объявленное административное действие по его идентификатору."""
        return {
            "success": False,
            "error": f"Action '{action_id}' is not implemented on plugin '{self.name}'.",
        }

    @abc.abstractmethod
    async def handle(self, message: str, **kwargs: Any) -> AsyncGenerator[Dict[str, Any], None]:
        """Обрабатывает входящий запрос или поток сообщений."""
        yield {"status": "complete", "text": ""}
