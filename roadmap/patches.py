# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Roadmap - Patches & WikiLLM Settings Service
# =============================================================================
# Description:
#   Сервис параметров конфигурации WikiLLM по умолчанию.
#
# File: patches.py
# Project: ai-windows-admin
# Package: roadmap
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 14:30:00
# =============================================================================

from __future__ import annotations

from typing import Any, Dict


class WikiLLMSettingsService:
    """Сервис системных параметров WikiLLM по умолчанию."""

    def get_settings(self) -> Dict[str, Any]:
        """Возвращает параметры по умолчанию для генерации и базы данных WikiLLM.

        Returns:
            Словарь параметров конфигурации.
        """
        return {
            "model_name": "gemini-3.1-flash-lite",
            "confidence_threshold": 0.85,
            "db_path": "data/windows_wikillm/knowledge.db",
            "editor_enabled": True,
            "auto_enrichment": True,
            "temperature": 0.2,
            "max_context_tokens": 4096,
            "auto_indexing": True,
        }

