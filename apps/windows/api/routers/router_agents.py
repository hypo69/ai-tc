# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Apps Windows Api Routers - Router Agents
# =============================================================================
# Description:
#   Предоставляет полнофункциональные эндпойнты для управления автономными
#   агентами: список агентов, манифесты .agents, инструменты, провайдеры,
#   тестовый запуск в Sandbox и генерацию системных промптов.
#
# Usage Examples:
#   Python API:
#     from apps.windows.api.routers.router_agents import init_router
#     router = init_router()
#
# File: router_agents.py
# Project: ai-tc
# Package: apps.windows.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20 16:45:00
# =============================================================================

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from header import __root__
from logger import logger
from .agents_executor import execute_agent_sandbox

_AGENTS_DIR = __root__ / ".agents"
_CONFIG_PATH = __root__ / "config.json"

# Предустановленные системные агенты
_DEFAULT_SYSTEM_AGENTS: List[Dict[str, Any]] = [
    {
        "id": "windows_controller_agent",
        "name": "Windows Controller Agent",
        "description": "Автономный системный контроллер: диагностика служб, событий, процессов и выполнение SafeOps операций",
        "provider": "gemini",
        "model": "gemini-3.1-flash",
        "temperature": 0.1,
        "max_steps": 15,
        "timeout_seconds": 60,
        "enabled": True,
        "is_system": True,
        "tools": ["system_diagnostics", "event_logs_inspector", "services_manager", "safeops_executor"],
        "system_prompt": "Вы — системный администратор и контроллер ОС Windows. Выполняйте безопасную диагностику и аудит.",
        "sandbox_default_query": "Проверь текущую загрузку CPU, оперативной памяти и статус критических служб Windows",
    },
    {
        "id": "system_logs_agent",
        "name": "System Logs Analyzer",
        "description": "Специализированный агент мониторинга и корреляции системных журналов Windows Event Logs и Application Telemetry",
        "provider": "gemini",
        "model": "gemini-3.1-flash-lite",
        "temperature": 0.2,
        "max_steps": 10,
        "timeout_seconds": 45,
        "enabled": True,
        "is_system": True,
        "tools": ["event_logs_inspector", "system_diagnostics"],
        "system_prompt": "Вы — эксперт по анализу журналов Windows. Находите аномалии и критические сбои.",
        "sandbox_default_query": "Проанализируй критические ошибки и предупреждения в журналах событий Windows (System и Application) за последние 24 часа",
    },
    {
        "id": "chat_agent",
        "name": "General Chat Agent",
        "description": "Интерактивный диалоговый ассистент с поддержкой поиска знаний в локальной базе WikiLLM",
        "provider": "gemini",
        "model": "gemini-3.1-flash",
        "temperature": 0.3,
        "max_steps": 12,
        "timeout_seconds": 60,
        "enabled": True,
        "is_system": True,
        "tools": ["search_web", "wikillm_search"],
        "system_prompt": "Вы — умный персональный помощник пользователя Windows.",
        "sandbox_default_query": "Найди в базе знаний WikiLLM краткую справку по диагностике и настройке системы",
    },
]

# Инструменты, доступные агентам
_DEFAULT_TOOLS: List[Dict[str, Any]] = [
    {"id": "system_diagnostics", "name": "system_diagnostics", "description": "Сбор метрик CPU, памяти, дисков и сетевого адаптера", "icon": "📊"},
    {"id": "event_logs_inspector", "name": "event_logs_inspector", "description": "Чтение и фильтрация журналов событий Windows (Event Log)", "icon": "📜"},
    {"id": "services_manager", "name": "services_manager", "description": "Инспекция и безопасное управление системными службами SCM", "icon": "⚙️"},
    {"id": "safeops_executor", "name": "safeops_executor", "description": "Выполнение проверенных SafeOps-скриптов администрирования", "icon": "🛡️"},
    {"id": "search_web", "name": "search_web", "description": "Поиск актуальной справочной информации в интернете", "icon": "🌐"},
    {"id": "wikillm_search", "name": "wikillm_search", "description": "Гибридный поиск по локальной базе знаний WikiLLM", "icon": "📚"},
    {"id": "run_command", "name": "run_command", "description": "Выполнение безопасных команд PowerShell / CMD", "icon": "💻"},
    {"id": "python_eval", "name": "python_eval", "description": "Вычисление формул и обработка массивов на Python", "icon": "🐍"},
]

# Провайдеры и модели
_DEFAULT_PROVIDERS: Dict[str, Any] = {
    "gemini": {
        "id": "gemini",
        "name": "Google Gemini",
        "default_model": "gemini-3.5-flash-lite",
        "models": [
            {"id": "gemini-3.5-flash-lite", "name": "Gemini 3.5 Flash Lite (Рекомендуется)"},
            {"id": "gemini-3.5-flash", "name": "Gemini 3.5 Flash"},
            {"id": "gemini-3.1-flash-lite", "name": "Gemini 3.1 Flash Lite"},
            {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash"},
        ],
    },
    "openai": {
        "id": "openai",
        "name": "OpenAI / Compatible",
        "default_model": "gpt-4o-mini",
        "models": [
            {"id": "gpt-4o-mini", "name": "GPT-4o Mini"},
            {"id": "gpt-4o", "name": "GPT-4o"},
        ],
    },
    "ollama": {
        "id": "ollama",
        "name": "Ollama Local",
        "default_model": "llama3.2",
        "models": [
            {"id": "llama3.2", "name": "Llama 3.2 (Локально)"},
            {"id": "qwen2.5-coder", "name": "Qwen 2.5 Coder"},
            {"id": "mistral", "name": "Mistral 7B"},
        ],
    },
    "windows_ai": {
        "id": "windows_ai",
        "name": "Windows Copilot / Local NPU",
        "default_model": "phi-silicon",
        "models": [
            {"id": "phi-silicon", "name": "Phi-3.5 Silicon NPU"},
        ],
    },
}


class AgentPayload(BaseModel):
    """Схема параметров агента для сохранения/обновления."""

    id: Optional[str] = None
    name: str
    description: Optional[str] = ""
    provider: Optional[str] = "gemini"
    model: Optional[str] = "gemini-3.1-flash"
    temperature: Optional[float] = 0.1
    max_steps: Optional[int] = 15
    timeout_seconds: Optional[int] = 60
    enabled: Optional[bool] = True
    is_system: Optional[bool] = False
    tools: Optional[List[str]] = Field(default_factory=list)
    system_prompt: Optional[str] = ""
    sandbox_default_query: Optional[str] = None


class AgentTestPayload(BaseModel):
    """Схема запроса тестирования агента."""

    agent_id: Optional[str] = None
    prompt: str = ""
    query: Optional[str] = None
    test_message: Optional[str] = None


class GeneratePromptPayload(BaseModel):
    """Схема запроса генерации промпта для агента."""

    name: str = ""
    description: str = ""
    role: Optional[str] = ""
    provider: Optional[str] = "gemini"
    model: Optional[str] = "gemini-3.1-flash"


def _resolve_sandbox_default_query(agent: Dict[str, Any]) -> str:
    """Подбирает релевантный тестовый запрос для песочницы на основе профиля агента."""
    explicit = str(agent.get("sandbox_default_query") or "").strip()
    if explicit:
        return explicit

    agent_id = str(agent.get("id") or "").lower()
    tools = [str(t).lower() for t in (agent.get("tools") or [])]
    description = str(agent.get("description") or "").strip()
    name = str(agent.get("name") or agent_id or "агент").strip()

    if "github" in agent_id or any("github" in t for t in tools):
        return "Покажи список открытых GitHub Issues в репозитории и предложи приоритетный план их выполнения"
    if "log" in agent_id or any("event_log" in t for t in tools):
        return "Проанализируй критические ошибки и предупреждения в журналах событий Windows (System и Application) за последние 24 часа"
    if "windows" in agent_id or any(t.startswith("windows_") or t in ("system_diagnostics", "services_manager") for t in tools):
        return "Проверь текущую загрузку CPU, оперативной памяти и статус критических служб Windows"
    if "chat" in agent_id or any(t in ("wikillm_search", "rag_search", "search_web") for t in tools):
        return "Найди в базе знаний WikiLLM краткую справку по диагностике и настройке системы"
    if any(t in ("python_eval", "run_command") for t in tools):
        return "Выполни быструю диагностическую проверку окружения и выведи краткий отчёт"
    if description:
        return f"Выполни тестовую задачу по профилю агента «{name}»: {description}"
    return f"Выполни диагностический тест возможностей агента «{name}»"


def _get_agents() -> List[Dict[str, Any]]:
    """Возвращает список агентов, объединяя системные шаблоны и манифесты .agents."""
    agents_map: Dict[str, Dict[str, Any]] = {a["id"]: dict(a) for a in _DEFAULT_SYSTEM_AGENTS}

    if _AGENTS_DIR.exists():
        for manifest_file in _AGENTS_DIR.glob("*.json"):
            try:
                raw = json.loads(manifest_file.read_text(encoding="utf-8"))
                if isinstance(raw, dict) and "id" in raw:
                    a_id = raw["id"]
                    item = dict(raw)
                    item.setdefault("enabled", True)
                    item.setdefault("is_system", False)
                    item.setdefault("provider", "gemini")
                    item.setdefault("model", "gemini-3.1-flash")
                    item.setdefault("temperature", 0.1)
                    item.setdefault("max_steps", 15)
                    item.setdefault("tools", [])
                    agents_map[a_id] = item
            except Exception as exc:
                logger.warning(f"[AgentsRouter] Ошибка чтения {manifest_file.name}: {exc}")

    for item in agents_map.values():
        item["sandbox_default_query"] = _resolve_sandbox_default_query(item)

    return list(agents_map.values())


def _save_agent_to_manifest(agent_dict: Dict[str, Any]) -> None:
    """Сохраняет агент в манифест .agents/<id>.json."""
    _AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    a_id = agent_dict["id"]
    file_path = _AGENTS_DIR / f"{a_id}.json"
    file_path.write_text(json.dumps(agent_dict, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"[AgentsRouter] Агент {a_id} сохранён в {file_path}")


def _get_tools() -> List[Dict[str, Any]]:
    """Возвращает список инструментов, доступных агентам."""
    return list(_DEFAULT_TOOLS)


def _get_providers() -> Dict[str, Any]:
    """Возвращает список провайдеров LLM из конфигурации или по умолчанию."""
    providers = dict(_DEFAULT_PROVIDERS)
    if _CONFIG_PATH.exists():
        try:
            cfg = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            ai_sec = cfg.get("ai_providers_and_models_configuration") or cfg.get("ai") or {}
            custom_providers = ai_sec.get("providers")
            if isinstance(custom_providers, dict):
                for p_key, p_val in custom_providers.items():
                    if p_key in providers and isinstance(p_val, dict):
                        if "default_model" in p_val:
                            providers[p_key]["default_model"] = p_val["default_model"]
        except Exception as exc:
            logger.debug(f"[AgentsRouter] Слияние провайдеров из config.json: {exc}")
    return providers


def init_router() -> APIRouter:
    """Инициализирует полнофункциональный роутер ``/api/v1/agents``."""
    router = APIRouter(prefix="/api/v1/agents", tags=["agents"])

    @router.get("", summary="Получить список агентов")
    @router.get("/", summary="Получить список агентов (со слешем)")
    async def list_agents():
        agents = _get_agents()
        return {"agents": agents, "total": len(agents)}

    @router.get("/tools", summary="Получить список инструментов агентов")
    async def list_tools():
        tools = _get_tools()
        return {"tools": tools, "total": len(tools)}

    @router.get("/providers", summary="Получить список провайдеров LLM")
    async def list_providers():
        providers = _get_providers()
        return {"providers": providers}

    @router.get("/{agent_id}", summary="Получить агента по ID")
    async def get_agent(agent_id: str):
        agents = _get_agents()
        for a in agents:
            if a["id"] == agent_id:
                return a
        raise HTTPException(status_code=404, detail=f"Агент '{agent_id}' не найден")

    @router.post("", summary="Создать нового агента")
    @router.post("/", summary="Создать нового агента (со слешем)")
    async def create_agent(payload: AgentPayload):
        a_id = payload.id or payload.name.lower().replace(" ", "_")
        agent_data = payload.model_dump()
        agent_data["id"] = a_id
        agent_data["is_system"] = False
        _save_agent_to_manifest(agent_data)
        return {"status": "success", "agent": agent_data}

    @router.put("/{agent_id}", summary="Обновить агента")
    async def update_agent(agent_id: str, payload: AgentPayload):
        agent_data = payload.model_dump()
        agent_data["id"] = agent_id
        # Для системных агентов сохраняем флаг
        if any(a["id"] == agent_id and a.get("is_system") for a in _DEFAULT_SYSTEM_AGENTS):
            agent_data["is_system"] = True
        _save_agent_to_manifest(agent_data)
        return {"status": "success", "agent": agent_data}

    @router.delete("/{agent_id}", summary="Удалить агента")
    async def delete_agent(agent_id: str):
        if any(a["id"] == agent_id and a.get("is_system") for a in _DEFAULT_SYSTEM_AGENTS):
            raise HTTPException(status_code=403, detail="Запрещено удалять встроенные системные агенты")
        target_file = _AGENTS_DIR / f"{agent_id}.json"
        if target_file.exists():
            target_file.unlink()
            logger.info(f"[AgentsRouter] Манифест {target_file} удалён")
            return {"status": "success", "deleted": agent_id}
        raise HTTPException(status_code=404, detail=f"Манифест агента '{agent_id}' не найден")

    @router.post("/test", summary="Тестовый запуск агента в Sandbox")
    async def test_agent(payload: AgentTestPayload):
        query = (payload.test_message or payload.query or payload.prompt or "").strip()
        if not query:
            query = "Диагностический тест связи с агентом."
        a_id = payload.agent_id or "generic_agent"
        agents = _get_agents()
        agent_data = next((a for a in agents if a["id"] == a_id), None)
        if not agent_data:
            agent_data = {
                "id": a_id,
                "name": a_id,
                "provider": "gemini",
                "model": "gemini-3.5-flash-lite",
                "temperature": 0.1,
                "max_steps": 10,
                "timeout_seconds": 60,
                "tools": [],
                "system_prompt": "",
            }
        return await execute_agent_sandbox(agent_data, query)

    @router.post("/generate-prompt", summary="AI-генерация системного промпта")
    async def generate_prompt(payload: GeneratePromptPayload):
        role_desc = payload.role or payload.description or "Автономный помощник Windows"
        generated_prompt = (
            f"Вы — специализированный агент '{payload.name or 'Custom Agent'}'.\n"
            f"Основное назначение: {role_desc}.\n\n"
            f"Правила работы:\n"
            f"1. Действуйте строго в рамках назначенной роли и используйте только разрешенные инструменты.\n"
            f"2. Перед выполнением потенциально опасных системных действий запрашивайте подтверждение SafeOps.\n"
            f"3. Форматируйте результаты в виде структурированного Markdown с метриками и выводами."
        )
        return {
            "status": "success",
            "system_prompt": generated_prompt,
            "prompt": generated_prompt,
        }

    return router


__all__ = ["init_router"]
