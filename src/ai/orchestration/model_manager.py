# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin AI - Model Manager Module
# =============================================================================
# Description:
#   Менеджер обнаружения, фильтрации и кэширования моделей ИИ для всех провайдеров.
#
# Usage Examples:
#   Python API:
#     from src.ai.orchestration.model_manager import load_unsupported_models
#
#     res = load_unsupported_models()
#     print(res)
#
# File: model_manager.py
# Project: ai-windows-admin
# Package: src.ai.orchestration
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 18:11:00
# =============================================================================

"""Менеджер обнаружения, фильтрации и кэширования моделей ИИ для всех провайдеров."""

import asyncio
import os
from pathlib import Path
import threading
from typing import Any, Dict, List, Set
import aiohttp
from google import genai
from header import __root__
from logger import logger
from src.utils.jjson import j_dumps, j_loads


def _get_active_config_path() -> Path:
    """Возвращает путь к активному файлу конфигурации с учетом переменных окружения и сценария TC."""
    cfg_env = os.getenv('AIWINDOWSADMIN_CONFIG') or os.getenv('CONFIG_FILE')
    if cfg_env:
        p = Path(cfg_env)
        if p.is_absolute() and p.exists():
            return p
        if (__root__ / cfg_env).exists():
            return __root__ / cfg_env
        if (__root__ / 'apps' / 'windows' / p.name).exists():
            return __root__ / 'apps' / 'windows' / p.name
    windows_cfg = __root__ / 'apps' / 'windows' / 'config.json'
    if windows_cfg.exists() and not (__root__ / 'config.json').exists():
        return windows_cfg
    return __root__ / 'config.json'


_GLOBAL_CONFIG_PATH: Path = __root__ / 'config.json'
_GEMINI_UNSUPPORTED_PATH: Path = __root__ / 'src' / 'ai' / 'gemini' / 'unsopported_gemini_models.json'
_CACHED_MODELS: Dict[str, List[str]] = {}
_CACHE_LOCK = threading.RLock()
_DEFAULT_GEMINI_FALLBACK: List[str] = [
    'gemini-3.8-flash',
    'gemini-flash-lite-latest',
    'gemini-3.7-flash',
    'gemini-3.6-flash',
    'gemini-3.1-flash-lite',
    'gemini-pro-latest',
]
_GEMINI_PRIORITY_ORDER: List[str] = [
    'gemini-3.8-flash',
    'gemini-flash-lite-latest',
    'gemini-3.7-flash',
    'gemini-3.6-flash',
    'gemini-3.1-flash-lite',
    'gemini-pro-latest',
]
_DEFAULT_GEMINI_CLI_FALLBACK: List[str] = [
    'gemini-3.1-flash-lite',
    'gemini-2.5-flash',
    'gemini-2.5-pro',
    'gemini-3.1-pro-preview',
    'gemini-3.1-flash-lite-preview',
    'gemini-3.5-flash-lite',
    'gemini-pro-latest',
]
_GEMINI_CLI_PRIORITY_ORDER: List[str] = [
    'gemini-3.1-flash-lite',
    'gemini-2.5-flash',
    'gemini-2.5-pro',
    'gemini-3.1-pro-preview',
    'gemini-3.1-flash-lite-preview',
    'gemini-3.5-flash-lite',
    'gemini-pro-latest',
]


def _normalize_model_name(name: str) -> str:
    """Нормализует идентификатор модели для единообразного сравнения."""
    res: str = name.strip()
    if res.startswith('models/'):
        res = res[len('models/'):]
    return res


normalize_model_name = _normalize_model_name


def _get_provider_cfg(provider: str) -> Dict[str, Any]:
    """Возвращает словарь настроек провайдера из ai_cfg или config.json."""
    prov = (provider or '').lower().strip()
    key = 'gemini_cli' if prov in ('gemini_cli', 'gemini-cli') else (
        'hf' if prov in ('hf', 'huggingface') else (
            'openai' if prov in ('openai', 'openai_compat', 'openai-compat', 'deepseek', 'groq', 'openrouter', 'lmstudio') else prov
        )
    )
    try:
        from src.config import ai_cfg
        providers = getattr(ai_cfg, 'providers', None) if ai_cfg else None
        if providers is not None:
            if isinstance(providers, dict):
                cfg = providers.get(key, {})
            else:
                cfg = getattr(providers, key, {})
            if isinstance(cfg, dict) and cfg:
                return cfg
            elif hasattr(cfg, '__dict__') and vars(cfg):
                return vars(cfg)
    except Exception:
        pass
    try:
        global_cfg = j_loads(_get_active_config_path()) or {}
        if isinstance(global_cfg, dict):
            ai_sec = global_cfg.get('ai_providers_and_models_configuration') or global_cfg.get('ai', {})
            if isinstance(ai_sec, dict):
                p_sec = ai_sec.get('providers', {})
                if isinstance(p_sec, dict) and key in p_sec:
                    val = p_sec[key]
                    if isinstance(val, dict):
                        return val
    except Exception as exc:
        logger.debug(f"[ModelManager] Ошибка чтения конфигурации провайдера {prov}: {exc}")
    return {}


def get_provider_config(provider: str) -> Dict[str, Any]:
    """Возвращает словарь настроек указанного провайдера из активной конфигурации.

    Args:
        provider (str): Название провайдера ('gemini', 'gemini_cli', 'agy', 'foundry', 'ollama', 'hf', 'onnx', 'openai').

    Returns:
        Dict[str, Any]: Словарь конфигурации провайдера.
    """
    return _get_provider_cfg(provider)


def is_provider_enabled(provider: str) -> bool:
    """Проверяет, включен ли указанный провайдер в конфигурации приложения.

    Args:
        provider: Имя провайдера ('gemini', 'gemini_cli', 'agy', 'foundry', 'ollama', 'hf', 'onnx', 'openai').

    Returns:
        bool: True, если провайдер активен, иначе False.
    """
    prov = (provider or '').lower().strip()
    if not prov:
        return False
    key = 'gemini_cli' if prov in ('gemini_cli', 'gemini-cli') else (
        'hf' if prov in ('hf', 'huggingface') else (
            'openai' if prov in ('openai', 'openai_compat', 'openai-compat', 'deepseek', 'groq', 'openrouter', 'lmstudio') else prov
        )
    )
    cfg = _get_provider_cfg(key)
    if cfg and 'enabled' in cfg:
        return bool(cfg['enabled'])
    return key in ('gemini', 'gemini_cli', 'agy')


def load_unsupported_models(provider: str='gemini') -> Set[str]:
    """Загружает множество неподдерживаемых моделей из файлов конфигурации.

    Args:
        provider (str): Имя провайдера ('gemini', 'gemini_cli', 'agy', 'foundry', 'ollama').

    Returns:
        Set[str]: Множество нормализованных имен неподдерживаемых моделей.
    """
    prov: str = provider.lower().strip()
    unsupported: Set[str] = set()
    if prov in ('gemini', 'gemini_cli', 'agy'):
        try:
            from src.ai.gemini.rules import load_unsupported_rules_and_models
            rules, explicit_models = load_unsupported_rules_and_models()
            unsupported.update(explicit_models)
            for r in rules:
                unsupported.add(r)
        except Exception as exc:
            logger.debug(f"[ModelManager] Не удалось загрузить правила Gemini: {exc}")

    global_cfg = j_loads(_get_active_config_path())
    if isinstance(global_cfg, dict):
        ai_sec = global_cfg.get('ai_providers_and_models_configuration') or global_cfg.get('ai', {})
        if isinstance(ai_sec, dict):
            providers = ai_sec.get('providers', {})
            if isinstance(providers, dict):
                prov_obj = providers.get(prov, {})
                if isinstance(prov_obj, dict):
                    prov_list = prov_obj.get('unsupported_models', [])
                    if isinstance(prov_list, list):
                        for item in prov_list:
                            if isinstance(item, str) and item.strip():
                                unsupported.add(_normalize_model_name(item))
    return unsupported


def is_model_supported(provider: str, model_name: str) -> bool:
    """Проверяет, поддерживается ли модель для указанного провайдера."""
    norm = _normalize_model_name(model_name)
    prov = provider.lower().strip()
    if prov in ('gemini', 'gemini_cli', 'agy'):
        try:
            from src.ai.gemini.rules import is_gemini_model_unsupported
            clean_name = norm.replace('agy-', '') if prov == 'agy' else norm
            if is_gemini_model_unsupported(clean_name):
                return False
        except Exception:
            pass
    unsupported = load_unsupported_models(provider)
    return norm not in unsupported


def add_unsupported_model(provider: str='gemini', model_name: str='', reason: str='') -> bool:
    """Добавляет неподдерживаемую модель в конфигурацию и удаляет из кэша.

    Args:
        provider (str): Имя провайдера.
        model_name (str): Имя модели для исключения.
        reason (str): Причина исключения.

    Returns:
        bool: True при успешном сохранении.
    """
    if not model_name:
        return False
    prov: str = provider.lower().strip()
    norm_name: str = _normalize_model_name(model_name)
    if prov in ('gemini', 'gemini_cli', 'agy'):
        try:
            from src.ai.gemini.rules import add_unsupported_gemini_model
            add_unsupported_gemini_model(norm_name, reason=reason)
        except Exception as exc:
            logger.debug(f"[ModelManager] Ошибка добавления неподдерживаемой модели Gemini: {exc}")
    active_cfg_path = _get_active_config_path()
    global_cfg = j_loads(active_cfg_path)
    if isinstance(global_cfg, dict):
        ai_sec = global_cfg.get('ai_providers_and_models_configuration')
        if not isinstance(ai_sec, dict):
            ai_sec = {}
            global_cfg['ai_providers_and_models_configuration'] = ai_sec
        providers = ai_sec.get('providers', {})
        if not isinstance(providers, dict):
            providers = {}
            ai_sec['providers'] = providers
        prov_obj = providers.get(prov, {})
        if not isinstance(prov_obj, dict):
            prov_obj = {}
            providers[prov] = prov_obj
        prov_list = prov_obj.get('unsupported_models', [])
        if not isinstance(prov_list, list):
            prov_list = []
        if norm_name not in prov_list:
            prov_list.append(norm_name)
            prov_obj['unsupported_models'] = sorted(list(set(prov_list)))
            global_cfg.pop('ai', None)
            j_dumps(global_cfg, active_cfg_path)
    with _CACHE_LOCK:
        if prov in _CACHED_MODELS:
            _CACHED_MODELS[prov] = [m for m in _CACHED_MODELS[prov] if _normalize_model_name(m) != norm_name]
        if 'agy' in _CACHED_MODELS:
            _CACHED_MODELS['agy'] = [m for m in _CACHED_MODELS['agy'] if _normalize_model_name(m.replace('agy-', '')) != norm_name]
    logger.warning(f"[ModelManager] Модель '{norm_name}' провайдера '{prov}' добавлена в list неподдерживаемых (причина: {reason[:120]})")
    return True


def _fetch_gemini_models_sync(api_key: str='', include_unsupported: bool=False) -> List[str]:
    """Синхронно получает список моделей Gemini с опциональной фильтрацией."""
    if not is_provider_enabled('gemini'):
        return []
    unsupported: Set[str] = load_unsupported_models('gemini')
    discovered: List[str] = []
    key_to_use: str = api_key
    if not key_to_use:
        try:
            from src.ai.gemini.gemini_api_key_state import load_api_keys
            keys, _, _ = load_api_keys()
            if keys:
                key_to_use = keys[0]
        except Exception as e:
            logger.debug(f'[ModelManager] Failed to load Gemini API key for listing: {e}')
        if not key_to_use:
            key_to_use = os.getenv('GEMINI_API_KEY', '') or os.getenv('GEMINI_API_KEY_1', '')
    if key_to_use:
        try:
            client = genai.Client(api_key=key_to_use)
            for m in client.models.list():
                m_name = getattr(m, 'name', '') or ''
                norm = _normalize_model_name(m_name)
                actions = getattr(m, 'supported_actions', None) or getattr(m, 'supported_generation_methods', None)
                if isinstance(actions, (list, tuple, set)) and actions and (not any(('generateContent' in str(a) for a in actions))):
                    continue
                out_modalities = getattr(m, 'output_modalities', None)
                if isinstance(out_modalities, (list, tuple, set)) and out_modalities and (not any(('TEXT' in str(mod).upper() for mod in out_modalities))):
                    continue
                if norm.endswith('-tts') or '-tts-' in norm or norm.startswith('tts-'):
                    continue
                if norm and norm not in discovered:
                    discovered.append(norm)
        except Exception as e:
            masked_key = f"{key_to_use[:6]}...{key_to_use[-4:]}" if len(key_to_use) > 10 else "***"
            request_info = {
                "method": "genai.Client.models.list()",
                "endpoint": "https://generativelanguage.googleapis.com/v1beta/models",
                "api_key": masked_key,
            }
            logger.error(
                f"[ModelManager] Не удалось получить список моделей Gemini через SDK: {e}. "
                f"Параметры и тело запроса: {request_info}"
            )
    combined: List[str] = list(discovered)
    for fb in _DEFAULT_GEMINI_FALLBACK:
        norm_fb = _normalize_model_name(fb)
        if norm_fb not in combined:
            combined.append(norm_fb)
    if include_unsupported:
        for unsup in unsupported:
            if unsup and unsup not in combined:
                combined.append(unsup)
        return combined
    pool: List[str] = [m for m in combined if m not in unsupported]
    try:
        from src.ai.gemini.rules import is_gemini_model_unsupported
        pool = [m for m in pool if not is_gemini_model_unsupported(m)]
    except Exception:
        pass
    if not pool:
        pool = list(_DEFAULT_GEMINI_FALLBACK)
    return pool


def _fetch_foundry_models_sync(base_url: str='', include_unsupported: bool=False) -> List[str]:
    """Синхронно получает список моделей от локального сервера Foundry с явным таймаутом."""
    if not is_provider_enabled('foundry'):
        return []
    foundry_cfg = _get_provider_cfg('foundry')
    base_url = base_url or (foundry_cfg.get('base_url', 'http://localhost:54837') if foundry_cfg else 'http://localhost:54837')
    fallback_id = foundry_cfg.get('default_model') or foundry_cfg.get('model', 'qwen2.5-1.5b-instruct-generic-cpu:4')
    unsupported: Set[str] = load_unsupported_models('foundry')
    import requests
    models: List[str] = []
    try:
        resp = requests.get(f'{base_url}/v1/models', timeout=(2.0, 5.0))
        if resp.status_code == 200:
            data: Dict[str, Any] = resp.json()
            for item in data.get('data', []):
                mid: str = item.get('id', '')
                if mid:
                    norm = _normalize_model_name(mid)
                    if include_unsupported or norm not in unsupported:
                        models.append(mid)
            if models:
                return models
    except Exception as e:
        logger.warning(f'[ModelManager] Foundry сервер ({base_url}) недоступен или вернул ошибку: {e}')
    if include_unsupported or _normalize_model_name(fallback_id) not in unsupported:
        return [fallback_id]
    return []


def _fetch_ollama_models_sync(base_url: str='', include_unsupported: bool=False) -> List[str]:
    """Синхронно получает список моделей от локального сервера Ollama с явным таймаутом."""
    if not is_provider_enabled('ollama'):
        return []
    ollama_cfg = _get_provider_cfg('ollama')
    base_url = base_url or (ollama_cfg.get('base_url', 'http://localhost:11434') if ollama_cfg else 'http://localhost:11434')
    fallback_id = ollama_cfg.get('default_model') or ollama_cfg.get('model', 'llama3.1')
    unsupported: Set[str] = load_unsupported_models('ollama')
    import requests
    models: List[str] = []
    try:
        resp = requests.get(f'{base_url}/api/tags', timeout=(2.0, 5.0))
        if resp.status_code == 200:
            data: Dict[str, Any] = resp.json()
            for item in data.get('models', []):
                name: str = item.get('name', '')
                if name:
                    norm = _normalize_model_name(name)
                    if include_unsupported or norm not in unsupported:
                        models.append(name)
            if models:
                return models
    except Exception as e:
        logger.warning(f'[ModelManager] Ollama сервер ({base_url}) недоступен или вернул ошибку: {e}')
    if include_unsupported or _normalize_model_name(fallback_id) not in unsupported:
        return [fallback_id]
    return []


def _fetch_gemini_cli_models_sync(include_unsupported: bool=False) -> List[str]:
    """Синхронно получает список моделей для Gemini CLI с опциональной фильтрацией."""
    if not is_provider_enabled('gemini_cli'):
        return []
    unsupported: Set[str] = load_unsupported_models('gemini_cli')
    if include_unsupported:
        combined = list(_DEFAULT_GEMINI_CLI_FALLBACK)
        for u in unsupported:
            if u not in combined:
                combined.append(u)
        return combined
    pool: List[str] = [m for m in _DEFAULT_GEMINI_CLI_FALLBACK if m not in unsupported]
    if not pool:
        pool = list(_DEFAULT_GEMINI_CLI_FALLBACK)
    return pool


def _fetch_hf_models_sync(include_unsupported: bool=False) -> List[str]:
    """Синхронно получает список кэшированных моделей HuggingFace."""
    if not is_provider_enabled('hf'):
        return []
    unsupported: Set[str] = load_unsupported_models('hf')
    models: List[str] = []
    try:
        from src.ai.chat.hf import hf_client
        downloaded: List[Dict[str, Any]] = hf_client.list_downloaded()
        for item in downloaded:
            mid: str = item.get('id', '')
            if mid:
                norm = _normalize_model_name(mid)
                if include_unsupported or norm not in unsupported:
                    models.append(mid)
        if models:
            return models
    except Exception as e:
        logger.warning(f'[ModelManager] HuggingFace list моделей недоступен: {e}')
    fallback: List[str] = ['Qwen/Qwen2.5-0.5B-Instruct', 'google/gemma-2-2b-it']
    if include_unsupported:
        return fallback + [u for u in unsupported if u not in fallback]
    return [m for m in fallback if _normalize_model_name(m) not in unsupported]


def _fetch_onnx_models_sync(include_unsupported: bool=False) -> List[str]:
    """Синхронно получает список моделей ONNX из локальной папки models/onnx, памяти и конфигурации."""
    if not is_provider_enabled('onnx'):
        return []
    unsupported: Set[str] = load_unsupported_models('onnx')
    discovered_models: Set[str] = set()
    try:
        from src.ai.chat.onnx import onnx_client
        loaded: List[Dict[str, Any]] = onnx_client.list_loaded()
        for item in loaded:
            mid: str = item.get('id', '')
            if mid:
                norm = _normalize_model_name(mid)
                if include_unsupported or norm not in unsupported:
                    discovered_models.add(mid)
    except Exception as e:
        logger.debug(f'[ModelManager] ONNX memory models check: {e}')
    try:
        global_cfg: Dict[str, Any] = j_loads(_get_active_config_path()) or {}
        onnx_cfg: Dict[str, Any] = global_cfg.get('onnx', {}) if isinstance(global_cfg, dict) else {}
        models_dir_rel: str = onnx_cfg.get('models_dir', 'models/onnx')
        models_dir: Path = __root__ / models_dir_rel if not Path(models_dir_rel).is_absolute() else Path(models_dir_rel)
        if models_dir.exists() and models_dir.is_dir():
            for entry in models_dir.iterdir():
                if entry.is_dir() or entry.suffix in ('.onnx', '.ort'):
                    name = entry.name
                    if name:
                        norm = _normalize_model_name(name)
                        if include_unsupported or norm not in unsupported:
                            discovered_models.add(name)
        def_model = onnx_cfg.get('default_model', '')
        if def_model:
            norm_def = _normalize_model_name(def_model)
            if include_unsupported or norm_def not in unsupported:
                discovered_models.add(def_model)
    except Exception as e:
        logger.warning(f'[ModelManager] ONNX local directory scan: {e}')
    if not discovered_models:
        discovered_models = {'phi-3.5-mini-instruct-onnx', 'qwen2.5-0.5b-instruct-onnx'}
    if include_unsupported:
        for unsup in unsupported:
            discovered_models.add(unsup)
        return sorted(list(discovered_models))
    return [m for m in sorted(discovered_models) if _normalize_model_name(m) not in unsupported]


def _fetch_openai_compat_models_sync(include_unsupported: bool=False) -> List[str]:
    """Синхронно получает список моделей OpenAI-совместимых провайдеров."""
    if not is_provider_enabled('openai'):
        return []
    unsupported: Set[str] = load_unsupported_models('openai')
    global_cfg: Dict[str, Any] = j_loads(_get_active_config_path())
    models: List[str] = []
    if isinstance(global_cfg, dict):
        compat_sec: Dict[str, Any] = global_cfg.get('openai_compat', {})
        if isinstance(compat_sec, dict):
            for prov_name, prov_data in compat_sec.get('providers', {}).items():
                if isinstance(prov_data, dict):
                    for m in prov_data.get('models', []):
                        if isinstance(m, str) and m:
                            norm = _normalize_model_name(m)
                            if include_unsupported or norm not in unsupported:
                                if prov_name != 'openai' and (not any((m.startswith(f'{p}:') for p in ('openai', 'deepseek', 'groq', 'openrouter', 'lmstudio', 'local')))):
                                    models.append(f'{prov_name}:{m}')
                                else:
                                    models.append(m)
    if not models:
        models = ['gpt-4o-mini', 'gpt-4o', 'deepseek:deepseek-chat']
    if include_unsupported:
        for u in unsupported:
            if u not in models:
                models.append(u)
        return models
    return [m for m in models if _normalize_model_name(m) not in unsupported]


def get_available_models(provider: str='gemini', api_key: str='', force_refresh: bool=False, include_unsupported: bool=False) -> List[str]:
    """Возвращает список доступных моделей для указанного провайдера.

    Args:
        provider (str): Имя провайдера ('gemini', 'gemini_cli', 'agy', 'foundry', 'ollama', 'hf', 'onnx', 'openai').
        api_key (str): Опциональный API-ключ для Gemini.
        force_refresh (bool): Принудительно обновить кэш.
        include_unsupported (bool): Включать ли неподдерживаемые модели.

    Returns:
        List[str]: Список идентификаторов моделей.
    """
    prov: str = provider.lower().strip()
    if not is_provider_enabled(prov):
        return []
    with _CACHE_LOCK:
        if not force_refresh and (not include_unsupported) and (prov in _CACHED_MODELS) and _CACHED_MODELS[prov]:
            return list(_CACHED_MODELS[prov])
    result_models: List[str] = []
    if prov == 'gemini':
        result_models = _fetch_gemini_models_sync(api_key=api_key, include_unsupported=include_unsupported)
        if not include_unsupported:
            with _CACHE_LOCK:
                _CACHED_MODELS['gemini'] = result_models
        return list(result_models)
    elif prov in ('gemini_cli', 'gemini-cli'):
        result_models = _fetch_gemini_cli_models_sync(include_unsupported=include_unsupported)
        if not include_unsupported:
            with _CACHE_LOCK:
                _CACHED_MODELS['gemini_cli'] = result_models
        return list(result_models)
    elif prov == 'agy':
        gemini_models: List[str] = get_available_models('gemini', api_key=api_key, force_refresh=force_refresh, include_unsupported=include_unsupported)
        agy_unsupported: Set[str] = load_unsupported_models('agy')
        if include_unsupported:
            result_models = [f'agy-{m}' if not m.startswith('agy-') else m for m in gemini_models]
        else:
            result_models = [f'agy-{m}' for m in gemini_models if _normalize_model_name(m) not in agy_unsupported and f'agy-{m}' not in agy_unsupported]
        if not include_unsupported:
            with _CACHE_LOCK:
                _CACHED_MODELS['agy'] = result_models
        return list(result_models)
    elif prov == 'foundry':
        result_models = _fetch_foundry_models_sync(include_unsupported=include_unsupported)
        if not include_unsupported:
            with _CACHE_LOCK:
                _CACHED_MODELS['foundry'] = result_models
        return list(result_models)
    elif prov == 'ollama':
        result_models = _fetch_ollama_models_sync(include_unsupported=include_unsupported)
        if not include_unsupported:
            with _CACHE_LOCK:
                _CACHED_MODELS['ollama'] = result_models
        return list(result_models)
    elif prov in ('hf', 'huggingface'):
        result_models = _fetch_hf_models_sync(include_unsupported=include_unsupported)
        if not include_unsupported:
            with _CACHE_LOCK:
                _CACHED_MODELS['hf'] = result_models
        return list(result_models)
    elif prov == 'onnx':
        result_models = _fetch_onnx_models_sync(include_unsupported=include_unsupported)
        if not include_unsupported:
            with _CACHE_LOCK:
                _CACHED_MODELS['onnx'] = result_models
        return list(result_models)
    elif prov in ('openai', 'openai_compat', 'openai-compat', 'deepseek', 'groq', 'openrouter', 'lmstudio'):
        result_models = _fetch_openai_compat_models_sync(include_unsupported=include_unsupported)
        if not include_unsupported:
            with _CACHE_LOCK:
                _CACHED_MODELS['openai'] = result_models
        return list(result_models)
    return result_models


async def actualize_all_models(force_refresh: bool=True) -> Dict[str, List[str]]:
    """Асинхронно актуализирует и прогревает кэш моделей для всех активных провайдеров.

    Args:
        force_refresh (bool): Принудительно опросить SDK/API провайдеров.

    Returns:
        Dict[str, List[str]]: Словарь со списками доступных моделей по провайдерам.
    """
    logger.info('[ModelManager] Запуск актуализации моделей для активных провайдеров...')
    loop = asyncio.get_running_loop()

    tasks: Dict[str, Any] = {}
    for p in ('gemini', 'gemini_cli', 'foundry', 'ollama', 'hf', 'onnx', 'openai'):
        if is_provider_enabled(p):
            tasks[p] = loop.run_in_executor(None, get_available_models, p, '', force_refresh)

    gathered_keys = list(tasks.keys())
    gathered_results = await asyncio.gather(*tasks.values(), return_exceptions=True) if tasks else []

    results_by_prov: Dict[str, List[str]] = {}
    for p, res in zip(gathered_keys, gathered_results):
        results_by_prov[p] = res if isinstance(res, list) else []

    gemini_list: List[str] = results_by_prov.get('gemini', [])
    gemini_cli_list: List[str] = results_by_prov.get('gemini_cli', [])
    foundry_list: List[str] = results_by_prov.get('foundry', [])
    ollama_list: List[str] = results_by_prov.get('ollama', [])
    hf_list: List[str] = results_by_prov.get('hf', [])
    onnx_list: List[str] = results_by_prov.get('onnx', [])
    openai_list: List[str] = results_by_prov.get('openai', [])
    agy_list: List[str] = get_available_models('agy', force_refresh=force_refresh) if is_provider_enabled('agy') else []

    result_pool: Dict[str, List[str]] = {
        'gemini': gemini_list,
        'gemini_cli': gemini_cli_list,
        'agy': agy_list,
        'foundry': foundry_list,
        'ollama': ollama_list,
        'hf': hf_list,
        'onnx': onnx_list,
        'openai': openai_list,
    }
    logger.info(
        f'[ModelManager] Актуализация завершена: Gemini={len(gemini_list)}, '
        f'Gemini_CLI={len(gemini_cli_list)}, AGY={len(agy_list)}, '
        f'Foundry={len(foundry_list)}, Ollama={len(ollama_list)}, '
        f'HF={len(hf_list)}, ONNX={len(onnx_list)}, OpenAI={len(openai_list)}'
    )
    return result_pool
