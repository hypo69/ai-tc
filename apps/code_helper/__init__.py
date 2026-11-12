# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Code Helper Package
# =============================================================================
# Description:
#   Автономный пакет Code Helper: RAG исходного кода, AST-индексация,
#   семантический поиск и диагностика с базой данных на Hostinger.
#
# File: __init__.py
# Project: ai-windows-admin
# Package: apps.code_helper
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 17:10:00
# =============================================================================

from __future__ import annotations

"""Пакет автономной системы Code Helper."""

from .models import (
    CodeChunk,
    CodeLocation,
    CodeRemediationStep,
    CodeSymbol,
    DiagnosticConclusion,
    IndexStats,
)
from .parser import CodeParser
from .rag import CodeHelperRAG
from .router import get_rag, init_router, router
from .server import create_app, run_standalone_server
from .storage import CodeHelperStorage

__all__ = [
    "CodeChunk",
    "CodeHelperRAG",
    "CodeHelperStorage",
    "CodeLocation",
    "CodeParser",
    "CodeRemediationStep",
    "CodeSymbol",
    "DiagnosticConclusion",
    "IndexStats",
    "create_app",
    "get_rag",
    "init_router",
    "router",
    "run_standalone_server",
]
