# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Scripts Cli Commands - Investigate
# =============================================================================
# Description:
#   Команды CLI для расследования системных инцидентов и запуска универсального
#   ИИ-агента расследований (UniversalLangChainAgent) с потоковым выводом в консоль.
#
# Usage Examples:
#   CLI:
#     py manage_tools.py investigate powershell
#     py manage_tools.py investigate solve "Кто-то постоянно запускает powershell. Найди виновника"
#     py manage_tools.py investigate interactive "Установить на рабочие столы в сети ссылки на Demo"
#
# File: investigate.py
# Project: ai-windows-admin
# Package: scripts.cli.commands
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-17 00:57:00
# =============================================================================

from __future__ import annotations

"""Команды CLI для расследования инцидентов и интерактивного решения системных задач."""

import argparse
import asyncio
import getpass
import json
import sys
from typing import Any, Dict, List, Optional

from logger import logger
from apps.windows.sdk.core.universal_langchain_agent import UniversalLangChainAgent
from apps.windows.sdk.modules.process_manager.router import investigate_powershell


def register_investigate_parser(subparsers: argparse._SubParsersAction) -> None:
    """Регистрирует подкоманды группы investigate в CLI.

    Args:
        subparsers: Экземпляр группы подпарсеров ArgumentParser.
    """
    inv_parser = subparsers.add_parser(
        'investigate',
        help='AI-расследование системных инцидентов и запуск автономного агента'
    )
    inv_sub = inv_parser.add_subparsers(dest='subcommand', help='Подкоманды investigate')

    # 1. Быстрое расследование инцидента с PowerShell
    inv_sub.add_parser(
        'powershell',
        help='Расследовать причину частых запусков powershell.exe в операционной системе'
    )

    # 2. Потоковое решение произвольной задачи через UniversalLangChainAgent
    solve_parser = inv_sub.add_parser(
        'solve',
        help='Решить произвольную системную задачу с динамическим синтезом инструментов'
    )
    solve_parser.add_argument(
        'query',
        nargs='?',
        default='',
        help='Формулировка задачи или вопроса к агенту'
    )
    solve_parser.add_argument(
        '--query',
        '-q',
        dest='query_flag',
        default='',
        help='Альтернативный ключ для передачи формулировки задачи'
    )

    # 3. Интерактивная сессия с поддержкой уточняющих вопросов (HITL)
    interactive_parser = inv_sub.add_parser(
        'interactive',
        help='Запустить интерактивную сессию с возможностью ввода промежуточных данных'
    )
    interactive_parser.add_argument(
        'query',
        nargs='?',
        default='',
        help='Начальная цель сценария'
    )


async def _run_streaming_agent(prompt: str) -> int:
    """Запускает универсального агента в потоковом режиме с выводом в logger.console.

    Args:
        prompt: Запрос пользователя.

    Returns:
        int: Код возврата (0 - успешно, 1 - ошибка).
    """
    logger.console(f"\n[+] Инициализация UniversalLangChainAgent для задачи: \"{prompt}\"...")
    try:
        agent = UniversalLangChainAgent()
    except Exception as exc:
        logger.console(f"[ОШИБКА] Не удалось инициализировать агента: {exc}")
        return 1

    logger.console("[+] Запуск потокового ReAct-цикла рассуждений...\n")

    current_delta_line = False
    try:
        async for event in agent.stream_solve(prompt):
            ev_type = event.get('type')
            if ev_type == 'status':
                if current_delta_line:
                    logger.console()
                    current_delta_line = False
                txt = event.get('text') or event.get('content') or ''
                if txt:
                    logger.console(f"  [СТАТУС] {txt}")
            elif ev_type == 'tool_created':
                if current_delta_line:
                    logger.console()
                    current_delta_line = False
                logger.console(f"\n  [СИНТЕЗ ИНСТРУМЕНТА] Модель создала новый инструмент: {event.get('title')} (`{event.get('tool_name')}`)")
            elif ev_type == 'tool_call':
                if current_delta_line:
                    logger.console()
                    current_delta_line = False
                tool_name = event.get('name') or event.get('tool_name') or 'unknown'
                args_dict = event.get('arguments') or event.get('args') or {}
                args_str = json.dumps(args_dict, ensure_ascii=False)
                logger.console(f"  [ИНСТРУМЕНТ] Вызов: {tool_name}({args_str})")
            elif ev_type == 'tool_result':
                if current_delta_line:
                    logger.console()
                    current_delta_line = False
                res_content = str(event.get('data_preview') or event.get('content') or '')
                if len(res_content) > 300:
                    res_content = res_content[:300] + '... [обрезано]'
                logger.console(f"  [НАБЛЮДЕНИЕ] {res_content}")
            elif ev_type in ('token', 'delta'):
                chunk = event.get('chunk') or event.get('content') or ''
                sys.stdout.write(chunk)
                sys.stdout.flush()
                current_delta_line = True
            elif ev_type in ('done', 'completed'):
                if current_delta_line:
                    logger.console()
                    current_delta_line = False
                logger.console("\n[OK] Задача успешно завершена агентом.\n")
            elif ev_type == 'error':
                if current_delta_line:
                    logger.console()
                    current_delta_line = False
                logger.console(f"\n[ОШИБКА АГЕНТА]: {event.get('content', '')}")
                return 1
        return 0
    except Exception as exc:
        logger.console(f"\n[КРИТИЧЕСКАЯ ОШИБКА]: {exc}")
        return 1


async def _run_interactive_session(prompt: str) -> int:
    """Запускает консольную интерактивную сессию с поддержкой ввода учетных данных.

    Args:
        prompt: Начальный запрос.

    Returns:
        int: Код возврата.
    """
    target_prompt = prompt.strip()
    if not target_prompt:
        logger.console("Введите цель задачи для интерактивного агента:")
        target_prompt = input("> ").strip()

    if not target_prompt:
        logger.console("[ОТМЕНА] Пустая формулировка задачи.")
        return 1

    logger.console(f"\n=== ИНТЕРАКТИВНЫЙ АГЕНТ (HITL) ===")
    logger.console(f"Цель: {target_prompt}")
    logger.console("Для передачи параметров во время пауз используйте приглашение ввода.\n")

    return await _run_streaming_agent(target_prompt)


def run_investigate_command(args: argparse.Namespace) -> int:
    """Точка входа для обработки команд группы investigate.

    Args:
        args: Разобранные аргументы командной строки.

    Returns:
        int: Код возврата процесса.
    """
    sub = getattr(args, 'subcommand', None)

    if sub == 'powershell':
        logger.console("\n=== РАССЛЕДОВАНИЕ ИНЦИДЕНТА: ЗАПУСКИ POWERSHELL.EXE ===")
        logger.console("[+] Сбор системных доказательств, WDDM-счетчиков и телеметрии...")
        try:
            report = asyncio.run(investigate_powershell())
            logger.console(f"\nСтатус расследования: {report.get('status', 'UNKNOWN')}")
            logger.console(f"Главный вердикт: {report.get('verdict', 'Не определен')}")
            logger.console(f"Целевой процесс: {report.get('target', 'powershell.exe')}")
            logger.console(f"Интервал опроса: ~{report.get('frequency_interval_sec', 5)} сек")

            code_loc = report.get('code_location', {})
            if code_loc:
                logger.console(f"Источник вызова: {code_loc.get('file')}:{code_loc.get('line')} ({code_loc.get('function')})")

            trigger = report.get('trigger', {})
            if trigger:
                logger.console(f"Служба / Запланированная задача: {trigger.get('task_name')} ({trigger.get('parent_daemon')})")

            running = report.get('active_powershell_instances', [])
            logger.console(f"\nАктивных процессов PowerShell в данный момент: {len(running)}")
            for p in running:
                logger.console(f"  • PID: {p.get('pid')}, Родительский PID: {p.get('ppid')}, Команда: {p.get('cmdline')}")

            total_sess = report.get('total_detected_sessions', 0)
            logger.console(f"\nВсего зафиксировано сессий в telemetry.db: {total_sess}")
            if report.get('last_seen'):
                logger.console(f"Последняя активность в БД: {report.get('last_seen')}")

            recs = report.get('recommendations', [])
            if recs:
                logger.console(f"\nРекомендации по устранению:")
                for r in recs:
                    logger.console(f"  - {r}")
            logger.console()
            return 0
        except Exception as exc:
            logger.console(f"[ОШИБКА] Сбой при сборе данных расследования: {exc}")
            return 1

    elif sub in ('solve', 'ask'):
        prompt = getattr(args, 'query_flag', '') or getattr(args, 'query', '')
        if not prompt.strip():
            logger.console("Ошибка: укажите формулировку задачи. Пример:")
            logger.console('  py manage_tools.py investigate solve "Кто-то постоянно запускает powershell"')
            return 1
        return asyncio.run(_run_streaming_agent(prompt))

    elif sub == 'interactive':
        prompt = getattr(args, 'query', '')
        return asyncio.run(_run_interactive_session(prompt))

    logger.console(f"Неизвестная подкоманда investigate: {sub}")
    logger.console("Доступные подкоманды: powershell, solve, interactive")
    return 1

