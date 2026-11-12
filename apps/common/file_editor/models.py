# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Common File Editor - Data Models
# =============================================================================
# Description:
#   Модели данных и схемы валидации для универсального модуля редактора файлов
#   на базе Rust + WebAssembly (apps/common/file_editor).
#   Описывает дескрипторы типов файлов VS Code, структуры чтения/записи
#   текстовых, табличных, бинарных (Hex), медийных и ноутбук-файлов (.ipynb).
#
# File: models.py
# Project: ai-windows-admin
# Package: apps.common.file_editor
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 14:31:05
# =============================================================================

from __future__ import annotations
"""Pydantic-схемы и перечисления универсального редактора файлов Rust + WebAssembly."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class EditorMode(str, Enum):
    """Режимы отображения и редактирования файлов в стиле VS Code."""

    CODE = "code"                # Исходный код и конфигурационные файлы (Monaco / Wasm Highlighter)
    MARKDOWN = "markdown"        # Markdown с живым Split-View предпросмотром
    TABULAR = "tabular"          # Табличный редактор CSV / TSV (Grid + Raw)
    NOTEBOOK = "notebook"        # Редактор ячеек Jupyter Notebook (.ipynb)
    VECTOR_SVG = "vector_svg"    # Двусторонний редактор векторной графики SVG (XML + Холст)
    IMAGE = "image"              # Графический инспектор и Canvas-редактор изображений
    PDF = "pdf"                  # Wasm-просмотрщик и экстрактор PDF в Markdown/Текст
    MEDIA = "media"              # Аудио/видео плеер-инспектор + Hex-режим
    HEX = "hex"                  # Побайтовый бинарный редактор (VS Code Hex Editor + Data Inspector)


class FileTypeDescriptor(BaseModel):
    """Дескриптор типа файла и параметров его редактирования в стиле VS Code."""

    extension: str = Field(..., description="Расширение файла без точки в нижнем регистре")
    language_id: str = Field(..., description="Идентификатор языка синтаксиса VS Code")
    display_name: str = Field(..., description="Читаемое название формата")
    default_mode: EditorMode = Field(..., description="Основной режим редактора по умолчанию")
    supported_modes: List[EditorMode] = Field(
        default_factory=list,
        description="Все доступные режимы редактирования для данного типа файла",
    )
    mime_type: str = Field(default="text/plain", description="Стандартный MIME-тип")
    icon_class: str = Field(default="bi-file-earmark-code", description="Иконка Bootstrap Icons")
    is_binary_default: bool = Field(
        default=False,
        description="Признак бинарного формата по умолчанию",
    )
    supports_formatting: bool = Field(
        default=False,
        description="Поддерживается ли автоформатирование буфера",
    )


class HexByteModification(BaseModel):
    """Одиночное изменение байта по смещению в бинарном файле."""

    offset: int = Field(..., ge=0, description="Смещение байта от начала файла (0-based)")
    value: int = Field(..., ge=0, le=255, description="Новое значение байта (0..255)")


class FileSaveRequest(BaseModel):
    """Запрос на сохранение отредактированного файла (текстового или бинарного)."""

    workspace_id: Optional[str] = Field(default=None, description="Идентификатор рабочего пространства")
    rel_path: str = Field(..., description="Относительный путь к файлу в рабочем пространстве")
    content: Optional[str] = Field(default=None, description="Текстовое содержимое (для текстовых режимов)")
    base64_content: Optional[str] = Field(
        default=None,
        description="Полное бинарное содержимое в Base64 (для изображений и бинарных файлов)",
    )
    hex_patches: Optional[List[HexByteModification]] = Field(
        default=None,
        description="Список точечных байтовых правок для режима Hex-редактора",
    )
    encoding: str = Field(default="utf-8", description="Кодировка текстового файла")
    line_ending: str = Field(default="LF", description="Тип перевода строк: LF или CRLF")
    commit_to_git: bool = Field(default=True, description="Создать ли коммит в Git после сохранения")
    commit_message: Optional[str] = Field(default=None, description="Сообщение коммита Git")


class FileFormatRequest(BaseModel):
    """Запрос на форматирование и синтаксическую валидацию содержимого буфера."""

    content: str = Field(..., description="Исходный текст буфера редактора")
    extension: str = Field(default="txt", description="Расширение или тип файла")
    language_id: Optional[str] = Field(default=None, description="Язык синтаксиса VS Code")
    indent_size: int = Field(default=2, ge=1, le=8, description="Размер отступа в пробелах")


class FileDiffRequest(BaseModel):
    """Запрос на вычисление построчного сравнения (Diff) буфера с файлом на диске."""

    workspace_id: Optional[str] = Field(default=None, description="Идентификатор рабочего пространства")
    rel_path: str = Field(..., description="Относительный путь к файлу")
    modified_content: str = Field(..., description="Текущее несохранённое содержимое в редакторе")
