# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Windows API Registry - Service Facade
# =============================================================================
# Description:
#   Сервисный синглтон фасад для доступа к реестру системных API Windows,
#   управлению пользовательскими настройками и вызову диспетчера.
#
# Usage Examples:
#   from apps.windows.api_registry.service import get_api_registry_service
#   service = get_api_registry_service()
#
# File: service.py
# Project: ai-windows-admin
# Package: apps.windows.api_registry
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 02:56:00
# =============================================================================

from __future__ import annotations
"""Сервисный фасад реестра Windows API и интеллектуального диспетчера."""

from typing import Any, Dict, List, Optional
from apps.windows.api_registry.catalog import (
    get_all_api_entries,
    get_api_by_id,
    get_apis_by_subsystem,
    get_subsystems_summary,
)
from apps.windows.api_registry.dispatcher import WindowsApiDispatcher
from apps.windows.api_registry.models import (
    ApiFamily,
    ApiRecommendationQuery,
    ApiRecommendationResult,
    PlatformSubsystem,
    RegistryFilterConfig,
    WindowsApiEntry,
)


class WindowsApiRegistryService:
    """Сервис управления реестром системных API Windows."""

    def __init__(self) -> None:
        """Инициализация сервиса и диспетчера."""
        self._dispatcher = WindowsApiDispatcher()
        self._config = RegistryFilterConfig()

    def get_catalog(
        self,
        subsystem: Optional[PlatformSubsystem] = None,
        family: Optional[ApiFamily] = None,
        zero_dependency_only: bool = False,
        search_query: Optional[str] = None,
    ) -> List[WindowsApiEntry]:
        """Возвращает отфильтрованный список системных API."""
        entries = get_all_api_entries()

        if subsystem:
            entries = [e for e in entries if e.subsystem == subsystem]

        if family:
            entries = [e for e in entries if e.family == family]

        if zero_dependency_only:
            entries = [e for e in entries if e.zero_dependency]

        if search_query:
            q = search_query.lower()
            entries = [
                e for e in entries
                if q in e.name.lower()
                or q in e.description.lower()
                or q in e.binary_or_namespace.lower()
                or any(q in fn.lower() for fn in e.functions)
            ]

        return entries

    def get_entry(self, api_id: str) -> Optional[WindowsApiEntry]:
        """Возвращает подробную карточку API по идентификатору."""
        return get_api_by_id(api_id)

    def get_subsystems(self) -> Dict[str, Dict[str, Any]]:
        """Возвращает сводку по 6 платформенным подсистемам."""
        return get_subsystems_summary()

    def get_bindings_status(self) -> Dict[str, Dict[str, Any]]:
        """Возвращает статус доступности Python-библиотек."""
        return self._dispatcher.check_bindings_availability()

    def recommend(self, query: ApiRecommendationQuery) -> ApiRecommendationResult:
        """Интеллектуальный подбор интерфейса под текстовую задачу."""
        return self._dispatcher.recommend(query)

    def execute_probe(self, api_id: str) -> Dict[str, Any]:
        """Запуск безопасного нативного диагностического зонда."""
        return self._dispatcher.execute_api_probe(api_id)

    def get_settings(self) -> RegistryFilterConfig:
        """Возвращает текущие настройки реестра."""
        return self._config

    def update_settings(self, new_config: RegistryFilterConfig) -> RegistryFilterConfig:
        """Обновляет пользовательские настройки диспетчера."""
        self._config = new_config
        return self._config


_service_instance: Optional[WindowsApiRegistryService] = None


def get_api_registry_service() -> WindowsApiRegistryService:
    """Возвращает глобальный синглтон WindowsApiRegistryService."""
    global _service_instance
    if _service_instance is None:
        _service_instance = WindowsApiRegistryService()
    return _service_instance
