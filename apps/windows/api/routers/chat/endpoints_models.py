# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - endpoints_models
# =============================================================================
# Description:
#   Эндпойнты моделей, провайдеров, инструкций и здоровья моделей.
#   Вынесено из router_chat.py (этап 4 оптимизации).
#
# File: endpoints_models.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers.chat
# Author: hypo69
# Copyright: c 2026 hypo69
# Updated: 2026-10-30 13:25:00
# =============================================================================

from __future__ import annotations

import time
import asyncio
from fastapi import APIRouter, HTTPException, Request

from logger import logger
from apps.windows.api.config_helper import save_ai_config

from header import __root__
from .helpers import _active_chat_models
from .helpers import _extract_user_auth
from .helpers import _get_effective_model_and_provider
from .helpers import _normalize_model_and_provider
from .helpers import _resolve_default_model_and_provider
from .helpers import get_chat_model
from .models import ModelInstructionPayload
from .models import SetModelPayload
from .models import SetProviderPayload
from .models import TestModelRequest


def register_model_endpoints(router: APIRouter, chat_model, narrator_model, plugins: dict) -> None:
    """Регистрирует эндпойнты моделей на роутере."""
    @router.get('/models')
    async def get_models(fastapi_req: Request, refresh: bool = False, include_unsupported: bool = False) -> dict:
        """Получение списка доступных моделей, сгруппированных по провайдеру."""
        from src.ai.model_manager import get_available_models, load_unsupported_models

        gemini_models = get_available_models('gemini', force_refresh=refresh, include_unsupported=include_unsupported)
        
        foundry_raw = get_available_models('foundry', force_refresh=refresh, include_unsupported=include_unsupported)
        foundry_models = [f"foundry:{m}" if not m.startswith('foundry:') else m for m in foundry_raw]

        ollama_raw = get_available_models('ollama', force_refresh=refresh, include_unsupported=include_unsupported)
        ollama_models = [f"ollama:{m}" if not m.startswith('ollama:') else m for m in ollama_raw]

        agy_models = get_available_models('agy', force_refresh=refresh, include_unsupported=include_unsupported)

        gemini_cli_raw = get_available_models('gemini_cli', force_refresh=refresh, include_unsupported=include_unsupported)
        gemini_cli_models = [f"gemini_cli:{m}" if not m.startswith('gemini_cli:') else m for m in gemini_cli_raw]

        openai_raw = get_available_models('openai', force_refresh=refresh, include_unsupported=include_unsupported)
        openai_models = [f"openai:{m}" if not any(m.startswith(f"{p}:") for p in ('openai', 'deepseek', 'groq', 'openrouter', 'lmstudio')) else m for m in openai_raw]

        hf_raw = get_available_models('hf', force_refresh=refresh, include_unsupported=include_unsupported)
        hf_models = [f"hf:{m}" if not m.startswith('hf:') else m for m in hf_raw]

        onnx_raw = get_available_models('onnx', force_refresh=refresh, include_unsupported=include_unsupported)
        onnx_models = [f"onnx:{m}" if not m.startswith('onnx:') else m for m in onnx_raw]

        return {
            'models': {
                'gemini': gemini_models,
                'foundry': foundry_models,
                'ollama': ollama_models,
                'agy': agy_models,
                'gemini_cli': gemini_cli_models,
                'openai': openai_models,
                'hf': hf_models,
                'onnx': onnx_models,
            },
            'unsupported_models': {
                'gemini': list(load_unsupported_models('gemini')),
                'foundry': list(load_unsupported_models('foundry')),
                'ollama': list(load_unsupported_models('ollama')),
                'agy': list(load_unsupported_models('agy')),
                'gemini_cli': list(load_unsupported_models('gemini_cli')),
                'openai': list(load_unsupported_models('openai')),
                'hf': list(load_unsupported_models('hf')),
                'onnx': list(load_unsupported_models('onnx')),
            }
        }

    @router.get('/model')
    @router.get('/active-model')
    async def get_model_endpoint(fastapi_req: Request, profile: str = "") -> dict:
        """Получение текущей активной AI-модели."""
        provider, model_name, config_file = await _get_effective_model_and_provider(fastapi_req, profile=profile)
        return {
            "status": "success",
            "model": model_name,
            "provider": provider,
            "display": f"{provider}: {model_name}",
            "config_file": config_file,
        }

    @router.post('/model')
    @router.put('/model')
    async def set_model_endpoint(req: SetModelPayload, fastapi_req: Request) -> dict:
        """Установка активной модели для текущего пользователя и сессии."""
        try:
            target_model = req.model.strip()
            if not target_model:
                raise HTTPException(status_code=400, detail="Имя модели не может быть пустым")

            normalized_model, provider = _normalize_model_and_provider(target_model, req.provider)
            user_identifier, _, _, _ = await _extract_user_auth(fastapi_req)

            # Обновление состояния базового chat_model
            active_chat_ref = getattr(getattr(fastapi_req, "app", None), "state", None)
            target_chat_model = getattr(active_chat_ref, "chat_model", None) if active_chat_ref else None
            if not target_chat_model:
                target_chat_model = chat_model
            if target_chat_model:
                if hasattr(target_chat_model, "_model_name"):
                    target_chat_model._model_name = normalized_model
                if hasattr(target_chat_model, "model_name"):
                    target_chat_model.model_name = normalized_model

            # Сохраняем в apps/windows/config.json
            save_ai_config(provider=provider, model_name=normalized_model)

            return {
                "status": "success",
                "message": "Модель успешно обновлена",
                "model": normalized_model,
                "provider": provider,
            }
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"[router_chat] Ошибка при установке модели: {exc}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(exc))

    @router.get('/provider')
    async def get_provider_endpoint(fastapi_req: Request, profile: str = "") -> dict:
        """Получение текущего активного AI-провайдера."""
        provider, model_name, config_file = await _get_effective_model_and_provider(fastapi_req, profile=profile)
        return {
            "status": "success",
            "provider": provider,
            "model": model_name,
            "display": f"{provider}: {model_name}",
            "config_file": config_file,
        }

    @router.post('/provider')
    @router.put('/provider')
    async def set_provider_endpoint(req: SetProviderPayload, fastapi_req: Request) -> dict:
        """Установка активного AI-провайдера для текущего пользователя и сессии."""
        try:
            target_provider = req.provider.strip()
            if not target_provider:
                raise HTTPException(status_code=400, detail="Имя провайдера не может быть пустым")

            normalized_model, provider = _normalize_model_and_provider(req.model, target_provider)
            user_identifier, _, _, _ = await _extract_user_auth(fastapi_req)

            # 1. Обновление состояния базового chat_model
            active_chat_ref = getattr(getattr(fastapi_req, "app", None), "state", None)
            target_chat_model = getattr(active_chat_ref, "chat_model", None) if active_chat_ref else None
            if not target_chat_model:
                target_chat_model = chat_model
            if target_chat_model:
                if hasattr(target_chat_model, "_model_name"):
                    target_chat_model._model_name = normalized_model
                if hasattr(target_chat_model, "model_name"):
                    target_chat_model.model_name = normalized_model

            # 3. Сохраняем в apps/windows/config.json
            save_ai_config(provider=provider, model_name=normalized_model)

            return {
                "status": "success",
                "message": "Провайдер успешно обновлен",
                "provider": provider,
                "model": normalized_model,
            }
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"[router_chat] Ошибка при установке провайдера: {exc}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(exc))

    @router.get('/model-instruction')
    async def get_model_instruction(fastapi_req: Request, model: str = "") -> dict:
        """Получение текущей системной инструкции для AI-модели или чата."""
        try:
            user_identifier, system_instruction, selected_model, settings = await _extract_user_auth(fastapi_req)
            effective_model = model.strip() or selected_model or ""
            provider, resolved_model, config_file = _resolve_default_model_and_provider()

            if not effective_model:
                effective_model = resolved_model

            source = "user_settings" if (settings and settings.get("system_instruction")) else "file_default"

            return {
                "status": "success",
                "instruction": system_instruction,
                "system_instruction": system_instruction,
                "model": effective_model,
                "provider": provider,
                "source": source,
            }
        except Exception as exc:
            logger.error(f"[router_chat] Ошибка при получении системной инструкции: {exc}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(exc))

    @router.post('/model-instruction')
    @router.put('/model-instruction')
    async def set_model_instruction(req: ModelInstructionPayload, fastapi_req: Request) -> dict:
        """Установка и сохранение системной инструкции для AI-модели или чата."""
        try:
            raw_instruction = req.instruction.strip() or req.system_instruction.strip() or req.content.strip()
            if not raw_instruction:
                raise HTTPException(status_code=400, detail="Инструкция не может быть пустой")

            user_identifier, _, selected_model, _ = await _extract_user_auth(fastapi_req)

            # 1. Обновляем базовый chat_model (из app.state или переданный при инициализации)
            active_chat_ref = getattr(getattr(fastapi_req, "app", None), "state", None)
            target_chat_model = getattr(active_chat_ref, "chat_model", None) if active_chat_ref else None
            if not target_chat_model:
                target_chat_model = chat_model

            if target_chat_model and hasattr(target_chat_model, "update_system_instruction"):
                try:
                    target_chat_model.update_system_instruction(raw_instruction)
                except Exception as e:
                    logger.debug(f"[router_chat] Не удалось обновить chat_model system_instruction: {e}")

            # 3. Обновляем все кэшированные инстансы _active_chat_models
            for cached_instance in _active_chat_models.values():
                if hasattr(cached_instance, "system_instruction"):
                    setattr(cached_instance, "system_instruction", raw_instruction)
                elif hasattr(cached_instance, "system_prompt"):
                    setattr(cached_instance, "system_prompt", raw_instruction)

            # 4. Сохранение на диск в файл apps/windows/prompts/chat/system_instruction.md по запросу
            if req.save_to_disk:
                prompt_file = __root__ / 'apps' / 'windows' / 'prompts' / 'chat' / 'system_instruction.md'
                prompt_file.parent.mkdir(parents=True, exist_ok=True)
                prompt_file.write_text(raw_instruction, encoding='utf-8')

            return {
                "status": "success",
                "message": "Системная инструкция успешно обновлена",
                "instruction": raw_instruction,
                "system_instruction": raw_instruction,
                "model": req.model or selected_model or "",
            }
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"[router_chat] Ошибка при сохранении системной инструкции: {exc}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(exc))

    @router.post('/test-model')
    async def test_model(req: TestModelRequest, fastapi_req: Request) -> dict:
        """Проверочный запрос к указанной AI-модели для валидации связи (Запрос -> Ответ).
        
        Введите вручную имя модели и провайдера, иначе будет использована настройка по умолчанию.
        """
        start_time = time.perf_counter()
        target_model = req.model.strip()
        provider = req.provider.strip().lower()

        # Если модель или провайдер не указаны вручную, используем настройку по умолчанию
        if not target_model or not provider:
            def_provider, def_model, _ = await _get_effective_model_and_provider(fastapi_req)
            if not target_model and not provider:
                target_model = def_model
                provider = def_provider.lower()
            elif not target_model:
                if provider == def_provider.lower() and def_model:
                    target_model = def_model
                elif provider == 'gemini':
                    target_model = 'gemini-3.1-flash'
                elif provider == 'agy':
                    target_model = 'gemini-3.6-flash'
                elif provider == 'ollama':
                    target_model = 'llama3.1'
                elif provider == 'foundry':
                    target_model = 'local'
                else:
                    target_model = def_model
            elif not provider:
                if target_model.startswith('foundry:'):
                    provider = 'foundry'
                elif target_model.startswith('ollama:'):
                    provider = 'ollama'
                elif target_model.startswith('agy-'):
                    provider = 'agy'
                elif target_model.startswith('gemini_cli:'):
                    provider = 'gemini_cli'
                elif target_model.startswith('hf:') or target_model.startswith('hf::'):
                    provider = 'hf'
                elif target_model.startswith('onnx:') or target_model.startswith('onnx::'):
                    provider = 'onnx'
                elif any(target_model.startswith(p) for p in ('openai:', 'deepseek:', 'groq:', 'openrouter:', 'lmstudio:', 'local:', 'compat:')):
                    provider = 'openai'
                elif 'gemini' in target_model.lower():
                    provider = 'gemini'
                else:
                    provider = def_provider.lower()

        if provider == 'foundry' and target_model and not target_model.startswith('foundry:'):
            target_model = f"foundry:{target_model}"
        elif provider == 'ollama' and target_model and not target_model.startswith('ollama:'):
            target_model = f"ollama:{target_model}"
        elif provider == 'agy' and target_model and not target_model.startswith('agy-'):
            target_model = f"agy-{target_model}"
        elif provider in ('gemini_cli', 'gemini-cli') and target_model and not target_model.startswith('gemini_cli:'):
            target_model = f"gemini_cli:{target_model}"
        elif provider in ('openai', 'openai_compat', 'openai-compat', 'deepseek', 'groq', 'openrouter', 'lmstudio') and target_model:
            openai_prefixes = ('openai:', 'deepseek:', 'groq:', 'openrouter:', 'lmstudio:', 'local:', 'compat:')
            if not any(target_model.startswith(p) for p in openai_prefixes):
                target_model = f"{provider}:{target_model}"
        elif provider in ('hf', 'huggingface') and target_model and not target_model.startswith('hf:'):
            target_model = f"hf:{target_model}"
        elif provider == 'onnx' and target_model and not target_model.startswith('onnx:'):
            target_model = f"onnx:{target_model}"

        if not target_model:
            return {
                'status': 'error',
                'message': 'Имя модели не указано',
                'model': '',
                'provider': provider,
                'duration_ms': 0.0
            }

        test_msg = req.message.strip()
        if not test_msg:
            test_msg = "Привет! Назови свою модель и провайдера, и подтверди готовность к работе."

        try:
            model_instance = get_chat_model(target_model, system_instruction=req.system_instruction)
            response_text = ""

            if hasattr(model_instance, 'ask'):
                response_text = await model_instance.ask(test_msg)
            elif hasattr(model_instance, 'chat'):
                response_text = await model_instance.chat(test_msg)
            elif hasattr(model_instance, 'chat_stream'):
                chunks = []
                async for chunk in model_instance.chat_stream(test_msg):
                    if chunk:
                        clean_chunk = chunk.replace("[CHAT]", "").replace("[VOICE]", "")
                        if clean_chunk:
                            chunks.append(clean_chunk)
                response_text = "".join(chunks)
            else:
                raise RuntimeError(f"Модель {target_model} не поддерживает методы генерации текста")

            duration_ms = round((time.perf_counter() - start_time) * 1000, 1)
            return {
                'status': 'success',
                'response': response_text,
                'model': target_model,
                'provider': provider,
                'duration_ms': duration_ms
            }
        except Exception as exc:
            logger.error(f"[ChatRouter] Error проверочного запроса к модели {target_model}: {exc}", exc_info=True)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 1)
            return {
                'status': 'error',
                'message': str(exc),
                'model': target_model,
                'provider': provider,
                'duration_ms': duration_ms
            }

    @router.get('/model-errors')
    async def get_model_errors_endpoint(provider: str = "", limit: int = 50) -> dict:
        """Получить список последних зафиксированных ошибок AI-моделей.

        :param provider: Опциональный фильтр по провайдеру (gemini, agy, foundry, ollama и т.д.).
        :param limit: Количество записей.
        :returns: JSON-ответ со списком событий ошибок.
        """
        from src.ai.orchestration.model_error_hub import get_model_errors
        events = get_model_errors(provider=provider or None, limit=limit)
        return {
            'status': 'success',
            'errors': [evt.model_dump() for evt in events],
            'count': len(events),
        }

    @router.get('/model-health')
    async def get_model_health_endpoint() -> dict:
        """Получить сводную статистику здоровья и доступности AI-моделей.

        :returns: Агрегированная сводка по ошибкам и провайдерам.
        """
        from src.ai.orchestration.model_error_hub import get_model_health_summary
        summary = get_model_health_summary()
        return {
            'status': 'success',
            'health': summary,
        }

