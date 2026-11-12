# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin UTILS - Package Init
# =============================================================================
# Description:
#   Модуль утилит для AI-Windows-Admin.
#   Использует ленивый импорт тяжелого подмодуля pdf (weasyprint)
#   через PEP 562 (__getattr__) для минимизации Private Bytes и дескрипторов.
#
# File: __init__.py
# Project: ai-windows-admin
# Package: src.utils
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 18:13:00
# =============================================================================

from __future__ import annotations
"""Модуль утилит для AI-Windows-Admin."""

import importlib
from typing import Any

from . import (
    archive,
    com_worker,
    convertors,
    csv,
    date_time,
    file,
    get_free_port,
    google_errors,
    header,
    image,
    jjson,
    ports,
    printer,
    smtp,
    system_engineering,
    url,
    versioning,
)
from .google_errors import (
    ParsedGoogleError,
    handle_google_errors,
    log_google_error,
    parse_google_error,
)
from .printer import pformat, pprint

# Тяжелые модули с отложенной (ленивой) загрузкой по требованию
_LAZY_MODULES = {
    'pdf',
}


def __getattr__(name: str) -> Any:
    """Ленивая загрузка тяжелых подмодулей по требованию (PEP 562)."""
    if name in _LAZY_MODULES:
        try:
            module = importlib.import_module(f".{name}", __package__)
            globals()[name] = module
            return module
        except ImportError:
            globals()[name] = False
            return False
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    'archive',
    'com_worker',
    'convertors',
    'csv',
    'date_time',
    'file',
    'get_free_port',
    'google_errors',
    'handle_google_errors',
    'header',
    'image',
    'jjson',
    'log_google_error',
    'parse_google_error',
    'ParsedGoogleError',
    'pdf',
    'pformat',
    'pprint',
    'ports',
    'printer',
    'smtp',
    'system_engineering',
    'url',
    'versioning',
]
