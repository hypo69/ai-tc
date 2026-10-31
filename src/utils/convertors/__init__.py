# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin UTILS - Convertors Package Init
# =============================================================================
# Description:
#   Пакет конвертеров данных и парсинга форматов для AI-Windows-Admin.
#
# File: __init__.py
# Project: ai-windows-admin
# Package: src.utils.convertors
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 19:48:00
# =============================================================================

from __future__ import annotations
"""Пакет конвертеров данных и парсинга форматов для AI-Windows-Admin."""

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
