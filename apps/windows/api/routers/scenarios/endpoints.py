# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - endpoints
# =============================================================================
# Description:
#   Фабрика роутера сценариев.
#   Вынесено из router_scenarios.py (этап 4 оптимизации).
#
# File: endpoints.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers.scenarios
# Author: hypo69
# Copyright: c 2026 hypo69
# Updated: 2026-10-15 01:20:00
# =============================================================================

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from logger import logger

__root__ = Path(__file__).resolve().parents[3]


import json
from .assistant import _execute_disk_benchmark_telemetry_step
from .assistant import _get_dynamic_tool_engine
from .assistant import _handle_scenario_chat
from .assistant import _run_disk_benchmark_scenario
from .catalog import AVAILABLE_SCENARIOS
from .dag_orchestrator import dag_engine, DAGSessionState
from .models import DAGConfirmRequest, DAGStartRequest
from .models import ScenarioChatRequest
from .models import ScenarioChatResponse
from .models import ScenarioCreatedSkillInfo
from .models import ScenarioExecuteFixRequest
from .models import ScenarioExecuteFixResponse
from .models import ScenarioItem
from .models import ScenarioQuestionsConfig
from .models import ScenarioRunRequest
from .models import ScenarioRunResult
from .models import ScenarioSaveApprovedResponseRequest
from .models import ScenarioSaveApprovedResponseResponse
from .models import ScenarioSaveSkillRequest
from .models import ScenarioStepResult
from .runners_basic import _run_log_audit_scenario
from .runners_basic import _run_quick_check_scenario
from .runners_system import _run_ai_providers_scenario
from .runners_system import _run_network_test_scenario
from .runners_system import _run_system_inspector_scenario
from .runners_system import _run_windows_admin_scenario
from .runners_update import _run_safe_update_guard_scenario


# -----------------------------------------------------------------------------
# Router Initialization
# -----------------------------------------------------------------------------

def init_router() -> APIRouter:
    """Инициализирует FastAPI роутер для управления сценариями тестирования.

    Returns:
        APIRouter: Настроенный роутер с префиксом /api/v1/scenarios.
    """
    router = APIRouter(prefix="/api/v1/scenarios", tags=["Test Computer Scenarios"])

    @router.get("", response_model=List[ScenarioItem])
    async def list_scenarios() -> List[ScenarioItem]:
        """Возвращает перечень доступных сценариев тестирования и аудита."""
        return [ScenarioItem(**sc) for sc in AVAILABLE_SCENARIOS]

    @router.post("/run", response_model=ScenarioRunResult)
    async def run_scenario(req: ScenarioRunRequest) -> ScenarioRunResult:
        """Запускает указанный тестовый сценарий и возвращает детальные результаты шагов."""
        scenario_id = req.scenario_id.lower().strip()

        if scenario_id in ("safe_update_guard", "update_guard", "update", "pre_update"):
            res = await _run_safe_update_guard_scenario()
        elif scenario_id == "quick_check":
            res = await _run_quick_check_scenario()
        elif scenario_id in ("log_audit", "logs_audit", "logs"):
            res = await _run_log_audit_scenario()
        elif scenario_id in ("system_inspector", "system", "hardware"):
            res = await _run_system_inspector_scenario()
        elif scenario_id in ("windows_admin", "windows", "security"):
            res = await _run_windows_admin_scenario()
        elif scenario_id in ("network_test", "network"):
            res = await _run_network_test_scenario()
        elif scenario_id in ("ai_providers_check", "ai"):
            res = await _run_ai_providers_scenario()
        elif scenario_id in ("disk_benchmark_audit", "disk_benchmark", "disk_speed", "disks"):
            return await _run_disk_benchmark_scenario()
        elif scenario_id == "all":
            # Выполняем объединенный прогон всех сценариев
            t0 = time.perf_counter()
            s_at = datetime.now(timezone.utc).isoformat()
            all_steps: List[ScenarioStepResult] = []

            for runner in [
                _run_quick_check_scenario,
                _run_log_audit_scenario,
                _run_system_inspector_scenario,
                _run_windows_admin_scenario,
                _run_network_test_scenario,
                _run_ai_providers_scenario,
                _run_disk_benchmark_scenario,
            ]:
                try:
                    res_inner = await runner()
                    all_steps.extend(res_inner.steps)
                except Exception as ex:
                    all_steps.append(ScenarioStepResult(
                        name=f"Сценарий {runner.__name__}",
                        status="error",
                        details=f"Исключение при выполнении: {ex}"
                    ))

            t_dur = (time.perf_counter() - t0) * 1000
            f_cnt = sum(1 for s in all_steps if s.status == "error")
            w_cnt = sum(1 for s in all_steps if s.status == "warn")
            p_cnt = sum(1 for s in all_steps if s.status == "ok")
            ov_status = "error" if f_cnt > 0 else ("warn" if w_cnt > 0 else "ok")

            return ScenarioRunResult(
                scenario_id="all",
                title="Комплексный прогон всех сценариев",
                status=ov_status,
                started_at=s_at,
                duration_ms=round(t_dur, 2),
                total_steps=len(all_steps),
                passed_steps=p_cnt,
                warn_steps=w_cnt,
                failed_steps=f_cnt,
                steps=all_steps,
                summary=f"Комплексный прогон завершен: успешно {p_cnt}, предупреждений {w_cnt}, ошибок {f_cnt}.",
            )
        else:
            raise HTTPException(status_code=400, detail=f"Неизвестный идентификатор сценария: '{req.scenario_id}'")

        # При каждом запуске любого сценария выполняем экспресс-бенчмарк всех дисков и сохраняем телеметрию
        disk_step = await _execute_disk_benchmark_telemetry_step()
        res.steps.append(disk_step)
        res.total_steps = len(res.steps)
        if disk_step.status == "ok":
            res.passed_steps += 1
        elif disk_step.status == "warn":
            res.warn_steps += 1
        elif disk_step.status == "error":
            res.failed_steps += 1
            res.status = "error"
        res.duration_ms = round(res.duration_ms + disk_step.duration_ms, 2)
        return res


    @router.post("/chat", response_model=ScenarioChatResponse)
    async def chat_scenario_assistant(req: ScenarioChatRequest) -> ScenarioChatResponse:
        """Интеллектуальный мини-чат сценариев: выполняет опрос системы или запрашивает LLM и генерирует навык."""
        if not req.message.strip():
            raise HTTPException(status_code=400, detail="Текст сообщения не может быть пустым.")
        return await _handle_scenario_chat(req)

    @router.post("/chat/stream")
    async def chat_scenario_assistant_stream(req: ScenarioChatRequest) -> StreamingResponse:
        """Потоковый SSE мини-чат сценариев: передает промежуточные этапы и результат в реальном времени."""
        if not req.message.strip():
            raise HTTPException(status_code=400, detail="Текст сообщения не может быть пустым.")

        engine = _get_dynamic_tool_engine()
        if not engine:
            raise HTTPException(status_code=500, detail="Движок DynamicWindowsToolEngine недоступен.")

        effective_conv_id = req.conversation_id if req.keep_context else None

        async def event_generator():
            try:
                async for evt in engine.process_query_stream(
                    query=req.message,
                    auto_create_skill=req.auto_create_skill,
                    conversation_id=effective_conv_id,
                    keep_context=req.keep_context,
                    use_rag=req.use_rag,
                ):
                    yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"
            except Exception as e:
                import traceback
                tb_str = traceback.format_exc()
                logger.error(f"Ошибка в chat_scenario_assistant_stream: {e}", exc_info=True)
                err_evt = {
                    "type": "error",
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "details": tb_str,
                }
                yield f"data: {json.dumps(err_evt, ensure_ascii=False)}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    @router.post("/chat/clear")
    async def clear_chat_session(req: ScenarioChatRequest) -> Dict[str, Any]:
        """Очищает контекст сессии диалога."""
        engine = _get_dynamic_tool_engine()
        if engine and req.conversation_id and req.conversation_id in engine.sessions:
            engine.sessions.pop(req.conversation_id, None)
        return {"status": "ok", "message": "Контекст сессии очищен"}

    @router.post("/save-skill", response_model=ScenarioCreatedSkillInfo)
    async def save_scenario_skill(req: ScenarioSaveSkillRequest) -> ScenarioCreatedSkillInfo:
        """Сохраняет подтвержденный пользователем инструмент в постоянный каталог навыков (.skills/ и .agents/skills/)."""
        engine = _get_dynamic_tool_engine()
        if not engine:
            raise HTTPException(status_code=500, detail="Движок DynamicWindowsToolEngine недоступен.")

        from apps.windows.sdk.core.dynamic_tool_engine import DynamicToolPlan
        plan = DynamicToolPlan(
            intent=req.tool_title,
            tool_name=req.tool_name,
            tool_title=req.tool_title,
            description_ru=req.description_ru,
            probe_type=req.probe_type,
            collector_name=req.collector_name,
            probe_script=req.probe_script,
            instructions=req.instructions or f"Выполнить системную команду: {req.command_executed or req.probe_script}",
        )
        res = engine.save_skill(plan, req.command_executed or req.probe_script)
        return ScenarioCreatedSkillInfo(
            name=res["name"],
            title=res["title"],
            path=res["path"],
            description_ru=res["description_ru"],
            is_new=res.get("is_new", True),
        )

    @router.post("/execute-fix", response_model=ScenarioExecuteFixResponse)
    async def execute_scenario_fix(req: ScenarioExecuteFixRequest) -> ScenarioExecuteFixResponse:
        """Безопасное выполнение SafeOps-исправления из интерфейса чата."""
        from apps.windows.sdk.core.models import ActionType, RemediationAction, RiskLevel
        from apps.windows.sdk.core.safe_executor import SafeExecutor

        executor = SafeExecutor()
        try:
            act_type = ActionType(req.action_type)
        except Exception:
            act_type = ActionType.CUSTOM_COMMAND

        try:
            r_level = RiskLevel(req.risk.lower())
        except Exception:
            r_level = RiskLevel.CAUTION

        action = RemediationAction(
            action_id=req.action_id,
            action_type=act_type,
            title=req.title or req.action_id,
            description=req.description,
            target=req.target,
            risk=r_level,
            execution_command=req.execution_command,
        )

        res_action = await asyncio.to_thread(executor.execute, action, req.confirmed_by_user)
        if res_action.success:
            return ScenarioExecuteFixResponse(
                action_id=res_action.action_id,
                status="ok",
                executed=res_action.executed,
                success=True,
                message=f"Исправление '{res_action.title}' успешно применено.",
            )
        else:
            return ScenarioExecuteFixResponse(
                action_id=res_action.action_id,
                status="error",
                executed=res_action.executed,
                success=False,
                message=res_action.error_message or "Не удалось применить исправление.",
                error_message=res_action.error_message,
            )

    @router.get("/questions", response_model=ScenarioQuestionsConfig)
    async def get_scenario_questions() -> ScenarioQuestionsConfig:
        """Возвращает пул вопросов и быстрых кнопок из внешнего файла questions.json."""
        q_path = Path(__file__).resolve().parent.parent / "webgui" / "scenarios_tab" / "questions.json"
        if q_path.exists():
            try:
                data = json.loads(q_path.read_text(encoding="utf-8"))
                return ScenarioQuestionsConfig(**data)
            except Exception as e:
                logger.error(f"Ошибка чтения questions.json: {e}")
        return ScenarioQuestionsConfig(
            description="Default questions pool",
            prompts=[
                "Включи аудит процессов в памяти",
                "Дай полную информацию о подключенных принтерах",
                "Какие мыши были подключены к этому компьютеру?",
                "Покажи список сетевых портов и активных соединений",
                "Проверь автозапуск и службы Windows",
                "Кто использует сеть?",
                "Проверь точки восстановления системы",
                "Найди давно не запускавшиеся программы",
                "Как расшарить папку с файлами",
            ],
            quick_buttons=[],
        )

    @router.post("/save-approved-response", response_model=ScenarioSaveApprovedResponseResponse)
    async def save_approved_scenario_response(req: ScenarioSaveApprovedResponseRequest) -> ScenarioSaveApprovedResponseResponse:
        """Сохраняет одобренный пользователем ответ мини-чата в базу TC для RAG и последующего тюнинга модели."""
        try:
            from src.ai.gemini.approved_responses_store import save_approved_response
            ok = save_approved_response(
                user_id=req.user_id,
                query=req.query,
                chat_text=req.chat_text,
                voice_text=req.voice_text or "",
                system_context=req.system_context or {},
                tags=req.tags or ["tc", "diagnostics", "training"],
            )
            if not ok:
                raise HTTPException(status_code=500, detail="Не удалось сохранить одобренный ответ в базу данных.")
            return ScenarioSaveApprovedResponseResponse(
                status="ok",
                message="Ответ успешно сохранён в базу знаний и датасет обучения модели (data/tc/approved_responses).",
                file_saved="ok"
            )
        except HTTPException:
            raise
        except Exception as ex:
            logger.error(f"Ошибка сохранения одобренного ответа TC: {ex}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(ex))

    @router.post("/dag/start", response_model=DAGSessionState)
    async def start_dag_scenario(req: DAGStartRequest) -> DAGSessionState:
        """Запускает автономный сценарий с графом выполнения (DAG) и поддержкой паузы."""
        title = req.title or f"Сценарий: {req.scenario_id}"
        state = dag_engine.start_scenario(
            scenario_id=req.scenario_id,
            title=title,
            probe_desc=req.probe_desc or "Опрос телеметрии и поиск навыков в WikiLLM",
            action_desc=req.action_desc or "Применение исправлений конфигурации хоста",
            requires_confirmation=req.requires_confirmation,
            confirmation_msg=req.confirmation_msg or f"Сценарий '{title}' требует подтверждения администратора.",
            context_data=req.context_data or {},
        )
        return state

    @router.get("/session/{session_id}", response_model=DAGSessionState)
    async def get_dag_session(session_id: str) -> DAGSessionState:
        """Возвращает снимок состояния сессии и графа DAG из Checkpointer."""
        state = dag_engine.get_session(session_id)
        if not state:
            raise HTTPException(status_code=404, detail=f"Сессия '{session_id}' не найдена в Checkpointer.")
        return state

    @router.post("/session/{session_id}/confirm", response_model=DAGSessionState)
    async def confirm_dag_session(session_id: str, req: DAGConfirmRequest) -> DAGSessionState:
        """Обрабатывает ответ администратора ('approve' или 'reject') и возобновляет сценарий."""
        state = dag_engine.confirm_scenario(session_id=session_id, action=req.action)
        if not state:
            raise HTTPException(status_code=404, detail=f"Сессия '{session_id}' не найдена.")
        return state

    @router.get("/sessions", response_model=List[DAGSessionState])
    async def list_dag_sessions() -> List[DAGSessionState]:
        """Возвращает список всех активных и сохраненных сессий сценариев."""
        return dag_engine.checkpointer.list_checkpoints()

    return router

