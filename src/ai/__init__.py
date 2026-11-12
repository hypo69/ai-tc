# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin AI -   Init   Module
# =============================================================================
# Description:
#   Модуль основной системы (`__init__`).
#
# Usage Examples:
#
#
# File: __init__.py
# Project: ai-windows-admin
# Package: src.ai
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 18:16:00
# =============================================================================

from __future__ import annotations
"""Модуль основной системы (`__init__`)."""

from .providers.agy import AgyChatBase
from .providers.foundry import FoundryChatBase, FoundryClient, FoundrySimpleChat, get_foundry_chat, set_foundry_chat
from .providers.gemini_cli import GeminiCliChatBase, GeminiCliProvider, GeminiCliResponse
from .providers.openai import OpenAICompatChat
from .providers.onnx import ONNXChatBase
from .providers.huggingface import HFChatBase
from .providers.ollama import OllamaChatBase, OllamaClient
from .providers.base import BaseChatProvider
from .gemini import GoogleGenerativeAI
from .agents import MCPClientManager, MediaSearchAgent
from .orchestration import get_available_models, actualize_all_models, add_unsupported_model, load_unsupported_models, UnifiedChatModel, is_provider_enabled, get_provider_config
from .rag import UnifiedKnowledgeHub, TextRAG, PixelRAG, LogRAG
try:
    from apps.windows.wikillm import WikiLLMEngine, WikiStorage
except ImportError:
    from .wikillm import WikiLLMEngine, WikiStorage

__all__ = [
    'BaseChatProvider',
    'GoogleGenerativeAI',
    'GeminiCliChatBase',
    'GeminiCliProvider',
    'GeminiCliResponse',
    'AgyChatBase',
    'OllamaChatBase',
    'OllamaClient',
    'FoundryChatBase',
    'FoundryClient',
    'FoundrySimpleChat',
    'get_foundry_chat',
    'set_foundry_chat',
    'ONNXChatBase',
    'HFChatBase',
    'OpenAICompatChat',
    'UnifiedChatModel',
    'get_available_models',
    'actualize_all_models',
    'add_unsupported_model',
    'load_unsupported_models',
    'is_provider_enabled',
    'get_provider_config',
    'MediaSearchAgent',
    'MCPClientManager',
    'UnifiedKnowledgeHub',
    'TextRAG',
    'PixelRAG',
    'LogRAG',
    'WikiLLMEngine',
    'WikiStorage',
]

