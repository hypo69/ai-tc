# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - Router Help Pages
# =============================================================================
# Description:
#   API-роутер для управления страницами и атомарными блоками контекстной справки:
#   - Обнаружение и каталогизация страниц справки по вкладкам (/api/v1/help-pages/catalog)
#   - Чтение и сохранение содержимого файлов справки (/api/v1/help-pages/read, /save)
#   - Создание новых страниц или атомарных блоков справки (/api/v1/help-pages/create)
#   - Валидация на отсутствие жестко закодированных цветов и соответствие стандартам
#
# Usage Examples:
#   GET /api/v1/help-pages/catalog
#   GET /api/v1/help-pages/file?path=tab_log_settings/help/blocks/block_kpi_cards.html
#   POST /api/v1/help-pages/file (JSON: {path, content})
#
# File: router_help_pages.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 18:03:00
# =============================================================================

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from logger import logger

router = APIRouter(prefix="/api/v1/help-pages", tags=["Help Pages & Blocks Editor"])

WEBGUI_DIR = Path(__file__).resolve().parents[1] / "webgui"


class HelpFileSaveRequest(BaseModel):
    """Модель запроса сохранения содержимого файла справки."""
    path: str = Field(..., description="Относительный путь файла в webgui, например 'tab_log_settings/help/blocks/block_kpi_cards.html'")
    content: str = Field(..., description="Новое HTML/MD содержимое файла")


class HelpFileCreateRequest(BaseModel):
    """Модель запроса создания новой страницы или атомарного блока справки."""
    module: str = Field(..., description="Идентификатор модуля/вкладки, например 'tab_log_settings'")
    kind: str = Field(..., description="Тип файла: 'composite' (index.html), 'block' или 'doc' (README.md)")
    name: str = Field(..., description="Имя блока (без расширения или имя файла)")
    title: Optional[str] = Field(None, description="Заголовок справки")
    description: Optional[str] = Field(None, description="Описание блока")


def _sanitize_path(relative_path: str) -> Path:
    """Проверяет безопасность пути и возвращает абсолютный путь внутри WEBGUI_DIR.

    Исключает атаки обхода каталога (path traversal).
    """
    clean_rel = os.path.normpath(relative_path.strip().lstrip("/\\"))
    if ".." in clean_rel:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Недопустимый путь: обнаружен выход за пределы директории (..)"
        )
    target_path = (WEBGUI_DIR / clean_rel).resolve()
    if not str(target_path).startswith(str(WEBGUI_DIR.resolve())):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Недопустимый путь: файл вне пределов директории webgui"
        )
    return target_path


@router.get("/catalog")
def get_help_catalog() -> Dict[str, Any]:
    """Возвращает каталог всех модулей, содержащих контекстную справку и их блоков."""
    modules = []

    # Сканируем директории tab_* и общую help
    candidate_dirs = [d for d in WEBGUI_DIR.iterdir() if d.is_dir() and (d.name.startswith("tab_") or d.name == "help")]

    for mod_dir in sorted(candidate_dirs, key=lambda x: x.name):
        help_dir = mod_dir / "help" if mod_dir.name != "help" else mod_dir
        if not help_dir.exists() or not help_dir.is_dir():
            # Также проверяем, есть ли уже блоки или композит
            continue

        composite_file = help_dir / "index.html"
        readme_file = help_dir / "README.md"
        blocks_dir = help_dir / "blocks"

        blocks = []
        if blocks_dir.exists() and blocks_dir.is_dir():
            for block_file in sorted(blocks_dir.glob("*.html")):
                content = block_file.read_text(encoding="utf-8", errors="ignore")
                # Извлекаем data-help-block и название если есть
                block_id_match = re.search(r'data-help-block=["\']([^"\']+)["\']', content)
                title_match = re.search(r'<h[1-6][^>]*>(.*?)</h[1-6]>', content, re.DOTALL)
                clean_title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip() if title_match else block_file.stem

                blocks.append({
                    "name": block_file.name,
                    "stem": block_file.stem,
                    "path": str(block_file.relative_to(WEBGUI_DIR)).replace("\\", "/"),
                    "block_id": block_id_match.group(1) if block_id_match else block_file.stem,
                    "title": clean_title,
                    "size_bytes": block_file.stat().st_size,
                    "updated_at": datetime.fromtimestamp(block_file.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                })

        modules.append({
            "module": mod_dir.name,
            "has_composite": composite_file.is_file(),
            "composite_path": str(composite_file.relative_to(WEBGUI_DIR)).replace("\\", "/") if composite_file.is_file() else None,
            "has_readme": readme_file.is_file(),
            "readme_path": str(readme_file.relative_to(WEBGUI_DIR)).replace("\\", "/") if readme_file.is_file() else None,
            "blocks_count": len(blocks),
            "blocks": blocks
        })

    return {
        "status": "success",
        "total_modules": len(modules),
        "modules": modules
    }


@router.get("/file")
def get_help_file(path: str = Query(..., description="Относительный путь к файлу справки")) -> Dict[str, Any]:
    """Считывает содержимое файла справки."""
    target_path = _sanitize_path(path)
    if not target_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Файл справки не найден: {path}"
        )

    try:
        content = target_path.read_text(encoding="utf-8")
        # Анализ на наличие inline HEX/RGB цветов
        has_hex = bool(re.search(r'style="[^"]*#[0-9a-fA-F]{3,6}[^"]*"', content))
        has_rgb = bool(re.search(r'style="[^"]*rgba?\([^)]+\)[^"]*"', content))

        return {
            "status": "success",
            "path": path,
            "content": content,
            "size_bytes": target_path.stat().st_size,
            "updated_at": datetime.fromtimestamp(target_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            "style_lint": {
                "has_hardcoded_hex": has_hex,
                "has_hardcoded_rgb": has_rgb,
                "is_theme_compliant": not (has_hex or has_rgb)
            }
        }
    except Exception as exc:
        logger.error(f"[HelpEditor] Ошибка чтения файла {path}: {exc}")
        raise HTTPException(status_code=500, detail=f"Ошибка чтения файла: {exc}")


@router.post("/file")
def save_help_file(req: HelpFileSaveRequest) -> Dict[str, Any]:
    """Сохраняет измененное содержимое файла справки и обновляет временную метку Updated."""
    target_path = _sanitize_path(req.path)

    # Проверка допустимых расширений
    if target_path.suffix.lower() not in [".html", ".md"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Редактирование разрешено только для файлов .html и .md"
        )

    content = req.content

    # Автоматическое обновление метки времени в шапке (Updated: YYYY-MM-DD HH:MM:SS)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if re.search(r'Updated:\s*\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}', content):
        content = re.sub(
            r'Updated:\s*\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}',
            f'Updated: {now_str}',
            content,
            count=1
        )

    # Валидация на inline цвета (предупреждение в лог)
    has_hex = bool(re.search(r'style="[^"]*#[0-9a-fA-F]{3,6}[^"]*"', content))
    has_rgb = bool(re.search(r'style="[^"]*rgba?\([^)]+\)[^"]*"', content))
    if has_hex or has_rgb:
        logger.console(f"[HelpEditor] Внимание: при сохранении {req.path} обнаружены hardcoded цвета.")

    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding="utf-8")
        logger.console(f"[HelpEditor] Файл успешно сохранен: {req.path}")
        return {
            "status": "success",
            "message": "Файл успешно сохранен",
            "path": req.path,
            "updated_at": now_str,
            "style_lint": {
                "has_hardcoded_hex": has_hex,
                "has_hardcoded_rgb": has_rgb,
                "is_theme_compliant": not (has_hex or has_rgb)
            }
        }
    except Exception as exc:
        logger.error(f"[HelpEditor] Ошибка записи файла {req.path}: {exc}")
        raise HTTPException(status_code=500, detail=f"Ошибка сохранения файла: {exc}")


@router.post("/create")
def create_help_block_or_page(req: HelpFileCreateRequest) -> Dict[str, Any]:
    """Создает новый шаблон атомарного блока или композитной страницы справки."""
    module_dir = WEBGUI_DIR / req.module
    if not module_dir.exists() or not module_dir.is_dir():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Модуль {req.module} не найден в webgui"
        )

    help_dir = module_dir / "help"
    help_dir.mkdir(parents=True, exist_ok=True)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if req.kind == "composite":
        target_file = help_dir / "index.html"
        if target_file.exists():
            raise HTTPException(status_code=400, detail="Композитный файл index.html уже существует")
        template = f"""<!--
=============================================================================
Process Name: Windows {req.module} - Composite Help View
=============================================================================
Description:
  Сводная иерархическая страница интерактивной справки для модуля {req.module}.
  Объединяет атомарные блоки справки через директиву data-help-include.

File: index.html
Project: ai-windows-admin
Package: windows/api/webgui/{req.module}/help
Author: hypo69
Copyright: © 2026 hypo69
Updated: {now_str}
=============================================================================
-->
<div class="help-composite-container p-1">
  <div class="p-3 mb-3 rounded border border-subtle bg-body-tertiary">
    <div class="d-flex align-items-center justify-content-between flex-wrap gap-2 mb-2">
      <div class="d-flex align-items-center gap-2">
        <i class="bi bi-journal-check text-primary fs-4"></i>
        <h5 class="mb-0 fw-bold text-body">{req.title or f'Справка: {req.module}'}</h5>
      </div>
      <span class="ui-badge ui-badge-info">{req.module}</span>
    </div>
    <p class="small text-muted mb-0">{req.description or 'Справочная информация и руководство пользователя.'}</p>
  </div>
  <div class="help-blocks-wrapper d-flex flex-column gap-2">
    <!-- Атомарные блоки подключаются через: -->
    <!-- <div data-help-include="/html/{req.module}/help/blocks/block_example.html"></div> -->
  </div>
</div>
"""
    elif req.kind == "block":
        blocks_dir = help_dir / "blocks"
        blocks_dir.mkdir(parents=True, exist_ok=True)
        filename = req.name if req.name.endswith(".html") else f"{req.name}.html"
        if not filename.startswith("block_"):
            filename = f"block_{filename}"
        target_file = blocks_dir / filename
        if target_file.exists():
            raise HTTPException(status_code=400, detail=f"Блок {filename} уже существует")

        block_id = filename.replace(".html", "")
        template = f"""<!--
=============================================================================
Process Name: Windows {req.module} - Atomic Help Block: {block_id}
=============================================================================
Description:
  Атомарный HTML-фрагмент справки {block_id}.

File: {filename}
Project: ai-windows-admin
Package: windows/api/webgui/{req.module}/help/blocks
Author: hypo69
Copyright: © 2026 hypo69
Updated: {now_str}
=============================================================================
-->
<div class="card bg-body border-subtle shadow-sm mb-3 help-atomic-block" data-help-block="{block_id}">
  <div class="card-header bg-body-tertiary d-flex align-items-center justify-content-between py-2 px-3">
    <div class="d-flex align-items-center gap-2">
      <i class="bi bi-info-circle text-primary fs-5"></i>
      <h6 class="mb-0 fw-bold text-body">{req.title or block_id}</h6>
    </div>
    <span class="ui-badge ui-badge-info">Атомарный блок</span>
  </div>
  <div class="card-body p-3">
    <p class="small text-muted mb-0">{req.description or 'Подробное описание функций блока.'}</p>
  </div>
</div>
"""
    elif req.kind == "doc":
        target_file = help_dir / "README.md"
        if target_file.exists():
            raise HTTPException(status_code=400, detail="README.md уже существует")
        template = f"""# Документация контекстной справки модуля {req.module}

## Назначение
{req.description or 'Описание архитектуры и блоков справки модуля.'}

Updated: {now_str}
"""
    else:
        raise HTTPException(status_code=400, detail=f"Неизвестный тип kind: {req.kind}")

    target_file.write_text(template, encoding="utf-8")
    rel_path = str(target_file.relative_to(WEBGUI_DIR)).replace("\\", "/")
    logger.console(f"[HelpEditor] Создан файл справки: {rel_path}")

    return {
        "status": "success",
        "message": f"Файл справки {target_file.name} успешно создан",
        "path": rel_path
    }


def init_router() -> APIRouter:
    """Фабричная функция инициализации роутера."""
    return router
