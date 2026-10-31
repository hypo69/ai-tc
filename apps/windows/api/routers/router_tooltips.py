# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows API - Tooltips Editor Router
# =============================================================================
# Description:
#   FastAPI роутер для чтения, создания, редактирования и синхронизации
#   интеллектуальных всплывающих подсказок (AI Smart Tooltips & i18n hints).
#
# Usage Examples:
#   Python API:
#     from apps.windows.api.routers.router_tooltips import init_router
#     router = init_router()
#
# File: router_tooltips.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 18:05:00
# =============================================================================

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

try:
    from logger import logger
except ImportError:
    logger = logging.getLogger("tooltips_router")

router = APIRouter(
    prefix="/api/v1/tooltips",
    tags=["Tooltips & Knowledge Base Editor"]
)

# Пути к файлам локалей проекта
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_LOCALES_DIRS = [
    _PROJECT_ROOT / "apps" / "windows" / "api" / "webgui" / "locales",
    _PROJECT_ROOT / "apps" / "common" / "webgui" / "locales",
]


class TooltipItemSchema(BaseModel):
    """Схема сущности всплывающей подсказки (AI Smart Tooltip)."""

    key: str = Field(..., description="Уникальный строковый идентификатор подсказки (например, internals-logs)")
    title: str = Field(..., description="Короткий заголовок подсказки")
    fullTitle: Optional[str] = Field(default="", description="Развернутый заголовок подсказки")
    summary: str = Field(..., description="Подробный пояснительный текст подсказки")
    category: str = Field(default="Справка", description="Категория подсказки (Логирование, Безопасность и др.)")
    icon: str = Field(default="💡", description="Эмодзи или иконка карточки подсказки")
    lang: str = Field(default="ru", description="Языковой код (ru, en, uk, he)")
    source: str = Field(default="custom", description="Источник подсказки: locale, knowledge_base или custom")


class TooltipsListResponse(BaseModel):
    """Схема ответа со списком подсказок."""

    status: str = Field(default="success", description="Статус ответа")
    total: int = Field(..., description="Общее число подсказок")
    lang: str = Field(default="ru", description="Текущий язык выборки")
    items: List[TooltipItemSchema] = Field(default_factory=list, description="Список подсказок")


def _read_locale_file(lang: str) -> Dict[str, Any]:
    """Чтение файла локализации для указанного языка из основного каталога веб-интерфейса.

    Args:
        lang: Код языка (ru, en, uk, he).

    Returns:
        Словарь содержимого JSON локали.
    """
    for loc_dir in _LOCALES_DIRS:
        loc_path = loc_dir / f"{lang}.json"
        if loc_path.is_file():
            try:
                with open(loc_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"[TooltipsRouter] Ошибка чтения {loc_path}: {e}")
    return {}


def _save_tooltip_to_locales(item: TooltipItemSchema) -> None:
    """Синхронное сохранение подсказки во все каталоги локализаций проекта.

    Args:
        item: Объект сохраняемой подсказки.
    """
    target_data = {
        "title": item.title,
        "fullTitle": item.fullTitle or item.title,
        "summary": item.summary,
        "category": item.category,
        "icon": item.icon,
    }

    normalized_key = item.key.strip()

    for loc_dir in _LOCALES_DIRS:
        loc_path = loc_dir / f"{item.lang}.json"
        if not loc_path.is_file():
            continue
        try:
            with open(loc_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if "tooltips" not in data or not isinstance(data["tooltips"], dict):
                data["tooltips"] = {}

            data["tooltips"][normalized_key] = target_data

            # Если тултип соответствует известной субвкладке internals, синхронизируем internals.subtab*Title
            if normalized_key in ("internals-logs", "subtab-internals-logs", "logs"):
                if "internals" in data and isinstance(data["internals"], dict):
                    data["internals"]["subtabLogsTitle"] = item.summary

            with open(loc_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"[TooltipsRouter] Не удалось сохранить {loc_path}: {e}")


def _delete_tooltip_from_locales(key: str, lang: str) -> bool:
    """Удаление подсказки из файлов локализации проекта.

    Args:
        key: Ключ удаляемой подсказки.
        lang: Код языка.

    Returns:
        True если элемент найден и удален.
    """
    found = False
    norm_key = key.strip()

    for loc_dir in _LOCALES_DIRS:
        loc_path = loc_dir / f"{lang}.json"
        if not loc_path.is_file():
            continue
        try:
            with open(loc_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if "tooltips" in data and norm_key in data["tooltips"]:
                del data["tooltips"][norm_key]
                found = True
                with open(loc_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[TooltipsRouter] Не удалось удалить подсказку из {loc_path}: {e}")

    return found


@router.get("", response_model=TooltipsListResponse)
async def list_tooltips(
    lang: str = Query("ru", description="Язык локализации (ru, en, uk, he)"),
    search: Optional[str] = Query(None, description="Поисковый запрос по ключу или описанию"),
    category: Optional[str] = Query(None, description="Фильтр по категории"),
) -> TooltipsListResponse:
    """Получение полного списка доступных подсказок с возможностью поиска и фильтрации."""
    data = _read_locale_file(lang)
    tooltips_dict: Dict[str, Any] = data.get("tooltips", {})

    items: List[TooltipItemSchema] = []
    search_lower = (search or "").lower().strip()
    cat_lower = (category or "").lower().strip()

    for k, v in tooltips_dict.items():
        if not isinstance(v, dict):
            continue

        item_title = v.get("title") or k
        item_full_title = v.get("fullTitle") or item_title
        item_summary = v.get("summary") or ""
        item_category = v.get("category") or "Справка"
        item_icon = v.get("icon") or "💡"

        # Фильтрация по поисковому запросу
        if search_lower:
            match_search = (
                search_lower in k.lower()
                or search_lower in item_title.lower()
                or search_lower in item_full_title.lower()
                or search_lower in item_summary.lower()
            )
            if not match_search:
                continue

        # Фильтрация по категории
        if cat_lower and cat_lower != item_category.lower():
            continue

        items.append(
            TooltipItemSchema(
                key=k,
                title=item_title,
                fullTitle=item_full_title,
                summary=item_summary,
                category=item_category,
                icon=item_icon,
                lang=lang,
                source="locale",
            )
        )

    # Сортировка по ключу
    items.sort(key=lambda x: x.key)

    return TooltipsListResponse(
        status="success",
        total=len(items),
        lang=lang,
        items=items,
    )


@router.get("/{key}", response_model=TooltipItemSchema)
async def get_tooltip(
    key: str,
    lang: str = Query("ru", description="Язык локализации"),
) -> TooltipItemSchema:
    """Получение детальной информации о подсказке по ее уникальному ключу."""
    data = _read_locale_file(lang)
    tooltips_dict = data.get("tooltips", {})
    norm_key = key.strip()

    if norm_key not in tooltips_dict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Подсказка с ключом '{key}' не найдена в словаре языка '{lang}'",
        )

    v = tooltips_dict[norm_key]
    return TooltipItemSchema(
        key=norm_key,
        title=v.get("title", norm_key),
        fullTitle=v.get("fullTitle", v.get("title", norm_key)),
        summary=v.get("summary", ""),
        category=v.get("category", "Справка"),
        icon=v.get("icon", "💡"),
        lang=lang,
        source="locale",
    )


@router.post("", response_model=TooltipItemSchema)
async def save_tooltip(item: TooltipItemSchema) -> TooltipItemSchema:
    """Создание или обновление подсказки в базе данных и файлах локализации."""
    if not item.key.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Идентификатор ключа (key) не может быть пустым",
        )
    _save_tooltip_to_locales(item)
    return item


@router.delete("/{key}")
async def delete_tooltip(
    key: str,
    lang: str = Query("ru", description="Язык локализации"),
) -> Dict[str, Any]:
    """Удаление подсказки из файлов локализации."""
    deleted = _delete_tooltip_from_locales(key, lang)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Подсказка с ключом '{key}' не найдена для удаления",
        )
    return {"status": "success", "message": f"Подсказка '{key}' успешно удалена"}


def init_router() -> APIRouter:
    """Инициализация и возврат роутера подсказок."""
    return router


__all__ = ["router", "init_router"]
