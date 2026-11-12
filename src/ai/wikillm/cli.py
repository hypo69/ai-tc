# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Wikillm - Cli
# =============================================================================
# Description:
#   Консольный интерфейс управления и запросов к базе знаний WikiLLM.
#
# Usage Examples:
#   CLI:
#     python -m src.ai.wikillm.cli
#   Python API:
#     from src.ai.wikillm.cli import main
#
#     res = main()
#
# File: cli.py
# Project: ai-windows-admin
# Package: src.ai.wikillm
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 22:22:44
# =============================================================================

from __future__ import annotations
from logger import logger
"""Консольный интерфейс управления и запросов к базе знаний WikiLLM."""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from .code_indexer import CodeKnowledgeIndexer
from .command_indexer import CommandKnowledgeIndexer
from .config import WikiLLMConfig
from .engine import WikiLLMEngine
from .extractor import ArtifactExtractor
from .models import ArtifactInput
from .storage import WikiStorage


async def _async_cli_main(args: argparse.Namespace) -> None:
    """Асинхронная точка входа для командной строки."""
    db_path = getattr(args, "db", None)
    config = WikiLLMConfig(database_path=db_path) if db_path else None
    storage = WikiStorage(db_path) if db_path else None
    engine = WikiLLMEngine(config=config, storage=storage)

    if args.command == "resolve":
        extracted = ArtifactExtractor.from_raw_text(args.query)
        art = extracted[0] if extracted else ArtifactInput(raw_query=args.query)
        logger.console(f"[*] Разрешение артефакта: {args.query}...")
        res = await engine.resolve(art, sync_gemini=not args.no_llm)
        logger.console(f"\n[+] Результат ({res.lookup_level.value}, cached={res.cached}, {res.execution_time_ms:.1f}ms):")
        if res.entity:
            logger.console(f"  Ключ:        {res.entity.canonical_key}")
            logger.console(f"  Имя:         {res.entity.name}")
            logger.console(f"  Категория:   {res.entity.category} ({res.entity.severity})")
            logger.console(f"  Сводка:      {res.entity.summary}")
            if res.entity.diagnostic_info:
                if res.entity.diagnostic_info.possible_causes:
                    logger.console(f"  Причины:     {', '.join(res.entity.diagnostic_info.possible_causes)}")
                if res.entity.diagnostic_info.remediation_steps:
                    logger.console("  Шаги устранения / Команда:")
                    for s in res.entity.diagnostic_info.remediation_steps:
                        cmd_info = f" -> `{s.command}`" if s.command else ""
                        logger.console(f"    • {s.title}: {s.description}{cmd_info}")
        else:
            logger.console(f"  [-] {res.message}")

    elif args.command == "search":
        results = engine.storage.search_fts(args.query, limit=args.limit)
        logger.console(f"[+] Найдено результатов: {len(results)}")
        for ent in results:
            logger.console(f"  • [{ent.canonical_key}] {ent.name} - {ent.summary[:80]}...")

    elif args.command == "index-code":
        indexer = CodeKnowledgeIndexer(engine.storage)
        logger.console(f"[*] Индексация исходного кода из {args.path}...")
        count = indexer.index_directory(args.path)
        logger.console(f"[+] Успешно проиндексировано {count} символов.")

    elif args.command == "index-commands":
        indexer = CommandKnowledgeIndexer(engine.storage)
        logger.console(f"[*] Индексация атомарных команд, скриптов и коллекторов телеметрии...")
        stats = indexer.index_all()
        logger.console(f"[+] Индексация завершена успешно:")
        logger.console(f"    • Атомарные команды Windows: {stats['atomic_capabilities']}")
        logger.console(f"    • Коллекторы телеметрии:     {stats['telemetry_collectors']}")
        logger.console(f"    • Параметры SafeOps:         {stats['system_params']}")
        logger.console(f"    • ИТОГО в базе знаний:       {stats['total_commands_indexed']}")

    elif args.command == "stats":
        metrics = engine.get_metrics()
        logger.console(json.dumps(metrics, indent=2, ensure_ascii=False))

    elif args.command == "tui":
        from .tui import run_tui
        await run_tui(engine)

    else:
        logger.console("Неизвестная команда. Используйте --help для справки.")


def main() -> None:
    """Главная синхронная точка входа CLI."""
    parser = argparse.ArgumentParser(description="WikiLLM: Progressive Knowledge Base CLI")
    parser.add_argument("--db", default=None, help="Пользовательский путь к базе SQLite (по умолчанию: data/windows_wikillm/knowledge.db)")
    subparsers = parser.add_subparsers(dest="command", help="Команды")

    # resolve
    p_res = subparsers.add_parser("resolve", help="Разрешить ошибку, команду, Event ID или симптом")
    p_res.add_argument("query", help="Код ошибки, команда (cmd:diskpart.disk.list) или запрос")
    p_res.add_argument("--no-llm", action="store_true", help="Не вызывать Gemini при промахе кэша")

    # search
    p_search = subparsers.add_parser("search", help="Полнотекстовый поиск в базе знаний")
    p_search.add_argument("query", help="Поисковая фраза")
    p_search.add_argument("--limit", type=int, default=10, help="Лимит результатов")

    # index-code
    p_idx = subparsers.add_parser("index-code", help="Индексация кода в слой Code Knowledge")
    p_idx.add_argument("--path", default="apps/windows", help="Путь к каталогу с кодом")

    # index-commands
    subparsers.add_parser("index-commands", help="Индексация команд, скриптов и коллекторов телеметрии")

    # stats
    subparsers.add_parser("stats", help="Статистика базы знаний и эффективность кэша")

    # tui
    subparsers.add_parser("tui", help="Запуск интерактивного TUI терминала")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    asyncio.run(_async_cli_main(args))


if __name__ == "__main__":
    main()

