# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Code Helper - CLI Entrypoint
# =============================================================================
# Description:
#   Автономный CLI интерфейс для управления Code Helper:
#   сборка индексов кода, поиск символов, тестирование подключения к MariaDB
#   на Hostinger, диагностика ошибок и запуск автономного сервера.
#
# Usage Examples:
#   CLI:
#     py -m apps.code_helper status
#     py -m apps.code_helper db-test
#     py -m apps.code_helper build --root . --name codebase
#     py -m apps.code_helper search "def execute"
#     py -m apps.code_helper symbols "CodeHelperStorage"
#     py -m apps.code_helper diagnose --error "ZeroDivisionError: division by zero"
#     py -m apps.code_helper serve --port 8105
#
# File: __main__.py
# Project: ai-windows-admin
# Package: apps.code_helper
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 17:10:00
# =============================================================================

from __future__ import annotations

"""CLI интерфейс автономного микроприложения Code Helper."""

import argparse
import asyncio
import json
import sys

from logger import logger
from .rag import CodeHelperRAG
from .server import run_standalone_server


def main() -> int:
    """Главная точка входа командной строки Code Helper."""
    parser = argparse.ArgumentParser(
        prog="py -m apps.code_helper",
        description="Code Helper — автономная система RAG исходного кода и диагностики (Hostinger MariaDB)",
    )
    subparsers = parser.add_subparsers(dest="command", help="Команда для выполнения")

    # status
    subparsers.add_parser("status", help="Проверка статуса базы знаний и хранилища")

    # db-test
    subparsers.add_parser("db-test", help="Тестирование прямого соединения с MariaDB на Hostinger")

    # build
    build_p = subparsers.add_parser("build", help="Сборка AST-индекса кодовой базы")
    build_p.add_argument("--root", default=".", help="Корневой каталог для сканирования")
    build_p.add_argument("--name", default="codebase", help="Имя индекса")
    build_p.add_argument("--no-markdown", action="store_true", help="Отключить индексацию .md файлов")

    # search
    search_p = subparsers.add_parser("search", help="Поиск фрагментов кода и документации")
    search_p.add_argument("query", help="Поисковый запрос")
    search_p.add_argument("--name", default="codebase", help="Имя индекса")
    search_p.add_argument("--top-k", type=int, default=5, help="Количество результатов")

    # symbols
    sym_p = subparsers.add_parser("symbols", help="Поиск функций, классов и методов AST")
    sym_p.add_argument("symbol", help="Имя или префикс символа")
    sym_p.add_argument("--name", default="codebase", help="Имя индекса")
    sym_p.add_argument("--limit", type=int, default=10, help="Лимит результатов")

    # diagnose
    diag_p = subparsers.add_parser("diagnose", help="Диагностика ошибки или вопроса по коду")
    diag_p.add_argument("--error", default="", help="Сообщение об ошибке или Traceback")
    diag_p.add_argument("--question", default="", help="Вопрос по архитектуре")
    diag_p.add_argument("--name", default="codebase", help="Имя индекса")

    # serve
    serve_p = subparsers.add_parser("serve", help="Запуск автономного ASGI веб-сервера")
    serve_p.add_argument("--host", default="127.0.0.1", help="Хост для привязки")
    serve_p.add_argument("--port", type=int, default=8105, help="Порт сервера")

    args = parser.parse_args()
    rag = CodeHelperRAG()

    if args.command == "status":
        info = rag.storage.test_connection()
        indexes = rag.storage.list_indexes()
        logger.console(f"Активный движок хранилища: {rag.storage.active_engine}")
        logger.console(f"Статус подключения Hostinger: {info.get('status')}")
        logger.console(f"Целевая база Hostinger: {info.get('database')} (пользователь: {info.get('user')})")
        logger.console(f"Локальный кэш SQLite: {rag.storage.sqlite_path}")
        logger.console(f"Всего индексов в базе: {len(indexes)}")
        for idx in indexes:
            logger.console(
                f"  - {idx.get('name')}: {idx.get('total_files')} файлов, "
                f"{idx.get('total_chunks')} чанков, {idx.get('total_symbols')} символов "
                f"({idx.get('storage_engine')})"
            )
        return 0

    if args.command == "db-test":
        logger.console("Тестирование соединения с Hostinger MariaDB...")
        res = rag.storage.test_connection()
        logger.console(json.dumps(res, ensure_ascii=False, indent=2))
        if res.get("status") == "connected":
            logger.console("Подключение к MariaDB на Hostinger успешно установлено!")
            return 0
        else:
            logger.console("Внимание: прямое подключение к Hostinger не удалось. Активен локальный fallback SQLite.")
            if res.get("hostinger_instruction"):
                logger.console(f"Подсказка: {res['hostinger_instruction']}")
            return 1

    if args.command == "build":
        logger.console(f"Сборка индекса '{args.name}' из каталога '{args.root}'...")
        stats = rag.build_index(
            project_root=args.root,
            index_name=args.name,
            include_markdown=not args.no_markdown,
        )
        logger.console(
            f"Индекс успешно собран за {stats.elapsed_seconds}с: {stats.total_files} файлов, "
            f"{stats.total_chunks} чанков, {stats.total_symbols} символов AST. "
            f"Движок: {stats.storage_engine}"
        )
        return 0

    if args.command == "search":
        logger.console(f"Поиск по запросу '{args.query}' в индексе '{args.name}'...")
        results = rag.search_code(args.query, index_name=args.name, top_k=args.top_k)
        if not results:
            logger.console("Ничего не найдено.")
            return 0
        for i, r in enumerate(results, 1):
            logger.console(
                f"[{i}] {r.get('symbol_type', '').upper()} {r.get('symbol_name')} "
                f"({r.get('file_path')}:{r.get('start_line')}-{r.get('end_line')}) "
                f"Score: {r.get('relevance_score')}"
            )
            logger.console(f"    {r.get('signature') or r.get('snippet', '')[:100]}")
        return 0

    if args.command == "symbols":
        logger.console(f"Поиск символов AST '{args.symbol}'...")
        results = rag.search_symbols(args.symbol, index_name=args.name, limit=args.limit)
        if not results:
            logger.console("Символы не найдены.")
            return 0
        for i, r in enumerate(results, 1):
            logger.console(
                f"[{i}] {r.get('symbol_type')} {r.get('symbol')} "
                f"({r.get('file_path')}:{r.get('start_line')}) -> {r.get('signature')}"
            )
        return 0

    if args.command == "diagnose":
        logger.console("Запуск диагностики...")
        conclusion = asyncio.run(
            rag.diagnose(
                question=args.question,
                error_message=args.error,
                index_name=args.name,
            )
        )
        logger.console(f"Резюме: {conclusion.summary}")
        logger.console(f"Первопричина: {conclusion.root_cause}")
        logger.console(f"Объяснение: {conclusion.explanation}")
        logger.console(f"Критичность: {conclusion.severity} (Уверенность: {conclusion.confidence})")
        if conclusion.affected_locations:
            logger.console("Затронутый код:")
            for loc in conclusion.affected_locations:
                logger.console(f"  - {loc.file_path}:{loc.start_line} [{loc.symbol_name}]")
        if conclusion.remediation_steps:
            logger.console("План исправления:")
            for s in conclusion.remediation_steps:
                logger.console(f"  * {s.title}: {s.description}")
        return 0

    if args.command == "serve":
        run_standalone_server(host=args.host, port=args.port)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
