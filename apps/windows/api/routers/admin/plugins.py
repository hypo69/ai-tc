# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - plugins
# =============================================================================
# Description:
#   Эндпойнты менеджера плагинов.
#   Вынесено из router_admin.py (этап 4 оптимизации).
#
# File: plugins.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers.admin
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-30 13:25:00
# =============================================================================

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import HTTPException, Request
from pydantic import BaseModel

from logger import logger
from apps.windows.api.auth import require_admin_user
from .routers import router, plugins_router


# ============================================================================
# Plugin Manager Endpoints
# ============================================================================

class PluginStateUpdate(BaseModel):
    enabled: bool

class PluginConfigUpdate(BaseModel):
    config: Dict[str, Any]

class PluginActionRequest(BaseModel):
    params: Dict[str, Any] = {}

def _get_app_plugins(request: Request) -> Dict[str, Any]:
    """Retrieve or lazily initialize system plugins dictionary."""
    if not hasattr(request.app.state, 'plugins') or not request.app.state.plugins:
        try:
            from plugins import load_plugins
            chat_model = getattr(request.app.state, 'chat_model', None)
            request.app.state.plugins = load_plugins(ai_model=chat_model)
        except Exception as exc:
            logger.error(f"Failed to load plugins in router_admin: {exc}")
            request.app.state.plugins = {}
    return request.app.state.plugins

def _get_request_user(request: Request) -> Optional[Dict[str, Any]]:
    """Возвращает данные пользователя по умолчанию (администратор)."""
    return {'id': 1, 'is_admin': 1, 'role': 'admin', 'name': 'Admin'}


def _get_plugin_manifest(p: Any, lang: Optional[str] = None) -> Dict[str, Any]:
    """Safely retrieves plugin manifest with optional language parameter."""
    try:
        return p.get_manifest(lang=lang)
    except TypeError:
        return p.get_manifest()

@router.get('/plugins')
@plugins_router.get('')
@plugins_router.get('/')
async def get_all_plugins(request: Request, scope: Optional[str] = None, lang: Optional[str] = None) -> Dict[str, Any]:
    """Returns list of registered plugins and their manifests.
    
    If scope is 'user' or accessed from user-facing plugins endpoint by non-admin,
    plugins marked as system (is_system == True or scope == 'system') are excluded.
    """
    plugins_dict = _get_app_plugins(request)
    manifests = [_get_plugin_manifest(p, lang=lang) for p in plugins_dict.values()]
    
    user = _get_request_user(request)
    is_admin = bool(user and (user.get('is_admin') or user.get('role') == 'admin'))
    is_user_endpoint = request.url.path.rstrip('/').endswith('/api/plugins')

    if scope == 'user' or (is_user_endpoint and not is_admin):
        manifests = [
            m for m in manifests
            if not m.get('is_system', True) and m.get('scope') != 'system'
        ]

    return {'plugins': manifests, 'count': len(manifests)}

@router.get('/plugins/{plugin_name}')
@plugins_router.get('/{plugin_name}')
async def get_plugin_details(plugin_name: str, request: Request, lang: Optional[str] = None) -> Dict[str, Any]:
    """Returns manifest of a specific plugin."""
    plugins_dict = _get_app_plugins(request)
    plugin = plugins_dict.get(plugin_name)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Плагин '{plugin_name}' не найден")
    
    user = _get_request_user(request)
    is_admin = bool(user and (user.get('is_admin') or user.get('role') == 'admin'))
    is_user_endpoint = request.url.path.startswith('/api/plugins')
    if (is_user_endpoint and not is_admin) and getattr(plugin, 'is_system', True):
        raise HTTPException(status_code=403, detail=f"Системный плагин '{plugin_name}' доступен только администратору")

    return _get_plugin_manifest(plugin, lang=lang)

@router.post('/plugins/{plugin_name}/toggle')
async def toggle_plugin(plugin_name: str, data: PluginStateUpdate, request: Request) -> Dict[str, Any]:
    """Enable or disable a plugin at runtime."""
    plugins_dict = _get_app_plugins(request)
    plugin = plugins_dict.get(plugin_name)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Плагин '{plugin_name}' не найден")

    user = _get_request_user(request)
    is_admin = bool(user and (user.get('is_admin') or user.get('role') == 'admin'))
    if getattr(plugin, 'is_system', True) and not is_admin:
        raise HTTPException(status_code=403, detail=f"Системный плагин '{plugin_name}' устанавливается и переключается только администратором")

    plugin.enabled = data.enabled
    plugin.update_config({'enabled': data.enabled})
    logger.info(f"Plugin {plugin_name} enabled state changed to {data.enabled}")
    return {'name': plugin_name, 'enabled': plugin.enabled, 'message': f"Плагин {plugin_name} {'включен' if data.enabled else 'выключен'}"}

@router.post('/plugins/{plugin_name}/config')
async def save_plugin_config(plugin_name: str, data: PluginConfigUpdate, request: Request) -> Dict[str, Any]:
    """Update plugin configuration."""
    plugins_dict = _get_app_plugins(request)
    plugin = plugins_dict.get(plugin_name)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Плагин '{plugin_name}' не найден")

    user = _get_request_user(request)
    is_admin = bool(user and (user.get('is_admin') or user.get('role') == 'admin'))
    if getattr(plugin, 'is_system', True) and not is_admin:
        raise HTTPException(status_code=403, detail=f"Параметры системного плагина '{plugin_name}' могут изменяться только администратором")

    plugin.update_config(data.config)
    return {'name': plugin_name, 'config': plugin.config, 'message': 'Конфигурация сохранена'}

@router.post('/plugins/{plugin_name}/action/{action_name}')
async def call_plugin_action(plugin_name: str, action_name: str, data: PluginActionRequest, request: Request) -> Dict[str, Any]:
    """Execute an action on a specific plugin."""
    plugins_dict = _get_app_plugins(request)
    plugin = plugins_dict.get(plugin_name)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Плагин '{plugin_name}' не найден")
    
    params = dict(data.params or {})
    user = _get_request_user(request)
    if user and not user.get('is_admin') and user.get('role') != 'admin':
        # Inject user_id for non-admin users so actions are isolated
        params['user_id'] = user.get('id')

    result = await plugin.execute_action(action_name, params)
    return result

@router.get('/plugin/{plugin_name}/status')
async def get_plugin_status(plugin_name: str, request: Request):
    """Retrieve status of plugin (backward compatibility)."""
    plugins_dict = _get_app_plugins(request)
    plugin = plugins_dict.get(plugin_name)
    if not plugin:
        raise HTTPException(status_code=404, detail='Плагин не найден')
    return await plugin.health_check()

@router.post('/plugin/{plugin_name}/status')
async def update_plugin_status(plugin_name: str, data: PluginStateUpdate, request: Request):
    """Update status of plugin (backward compatibility)."""
    require_admin_user(request)
    plugins_dict = _get_app_plugins(request)
    plugin = plugins_dict.get(plugin_name)
    if not plugin:
        raise HTTPException(status_code=404, detail='Плагин не найден')
    plugin.enabled = data.enabled
    plugin.update_config({'enabled': data.enabled})
    logger.info(f'Plugin {plugin_name} enabled state changed to {data.enabled}')
    return {'name': plugin_name, 'enabled': plugin.enabled}
