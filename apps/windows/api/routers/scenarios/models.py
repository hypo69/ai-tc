# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - models
# =============================================================================
# Description:
#   Pydantic-модели сценариев.
#   Вынесено из router_scenarios.py (этап 4 оптимизации).
#
# File: models.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers.scenarios
# Author: hypo69
# Copyright: c 2026 hypo69
# Updated: 2026-10-15 01:20:00
# =============================================================================

from __future__ import annotations

from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
    Optional,
)

from pydantic import BaseModel, Field


__root__ = Path(__file__).resolve().parents[3]


# -----------------------------------------------------------------------------
# DTO Models
# -----------------------------------------------------------------------------

class ScenarioQuestionsConfig(BaseModel):
    """Конфигурация подсказок и быстрых вопросов для мини-чата."""
    description: str = Field(default="", description="Описание пула вопросов")
    prompts: List[str] = Field(default_factory=list, description="Список вопросов для динамической ротации")
    quick_buttons: List[Dict[str, str]] = Field(default_factory=list, description="Список кнопок быстрого доступа")


class ScenarioStepResult(BaseModel):
    """Результат выполнения отдельного шага сценария."""
    name: str = Field(description="Наименование шага проверки")
    status: str = Field(description="Статус шага: 'ok', 'warn', 'error', 'skipped'")
    duration_ms: float = Field(default=0.0, description="Время выполнения шага в миллисекундах")
    details: str = Field(default="", description="Подробное описание или результат проверки")
    recommendation: Optional[str] = Field(default=None, description="Рекомендация при предупреждении или ошибке")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Дополнительные структурированные данные")


class ScenarioRunResult(BaseModel):
    """Сводный результат прогона тестового сценария."""
    scenario_id: str = Field(description="Идентификатор сценария")
    title: str = Field(description="Отображаемое название сценария")
    status: str = Field(description="Общий статус сценария: 'ok', 'warn', 'error'")
    started_at: str = Field(description="Время запуска сценария (ISO 8601)")
    duration_ms: float = Field(description="Общее время выполнения в миллисекундах")
    total_steps: int = Field(description="Общее количество выполненных шагов")
    passed_steps: int = Field(description="Количество успешных шагов")
    warn_steps: int = Field(description="Количество шагов с предупреждением")
    failed_steps: int = Field(description="Количество проваленных шагов")
    steps: List[ScenarioStepResult] = Field(default_factory=list, description="Список результатов шагов")
    summary: str = Field(description="Итоговый экспертный вердикт на русском языке")


class ScenarioItem(BaseModel):
    """Метаданные сценария тестирования."""
    id: str = Field(description="Уникальный ID сценария")
    title: str = Field(description="Название сценария")
    description: str = Field(description="Описание сценария и решаемых задач")
    category: str = Field(description="Категория сценария (quick, diagnostics, logs, security, network, ai)")
    icon: str = Field(description="Иконка или эмодзи")
    recommended: bool = Field(default=False, description="Флаг рекомендации после установки")
    estimated_duration_sec: int = Field(default=3, description="Ориентировочное время выполнения в секундах")


class ScenarioRunRequest(BaseModel):
    """Запрос на запуск сценария."""
    scenario_id: str = Field(description="ID сценария ('quick_check', 'log_audit', 'system_inspector', 'windows_admin', 'network_test', 'ai_providers_check', 'all')")
    params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Дополнительные параметры выполнения")


class ScenarioCreatedSkillInfo(BaseModel):
    """Информация о сформированном навыке."""
    name: str = Field(description="Имя навыка (kebab-case)")
    title: str = Field(description="Человекочитаемый заголовок навыка")
    path: str = Field(description="Путь к файлу SKILL.md")
    description_ru: str = Field(description="Описание на русском языке")
    is_new: bool = Field(default=True, description="Был ли навык создан заново")


class ScenarioToolPlanInfo(BaseModel):
    """Метаданные сгенерированного плана инструмента."""
    tool_name: str = Field(description="Имя инструмента (kebab-case)")
    tool_title: str = Field(description="Человекочитаемый заголовок инструмента")
    description_ru: str = Field(description="Описание на русском языке")
    probe_type: str = Field(default="powershell", description="Тип зонда: 'powershell', 'collector', 'winapi'")
    collector_name: Optional[str] = Field(default=None, description="Имя коллектора")
    probe_script: Optional[str] = Field(default=None, description="PowerShell скрипт опроса")
    instructions: str = Field(default="", description="Пошаговый протокол выполнения")


class ScenarioSaveSkillRequest(BaseModel):
    """Запрос на сохранение подтвержденного пользователем инструмента в качестве навыка."""
    tool_name: str = Field(description="Имя навыка (kebab-case)")
    tool_title: str = Field(description="Человекочитаемый заголовок навыка")
    description_ru: str = Field(description="Описание назначения навыка")
    probe_type: str = Field(default="powershell", description="Тип зонда")
    collector_name: Optional[str] = Field(default=None, description="Имя коллектора")
    probe_script: Optional[str] = Field(default=None, description="PowerShell скрипт")
    instructions: str = Field(default="", description="Протокол выполнения")
    command_executed: Optional[str] = Field(default=None, description="Фактически выполненная команда")


class ScenarioRemediationActionInfo(BaseModel):
    """Метаданные доступного SafeOps-действия по исправлению проблемы."""
    action_id: str = Field(description="Уникальный идентификатор действия")
    action_type: str = Field(default="custom_command", description="Тип действия")
    title: str = Field(description="Человекочитаемое название действия")
    description: str = Field(default="", description="Описание назначения действия")
    target: str = Field(default="", description="Целевой объект (служба, файл, процесс)")
    risk: str = Field(default="caution", description="Уровень риска: safe, caution, critical")
    execution_command: str = Field(default="", description="Команда для выполнения")


class ScenarioExecuteFixRequest(BaseModel):
    """Запрос на выполнение SafeOps-исправления из мини-чата."""
    action_id: str = Field(description="ID действия")
    action_type: str = Field(default="custom_command", description="Тип действия")
    title: str = Field(default="", description="Название действия")
    description: str = Field(default="", description="Описание действия")
    target: str = Field(default="", description="Целевой объект")
    risk: str = Field(default="caution", description="Уровень риска")
    execution_command: str = Field(default="", description="Команда выполнения")
    confirmed_by_user: bool = Field(default=False, description="Подтверждено ли действие пользователем")


class ScenarioExecuteFixResponse(BaseModel):
    """Результат выполнения SafeOps-исправления."""
    action_id: str = Field(description="ID действия")
    status: str = Field(description="Статус: 'ok' или 'error'")
    executed: bool = Field(default=True, description="Было ли действие фактически выполнено")
    success: bool = Field(default=True, description="Успешно ли завершилось действие")
    message: str = Field(description="Сообщение о результате")
    error_message: Optional[str] = Field(default=None, description="Текст ошибки при сбое")


class ScenarioSaveApprovedResponseRequest(BaseModel):
    """Запрос на сохранение одобренного ответа мини-чата для обучения модели и RAG."""
    user_id: str = Field(default="tc_admin", description="Идентификатор пользователя")
    query: str = Field(description="Исходный запрос пользователя")
    chat_text: str = Field(description="Текст ответа модели")
    voice_text: Optional[str] = Field(default="", description="Текст для озвучки")
    system_context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Контекст системы и выполненных команд")
    tags: Optional[List[str]] = Field(default_factory=lambda: ["tc", "diagnostics", "training"], description="Категории и теги")


class ScenarioSaveApprovedResponseResponse(BaseModel):
    """Результат сохранения ответа для обучения модели."""
    status: str = Field(default="ok", description="Статус: 'ok' или 'error'")
    message: str = Field(description="Пользовательское сообщение о результате")
    file_saved: Optional[str] = Field(default=None, description="Имя сохраненного файла или статус")


class ScenarioChatRequest(BaseModel):
    """Запрос в мини-чат интеллектуального помощника сценариев."""
    message: str = Field(description="Текст запроса или вопроса на естественном языке")
    conversation_id: Optional[str] = Field(default=None, description="Идентификатор диалога")
    auto_create_skill: bool = Field(default=False, description="Автоматически генерировать навык без подтверждения")
    keep_context: bool = Field(default=False, description="Сохранять и учитывать контекст предыдущих сообщений диалога")
    use_rag: bool = Field(default=True, description="Использовать базу знаний RAG для поиска контекста")


class ScenarioChatResponse(BaseModel):
    """Ответ мини-чата сценариев с результатом выполнения и метаданными навыка."""
    reply: str = Field(description="Форматированный ответ в Markdown")
    command_executed: Optional[str] = Field(default=None, description="Выполненная системная команда или скрипт")
    created_skill: Optional[ScenarioCreatedSkillInfo] = Field(default=None, description="Данные о созданном/обновленном навыке")
    generated_prompt: Optional[str] = Field(default=None, description="Сформированный промпт, переданный языковой модели")
    tool_plan: Optional[ScenarioToolPlanInfo] = Field(default=None, description="Метаданные плана инструмента для ручного сохранения")
    remediation_actions: List[ScenarioRemediationActionInfo] = Field(default_factory=list, description="Список доступных действий по исправлению")
    raw_data: Optional[Any] = Field(default=None, description="Сырые структурированные данные")
    agents_used: List[Dict[str, Any]] = Field(default_factory=list, description="Список задействованных агентов и модулей")
    knowledge_used: List[Dict[str, Any]] = Field(default_factory=list, description="Список задействованных источников знаний и артефактов")
    status: str = Field(default="ok", description="Статус обработки: 'ok', 'warn', 'error'")


class DAGStartRequest(BaseModel):
    """Запрос на запуск автономного сценария с графом выполнения (DAG)."""
    scenario_id: str = Field(description="Идентификатор сценария")
    title: Optional[str] = Field(default=None, description="Пользовательский заголовок сценария")
    probe_desc: Optional[str] = Field(default="Опрос телеметрии и поиск навыков в WikiLLM", description="Описание шага PROBE")
    action_desc: Optional[str] = Field(default="Применение исправлений конфигурации хоста", description="Описание шага ACTION")
    requires_confirmation: bool = Field(default=True, description="Требовать паузу и подтверждение администратора")
    confirmation_msg: Optional[str] = Field(default=None, description="Текст подтверждения для администратора")
    context_data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Контекст сессии")


class DAGConfirmRequest(BaseModel):
    """Запрос на подтверждение действия администратором (Human-in-the-loop)."""
    action: str = Field(description="Действие администратора: 'approve' (разрешить) или 'reject' (отклонить)")


