# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Scripts Cli Commands - Paperless
# =============================================================================
# Description:
#   Команды управления Paperless-ngx: запуск/остановка Docker-окружения,
#   проверка API, получение токена и синхронизация рабочей области.
#
# Usage Examples:
#   CLI:
#     py manage_tools.py paperless up [--build]
#     py manage_tools.py paperless token --username admin --password ***
#     py manage_tools.py paperless sync --workspace default
#
# File: paperless.py
# Project: ai-windows-admin
# Package: scripts.cli.commands
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 16:32:00
# =============================================================================

from __future__ import annotations
"""Команды управления Paperless-ngx (paperless)."""

import argparse
import json

from header import __root__
from logger import logger


def register_paperless_parser(subparsers: argparse._SubParsersAction) -> None:
    """Регистрирует парсер команды `paperless`."""
    parser = subparsers.add_parser('paperless', help='Paperless-ngx management')
    sub = parser.add_subparsers(dest='subcommand', help='Subcommands')
    up = sub.add_parser('up', help='Start Paperless-ngx via Docker Compose')
    up.add_argument('--build', action='store_true', help='Build image from local paperless-ngx sources')
    sub.add_parser('down', help='Stop Paperless-ngx')
    sub.add_parser('status', help='Show containers and API availability')
    token = sub.add_parser('token', help='Obtain API token')
    token.add_argument('--username', required=True)
    token.add_argument('--password', required=True)
    sync = sub.add_parser('sync', help='Index workspace documents from Paperless')
    sync.add_argument('--workspace', required=True)


def run_paperless_command(args: argparse.Namespace) -> int:
    """Обработчик команды `paperless`."""
    from apps.ai_assistant.core.paperless_bootstrap import compose
    from apps.ai_assistant.core.paperless_connector import PaperlessConnector, PaperlessError

    sub = args.subcommand
    if sub == 'up':
        return compose(['up', '-d', *(['--build'] if args.build else [])], build=args.build)
    if sub == 'down':
        return compose(['down'])
    try:
        if sub == 'status':
            compose(['ps'])
            logger.console(f"API: {'OK' if PaperlessConnector.from_config().ping() else 'недоступен'}")
            return 0
        if sub == 'token':
            cfg = json.loads((__root__ / 'config.json').read_text(encoding='utf-8'))['paperless']
            value = PaperlessConnector.obtain_token(cfg['base_url'], args.username, args.password, cfg['read_timeout_sec'])
            logger.console(f'Добавьте в .env: PAPERLESS_API_TOKEN={value}')
            return 0
        if sub == 'sync':
            from apps.ai_assistant.core.paperless_sync import sync_workspace_from_paperless
            from apps.ai_assistant.core.workspace_manager import WorkspaceManager
            report = sync_workspace_from_paperless(WorkspaceManager(), PaperlessConnector.from_config(), args.workspace)
            logger.console(json.dumps(report, ensure_ascii=False))
            return 0 if not report['failed'] else 1
    except PaperlessError as exc:
        logger.error(str(exc))
        return 1
    logger.console(f'Unknown paperless subcommand: {sub}')
    return 1
