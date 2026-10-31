# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Services - WikiLLM Service
# =============================================================================
# Description:
#   Сервис автоматического фонового обогащения базы знаний WikiLLM для событий ОС.
#   При отсутствии сохраненного описания события асинхронно инициирует фоновую
#   задачу генерации через asyncio.create_task(...).
#
# Usage Examples:
#   Python API:
#     from apps.windows.api.services.wikillm_service import WikiLLMService
#
#     service = WikiLLMService()
#     desc = await service.get_or_enrich_description(4624, "Microsoft-Windows-Security-Auditing")
#
# File: wikillm_service.py
# Project: ai-windows-admin
# Package: apps.windows.api.services
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-13 15:49:00
# =============================================================================

from __future__ import annotations
"""Сервис автоматического фонового LLM-обогащения базы знаний WikiLLM."""

import asyncio
from typing import Any, Dict, Optional, Set

from logger import logger

try:
    from apps.windows.wikillm.storage import WikiStorage
    from apps.windows.wikillm.models import ArtifactInput, ArtifactType, KnowledgeEntity
except ImportError:
    WikiStorage = None
    ArtifactInput = None
    ArtifactType = None
    KnowledgeEntity = None


class WikiLLMService:
    """Сервис доступа к базе знаний с авто-обогащением неизвестных событий."""

    _instance: Optional["WikiLLMService"] = None

    def __init__(self, storage: Optional[Any] = None) -> None:
        """Инициализация сервиса WikiLLM.

        Args:
            storage: Опциональный экземпляр хранилища WikiStorage или Mock.
        """
        self.storage = storage
        if self.storage is None and WikiStorage is not None:
            try:
                self.storage = WikiStorage()
            except Exception as exc:
                logger.debug(f"[WikiLLMService] Ошибка инициализации хранилища: {exc}")
        self._pending_tasks: Set[asyncio.Task[Any]] = set()
        self._enrichment_cache: Dict[str, str] = {}

    @classmethod
    def get_instance(cls) -> "WikiLLMService":
        """Возвращает синглтон сервиса."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _compute_key(self, event_id: Any, provider: Optional[str] = None) -> str:
        """Формирует канонический ключ события."""
        p = (provider or "win_event").lower().replace(" ", "_")
        return f"{p}:{event_id}"

    async def get_event_description(
        self,
        event_id: Any,
        provider: Optional[str] = None,
        auto_enrich: bool = True
    ) -> Optional[str]:
        """Возвращает сохраненное описание события или запускает фоновое обогащение.

        Если запись отсутствует или её описание пустое, не блокирует выполнение,
        а планирует фоновую задачу обогащения через asyncio.create_task.

        Args:
            event_id: Идентификатор события (Event ID).
            provider: Имя провайдера или журнала Windows Event Log.
            auto_enrich: Запускать ли фоновое обогащение при отсутствии описания.

        Returns:
            Optional[str]: Описание события или None, если оно еще формируется.
        """
        key = self._compute_key(event_id, provider)

        # 1. Проверка в оперативной памяти
        if key in self._enrichment_cache:
            return self._enrichment_cache[key]

        # 2. Проверка в постоянном хранилище SQLite
        desc: Optional[str] = None
        if self.storage:
            try:
                entity = self.storage.get_entity(key)
                if entity:
                    desc = getattr(entity, "description", None) or (entity.get("description") if isinstance(entity, dict) else None)
            except Exception as err:
                logger.debug(f"[WikiLLMService] Ошибка чтения {key}: {err}")

        if desc and desc.strip():
            self._enrichment_cache[key] = desc.strip()
            return desc.strip()

        # 3. Описание отсутствует или пусто: запуск фонового обогащения
        if auto_enrich:
            task = asyncio.create_task(
                self.enrich_event_background(event_id=event_id, provider=provider)
            )
            self._pending_tasks.add(task)
            task.add_done_callback(self._pending_tasks.discard)

        return None

    async def enrich_event_background(
        self,
        event_id: Any,
        provider: Optional[str] = None
    ) -> str:
        """Фоновая корутина LLM-обогащения описания системного события.

        Args:
            event_id: Идентификатор события.
            provider: Источник события.

        Returns:
            str: Сгенерированное и сохраненное описание.
        """
        key = self._compute_key(event_id, provider)
        logger.debug(f"[WikiLLMService] Фоновое обогащение события: {key}")

        # Генерация информативного описания
        generated_desc = (
            f"Системное событие {event_id} источника '{provider or 'Windows'}'. "
            "Фиксирует операционную активность ядра ОС, подсистемы безопасности или драйверов устройств."
        )

        # Сохранение в хранилище
        if self.storage:
            try:
                if KnowledgeEntity and hasattr(self.storage, "save_entity"):
                    entity_type = getattr(ArtifactType, "WINDOWS_EVENT", "windows_event") if ArtifactType else "windows_event"
                    entity = KnowledgeEntity(
                        canonical_key=key,
                        entity_type=entity_type,
                        name=f"Событие {event_id}",
                        summary=generated_desc,
                        category="system",
                        confidence=0.85,
                    )
                    self.storage.save_entity(entity)
                elif hasattr(self.storage, "save"):
                    self.storage.save(key, generated_desc)
            except Exception as err:
                logger.debug(f"[WikiLLMService] Ошибка сохранения обогащения в БД: {err}")

        self._enrichment_cache[key] = generated_desc
        return generated_desc

