# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - schedulers
# =============================================================================
# Description:
#   Эндпойнты настроек и запуска планировщиков.
#   Вынесено из router_admin.py (этап 4 оптимизации).
#
# File: schedulers.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers.admin
# Author: hypo69
# Copyright: c 2026 hypo69
# Updated: 2026-10-12 06:00:00
# =============================================================================

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict

from fastapi import HTTPException, Request
from pydantic import BaseModel, Field

from header import __root__
from logger import logger
from apps.windows.api.auth import require_admin_user
from .routers import router


# ============================================================================
# Scheduler Settings & Trigger API
# ============================================================================

class RagReindexConfig(BaseModel):
    enabled: bool = True
    interval_hours: float = 24.0

class EmailCheckConfig(BaseModel):
    enabled: bool = True
    interval_minutes: float = 5.0

class SchedulersConfigRequest(BaseModel):
    enabled: bool = True
    rag_reindex: RagReindexConfig = Field(default_factory=RagReindexConfig)
    email_check: EmailCheckConfig = Field(default_factory=EmailCheckConfig)


@router.get('/schedulers')
async def get_schedulers_config(request: Request) -> Dict[str, Any]:
    """Retrieve current background scheduler configuration and diagnostic status."""
    require_admin_user(request)
    from src.utils.scheduler import scheduler
    
    cfg_file = __root__ / 'config.json'
    sched_cfg = {}
    if cfg_file.exists():
        try:
            with open(cfg_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                sched_cfg = data.get('schedulers', {})
        except Exception as e:
            logger.error(f"Error reading schedulers config: {e}")

    return {
        'config': {
            'enabled': sched_cfg.get('enabled', True),
            'rag_reindex': sched_cfg.get('rag_reindex', {
                'enabled': True,
                'interval_hours': 24.0
            }),
            'email_check': sched_cfg.get('email_check', {
                'enabled': True,
                'interval_minutes': 5.0
            }),
        },
        'status': scheduler.status
    }


@router.post('/schedulers')
async def save_schedulers_config(data: SchedulersConfigRequest, request: Request) -> Dict[str, Any]:
    """Save background scheduler configuration to config.json and restart running jobs."""
    require_admin_user(request)
    from src.utils.scheduler import scheduler
    import src.config as app_config
    
    cfg_file = __root__ / 'config.json'
    try:
        with open(cfg_file, 'r', encoding='utf-8') as f:
            cfg_data = json.load(f)
    except Exception:
        cfg_data = {}

    sched_dict = {
        'enabled': data.enabled,
        'rag_reindex': {
            'enabled': data.rag_reindex.enabled,
            'interval_hours': data.rag_reindex.interval_hours
        },
        'email_check': {
            'enabled': data.email_check.enabled,
            'interval_minutes': data.email_check.interval_minutes
        }
    }

    cfg_data['schedulers'] = sched_dict

    with open(cfg_file, 'w', encoding='utf-8') as f:
        json.dump(cfg_data, f, indent=4, ensure_ascii=False)

    # Обновление глобального SimpleNamespace
    from src.utils.jjson import j_loads_ns
    app_config.global_settings = j_loads_ns(cfg_file)
    app_config.schedulers_cfg = getattr(app_config.global_settings, "schedulers", getattr(app_config.global_settings, "scheduler", None))

    # Перезапуск планировщика с новыми параметрами
    await scheduler.restart()

    logger.info("Scheduler configuration saved and service restarted successfully.")
    return {
        'status': 'ok',
        'message': 'Настройки планировщика успешно сохранены',
        'schedulers': scheduler.status
    }


@router.post('/schedulers/trigger/{job_name}')
async def trigger_scheduler_job(job_name: str, request: Request) -> Dict[str, Any]:
    """Manually trigger an immediate execution of a scheduled job."""
    require_admin_user(request)
    from src.utils.scheduler import scheduler
    
    if job_name == 'rag':
        summary = await scheduler.recheck_and_update_all_rags()
        scheduler._last_rag_run = datetime.now()
        return {'status': 'ok', 'job': 'rag', 'result': summary}
    elif job_name == 'email':
        messages = await scheduler.check_emails()
        scheduler._last_email_run = datetime.now()
        return {'status': 'ok', 'job': 'email', 'count': len(messages), 'messages': messages[:5]}
    else:
        raise HTTPException(status_code=400, detail=f"Неизвестная задача: {job_name}. Доступны: 'rag', 'email'")

