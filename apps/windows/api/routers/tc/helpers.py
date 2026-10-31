# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - helpers
# =============================================================================
# Description:
#   Вспомогательные функции TC: конфиг, модель и провайдер, авторизация.
#   Вынесено из router_tc.py (этап 4 оптимизации).
#
# File: helpers.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers.tc
# Author: hypo69
# Copyright: c 2026 hypo69
# Updated: 2026-10-30 13:25:00
# =============================================================================

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import (
    Any,
    Dict,
    Optional,
    Tuple,
)

from fastapi import Request

from header import __root__
from logger import logger
from apps.windows.api.config_helper import save_ai_config


# -----------------------------------------------------------------------------
# Вспомогательные функции
# -----------------------------------------------------------------------------

def _find_tc_config_path() -> Optional[Path]:
    """Находит актуальный путь к файлу конфигурации Test Computer.

    Returns:
        Optional[Path]: Путь к найденному файлу конфигурации или None.
    """
    cfg_env = os.getenv("AIWINDOWSADMIN_CONFIG") or os.getenv("CONFIG_FILE")
    if cfg_env:
        p = Path(cfg_env)
        active_p = p if p.is_absolute() else (__root__ / cfg_env)
        if active_p.exists():
            return active_p

    candidates = [
        __root__ / "apps" / "windows" / "config.json",
        __root__ / "config_tc.json",
        __root__ / "tc.json",
    ]
    for p in candidates:
        if p.exists():
            return p
    return candidates[0]


def _get_tc_default_instruction() -> str:
    """Загружает системную инструкцию по умолчанию для Test Computer.

    Returns:
        str: Текст системной инструкции.
    """
    tc_prompt_file = __root__ / "apps" / "windows" / "prompts" / "tc" / "system_instruction.md"
    if tc_prompt_file.exists():
        try:
            content = tc_prompt_file.read_text(encoding="utf-8", errors="replace").strip()
            if content:
                return content
        except Exception as e:
            logger.debug(f"[router_tc] Ошибка чтения apps/windows/prompts/tc/system_instruction.md: {e}")

    chat_prompt_file = __root__ / "apps" / "windows" / "prompts" / "chat" / "system_instruction.md"
    if chat_prompt_file.exists():
        try:
            content = chat_prompt_file.read_text(encoding="utf-8", errors="replace").strip()
            if content:
                return content
        except Exception as e:
            logger.debug(f"[router_tc] Ошибка чтения apps/windows/prompts/chat/system_instruction.md: {e}")

    return "Ты — автономный сервисный инженер и диагност операционной системы Windows платформы AI Windows Admin Test Computer."


def _resolve_tc_model_and_provider() -> Tuple[str, str, str]:
    """Считывает провайдер и модель по умолчанию из профиля Test Computer (tc.json).

    Returns:
        Tuple[str, str, str]: (provider, model_name, config_filename)
    """
    cfg_path = _find_tc_config_path()
    provider = "GEMINI_CLI"
    model_name = "gemini-3.1-flash-lite"
    config_file = cfg_path.name if cfg_path else "tc.json"

    if cfg_path and cfg_path.exists():
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                ai_sec = data.get("ai_providers_and_models_configuration") or data.get("ai") or {}
                if ai_sec.get("default_provider"):
                    provider = str(ai_sec.get("default_provider")).upper()
                if ai_sec.get("default_model"):
                    model_name = str(ai_sec.get("default_model")).strip()

                if not model_name:
                    if ai_sec.get("provider"):
                        prov_key = str(ai_sec.get("provider")).lower()
                        provider = prov_key.upper()
                        if isinstance(ai_sec.get(prov_key), dict) and ai_sec[prov_key].get("model"):
                            model_name = ai_sec[prov_key].get("model")
                        elif isinstance(ai_sec.get("providers"), dict) and isinstance(ai_sec["providers"].get(prov_key), dict) and ai_sec["providers"][prov_key].get("model"):
                            model_name = ai_sec["providers"][prov_key].get("model")
                        elif ai_sec.get("model"):
                            model_name = ai_sec.get("model")
                    elif isinstance(ai_sec.get("providers"), dict):
                        prov_dict = ai_sec.get("providers", {})
                        for prov_key, prov_cfg in prov_dict.items():
                            if isinstance(prov_cfg, dict) and prov_cfg.get("enabled"):
                                provider = prov_key.upper()
                                model_name = prov_cfg.get("model") or ""
                                break
                    elif ai_sec.get("model"):
                        model_name = ai_sec.get("model")
        except Exception as e:
            logger.debug(f"[router_tc] Ошибка чтения конфигурации TC {cfg_path}: {e}")

    return provider, model_name, config_file


def _normalize_tc_model_and_provider(target_model: str = "", target_provider: str = "") -> Tuple[str, str]:
    """Нормализует имя модели и провайдера для профиля Test Computer.

    Args:
        target_model: Имя модели.
        target_provider: Имя провайдера.

    Returns:
        Tuple[str, str]: (normalized_model, normalized_provider_upper)
    """
    model = (target_model or "").strip()
    provider = (target_provider or "").strip().lower()

    if not provider:
        if model.startswith("foundry:"):
            provider = "foundry"
        elif model.startswith("ollama:"):
            provider = "ollama"
        elif model.startswith("agy-") or "agy" in model.lower():
            provider = "agy"
        elif model.startswith("gemini_cli:") or model.startswith("gemini-cli-"):
            provider = "gemini_cli"
        elif model.startswith("hf:") or model.startswith("hf::"):
            provider = "hf"
        elif model.startswith("onnx:") or model.startswith("onnx::"):
            provider = "onnx"
        elif any(model.startswith(p) for p in ("openai:", "deepseek:", "groq:", "openrouter:", "lmstudio:", "local:", "compat:")):
            provider = "openai"
        elif "gemini" in model.lower():
            provider = "gemini"
        else:
            provider = "gemini_cli"

    if not model:
        if provider in ("gemini_cli", "gemini-cli"):
            model = "gemini-3.1-flash-lite"
        elif provider == "gemini":
            model = "gemini-3.1-flash"
        elif provider == "agy":
            model = "gemini-3.6-flash"
        elif provider == "ollama":
            model = "llama3.1"
        elif provider == "foundry":
            model = "local"
        elif provider in ("openai", "openai_compat", "deepseek", "groq", "openrouter", "lmstudio"):
            model = "gpt-4o-mini"
        elif provider in ("hf", "huggingface"):
            model = "microsoft/Phi-3-mini-4k-instruct"
        elif provider == "onnx":
            model = "cpu-int4-rt"
        else:
            model = "gemini-3.1-flash-lite"

    return model, provider.upper()


def _save_tc_config_ai(provider: str, model_name: str) -> bool:
    """Сохраняет активный AI-провайдер и модель в конфигурационный файл apps/windows/config.json.

    Args:
        provider: Имя провайдера (GEMINI_CLI, GEMINI, AGY, OLLAMA и др.).
        model_name: Имя модели.

    Returns:
        bool: True если сохранение прошло успешно.
    """
    cfg_path = _find_tc_config_path()
    return save_ai_config(provider=provider, model_name=model_name, config_path=cfg_path)


async def _extract_tc_user_auth(fastapi_req: Request) -> Tuple[str, str, str, dict]:
    """Извлекает параметры сессии и настройки для профиля Test Computer."""
    user_identifier = "1"
    system_instruction = _get_tc_default_instruction()
    selected_model = ""
    settings: Dict[str, Any] = {}
    return user_identifier, system_instruction, selected_model, settings

