# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin AI Instruments Package
# =============================================================================
# Description:
#   Изолированная подсистема инструментов ИИ-агента (ai_instruments.db).
#   Хранит ТОЛЬКО исполняемые инструменты, скрипты автоматизации и утилиты,
#   отделяя их от базы знаний параметров и сущностей WikiLLM (knowledge.db).
#
# Usage Examples:
#   Python API:
#     from apps.windows.ai_instruments import AIInstrumentsService, AIInstrumentsStorage
#
# File: __init__.py
# Project: ai-windows-admin
# Package: apps.windows.ai_instruments
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-20 12:44:00
# =============================================================================

from __future__ import annotations

"""Пакет изолированной базы инструментов ИИ-агента."""

from .models import AIInstrument, AIInstrumentCreate, AIInstrumentExecuteRequest
from .service import AIInstrumentsService
from .storage import AIInstrumentsStorage

__all__ = [
    "AIInstrument",
    "AIInstrumentCreate",
    "AIInstrumentExecuteRequest",
    "AIInstrumentsStorage",
    "AIInstrumentsService",
]

