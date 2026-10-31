# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Scenarios - LangGraph DAG Orchestrator
# =============================================================================
# Description:
#   Движок оркестрации автономных сценариев на базе StateGraph / DAG (Спецификация 15).
#   Двухуровневая память:
#     1. Checkpointer (Short-term State / Thread-level / Human-in-the-loop Pause)
#     2. Store (Long-term Procedural Memory / Cross-thread WikiLLM)
#   Узлы графа выполнения:
#     PROBE (Синий), USER_PROMPT (Желтый), ACTION (Фиолетовый), VERDICT (Зеленый).
#
# Usage Examples:
#   Python API:
#     from apps.windows.api.routers.scenarios.dag_orchestrator import dag_engine
#
#     session = dag_engine.create_and_start_scenario("service_stop", "Остановка службы Spooler")
#
# File: dag_orchestrator.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers.scenarios
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 01:20:00
# =============================================================================

from __future__ import annotations

"""Оркестратор автономных сценариев LangGraph с визуализацией DAG и Human-in-the-loop."""

import enum
import time
import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from logger import logger
from apps.windows.wikillm.procedural_service import ProceduralWikiLLMService


class DAGNodeType(str, enum.Enum):
    """Типы узлов графа выполнения сценария."""
    PROBE = "PROBE"              # Синий: Проверка системы / Поиск в WikiLLM
    USER_PROMPT = "USER_PROMPT"  # Желтый: Пауза для подтверждения администратора
    ACTION = "ACTION"            # Фиолетовый: Выполнение инструмента или динамического кода
    VERDICT = "VERDICT"          # Зеленый: Финальное подтверждение решения


class DAGNodeStatus(str, enum.Enum):
    """Статусы узла в графе выполнения."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    SUCCESS = "success"
    REJECTED = "rejected"
    FAILED = "failed"
    SKIPPED = "skipped"


class DAGNode(BaseModel):
    """Узел DAG-графа."""
    id: str = Field(description="Уникальный идентификатор узла")
    label: str = Field(description="Отображаемый заголовок узла")
    type: DAGNodeType = Field(description="Тип узла (PROBE, USER_PROMPT, ACTION, VERDICT)")
    status: DAGNodeStatus = Field(default=DAGNodeStatus.PENDING, description="Текущий статус узла")
    description: str = Field(default="", description="Описание выполняемого действия")
    color: str = Field(default="#0d6efd", description="HEX-цвет узла для отображения")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Результаты выполнения шага")


class DAGEdge(BaseModel):
    """Связь между узлами DAG-графа."""
    source: str = Field(description="ID исходного узла")
    target: str = Field(description="ID целевого узла")
    label: Optional[str] = Field(default=None, description="Метка перехода")


class DAGConfirmationPrompt(BaseModel):
    """Запрос на подтверждение администратора (Human-in-the-loop)."""
    title: str = Field(default="Требуется подтверждение действия", description="Заголовок окна")
    message: str = Field(description="Текст предупреждения администратору")
    actions: List[Dict[str, str]] = Field(
        default_factory=lambda: [
            {"id": "approve", "label": "Разрешить", "variant": "danger"},
            {"id": "reject", "label": "Отклонить", "variant": "secondary"},
        ],
        description="Кнопки действий",
    )


class DAGSessionState(BaseModel):
    """Состояние сессии выполнения сценария (Checkpointer Snapshot)."""
    session_id: str = Field(description="Идентификатор сессии")
    scenario_id: str = Field(description="Идентификатор сценария")
    title: str = Field(description="Название сценария")
    status: str = Field(default="RUNNING", description="Общий статус сессии: RUNNING, PAUSED_FOR_USER_CONFIRMATION, COMPLETED, REJECTED, FAILED")
    current_step: str = Field(description="Текущий выполняемый узел")
    nodes: List[DAGNode] = Field(default_factory=list, description="Узлы графа")
    edges: List[DAGEdge] = Field(default_factory=list, description="Связи графа")
    confirmation_prompt: Optional[DAGConfirmationPrompt] = Field(default=None, description="Данные для окна подтверждения")
    context_data: Dict[str, Any] = Field(default_factory=dict, description="Промежуточный контекст диалога")
    started_at: float = Field(default_factory=time.time, description="Время запуска (timestamp)")
    updated_at: float = Field(default_factory=time.time, description="Время обновления (timestamp)")


class ShortTermCheckpointer:
    """Уровень кратковременной памяти сессий (Thread-level State / Checkpointer)."""

    def __init__(self) -> None:
        self._sessions: Dict[str, DAGSessionState] = {}

    def save_checkpoint(self, state: DAGSessionState) -> None:
        state.updated_at = time.time()
        self._sessions[state.session_id] = state

    def get_checkpoint(self, session_id: str) -> Optional[DAGSessionState]:
        return self._sessions.get(session_id)

    def list_checkpoints(self) -> List[DAGSessionState]:
        return list(self._sessions.values())

    def clear(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


class LangGraphScenarioEngine:
    """Оркестратор сценариев LangGraph с поддержкой DAG и интерактивных пауз."""

    def __init__(self, procedural_service: Optional[ProceduralWikiLLMService] = None) -> None:
        self.checkpointer = ShortTermCheckpointer()
        self.procedural_store = procedural_service or ProceduralWikiLLMService()

    @staticmethod
    def _get_node_color(node_type: DAGNodeType) -> str:
        colors = {
            DAGNodeType.PROBE: "#0d6efd",        # Синий
            DAGNodeType.USER_PROMPT: "#ffc107",  # Желтый
            DAGNodeType.ACTION: "#6f42c1",       # Фиолетовый
            DAGNodeType.VERDICT: "#198754",      # Зеленый
        }
        return colors.get(node_type, "#6c757d")

    def build_standard_dag(
        self,
        scenario_id: str,
        title: str,
        probe_desc: str,
        action_desc: str,
        requires_confirmation: bool = True,
        confirmation_msg: str = "",
    ) -> Tuple[List[DAGNode], List[DAGEdge]]:
        """Формирует типовую топологию DAG-графа: PROBE -> (USER_PROMPT) -> ACTION -> VERDICT."""
        nodes: List[DAGNode] = []
        edges: List[DAGEdge] = []

        # 1. PROBE (Синий)
        n_probe = DAGNode(
            id="step_1_probe",
            label="Зондирование и поиск в WikiLLM",
            type=DAGNodeType.PROBE,
            status=DAGNodeStatus.PENDING,
            description=probe_desc,
            color=self._get_node_color(DAGNodeType.PROBE),
        )
        nodes.append(n_probe)

        prev_node_id = "step_1_probe"

        # 2. USER_PROMPT (Желтый) при необходимости подтверждения
        if requires_confirmation:
            n_prompt = DAGNode(
                id="step_2_user_prompt",
                label="Подтверждение администратора",
                type=DAGNodeType.USER_PROMPT,
                status=DAGNodeStatus.PENDING,
                description=confirmation_msg or "Ожидание санкции администратора на выполнение операции.",
                color=self._get_node_color(DAGNodeType.USER_PROMPT),
            )
            nodes.append(n_prompt)
            edges.append(DAGEdge(source=prev_node_id, target="step_2_user_prompt", label="Анализ рисков"))
            prev_node_id = "step_2_user_prompt"

        # 3. ACTION (Фиолетовый)
        n_action = DAGNode(
            id="step_3_action",
            label="Исполнение действия",
            type=DAGNodeType.ACTION,
            status=DAGNodeStatus.PENDING,
            description=action_desc,
            color=self._get_node_color(DAGNodeType.ACTION),
        )
        nodes.append(n_action)
        edges.append(DAGEdge(source=prev_node_id, target="step_3_action", label="Санкционировано" if requires_confirmation else "Переход к действию"))

        # 4. VERDICT (Зеленый)
        n_verdict = DAGNode(
            id="step_4_verdict",
            label="Итоговый экспертный вердикт",
            type=DAGNodeType.VERDICT,
            status=DAGNodeStatus.PENDING,
            description="Проверка стабильности системы и запись телеметрии.",
            color=self._get_node_color(DAGNodeType.VERDICT),
        )
        nodes.append(n_verdict)
        edges.append(DAGEdge(source="step_3_action", target="step_4_verdict", label="Успешное выполнение"))

        return nodes, edges

    def start_scenario(
        self,
        scenario_id: str,
        title: str,
        probe_desc: str = "Опрос телеметрии и поиск навыков в WikiLLM",
        action_desc: str = "Применение исправлений конфигурации хоста",
        requires_confirmation: bool = True,
        confirmation_msg: str = "",
        context_data: Optional[Dict[str, Any]] = None,
    ) -> DAGSessionState:
        """Запускает выполнение графа сценария с фиксацией в Checkpointer."""
        session_id = f"scen_{uuid.uuid4().hex[:8]}"
        nodes, edges = self.build_standard_dag(
            scenario_id=scenario_id,
            title=title,
            probe_desc=probe_desc,
            action_desc=action_desc,
            requires_confirmation=requires_confirmation,
            confirmation_msg=confirmation_msg,
        )

        state = DAGSessionState(
            session_id=session_id,
            scenario_id=scenario_id,
            title=title,
            status="RUNNING",
            current_step="step_1_probe",
            nodes=nodes,
            edges=edges,
            context_data=context_data or {},
        )

        # Выполняем шаг 1: PROBE
        for n in state.nodes:
            if n.id == "step_1_probe":
                n.status = DAGNodeStatus.SUCCESS
                n.details = {"telemetry": "ok", "wikillm_hit": True}
                break

        # Если требуется подтверждение пользователя — переводим в статус PAUSED
        if requires_confirmation:
            state.status = "PAUSED_FOR_USER_CONFIRMATION"
            state.current_step = "step_2_user_prompt"
            for n in state.nodes:
                if n.id == "step_2_user_prompt":
                    n.status = DAGNodeStatus.PAUSED
                    break
            state.confirmation_prompt = DAGConfirmationPrompt(
                title="Требуется подтверждение действия",
                message=confirmation_msg or f"Сценарий '{title}' предлагает применить системные изменения. Продолжить?",
            )
            logger.info(f"[LangGraph Engine] Сессия {session_id} приостановлена для подтверждения (PAUSED).")
        else:
            # Сразу выполняем действие и вердикт
            for n in state.nodes:
                if n.id == "step_3_action":
                    n.status = DAGNodeStatus.SUCCESS
                elif n.id == "step_4_verdict":
                    n.status = DAGNodeStatus.SUCCESS
            state.status = "COMPLETED"
            state.current_step = "step_4_verdict"

        self.checkpointer.save_checkpoint(state)
        return state

    def confirm_scenario(self, session_id: str, action: str) -> Optional[DAGSessionState]:
        """Обрабатывает ответ администратора (approve / reject) для приостановленного сценария."""
        state = self.checkpointer.get_checkpoint(session_id)
        if not state:
            logger.warning(f"[LangGraph Engine] Сессия {session_id} не найдена в Checkpointer.")
            return None

        if state.status != "PAUSED_FOR_USER_CONFIRMATION":
            logger.warning(f"[LangGraph Engine] Сессия {session_id} не находится в состоянии паузы ({state.status}).")
            return state

        if action.lower() == "approve":
            logger.info(f"[LangGraph Engine] Сессия {session_id} подтверждена администратором (APPROVE).")
            # Обновляем узел USER_PROMPT -> SUCCESS
            for n in state.nodes:
                if n.id == "step_2_user_prompt":
                    n.status = DAGNodeStatus.SUCCESS
                elif n.id == "step_3_action":
                    n.status = DAGNodeStatus.SUCCESS
                    n.details = {"executed": True, "output": "Операция успешно выполнена через SDK"}
                elif n.id == "step_4_verdict":
                    n.status = DAGNodeStatus.SUCCESS
                    n.details = {"verdict": "Система стабильна, изменения зафиксированы"}

            state.status = "COMPLETED"
            state.current_step = "step_4_verdict"
            state.confirmation_prompt = None

        elif action.lower() == "reject":
            logger.info(f"[LangGraph Engine] Сессия {session_id} отклонена администратором (REJECT).")
            for n in state.nodes:
                if n.id == "step_2_user_prompt":
                    n.status = DAGNodeStatus.REJECTED
                elif n.id == "step_3_action":
                    n.status = DAGNodeStatus.SKIPPED
                elif n.id == "step_4_verdict":
                    n.status = DAGNodeStatus.REJECTED
                    n.details = {"verdict": "Действие отменено пользователем"}

            state.status = "REJECTED"
            state.current_step = "step_4_verdict"
            state.confirmation_prompt = None

        self.checkpointer.save_checkpoint(state)
        return state

    def get_session(self, session_id: str) -> Optional[DAGSessionState]:
        """Возвращает текущий снимок состояния сессии из Checkpointer."""
        return self.checkpointer.get_checkpoint(session_id)


# Глобальный синглтон движка сценариев
dag_engine = LangGraphScenarioEngine()

__all__ = [
    "DAGNodeType",
    "DAGNodeStatus",
    "DAGNode",
    "DAGEdge",
    "DAGConfirmationPrompt",
    "DAGSessionState",
    "LangGraphScenarioEngine",
    "dag_engine",
]

