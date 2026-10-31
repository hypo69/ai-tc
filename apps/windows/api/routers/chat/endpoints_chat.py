# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - endpoints_chat
# =============================================================================
# Description:
#   Основной потоковый эндпойнт чата.
#   Вынесено из router_chat.py (этап 4 оптимизации).
#
# File: endpoints_chat.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers.chat
# Author: hypo69
# Copyright: c 2026 hypo69
# Updated: 2026-10-15 11:27:00
# =============================================================================

from __future__ import annotations

import os
import asyncio
from fastapi import APIRouter, Request

from logger import logger

from .helpers import _build_debug_prompt
from .helpers import _clean_chat_history
from .helpers import _extract_user_auth
from .helpers import _get_voice_gender_rule
from .helpers import get_chat_model
from .models import ChatRequest


def register_chat_endpoint(router: APIRouter, chat_model, narrator_model, plugins: dict) -> None:
    """Регистрирует эндпойнт чата на роутере."""
    @router.post('')

    async def chat(chat_req: ChatRequest, request: Request):
        """Обработка чат-запроса по алгоритму RAG-First: RAG Search -> Direct Match / LLM Fallback -> Auto-Index."""
        from fastapi.responses import StreamingResponse
        import json

        async def event_generator():
            try:
                user_identifier, system_instruction, selected_model, settings = await _extract_user_auth(request)

                api_key = getattr(chat_model, 'api_key', '') or os.getenv('GEMINI_API_KEY', '')

                # 1. RAG: Поиск по базе знаний (опционально, по умолчанию отключен)
                is_rag_active = bool(chat_req.generation_config.get('rag_enabled', False))

                context_text = ""
                if is_rag_active:
                    try:
                        from src.rag import get_rag_engine
                        rag_engine = get_rag_engine()

                        top_k = int(chat_req.generation_config.get('top_k', 3))
                        threshold = float(chat_req.generation_config.get('min_score', chat_req.generation_config.get('threshold', 0.45)))

                        yield f"data: {json.dumps({'status': '🔍 Поиск в базе знаний (RAG)...'})}\n\n"
                        decision = await rag_engine.evaluate(
                            query=chat_req.message,
                            user_identifier=user_identifier,
                            api_key=api_key,
                            threshold=threshold,
                            top_k=top_k
                        )

                        # 2. Если найден точный ответ — мгновенный возврат (Direct RAG)
                        if decision.is_direct:
                            yield f"data: {json.dumps({'status': decision.status_message or '⚡ Ответ найден в базе знаний...'})}\n\n"
                    except (ImportError, Exception) as rag_err:
                        logger.debug(f"[Chat RAG] RAG пропущен: {rag_err}")
                        yield f"data: {json.dumps({'status': decision.status_message or '⚡ Ответ найден в базе знаний...'})}\n\n"
                        yield f"data: {json.dumps({'text': decision.direct_text})}\n\n"
                        return
                    context_text = decision.context_text

                # 3. Подготовка контекста для LLM
                dynamic_context_parts = []
                if context_text:
                    dynamic_context_parts.append(context_text)

                user_msg_with_context = chat_req.message
                if dynamic_context_parts:
                    user_msg_with_context = "\n\n".join(dynamic_context_parts) + "\n\n[Запрос пользователя]:\n" + chat_req.message

                # Режим отладки (DEBUG MODE)
                if chat_req.generation_config.get('debug_mode', False):
                    voice_gender_instruction = _get_voice_gender_rule(settings)
                    debug_text = _build_debug_prompt(chat_req, context_text, voice_gender_instruction)
                    yield f"data: {json.dumps({'status': 'DEBUG MODE: Промпт сформирован, не отправляется в модель'})}\n\n"
                    yield f"data: {json.dumps({'text': debug_text})}\n\n"
                    return

                # Интеллектуальный роутинг: Агент анализа системных логов Windows (System Logs Analyzer Agent)
                msg_lower = chat_req.message.lower()
                is_system_logs_request = any(
                    phrase in msg_lower for phrase in (
                        'критические ошибки в операционной системе',
                        'критических ошибок в операционной системе',
                        'ошибки в операционной системе',
                        'ошибок в операционной системе',
                        'критические ошибки в ос',
                        'критических ошибок в ос',
                        'ошибки в ос',
                        'ошибок в ос',
                        'system logs analyzer',
                        'журнал событий windows',
                        'журналы событий windows',
                        'системные логи windows',
                        'системных логах windows',
                    )
                )

                if is_system_logs_request:
                    yield f"data: {json.dumps({'status': '🚀 Запуск System Logs Analyzer Agent...'})}\n\n"
                    from src.ai.agents.system_logs_agent import SystemLogsAgent
                    agent = SystemLogsAgent()
                    
                    selected_model_name = chat_req.generation_config.get('model') or selected_model or 'gemini-3.1-flash'
                    active_model = get_chat_model(selected_model_name, system_instruction or "", user_id=user_identifier)
                    
                    yield f"data: {json.dumps({'status': '🔍 Сбор и кластеризация событий из Windows Event Log...'})}\n\n"
                    agent_report = await agent.run(chat_req.message, active_llm=active_model)
                    
                    yield f"data: {json.dumps({'text': agent_report})}\n\n"
                    return

                token = request.cookies.get('auth_token') if request else None
                room_id = token or 'default'

                if chat_req.generation_config.get('model'):
                    selected_model = chat_req.generation_config['model']

                clean_history = _clean_chat_history(chat_req.history)
                kwargs = {
                    'history': clean_history,
                    'room_id': room_id,
                    'model_name': selected_model,
                }
                if chat_req.generation_config.get('search_engine'):
                    kwargs['search_engine'] = chat_req.generation_config['search_engine']

                if selected_model:
                    active_model = get_chat_model(selected_model, system_instruction or "", user_id=user_identifier)
                    api_key = getattr(active_model, 'api_key', '') or getattr(chat_model, 'api_key', '') or api_key
                else:
                    active_model = chat_model

                yield f"data: {json.dumps({'status': 'Генерация ответа...'})}\n\n"

                chat_kwargs = kwargs.copy()
                chat_kwargs.pop('room_id', '')
                chat_kwargs.pop('search_engine', None)
                gen_cfg = chat_req.generation_config.copy()
                gen_cfg['response_type'] = 'chat'
                chat_kwargs['generation_config'] = gen_cfg

                stream_generator = active_model.chat_stream(user_msg_with_context, **chat_kwargs)

                chat_response = ""
                async for chunk in stream_generator:
                    if chunk:
                        # Защита: прерывание потока при обнаружении текста фатальной ошибки harness/SDK
                        if any(marker in chunk for marker in (
                            "Harness process exited unexpectedly",
                            "Error Antigravity SDK",
                            "Ошибка провайдера agy",
                            "This model is currently experiencing high demand",
                        )):
                            logger.error(f"[Chat] Перехвачена критическая ошибка в потоке ответа: {chunk}")
                            yield f"data: {json.dumps({'error': chunk.strip()})}\n\n"
                            return

                        c = chunk.replace("[CHAT]", "").replace("[VOICE]", "")
                        if c:
                            chat_response += c
                            yield f"data: {json.dumps({'text': c})}\n\n"

                # 4. Фоновая индексация взаимодействия в RAG (только если RAG был явно включен)
                if is_rag_active and chat_response and api_key and user_identifier:
                    from src.rag import index_user_interaction
                    asyncio.ensure_future(asyncio.to_thread(
                        index_user_interaction, user_identifier, api_key, chat_req.message, chat_response
                    ))

            except Exception as ex:
                logger.error('Error обработки чат-запроса', ex)
                yield f"data: {json.dumps({'error': str(ex)})}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

