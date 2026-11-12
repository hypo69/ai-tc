# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin AI - Errors Module
# =============================================================================
# Description:
#   Mixin class for centralized error handling in GoogleGenerativeAI.
#
# Usage Examples:
#   Python API:
#     from src.ai.gemini.errors import GoogleGenerativeAIErrorMixin
#
#     service = GoogleGenerativeAIErrorMixin()
#
# File: errors.py
# Project: ai-windows-admin
# Package: src.ai.gemini
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-03 16:25:00
# =============================================================================

"""Mixin class for centralized error handling in GoogleGenerativeAI."""

import asyncio
import json
import re
import time
from typing import Any, Optional
import requests
from logger import logger
from src.ai.orchestration.model_error_hub import record_model_error
from src.ai.orchestration.model_pool_state import mark_model_exhausted
from .core import add_unsupported_model


def format_error_as_json(
    ex: Any,
    model: str = '',
    attempt: int = 0,
    max_attempts: int = 0,
    status_code: Optional[int] = None,
    action_taken: str = '',
) -> str:
    """Форматирование исключений и ошибок модели в структурированный JSON.

    Args:
        ex (Any): Объект исключения, ошибки или текст.
        model (str): Наименование активной модели Gemini.
        attempt (int): Номер текущей попытки.
        max_attempts (int): Максимальное количество попыток.
        status_code (Optional[int]): HTTP статус-код при наличии.
        action_taken (str): Принятое действие при обработке ошибки.

    Returns:
        str: Сериализованный JSON с деталями ошибки.
    """
    err_dict: dict[str, Any] = {}

    details = getattr(ex, 'details', None)
    if isinstance(details, dict):
        err_dict = dict(details)
    elif isinstance(details, list):
        err_dict = {
            'error': {
                'code': getattr(ex, 'code', status_code),
                'status': getattr(ex, 'status', None),
                'message': getattr(ex, 'message', str(ex)),
                'details': details,
            }
        }

    if not err_dict and hasattr(ex, 'response'):
        resp = getattr(ex, 'response')
        if hasattr(resp, 'json') and callable(resp.json):
            try:
                j = resp.json()
                if isinstance(j, dict):
                    err_dict = j
            except Exception:
                pass

    if not err_dict:
        ex_str = str(ex)
        try:
            start = ex_str.find('{')
            end = ex_str.rfind('}')
            if start != -1 and end != -1 and end > start:
                json_str = ex_str[start:end + 1]
                try:
                    parsed = json.loads(json_str)
                    if isinstance(parsed, dict):
                        err_dict = parsed
                except Exception:
                    import ast
                    parsed = ast.literal_eval(json_str)
                    if isinstance(parsed, dict):
                        err_dict = parsed
        except Exception:
            pass

    if not err_dict:
        code = getattr(ex, 'code', None) or getattr(ex, 'status_code', None) or status_code
        status = getattr(ex, 'status', None)
        message = getattr(ex, 'message', None) or str(ex)
        err_type = type(ex).__name__ if isinstance(ex, Exception) else 'ModelError'
        err_dict = {
            'error': {
                'code': code,
                'status': status,
                'message': message,
                'type': err_type,
            }
        }

    if 'error' in err_dict and isinstance(err_dict['error'], dict):
        if model and 'model' not in err_dict['error']:
            err_dict['error']['model'] = model
        if attempt and 'attempt' not in err_dict['error']:
            err_dict['error']['attempt'] = attempt
        if max_attempts and 'max_attempts' not in err_dict['error']:
            err_dict['error']['max_attempts'] = max_attempts
        if action_taken and 'action_taken' not in err_dict['error']:
            err_dict['error']['action_taken'] = action_taken
    else:
        err_dict = {
            'error': err_dict,
            'model': model,
            'attempt': attempt,
            'max_attempts': max_attempts,
            'action_taken': action_taken,
        }

    return json.dumps(err_dict, ensure_ascii=False, indent=2)


class GoogleGenerativeAIErrorMixin:
    """Mixin class for centralized error handling in GoogleGenerativeAI.

    Provides methods for handling API errors, switching API keys, and model rotation.
    """

    def format_error_json(
        self,
        ex: Any,
        model: str = '',
        attempt: int = 0,
        max_attempts: int = 0,
        status_code: Optional[int] = None,
        action_taken: str = '',
    ) -> str:
        """Вспомогательный метод форматирования ошибки в JSON."""
        return format_error_as_json(
            ex=ex,
            model=model or getattr(self, 'model_name', ''),
            attempt=attempt,
            max_attempts=max_attempts,
            status_code=status_code,
            action_taken=action_taken,
        )

    async def _handle_api_error(self, ex: Exception, active_model: str, attempt: int, max_attempts: int) -> bool:
        """Centralized handling of API exceptions and retry coordination.

        Args:
            ex (Exception): Raised exception.
            active_model (str): Name of model being used.
            attempt (int): Current attempt number.
            max_attempts (int): Maximum number of attempts.

        Returns:
            bool: True if retry needed, False if error is unrecoverable.
        """
        self._record_error(ex)
        ex_str: str = str(ex)
        low: str = ex_str.lower()
        err_json: str = format_error_as_json(
            ex=ex,
            model=active_model,
            attempt=attempt + 1,
            max_attempts=max_attempts,
        )
        if attempt + 1 >= max_attempts:
            logger.error(f'Gemini Model Error (Attempt {attempt + 1}/{max_attempts}):\n{err_json}', exc_info=False)
        else:
            logger.warning(f'Gemini Model Retry (Attempt {attempt + 1}/{max_attempts}):\n{err_json}', exc_info=False)
        if '401' in ex_str or 'API_KEY_INVALID' in ex_str or 'PERMISSION_DENIED' in ex_str:
            logger.warning(f'GoogleGenerativeAI: Authorization error (API key invalid/expired). Rotating key...', exc_info=False)
            record_model_error(provider='gemini', model_name=active_model, error=ex_str, status_code=401, attempt=attempt, max_attempts=max_attempts, action_taken='rotate_key')
            self._invalidate_api_key(self.api_key)
            return self._switch_api_key()
        if any((k in ex_str for k in ['404', 'NOT_FOUND', 'is no longer available', 'not found for API version', 'not supported for generateContent', 'response modalities', 'response_modalities', 'not supported by the model'])):
            logger.warning(f'GoogleGenerativeAI: Model {active_model} is unsupported or deprecated ({ex_str}). Switching model...', exc_info=False)
            record_model_error(provider='gemini', model_name=active_model, error=ex_str, status_code=404, attempt=attempt, max_attempts=max_attempts, action_taken='switch_model')
            add_unsupported_model(active_model, reason=ex_str)
            return self._switch_model()
        # 1. Перегрузка модели на стороне серверов Google (503 / Overloaded / High demand)
        # ВАЖНО: Ключ API в данном случае полностью рабочий и НЕ должен маркироваться как exhausted!
        is_overloaded = (
            '503' in ex_str
            or 'unavailable' in low
            or 'overload' in low
            or 'overloaded' in low
            or 'high demand' in low
            or 'service unavailable' in low
            or 'model is overloaded' in low
            or 'temporarily unavailable' in low
        )
        if is_overloaded:
            self._unavailable_attempts += 1
            record_model_error(
                provider='gemini',
                model_name=active_model,
                error=ex_str,
                status_code=503,
                attempt=attempt,
                max_attempts=max_attempts,
                action_taken='retry' if self._unavailable_attempts <= 2 else 'switch_model',
            )
            if self._unavailable_attempts <= 2:
                wait_sec = 2 ** min(self._unavailable_attempts, 4)
                logger.warning(
                    f'GoogleGenerativeAI: Модель {active_model} перегружена (Overloaded/503). '
                    f'Ключ активен. Ожидание {wait_sec}с (попытка {attempt + 1}/{max_attempts})...',
                    exc_info=False
                )
                await asyncio.sleep(wait_sec)
                return True

            logger.warning(
                f'GoogleGenerativeAI: Модель {active_model} устойчиво перегружена. '
                f'Переключаемся на резервную модель из пула...',
                exc_info=False
            )
            mark_model_exhausted('gemini', active_model)
            if hasattr(self, '_switch_model') and self._switch_model():
                self._unavailable_attempts = 0
                return True

            self._unavailable_attempts = 0
            return False

        # 4. Ошибка 429 / RESOURCE_EXHAUSTED
        if '429' in ex_str or 'resource_exhausted' in low:
            is_rpm_limit = any(k in low for k in ['per_minute', 'per minute', 'rate limit', 'rpm', 'tpm', 'too many requests'])
            if is_rpm_limit:
                logger.warning('GoogleGenerativeAI: Превышен минутный лимит запросов (RPM/Rate Limit). Мягкая ротация ключа без блокировки 24ч...')
                record_model_error(provider='gemini', model_name=active_model, error=ex_str, status_code=429, attempt=attempt, max_attempts=max_attempts, action_taken='rotate_key_soft')
                if hasattr(self, '_rotate_api_key_soft') and self._rotate_api_key_soft():
                    return True
                wait_sec = 4.0 + (attempt * 2)
                await asyncio.sleep(wait_sec)
                return True

            logger.warning('GoogleGenerativeAI: Ошибка 429 (Суточная квота ключа исчерпана). Маркируем ключ как exhausted и переключаемся...')
            record_model_error(provider='gemini', model_name=active_model, error=ex_str, status_code=429, attempt=attempt, max_attempts=max_attempts, action_taken='rotate_key')
            self._mark_key_exhausted(self.api_key)
            if self._switch_api_key():
                return True
            return self._switch_model()
        if isinstance(ex, requests.exceptions.RequestException):
            if attempt < 5:
                logger.warning('GoogleGenerativeAI: Network Error. Waiting 10s...', exc_info=False)
                record_model_error(provider='gemini', model_name=active_model, error=ex_str, attempt=attempt, max_attempts=5, action_taken='retry', retry_delay_seconds=10.0)
                await asyncio.sleep(10)
                return True
            record_model_error(provider='gemini', model_name=active_model, error=ex_str, attempt=attempt, max_attempts=5, action_taken='failed')
            return False
        if attempt < max_attempts - 1:
            wait_sec = 2 ** min(attempt, 4)
            logger.warning(f'GoogleGenerativeAI: API Error on attempt {attempt + 1}/{max_attempts}: {ex_str}. Retrying...', exc_info=False)
            record_model_error(provider='gemini', model_name=active_model, error=ex_str, attempt=attempt, max_attempts=max_attempts, action_taken='retry', retry_delay_seconds=float(wait_sec))
            await asyncio.sleep(wait_sec)
            return True
        logger.error(f'GoogleGenerativeAI: API Error (exhausted {max_attempts} attempts): {ex_str}', exc_info=False)
        record_model_error(provider='gemini', model_name=active_model, error=ex_str, attempt=attempt, max_attempts=max_attempts, action_taken='failed')
        return False