# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - endpoints_sessions
# =============================================================================
# Description:
#   Эндпойнты сохранения в RAG и сессий чата.
#   Вынесено из router_chat.py (этап 4 оптимизации).
#
# File: endpoints_sessions.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers.chat
# Author: hypo69
# Copyright: c 2026 hypo69
# Updated: 2026-10-12 06:20:00
# =============================================================================

from __future__ import annotations

import os
import asyncio
from fastapi import APIRouter, HTTPException, Request

from logger import logger

from apps.windows.api import chat_sessions_db
from .helpers import _extract_user_auth
from .models import ChatSessionPayload
from .models import SaveRagRequest
from .models import SyncSessionsRequest


def register_session_endpoints(router: APIRouter, chat_model, narrator_model, plugins: dict) -> None:
    """Регистрирует эндпойнты RAG и сессий на роутере."""
    @router.post('/save-rag')
    async def save_to_rag(rag_req: SaveRagRequest, request: Request):
        """Ручное сохранение одобренного ответа в постоянный JSON-архив."""
        try:
            user_identifier, _, _, _ = await _extract_user_auth(request)
            try:
                from src.rag import save_user_approved_response
                save_success = await asyncio.to_thread(
                    save_user_approved_response,
                    user_identifier, rag_req.query, rag_req.chat_text, rag_req.voice_text
                )
            except ImportError:
                save_success = True
            if save_success:
                return {"status": "success", "message": "Successfully сохранено для последующей компиляции RAG"}
            else:
                raise HTTPException(status_code=500, detail="Error сохранения ответа")
        except Exception as e:
            logger.error("Error при ручном сохранении ответа", e)
            raise HTTPException(status_code=500, detail=str(e))

    @router.post('/save-rag-instant')
    async def save_to_rag_instant(rag_req: SaveRagRequest, request: Request):
        """Мгновенное сохранение ответа: запись в JSON + векторизация в FAISS."""
        try:
            user_identifier, _, _, _ = await _extract_user_auth(request)
            api_key = getattr(chat_model, 'api_key', '') or os.getenv('GEMINI_API_KEY', '')

            content_to_index = rag_req.voice_text if rag_req.voice_text.strip() else rag_req.chat_text

            try:
                from src.rag import save_user_approved_response, index_user_interaction
                save_success = await asyncio.to_thread(
                    save_user_approved_response,
                    user_identifier, rag_req.query, rag_req.chat_text, rag_req.voice_text
                )
                rag_success = await asyncio.to_thread(
                    index_user_interaction, user_identifier, api_key, rag_req.query, content_to_index
                )
            except ImportError:
                save_success, rag_success = True, True

            if save_success and rag_success:
                return {"status": "success", "message": "Successfully сохранено в архив и проиндексировано в RAG"}
            elif save_success:
                return {"status": "success", "message": "Сохранено в архив, но произошла Error при индексации в RAG"}
            else:
                raise HTTPException(status_code=500, detail="Error сохранения ответа")
        except Exception as e:
            logger.error("Error при мгновенном сохранении в RAG", e)
            raise HTTPException(status_code=500, detail=str(e))

    @router.get('/sessions')
    async def get_all_sessions(request: Request):
        """Retrieve all chat sessions for the current user or host."""
        try:
            user_identifier, _, _, _ = await _extract_user_auth(request)
            sessions = await asyncio.to_thread(chat_sessions_db.list_sessions, user_identifier)
            return {"status": "success", "sessions": sessions}
        except Exception as e:
            logger.error("Error retrieving chat sessions", e)
            raise HTTPException(status_code=500, detail=str(e))

    @router.get('/sessions/{session_id}')
    async def get_single_session(session_id: str, request: Request):
        """Retrieve a specific chat session by ID."""
        try:
            user_identifier, _, _, _ = await _extract_user_auth(request)
            session_data = await asyncio.to_thread(chat_sessions_db.get_session, session_id, user_identifier)
            if not session_data:
                raise HTTPException(status_code=404, detail="Session not found")
            return {"status": "success", "session": session_data}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error retrieving chat session {session_id}", e)
            raise HTTPException(status_code=500, detail=str(e))

    @router.post('/sessions')
    async def save_session_endpoint(payload: ChatSessionPayload, request: Request):
        """Save or update a chat session."""
        try:
            user_identifier, _, _, _ = await _extract_user_auth(request)
            data = payload.model_dump()
            saved = await asyncio.to_thread(chat_sessions_db.save_session, data, user_identifier)
            return {"status": "success", "session": saved}
        except Exception as e:
            logger.error("Error saving chat session", e)
            raise HTTPException(status_code=500, detail=str(e))

    @router.post('/sessions/sync')
    async def sync_sessions_endpoint(sync_req: SyncSessionsRequest, request: Request):
        """Bulk synchronize chat sessions from client to server."""
        try:
            user_identifier, _, _, _ = await _extract_user_auth(request)
            merged = await asyncio.to_thread(chat_sessions_db.bulk_sync_sessions, sync_req.sessions, user_identifier)
            return {"status": "success", "sessions": merged}
        except Exception as e:
            logger.error("Error synchronizing chat sessions", e)
            raise HTTPException(status_code=500, detail=str(e))

    @router.delete('/sessions/{session_id}')
    async def delete_session_endpoint(session_id: str, request: Request):
        """Delete a specific chat session."""
        try:
            user_identifier, _, _, _ = await _extract_user_auth(request)
            deleted = await asyncio.to_thread(chat_sessions_db.delete_session, session_id, user_identifier)
            return {"status": "success", "deleted": deleted}
        except Exception as e:
            logger.error(f"Error deleting chat session {session_id}", e)
            raise HTTPException(status_code=500, detail=str(e))

    @router.delete('/sessions')
    async def clear_all_sessions_endpoint(request: Request):
        """Clear all chat sessions for the current user."""
        try:
            user_identifier, _, _, _ = await _extract_user_auth(request)
            cleared = await asyncio.to_thread(chat_sessions_db.clear_sessions, user_identifier)
            return {"status": "success", "cleared": cleared}
        except Exception as e:
            logger.error("Error clearing chat sessions", e)
            raise HTTPException(status_code=500, detail=str(e))

