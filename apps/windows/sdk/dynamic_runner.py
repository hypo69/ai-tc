# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows SDK - Dynamic Tool Runner v2
# =============================================================================
# Description:
#   Исполнительная среда и изолированная песочница DynamicToolRunner v2
#   с двухшаговой валидацией (AST-анализ и Pydantic-санитизация аргументов)
#   для процедурной памяти WikiLLM (Спецификация 14).
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.dynamic_runner import DynamicToolRunner
#
#     res = DynamicToolRunner.execute_from_wikillm(tool_record, {"text": "hello"})
#
# File: dynamic_runner.py
# Project: ai-windows-admin
# Package: apps.windows.sdk
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 01:20:00
# =============================================================================

from __future__ import annotations

"""Исполнительная среда и песочница для динамически синтезированных модулей из WikiLLM."""

import asyncio
import inspect
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from logger import logger
from apps.windows.sdk.security_ast import DynamicToolInputContract, validate_code_security


class DynamicToolRunner:
    """Исполнительная среда DynamicToolRunner v2 для динамических модулей."""

    @classmethod
    def execute_code(
        cls,
        code_str: str,
        entry_point: str = "run",
        args: Optional[Dict[str, Any]] = None,
        tool_id: str = "dynamic_tool",
        author_agent: str = "agent",
        canonical_key: str = "unknown",
        skip_security: bool = False,
    ) -> Dict[str, Any]:
        """Динамически валидирует, компилирует и исполняет исходный код Python.

        Args:
            code_str: Исходный код Python для исполнения.
            entry_point: Имя целевой функции (точки входа).
            args: Аргументы для передачи в точку входа.
            tool_id: Идентификатор инструмента для логирования.
            author_agent: Имя агента-автора кода.
            canonical_key: Канонический ключ инструмента.
            skip_security: Флаг отключения проверки безопасности (только для доверенных внутренних тестов).

        Returns:
            Dict[str, Any]: Словарь со статусом выполнения и результатом или ошибкой.
        """
        if args is None:
            args = {}

        if not code_str or not code_str.strip():
            logger.warning(f"[DynamicToolRunner v2] Модуль {tool_id} содержит пустой код.")
            return {"status": "error", "error": "Пустой код модуля для выполнения"}

        # 🛡️ ШАГ 1: AST-анализ синтаксического дерева
        if not skip_security:
            is_safe, violations = validate_code_security(
                code_str=code_str,
                author_agent=author_agent,
                canonical_key=canonical_key or tool_id,
            )
            if not is_safe:
                if any("Синтаксическая ошибка" in v or "пуст" in v for v in violations):
                    return {
                        "status": "error",
                        "error": violations[0],
                    }
                return {
                    "status": "security_violation",
                    "errors": violations,
                    "message": "Код отклонен AST-анализатором из-за нарушения правил безопасности.",
                }

        # 🛡️ ШАГ 2: Pydantic-санитизация входных аргументов
        if not skip_security and args:
            try:
                contract = DynamicToolInputContract(tool_id=tool_id, args=args)
                args = contract.args
            except Exception as val_err:
                err_msg = str(val_err)
                logger.warning(f"[DynamicToolRunner v2] Санитизация отклонила аргументы {tool_id}: {err_msg}")
                return {
                    "status": "security_violation",
                    "errors": [err_msg],
                    "message": f"Аргументы отклонены валидатором безопасности: {err_msg}",
                }

        # 🛡️ ШАГ 3: Изолированное исполнение и гарантированная очистка ресурсов
        temp_files_to_cleanup: List[str] = []
        module_scope: Dict[str, Any] = {
            "__builtins__": __builtins__,
            "__name__": f"__dynamic_tool_{tool_id}__",
        }

        try:
            compiled = compile(code_str, f"<dynamic_tool:{tool_id}>", "exec")
            exec(compiled, module_scope)

            if entry_point not in module_scope:
                err_msg = f"Точка входа '{entry_point}' не найдена в модуле {tool_id}."
                logger.error(f"[DynamicToolRunner v2] {err_msg}")
                return {"status": "error", "error": err_msg}

            func = module_scope[entry_point]
            if not callable(func):
                err_msg = f"Объект '{entry_point}' в модуле {tool_id} не является вызываемой функцией."
                logger.error(f"[DynamicToolRunner v2] {err_msg}")
                return {"status": "error", "error": err_msg}

            # Поддержка как синхронных, так и асинхронных функций
            if inspect.iscoroutinefunction(func):
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None

                if loop and loop.is_running():
                    future = asyncio.run_coroutine_threadsafe(func(**args), loop)
                    result = future.result(timeout=30)
                else:
                    result = asyncio.run(func(**args))
            else:
                result = func(**args)

            logger.info(f"[DynamicToolRunner v2] Успешно выполнен модуль {tool_id}")
            return {"status": "success", "output": result}

        except Exception as exc:
            err_text = str(exc)
            logger.error(f"[DynamicToolRunner v2] Ошибка выполнения модуля {tool_id}: {err_text}")
            return {"status": "error", "error": err_text}

        finally:
            # Гарантированное удаление временных файлов
            for p in temp_files_to_cleanup:
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass

    @classmethod
    def execute_from_wikillm(
        cls,
        tool_record: Dict[str, Any],
        args: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Динамически валидирует и исполняет код модуля из записи WikiLLM.

        Args:
            tool_record: Запись процедурного инструмента из WikiLLM.
            args: Входные параметры вызова.

        Returns:
            Dict[str, Any]: Результат выполнения модуля.
        """
        code_str = tool_record.get("code_payload", "")
        entry_point = tool_record.get("entry_point", "run")
        tool_id = tool_record.get("tool_id", "unnamed_tool")
        author_agent = tool_record.get("author_agent", "agent")
        canonical_key = tool_record.get("canonical_key", tool_id)

        return cls.execute_code(
            code_str=code_str,
            entry_point=entry_point,
            args=args,
            tool_id=tool_id,
            author_agent=author_agent,
            canonical_key=canonical_key,
        )


__all__ = ["DynamicToolRunner"]

