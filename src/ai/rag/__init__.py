# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin AI - RAG Package Init
# =============================================================================
# Description:
#   Инициализатор пакета унифицированного RAG (Text, Pixel, Log, UnifiedHub).
#
# Usage Examples:
#   Python API:
#     from src.ai.rag import UnifiedKnowledgeHub, TextRAG, PixelRAG, LogRAG
#
# File: __init__.py
# Project: ai-windows-admin
# Package: src.ai.rag
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 18:30:00
# =============================================================================

from __future__ import annotations
"""Инициализатор пакета унифицированного RAG (Text, Pixel, Log, Codebase, UnifiedHub)."""

from .codebase_rag import (
    AffectedCodeLocation,
    CodebaseRAG,
    CodeDiagnosticConclusion,
    CodeRemediationStep,
)
from .text_rag import TextRAG
from .pixel_rag import PixelRAG
from .log_rag import LogRAG
from .unified_hub import UnifiedKnowledgeHub
from .router import init_router, router

__all__ = [
    "AffectedCodeLocation",
    "CodebaseRAG",
    "CodeDiagnosticConclusion",
    "CodeRemediationStep",
    "TextRAG",
    "PixelRAG",
    "LogRAG",
    "UnifiedKnowledgeHub",
    "init_router",
    "router",
]

