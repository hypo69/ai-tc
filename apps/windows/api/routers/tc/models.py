# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - models
# =============================================================================
# Description:
#   Pydantic-модели TC.
#   Вынесено из router_tc.py (этап 4 оптимизации).
#
# File: models.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers.tc
# Author: hypo69
# Copyright: c 2026 hypo69
# Updated: 2026-10-22 13:30:00
# =============================================================================

from __future__ import annotations


from pydantic import BaseModel, Field


# -----------------------------------------------------------------------------
# DTO Models
# -----------------------------------------------------------------------------

class TcModelInstructionPayload(BaseModel):
    """Модель данных для обновления системной инструкции AI-модели Test Computer."""
    instruction: str = Field(
        default="",
        description="Текст системной инструкции для AI-модели Test Computer.",
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
        default=True,
        description="Флаг сохранения системной инструкции в файл apps/windows/prompts/tc/system_instruction.md.",
    )


class TcSetModelPayload(BaseModel):
    """Модель данных для установки активной AI-модели Test Computer."""
    model: str = Field(
        ...,
        description="Имя модели для установки (например: gemini-3.1-flash, gemini-3.1-flash-lite, agy-gemini-3.6-flash, llama3.1).",
    )
    provider: str = Field(
        default="",
        description="Опциональное имя провайдера (gemini, gemini_cli, agy, foundry, ollama, openai, hf, onnx).",
    )
    save_to_config: bool = Field(
        default=True,
        description="Флаг сохранения изменений в конфигурационный файл tc.json.",
    )


class TcSetProviderPayload(BaseModel):
    """Модель данных для установки активного AI-провайдера Test Computer."""
    provider: str = Field(
        ...,
        description="Имя провайдера (gemini, gemini_cli, agy, foundry, ollama, openai, hf, onnx).",
    )
    model: str = Field(
        default="",
        description="Опциональное имя модели. Если не указано, выбирается модель по умолчанию для провайдера.",
    )
    save_to_config: bool = Field(
        default=True,
        description="Флаг сохранения изменений в конфигурационный файл tc.json.",
    )


class TcCpuResponse(BaseModel):
    """Модель ответа метрик процессора из базы данных телеметрии."""
    total_percent: float = Field(default=0.0, description="Загрузка CPU в процентах")
    frequency_mhz: float = Field(default=0.0, description="Текущая частота CPU в МГц")
    physical_cores: int = Field(default=6, description="Количество физических ядер")
    logical_cores: int = Field(default=12, description="Количество логических потоков")
    model: str = Field(default="CPU", description="Модель процессора")
    display_val: str = Field(default="0.0%", description="Отображаемое значение загрузки")
    display_cores: str = Field(default="6 Физических / 12 Потоков", description="Строка с ядрами и потоками")
    display_freq: str = Field(default="", description="Строка с частотой")
    timestamp: str = Field(default="", description="Временная метка снимка из базы данных")
    source: str = Field(default="telemetry.db", description="Источник данных")

