# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc AI -   Init   Module
# =============================================================================
# Description:
#   Модуль основной системы (`__init__`).
#
# Usage Examples:
#
#
# File: __init__.py
# Project: ai-tc
# Package: src.ai.providers.foundry
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 05:00:00
# =============================================================================

"""Модуль основной системы (`__init__`)."""

from .client import FoundryClient
from .chat import FoundryChatBase, FoundrySimpleChat, get_foundry_chat, set_foundry_chat
__all__ = ['FoundryClient', 'FoundryChatBase', 'FoundrySimpleChat', 'get_foundry_chat', 'set_foundry_chat']
