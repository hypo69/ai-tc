# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Wikillm Resolvers - Semantic
# =============================================================================
# Description:
#   Резолвер семантического и полнотекстового поиска (FTS5). Выполняет поиск по смыслу,
#
# Usage Examples:
#   Python API:
#     from src.ai.wikillm.resolvers.semantic import SemanticResolver
#
#     service = SemanticResolver()
#
# File: semantic.py
# Project: ai-windows-admin
# Package: src.ai.wikillm.resolvers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 17:35:00
# =============================================================================

from __future__ import annotations
"""Резолвер семантического и полнотекстового поиска (FTS5). Выполняет поиск по смыслу,"""

from typing import Optional
from ..models import ArtifactInput, KnowledgeEntity, LookupLevel
from ..storage import WikiStorage
from .base import BaseResolver


class SemanticResolver(BaseResolver):
    """Резолвер семантического сопоставления и полнотекстового поиска FTS5."""

    def __init__(self, storage: WikiStorage) -> None:
        """Инициализирует SemanticResolver.

        Args:
            storage: Экземпляр хранилища WikiStorage.
        """
        super().__init__(level=LookupLevel.SEMANTIC, name="SemanticFTSResolver")
        self.storage = storage

    async def resolve(self, artifact: ArtifactInput) -> Optional[KnowledgeEntity]:
        """Выполняет полнотекстовый поиск по сообщению или описанию симптома.

        Args:
            artifact: Входной артефакт.

        Returns:
            KnowledgeEntity с наивысшим рангом релевантности или None.
        """
        search_query = artifact.message or artifact.raw_query or ""
        if not search_query or len(search_query.strip()) < 3:
            return None

        candidates = self.storage.search_fts(search_query, limit=1)
        if candidates:
            return candidates[0]

        return None

