# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - instructions
# =============================================================================
# Description:
#   Эндпойнты инструкций, системных промптов и источников.
#   Вынесено из router_admin.py (этап 4 оптимизации).
#
# File: instructions.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers.admin
# Author: hypo69
# Copyright: c 2026 hypo69
# Updated: 2026-10-22 13:30:00
# =============================================================================

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from fastapi import HTTPException, Request
from pydantic import BaseModel

from header import __root__
from src.config import ai_cfg
from logger import logger
from apps.windows.api.auth import require_admin_user
from .routers import router


# ============================================================================
# Пути к файлам инструкций
# ============================================================================

_INSTRUCTION_FILES: Dict[str, Path] = {
    'chat': __root__ / 'apps' / 'windows' / 'prompts' / 'chat' / 'system_instruction.md',
    'narrator': __root__ / 'apps' / 'windows' / 'prompts' / 'narrator' / 'narrator_style.md',
}

_VERSIONS_DIRS: Dict[str, Path] = {
    'chat': __root__ / 'apps' / 'windows' / 'prompts' / 'chat' / 'versions',
    'narrator': __root__ / 'apps' / 'windows' / 'prompts' / 'narrator' / 'versions',
}

_SOURCES_FILE = __root__ / 'plugins' / 'movie_search_sources' / 'sources.json'

# ============================================================================
# Pydantic-модели
# ============================================================================

class SystemInstructionUpdate(BaseModel):
    """Модель обновления системной инструкции."""
    content: str


class InstructionRoleUpdate(BaseModel):
    """Модель сохранения новой версии инструкции."""
    mode: str = 'chat'
    content: str


class InstructionActivateRequest(BaseModel):
    """Модель активации сохраненной версии инструкции."""
    mode: str = 'chat'
    filename: str


class RawSourcesUpdate(BaseModel):
    """Модель обновления JSON-текста источников."""
    content: str


# ============================================================================
# Helper functions
# ============================================================================

def _get_active_file(mode: str) -> Path:
    """Возвращает путь к активному файлу инструкции для указанного режима."""
    return _INSTRUCTION_FILES.get(mode, _INSTRUCTION_FILES['chat'])


def _get_versions_dir(mode: str) -> Path:
    """Возвращает директорию версий инструкций для указанного режима."""
    path = _VERSIONS_DIRS.get(mode, _VERSIONS_DIRS['chat'])
    path.mkdir(parents=True, exist_ok=True)
    return path


def _next_version_number(versions_dir: Path) -> int:
    """Определяет следующий порядковый номер версии инструкции."""
    versions_dir.mkdir(parents=True, exist_ok=True)
    max_ver = 0
    for file in versions_dir.glob('v*.md'):
        m = re.match(r'^v(\d+)_', file.name)
        if m:
            max_ver = max(max_ver, int(m.group(1)))
    return max_ver + 1


def _load_sources_raw() -> str:
    """Загружает содержимое файла источников."""
    if _SOURCES_FILE.exists():
        return _SOURCES_FILE.read_text(encoding='utf-8')
    return '{}'


def _save_sources_raw(content: str) -> None:
    """Сохраняет содержимое файла источников."""
    _SOURCES_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SOURCES_FILE.write_text(content, encoding='utf-8')


@router.get('/system_instruction')
async def get_system_instruction(request: Request) -> Dict[str, str]:
    """Получение текста системной инструкции чата (legacy endpoint)."""
    require_admin_user(request)
    active_file = _get_active_file('chat')
    try:
        content = active_file.read_text(encoding='utf-8') if active_file.exists() else ''
        return {'content': content}
    except Exception as ex:
        logger.error('Error чтения system_instruction', ex)
        raise HTTPException(status_code=500, detail='Не удалось прочитать системную инструкцию')

@router.post('/system_instruction')
async def update_system_instruction(request: Request, data: SystemInstructionUpdate) -> Dict[str, str]:
    """Update текста системной инструкции чата (legacy endpoint)."""
    require_admin_user(request)
    active_file = _get_active_file('chat')
    try:
        active_file.parent.mkdir(parents=True, exist_ok=True)
        active_file.write_text(data.content, encoding='utf-8')
        if hasattr(request.app.state, 'chat_model') and request.app.state.chat_model:
            request.app.state.chat_model.update_system_instruction(data.content)
        logger.info('System instruction updated via admin panel (legacy endpoint)')
        return {'status': 'ok', 'message': 'Системная инструкция successfully сохранена'}
    except Exception as ex:
        logger.error('Error записи system_instruction', ex)
        raise HTTPException(status_code=500, detail='Не удалось сохранить системную инструкцию')

# ============================================================================
# Instructions Endpoints (файловое версионирование)
# ============================================================================

@router.get('/instructions')
async def get_instruction(request: Request, mode: str = 'chat') -> Dict[str, str]:
    """Получение активной инструкции по режиму из файла."""
    require_admin_user(request)
    active_file = _get_active_file(mode)
    try:
        content = active_file.read_text(encoding='utf-8') if active_file.exists() else ''
        return {'content': content, 'mode': mode, 'file': str(active_file.name)}
    except Exception as ex:
        logger.error(f'Error чтения инструкции mode={mode}', ex)
        raise HTTPException(status_code=500, detail='Не удалось прочитать инструкцию')

@router.post('/instructions/save')
async def save_instruction(request: Request, data: InstructionRoleUpdate) -> Dict[str, str]:
    """Сохранение новой версии инструкции в файл и update активного файла."""
    require_admin_user(request)
    active_file = _get_active_file(data.mode)
    versions_dir = _get_versions_dir(data.mode)

    try:
        # 1. Вычисляем номер следующей версии
        version_num = _next_version_number(versions_dir)
        date_str = datetime.now().strftime('%Y-%m-%d')
        version_filename = f'v{version_num}_{date_str}.md'
        version_path = versions_dir / version_filename

        # 2. Сохраняем файл версии
        version_path.write_text(data.content, encoding='utf-8')
        logger.info(f'Saved instruction version: {version_path}')

        # 3. Перезаписываем активный файл
        active_file.parent.mkdir(parents=True, exist_ok=True)
        active_file.write_text(data.content, encoding='utf-8')
        
        # Обновляем модель в памяти без перезагрузки
        if data.mode == 'chat' and hasattr(request.app.state, 'chat_model'):
            request.app.state.chat_model.update_system_instruction(data.content)
        elif data.mode == 'narrator' and hasattr(request.app.state, 'narrator_model'):
            request.app.state.narrator_model.update_system_instruction(data.content)
            
        logger.info(f'Updated active instruction file: {active_file} (mode={data.mode})')

        return {
            'status': 'ok',
            'message': f'Инструкция сохранена как версия {version_filename}',
            'version': version_filename
        }
    except Exception as ex:
        logger.error(f'Error сохранения инструкции mode={data.mode}', ex)
        raise HTTPException(status_code=500, detail='Не удалось сохранить инструкцию')

@router.get('/instructions/versions')
async def get_instruction_versions(request: Request, mode: str = 'chat') -> Dict[str, Any]:
    """Получение списка версий инструкций из папки versions/."""
    require_admin_user(request)
    versions_dir = _get_versions_dir(mode)
    active_file = _get_active_file(mode)

    try:
        # Читаем содержимое активного файла для сравнения
        active_content = active_file.read_text(encoding='utf-8') if active_file.exists() else ''

        version_files = sorted(versions_dir.glob('v*.md'), key=lambda f: f.stat().st_mtime, reverse=True)

        versions = []
        for vf in version_files:
            try:
                file_content = vf.read_text(encoding='utf-8')
                stat = vf.stat()
                created_at = datetime.fromtimestamp(stat.st_mtime).isoformat()
                is_active = (file_content.strip() == active_content.strip())
                versions.append({
                    'filename': vf.name,
                    'mode': mode,
                    'is_active': is_active,
                    'created_at': created_at,
                    'size': stat.st_size,
                    'preview': file_content[:120] + '...' if len(file_content) > 120 else file_content,
                })
            except Exception as read_ex:
                logger.warning(f'Не удалось прочитать файл версии {vf}: {read_ex}')

        return {'versions': versions, 'mode': mode}
    except Exception as ex:
        logger.error(f'Error чтения версий mode={mode}', ex)
        raise HTTPException(status_code=500, detail='Не удалось прочитать версии')

@router.post('/instructions/activate')
async def activate_instruction(request: Request, data: InstructionActivateRequest) -> Dict[str, str]:
    """Активация выбранной версии инструкции — копирует файл версии в активный."""
    require_admin_user(request)
    versions_dir = _get_versions_dir(data.mode)
    active_file = _get_active_file(data.mode)

    # Безопасность: только имя файла, без path traversal
    safe_filename = Path(data.filename).name
    version_path = versions_dir / safe_filename

    if not version_path.exists():
        raise HTTPException(status_code=404, detail=f'Версия {safe_filename} не найдена')

    try:
        content = version_path.read_text(encoding='utf-8')
        active_file.parent.mkdir(parents=True, exist_ok=True)
        active_file.write_text(content, encoding='utf-8')
        
        # Обновляем модель в памяти без перезагрузки
        if data.mode == 'chat' and hasattr(request.app.state, 'chat_model'):
            request.app.state.chat_model.update_system_instruction(content)
        elif data.mode == 'narrator' and hasattr(request.app.state, 'narrator_model'):
            request.app.state.narrator_model.update_system_instruction(content)
            
        logger.info(f'Activated instruction version {safe_filename} for mode={data.mode}')
        return {'status': 'ok', 'message': f'Версия {safe_filename} активирована', 'version': safe_filename}
    except Exception as ex:
        logger.error(f'Error активации версии {safe_filename}', ex)
        raise HTTPException(status_code=500, detail='Не удалось активировать версию')

@router.post('/instructions/check')
async def check_instruction_in_model(request: Request, data: Dict[str, Any]) -> Dict[str, Any]:
    """Временная check инструкции в модели без сохранения."""
    require_admin_user(request)
    try:
        from src.ai.unified_chat import UnifiedChatModel
        import os

        api_key_names = [n.strip() for n in os.getenv('GEMINI_API_KEY_NAMES', '').split(',') if n.strip()]
        if not api_key_names:
            raise HTTPException(status_code=500, detail='GEMINI_API_KEY_NAMES не настроен')

        system_instruction = data.get('instruction', '')
        prompt = data.get('prompt', 'Привет!')
        
        # Get foundry model from new config format
        from src.config import ai_cfg
        providers = getattr(ai_cfg, "providers", {}) if ai_cfg else {}
        foundry_cfg = providers.get("foundry", {}) if isinstance(providers, dict) else {}
        foundry_model_id = foundry_cfg.get("model", None) or os.getenv('FOUNDRY_MODEL_ID', 'qwen2.5-1.5b-instruct-generic-cpu:4')

        # Создаём временный инстанс модели для теста
        temp_model = UnifiedChatModel(
            api_key_names=api_key_names,
            system_instruction=system_instruction,
        )

        response = await temp_model.chat(prompt)

        total_tokens = len(system_instruction) // 3 + len(prompt) // 3 + len(response or '') // 3

        return {
            'status': 'ok',
            'response': response or '',
            'token_count': total_tokens
        }
    except Exception as ex:
        logger.error('Error проверки инструкции в модели', ex)
        raise HTTPException(status_code=500, detail=f'Error проверки: {ex}')

# ============================================================================
# Sources Endpoints
# ============================================================================

@router.get('/sources/raw')
async def get_sources_raw(request: Request) -> Dict[str, str]:
    """Получение сырого JSON-текста источников."""
    require_admin_user(request)
    content = _load_sources_raw()
    return {'content': content}

@router.post('/sources/raw')
async def update_sources_raw(request: Request, data: RawSourcesUpdate) -> Dict[str, str]:
    """Update сырого JSON-текста источников."""
    require_admin_user(request)
    _save_sources_raw(data.content)
    logger.info('Sources JSON updated via admin panel')
    return {'status': 'ok'}

