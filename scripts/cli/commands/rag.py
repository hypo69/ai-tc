# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Scripts Cli Commands - Rag
# =============================================================================
# Description:
#   Команды управления RAG-индексацией (rag) и Code Helper (codebase RAG).
#
# Usage Examples:
#   Python API:
#     from scripts.cli.commands.rag import register_rag_parser
#
#     res = register_rag_parser()
#
# File: rag.py
# Project: ai-windows-admin
# Package: scripts.cli.commands
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 17:15:00
# =============================================================================

from __future__ import annotations

"""Команды управления RAG-индексацией (rag) и автономным Code Helper."""

import argparse
import asyncio
from header import __root__
from logger import logger


def register_rag_parser(subparsers: argparse._SubParsersAction) -> None:
    """Регистрация аргументов команды rag."""
    rag_parser = subparsers.add_parser('rag', help='RAG index management')
    rag_subparsers = rag_parser.add_subparsers(dest='subcommand', help='Subcommands')
    rag_rebuild = rag_subparsers.add_parser('rebuild', help='Full rebuild of RAG index')
    rag_rebuild.add_argument('rest', nargs=argparse.REMAINDER, help='Rebuild options')
    rag_subparsers.add_parser('reindex', help='Reindex knowledge base')
    rag_subparsers.add_parser('validate', help='Validate knowledge base files')
    rag_subparsers.add_parser('status', help='Check RAG index status')
    rag_subparsers.add_parser('tc-status', help='Check Test Computer (TC) Q&A RAG status')
    rag_tc_export = rag_subparsers.add_parser('tc-export', help='Export TC Q&A dataset for fine-tuning')
    rag_tc_export.add_argument('rest', nargs=argparse.REMAINDER, help='Format (alpaca, sharegpt, gemini)')

    # Интеграция с автономным Code Helper (apps/code_helper)
    rag_subparsers.add_parser('code-status', help='Проверить статус базы знаний Code Helper (Hostinger)')
    rag_subparsers.add_parser('code-db-test', help='Проверить прямое подключение к MariaDB на Hostinger')
    code_bld = rag_subparsers.add_parser('code-build', help='Собрать AST-индекс кодовой базы в Hostinger MariaDB')
    code_bld.add_argument('--root', default='.', help='Корневой каталог для индексации')
    code_bld.add_argument('--name', default='codebase', help='Имя индекса')
    code_search = rag_subparsers.add_parser('code-search', help='Поиск по коду через Code Helper')
    code_search.add_argument('query', help='Поисковый запрос')
    code_search.add_argument('--name', default='codebase', help='Имя индекса')


def run_rag_command(args: argparse.Namespace) -> int:
    """Операции над векторным индексом RAG и Code Helper."""
    sub = args.subcommand
    extra = getattr(args, 'rest', [])

    if sub == 'code-status':
        try:
            from apps.code_helper.rag import CodeHelperRAG
            rag = CodeHelperRAG()
            info = rag.storage.test_connection()
            indexes = rag.storage.list_indexes()
            logger.console(f"Code Helper — активный движок: {rag.storage.active_engine}")
            logger.console(f"Hostinger MariaDB ({info.get('database')}): {info.get('status')}")
            logger.console(f"Локальный кэш SQLite: {rag.storage.sqlite_path}")
            logger.console(f"Количество индексов: {len(indexes)}")
            return 0
        except Exception as e:
            logger.console(f"Ошибка проверки статуса Code Helper: {e}")
            return 1

    if sub == 'code-db-test':
        try:
            from apps.code_helper.rag import CodeHelperRAG
            rag = CodeHelperRAG()
            res = rag.storage.test_connection()
            logger.console(f"Hostinger Status: {res.get('status')}")
            if res.get('error'):
                logger.console(f"Ошибка: {res['error']}")
            if res.get('hostinger_instruction'):
                logger.console(f"Инструкция: {res['hostinger_instruction']}")
            return 0 if res.get('status') == 'connected' else 1
        except Exception as e:
            logger.console(f"Ошибка тестирования MariaDB Hostinger: {e}")
            return 1

    if sub == 'code-build':
        try:
            from apps.code_helper.rag import CodeHelperRAG
            rag = CodeHelperRAG()
            root = getattr(args, 'root', '.')
            name = getattr(args, 'name', 'codebase')
            stats = rag.build_index(project_root=root, index_name=name)
            logger.console(
                f"Индекс '{name}' успешно собран: {stats.total_files} файлов, "
                f"{stats.total_chunks} чанков, {stats.total_symbols} символов ({stats.storage_engine})"
            )
            return 0
        except Exception as e:
            logger.console(f"Ошибка сборки индекса: {e}")
            return 1

    if sub == 'code-search':
        try:
            from apps.code_helper.rag import CodeHelperRAG
            rag = CodeHelperRAG()
            q = getattr(args, 'query', '')
            name = getattr(args, 'name', 'codebase')
            results = rag.search_code(q, index_name=name)
            logger.console(f"Найдено результатов: {len(results)}")
            for i, r in enumerate(results, 1):
                logger.console(f"[{i}] {r.get('symbol_type')} {r.get('symbol_name')} ({r.get('file_path')})")
            return 0
        except Exception as e:
            logger.console(f"Ошибка поиска: {e}")
            return 1

    if sub == 'rebuild':
        try:
            from src.rag import build_rules_index
            index_path, docs_path = build_rules_index(*extra)
            logger.console(f'RAG index rebuilt successfully: {index_path}, {docs_path}')
            return 0
        except TypeError:
            from src.rag import build_rules_index
            index_path, docs_path = build_rules_index()
            logger.console(f'RAG index rebuilt successfully: {index_path}, {docs_path}')
            return 0
        except Exception as e:
            logger.console(f'Error rebuilding RAG: {e}')
            return 1
    if sub == 'status':
        try:
            idx_file = __root__ / 'tmp' / 'rag' / 'rules.index'
            logger.console(f"Core RAG status: {('Ready' if idx_file.exists() else 'Not built')}")
            return 0
        except Exception as e:
            logger.console(f'Error checking RAG status: {e}')
            return 1
    if sub == 'tc-status':
        try:
            from src.ai.gemini.approved_responses_store import list_responses, get_store_dir
            responses = list_responses()
            store_dir = get_store_dir()
            logger.console(f'TC Approved Responses Directory: {store_dir}')
            logger.console(f'Total Approved TC Q&A items: {len(responses)}')
            return 0
        except Exception as e:
            logger.console(f'Error checking TC RAG status: {e}')
            return 1
    if sub == 'tc-export':
        try:
            from src.ai.gemini.approved_responses_store import export_tuning_dataset
            fmt = 'alpaca'
            if extra and len(extra) > 0:
                fmt = extra[0]
            out_file = __root__ / 'data' / 'tc' / 'datasets' / f'tc_qa_{fmt}.jsonl'
            count = export_tuning_dataset(out_file, fmt=fmt)
            logger.console(f'Exported {count} TC Q&A items to {out_file} (format: {fmt})')
            return 0
        except Exception as e:
            logger.console(f'Error exporting TC dataset: {e}')
            return 1
    logger.console(f'Unknown rag subcommand: {sub}')
    return 1
