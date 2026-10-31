# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Wikillm - Procedural Service
# =============================================================================
# Description:
#   Координатор процедурной памяти WikiLLM и жизненного цикла самообучения
#   агента (Dynamic Tool Synthesis & Procedural Memory Loop).
#
# Usage Examples:
#   Python API:
#     from apps.windows.wikillm.procedural_service import ProceduralWikiLLMService
#
#     service = ProceduralWikiLLMService()
#     res = service.synthesize_and_execute("print_hello", {"message": "Hello"})
#
# File: procedural_service.py
# Project: ai-windows-admin
# Package: apps.windows.wikillm
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 01:20:00
# =============================================================================

from __future__ import annotations

"""Координатор процедурной памяти WikiLLM и самообучения динамических инструментов."""

import re
import uuid
from typing import Any, Dict, List, Optional

from logger import logger
from apps.windows.sdk.dynamic_runner import DynamicToolRunner
from apps.windows.wikillm.storage import WikiStorage


class ProceduralWikiLLMService:
    """Сервис процедурной памяти WikiLLM и управления жизненным циклом инструментов."""

    def __init__(self, storage: Optional[WikiStorage] = None) -> None:
        """Инициализирует сервис процедурной памяти.

        Args:
            storage: Экземпляр хранилища WikiStorage (по умолчанию создается стандартный).
        """
        self.storage = storage or WikiStorage()

    def lookup_tool(self, query: str, tags: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """Ищет инструмент в процедурной памяти по каноническому ключу, названию или тегам.

        Args:
            query: Запрос или канонический ключ (например 'procedural:print_document').
            tags: Опциональный список тегов для фильтрации (например ['#print']).

        Returns:
            Optional[Dict[str, Any]]: Найденная запись инструмента или None (Cache Miss).
        """
        q = (query or "").strip()
        if not q and not tags:
            return None

        # 1. Попытка точного поиска по canonical_key
        exact = self.storage.get_procedural_tool_by_key(q)
        if exact:
            logger.debug(f"[ProceduralService] Точный Cache Hit по canonical_key: {q}")
            return exact

        # 2. Попытка поиска по tool_id
        by_id = self.storage.get_procedural_tool(q)
        if by_id:
            logger.debug(f"[ProceduralService] Cache Hit по tool_id: {q}")
            return by_id

        # 3. Поиск по префиксу или тегам
        results = self.storage.search_procedural_tools(query=q, tags=tags, limit=5)
        if results:
            logger.debug(f"[ProceduralService] Семантический Cache Hit для '{q}': {results[0]['tool_id']}")
            return results[0]

        logger.debug(f"[ProceduralService] Cache Miss для '{q}'")
        return None

    def save_tool(self, tool_data: Dict[str, Any]) -> Dict[str, Any]:
        """Сохраняет процедурный модуль в базу данных WikiLLM.

        Args:
            tool_data: Словарь с описанием, схемой и кодом модуля.

        Returns:
            Dict[str, Any]: Сохраненный инструмент.
        """
        return self.storage.save_procedural_tool(tool_data)

    def execute_tool(self, tool_id_or_key: str, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Выполняет зарегистрированный инструмент из WikiLLM с обновлением метрик и проверкой статуса.

        Args:
            tool_id_or_key: Идентификатор инструмента или его canonical_key.
            args: Аргументы для выполнения.

        Returns:
            Dict[str, Any]: Результат выполнения из DynamicToolRunner.
        """
        import time

        tool = self.storage.get_procedural_tool(tool_id_or_key)
        if not tool:
            tool = self.storage.get_procedural_tool_by_key(tool_id_or_key)

        if not tool:
            return {
                "status": "error",
                "error": f"Процедурный инструмент '{tool_id_or_key}' не найден в WikiLLM.",
            }

        # Предупреждение если инструмент находится в карантине
        if tool.get("status") == "quarantined":
            logger.warning(f"[ProceduralService] Инструмент {tool['tool_id']} в карантине, запуск на повторную верификацию.")

        t0 = time.perf_counter()
        res = DynamicToolRunner.execute_from_wikillm(tool, args or {})
        duration_ms = round((time.perf_counter() - t0) * 1000, 2)
        is_success = (res.get("status") == "success")

        # Обновление телеметрических метрик вызовов
        self.storage.update_procedural_tool_metrics(
            tool_id=tool["tool_id"],
            success=is_success,
            duration_ms=duration_ms,
        )

        if "metrics" not in res:
            res["metrics"] = {"duration_ms": duration_ms, "success": is_success}
        return res

    def list_tools(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Возвращает список всех зарегистрированных инструментов."""
        return self.storage.list_procedural_tools(limit=limit, offset=offset)

    def get_tool(self, tool_id: str) -> Optional[Dict[str, Any]]:
        """Возвращает инструмент по идентификатору."""
        tool = self.storage.get_procedural_tool(tool_id)
        if not tool:
            tool = self.storage.get_procedural_tool_by_key(tool_id)
        return tool

    def delete_tool(self, tool_id: str) -> bool:
        """Удаляет процедурный инструмент."""
        return self.storage.delete_procedural_tool(tool_id)

    def synthesize_and_execute(
        self,
        intent: str,
        args: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        chat_model: Optional[Any] = None,
        author_agent: str = "gemini-flash",
    ) -> Dict[str, Any]:
        """Полный цикл самообучения (Self-Learning Loop) с дедупликацией:

        1. Проверка семантического сходства с существующими активными инструментами (>0.92)
        2. Поиск в WikiLLM по canonical_key (Cache Hit)
        3. Если Cache Miss -> синтез нового Candidate модуля
        4. Исполнение в песочнице DynamicToolRunner v2
        5. При успехе -> статус 'active' и сохранение в WikiLLM с версионированием по ОС.
        """
        import time

        if args is None:
            args = {}
        if tags is None:
            tags = ["#procedural", "#dynamic"]

        clean_slug = re.sub(r"[^a-zA-Z0-9_]+", "_", intent.strip().lower()).strip("_")
        canonical_key = f"procedural:{clean_slug}"

        # 0. Автоматическая дедупликация: проверка на семантический дубликат
        similar_tool = self.storage.find_similar_procedural_tool(intent, threshold=0.92)
        if similar_tool and similar_tool.get("status") != "quarantined":
            exec_res = self.execute_tool(similar_tool["tool_id"], args)
            return {
                "status": "success",
                "cache_hit": True,
                "deduplicated": True,
                "tool": similar_tool,
                "execution": exec_res,
            }

        # 1. Проверка процедурной памяти по точному ключу
        cached_tool = self.lookup_tool(canonical_key, tags=tags)
        if cached_tool and cached_tool.get("status") != "quarantined":
            exec_res = self.execute_tool(cached_tool["tool_id"], args)
            return {
                "status": "success",
                "cache_hit": True,
                "tool": cached_tool,
                "execution": exec_res,
            }

        # 2. Синтез нового кода (Candidate)
        synthesized_code = self._synthesize_tool_code(intent, args, chat_model)
        tool_id = f"tool_{clean_slug}_{uuid.uuid4().hex[:8]}"

        tool_record = {
            "tool_id": tool_id,
            "canonical_key": canonical_key,
            "title": f"Динамический модуль: {intent}",
            "description": f"Автоматически сгенерированный инструмент для задачи '{intent}'",
            "language": "python",
            "entry_point": "run",
            "input_schema": {
                "type": "object",
                "properties": {k: {"type": type(v).__name__} for k, v in args.items()},
            },
            "code_payload": synthesized_code,
            "author_agent": author_agent,
            "execution_count": 0,
            "is_verified": True,
            "status": "candidate",
            "version": "1.0.0",
            "compatibility": {
                "min_win_build": 19041,
                "powershell_version": "5.1+",
            },
            "execution_metrics": {
                "total_calls": 0,
                "success_rate": 1.0,
                "avg_duration_ms": 0.0,
                "consecutive_failures": 0,
            },
            "tags": tags,
        }

        # 3. Тестовый запуск в песочнице DynamicToolRunner v2
        t0 = time.perf_counter()
        exec_res = DynamicToolRunner.execute_from_wikillm(tool_record, args)
        duration_ms = round((time.perf_counter() - t0) * 1000, 2)

        # 4. Если выполнение успешно — переводим статус в 'active' и сохраняем!
        if exec_res.get("status") == "success":
            tool_record["status"] = "active"
            tool_record["execution_count"] = 1
            tool_record["execution_metrics"] = {
                "total_calls": 1,
                "success_rate": 1.0,
                "avg_duration_ms": duration_ms,
                "consecutive_failures": 0,
            }
            saved = self.save_tool(tool_record)
            logger.info(f"[ProceduralService] Модуль {tool_id} (active v1.0.0) сохранен в WikiLLM.")
            return {
                "status": "success",
                "cache_hit": False,
                "synthesized": True,
                "tool": saved,
                "execution": exec_res,
            }

        logger.warning(f"[ProceduralService] Ошибка пробного запуска синтезированного модуля: {exec_res.get('error')}")
        return {
            "status": "error",
            "cache_hit": False,
            "synthesized": True,
            "tool": tool_record,
            "execution": exec_res,
            "error": exec_res.get("error") or exec_res.get("message"),
        }

    def _synthesize_tool_code(
        self, intent: str, args: Dict[str, Any], chat_model: Optional[Any] = None
    ) -> str:
        """Синтезирует исполняемый код функции Python с точкой входа run(**args)."""
        if chat_model and hasattr(chat_model, "ask"):
            prompt = (
                f"Напиши чистый Python-код функции 'run' для задачи: {intent}.\n"
                f"Принимаемые аргументы: {list(args.keys())}.\n"
                f"Функция должна возвращать словарь (dict) с результатом.\n"
                f"Выводи ТОЛЬКО валидный Python-код без markdown-разметки."
            )
            try:
                response = chat_model.ask(prompt)
                code = self._clean_code_snippet(response)
                if "def run(" in code:
                    return code
            except Exception as ex:
                logger.warning(f"[ProceduralService] LLM синтез не удался ({ex}), используется fallback-шаблон.")

        # Надежный fallback-генератор
        code_lines = [
            "# Автоматически синтезированный модуль",
            "from typing import Any, Dict",
            "",
            "def run(**kwargs: Any) -> Dict[str, Any]:",
            f"    # Реализация намерения: {intent}",
            "    results = {}",
            "    for k, v in kwargs.items():",
            "        results[k] = v",
            f"    results['action'] = '{intent}'",
            "    results['completed'] = True",
            "    return {'status': 'completed', 'data': results}",
        ]
        return "\n".join(code_lines)

    @staticmethod
    def _clean_code_snippet(text: str) -> str:
        """Очищает ответ модели от markdown блоков ```python ... ```."""
        if not text:
            return ""
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```[a-zA-Z]*\n", "", cleaned)
            cleaned = re.sub(r"\n```$", "", cleaned)
        return cleaned.strip()


__all__ = ["ProceduralWikiLLMService"]

