# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows API - Interactive Scenario Agent Router
# =============================================================================
# Description:
#   Слой 7: Модуль пошагового диалогового агента сценариев со стейт-машиной
#   (Stateful Interactive Scenario Agent). Позволяет запускать многошаговые
#   сценарии с паузами на уточнение параметров у пользователя.
#
# Usage Examples:
#   POST /api/v1/interactive-agent/start
#   POST /api/v1/interactive-agent/sessions/{session_id}/reply
#   GET  /api/v1/interactive-agent/sessions/{session_id}
#
# File: router_interactive_agent.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-16 20:45:00
# =============================================================================

from __future__ import annotations

"""Модуль пошагового диалогового агента сценариев со стейт-машиной (Stateful Interactive Scenario Agent)."""

import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

try:
    from logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/interactive-agent", tags=["Interactive Scenario Agent"])


class ScenarioStep(BaseModel):
    """Модель шага интерактивного сценария."""

    step_id: str = Field(..., description="Строковый идентификатор шага")
    title: str = Field(..., description="Заголовок шага")
    description: str = Field(..., description="Подробное описание шага")
    step_type: str = Field(..., description="Тип шага: PROBE, USER_PROMPT, ACTION")
    status: str = Field(default="PENDING", description="Статус: PENDING, RUNNING, WAITING_INPUT, COMPLETED, FAILED")
    prompt_for_user: Optional[str] = Field(default=None, description="Текст вопроса к пользователю")
    input_field_type: Optional[str] = Field(default=None, description="Тип поля ввода: text, password, select")
    input_options: Optional[List[str]] = Field(default=None, description="Опции выбора")
    result_summary: Optional[str] = Field(default=None, description="Результат выполнения шага")


class ScenarioSession(BaseModel):
    """Модель сессии выполнения интерактивного сценария."""

    session_id: str = Field(..., description="Уникальный идентификатор сессии")
    user_goal: str = Field(..., description="Исходная цель сценария, сформулированная пользователем")
    status: str = Field(default="INIT", description="Текущее состояние сессии: INIT, RUNNING, AWAITING_USER_INPUT, COMPLETED, FAILED")
    current_step_index: int = Field(default=0, description="Индекс текущего активного шага")
    steps: List[ScenarioStep] = Field(default_factory=list, description="Список шагов сценария")
    context_vars: Dict[str, Any] = Field(default_factory=dict, description="Словарь собранных контекстных переменных")
    created_at: float = Field(default_factory=time.time, description="Время создания сессии")


# Внутрипамятное хранилище сессий (Session Store)
SESSION_STORE: Dict[str, ScenarioSession] = {}


class StartAgentRequest(BaseModel):
    """Запрос на инициализацию сессии интерактивного агента."""

    user_prompt: str = Field(..., description="Текстовый запрос пользователя")


class UserReplyRequest(BaseModel):
    """Запрос ответа пользователя на текущий уточняющий шаг."""

    user_input: str = Field(..., description="Значение, введенное пользователем")
    step_id: Optional[str] = Field(default=None, description="Опциональный идентификатор шага")


@router.post("/start", response_model=ScenarioSession)
async def start_interactive_session(req: StartAgentRequest) -> ScenarioSession:
    """Инициализация нового пошагового сценария с генерацией цепочки рассуждений и проверок.

    Args:
        req: Запрос с описанием задачи на естественном языке.

    Returns:
        ScenarioSession: Созданный объект сессии со сформированными шагами.
    """
    session_id = str(uuid.uuid4())[:8]
    prompt_text = req.user_prompt.strip()

    # Декомпозиция типовой задачи (например, "Сделай ссылку на папку Public Docs...")
    steps = [
        ScenarioStep(
            step_id="step_1_locate_folder",
            title="Поиск исходной директории на локальном ПК",
            description="Проверка наличия целевой папки на рабочем столе текущего пользователя",
            step_type="PROBE",
        ),
        ScenarioStep(
            step_id="step_2_network_discovery",
            title="Сканирование компьютеров в локальной сети",
            description="Опрос активных хостов сети (NetBIOS/Arp/WinRM)",
            step_type="PROBE",
        ),
        ScenarioStep(
            step_id="step_3_credentials_prompt",
            title="Запрос учетных данных для подключения к ПК сети",
            description="Требуются права администратора сети для создания ярлыков на удаленных системах",
            step_type="USER_PROMPT",
            prompt_for_user="Введите логин и пароль администратора для подключения к удаленным ПК:",
            input_field_type="password",
        ),
        ScenarioStep(
            step_id="step_4_deploy_shortcuts",
            title="Создание ярлыков на рабочих столах целевых ПК",
            description="Подключение по WinRM/SMB и развертывание символической ссылки",
            step_type="ACTION",
        ),
    ]

    session = ScenarioSession(
        session_id=session_id,
        user_goal=prompt_text,
        status="RUNNING",
        steps=steps,
        context_vars={"user_prompt": prompt_text},
    )
    SESSION_STORE[session_id] = session

    # Выполняем Шаг 1 автоматически
    _execute_step_1(session)
    return session


def _execute_step_1(session: ScenarioSession) -> None:
    """Выполнение первого зондирующего шага и переход к уточнению.

    Args:
        session: Текущая активная сессия.
    """
    step1 = session.steps[0]
    step1.status = "COMPLETED"
    step1.result_summary = r"Папка 'Public Docs' не найдена по пути %USERPROFILE%\Desktop\Public Docs."

    # Переходим к шагу уточнения у пользователя
    prompt_step = ScenarioStep(
        step_id="step_1b_ask_folder",
        title="Уточнение пути к целевой папке",
        description="Папка не обнаружена по умолчанию. Укажите точный путь к целевой директории.",
        step_type="USER_PROMPT",
        status="WAITING_INPUT",
        prompt_for_user=r"Укажите полный путь к целевой папке (например, C:\PublicDocs или D:\Share):",
        input_field_type="text",
    )
    session.steps.insert(1, prompt_step)
    session.current_step_index = 1
    session.status = "AWAITING_USER_INPUT"


@router.post("/sessions/{session_id}/reply", response_model=ScenarioSession)
async def user_reply(session_id: str, req: UserReplyRequest) -> ScenarioSession:
    """Возобновление сессии после получения ответа от пользователя.

    Args:
        session_id: Уникальный идентификатор сессии.
        req: Ответ пользователя на уточняющий вопрос.

    Returns:
        ScenarioSession: Обновленный объект сессии со следующими шагами.
    """
    if session_id not in SESSION_STORE:
        raise HTTPException(status_code=404, detail="Сессия не найдена")

    session = SESSION_STORE[session_id]
    current_step = session.steps[session.current_step_index]

    # Сохраняем введенное значение
    current_step.result_summary = f"Пользователь указал: {req.user_input}"
    current_step.status = "COMPLETED"
    session.context_vars[current_step.step_id] = req.user_input

    # Переход к следующему шагу
    session.current_step_index += 1
    if session.current_step_index < len(session.steps):
        next_step = session.steps[session.current_step_index]
        if next_step.step_type == "USER_PROMPT":
            next_step.status = "WAITING_INPUT"
            session.status = "AWAITING_USER_INPUT"
        else:
            next_step.status = "RUNNING"
            # Симуляция выполнения
            next_step.status = "COMPLETED"
            next_step.result_summary = "Успешно найдено 4 активных узла в локальной сети: PC-OFFICE-01, PC-OFFICE-02..."
            session.current_step_index += 1
            if session.current_step_index < len(session.steps):
                session.steps[session.current_step_index].status = "WAITING_INPUT"
                session.status = "AWAITING_USER_INPUT"
            else:
                session.status = "COMPLETED"
    else:
        session.status = "COMPLETED"

    return session


@router.get("/sessions/{session_id}", response_model=ScenarioSession)
async def get_session_status(session_id: str) -> ScenarioSession:
    """Получение текущего состояния интерактивной сессии.

    Args:
        session_id: Идентификатор целевой сессии.

    Returns:
        ScenarioSession: Данные сессии и статус выполнения.
    """
    if session_id not in SESSION_STORE:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    return SESSION_STORE[session_id]


class UniversalAgentSolveRequest(BaseModel):
    """Запрос к универсальному саморасширяющемуся агенту."""
    query: str = Field(..., description="Абстрактный запрос оператора")
    model: Optional[str] = Field(default=None, description="Модель")


@router.post("/stream-solve")
async def stream_universal_solve(req: UniversalAgentSolveRequest):
    """Потоковое решение абстрактной задачи через UniversalLangChainAgent."""
    import json
    from fastapi.responses import StreamingResponse
    from apps.windows.sdk.core.universal_langchain_agent import UniversalLangChainAgent

    agent = UniversalLangChainAgent(model_name=req.model)

    async def event_generator():
        try:
            async for ev in agent.stream_solve(req.query):
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"[InteractiveAgent] Ошибка в stream-solve: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'text': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


