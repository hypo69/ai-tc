# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - models
# =============================================================================
# Description:
#   Pydantic-модели чата.
#   Вынесено из router_chat.py (этап 4 оптимизации).
#
# File: models.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers.chat
# Author: hypo69
# Copyright: c 2026 hypo69
# Updated: 2026-10-22 13:30:00
# =============================================================================

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []
    generation_config: dict = {}

class SaveRagRequest(BaseModel):
    query: str
    chat_text: str
    voice_text: str

class TestModelRequest(BaseModel):
    """Модель данных для проверочного запроса к AI-модели.

    Введите вручную имя модели и провайдера, иначе будет использована настройка по умолчанию.
    """
    __test__ = False

    model: str = Field(
        default="",
        description="Имя модели. Введите вручную имя модели и провайдера, иначе будет использована настройка по умолчанию.",
    )
    provider: str = Field(
        default="",
        description="Имя провайдера (gemini, agy, foundry, ollama, openai, hf, onnx, gemini_cli). Введите вручную имя модели и провайдера, иначе будет использована настройка по умолчанию.",
    )
    message: str = Field(
        default="Привет! Назови свою модель и провайдера, и подтверди готовность к работе.",
        description="Текст тестового сообщения для валидации связи.",
    )
    system_instruction: str = Field(
        default="",
        description="Опциональная системная инструкция для тестируемой модели.",
    )


class ModelInstructionPayload(BaseModel):
    """Модель данных для обновления системной инструкции AI-модели."""
    instruction: str = Field(
        default="",
        description="Текст системной инструкции для AI-модели.",
    )
    system_instruction: str = Field(
        default="",
        description="Алиас для текста системной инструкции.",
    )
    content: str = Field(
        default="",
        description="Алиас для текста системной инструкции.",
    )
    model: str = Field(
        default="",
        description="Опциональное имя модели.",
    )
    save_to_disk: bool = Field(
        default=False,
        description="Флаг сохранения системной инструкции в файл apps/windows/prompts/chat/system_instruction.md.",
    )

ModelInstructionRequest = ModelInstructionPayload


class SetModelPayload(BaseModel):
    """Модель данных для установки активной AI-модели."""
    model: str = Field(
        ...,
        description="Имя модели для установки (например: gemini-3.1-flash, ollama:llama3.1, agy-gemini-3.6-flash).",
    )
    provider: str = Field(
        default="",
        description="Опциональное имя провайдера (gemini, agy, foundry, ollama, openai, hf, onnx, gemini_cli).",
    )


class SetProviderPayload(BaseModel):
    """Модель данных для установки активного AI-провайдера."""
    provider: str = Field(
        ...,
        description="Имя провайдера (gemini, agy, foundry, ollama, openai, hf, onnx, gemini_cli).",
    )
    model: str = Field(
        default="",
        description="Опциональное имя модели. Если не указано, выбирается модель по умолчанию для провайдера.",
    )


class ChatSessionPayload(BaseModel):
    id: str = ""
    userId: str = ""
    title: str = "New Chat"
    isCustomTitle: bool = False
    createdAt: int = 0
    updatedAt: int = 0
    messages: list[dict] = []
    chatHistory: list[dict] = []

class SyncSessionsRequest(BaseModel):
    sessions: list[dict] = []

