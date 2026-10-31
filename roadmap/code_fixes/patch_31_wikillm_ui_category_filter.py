# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Roadmap - WikiLLM Articles & Category Filter
# =============================================================================
# Description:
#   Фильтрация статей базы знаний WikiLLM по категориям, тегам и поисковому запросу.
#
# File: patch_31_wikillm_ui_category_filter.py
# Project: ai-windows-admin
# Package: roadmap.code_fixes
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 14:31:00
# =============================================================================

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/wikillm", tags=["WikiLLM Articles"])


class WikiArticle(BaseModel):
    """Модель статьи базы знаний WikiLLM."""
    id: str = Field(..., description="Уникальный идентификатор статьи")
    process_name: str = Field(..., description="Имя процесса")
    title: str = Field(..., description="Заголовок инструкции / статьи")
    category: str = Field(..., description="Категория процесса")
    tags: List[str] = Field(default_factory=list, description="Теги статьи")
    content_pattern: str = Field(..., description="Паттерн решения / рекомендации")


class WikiArticlesResponse(BaseModel):
    """Схема ответа со списком статей WikiLLM."""
    status: str = Field(default="success", description="Статус выполнения запроса")
    total: int = Field(..., description="Общее количество отфильтрованных статей")
    articles: List[WikiArticle] = Field(default_factory=list, description="Список статей")


DEFAULT_ARTICLES: List[Dict[str, Any]] = [
    {
        "id": "art_edge_mem",
        "process_name": "msedge.exe",
        "title": "Microsoft Edge - Диагностика утечек памяти",
        "category": "browser",
        "tags": ["memory_leak", "gpu_acceleration"],
        "content_pattern": "Высокое потребление RAM вкладками Edge. Рекомендуется включить спящий режим вкладок.",
    },
    {
        "id": "art_chrome_gpu",
        "process_name": "chrome.exe",
        "title": "Google Chrome - Аппаратное ускорение GPU",
        "category": "browser",
        "tags": ["gpu_acceleration"],
        "content_pattern": "Сбои рендеринга видео. Перезапустить процесс с флагом отключения GPU acceleration.",
    },
    {
        "id": "art_spoolsv_cpu",
        "process_name": "spoolsv.exe",
        "title": "Диспетчер очереди печати - Высокая нагрузка CPU",
        "category": "system_service",
        "tags": ["high_cpu"],
        "content_pattern": "Зависание очереди печати spoolsv.exe. Очистить директорию PRINTERS и перезапустить службу.",
    },
    {
        "id": "art_git_untrusted",
        "process_name": "git.exe",
        "title": "Git - Недоверенный каталог репозитория",
        "category": "dev_tool",
        "tags": ["untrusted_path"],
        "content_pattern": "Ошибка fatal: detected dubious ownership in repository. Добавить директорию в safe.directory.",
    },
    {
        "id": "art_python_leak",
        "process_name": "python.exe",
        "title": "Python - Профайлинг утечек памяти фоновых агентов",
        "category": "dev_tool",
        "tags": ["memory_leak", "high_cpu"],
        "content_pattern": "Неконтролируемый рост кучи Python. Использовать tracemalloc и сборщик мусора gc.collect().",
    },
]


def filter_articles(
    articles: List[Dict[str, Any]],
    category: Optional[str] = None,
    tag: Optional[str] = None,
    search_query: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Фильтрует список статей по категории, тегу и поисковому запросу.

    Args:
        articles: Список словарей статей.
        category: Категория процесса.
        tag: Фильтрующий тег.
        search_query: Поисковая подстрока.

    Returns:
        Отфильтрованный список статей.
    """
    result = list(articles)
    if category and str(category).lower() != "all":
        cat_lower = str(category).lower()
        result = [a for a in result if a.get("category", "").lower() == cat_lower]

    if tag:
        tag_lower = str(tag).lower()
        result = [a for a in result if any(t.lower() == tag_lower for t in a.get("tags", []))]

    if search_query:
        sq = str(search_query).lower()
        result = [
            a for a in result
            if sq in a.get("process_name", "").lower()
            or sq in a.get("title", "").lower()
            or sq in a.get("content_pattern", "").lower()
        ]

    return result


@router.get("/articles", response_model=WikiArticlesResponse)
async def get_articles_endpoint(
    category: Optional[str] = Query(None, description="Фильтр по категории процесса"),
    tag: Optional[str] = Query(None, description="Фильтр по тегу"),
    search_query: Optional[str] = Query(None, description="Поисковый запрос"),
) -> WikiArticlesResponse:
    """Возвращает отфильтрованные статьи базы знаний WikiLLM."""
    filtered = filter_articles(
        DEFAULT_ARTICLES,
        category=category,
        tag=tag,
        search_query=search_query,
    )
    return WikiArticlesResponse(
        status="success",
        total=len(filtered),
        articles=[WikiArticle(**a) for a in filtered],
    )

