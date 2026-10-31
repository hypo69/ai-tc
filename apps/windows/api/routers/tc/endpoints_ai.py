# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - endpoints_ai
# =============================================================================
# Description:
#   Эндпойнты инструкции, модели и провайдера AI-агента TC.
#   Вынесено из router_tc.py (этап 4 оптимизации).
#
# File: endpoints_ai.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers.tc
# Author: hypo69
# Copyright: c 2026 hypo69
# Updated: 2026-10-30 13:25:00
# =============================================================================

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Request

from header import __root__
from logger import logger
from .helpers import _extract_tc_user_auth
from .helpers import _normalize_tc_model_and_provider
from .helpers import _resolve_tc_model_and_provider
from .helpers import _save_tc_config_ai
from .models import TcModelInstructionPayload
from .models import TcSetModelPayload
from .models import TcSetProviderPayload


def register_ai_endpoints(router: APIRouter) -> None:
    """Регистрирует эндпойнты AI-агента TC на роутере."""
    # =========================================================================
    # 1. Системная инструкция: /api/v1/tc/model-instruction (GET / POST / PUT)
    # =========================================================================

    @router.get("/model-instruction")
    async def get_tc_model_instruction(fastapi_req: Request, model: str = "") -> dict:
        """Получение текущей системной инструкции AI-модели для Test Computer."""
        try:
            user_identifier, system_instruction, selected_model, settings = await _extract_tc_user_auth(fastapi_req)
            provider, default_model, config_file = _resolve_tc_model_and_provider()
            effective_model = model.strip() or selected_model or default_model

            source = "user_settings" if (settings and (settings.get("tc_system_instruction") or settings.get("system_instruction"))) else "file_default"

            return {
                "status": "success",
                "instruction": system_instruction,
                "system_instruction": system_instruction,
                "model": effective_model,
                "provider": provider,
                "source": source,
                "config_file": config_file,
            }
        except Exception as exc:
            logger.error(f"[router_tc] Ошибка при получении системной инструкции TC: {exc}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(exc))

    @router.post("/model-instruction")
    @router.put("/model-instruction")
    async def set_tc_model_instruction(req: TcModelInstructionPayload, fastapi_req: Request) -> dict:
        """Установка и сохранение системной инструкции AI-модели для Test Computer."""
        try:
            raw_instruction = req.instruction.strip() or req.system_instruction.strip() or req.content.strip()
            if not raw_instruction:
                raise HTTPException(status_code=400, detail="Инструкция не может быть пустой")

            user_identifier, _, selected_model, _ = await _extract_tc_user_auth(fastapi_req)

            # 1. Сохранение на диск по требованию (apps/windows/prompts/tc/system_instruction.md)
            if req.save_to_disk:
                tc_prompt_file = __root__ / "apps" / "windows" / "prompts" / "tc" / "system_instruction.md"
                tc_prompt_file.parent.mkdir(parents=True, exist_ok=True)
                tc_prompt_file.write_text(raw_instruction, encoding="utf-8")

            return {
                "status": "success",
                "message": "Системная инструкция для Test Computer успешно обновлена",
                "instruction": raw_instruction,
                "system_instruction": raw_instruction,
                "model": req.model or selected_model or "",
            }
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"[router_tc] Ошибка при сохранении системной инструкции TC: {exc}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(exc))

    # =========================================================================
    # 2. Модель: /api/v1/tc/model (GET / POST / PUT)
    # =========================================================================

    @router.get("/model")
    async def get_tc_model(fastapi_req: Request) -> dict:
        """Получение текущей активной AI-модели Test Computer."""
        try:
            _, _, user_selected_model, _ = await _extract_tc_user_auth(fastapi_req)
            provider, default_model, config_file = _resolve_tc_model_and_provider()
            effective_model = user_selected_model or default_model

            return {
                "status": "success",
                "model": effective_model,
                "provider": provider,
                "display": f"{provider}: {effective_model}",
                "config_file": config_file,
            }
        except Exception as exc:
            logger.error(f"[router_tc] Ошибка при получении модели TC: {exc}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(exc))

    @router.post("/model")
    @router.put("/model")
    async def set_tc_model(req: TcSetModelPayload, fastapi_req: Request) -> dict:
        """Установка активной AI-модели Test Computer."""
        try:
            target_model = req.model.strip()
            if not target_model:
                raise HTTPException(status_code=400, detail="Имя модели не может быть пустым")

            normalized_model, provider = _normalize_tc_model_and_provider(target_model, req.provider)
            user_identifier, _, _, _ = await _extract_tc_user_auth(fastapi_req)

            # 1. Обновляем конфигурационный файл tc.json
            if req.save_to_config:
                _save_tc_config_ai(provider, normalized_model)

            return {
                "status": "success",
                "message": "Модель Test Computer успешно обновлена",
                "model": normalized_model,
                "provider": provider,
            }
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"[router_tc] Ошибка при установке модели TC: {exc}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(exc))

    # =========================================================================
    # 3. Провайдер: /api/v1/tc/provider (GET / POST / PUT)
    # =========================================================================

    @router.get("/provider")
    async def get_tc_model_provider(fastapi_req: Request) -> dict:
        """Получение текущего активного AI-провайдера Test Computer."""
        try:
            _, _, user_selected_model, _ = await _extract_tc_user_auth(fastapi_req)
            provider, default_model, config_file = _resolve_tc_model_and_provider()
            effective_model = user_selected_model or default_model

            return {
                "status": "success",
                "provider": provider,
                "model": effective_model,
                "display": f"{provider}: {effective_model}",
                "config_file": config_file,
            }
        except Exception as exc:
            logger.error(f"[router_tc] Ошибка при получении провайдера TC: {exc}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(exc))

    @router.post("/provider")
    @router.put("/provider")
    async def set_tc_model_provider(req: TcSetProviderPayload, fastapi_req: Request) -> dict:
        """Установка активного AI-провайдера Test Computer."""
        try:
            target_provider = req.provider.strip()
            if not target_provider:
                raise HTTPException(status_code=400, detail="Имя провайдера не может быть пустым")

            normalized_model, provider = _normalize_tc_model_and_provider(req.model, target_provider)
            user_identifier, _, _, _ = await _extract_tc_user_auth(fastapi_req)

            # 1. Обновляем конфигурационный файл tc.json
            if req.save_to_config:
                _save_tc_config_ai(provider, normalized_model)

            return {
                "status": "success",
                "message": "Провайдер Test Computer успешно обновлен",
                "provider": provider,
                "model": normalized_model,
            }
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"[router_tc] Ошибка при установке провайдера TC: {exc}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(exc))

