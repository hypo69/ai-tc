# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc UTILS - Convertors Package Init
# =============================================================================
# Description:
#   Пакет конвертеров данных и парсинга форматов для ai-tc.
#
# File: __init__.py
# Project: ai-tc
# Package: src.utils.convertors
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 05:00:00
# =============================================================================

from __future__ import annotations
"""Пакет конвертеров данных и парсинга форматов для ai-tc."""

from . import base64, csv, dict, excel, google_sheet, html, html2text, json, md, model_response, ns, png, tts, unicode, xml2dict
from .model_response import parse_model_response, clean_model_response, markdown_to_safe_html

__all__ = [
    'base64',
    'csv',
    'dict',
    'excel',
    'google_sheet',
    'html',
    'html2text',
    'json',
    'md',
    'model_response',
    'parse_model_response',
    'clean_model_response',
    'markdown_to_safe_html',
    'ns',
    'png',
    'tts',
    'unicode',
    'xml2dict',
]
