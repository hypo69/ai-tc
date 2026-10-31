# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Базовый интерфейс платформенных адаптеров (Base Platform)
# =============================================================================
# Description:
#   Определение контрактов платформенных адаптеров для унификации структуры
#   ответов между Windows и Linux (Раздел 4.3 и 8 ТЗ).
#
# File: base.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.platforms
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:52:00
# =============================================================================

import json
from typing import Any, Dict
from ..transports.base import RawExecutionResult


def pack_raw_result(raw: RawExecutionResult, extra: Dict[str, Any]) -> Dict[str, Any]:
    """Упаковка результата транспорта с мета-полями для ExecutionEngine.

    Args:
        raw (RawExecutionResult): Сырой результат выполнения команды.
        extra (Dict[str, Any]): Структурированные данные домена.

    Returns:
        Dict[str, Any]: Объединённый словарь для конвейера выполнения.

    Examples:
        >>> r = RawExecutionResult(exit_code=0, stdout="ok", stderr="", duration_ms=10)
        >>> d = pack_raw_result(r, {"total_mb": 1024})
        >>> d["total_mb"]
        1024
    """
    payload = dict(extra)
    payload["_exit_code"] = raw.exit_code
    payload["_stdout"] = raw.stdout
    payload["_stderr"] = raw.stderr
    payload["_duration_ms"] = raw.duration_ms
    return payload


def safe_parse_json(stdout_text: str) -> Dict[str, Any]:
    """Безопасный разбор JSON-вывода из stdout с резервным возвратом словаря.

    Args:
        stdout_text (str): Строка вывода команды.

    Returns:
        Dict[str, Any]: Разобранный словарь или `{'items': ...}` / `{'raw': ...}`.

    Examples:
        >>> safe_parse_json('{"a": 1}')
        {'a': 1}
    """
    if not stdout_text:
        return {}
    try:
        parsed = json.loads(stdout_text)
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list):
            return {"items": parsed}
        return {"value": parsed}
    except Exception:
        return {"raw_output": stdout_text}
