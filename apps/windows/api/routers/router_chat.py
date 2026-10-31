# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - Router Chat
# =============================================================================
# Description:
#   Handles AI conversational endpoints, streaming responses across multiple providers,
#
# Usage Examples:
#   Python API:
#     from apps.windows.api.routers.router_chat import ChatRequest
#
#     service = ChatRequest()
#
# File: router_chat.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-14 03:26:00
# =============================================================================

"""Handles AI conversational endpoints, streaming responses across multiple providers,"""

from typing import Any, Optional
from fastapi import APIRouter

from apps.windows.api.routers.chat.endpoints_chat import register_chat_endpoint
from apps.windows.api.routers.chat.endpoints_models import register_model_endpoints
from apps.windows.api.routers.chat.endpoints_sessions import register_session_endpoints
from apps.windows.api.routers.chat.helpers import get_chat_model  # noqa: F401


def init_router(
    chat_model: Optional[Any] = None,
    narrator_model: Optional[Any] = None,
    plugins: Optional[dict] = None,
) -> APIRouter:
    """Инициализация роутера с привязкой моделей (chat и narrator)."""
    if plugins is None:
        plugins = {}

    if hasattr(narrator_model, 'gemini_model') and narrator_model.gemini_model:
        narrator_model.gemini_model.save_history_chat = False

    chat_router = APIRouter(prefix='/api/v1/chat', tags=['chat'])
    register_model_endpoints(chat_router, chat_model, narrator_model, plugins)
    register_session_endpoints(chat_router, chat_model, narrator_model, plugins)
    register_chat_endpoint(chat_router, chat_model, narrator_model, plugins)
    return chat_router


__all__ = ['init_router', 'get_chat_model']

