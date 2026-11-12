# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Code Helper - Data Models & Schemas
# =============================================================================
# Description:
#   Модели данных Pydantic для автономного RAG кодовой базы, AST-индексации,
#   поиска по кодовой базе и формирования диагностических заключений.
#
# File: models.py
# Project: ai-windows-admin
# Package: apps.code_helper
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 17:10:00
# =============================================================================

from __future__ import annotations

"""Модели данных Pydantic для автономной системы Code Helper."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CodeLocation(BaseModel):
    """Описание затронутого участка исходного кода или документации."""

    file_path: str = Field(description="Относительный путь к файлу в проекте")
    symbol_name: str = Field(default="", description="Имя функции, класса или метода")
    symbol_type: str = Field(default="module", description="Тип узла (class, function, method, doc)")
    start_line: int = Field(default=1, ge=1, description="Начальная строка в файле")
    end_line: int = Field(default=1, ge=1, description="Конечная строка в файле")
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Оценка релевантности участка")
    snippet: str = Field(default="", description="Фрагмент исходного кода или сигнатура")


class CodeRemediationStep(BaseModel):
    """Рекомендуемый шаг по исправлению ошибки или оптимизации кода."""

    title: str = Field(description="Краткий заголовок действия")
    description: str = Field(description="Подробное техническое описание исправления")
    target_file: str = Field(default="", description="Целевой файл для внесения изменений")
    suggested_code: str = Field(default="", description="Пример исправленного кода или команды")


class DiagnosticConclusion(BaseModel):
    """Итоговое структурированное заключение RAG-анализатора по кодовой базе."""

    summary: str = Field(description="Краткое резюме заключения")
    root_cause: str = Field(description="Выявленная первопричина проблемы или архитектурный ответ")
    explanation: str = Field(description="Развернутое техническое объяснение на основе кода")
    severity: str = Field(default="error", description="Уровень критичности (info, warning, error, critical)")
    confidence: float = Field(default=0.85, ge=0.0, le=1.0, description="Уверенность в заключении (0..1)")
    affected_locations: List[CodeLocation] = Field(
        default_factory=list,
        description="Список затронутых файлов, функций и строк кода",
    )
    remediation_steps: List[CodeRemediationStep] = Field(
        default_factory=list,
        description="Пошаговый план исправления или проверки",
    )
    extracted_signals: Dict[str, Any] = Field(
        default_factory=dict,
        description="Извлеченные из логов и ошибки сигналы (исключения, файлы, символы)",
    )
    source_mode: str = Field(
        default="deterministic_ast",
        description="Режим формирования заключения (hybrid_llm или deterministic_ast)",
    )
    execution_time_ms: float = Field(default=0.0, description="Время выполнения анализа в миллисекундах")


class CodeChunk(BaseModel):
    """Смысловой фрагмент кода или документации для базы знаний."""

    chunk_id: str = Field(description="Уникальный идентификатор чанка")
    index_name: str = Field(default="codebase", description="Имя индекса")
    file_path: str = Field(description="Относительный путь к файлу")
    symbol_name: str = Field(default="", description="Имя символа или заголовка")
    symbol_type: str = Field(default="module", description="Тип: module, class, function, method, doc")
    start_line: int = Field(default=1, ge=1, description="Начальная строка")
    end_line: int = Field(default=1, ge=1, description="Конечная строка")
    content: str = Field(description="Полный индексируемый текст чанка")
    signature: str = Field(default="", description="Сигнатура функции/класса")
    docstring: str = Field(default="", description="Документация блока")
    snippet: str = Field(default="", description="Краткий фрагмент кода")
    content_hash: str = Field(default="", description="SHA-256 хеш содержимого")
    updated_at: str = Field(default="", description="Время обновления ISO/строка")


class CodeSymbol(BaseModel):
    """Запись AST-символа (класс, метод, функция) для быстрого перехода."""

    symbol_id: str = Field(description="Уникальный идентификатор символа")
    index_name: str = Field(default="codebase", description="Имя индекса")
    symbol: str = Field(description="Полное имя символа (например Class.method)")
    short_name: str = Field(description="Короткое имя символа")
    symbol_type: str = Field(default="function", description="Тип: function, async_function, class, method")
    file_path: str = Field(description="Относительный путь к файлу")
    signature: str = Field(default="", description="Сигнатура вызова")
    docstring: str = Field(default="", description="Docstring символа")
    start_line: int = Field(default=1, ge=1, description="Начальная строка")
    end_line: int = Field(default=1, ge=1, description="Конечная строка")
    related_symbols: List[str] = Field(default_factory=list, description="Связанные символы или импорты")
    snippet: str = Field(default="", description="Фрагмент кода")
    updated_at: str = Field(default="", description="Время обновления")


class IndexStats(BaseModel):
    """Статистика собранного индекса кодовой базы."""

    name: str = Field(default="codebase", description="Имя индекса")
    project_root: str = Field(default=".", description="Корневой каталог сканирования")
    total_files: int = Field(default=0, ge=0, description="Количество проиндексированных файлов")
    total_chunks: int = Field(default=0, ge=0, description="Количество чанков")
    total_symbols: int = Field(default=0, ge=0, description="Количество AST-символов")
    elapsed_seconds: float = Field(default=0.0, description="Время сборки в секундах")
    updated_at: str = Field(default="", description="Дата и время обновления")
    storage_engine: str = Field(default="mariadb", description="Движок хранилища (mariadb или sqlite)")


# Схемы API запросов
class BuildIndexRequest(BaseModel):
    """Запрос на сборку индекса кодовой базы."""

    project_root: str = Field(default=".", description="Корневой каталог проекта")
    index_name: str = Field(default="codebase", description="Имя целевого индекса")
    include_dirs: List[str] = Field(default_factory=list, description="Список поддиректорий для индексации")
    include_markdown: bool = Field(default=True, description="Индексировать ли Markdown файлы (.md)")


class SearchRequest(BaseModel):
    """Запрос на поиск по коду и документации."""

    query: str = Field(..., description="Поисковый запрос, сигнатура или ключевые слова")
    index_name: str = Field(default="codebase", description="Имя индекса")
    top_k: int = Field(default=5, ge=1, le=50, description="Лимит возвращаемых результатов")


class SymbolSearchRequest(BaseModel):
    """Запрос на поиск символов AST."""

    symbol: str = Field(..., description="Имя или префикс символа")
    index_name: str = Field(default="codebase", description="Имя индекса")
    limit: int = Field(default=15, ge=1, le=100, description="Лимит результатов")


class DiagnoseRequest(BaseModel):
    """Запрос на диагностику вопроса, логов или ошибки."""

    question: str = Field(default="", description="Вопрос по архитектуре или коду")
    logs: List[str] = Field(default_factory=list, description="Строки логов")
    error_message: str = Field(default="", description="Текст ошибки или Traceback")
    index_name: str = Field(default="codebase", description="Имя индекса")
    top_k: int = Field(default=6, ge=1, le=25, description="Количество фрагментов кода для контекста")
    use_llm: bool = Field(default=True, description="Использовать ли LLM при доступности")
