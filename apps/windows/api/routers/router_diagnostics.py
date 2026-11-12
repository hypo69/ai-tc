# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - Router Diagnostics
# =============================================================================
# Description:
#   Универсальный REST API эндпоинт для AI-диагностики, контекстного объяснения,
#   динамической генерации трех вопросов по теме промпта и чата с обогащением WikiLLM.
#
# Usage Examples:
#   Python API:
#     from apps.windows.api.routers.router_diagnostics import (
#         DiagnosticExplainRequest,
#         DiagnosticSuggestQuestionsRequest,
#         DiagnosticChatRequest,
#     )
#
# File: router_diagnostics.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 13:08:00
# =============================================================================

from __future__ import annotations
"""Универсальный REST API эндпоинт для AI-диагностики, контекстного объяснения,
динамической генерации вопросов и чат-обогащения базы знаний WikiLLM."""

import asyncio
import json
import os
import re
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from header import __root__
from logger import logger
from utils.command_validator import run_safe


class DiagnosticExplainRequest(BaseModel):
    """Запрос на AI-объяснение элемента таблицы."""
    table_type: str = Field(default="generic", description="Тип таблицы (software, process, service, task, network, registry, user, website, rag_doc, disk)")
    panel_id: Optional[str] = Field(default=None, description="Идентификатор вызывающей панели интерфейса (например, panel-winadmin-users)")
    system_instruction: Optional[str] = Field(default=None, description="Пользовательская или переопределенная системная инструкция для LLM")
    title: str = Field(default="", description="Основное имя или заголовок элемента")
    subtitle: Optional[str] = Field(default="", description="Вторичный заголовок (издатель, путь, IP, статус)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Набор ключевых атрибутов записи")
    raw_data: Optional[str] = Field(default="", description="Сырая строка команды, пути или JSON")
    model: Optional[str] = Field(default=None, description="Опциональное имя конкретной модели")
    provider: Optional[str] = Field(default=None, description="Опциональный AI провайдер")
    web_search: bool = Field(default=True, description="Выполнять ли онлайн поиск для обогащения контекста")
    cache_only: bool = Field(default=False, description="Проверить только кэш/базу знаний WikiLLM без вызова LLM")
    force_refresh: bool = Field(default=False, description="Принудительно запросить модель ИИ для улучшения/обновления кэша")
    prompt: Optional[str] = Field(default=None, description="Опциональный пользовательский промпт / вопрос")
    question: Optional[str] = Field(default=None, description="Опциональный вопрос администратора")
    lang: Optional[str] = Field(default=None, description="Язык интерфейса и шаблона промпта (ru, en, etc.)")
    use_wikillm: bool = Field(default=True, description="Использовать ли локальную базу знаний WikiLLM для проверки и обогащения")
    wikillm_general_data: Optional[Dict[str, Any]] = Field(default=None, description="Справочные данные из базы знаний WikiLLM")


class DiagnosticExplainResponse(BaseModel):
    """Структурированный ответ AI-диагностики элемента таблицы."""
    summary: str = Field(description="Краткое понятное описание назначения элемента или анализ ресурсов")
    developer: str = Field(default="Неизвестен", description="Разработчик / принадлежность / вендор")
    category: str = Field(default="Системный компонент", description="Категория элемента")
    security_verdict: str = Field(description="Оценка безопасности, легитимности и рисков")
    performance_impact: str = Field(description="Влияние на производительность и ресурсы")
    recommendation: str = Field(description="Практическая рекомендация эксперта")
    action_steps: List[str] = Field(default_factory=list, description="Пошаговые рекомендуемые действия")
    developer_advice: Optional[str] = Field(
        default="",
        description="Советы разработчику: технические детали, API/SDK, ключи реестра, WMI и скрипты автоматизации"
    )
    suggested_quick_questions: List[str] = Field(
        default_factory=list,
        description="3-4 контекстных быстрых вопроса для кнопок id='uai-chat-quick-buttons'"
    )
    canonical_key: Optional[str] = Field(default=None, description="Канонический ключ сущности в WikiLLM")
    source: str = Field(default="gemini", description="Источник ответа (wikillm / gemini / heuristic / not_found)")
    is_verified: bool = Field(default=False, description="Признак верификации знания в WikiLLM")
    general_summary: Optional[str] = Field(default=None, description="Общие справочные данные о программе из WikiLLM")
    has_wikillm_general_data: bool = Field(default=False, description="Признак наличия общих данных о программе в WikiLLM")
    telemetry_data: Optional[Dict[str, Any]] = Field(default=None, description="Расширенная телеметрия текущего инстанса процесса")


class DiagnosticSuggestQuestionsRequest(BaseModel):
    """Запрос на составление 3 контекстных вопросов администратора."""
    table_type: str = Field(default="generic", description="Тип таблицы / сущности")
    panel_id: Optional[str] = Field(default=None, description="Идентификатор панели")
    title: str = Field(default="", description="Заголовок сущности")
    subtitle: Optional[str] = Field(default="", description="Подзаголовок / контекст")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Метаданные")
    raw_data: Optional[str] = Field(default="", description="Сырые данные")
    model: Optional[str] = Field(default=None, description="Модель")
    provider: Optional[str] = Field(default=None, description="Провайдер")
    lang: Optional[str] = Field(default=None, description="Язык")
    force_refresh: bool = Field(default=False, description="Принудительно обновить список вопросов")
    use_wikillm: bool = Field(default=True, description="Использовать ли базу знаний WikiLLM для кэша быстрых вопросов")


class DiagnosticSuggestQuestionsResponse(BaseModel):
    """Ответ со списком 3 уникальных вопросов."""
    questions: List[str] = Field(description="Список ровно трех вопросов администратора")
    canonical_key: Optional[str] = Field(default=None, description="Канонический ключ WikiLLM")
    table_type: str = Field(description="Тип таблицы")
    source: str = Field(default="gemini", description="Источник генерации")


class DiagnosticChatRequest(BaseModel):
    """Запрос в интерактивный чат с автоматическим обогащением базы знаний WikiLLM."""
    name: Optional[str] = Field(default=None, description="Имя / заголовок сущности (алиас title)")
    path: Optional[str] = Field(default=None, description="Путь / подзаголовок (алиас subtitle)")
    title: Optional[str] = Field(default=None, description="Основное имя или заголовок")
    subtitle: Optional[str] = Field(default=None, description="Вторичный заголовок")
    prompt: Optional[str] = Field(default=None, description="Вопрос пользователя (алиас question)")
    question: Optional[str] = Field(default=None, description="Вопрос пользователя")
    table_type: Optional[str] = Field(default=None, description="Тип таблицы / сущности")
    panel_id: Optional[str] = Field(default=None, description="Идентификатор панели")
    canonical_key: Optional[str] = Field(default=None, description="Канонический ключ WikiLLM")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Метаданные")
    cmdline: Optional[str] = Field(default=None, description="Командная строка или сырые данные")
    raw_data: Optional[str] = Field(default=None, description="Сырые данные")
    stream: bool = Field(default=False, description="Потоковая передача ответа (SSE)")
    model: Optional[str] = Field(default=None, description="Модель")
    provider: Optional[str] = Field(default=None, description="Провайдер")
    system_instruction: Optional[str] = Field(default=None, description="Пользовательская системная инструкция")
    force_refresh: bool = Field(default=False, description="Принудительно запросить модель минуя кэш ответов WikiLLM")
    enrich_wikillm: bool = Field(default=False, description="Обогащать ли базу знаний WikiLLM парой вопрос-ответ (по умолчанию False, дополнительные вопросы одноразовые)")
    use_wikillm: bool = Field(default=True, description="Использовать ли базу знаний WikiLLM для контекста диалога")


from apps.windows.api.diagnostics_prompt_manager import (
    DiagnosticPromptTemplate,
    prompt_manager,
)


class DiagnosticPromptUpdateRequest(BaseModel):
    """Запрос на обновление шаблона промпта для таблицы."""
    system_instruction: str = Field(description="Системная инструкция для LLM")
    prompt_template: str = Field(description="Шаблон текста промпта с переменными {title}, {subtitle}, {metadata}, {raw_data}")
    name: Optional[str] = Field(default=None, description="Опциональное отображаемое имя")
    description: Optional[str] = Field(default=None, description="Опциональное описание")


class DiagnosticExecuteCommandRequest(BaseModel):
    """Модель запроса на выполнение консольной команды через модальный AI-интерфейс."""
    command: str = Field(..., description="Команда для выполнения на хосте")
    timeout_sec: int = Field(default=35, ge=1, le=120, description="Тайм-аут выполнения команды в секундах")
    shell: str = Field(default="powershell", description="Используемая оболочка: powershell, pwsh, cmd")
    as_admin: bool = Field(default=False, description="Запуск с повышенными привилегиями администратора")


class DiagnosticExecuteCommandResponse(BaseModel):
    """Модель ответа выполнения команды PowerShell."""
    success: bool = Field(..., description="Флаг успешности завершения команды (код возврата 0)")
    returncode: int = Field(..., description="Код возврата процесса")
    stdout: str = Field(default="", description="Стандартный вывод команды")
    stderr: str = Field(default="", description="Поток ошибок команды")
    execution_time_ms: float = Field(default=0.0, description="Время выполнения в миллисекундах")
    command: str = Field(default="", description="Фактически выполненная команда")


def _is_stream_chunk_error(chunk: Optional[str]) -> bool:
    """Проверяет отдельный фрагмент потока (SSE chunk) на наличие системной ошибки провайдера/SDK.

    В отличие от _is_model_error, не выполняет проверку минимальной длины, так как
    валидные токены стриминга могут состоять из единичных символов или коротких слов.
    """
    if not chunk:
        return False
    t = chunk.strip()
    lower = t.lower()
    if lower.startswith(("streaming error:", "model error:", "error: [", "traceback (most recent call last):")):
        return True
    if lower.startswith("{") and '"error"' in lower and ('"code"' in lower or '"message"' in lower):
        return True
    stream_error_markers = (
        "все api ключи исчерпаны",
        "resourceexhausted",
        "resource_exhausted",
        "429 too many requests",
        "quota exceeded",
        "rate limit exceeded",
        "harness process exited unexpectedly",
        "503 service unavailable",
        "service unavailable",
        "сбой ответа модели",
    )
    return any(marker in lower for marker in stream_error_markers)


def _is_model_error(text: Optional[str]) -> bool:
    """Проверяет, содержит ли итоговый текст ответа маркеры ошибки языковой модели или провайдера."""
    if not text:
        return True
    t = text.strip()
    if len(t) < 15:
        return True
    lower = t.lower()
    error_markers = (
        "streaming error:",
        "model error:",
        "все api ключи исчерпаны",
        "service unavailable",
        "503 service unavailable",
        "this model is currently experiencing high demand",
        "resourceexhausted",
        "resource_exhausted",
        "429 too many requests",
        "quota exceeded",
        "rate limit",
        "api_key_invalid",
        "harness process exited unexpectedly",
        "ошибка провайдера",
        "сбой ответа модели",
        "данный компонент выполняет стандартные задачи подсистемы",
        "экспертное заключение по сущности",
    )
    if any(marker in lower for marker in error_markers):
        return True
    if lower.startswith("{") and '"error"' in lower and ('"code"' in lower or '"message"' in lower):
        return True
    return False


def _extract_and_parse_json(text: str) -> tuple[Optional[Any], Optional[Exception]]:
    """Надежное извлечение и парсинг JSON из ответа языковой модели.

    Поддерживает:
    - Снятие markdown-блоков ```json ... ``` и ``` ... ```;
    - Поиск валидных границ внешних скобок {...} и [...];
    - Устойчивость к неэкранированным переводам строк и управляющим символам (strict=False);
    - Санитизацию висячих запятых (trailing commas).

    Args:
        text (str): Сырой ответ модели.

    Returns:
        tuple[Optional[Any], Optional[Exception]]: Кортеж (распарсенный объект, ошибка парсинга при неудаче).
    """
    if not text:
        return None, ValueError("Пустой ответ модели для парсинга JSON")

    cleaned = text.strip()

    # 1. Извлечение из Markdown-блока ```json ... ``` или ``` ... ```
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    # 2. Поиск внешних скобок (объект или список)
    first_brace = cleaned.find("{")
    first_bracket = cleaned.find("[")

    candidates: List[str] = []
    if first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
        last_brace = cleaned.rfind("}")
        if last_brace > first_brace:
            candidates.append(cleaned[first_brace:last_brace + 1])
    elif first_bracket != -1:
        last_bracket = cleaned.rfind("]")
        if last_bracket > first_bracket:
            candidates.append(cleaned[first_bracket:last_bracket + 1])

    if not candidates:
        candidates.append(cleaned)

    last_err: Optional[Exception] = None
    for cand in candidates:
        # Попытка 1: стандартный строгий парсер
        try:
            return json.loads(cand), None
        except Exception as e:
            last_err = e

        # Попытка 2: нестрогий парсер (разрешает неэкранированные \n, \t и управляющие символы в строках)
        try:
            return json.loads(cand, strict=False), None
        except Exception as e:
            last_err = e

        # Попытка 3: удаление висячих запятых (trailing commas) перед закрывающими скобками
        cand_no_commas = re.sub(r",\s*([}\]])", r"\1", cand)
        try:
            return json.loads(cand_no_commas, strict=False), None
        except Exception as e:
            last_err = e

    return None, last_err

async def _collect_expanded_process_telemetry(
    req: DiagnosticExplainRequest,
    canonical_key: Optional[str] = None
) -> Dict[str, Any]:
    """Собирает расширенную телеметрию текущего инстанса процесса (Live Snapshot)."""
    target_pid: Optional[int] = None

    # 1. Поиск PID в metadata
    for pid_key in ("pid", "PID", "main_pid", "target_pid"):
        val = req.metadata.get(pid_key)
        if val is not None:
            try:
                target_pid = int(val)
                if target_pid > 0:
                    break
            except (ValueError, TypeError):
                pass

    # 2. Поиск PID в title или subtitle
    if not target_pid:
        m = re.search(r"[\s\[\(]+PID[:\s]*(\d+)[\s\]\)]*", f"{req.title} {req.subtitle or ''}", re.IGNORECASE)
        if m:
            try:
                target_pid = int(m.group(1))
            except (ValueError, TypeError):
                pass

    # 3. Поиск PID в raw_data
    raw_dict: Dict[str, Any] = {}
    if req.raw_data and req.raw_data.strip().startswith("{"):
        try:
            raw_dict = json.loads(req.raw_data)
            if not target_pid:
                for k in ("pid", "main_pid", "PID"):
                    if raw_dict.get(k):
                        target_pid = int(raw_dict[k])
                        break
        except Exception:
            pass

    # 4. Если PID не найден, ищем активный процесс по имени
    clean_proc_name = ""
    if canonical_key and canonical_key.startswith("process:"):
        clean_proc_name = canonical_key.replace("process:", "").strip().lower()
    elif req.title:
        m_exe = re.search(r"([a-zA-Z0-9_\-\.]+\.exe)", f"{req.title} {req.subtitle or ''}", re.IGNORECASE)
        if m_exe:
            clean_proc_name = m_exe.group(1).lower()
        else:
            clean_proc_name = req.title.split()[0].strip().lower()

    if not target_pid and clean_proc_name:
        try:
            import psutil
            for p in psutil.process_iter(["pid", "name"]):
                try:
                    if p.info["name"] and p.info["name"].lower() == clean_proc_name:
                        target_pid = p.info["pid"]
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass

    telemetry: Dict[str, Any] = {}
    if target_pid and target_pid > 0:
        try:
            from apps.windows.api.routers.router_telemetry import get_process_deep_history
            deep_hist = await get_process_deep_history(target_pid)
            if hasattr(deep_hist, "model_dump"):
                telemetry = deep_hist.model_dump()
            elif isinstance(deep_hist, dict):
                telemetry = dict(deep_hist)
        except Exception as deep_ex:
            logger.debug(f"[RouterDiagnostics] get_process_deep_history({target_pid}) fallback: {deep_ex}")

    # Резервный опрос SQLite
    if not telemetry and target_pid:
        try:
            from apps.windows.telemetry.sqlite import TelemetryStorage
            storage = TelemetryStorage.get_instance(read_only=True)
            snap = storage.get_process_pid_snapshot(pid=target_pid)
            if snap:
                telemetry = dict(snap)
        except Exception:
            pass

    # Базовый срез телеметрии при отсутствии прямого доступа
    if not telemetry:
        telemetry = {
            "pid": target_pid or "-",
            "process_name": clean_proc_name or req.title,
            "executable_path": req.metadata.get("exe_path") or req.metadata.get("executable") or raw_dict.get("exe_path"),
            "command_line": req.metadata.get("command_line") or req.metadata.get("cmdline") or raw_dict.get("command_line"),
            "cpu_percent": float(req.metadata.get("cpu_percent") or raw_dict.get("cpu_percent") or 0.0),
            "memory_working_set_mb": float(req.metadata.get("memory_working_set_mb") or req.metadata.get("memory_mb") or raw_dict.get("memory_mb") or 0.0),
            "memory_private_bytes_mb": float(req.metadata.get("memory_private_bytes_mb") or raw_dict.get("memory_private_bytes_mb") or 0.0),
            "handles_count": int(req.metadata.get("handles_count") or req.metadata.get("handles") or raw_dict.get("handles") or 0),
            "thread_count": int(req.metadata.get("thread_count") or req.metadata.get("threads") or raw_dict.get("num_threads") or 1),
            "active_sockets_count": int(req.metadata.get("active_sockets_count") or req.metadata.get("active_sockets") or 0),
            "user_name": req.metadata.get("username") or raw_dict.get("username"),
        }

    # Обогащаем ключами из metadata, если они не были заполнены
    for m_key in ("memory_working_set_mb", "memory_private_bytes_mb", "memory_peak_working_set_mb", "handles_count", "thread_count", "active_sockets_count"):
        if m_key in req.metadata and req.metadata[m_key] is not None and not telemetry.get(m_key):
            telemetry[m_key] = req.metadata[m_key]

    # Подгрузка недавней истории телеметрии (сэмплы процесса во времени)
    try:
        from apps.windows.telemetry.sqlite import TelemetryStorage
        storage = TelemetryStorage.get_instance(read_only=True)
        if target_pid and target_pid > 0:
            hist_rows = storage.get_process_history(pid=target_pid, limit=10)
            if hist_rows:
                telemetry["recent_telemetry_history"] = [
                    {
                        "timestamp": r.get("created_at") or r.get("timestamp"),
                        "cpu_percent": r.get("cpu_percent", 0.0),
                        "memory_mb": r.get("memory_mb", 0.0),
                        "handles": r.get("num_handles", 0),
                        "threads": r.get("num_threads", 0),
                    }
                    for r in hist_rows[:10]
                ]
    except Exception as h_err:
        logger.debug(f"[RouterDiagnostics] Не удалось подгрузить историю телеметрии: {h_err}")

    # Обогащаем данными о группе процессов, если это сводная группа
    if raw_dict.get("subprocesses") or raw_dict.get("instance_count", 1) > 1 or req.metadata.get("is_group"):
        subs = raw_dict.get("subprocesses") or []
        telemetry["is_process_group"] = True
        telemetry["group_instance_count"] = raw_dict.get("instance_count") or len(subs) or 1
        telemetry["group_total_memory_mb"] = raw_dict.get("total_memory_mb") or req.metadata.get("total_memory_mb")
        telemetry["group_total_cpu_percent"] = raw_dict.get("total_cpu_percent") or req.metadata.get("total_cpu_percent")
        telemetry["group_total_threads"] = raw_dict.get("total_threads") or req.metadata.get("total_threads")
        if subs:
            telemetry["subprocesses_summary"] = [
                {
                    "pid": s.get("pid"),
                    "memory_mb": s.get("memory_mb"),
                    "cpu_percent": s.get("cpu_percent"),
                    "threads": s.get("num_threads"),
                    "command_line": s.get("command_line") or s.get("cmdline"),
                }
                for s in subs[:15]
            ]

    return telemetry


# Памятный кэш для быстрых вопросов (предотвращает повторные вызовы LLM)
_QUESTIONS_CACHE: Dict[str, List[str]] = {}


def init_router() -> APIRouter:
    """Инициализирует и возвращает FastAPI роутер универсальной диагностики.

    Returns:
        APIRouter: Настроенный роутер с префиксом /api/v1/diagnostics.
    """
    router = APIRouter(prefix="/api/v1/diagnostics", tags=["Universal Diagnostics"])

    @router.get("/prompts", response_model=List[DiagnosticPromptTemplate])
    async def list_diagnostic_prompts() -> List[DiagnosticPromptTemplate]:
        """Возвращает список всех шаблонов промптов для таблиц системы."""
        return prompt_manager.list_templates()

    @router.get("/prompts/{table_type}", response_model=DiagnosticPromptTemplate)
    async def get_diagnostic_prompt(
        table_type: str,
        panel_id: Optional[str] = Query(None, description="Идентификатор панели для приоритетного поиска кастомного промпта"),
        lang: Optional[str] = Query(None, description="Язык шаблона (ru, en, etc.)")
    ) -> DiagnosticPromptTemplate:
        """Возвращает шаблон промпта для конкретного типа таблицы или панели."""
        return prompt_manager.get_template(table_type, panel_id=panel_id, lang=lang)

    @router.post("/prompts/{table_type}", response_model=DiagnosticPromptTemplate)
    async def save_diagnostic_prompt(
        table_type: str,
        req: DiagnosticPromptUpdateRequest,
        panel_id: Optional[str] = Query(None, description="Опциональный panel_id для изолированного сохранения для конкретной панели")
    ) -> DiagnosticPromptTemplate:
        """Сохраняет пользовательский шаблон промпта для типа таблицы или панели."""
        target_key = panel_id or table_type
        return prompt_manager.save_template(
            table_type=table_type,
            system_instruction=req.system_instruction,
            prompt_template=req.prompt_template,
            name=req.name,
            description=req.description,
            target_key=target_key,
        )

    @router.post("/prompts/{table_type}/reset", response_model=DiagnosticPromptTemplate)
    async def reset_diagnostic_prompt(
        table_type: str,
        panel_id: Optional[str] = Query(None, description="Опциональный panel_id для сброса шаблона конкретной панели")
    ) -> DiagnosticPromptTemplate:
        """Сбрасывает шаблон промпта к дефолтной системной версии."""
        target_key = panel_id or table_type
        return prompt_manager.reset_template(
            table_type=table_type,
            fallback_table_type=table_type,
            target_key=target_key
        )

    @router.post("/execute-powershell", response_model=DiagnosticExecuteCommandResponse)
    async def execute_diagnostic_powershell_command(
        req: DiagnosticExecuteCommandRequest,
    ) -> DiagnosticExecuteCommandResponse:
        """Выполняет команду на локальном хосте (PowerShell / pwsh / cmd) и возвращает подробный вывод.

        Команда исполняется в изолированном контексте с обходом ExecutionPolicy,
        с настраиваемым таймаутом, выбором оболочки и опциональным повышением привилегий (RunAs).

        Args:
            req: Запрос с текстом команды, оболочкой, таймаутом и флагом администратора.

        Returns:
            DiagnosticExecuteCommandResponse: Результат с кодом возврата, stdout, stderr и временем выполнения.

        Raises:
            HTTPException: При пустой команде.
        """
        raw_cmd = (req.command or "").strip()
        if not raw_cmd:
            raise HTTPException(status_code=400, detail="Команда не может быть пустой")

        start_time = time.perf_counter()
        shell_type = (req.shell or "powershell").strip().lower()

        def _run() -> DiagnosticExecuteCommandResponse:
            try:
                logger.info(f"Выполнение команды [{shell_type}, admin={req.as_admin}] из модального окна AI: {raw_cmd[:120]}")

                if req.as_admin:
                    # Выполнение с повышенными привилегиями через Start-Process -Verb RunAs
                    temp_dir = tempfile.gettempdir()
                    uid = uuid.uuid4().hex[:8]
                    out_file = os.path.join(temp_dir, f"uai_cmd_out_{uid}.txt")
                    wrapper_ps1 = os.path.join(temp_dir, f"uai_wrapper_{uid}.ps1")

                    if shell_type == "cmd":
                        inner = f'cmd.exe /c "{raw_cmd}"'
                    else:
                        inner = f'& {{ {raw_cmd} }}'

                    wrapper_code = f"""$ErrorActionPreference = 'Continue'
try {{
    {inner} *>&1 | Out-File -FilePath "{out_file}" -Encoding utf8
    $code = $LASTEXITCODE
    if ($null -eq $code) {{ $code = 0 }}
    exit $code
}} catch {{
    $_ | Out-File -FilePath "{out_file}" -Append -Encoding utf8
    exit 1
}}
"""
                    with open(wrapper_ps1, "w", encoding="utf-8") as f:
                        f.write(wrapper_code)

                    try:
                        proc = subprocess.run(
                            [
                                "powershell.exe",
                                "-NoProfile",
                                "-NonInteractive",
                                "-ExecutionPolicy",
                                "Bypass",
                                "-Command",
                                f"Start-Process powershell.exe -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File \"{wrapper_ps1}\"' -Verb RunAs -Wait -PassThru | ForEach-Object {{ exit $_.ExitCode }}",
                            ],
                            capture_output=True,
                            text=True,
                            encoding="oem",
                            errors="replace",
                            timeout=req.timeout_sec,
                        )
                        retcode = proc.returncode
                        out_text = ""
                        if os.path.exists(out_file):
                            try:
                                with open(out_file, "r", encoding="utf-8", errors="replace") as f:
                                    out_text = f.read()
                            except Exception:
                                pass

                        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
                        return DiagnosticExecuteCommandResponse(
                            success=(retcode == 0),
                            returncode=retcode,
                            stdout=out_text if retcode == 0 else (out_text or proc.stdout or ""),
                            stderr="" if retcode == 0 else (proc.stderr or out_text or ""),
                            execution_time_ms=elapsed_ms,
                            command=raw_cmd,
                        )
                    finally:
                        for p in (wrapper_ps1, out_file):
                            try:
                                if os.path.exists(p):
                                    os.remove(p)
                            except Exception:
                                pass

                # Стандартный непривилегированный запуск через модуль самопроверки run_safe
                safe_res = run_safe(
                    command=raw_cmd,
                    dry_run=False,
                    timeout_sec=req.timeout_sec,
                    shell=shell_type,
                    as_admin=False,
                    enforce_error_visibility=True,
                )
                elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
                err_text = safe_res.get("stderr") or ""
                if safe_res.get("warnings"):
                    warn_prefix = "\n".join(f"[Предупреждение]: {w}" for w in safe_res["warnings"])
                    err_text = f"{warn_prefix}\n{err_text}".strip()

                return DiagnosticExecuteCommandResponse(
                    success=safe_res.get("success", False),
                    returncode=safe_res.get("returncode", 0),
                    stdout=safe_res.get("stdout") or "",
                    stderr=err_text,
                    execution_time_ms=elapsed_ms,
                    command=safe_res.get("sanitized_command") or raw_cmd,
                )
            except subprocess.TimeoutExpired:
                elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
                logger.warning(f"Таймаут выполнения команды ({req.timeout_sec} сек): {raw_cmd[:80]}")
                return DiagnosticExecuteCommandResponse(
                    success=False,
                    returncode=-1,
                    stdout="",
                    stderr=f"Превышен таймаут выполнения команды ({req.timeout_sec} сек)",
                    execution_time_ms=elapsed_ms,
                    command=raw_cmd,
                )
            except Exception as ex:
                elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
                logger.error(f"Сбой выполнения команды: {ex}")
                return DiagnosticExecuteCommandResponse(
                    success=False,
                    returncode=-2,
                    stdout="",
                    stderr=f"Ошибка запуска процесса: {str(ex)}",
                    execution_time_ms=elapsed_ms,
                    command=raw_cmd,
                )

        return await asyncio.to_thread(_run)

    def _resolve_diagnostic_model(requested_model: Optional[str] = None, web_search: bool = False) -> str:
        """Определяет модель для диагностики из запроса или активного файла конфигурации.

        Если модель не указана явно в запросе и не найдена в конфигурации,
        выбрасывает HTTPException(400) согласно стандартам разработки (запрет скрытого хардкода).

        Args:
            requested_model: Модель, переданная в запросе.
            web_search: Флаг использования веб-поиска.

        Returns:
            str: Имя валидной модели.

        Raises:
            HTTPException: Если модель не передана и не определена в конфигурации.
        """
        if requested_model and requested_model.strip():
            m = requested_model.strip()
            if m.startswith("gemini_cli:"):
                return m.split(":", 1)[1]
            return m

        # Поиск активного конфигурационного файла
        cfg_env = os.getenv("AIWINDOWSADMIN_CONFIG") or os.getenv("CONFIG_FILE")
        active_path: Optional[Path] = None
        if cfg_env:
            p = Path(cfg_env)
            active_path = p if p.is_absolute() else (__root__ / cfg_env)

        candidates = [
            active_path,
            __root__ / "apps" / "windows" / "config.json",
            __root__ / "config.json",
        ]

        for candidate in candidates:
            if candidate and candidate.exists():
                try:
                    with open(candidate, "r", encoding="utf-8") as f:
                        cfg = json.load(f)

                    # 1. Если включен web_search, проверяем секцию web_search
                    if web_search:
                        ws_cfg = cfg.get("web_search", {})
                        if isinstance(ws_cfg, dict) and ws_cfg.get("gemini_model"):
                            val = str(ws_cfg["gemini_model"]).strip()
                            if val:
                                return val

                    # 2. Проверяем ai_providers_and_models_configuration
                    ai_p_cfg = cfg.get("ai_providers_and_models_configuration", {})
                    if isinstance(ai_p_cfg, dict):
                        if ai_p_cfg.get("default_model"):
                            val = str(ai_p_cfg["default_model"]).strip()
                            if val:
                                return val
                        providers = ai_p_cfg.get("providers", {})
                        if isinstance(providers, dict):
                            gemini_p = providers.get("gemini", {})
                            if isinstance(gemini_p, dict) and gemini_p.get("model"):
                                val = str(gemini_p["model"]).strip()
                                if val:
                                    return val

                    # 3. Проверяем секцию ai
                    ai_sec = cfg.get("ai", {})
                    if isinstance(ai_sec, dict):
                        if ai_sec.get("default_model"):
                            val = str(ai_sec["default_model"]).strip()
                            if val:
                                return val
                        if ai_sec.get("model"):
                            val = str(ai_sec["model"]).strip()
                            if val:
                                return val
                        providers = ai_sec.get("providers", {})
                        if isinstance(providers, dict):
                            gemini_p = providers.get("gemini", {})
                            if isinstance(gemini_p, dict) and gemini_p.get("model"):
                                val = str(gemini_p["model"]).strip()
                                if val:
                                    return val
                except Exception as e:
                    logger.debug(f"[router_diagnostics] Ошибка чтения конфигурации {candidate}: {e}")

        # Если модель не указана и не найдена в конфиге - выбрасываем ошибку (Fail-Fast)
        raise HTTPException(
            status_code=400,
            detail="Модель AI не указана в запросе и не настроена в конфигурации (default_model / web_search.gemini_model)."
        )

    def _format_error_detail(err: Any) -> Dict[str, Any]:
        """Извлекает структурированную информацию об ошибке в виде JSON-словаря для возврата клиенту."""
        if isinstance(err, dict):
            return err if "error" in err else {"error": err}
        err_str = str(err).strip()
        if err_str.startswith("Model error:"):
            err_str = err_str[len("Model error:"):].strip()
        # Поиск встроенного JSON в строке ошибки
        if "{" in err_str and "}" in err_str:
            try:
                start_idx = err_str.find("{")
                end_idx = err_str.rfind("}") + 1
                parsed = json.loads(err_str[start_idx:end_idx])
                if isinstance(parsed, dict):
                    return parsed if "error" in parsed else {"error": parsed}
            except Exception:
                pass
        return {
            "error": {
                "code": 502,
                "status": "MODEL_ERROR",
                "message": err_str,
            }
        }




    @router.post("/explain", response_model=DiagnosticExplainResponse)
    async def explain_table_item(req: DiagnosticExplainRequest) -> DiagnosticExplainResponse:
        """Генерирует AI-объяснение и оценку для выбранного элемента таблицы."""
        # 1. Вычисляем канонический ключ для базы знаний WikiLLM
        canonical_key: Optional[str] = None
        try:
            from apps.windows.wikillm.normalizer import CanonicalKeyNormalizer
            canonical_key = CanonicalKeyNormalizer.compute_key_from_parts(
                table_type=req.table_type,
                title=req.title,
                subtitle=req.subtitle or "",
            )
        except Exception as e:
            logger.debug(f"Ошибка вычисления канонического ключа WikiLLM: {e}")

        # 2. Проверяем наличие верифицированного знания в локальной базе WikiLLM
        is_process_type = (
            req.table_type.lower() in ("process", "proc")
            or (canonical_key and canonical_key.startswith("process:"))
            or (req.panel_id and ("process" in req.panel_id.lower() or "top-proc" in req.panel_id.lower()))
        )

        wikillm_entity = None
        dev_text = req.subtitle or "Неизвестен"
        sec_text = "Проверено в базе знаний WikiLLM"
        dev_advice = ""
        matched_key = canonical_key

        if getattr(req, "use_wikillm", True) and canonical_key and not getattr(req, "force_refresh", False):
            try:
                from apps.windows.wikillm.router import get_engine
                engine = get_engine()
                candidate_keys = [canonical_key]
                if "security_event:" in canonical_key:
                    candidate_keys.append(canonical_key.replace("security_event:", "windows_event:Security:"))
                    candidate_keys.append(canonical_key.replace("security_event:", "generic:"))
                elif "windows_event:" in canonical_key:
                    parts = canonical_key.split(":")
                    if len(parts) >= 3:
                        candidate_keys.append(f"security_event:{parts[2]}")

                eid_m = re.search(r"\b(4\d{3}|1\d{3}|7\d{3}|\d{3,6})\b", canonical_key)
                if eid_m:
                    eid_val = eid_m.group(1)
                    if eid_val == "4624":
                        candidate_keys.extend(["security_event:4624_-_successful_logon", "generic:4624_-_successful_logon"])
                    else:
                        candidate_keys.append(f"security_event:{eid_val}")

                entity = None
                matched_key = canonical_key
                for cand in candidate_keys:
                    candidate_ent = engine.storage.get_entity(cand)
                    if candidate_ent and (candidate_ent.provenance_source.value == "documented" or any(c.verified for c in candidate_ent.claims)):
                        entity = candidate_ent
                        matched_key = cand
                        break

                if entity:
                    wikillm_entity = entity
                    rec_text = "Оставить без изменений."
                    dev_advice = ""
                    for c in entity.claims:
                        if "Рекомендация:" in c.statement:
                            rec_text = c.statement.replace("Рекомендация:", "").strip()
                        elif "Советы разработчику:" in c.statement:
                            dev_advice = c.statement.replace("Советы разработчику:", "").strip()
                        elif "developer_advice" in c.statement.lower():
                            dev_advice = c.statement.strip()

                    actions = [s.title for s in entity.diagnostic_info.remediation_steps] if entity.diagnostic_info else []
                    sec_text = entity.diagnostic_info.symptoms[0] if entity.diagnostic_info and entity.diagnostic_info.symptoms else "Проверено в базе знаний WikiLLM"
                    dev_text = entity.diagnostic_info.related_components[0] if entity.diagnostic_info and entity.diagnostic_info.related_components else req.subtitle or "Верифицировано"

                    # Для процессов: если запрошена ТОЛЬКО проверка кэша (cache_only), возвращаем общие данные.
                    # Но если запрашивается полноценный анализ (not cache_only), не прерываем выполнение!
                    # Сохраняем wikillm_entity и переходим к запросу анализа live-параметров процесса моделью.
                    if req.cache_only or not is_process_type:
                        logger.info(f"[WikiLLM] Мгновенный ответ из базы знаний для '{matched_key}' (верифицировано)")
                        return DiagnosticExplainResponse(
                            summary=entity.summary,
                            developer=dev_text,
                            category=entity.category,
                            security_verdict=sec_text,
                            performance_impact="В пределах нормы (из базы знаний WikiLLM)",
                            recommendation=rec_text,
                            action_steps=actions or ["Действий не требуется."],
                            developer_advice=dev_advice,
                            canonical_key=matched_key,
                            source="wikillm",
                            is_verified=True,
                            general_summary=entity.summary,
                            has_wikillm_general_data=True,
                        )
            except Exception as e:
                logger.debug(f"Проверка WikiLLM пропущена: {e}")

        # Если запрошена только проверка кэша базы знаний и запись не найдена
        if req.cache_only:
            return DiagnosticExplainResponse(
                summary="",
                developer="",
                category="",
                security_verdict="",
                performance_impact="",
                recommendation="",
                action_steps=[],
                canonical_key=canonical_key,
                source="not_found",
                is_verified=False,
                has_wikillm_general_data=False,
            )

        # Сбор расширенной телеметрии для процессов
        expanded_telemetry: Optional[Dict[str, Any]] = None
        if is_process_type:
            expanded_telemetry = await _collect_expanded_process_telemetry(req, canonical_key)

        # Получаем соответствующий шаблон промпта для типа таблицы с приоритетом panel_id
        tmpl = prompt_manager.get_template(req.table_type, panel_id=req.panel_id, lang=req.lang)
        sys_instruction = req.system_instruction.strip() if (req.system_instruction and req.system_instruction.strip()) else tmpl.system_instruction

        if is_process_type and wikillm_entity and expanded_telemetry:
            # Кардинально обновленная логика: общие данные уже есть в WikiLLM.
            # Запрашиваем у модели исключительно анализ текущего потребления и состояния ресурсов процесса по расширенной телеметрии.
            sys_instruction = (
                "Ты — ведущий эксперт по мониторингу производительности и профилированию процессов Windows (Windows Performance & Resource Analyst). "
                "Твоя задача — провести глубокий анализ текущего потребления и состояния ресурсов запущенного процесса на основе предоставленной детальной телеметрии. "
                "Общие сведения о назначении программы и разработчике уже известны из базы знаний WikiLLM. "
                "НЕ ОПИСЫВАЙ заново, что это за программа! Сконцентрируйся исключительно на анализе текущих параметров, эффективности, утечек, нагрузке на подсистемы и состоянии процесса. "
                "Отвечай строго в формате чистого JSON на русском языке."
            )
            prompt = f"""[ОБЩИЕ ДАННЫЕ ПРОЦЕССА ИЗ БАЗЫ ЗНАНИЙ WIKILLM]:
- Исполняемый файл: {wikillm_entity.name}
- Разработчик / Вендор: {dev_text}
- Категория: {wikillm_entity.category}
- Назначение / Описание программы: {wikillm_entity.summary}
- Базовая оценка доверия и безопасности: {sec_text}

[АКТУАЛЬНАЯ ТЕЛЕМЕТРИЯ ТЕКУЩЕГО ИНСТАНСА ПРОЦЕССА (EXPANDED RUNTIME TELEMETRY JSON)]:
{json.dumps(expanded_telemetry, ensure_ascii=False, indent=2)}

[ЗАДАНИЕ НА АНАЛИЗ ТЕКУЩИХ ПАРАМЕТРОВ И СОСТОЯНИЯ РЕСУРСОВ]:
ВНИМАНИЕ: Описание того, что это за процесс, разработчик и его общее назначение УЖЕ ИЗВЕСТНЫ из базы знаний WikiLLM (приведены выше).
НЕ ПОВТОРЯЙ и НЕ ОПИСЫВАЙ заново, что это за программа!
Твоя задача — провести СТРОГО АНАЛИЗ ТЕКУЩИХ ПАРАМЕТРОВ, ПОТРЕБЛЕНИЯ И СОСТОЯНИЯ РЕСУРСОВ этого процесса на основе предоставленной расширенной телеметрии:
1. Оцени текущее потребление ресурсов: нагрузка на процессор (CPU: {expanded_telemetry.get('cpu_percent', 0)}%), оперативная память (Working Set: {expanded_telemetry.get('memory_working_set_mb', 0)} МБ, Private Bytes: {expanded_telemetry.get('memory_private_bytes_mb', 0)} МБ, Peak: {expanded_telemetry.get('memory_peak_working_set_mb', 0)} МБ, Page Faults: {expanded_telemetry.get('memory_page_faults_total', 0)}), дескрипторы ({expanded_telemetry.get('handles_count', 0)}), потоки ({expanded_telemetry.get('thread_count', 1)}), дисковый ввод-вывод (чтение/запись МБ и операций), сетевые сокеты и соединения ({expanded_telemetry.get('active_sockets_count', 0)} сокетов).
2. Соответствует ли текущая нагрузка нормальному поведению данного типа ПО?
3. Есть ли признаки утечек памяти (memory leak), зависания в бесконечном цикле, взрывного роста дескрипторов, I/O thrashing или скрытой сетевой активности?
4. Сформулируй вердикт по ресурсам и дай конкретные практические рекомендации администратору (нужна ли оптимизация, перезапуск, изменение приоритета, завершение процесса при простое, или ресурсы потребляются штатно).

Верни СТРОГО валидный JSON следующей схемы:
{{
  "summary": "Анализ текущего потребления и состояния ресурсов: подробная оценка работы процесса (PID {expanded_telemetry.get('pid', '-')}), оценка нагрузки на CPU ({expanded_telemetry.get('cpu_percent', 0)}%) и память (WS: {expanded_telemetry.get('memory_working_set_mb', 0)} MB, Private: {expanded_telemetry.get('memory_private_bytes_mb', 0)} MB), оценка дескрипторов ({expanded_telemetry.get('handles_count', 0)}) и потоков ({expanded_telemetry.get('thread_count', 1)}). Диагностика текущего поведения.",
  "developer": "{dev_text}",
  "category": "{wikillm_entity.category}",
  "performance_impact": "Детальный срез по подсистемам: ЦП, ОЗУ, Дисковый ввод-вывод (чтение/запись МБ и IOPS), Сетевой трафик и сокеты, Дескрипторы ОС.",
  "security_verdict": "Анализ безопасности текущей сессии: путь запуска, учетная запись пользователя, активные сетевые сокеты, порождение дочерних процессов.",
  "recommendation": "Четкая практическая рекомендация системному администратору по управлению ресурсами процесса (штатная работа / требуется оптимизация / рекомендуется перезапуск / ограничить приоритет / завершить при простое).",
  "action_steps": ["Рекомендованное действие 1", "Рекомендованное действие 2"]
}}
"""
        elif is_process_type and expanded_telemetry:
            # Общих данных в WikiLLM пока нет: запрашиваем и общую справочную информацию (что это, для чего, назначение, применение), и динамический анализ ресурсов
            sys_instruction = (
                "Ты — ведущий системный архитектор Windows, эксперт по внутреннему устройству ОС (Windows Internals) и аналитик производительности. "
                "В базе знаний WikiLLM пока нет справочной информации об этой программе. "
                "Твоя задача состоит из двух обязательных уровней: "
                "1. Собрать полную общеописательную справочную информацию о программе: что это за ПО, для чего создано, его главное назначение в Windows, сценарии и области применения, официальный разработчик/вендор и базовое доверие. Это описание будет сохранено в базе знаний WikiLLM. "
                "2. Провести детальный экспертный анализ текущего потребления и состояния ресурсов запущенного инстанса процесса по предоставленной телеметрии и истории сэмплов. "
                "Отвечай строго в формате чистого JSON на русском языке."
            )
            prompt = f"""[АКТУАЛЬНАЯ ТЕЛЕМЕТРИЯ И ИСТОРИЯ ПРОЦЕССА (EXPANDED RUNTIME TELEMETRY JSON)]:
{json.dumps(expanded_telemetry, ensure_ascii=False, indent=2)}

[ЗАДАНИЕ ДЛЯ ЭКСПЕРТА ПО ПРОЦЕССАМ И РЕСУРСАМ WINDOWS]:
В базе знаний WikiLLM пока нет справочной информации об этом процессе ({expanded_telemetry.get('process_name') or req.title}).
Выполни комплексный анализ, состоящий из двух ключевых уровней:

УРОВЕНЬ 1. ОБЩЕОПИСАТЕЛЬНАЯ СПРАВОЧНАЯ ИНФОРМАЦИЯ О ПРОГРАММЕ (для сохранения в WikiLLM):
- Что это за программа / исполняемый файл ({expanded_telemetry.get('process_name') or req.title})
- Для чего она создана, её главное назначение в экосистеме Windows
- Где и как она применяется (пользовательский интерфейс, фоновый агент, системная служба, компонент фреймворка, утилита)
- Точный официальный разработчик / вендор (например Microsoft Corporation, Google, Valve, etc.)
- Сформируй развернутое, емкое и структурированное описание в поле "general_summary" (без временных PID и сиюминутных цифр ОЗУ).

УРОВЕНЬ 2. АНАЛИЗ ТЕКУЩЕГО ПОТРЕБЛЕНИЯ И СОСТОЯНИЯ РЕСУРСОВ:
- Оценка текущего потребления ресурсов по телеметрии: CPU ({expanded_telemetry.get('cpu_percent', 0)}%), RAM Working Set ({expanded_telemetry.get('memory_working_set_mb', 0)} MB), Private Bytes ({expanded_telemetry.get('memory_private_bytes_mb', 0)} MB), Handles ({expanded_telemetry.get('handles_count', 0)}), Threads ({expanded_telemetry.get('thread_count', 1)}), сокеты ({expanded_telemetry.get('active_sockets_count', 0)}).
- Оценка динамики и стабильности по истории сэмплов (если есть).
- Оценка безопасности текущей сессии запуска (путь, права, сетевые соединения).
- Практическая рекомендация администратору и шаги действий.

Верни СТРОГО валидный JSON следующей схемы:
{{
  "general_summary": "Развернутая справочная информация о программе: что это за ПО, для чего создано, его назначение и применение в Windows, официальный вендор и легитимность (для фиксации в WikiLLM).",
  "summary": "Анализ текущего потребления и состояния ресурсов: подробная оценка работы инстанса (PID {expanded_telemetry.get('pid', '-')}), нагрузка на CPU ({expanded_telemetry.get('cpu_percent', 0)}%) и память (WS: {expanded_telemetry.get('memory_working_set_mb', 0)} MB, Private: {expanded_telemetry.get('memory_private_bytes_mb', 0)} MB), оценка дескрипторов ({expanded_telemetry.get('handles_count', 0)}) и потоков ({expanded_telemetry.get('thread_count', 1)}). Диагностика поведения.",
  "developer": "Официальный разработчик / вендор программы",
  "category": "Категория программы (Интерактивное приложение / Системная утилита / Фоновая служба / Компонент ОС)",
  "performance_impact": "Детальный срез по подсистемам: ЦП, ОЗУ, Диск, Сеть, Дескрипторы.",
  "security_verdict": "Оценка безопасности сессии и прав запуска.",
  "recommendation": "Практическая рекомендация администратору по ресурсам процесса.",
  "action_steps": ["Рекомендованное действие 1", "Рекомендованное действие 2"]
}}
"""
        else:
            prompt = tmpl.format_prompt(
                title=req.title,
                subtitle=req.subtitle or "",
                metadata=req.metadata,
                raw_data=req.raw_data or "",
            )
            eff_custom_q = (req.question or req.prompt or "").strip()
            if eff_custom_q:
                prompt += f"\n\n[Целевой вопрос / приоритетный аспект анализа от администратора]:\n{eff_custom_q}"

        prov = (req.provider or "gemini").lower().strip()
        model_name = _resolve_diagnostic_model(requested_model=req.model, web_search=req.web_search)

        try:
            async def _invoke_ai_model(prompt_text: str, current_sys_instruction: str, cfg: Dict[str, Any]) -> str:
                if prov == "gemini_cli":
                    from src.ai.providers.gemini_cli import GeminiCliChatBase
                    cli_agent = GeminiCliChatBase(model_id=model_name, system_prompt=current_sys_instruction)
                    return await cli_agent.ask(prompt_text)
                elif prov == "agy":
                    from src.ai.providers.agy import AgyChatBase
                    agy_agent = AgyChatBase(model_id=model_name, system_prompt=current_sys_instruction)
                    return await agy_agent.ask(prompt_text)
                else:
                    from src.ai.gemini.generative_ai import GoogleGenerativeAI
                    ai = GoogleGenerativeAI(
                        model_name=model_name,
                        system_instruction=current_sys_instruction,
                        generation_config=cfg,
                    )
                    try:
                        return await ai.ask(prompt_text, attempts=5, generation_config=cfg)
                    except Exception as g_err:
                        if cfg.get("use_google_search") and ("429" in str(g_err) or "RESOURCE_EXHAUSTED" in str(g_err)):
                            logger.warning("Google Search Grounding 429 quota reached, retrying without search grounding...")
                            return await ai.ask(prompt_text, attempts=5, generation_config={})
                        raise g_err

            gen_cfg: Dict[str, Any] = {}
            is_lite: bool = "lite" in model_name.lower()
            if req.web_search and not is_lite:
                gen_cfg["use_google_search"] = True

            resp_text: str = await _invoke_ai_model(prompt, sys_instruction, gen_cfg)

            if not resp_text:
                raise HTTPException(
                    status_code=502,
                    detail={"error": {"code": 204, "status": "EMPTY_RESPONSE", "message": "Модель ИИ вернула пустой ответ"}}
                )

            cleaned = resp_text.strip()
            # Проверка на прямое сообщение об ошибке от провайдера
            if cleaned.startswith("Model error:") or cleaned.startswith("Error:"):
                err_detail = _format_error_detail(cleaned)
                raise HTTPException(status_code=502, detail=err_detail)

            data, parse_err = _extract_and_parse_json(resp_text)

            # Если штатный парсер не справился — возвращаем модели ее ответ с ошибкой и просим вернуть валидный JSON
            if data is None and resp_text:
                logger.warning(
                    f"Штатный парсинг JSON ответа модели '{model_name}' завершился ошибкой: {parse_err}. "
                    f"Отправляем повторный запрос модели на исправление синтаксиса JSON..."
                )
                repair_prompt = (
                    f"Предыдущий ответ содержит синтаксическую ошибку JSON: {parse_err}.\n"
                    "Исправь ошибки синтаксиса (экранируй переводы строк \\n, спецсимволы, кавычки, закрой скобки) "
                    "и верни СТРОГО валидный JSON-объект без пояснений и без markdown-обёрток:\n\n"
                    f"{resp_text}"
                )
                repair_instruction = (
                    "Ты специализированный нормализатор JSON. "
                    "Твоя задача — исправить синтаксис JSON и вернуть только валидный JSON-документ."
                )
                try:
                    repaired_text = await _invoke_ai_model(repair_prompt, repair_instruction, {})
                    data, repair_err = _extract_and_parse_json(repaired_text)
                    if data is not None:
                        logger.info(f"JSON-ответ успешно исправлен и валидирован моделью '{model_name}'.")
                    else:
                        logger.warning(
                            f"Повторное исправление JSON моделью '{model_name}' не удалось: {repair_err}. "
                            f"Длина ответа: {len(repaired_text)}."
                        )
                except Exception as fix_ex:
                    logger.warning(f"Сбой при попытке повторного запроса к модели для исправления JSON: {fix_ex}")

            if data is None:
                logger.warning(
                    f"Ошибка парсинга JSON ответа модели '{model_name}': {parse_err}. "
                    f"Длина ответа: {len(resp_text)} символов. Полный ответ:\n{resp_text}"
                )
                raise HTTPException(
                    status_code=502,
                    detail={
                        "error": {
                            "code": 502,
                            "status": "INVALID_JSON",
                            "message": f"Не удалось разобрать JSON-ответ от модели: {parse_err}",
                            "raw_response": resp_text
                        }
                    }
                )

            if isinstance(data, dict):
                # Если сама модель вернула JSON с ошибкой
                if "error" in data:
                    raise HTTPException(status_code=502, detail=data)

                # Проверяем обязательное поле summary
                if not data.get("summary"):
                    raise HTTPException(
                        status_code=502,
                        detail={
                            "error": {
                                "code": 502,
                                "status": "MISSING_SUMMARY",
                                "message": "В ответе модели отсутствует обязательное поле 'summary'",
                                "model_response": data
                            }
                        }
                    )

                dev_advice = (
                    data.get("developer_advice")
                    or data.get("developer_tips")
                    or data.get("dev_advice")
                    or data.get("dev_guide")
                    or ""
                )
                if isinstance(dev_advice, (dict, list)):
                    dev_advice = json.dumps(dev_advice, ensure_ascii=False, indent=2)

                gen_sum = wikillm_entity.summary if wikillm_entity else data.get("general_summary")
                eff_dev = data.get("developer") or (dev_text if wikillm_entity else (req.subtitle or "Неизвестен"))
                eff_cat = data.get("category") or (wikillm_entity.category if wikillm_entity else "Диагностика")

                # Извлекаем чистое имя исполняемого файла процесса
                proc_file_clean = ""
                if is_process_type:
                    m_exe = re.search(r"([a-zA-Z0-9_\-\.]+\.exe)", f"{req.title} {canonical_key or ''} {req.subtitle or ''}", re.IGNORECASE)
                    if m_exe:
                        proc_file_clean = m_exe.group(1).lower()
                    elif canonical_key and canonical_key.startswith("process:"):
                        proc_file_clean = canonical_key.replace("process:", "").strip().lower()
                    elif req.title:
                        proc_file_clean = req.title.split()[0].strip().lower()

                # Автоматически сохраняем общеописательные данные процесса в WikiLLM, если их там еще не было
                auto_saved_to_wikillm = False
                if is_process_type and not wikillm_entity and gen_sum and len(gen_sum.strip()) >= 15:
                    try:
                        from apps.windows.wikillm.router import approve_knowledge as auto_approve_knowledge, ApproveKnowledgeRequest
                        proc_key_name = proc_file_clean or (canonical_key.replace("process:", "") if canonical_key else "process")
                        auto_approve_req = ApproveKnowledgeRequest(
                            canonical_key=f"process:{proc_key_name.lower()}",
                            title=proc_key_name,
                            developer=eff_dev,
                            category=eff_cat,
                            summary=gen_sum.strip(),
                            general_summary=gen_sum.strip(),
                            performance_impact="Штатный профиль приложения (из базы знаний WikiLLM)",
                            security_verdict=data.get("security_verdict") or "Легитимный процесс (верифицировано)",
                            recommendation="Оставить без изменений.",
                            action_steps=data.get("action_steps") or ["Действий не требуется."],
                            developer_advice=str(dev_advice) if dev_advice else "",
                            table_type="process",
                        )
                        await auto_approve_knowledge(auto_approve_req)
                        auto_saved_to_wikillm = True
                        logger.info(f"[WikiLLM] Общеописательная информация о процессе '{proc_key_name}' успешно автоматически зафиксирована в WikiLLM.")
                    except Exception as auto_save_ex:
                        logger.warning(f"[WikiLLM] Авто-сохранение общеописательных данных процесса в WikiLLM завершилось ошибкой: {auto_save_ex}")

                eff_canonical = f"process:{proc_file_clean.lower()}" if (is_process_type and proc_file_clean) else (matched_key if wikillm_entity else canonical_key)
                has_general = bool(wikillm_entity or auto_saved_to_wikillm or (is_process_type and gen_sum))
                is_ver = bool(wikillm_entity or auto_saved_to_wikillm)
                eff_source = "wikillm_resource_analysis" if (wikillm_entity or auto_saved_to_wikillm) else prov

                return DiagnosticExplainResponse(
                    summary=data.get("summary", ""),
                    developer=eff_dev,
                    category=eff_cat,
                    security_verdict=data.get("security_verdict", "Оценка безопасности завершена."),
                    performance_impact=data.get("performance_impact", "В пределах нормы."),
                    recommendation=data.get("recommendation", "Оставить как есть."),
                    action_steps=data.get("action_steps", ["Проверьте актуальность конфигурации."]),
                    developer_advice=str(dev_advice),
                    canonical_key=eff_canonical,
                    source=eff_source,
                    is_verified=is_ver,
                    general_summary=gen_sum,
                    has_wikillm_general_data=has_general,
                    telemetry_data=expanded_telemetry if is_process_type else None,
                )

            raise HTTPException(
                status_code=502,
                detail={"error": {"code": 502, "status": "INVALID_RESPONSE", "message": "Ответ модели не является объектом JSON"}}
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Ошибка вызова модели AI для '{req.title}': {e}", exc_info=True)
            err_detail = _format_error_detail(e)
            raise HTTPException(status_code=502, detail=err_detail)

    @router.post("/approve")
    @router.post("/wikillm/approve")
    async def approve_knowledge_endpoint(req: Dict[str, Any]) -> Dict[str, Any]:
        """Одобряет результат диагностики и фиксирует его в базе знаний WikiLLM."""
        from apps.windows.wikillm.router import approve_knowledge as wikillm_approve, ApproveKnowledgeRequest
        req_copy = dict(req)
        if req_copy.get("table_type") == "process" or (str(req_copy.get("canonical_key") or "").startswith("process:")):
            import re
            req_copy["title"] = re.sub(r"[\s\[\(]+PID[:\s]*\d+[\s\]\)]*", "", req_copy.get("title", ""), flags=re.IGNORECASE).strip()
            if req_copy.get("general_summary"):
                req_copy["summary"] = req_copy["general_summary"]
            req_copy["performance_impact"] = "Штатный профиль приложения (из базы знаний WikiLLM)"
        req_obj = ApproveKnowledgeRequest(**req_copy)
        return await wikillm_approve(req_obj)

    @router.post("/suggest-questions", response_model=DiagnosticSuggestQuestionsResponse)
    @router.post("/quick-questions", response_model=DiagnosticSuggestQuestionsResponse)
    async def suggest_quick_questions(req: DiagnosticSuggestQuestionsRequest) -> DiagnosticSuggestQuestionsResponse:
        """Составляет три актуальных уникальных вопроса по теме текущего промпта без сохранения в базе WikiLLM."""
        canonical_key: Optional[str] = None
        try:
            from apps.windows.wikillm.normalizer import CanonicalKeyNormalizer
            canonical_key = CanonicalKeyNormalizer.compute_key_from_parts(
                table_type=req.table_type,
                title=req.title,
                subtitle=req.subtitle or "",
            )
        except Exception as e:
            logger.debug(f"Ошибка вычисления канонического ключа WikiLLM: {e}")

        # Проверяем наличие вопросов в кэше памяти и в базе знаний WikiLLM
        if getattr(req, "use_wikillm", True) and canonical_key and not getattr(req, "force_refresh", False):
            if canonical_key in _QUESTIONS_CACHE:
                logger.info(f"[WikiLLM] Быстрые вопросы из кэша памяти для '{canonical_key}'")
                return DiagnosticSuggestQuestionsResponse(
                    questions=_QUESTIONS_CACHE[canonical_key],
                    canonical_key=canonical_key,
                    table_type=req.table_type,
                    source="wikillm_cache",
                )
            candidate_keys = []
            if "security_event:" in canonical_key:
                candidate_keys.append(canonical_key.replace("security_event:", "windows_event:Security:"))
                candidate_keys.append(canonical_key.replace("security_event:", "generic:"))
            for ck in candidate_keys:
                if ck in _QUESTIONS_CACHE:
                    return DiagnosticSuggestQuestionsResponse(
                        questions=_QUESTIONS_CACHE[ck],
                        canonical_key=canonical_key,
                        table_type=req.table_type,
                        source="wikillm_cache",
                    )
            try:
                from apps.windows.wikillm.router import get_engine
                engine = get_engine()
                for k_candidate in [canonical_key] + candidate_keys:
                    ent = engine.storage.get_entity(k_candidate)
                    if ent and ent.claims:
                        for clm in ent.claims:
                            if clm.statement.startswith("Быстрые вопросы:"):
                                raw_qs = clm.statement.replace("Быстрые вопросы:", "").strip()
                                cached_list = [q.strip() for q in raw_qs.split("|") if q.strip()]
                                if len(cached_list) >= 2:
                                    _QUESTIONS_CACHE[canonical_key] = cached_list
                                    logger.info(f"[WikiLLM] Быстрые вопросы из базы знаний для '{k_candidate}'")
                                    return DiagnosticSuggestQuestionsResponse(
                                        questions=cached_list,
                                        canonical_key=canonical_key,
                                        table_type=req.table_type,
                                        source="wikillm_entity",
                                    )
            except Exception:
                pass

        # Получаем соответствующий шаблон промпта
        tmpl = prompt_manager.get_template(req.table_type, panel_id=req.panel_id, lang=req.lang)
        q_prompt = tmpl.format_questions_prompt(
            title=req.title,
            subtitle=req.subtitle or "",
            metadata=req.metadata,
            raw_data=req.raw_data or "",
        )
        sys_instruction = (
            f"{tmpl.system_instruction}\n"
            "Твоя задача — составить ровно 3 уникальных, свежих и актуальных вопроса системного администратора по этой сущности. "
            "Каждый раз придумывай новые вопросы, не повторяйся. "
            "Отвечай СТРОГО в формате чистого JSON-массива из 3 строк: [\"Вопрос 1\", \"Вопрос 2\", \"Вопрос 3\"]."
        )

        prov = (req.provider or "gemini").lower().strip()
        try:
            model_name = _resolve_diagnostic_model(requested_model=req.model, web_search=False)
            import asyncio
            resp_text: str = ""

            if prov == "gemini_cli":
                from src.ai.providers.gemini_cli import GeminiCliChatBase
                cli_agent = GeminiCliChatBase(model_id=model_name, system_prompt=sys_instruction)
                resp_text = await asyncio.wait_for(cli_agent.ask(q_prompt), timeout=15.0)
            elif prov == "agy":
                from src.ai.providers.agy import AgyChatBase
                agy_agent = AgyChatBase(model_id=model_name, system_prompt=sys_instruction)
                resp_text = await asyncio.wait_for(agy_agent.ask(q_prompt), timeout=15.0)
            else:
                from src.ai.gemini.generative_ai import GoogleGenerativeAI
                ai = GoogleGenerativeAI(
                    model_name=model_name,
                    system_instruction=sys_instruction,
                )
                resp_text = await asyncio.wait_for(ai.ask(q_prompt, attempts=3), timeout=15.0)

            if resp_text and not resp_text.startswith("Model error:"):
                questions_list, _ = _extract_and_parse_json(resp_text)
                if isinstance(questions_list, list) and len(questions_list) > 0:
                        clean_qs = [str(q).strip().strip('"').strip("'") for q in questions_list if str(q).strip()][:3]
                        if len(clean_qs) >= 2:
                            if canonical_key:
                                _QUESTIONS_CACHE[canonical_key] = clean_qs
                                try:
                                    from apps.windows.wikillm.router import get_engine
                                    from apps.windows.wikillm.models import Claim, KnowledgeSource
                                    engine = get_engine()
                                    ent = engine.storage.get_entity(canonical_key)
                                    if ent:
                                        ent.claims.append(
                                            Claim(
                                                statement=f"Быстрые вопросы: {' | '.join(clean_qs)}",
                                                confidence=1.0,
                                                source=KnowledgeSource.DOCUMENTED,
                                                verified=True,
                                            )
                                        )
                                        engine.storage.save_entity(ent)
                                except Exception:
                                    pass
                            return DiagnosticSuggestQuestionsResponse(
                                questions=clean_qs,
                                canonical_key=canonical_key,
                                table_type=req.table_type,
                                source=prov,
                            )
        except Exception as err:
            logger.debug(f"Генерация вопросов через AI LLM ({prov}) завершилась fallback: {err}")

        # Качественный контекстный эвристический fallback
        fallback_qs = _generate_heuristic_questions(req)
        return DiagnosticSuggestQuestionsResponse(
            questions=fallback_qs,
            canonical_key=canonical_key,
            table_type=req.table_type,
            source="heuristic",
        )

    @router.post("/chat")
    @router.post("/chat/software-explain")
    async def chat_diagnostic_endpoint(req: DiagnosticChatRequest) -> Any:
        """Интерактивный диалог по сущности с обращением к LLM и обогащением базы знаний WikiLLM."""
        eff_title = req.title or req.name or "Неизвестная сущность"
        eff_subtitle = req.subtitle or req.path or ""
        eff_question = (req.question or req.prompt or "").strip()
        eff_raw = req.raw_data or req.cmdline or ""
        eff_table_type = req.table_type or "generic"

        if not eff_question:
            raise HTTPException(status_code=400, detail="Вопрос (question / prompt) не может быть пустым.")

        # Вычисляем канонический ключ сущности для WikiLLM
        canonical_key = req.canonical_key
        if not canonical_key:
            try:
                from apps.windows.wikillm.normalizer import CanonicalKeyNormalizer
                canonical_key = CanonicalKeyNormalizer.compute_key_from_parts(
                    table_type=eff_table_type,
                    title=eff_title,
                    subtitle=eff_subtitle,
                )
            except Exception:
                canonical_key = f"{eff_table_type}:{eff_title}"

        # Если eff_title представляет собой MD5-хэш или ID, восстанавливаем человекочитаемое имя
        if len(eff_title) == 32 and all(c in "0123456789abcdefABCDEF" for c in eff_title):
            readable = (
                req.metadata.get("name")
                or req.metadata.get("display_name")
                or req.metadata.get("app_name")
                or req.metadata.get("title")
                or req.metadata.get("Process")
                or req.metadata.get("Program")
            )
            if readable:
                eff_title = str(readable)

        # Считываем контекст сущности из WikiLLM для обогащения промпта (вопросы чата одноразовые)
        wikillm_summary = ""
        if getattr(req, "use_wikillm", True) and canonical_key:
            try:
                from apps.windows.wikillm.router import get_engine
                engine = get_engine()
                entity = engine.storage.get_entity(canonical_key)
                if entity:
                    if (not eff_title or eff_title == canonical_key) and entity.name:
                        eff_title = entity.name
                    wikillm_summary = f"- Данные WikiLLM: {entity.name} ({entity.category}). {entity.summary}\n"
            except Exception as e:
                logger.debug(f"Контекст WikiLLM для диалога пропущен: {e}")

        tmpl = prompt_manager.get_template(eff_table_type, panel_id=req.panel_id)
        base_instruction = (req.system_instruction or "").strip() or tmpl.system_instruction
        # Очищаем требование обязательного JSON-формата из шаблона для режима интерактивного диалога
        clean_instruction = re.sub(
            r"(?i)(отвечай\s+строго\s+в\s+формате\s+чистого\s+json[^\.\n]*[\.\n]?|respond\s+strictly\s+in\s+pure\s+json[^\.\n]*[\.\n]?)",
            "",
            base_instruction
        ).strip()
        sys_instruction = (
            f"{clean_instruction}\n\n"
            "Ты являешься экспертным системным консультантом Windows и инженером безопасности в среде AI Windows Admin.\n"
            "Тебе доступны данные системных подсистем: процессы (/api/v1/tc/processes), телеметрия (/api/v1/tc/status), "
            "форензика (/api/v1/system/diagnostics/forensics), инспекция ПО (/api/v1/software-scanner), журналы аудита (/api/v1/system-logs) и реестр (/api/v1/registry).\n"
            "ВАЖНЕЙШИЕ ПРАВИЛА ФОРМАТА В ЧАТЕ:\n"
            "- Отвечай как живой экспертный консультант — развернутым, структурированным текстом на русском языке с использованием Markdown (заголовки ###, списки, выделения **жирным**).\n"
            "- КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНЫ любые вступительные приветствия, самопрезентации и ритуальные фразы (например: «Приветствую...», «Здравствуйте...», «Как эксперт по...», «Как системный инженер...», «Я провел анализ...», «Я проанализировал представленные данные...»).\n"
            "- Начинай ответ СРАЗУ и строго с существа вопроса, фактов, технического анализа и выводов (без вежливых клише, прелюдий и самопредставлений).\n"
            "- КАТЕГОРИЧЕСКИ НЕ оборачивай свой ответ в JSON (не используй фигурные скобки { }, кавычки ключей, схемы 'analysis_report', 'technical_assessment' и т.д.).\n"
            "- Отвечай сразу прямым экспертным текстом диалога."
        )

        meta_str = '\n'.join([f'- {k}: {v}' for k, v in req.metadata.items()]) if req.metadata else '- Нет дополнительных метаданных'
        chat_prompt = (
            f"Контекст анализируемой сущности Windows:\n"
            f"Тип: {eff_table_type}\n"
            f"Имя / Заголовок: {eff_title}\n"
            f"Контекст / Путь: {eff_subtitle}\n"
            f"{wikillm_summary}"
            f"Метаданные:\n{meta_str}\n"
            f"Сырые данные / Телеметрия: {eff_raw}\n\n"
            f"[Вопрос системного администратора]:\n{eff_question}\n\n"
            f"Сформулируй исчерпывающий, структурированный экспертный ответ на русском языке в виде понятного диалогового текста (КАТЕГОРИЧЕСКИ НЕ используй JSON).\n"
            f"ВАЖНО: Ни в коем случае НЕ здоровайся («Приветствую», «Здравствуйте») и НЕ представляйся («Как эксперт...», «Я проанализировал...»). Сразу начинай с технического ответа по существу."
        )

        prov = (req.provider or "gemini").lower().strip()
        try:
            model_name = _resolve_diagnostic_model(requested_model=req.model, web_search=False)
        except Exception:
            model_name = "gemini-3.1-flash-lite"

        if req.stream:
            async def event_generator():
                full_reply_chunks: List[str] = []
                has_stream_error = False

                # Проверяем, требует ли запрос запуска автономного ReAct-агента с WikiLLM Toolbox
                agent_keywords = ("найди", "кто", "почему", "проверь", "выясни", "исследуй", "виновник", "запускает", "powershell", "диагностика", "утечка", "аномалия", "абстрактн", "пользовател", "учетн", "аккаунт", "парол", "удалить", "заблокировать", "net user", "net localgroup")
                is_agent_task = any(kw in eff_question.lower() for kw in agent_keywords) or (req.panel_id == "panel-process-manager-dispetcher-protsessov-i-prilozhen")

                if is_agent_task:
                    try:
                        from apps.windows.sdk.core.universal_langchain_agent import UniversalLangChainAgent
                        agent = UniversalLangChainAgent(model_name=model_name)
                        async for event in agent.stream_solve(eff_question):
                            ev_type = event.get("type")
                            if ev_type == "status":
                                status_txt = f"\n> 💡 *{event.get('text')}*\n\n"
                                full_reply_chunks.append(status_txt)
                                yield f"data: {json.dumps({'chunk': status_txt}, ensure_ascii=False)}\n\n"
                            elif ev_type == "tool_created":
                                tool_txt = f"\n> 🛠️ **WikiLLM Synthesis**: Модель создала новый инструмент `{event.get('tool_name')}`: *{event.get('title')}*\n\n"
                                full_reply_chunks.append(tool_txt)
                                yield f"data: {json.dumps({'chunk': tool_txt}, ensure_ascii=False)}\n\n"
                            elif ev_type == "tool_call":
                                call_txt = f"\n> ⚙️ **WikiLLM Toolbox**: Запуск `{event.get('name')}`\n\n"
                                full_reply_chunks.append(call_txt)
                                yield f"data: {json.dumps({'chunk': call_txt}, ensure_ascii=False)}\n\n"
                            elif ev_type == "tool_result":
                                data_prev = event.get("data_preview", "")
                                if data_prev and data_prev not in ("null", "[]", "{}"):
                                    res_txt = f"\n> 📊 **Данные от `{event.get('name')}`**:\n```json\n{data_prev}\n```\n\n"
                                    full_reply_chunks.append(res_txt)
                                    yield f"data: {json.dumps({'chunk': res_txt}, ensure_ascii=False)}\n\n"
                            elif ev_type == "token":
                                tok = event.get("chunk", "")
                                full_reply_chunks.append(tok)
                                yield f"data: {json.dumps({'chunk': tok}, ensure_ascii=False)}\n\n"
                            elif ev_type == "action":
                                act = event.get("action", {})
                                act_chunk = f"\n\n```action\n{json.dumps(act, ensure_ascii=False, indent=2)}\n```\n"
                                full_reply_chunks.append(act_chunk)
                                yield f"data: {json.dumps({'chunk': act_chunk}, ensure_ascii=False)}\n\n"

                        final_dialogue = "".join(full_reply_chunks).strip()
                        yield f"data: {json.dumps({'status': 'done', 'canonical_key': canonical_key, 'dialogue': final_dialogue}, ensure_ascii=False)}\n\n"
                        yield "data: [DONE]\n\n"
                        return
                    except Exception as ag_err:
                        logger.warning(f"[RouterDiagnostics] Сбой выполнения UniversalLangChainAgent, переход на стандартный LLM стриминг: {ag_err}")

                try:
                    if prov == "gemini_cli":
                        from src.ai.providers.gemini_cli import GeminiCliChatBase
                        cli_agent = GeminiCliChatBase(model_id=model_name, system_prompt=sys_instruction)
                        resp_chunk = await cli_agent.ask(chat_prompt)
                        if resp_chunk:
                            full_reply_chunks.append(resp_chunk)
                            yield f"data: {json.dumps({'chunk': resp_chunk})}\n\n"
                    elif prov == "agy":
                        from src.ai.providers.agy import AgyChatBase
                        agy_agent = AgyChatBase(model_id=model_name, system_prompt=sys_instruction)
                        resp_chunk = await agy_agent.ask(chat_prompt)
                        if resp_chunk:
                            full_reply_chunks.append(resp_chunk)
                            yield f"data: {json.dumps({'chunk': resp_chunk})}\n\n"
                    else:
                        from src.ai.gemini.generative_ai import GoogleGenerativeAI
                        ai = GoogleGenerativeAI(
                            model_name=model_name,
                            system_instruction=sys_instruction,
                        )
                        # Стримим ответ через chat_stream без искусственных таймаутов
                        async for chunk in ai.chat_stream(chat_prompt):
                            if chunk:
                                if _is_stream_chunk_error(chunk):
                                    has_stream_error = True
                                    logger.error(f"Сбой обращения к модели в чате диагностики (обнаружен маркер ошибки в потоке): {chunk[:160]}")
                                    err_detail = _format_error_detail(chunk)
                                    yield f"data: {json.dumps(err_detail, ensure_ascii=False)}\n\n"
                                    return
                                full_reply_chunks.append(chunk)
                                yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"
                except Exception as stream_err:
                    has_stream_error = True
                    logger.error(f"Сбой обращения к модели в чате диагностики: {stream_err}")
                    err_detail = _format_error_detail(str(stream_err))
                    yield f"data: {json.dumps(err_detail, ensure_ascii=False)}\n\n"
                    return

                final_text = "".join(full_reply_chunks).strip()
                dialogue_fmt = clean_chat_greetings(_format_json_response_to_dialogue(final_text))
                clean_final = dialogue_fmt or clean_chat_greetings(final_text)
                if _is_model_error(clean_final):
                    has_stream_error = True

                # Обогащаем WikiLLM только при успешном реальном ответе модели
                enriched = False
                if not has_stream_error and req.enrich_wikillm and canonical_key and clean_final:
                    enriched = _enrich_wikillm_qa(
                        canonical_key=canonical_key,
                        table_type=eff_table_type,
                        title=eff_title,
                        subtitle=eff_subtitle,
                        question=eff_question,
                        answer=clean_final,
                        model_name=model_name,
                    )
                if has_stream_error:
                    err_detail = _format_error_detail(clean_final or "Сбой ответа языковой модели")
                    yield f"data: {json.dumps(err_detail, ensure_ascii=False)}\n\n"
                    yield "data: [DONE]\n\n"
                    return

                yield f"data: {json.dumps({'status': 'done', 'enriched': enriched, 'canonical_key': canonical_key, 'source': prov, 'dialogue': clean_final}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(event_generator(), media_type="text/event-stream")

        # Обычный не-стриминговый режим (терпеливое ожидание ответа без таймаутов)
        resp_text: str = ""
        try:
            if prov == "gemini_cli":
                from src.ai.providers.gemini_cli import GeminiCliChatBase
                cli_agent = GeminiCliChatBase(model_id=model_name, system_prompt=sys_instruction)
                resp_text = await cli_agent.ask(chat_prompt)
            elif prov == "agy":
                from src.ai.providers.agy import AgyChatBase
                agy_agent = AgyChatBase(model_id=model_name, system_prompt=sys_instruction)
                resp_text = await agy_agent.ask(chat_prompt)
            else:
                from src.ai.gemini.generative_ai import GoogleGenerativeAI
                ai = GoogleGenerativeAI(
                    model_name=model_name,
                    system_instruction=sys_instruction,
                )
                resp_text = await ai.ask(chat_prompt, attempts=3)
        except Exception as e:
            logger.error(f"Сбой прямого вызова LLM в чате: {e}")
            return {
                "status": "error",
                "error": {"message": str(e)},
                "canonical_key": canonical_key,
                "table_type": eff_table_type,
                "source": prov,
            }

        if not resp_text or _is_model_error(resp_text):
            err_detail = _format_error_detail(resp_text or "Модель вернула пустой ответ.")
            return {
                "status": "error",
                "error": err_detail.get("error", {"message": resp_text or "Модель вернула пустой ответ."}),
                "canonical_key": canonical_key,
                "table_type": eff_table_type,
                "source": prov,
            }

        dialogue_fmt = clean_chat_greetings(_format_json_response_to_dialogue(resp_text))
        final_ans = dialogue_fmt or clean_chat_greetings(resp_text)
        enriched = False
        if req.enrich_wikillm and canonical_key and final_ans:
            enriched = _enrich_wikillm_qa(
                canonical_key=canonical_key,
                table_type=eff_table_type,
                title=eff_title,
                subtitle=eff_subtitle,
                question=eff_question,
                answer=final_ans,
                model_name=model_name,
            )

        return {
            "status": "ok",
            "answer": final_ans,
            "summary": final_ans,
            "raw_text": resp_text,
            "canonical_key": canonical_key,
            "enriched": enriched,
            "table_type": eff_table_type,
            "source": prov,
        }

    return router


def clean_chat_greetings(text: str) -> str:
    """Удаляет из начала ответа модели ритуальные приветствия, самопрезентации и вводную воду."""
    if not text:
        return ""
    cleaned = text.strip()

    # 1. Удаляем приветствия в самом начале (Приветствую, Здравствуйте, Добрый день и т.д.)
    cleaned = re.sub(
        r"^(?:Приветствую(?:,\s*коллега)?|Здравствуйте|Добрый\s+(?:день|вечер|утро)|Доброго\s+времени\s+суток)[!\.,]?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    # 2. Удаляем вводное предложение с самопредставлением и фактом анализа данных
    pattern_expert = (
        r"^(?:Как\s+(?:эксперт|системный|ведущий|главный|старший|инженер|архитектор|специалист|консультант|администратор)[^\n]*?"
        r"(?:я\s+(?:провел[а]?|проанализировал[а]?|изучил[а]?)|проанализировал[а]?|провел[а]?|изучил[а]?)[^\n]*?"
        r"(?:\.\s+(?=[А-ЯA-Z#\n])|\.\s*$|\n+))"
    )
    cleaned = re.sub(pattern_expert, "", cleaned, flags=re.IGNORECASE)

    # 3. Удаляем вводное предложение типа 'Я провел анализ представленных данных...'
    pattern_ya = (
        r"^(?:Я\s+(?:провел[а]?|проанализировал[а]?|изучил[а]?)\s+(?:детальный\s+|технический\s+|глубокий\s+)?"
        r"(?:анализ|представленные\s+данные|данные|информацию|телеметрию)[^\n]*?"
        r"(?:\.\s+(?=[А-ЯA-Z#\n])|\.\s*$|\n+))"
    )
    cleaned = re.sub(pattern_ya, "", cleaned, flags=re.IGNORECASE)

    # 4. Удаляем преамбулы 'Относительно вашего вопроса...' или 'В качестве эксперта...'
    pattern_intro = (
        r"^(?:(?:В\s+качестве\s+эксперта|Относительно\s+(?:вашего|заданного)?\s*вопроса)[^\n]*?"
        r"(?:\.\s+(?=[А-ЯA-Z#\n])|\.\s*$|\n+))"
    )
    cleaned = re.sub(pattern_intro, "", cleaned, flags=re.IGNORECASE)

    # 5. Заголовок-заглушка "Экспертное заключение по..."
    cleaned = re.sub(
        r"^(?:###\s+Экспертное\s+заключение\s+по[^\n]*\n+)",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    return cleaned.strip()


def _format_json_response_to_dialogue(text: str) -> str:
    """Конвертирует JSON-ответ модели в структурированный диалоговый текст на русском языке."""
    if not text:
        return ""

    data, _ = _extract_and_parse_json(text)
    if isinstance(data, dict):
        try:
            # Разворачиваем вложенные словари-обертки (analysis_report, report, diagnostic, data, result и т.д.)
            while isinstance(data, dict):
                keys = list(data.keys())
                if len(keys) == 1 and isinstance(data[keys[0]], dict):
                    data = data[keys[0]]
                elif "analysis_report" in data and isinstance(data["analysis_report"], dict):
                    data = data["analysis_report"]
                elif "report" in data and isinstance(data["report"], dict):
                    data = data["report"]
                elif "diagnostic" in data and isinstance(data["diagnostic"], dict):
                    data = data["diagnostic"]
                elif "data" in data and isinstance(data["data"], dict):
                    data = data["data"]
                elif "result" in data and isinstance(data["result"], dict):
                    data = data["result"]
                else:
                    break

            if isinstance(data, dict):
                # 1. Проверяем наличие детального технического заключения (technical_assessment)
                tech_assessment = (
                    data.get("technical_assessment")
                    or data.get("assessment")
                    or data.get("analysis")
                )
                if tech_assessment and isinstance(tech_assessment, str):
                    tech_parts = []
                    # Заголовочная информация о сущности
                    entity_name = data.get("entity") or data.get("name") or data.get("title")
                    pid = data.get("pid")
                    if entity_name or pid:
                        meta_info = f"🔍 **Сущность:** {entity_name or 'Процесс'}"
                        if pid:
                            meta_info += f" (PID: {pid})"
                        tech_parts.append(meta_info)

                    # Суть проблемы
                    issue = data.get("issue_summary") or data.get("issue")
                    if issue:
                        tech_parts.append(f"⚠️ **Суть проблемы:** {issue}")

                    # Основное тело технического отчета
                    tech_parts.append(clean_chat_greetings(tech_assessment.strip()))

                    # Дополнительные поля, если они не включены в отчет
                    rec = data.get("recommendation") or data.get("recommendations")
                    if rec and isinstance(rec, str) and rec not in tech_assessment:
                        tech_parts.append(f"💡 **Рекомендация эксперта:** {rec.strip()}")

                    verdict = data.get("security_verdict") or data.get("verdict")
                    if verdict and isinstance(verdict, str) and verdict not in tech_assessment:
                        tech_parts.append(f"🛡️ **Вердикт:** {verdict.strip()}")

                    actions = data.get("action_steps") or data.get("actions")
                    if isinstance(actions, list) and actions:
                        act_lines = "\n".join(f"  • {step}" for step in actions)
                        tech_parts.append(f"📋 **Рекомендуемые действия:**\n{act_lines}")

                    return clean_chat_greetings("\n\n".join(tech_parts))

                # 2. Стандартный разбор диагностических полей
                parts = []
                if data.get("answer"):
                    parts.append(clean_chat_greetings(str(data["answer"]).strip()))
                if data.get("summary"):
                    parts.append(f"📌 **Назначение:** {data['summary']}")
                if data.get("developer") or data.get("category"):
                    dev = data.get("developer", "Неизвестен")
                    cat = data.get("category", "Компонент")
                    parts.append(f"🏢 **Разработчик:** {dev} ({cat})")
                if data.get("security_verdict"):
                    parts.append(f"🛡️ **Безопасность:** {data['security_verdict']}")
                if data.get("performance_impact"):
                    parts.append(f"⚡ **Влияние на ресурсы:** {data['performance_impact']}")
                if data.get("recommendation"):
                    parts.append(f"💡 **Рекомендация эксперта:** {data['recommendation']}")
                actions = data.get("action_steps")
                if isinstance(actions, list) and actions:
                    act_lines = "\n".join(f"  • {step}" for step in actions)
                    parts.append(f"📋 **Рекомендуемые действия:**\n{act_lines}")
                causes = data.get("possible_causes")
                if isinstance(causes, list) and causes:
                    cause_lines = "\n".join(f"  • {cause}" for cause in causes)
                    parts.append(f"⚠️ **Возможные причины:**\n{cause_lines}")
                dev_adv = data.get("developer_advice") or data.get("developer_tips") or data.get("dev_advice")
                if dev_adv and isinstance(dev_adv, str):
                    parts.append(f"🛠️ **Советы разработчику:**\n{dev_adv.strip()}")

                # 3. Если стандартные поля не подошли, аккуратно преобразуем оставшиеся свойства
                if not parts:
                    for k, v in data.items():
                        if k not in ("canonical_key", "status", "source", "table_type"):
                            if isinstance(v, list):
                                list_str = "\n".join(f"  • {item}" for item in v)
                                parts.append(f"**{k}:**\n{list_str}")
                            elif isinstance(v, dict):
                                dict_lines = "\n".join(f"  • {sub_k}: {sub_v}" for sub_k, sub_v in v.items())
                                parts.append(f"**{k}:**\n{dict_lines}")
                            elif v:
                                parts.append(f"**{k}:** {v}")

                if parts:
                    return clean_chat_greetings("\n\n".join(parts))
        except Exception:
            pass
    return clean_chat_greetings(text)


def _enrich_wikillm_qa(
    canonical_key: str,
    table_type: str,
    title: str,
    subtitle: str,
    question: str,
    answer: str,
    model_name: Optional[str] = None
) -> bool:
    """Обогащает базу знаний WikiLLM парой вопрос-ответ оператора."""
    if not canonical_key or not question or not answer:
        return False
    # Исключаем сохранение шаблонных/эвристических заглушек и любых ошибок модели
    lower_ans = answer.lower()
    error_markers = (
        "данный компонент выполняет стандартные задачи подсистемы",
        "экспертное заключение по сущности",
        "model error:",
        "ошибка ответа",
        "streaming error:",
        "service unavailable",
        "503 service unavailable",
        "this model is currently experiencing high demand",
        "resourceexhausted",
        "resource_exhausted",
        "429 too many requests",
        "quota exceeded",
        "rate limit",
        "все api ключи исчерпаны",
        "harness process exited",
        "ошибка провайдера",
    )
    if any(m in lower_ans for m in error_markers) or len(answer.strip()) < 15:
        logger.warning(f"[WikiLLM] Попытка записи ошибки или мусорного ответа для '{canonical_key}' отклонена: {answer[:120]}")
        return False

    clean_answer = clean_chat_greetings(answer)
    if not clean_answer:
        return False
    try:
        from apps.windows.wikillm.router import get_engine
        from apps.windows.wikillm.models import (
            KnowledgeEntity,
            Claim,
            Evidence,
            KnowledgeSource,
            ArtifactType,
        )
        engine = get_engine()
        entity = engine.storage.get_entity(canonical_key)
        type_map = {
            "process": ArtifactType.PROCESS,
            "service": ArtifactType.SERVICE,
            "driver": ArtifactType.DRIVER,
            "software": ArtifactType.SOFTWARE,
            "task": ArtifactType.TASK,
            "network": ArtifactType.NETWORK,
            "disk": ArtifactType.DISK,
            "user": ArtifactType.USER,
            "user_account": ArtifactType.USER,
            "power_session": ArtifactType.WINDOWS_EVENT,
            "power_event": ArtifactType.WINDOWS_EVENT,
            "security_event": ArtifactType.WINDOWS_EVENT,
        }
        entity_type = type_map.get((table_type or "").lower(), ArtifactType.GENERIC)

        if not entity:
            entity = KnowledgeEntity(
                canonical_key=canonical_key,
                entity_type=entity_type,
                name=title or canonical_key,
                summary=f"Контекстный анализ сущности «{title}» ({subtitle})",
                category=table_type or "system",
                confidence=1.0,
                provenance_source=KnowledgeSource.DOCUMENTED,
                provenance_model=model_name or "gemini",
                claims=[],
                tags=[table_type or "generic", "qa_enriched", "wikillm_chat"],
            )

        qa_statement = f"Вопрос: {question.strip()}\nОтвет: {clean_answer}"
        # Проверяем отсутствие дубликата вопроса в claims
        if not any(c.statement.startswith(f"Вопрос: {question.strip()}") for c in entity.claims):
            entity.claims.append(
                Claim(
                    statement=qa_statement,
                    confidence=1.0,
                    source=KnowledgeSource.DOCUMENTED,
                    verified=True,
                )
            )

        ev = Evidence(
            description="Диагностический интерактивный диалог Q&A",
            sample_value=question.strip()[:200],
        )
        entity.evidence.append(ev)

        engine.storage.save_entity(entity)
        engine.storage.record_observation(canonical_key)
        logger.info(f"[WikiLLM] Знание '{canonical_key}' успешно обогащено вопросом '{question[:60]}...' и ответом.")
        return True
    except Exception as exc:
        logger.warning(f"[WikiLLM] Не удалось обогатить базу знаний для '{canonical_key}': {exc}")
        return False


def _generate_heuristic_questions(req: DiagnosticSuggestQuestionsRequest) -> List[str]:
    """Генерирует 3 контекстных вопроса системного администратора на основе эвристики."""
    tt = (req.table_type or "generic").lower()
    t = req.title or "данного компонента"

    panel = (req.panel_id or "").lower()
    meta = req.metadata or {}
    if tt in ("desktop_window", "desktop_windows", "window", "windows", "hwnd") or panel == "panel-windows":
        proc_label = meta.get("process_name") or meta.get("Процесс") or req.subtitle or "процесса-владельца"
        cls_label = meta.get("class_name") or meta.get("Класс окна (Win32)") or "Win32"
        dims_label = meta.get("Габариты (Ш × В)") or meta.get("Габариты") or ""
        if any(tiny in str(dims_label) for tiny in ("2 × 2", "2x2", "32 × 32", "32x32", "1 × 1", "0 × 0")):
            q1 = f"Почему окно «{t}» процесса {proc_label} имеет технический микро-размер ({dims_label}) и зачем оно нужно?"
        else:
            q1 = f"Какую именно роль выполняет окно «{t}» (класс {cls_label}) в работе процесса {proc_label}?"
        return [
            q1,
            f"Что произойдет с приложением {proc_label}, если принудительно закрыть это окно (WM_CLOSE)?",
            "Безопасно ли данное окно и не перехватывает ли оно глобальный фокус ввода или экран?",
        ]
    if tt in ("power_session", "panel-system-control-4"):
        return [
            f"Какова точная причина и процесс-инициатор завершения сессии «{t}»?",
            "Были ли зарегистрированы события аварийного обесточивания (Kernel-Power Event 41)?",
            "Как текущий аптайм соотносится с надежностью дисковой подсистемы и стабильностью хоста?",
        ]
    if tt in ("power_event", "panel-system-control-5"):
        return [
            f"Какова степень критичности события {t} для непрерывной работы Windows?",
            "Указывает ли данное событие на аппаратный сбой блока питания или программный сбой?",
            "Какие шаги в журнале BugCheck рекомендуются для предотвращения повторения сбоя?",
        ]
    if tt == "cpu":
        return [
            f"Каковы показатели троттлинга и термического запаса процессора «{t}» под нагрузкой?",
            "Изолированы ли аппаратные уязвимости микроархитектуры (Spectre/Meltdown) в текущей ОС?",
            "Какой профиль электропитания (Power Plan) оптимален для данного CPU?",
        ]
    if tt == "gpu":
        return [
            f"Хватает ли выделенного объема видеопамяти VRAM видеокарты «{t}» для текущих задач?",
            "Имеются ли известные критические ошибки или утечки памяти в установленной версии видеодрайвера?",
            "Каковы рекомендации по температурному лимиту и профилю охлаждения GPU?",
        ]
    if tt == "software":
        return [
            f"Имеет ли установленная программа «{t}» действующую доверенную цифровую подпись?",
            "Прописаны ли фоновые службы автообновления или автозапуск для этой программы?",
            "Безопасно ли полностью деинсталлировать «{t}» без нарушения зависимостей других утилит?",
        ]
    if tt in ("process", "panel-process-manager-dispetcher-protsessov-i-prilozhen"):
        return [
            f"Безопасно ли принудительно завершить процесс «{t}» без системного сбоя?",
            "Задействует ли процесс «{t}» низкоуровневые Ring 0 драйверы режима ядра?",
            "Какова суммарная нагрузка данного процесса на процессор и оперативную память?",
        ]
    if tt == "service":
        return [
            f"Какой тип запуска (Автоматически / Вручную) рекомендуется для службы «{t}»?",
            "В контексте какой учетной записи (LocalSystem или NetworkService) выполняется служба?",
            "Какие системные компоненты перестанут работать при отключении службы «{t}»?",
        ]
    if tt == "network":
        return [
            f"Кому принадлежит удаленный адрес и открытый сетевой порт соединения «{t}»?",
            "Является ли трафик этого соединения зашифрованным (TLS/SSH/HTTPS)?",
            "Рекомендуется ли заблокировать данное подключение правилом Windows Defender Firewall?",
        ]
    if tt == "user_account":
        return [
            f"Входит ли учетная запись «{t}» в привилегированную группу локальных администраторов?",
            "Каков статус активности учетной записи и настроена ли регулярная смена пароля?",
            "Рекомендуется ли отключить аккаунт «{t}» согласно политике минимальных привилегий?",
        ]
    if tt == "security_event":
        return [
            f"Указывает ли событие аудита {t} на попытку несанкционированного доступа или брутфорса?",
            "Какой тип входа (Logon Type) и субъект безопасности зафиксированы в событии?",
            "Какие меры реагирования и ужесточения политик аудита необходимы?",
        ]
    if tt == "task":
        return [
            f"Какие триггеры и расписание настроены для задачи планировщика «{t}»?",
            "В контексте каких привилегий (SYSTEM или текущий пользователь) запускается задача?",
            "Безопасен ли исполняемый путь и аргументы командной строки задачи «{t}»?",
        ]
    if tt == "registry":
        return [
            f"Каково штатное значение по умолчанию для параметра реестра «{t}»?",
            "Как изменение этого параметра влияет на производительность и безопасность Windows?",
            "Как быстро вернуть стандартное значение при возникновении системных сбоев?",
        ]
    if tt == "disk":
        return [
            f"Каков текущий процент износа (Wear Level) и статус SMART накопителя «{t}»?",
            "Включено ли шифрование BitLocker и какова скорость операций ввода-вывода (IOPS)?",
            "Имеются ли поврежденные сектора или ошибки файловой системы на этом томе?",
        ]
    if tt == "startup":
        return [
            f"Насколько сильно элемент автозагрузки «{t}» замедляет время загрузки Windows?",
            "Из какой ветки реестра или папки автозапуска инициируется запуск?",
            "Рекомендуется ли отключить автозагрузку «{t}» для ускорения старта системы?",
        ]
    if tt == "app_log":
        return [
            f"Какова первопричина возникновения записи в журнале «{t}»?",
            "Затронуты ли критические сервисы системы в результате этого события?",
            "Какие диагностические действия рекомендуется предпринять в первую очередь?",
        ]
    if tt == "help":
        return [
            f"Какие лучшие инженерные практики рекомендуются для настройки подсистемы «{t}»?",
            "С помощью каких команд PowerShell можно быстро продиагностировать этот компонент?",
            "Каковы архитектурные границы изоляции и требования к привилегиям в Windows?",
        ]

    # Общий fallback
    return [
        f"Каково ключевое назначение сущности «{t}» в операционной системе Windows?",
        f"Имеются ли риски безопасности или избыточного потребления ресурсов для «{t}»?",
        f"Какие оптимальные действия системного администратора рекомендуются для «{t}»?",
    ]




__all__ = [
    "init_router",
    "DiagnosticExecuteCommandRequest",
    "DiagnosticExecuteCommandResponse",
]


