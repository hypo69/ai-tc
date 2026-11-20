# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Apps Windows Api Routers - Agents Sandbox Executor
# =============================================================================
# Description:
#   Исполнитель ReAct-агентов для песочницы Sandbox (/api/v1/agents/test).
#   Подключает реальные инструменты из src.ai.agents.tools, инициализирует
#   LLM-провайдера (Gemini / Ollama / OpenAI-совместимые) и возвращает
#   структурированную трассировку шагов выполнения (ReAct Trace).
#
# Usage Examples:
#   Python API:
#     from apps.windows.api.routers.agents_executor import execute_agent_sandbox
#     result = await execute_agent_sandbox(agent_data, "Проверь CPU и RAM")
#
# File: agents_executor.py
# Project: ai-tc
# Package: apps.windows.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20 16:45:00
# =============================================================================

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from header import __root__
from logger import logger

_CONFIG_PATH: Path = __root__ / "config.json"
_FALLBACK_GEMINI_MODEL: str = "gemini-3.5-flash-lite"

# Маппинг коротких алиасов системных агентов на реальные инструменты src.ai.agents.tools
_TOOL_ALIASES: Dict[str, List[str]] = {
    "system_diagnostics": ["windows_collector_audit", "windows_process_list"],
    "event_logs_inspector": ["windows_event_log_query", "system_logs_analyzer"],
    "services_manager": ["windows_services_list"],
    "safeops_executor": ["windows_execute_atomic_op"],
    "search_web": ["web_search"],
    "wikillm_search": ["rag_search"],
    "run_command": ["windows_safe_probe"],
}

# Устаревшие/несуществующие идентификаторы моделей Gemini, которые нужно заменить на актуальную
_DEPRECATED_GEMINI_MODELS = {
    "gemini-3.1-flash",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
    "gemini-2.0-flash",
}


def _get_default_gemini_model() -> str:
    """Считывает актуальную модель Gemini по умолчанию из config.json."""
    if _CONFIG_PATH.exists():
        try:
            cfg = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            ai_sec = cfg.get("ai_providers_and_models_configuration") or {}
            gemini_cfg = (ai_sec.get("providers") or {}).get("gemini") or {}
            model = gemini_cfg.get("default_model") or gemini_cfg.get("model") or ai_sec.get("default_model")
            if isinstance(model, str) and model.strip():
                return model.strip()
        except Exception as exc:
            logger.debug(f"[AgentsExecutor] Не удалось прочитать default_model из config.json: {exc}")
    return _FALLBACK_GEMINI_MODEL


def _resolve_gemini_model_name(requested_model: str) -> str:
    """Возвращает валидное имя модели Gemini с заменой устаревших идентификаторов."""
    model = (requested_model or "").strip()
    if not model or model in _DEPRECATED_GEMINI_MODELS:
        return _get_default_gemini_model()
    return model


def _load_gemini_api_key() -> str:
    """Получает ключ GEMINI_API_KEY из окружения или хранилища ключей проекта."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if api_key:
        return api_key
    try:
        from src.ai.gemini.gemini_api_key_state import load_api_keys

        loaded, _, _ = load_api_keys()
        aiza_keys = [k for k in loaded if isinstance(k, str) and k.startswith("AIzaSy")]
        if aiza_keys:
            return aiza_keys[0]
        if loaded:
            return str(loaded[0])
    except Exception as exc:
        logger.warning(f"[AgentsExecutor] Не удалось загрузить ключи Gemini: {exc}")
    return ""


def resolve_agent_tools(tool_names: Optional[List[str]]) -> List[Any]:
    """Преобразует список имён инструментов агента в реальные LangChain-инструменты.

    Args:
        tool_names: Список имён или алиасов инструментов из манифеста агента.

    Returns:
        List[Any]: Список уникальных вызываемых инструментов.
    """
    if not tool_names:
        return []

    import src.ai.agents.tools as tools_mod

    resolved: List[Any] = []
    seen_names: set[str] = set()

    for raw_name in tool_names:
        name = str(raw_name).strip()
        if not name:
            continue
        candidate_names = _TOOL_ALIASES.get(name, [name])
        for cand in candidate_names:
            if cand in seen_names:
                continue
            tool_obj = getattr(tools_mod, cand, None)
            if tool_obj is not None:
                resolved.append(tool_obj)
                seen_names.add(cand)

    return resolved


def _create_llm(provider: str, model_name: str, temperature: float) -> Tuple[Any, str]:
    """Создаёт экземпляр LLM для выбранного провайдера и модели.

    Args:
        provider: Идентификатор провайдера (gemini, ollama, openai и др.).
        model_name: Имя модели.
        temperature: Температура генерации.

    Returns:
        Tuple[Any, str]: Кортеж (инстанс LLM, фактически выбранное имя модели).
    """
    prov = (provider or "gemini").strip().lower()

    if prov == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        api_key = _load_gemini_api_key()
        if not api_key:
            raise EnvironmentError("GEMINI_API_KEY не настроен. Укажите ключ в .env или в разделе ключей API.")
        effective_model = _resolve_gemini_model_name(model_name)
        llm = ChatGoogleGenerativeAI(
            model=effective_model,
            google_api_key=api_key,
            temperature=temperature,
        )
        return llm, effective_model

    if prov == "ollama":
        try:
            from langchain_ollama import ChatOllama

            effective_model = (model_name or "qwen2.5-coder").strip()
            base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
            return ChatOllama(model=effective_model, base_url=base_url, temperature=temperature), effective_model
        except ImportError:
            pass

    # Fallback на универсальный фабричный метод чата проекта
    from apps.windows.api.routers.chat.helpers import get_chat_model

    prefixed = model_name if ":" in model_name else f"{prov}:{model_name}"
    return get_chat_model(prefixed), model_name


def _extract_text_content(raw_content: Any) -> str:
    """Извлекает чистый текст из ответа LangChain/Gemini (str или list[dict])."""
    if raw_content is None:
        return ""
    if isinstance(raw_content, str):
        return raw_content.strip()
    if isinstance(raw_content, list):
        parts: List[str] = []
        for item in raw_content:
            if isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(str(text))
            elif item is not None:
                parts.append(str(item))
        return "\n".join(parts).strip()
    return str(raw_content).strip()


def _summarize_tool_output(raw_text: str, max_len: int = 220) -> Tuple[str, bool]:
    """Формирует краткое описание результата инструмента и определяет флаг ошибки."""
    text = (raw_text or "").strip()
    is_error = False
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            if parsed.get("status") == "error" or "error" in parsed:
                is_error = True
                err_msg = parsed.get("error") or parsed.get("message") or text
                text = f"Ошибка: {err_msg}"
            elif "summary" in parsed and isinstance(parsed["summary"], dict):
                summary_items = [f"{k}={v}" for k, v in list(parsed["summary"].items())[:6]]
                text = ", ".join(summary_items)
    except (ValueError, TypeError):
        pass

    if len(text) > max_len:
        text = text[: max_len - 1].rstrip() + "…"
    return text or "пустой результат", is_error


def _build_react_trace(
    messages: List[Any],
    agent_name: str,
    model_name: str,
    tools_count: int,
) -> List[Dict[str, Any]]:
    """Строит пошаговую трассировку ReAct для отображения в Sandbox UI."""
    steps: List[Dict[str, Any]] = [
        {
            "step": 1,
            "type": "tool_init",
            "content": f"Инициализирован агент «{agent_name}» (модель: {model_name}, инструментов: {tools_count})",
        }
    ]
    step_num = 2

    for msg in messages:
        cls_name = type(msg).__name__
        tool_calls = getattr(msg, "tool_calls", None) or []

        if tool_calls:
            for tc in tool_calls:
                t_name = tc.get("name", "unknown_tool") if isinstance(tc, dict) else getattr(tc, "name", "unknown_tool")
                t_args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
                args_str = json.dumps(t_args, ensure_ascii=False) if t_args else ""
                if len(args_str) > 140:
                    args_str = args_str[:139] + "…"
                steps.append(
                    {
                        "step": step_num,
                        "type": "action",
                        "content": f"Вызов инструмента {t_name}({args_str})",
                    }
                )
                step_num += 1
        elif cls_name == "ToolMessage":
            t_name = getattr(msg, "name", "tool")
            raw_out = _extract_text_content(getattr(msg, "content", ""))
            summary, is_err = _summarize_tool_output(raw_out)
            steps.append(
                {
                    "step": step_num,
                    "type": "error" if is_err else "observation",
                    "content": f"Результат {t_name}: {summary}",
                }
            )
            step_num += 1

    steps.append(
        {
            "step": step_num,
            "type": "finish",
            "content": "Рассуждение завершено, сформирован итоговый ответ.",
        }
    )
    return steps


def _create_react_executor(llm: Any, tools: List[Any], system_prompt: str) -> Any:
    """Создаёт граф ReAct-агента совместимо с LangChain 1.x / LangGraph."""
    try:
        from langchain.agents import create_agent

        return create_agent(llm, tools, system_prompt=system_prompt)
    except Exception:
        from langgraph.prebuilt import create_react_agent

        try:
            return create_react_agent(llm, tools, prompt=system_prompt)
        except TypeError:
            return create_react_agent(llm, tools, state_modifier=system_prompt)


async def execute_agent_sandbox(agent_data: Dict[str, Any], query: str) -> Dict[str, Any]:
    """Выполняет реальный запрос пользователя через выбранного агента и его инструменты.

    Args:
        agent_data: Конфигурация агента из реестра / манифеста.
        query: Текстовый запрос пользователя.

    Returns:
        Dict[str, Any]: Словарь с полями status, agent_id, model, duration_ms,
        steps (ReAct Trace), response и output.
    """
    t0 = time.perf_counter()
    agent_id = str(agent_data.get("id") or "generic_agent")
    agent_name = str(agent_data.get("name") or agent_id)
    provider = str(agent_data.get("provider") or "gemini")
    requested_model = str(agent_data.get("model") or _get_default_gemini_model())
    temperature = float(agent_data.get("temperature", 0.1) or 0.1)
    max_steps = int(agent_data.get("max_steps", 15) or 15)
    timeout_seconds = int(agent_data.get("timeout_seconds", 90) or 90)
    system_prompt = str(agent_data.get("system_prompt") or "").strip()
    if not system_prompt:
        system_prompt = (
            f"Вы — автономный ИИ-агент «{agent_name}». "
            "Используйте подключённые инструменты для получения реальных данных и отвечайте на русском языке."
        )

    resolved_tools = resolve_agent_tools(agent_data.get("tools"))
    logger.info(
        f"[AgentsExecutor] Запуск агента '{agent_id}' "
        f"(provider={provider}, model={requested_model}, tools={len(resolved_tools)})"
    )

    try:
        llm, effective_model = _create_llm(provider, requested_model, temperature)

        # Вариант 1: LangChain-совместимая модель + ReAct граф с инструментами
        if hasattr(llm, "bind_tools") and resolved_tools:
            executor = _create_react_executor(llm, resolved_tools, system_prompt)
            result = await asyncio.wait_for(
                executor.ainvoke(
                    {"messages": [("user", query)]},
                    config={"recursion_limit": max(10, max_steps * 2)},
                ),
                timeout=timeout_seconds,
            )
            messages = result.get("messages", [])
            final_text = _extract_text_content(getattr(messages[-1], "content", "")) if messages else ""
            if not final_text:
                final_text = "Агент завершил выполнение без текстового ответа."
            steps = _build_react_trace(messages, agent_name, effective_model, len(resolved_tools))
        # Вариант 2: LangChain-модель без инструментов
        elif hasattr(llm, "ainvoke"):
            res = await asyncio.wait_for(
                llm.ainvoke([("system", system_prompt), ("user", query)]),
                timeout=timeout_seconds,
            )
            final_text = _extract_text_content(getattr(res, "content", res))
            steps = _build_react_trace([], agent_name, effective_model, 0)
        # Вариант 3: Внутренний провайдер чата проекта с методом ask()
        elif hasattr(llm, "ask"):
            full_prompt = f"{system_prompt}\n\nЗапрос пользователя: {query}"
            res = await asyncio.wait_for(llm.ask(full_prompt), timeout=timeout_seconds)
            final_text = _extract_text_content(res)
            steps = _build_react_trace([], agent_name, effective_model, 0)
        else:
            raise RuntimeError(f"Провайдер '{provider}' не поддерживает асинхронный вызов")

        duration_ms = int((time.perf_counter() - t0) * 1000)
        logger.info(f"[AgentsExecutor] Агент '{agent_id}' завершил работу за {duration_ms} мс")
        return {
            "status": "success",
            "agent_id": agent_id,
            "model": effective_model,
            "tools_count": len(resolved_tools),
            "duration_ms": duration_ms,
            "steps": steps,
            "response": final_text,
            "output": final_text,
        }

    except asyncio.TimeoutError:
        duration_ms = int((time.perf_counter() - t0) * 1000)
        err_text = f"Превышен таймаут выполнения агента ({timeout_seconds} сек)."
        logger.error(f"[AgentsExecutor] {err_text} agent_id={agent_id}")
        return {
            "status": "error",
            "agent_id": agent_id,
            "model": requested_model,
            "tools_count": len(resolved_tools),
            "duration_ms": duration_ms,
            "steps": [
                {
                    "step": 1,
                    "type": "tool_init",
                    "content": f"Запуск агента «{agent_name}» (инструментов: {len(resolved_tools)})",
                },
                {"step": 2, "type": "error", "content": err_text},
            ],
            "response": err_text,
            "output": err_text,
        }
    except Exception as exc:
        duration_ms = int((time.perf_counter() - t0) * 1000)
        err_text = f"Ошибка выполнения агента «{agent_name}»: {exc}"
        logger.error(f"[AgentsExecutor] {err_text}", exc_info=True)
        return {
            "status": "error",
            "agent_id": agent_id,
            "model": requested_model,
            "tools_count": len(resolved_tools),
            "duration_ms": duration_ms,
            "steps": [
                {
                    "step": 1,
                    "type": "tool_init",
                    "content": f"Запуск агента «{agent_name}» (инструментов: {len(resolved_tools)})",
                },
                {"step": 2, "type": "error", "content": str(exc)},
            ],
            "response": err_text,
            "output": err_text,
        }


__all__ = ["execute_agent_sandbox", "resolve_agent_tools"]
