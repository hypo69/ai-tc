# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - helpers
# =============================================================================
# Description:
#   Вспомогательные функции чата: выбор модели, очистка истории, нормализация.
#   Вынесено из router_chat.py (этап 4 оптимизации).
#
# File: helpers.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers.chat
# Author: hypo69
# Copyright: c 2026 hypo69
# Updated: 2026-10-30 13:25:00
# =============================================================================

from __future__ import annotations

import os
import asyncio
from fastapi import Request

from logger import logger
from src.config import ai_cfg, tts_cfg

from header import __root__
from .models import ChatRequest


# Короткие слова-продолжения диалога, которые сами по себе не содержат медиа-ключевых слов
_CONTEXT_CONTINUATION_WORDS = {
    'да', 'нет', 'yes', 'no', 'ок', 'ok', 'хочу', 'конечно',
    'давай', 'проверь', 'найди', 'покажи', 'ладно', 'угу', 'yep', 'sure',
    'want', 'check', 'find', 'show', 'okay',
}


_active_chat_models: dict[str, object] = {}


def _get_default_system_instruction() -> str:
    """Load default system instruction for chat assistant."""
    prompt_file = __root__ / 'apps' / 'windows' / 'prompts' / 'chat' / 'system_instruction.md'
    if prompt_file.exists():
        try:
            content = prompt_file.read_text(encoding='utf-8', errors='replace').strip()
            if content:
                return content
        except Exception as e:
            logger.debug(f"[router_chat] Could not read default prompt file: {e}")
    return "Вы — интеллектуальный ассистент платформы AI Windows Admin с доступом к Google Workspace и RAG-базе знаний."

def get_chat_model(selected_model_name: str, system_instruction: str = "", user_id: str = ""):
    """Dynamically construct or retrieve cached AI model instance."""
    eff_sys_prompt = system_instruction.strip() if system_instruction and system_instruction.strip() else _get_default_system_instruction()
    cache_key = f"{user_id}:{selected_model_name}" if user_id else selected_model_name
    if cache_key in _active_chat_models:
        instance = _active_chat_models[cache_key]
        if eff_sys_prompt and hasattr(instance, 'system_instruction'):
            if getattr(instance, 'system_instruction', None) != eff_sys_prompt:
                instance.system_instruction = eff_sys_prompt
        return instance

    is_gemini_cli = selected_model_name.startswith('gemini_cli:') or selected_model_name.startswith('gemini-cli-')
    is_foundry = selected_model_name.startswith('foundry:')
    is_ollama = selected_model_name.startswith('ollama:')
    is_hf = selected_model_name.startswith('hf:') or selected_model_name.startswith('hf::')
    is_onnx = selected_model_name.startswith('onnx:') or selected_model_name.startswith('onnx::')
    openai_prefixes = ('openai:', 'openai::', 'deepseek:', 'groq:', 'openrouter:', 'lmstudio:', 'local:', 'compat:')
    is_openai = any(selected_model_name.startswith(p) for p in openai_prefixes)
    is_agy = selected_model_name.startswith('agy-') or 'agy' in selected_model_name.lower()
    is_gemini = not is_gemini_cli and not is_hf and not is_onnx and not is_openai and (selected_model_name.startswith('gemini-') or 'gemini' in selected_model_name.lower())

    if is_gemini_cli:
        from src.ai.gemini_cli_chat import GeminiCliChatBase
        inst = GeminiCliChatBase(
            model_id=selected_model_name,
            system_prompt=eff_sys_prompt,
        )
    elif is_foundry:
        model_id = selected_model_name.split(':', 1)[-1]
        from src.ai.providers.foundry import FoundryChatBase
        inst = FoundryChatBase(
            model_id=model_id,
            system_prompt=eff_sys_prompt,
        )
    elif is_ollama:
        model_id = selected_model_name.split(':', 1)[-1]
        from src.ai.providers.ollama import OllamaChatBase
        ollama_url = ai_cfg.ollama_base_url if ai_cfg else 'http://localhost:11434'
        inst = OllamaChatBase(
            model_id=model_id,
            system_prompt=eff_sys_prompt,
            api_url=ollama_url
        )
    elif is_hf:
        model_id = selected_model_name.split(':', 1)[-1].lstrip(':')
        from src.ai.hf_chat import HFChatBase
        inst = HFChatBase(
            model_id=model_id,
            system_prompt=eff_sys_prompt,
        )
    elif is_onnx:
        model_id = selected_model_name.split(':', 1)[-1].lstrip(':')
        from src.ai.providers.onnx import ONNXChatBase
        inst = ONNXChatBase(
            model_id=model_id,
            system_prompt=eff_sys_prompt,
        )
    elif is_openai:
        prov_part, model_part = selected_model_name.split(':', 1)
        model_id = model_part.lstrip(':')
        prov_name = prov_part.lower().rstrip(':')
        if prov_name == 'compat':
            prov_name = 'openai'
        from src.ai.providers.openai import OpenAICompatChat
        inst = OpenAICompatChat.create_for_provider(
            provider_name=prov_name,
            model_id=model_id,
            system_prompt=eff_sys_prompt,
        )
    elif is_agy:
        from src.ai.providers.agy import AgyChatBase
        inst = AgyChatBase(
            model_id=selected_model_name,
            system_prompt=eff_sys_prompt,
        )
    elif is_gemini:
        from src.ai.providers.gemini import GeminiChatBase
        inst = GeminiChatBase(
            model_id=selected_model_name,
            system_prompt=eff_sys_prompt,
        )
    else:
        from src.ai.providers.foundry import FoundryChatBase
        inst = FoundryChatBase(
            model_id=selected_model_name,
            system_prompt=eff_sys_prompt,
        )

    _active_chat_models[cache_key] = inst
    return inst

async def _extract_user_auth(fastapi_req: Request) -> tuple[str, str, str, dict]:
    """Извлекает идентификатор сессии, системную инструкцию, модель и настройки."""
    user_identifier = "1"
    system_instruction = _get_default_system_instruction()
    selected_model = ""
    settings = {}
    return user_identifier, system_instruction, selected_model, settings

def _get_voice_gender_rule(settings: dict) -> str:
    """Определяет гендерное правило для ответов ассистента на основе настроек голоса TTS."""
    default_voice = getattr(tts_cfg, "default_voice", "ru-RU-DmitryNeural") if tts_cfg else "ru-RU-DmitryNeural"
    tts_voice = settings.get('tts_voice', '') or default_voice
    voice_lower = tts_voice.lower()
    is_male_voice = any(name in voice_lower for name in ("dmitry", "yaraslaus", "male", "bayan", "aidar", "eugene", "georgy"))
    is_female_voice = any(name in voice_lower for name in ("svetlana", "elena", "female", "kseniya", "tanya", "aliona", "dariya"))
    if is_male_voice:
        return "ВАЖНОЕ ПРАВИЛО: Отвечай от мужского лица (например: 'Я нашел', 'Я подобрал')."
    if is_female_voice:
        return "ВАЖНОЕ ПРАВИЛО: Отвечай от женского лица (например: 'Я нашла', 'Я подобрала')."
    return ""

def _clean_chat_history(history: list[dict]) -> list[dict]:
    """Очищает историю сообщений перед передачей в модель."""
    if not history:
        return []
    _ERROR_PATTERNS = (
        '❌', 'Error', 'Error', 'TypeError', 'AttributeError', 'Traceback',
        '[Error]', 'Не удалось найти', 'В локальной базе ничего не найдено',
        'DEBUG MODE', 'DEBUG:', '[DEBUG'
    )
    _STATUS_PREFIXES = (
        '🔍', '🌐', '🤖', '🛠️', '🎡', '📡', 'Вызов плагина', 'Генерация', 'Check',
        'DEBUG MODE:', 'DEBUG:'
    )

    def _is_clean(entry: dict) -> bool:
        parts = entry.get('parts', [])
        text = ''
        if isinstance(parts, list) and len(parts) > 0:
            p = parts[0]
            text = p if isinstance(p, str) else p.get('text', '') if isinstance(p, dict) else ''
        elif isinstance(parts, str):
            text = parts
        text = (text or '').strip()
        if not text:
            return False
        if any(pfx in text for pfx in _ERROR_PATTERNS):
            return False
        if any(text.startswith(pfx) for pfx in _STATUS_PREFIXES):
            return False
        if text.startswith('{') and ('"title"' in text or '"error"' in text or '"genres"' in text):
            return False
        if 'Ответ модели: {' in text and '"title"' in text:
            return False
        return True

    def _compact_turn(entry: dict) -> dict:
        parts = entry.get('parts', [])
        text = ''
        if isinstance(parts, list) and len(parts) > 0:
            p = parts[0]
            text = p if isinstance(p, str) else p.get('text', '') if isinstance(p, dict) else ''
        elif isinstance(parts, str):
            text = parts

        if entry.get('role') in ('model', 'assistant') and len(text) > 200:
            import re
            compact = re.sub(r'<film>(.*?)</film>', r'«\1»', text, flags=re.IGNORECASE)
            compact = re.sub(r'#+\s*', '', compact)
            compact = re.sub(r'[*_`]+', '', compact)
            compact = re.sub(r'\s+', ' ', compact).strip()
            if len(compact) > 200:
                compact = compact[:197].rsplit(' ', 1)[0] + '...'
            return {'role': entry['role'], 'parts': [compact]}
        return entry

    raw_clean = [e for e in history if _is_clean(e)]
    cleaned_entries: list[dict] = []
    i = 0
    while i < len(raw_clean):
        entry = raw_clean[i]
        if entry.get('role') == 'user':
            if i + 1 < len(raw_clean) and raw_clean[i + 1].get('role') in ('model', 'assistant'):
                cleaned_entries.append(_compact_turn(entry))
                cleaned_entries.append(_compact_turn(raw_clean[i + 1]))
                i += 2
                continue
        i += 1

    return cleaned_entries[-10:]

def _build_debug_prompt(request: ChatRequest, user_context_str: str, voice_gender_rule: str) -> str:
    """Формирует текстовый дамп полного промпта для отладочного режима."""
    full_prompt_parts = []
    dynamic_parts = []
    if voice_gender_rule:
        dynamic_parts.append(voice_gender_rule)
    if user_context_str:
        dynamic_parts.append(user_context_str)
    if dynamic_parts:
        full_prompt_parts.append("── DYNAMIC CONTEXT ──\n" + "\n\n".join(dynamic_parts))

    clean_history = _clean_chat_history(request.history)
    if clean_history:
        full_prompt_parts.append("── CHAT HISTORY (последние 5) ──\n" + "\n---\n".join([
            f"{entry.get('role', 'unknown').upper()}:\n{entry.get('parts', [''])[0] if isinstance(entry.get('parts'), list) else entry.get('parts', '')}"
            for entry in clean_history[-5:]
        ]))

    full_prompt_parts.append(f"── USER MESSAGE ──\n{request.message}")
    return "\n\n".join(full_prompt_parts)

def _resolve_default_model_and_provider(profile: str = "") -> tuple[str, str, str]:
    """Определяет провайдер и имя модели по умолчанию из активного конфигурационного файла.

    :param profile: Опциональное имя профиля конфигурации.
    :returns: Кортеж (provider, model_name, config_file).
    """
    import json
    from pathlib import Path

    cfg_env = os.getenv("AIWINDOWSADMIN_CONFIG") or os.getenv("CONFIG_FILE")
    active_path = None
    if cfg_env:
        p = Path(cfg_env)
        active_path = p if p.is_absolute() else (__root__ / cfg_env)

    if not active_path or not active_path.exists():
        if profile in ("tc", "test-computer", "test_computer", "apps_tc"):
            for candidate in [
                __root__ / "apps" / "windows" / "config.json",
                __root__ / "config_tc.json",
                __root__ / "tc.json",
            ]:
                if candidate.exists():
                    active_path = candidate
                    break
        else:
            for candidate in [
                __root__ / "apps" / "windows" / "config.json",
                __root__ / "config_tc.json",
                __root__ / "tc.json",
            ]:
                if candidate.exists() and not (__root__ / "config.json").exists():
                    active_path = candidate
                    break

        if not active_path or not active_path.exists():
            active_path = __root__ / "config.json"

    provider = "GEMINI"
    model_name = ""
    config_file = active_path.name if active_path else "config.json"

    if active_path and active_path.exists():
        try:
            with open(active_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                ai_sec = data.get("ai_providers_and_models_configuration") or data.get("ai") or {}
                
                # 1. Проверяем явные default_provider и default_model
                if ai_sec.get("default_provider"):
                    provider = str(ai_sec.get("default_provider")).upper()
                if ai_sec.get("default_model"):
                    model_name = str(ai_sec.get("default_model")).strip()

                # 2. Если модель не найдена, проверяем секции provider/providers
                if not model_name:
                    if ai_sec.get("provider"):
                        prov_key = str(ai_sec.get("provider")).lower()
                        provider = prov_key.upper()
                        if isinstance(ai_sec.get(prov_key), dict) and ai_sec[prov_key].get("model"):
                            model_name = ai_sec[prov_key].get("model")
                        elif isinstance(ai_sec.get("providers"), dict) and isinstance(ai_sec["providers"].get(prov_key), dict) and ai_sec["providers"][prov_key].get("model"):
                            model_name = ai_sec["providers"][prov_key].get("model")
                        elif ai_sec.get(f"{prov_key}_model_id"):
                            model_name = ai_sec.get(f"{prov_key}_model_id")
                        elif ai_sec.get("model"):
                            model_name = ai_sec.get("model")
                    elif isinstance(ai_sec.get("providers"), dict):
                        providers = ai_sec.get("providers", {})
                        for prov_key, prov_cfg in providers.items():
                            if isinstance(prov_cfg, dict) and prov_cfg.get("enabled"):
                                provider = prov_key.upper()
                                model_name = prov_cfg.get("model") or model_name
                                break
                    elif ai_sec.get("use_agy"):
                        provider = "AGY"
                        model_name = ai_sec.get("agy_model_id") or ai_sec.get("model") or ""
                    elif ai_sec.get("use_gemini"):
                        provider = "GEMINI"
                        model_name = ai_sec.get("gemini_model_id") or ai_sec.get("model") or ""
                    elif ai_sec.get("use_ollama"):
                        provider = "OLLAMA"
                        model_name = ai_sec.get("ollama_model_id") or ai_sec.get("model") or ""
                    elif ai_sec.get("use_foundry"):
                        provider = "FOUNDRY"
                        model_name = ai_sec.get("foundry_model_id") or ai_sec.get("model") or ""
                    elif ai_sec.get("model"):
                        model_name = ai_sec.get("model")
                        provider = "AI"
        except Exception as e:
            logger.debug(f"[router_chat] Could not read active config {active_path}: {e}")

    return provider, model_name, config_file

async def _get_effective_model_and_provider(fastapi_req: Request = None, profile: str = "") -> tuple[str, str, str]:
    """Получает эффективный провайдер и модель с учетом активной конфигурации и настроек текущего пользователя."""
    provider, model_name, config_file = _resolve_default_model_and_provider(profile=profile)
    if fastapi_req is not None:
        try:
            _, _, user_selected_model, _ = await _extract_user_auth(fastapi_req)
            if user_selected_model:
                if ':' in user_selected_model:
                    p_prefix, m_suffix = user_selected_model.split(':', 1)
                    provider = p_prefix.upper()
                    model_name = m_suffix
                elif user_selected_model.startswith('agy-'):
                    provider = "AGY"
                    model_name = user_selected_model
                elif 'gemini' in user_selected_model.lower():
                    provider = "GEMINI"
                    model_name = user_selected_model
                else:
                    model_name = user_selected_model
        except Exception:
            pass
    return provider, model_name, config_file

def _normalize_model_and_provider(target_model: str = "", target_provider: str = "") -> tuple[str, str]:
    """Нормализует имя модели и провайдера, разрешая значения по умолчанию и форматируя префиксы."""
    model = (target_model or "").strip()
    provider = (target_provider or "").strip().lower()

    if not provider:
        if model.startswith('foundry:'):
            provider = 'foundry'
        elif model.startswith('ollama:'):
            provider = 'ollama'
        elif model.startswith('agy-'):
            provider = 'agy'
        elif model.startswith('gemini_cli:'):
            provider = 'gemini_cli'
        elif model.startswith('hf:') or model.startswith('hf::'):
            provider = 'hf'
        elif model.startswith('onnx:') or model.startswith('onnx::'):
            provider = 'onnx'
        elif any(model.startswith(p) for p in ('openai:', 'deepseek:', 'groq:', 'openrouter:', 'lmstudio:', 'local:', 'compat:')):
            provider = 'openai'
        elif 'gemini' in model.lower():
            provider = 'gemini'
        else:
            provider = 'gemini'

    if not model:
        if provider == 'gemini':
            model = 'gemini-3.1-flash'
        elif provider == 'agy':
            model = 'gemini-3.6-flash'
        elif provider == 'ollama':
            model = 'llama3.1'
        elif provider == 'foundry':
            model = 'local'
        elif provider in ('gemini_cli', 'gemini-cli'):
            model = 'gemini-3-flash-preview'
        elif provider in ('openai', 'openai_compat', 'openai-compat', 'deepseek', 'groq', 'openrouter', 'lmstudio'):
            model = 'gpt-4o-mini'
        elif provider in ('hf', 'huggingface'):
            model = 'microsoft/Phi-3-mini-4k-instruct'
        elif provider == 'onnx':
            model = 'cpu-int4-rt'
        else:
            model = 'gemini-3.1-flash'

    if provider == 'foundry' and not model.startswith('foundry:'):
        model = f"foundry:{model}"
    elif provider == 'ollama' and not model.startswith('ollama:'):
        model = f"ollama:{model}"
    elif provider == 'agy' and not model.startswith('agy-'):
        model = f"agy-{model}"
    elif provider in ('gemini_cli', 'gemini-cli') and not model.startswith('gemini_cli:'):
        model = f"gemini_cli:{model}"
    elif provider in ('openai', 'openai_compat', 'openai-compat', 'deepseek', 'groq', 'openrouter', 'lmstudio'):
        openai_prefixes = ('openai:', 'deepseek:', 'groq:', 'openrouter:', 'lmstudio:', 'local:', 'compat:')
        if not any(model.startswith(p) for p in openai_prefixes):
            model = f"{provider}:{model}"
    elif provider in ('hf', 'huggingface') and not model.startswith('hf:'):
        model = f"hf:{model}"
    elif provider == 'onnx' and not model.startswith('onnx:'):
        model = f"onnx:{model}"

    return model, provider.upper()

