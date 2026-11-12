# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Wikillm - Tui
# =============================================================================
# Description:
#   Интерактивный консольный терминал для исследования, поиска и разрешения
#
# Usage Examples:
#   Python API:
#     import src.ai.wikillm.tui as tui
#
# File: tui.py
# Project: ai-windows-admin
# Package: src.ai.wikillm
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 22:22:44
# =============================================================================

from __future__ import annotations
from logger import logger
"""Интерактивный консольный терминал для исследования, поиска и разрешения"""

import asyncio
from typing import Optional
from .engine import WikiLLMEngine
from .extractor import ArtifactExtractor
from .models import ArtifactInput


async def run_tui(engine: Optional[WikiLLMEngine] = None) -> None:
    """Запускает интерактивный TUI цикл в консоли."""
    eng = engine or WikiLLMEngine()
    await eng.start()

    logger.console("\n" + "=" * 70)
    logger.console(" 🧠 WikiLLM: Progressive Windows Knowledge Terminal")
    logger.console(" Команды: ':stats', ':list', ':q' для выхода")
    logger.console("=" * 70 + "\n")

    try:
        while True:
            try:
                user_input = input("WikiLLM> ").strip()
            except (EOFError, KeyboardInterrupt):
                break

            if not user_input:
                continue

            if user_input.lower() in (":q", ":quit", "exit"):
                break

            if user_input == ":stats":
                metrics = eng.get_metrics()
                logger.console("\n📊 Статистика базы знаний:")
                logger.console(f"  Сущностей в БД:      {metrics['storage_stats']['total_entities']}")
                logger.console(f"  Наблюдений артефактов: {metrics['storage_stats']['total_observation_events']}")
                logger.console(f"  Всего запросов:      {metrics['lookup_stats']['total_requests']}")
                logger.console(f"  L1 Exact Hits:       {metrics['lookup_stats']['l1_exact_hits']}")
                logger.console(f"  L2 Fingerprint Hits: {metrics['lookup_stats']['l2_fingerprint_hits']}")
                logger.console(f"  L3 Semantic Hits:    {metrics['lookup_stats']['l3_semantic_hits']}")
                logger.console(f"  L4 Gemini Синтез:    {metrics['lookup_stats']['l4_gemini_resolutions']}")
                logger.console(f"  Cache Hit Rate:      {metrics['cache_hit_rate_pct']}%\n")
                continue

            if user_input == ":list":
                entities = eng.storage.list_entities(limit=20)
                logger.console(f"\n📑 Последние {len(entities)} записей базы знаний:")
                for e in entities:
                    logger.console(f"  • [{e.canonical_key}] {e.name} ({e.category})")
                logger.console()
                continue

            # Разрешение пользовательского запроса
            extracted = ArtifactExtractor.from_raw_text(user_input)
            art = extracted[0] if extracted else ArtifactInput(raw_query=user_input)

            logger.console(f"[*] Поиск артефакта '{art.raw_query or user_input}'...")
            res = await eng.resolve(art, sync_gemini=True)

            logger.console(f"\n[+] Уровень: {res.lookup_level.value.upper()} | Время: {res.execution_time_ms:.1f} мс | Кэш: {res.cached}")
            if res.entity:
                logger.console(f"  Ключ:        {res.entity.canonical_key}")
                logger.console(f"  Имя:         {res.entity.name}")
                logger.console(f"  Категория:   {res.entity.category} ({res.entity.severity})")
                logger.console(f"  Сводка:      {res.entity.summary}")
                if res.entity.diagnostic_info and res.entity.diagnostic_info.possible_causes:
                    logger.console(f"  Причины:     {', '.join(res.entity.diagnostic_info.possible_causes)}")
                if res.entity.diagnostic_info and res.entity.diagnostic_info.remediation_steps:
                    logger.console("  Шаги устранения:")
                    for s in res.entity.diagnostic_info.remediation_steps:
                        logger.console(f"    -> {s.title}: {s.description}")
            else:
                logger.console(f"  [-] {res.message}")
            logger.console()

    finally:
        await eng.stop()
        logger.console("\nЗавершение работы WikiLLM.")

