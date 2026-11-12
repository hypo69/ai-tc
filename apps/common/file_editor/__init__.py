# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Common File Editor - Package Init
# =============================================================================
# Description:
#   Пакет универсального редактора файлов на базе Rust + WebAssembly
#   с поддержкой всех типов файлов Visual Studio Code.
#
# File: __init__.py
# Project: ai-windows-admin
# Package: apps.common.file_editor
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 17:02:00
# =============================================================================

from __future__ import annotations
"""Экспорт компонентов общего модуля редактора файлов Rust + WebAssembly."""

from apps.common.file_editor.catalog import SupportedFileCatalog
from apps.common.file_editor.models import (
    EditorMode,
    FileDiffRequest,
    FileFormatRequest,
    FileSaveRequest,
    FileTypeDescriptor,
    HexByteModification,
)
from apps.common.file_editor.router import router as file_editor_router
from apps.common.file_editor.service import FileEditorService
from apps.common.file_editor.wasm_compiler import WASM_BINARY_PATH, ensure_wasm_binary

__all__ = [
    "EditorMode",
    "FileDiffRequest",
    "FileEditorService",
    "FileFormatRequest",
    "FileSaveRequest",
    "FileTypeDescriptor",
    "HexByteModification",
    "SupportedFileCatalog",
    "WASM_BINARY_PATH",
    "ensure_wasm_binary",
    "file_editor_router",
]
