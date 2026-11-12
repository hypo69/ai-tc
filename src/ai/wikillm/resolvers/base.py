# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Wikillm Resolvers - Base
# =============================================================================
# Description:
#   Базовый абстрактный интерфейс для уровней поиска и разрешения артефактов.
#
# Usage Examples:
#   Python API:
#     from src.ai.wikillm.resolvers.base import BaseResolver
#
#     service = BaseResolver()
#
# File: base.py
# Project: ai-windows-admin
# Package: src.ai.wikillm.resolvers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 17:35:00
# =============================================================================

from __future__ import annotations
"""Базовый абстрактный интерфейс для уровней поиска и разрешения артефактов."""

from abc import ABC, abstractmethod
from typing import Optional
from ..models import ArtifactInput, KnowledgeEntity, LookupLevel


class BaseResolver(ABC):
    """Абстрактный резолвер артефактов."""

    def __init__(self, level: LookupLevel, name: str) -> None:
        """Инициализирует базовый резолвер.

        Args:
            level: Уровень поиска (LookupLevel).
            name: Человекочитаемое имя резолвера.
        """
        self.level = level
        self.name = name

    @abstractmethod
    async def resolve(self, artifact: ArtifactInput) -> Optional[KnowledgeEntity]:
        """Пытается разрешить артефакт на текущем уровне.

        Args:
            artifact: Входной артефакт.

        Returns:
            Сущность KnowledgeEntity или None, если знание не найдено.
        """
        raise NotImplementedError

