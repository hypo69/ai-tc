# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Skill - GitHub Issue Tracker CLI
# =============================================================================
# Description:
#   Консольная утилита для управления задачами GitHub Issues, просмотра вех
#   и синхронизации меток репозитория AI-TC.
#
# Usage Examples:
#   py manage_issues.py list --state open
#   py manage_issues.py view 125
#   py manage_issues.py sync-labels
#
# File: manage_issues.py
# Project: ai-windows-admin
# Package: .agents.skills.github-issue-tracker.scripts
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 13:48:00
# =============================================================================

from __future__ import annotations
"""Консольная утилита управления задачами GitHub в рамках навыка github-issue-tracker."""

import argparse
import sys
from pathlib import Path

# Обеспечение доступности корневых пакетов
root_dir = Path(__file__).resolve().parents[4]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from logger import logger
from src.github.service import GitHubService
from src.github.models import IssueType, Priority, Component


def cmd_list(args: argparse.Namespace, service: GitHubService) -> None:
    """Отображение списка задач."""
    labels = [args.label] if args.label else None
    issues = service.get_issues(state=args.state, labels=labels, limit=args.limit)
    if not issues:
        logger.console(f'Задачи не найдены (state={args.state}).')
        return

    logger.console(f'\n=== Список задач GitHub ({len(issues)}) ===')
    for item in issues:
        type_str = item.issue_type.value
        prio_str = item.priority.value.replace('priority:', '')
        comp_str = item.component.value.replace('component:', '')
        logger.console(
            f'#{item.number:4d} | [{item.state.value.upper():^6}] | '
            f'[{type_str:^11}] | [{prio_str:^8}] | [{comp_str:^10}] | {item.title}'
        )


def cmd_view(args: argparse.Namespace, service: GitHubService) -> None:
    """Просмотр детальной информации по задаче."""
    issue = service.get_issue(args.number)
    if not issue:
        logger.console(f'Задача #{args.number} не найдена.')
        return

    logger.console(f'\n=== Issue #{issue.number}: {issue.title} ===')
    logger.console(f'Статус:      {issue.state.value}')
    logger.console(f'Метки:       {", ".join(issue.labels)}')
    logger.console(f'Исполнители: {", ".join(issue.assignees) or "Не назначены"}')
    logger.console(f'URL:         {issue.url}')
    logger.console('\n--- Описание ---')
    logger.console(issue.body or '(Описание отсутствует)')


def cmd_create(args: argparse.Namespace, service: GitHubService) -> None:
    """Создание новой задачи."""
    issue_type = IssueType.from_str(args.type)
    priority = Priority.from_str(args.priority)
    component = Component.from_str(args.component)

    created = service.create_issue(
        title=args.title,
        body=args.body or '',
        issue_type=issue_type,
        priority=priority,
        component=component,
        assignee=args.assignee
    )
    if created:
        logger.console(f'Успешно создан Issue: {created.url}')
    else:
        logger.console('Не удалось создать Issue.')


def cmd_sync_labels(args: argparse.Namespace, service: GitHubService) -> None:
    """Синхронизация типовых меток."""
    count = service.sync_standard_labels()
    logger.console(f'Синхронизировано меток: {count}')


def main() -> None:
    """Главная точка входа утилиты."""
    parser = argparse.ArgumentParser(description='Утилита управления задачами GitHub Issues AI-TC')
    subparsers = parser.add_subparsers(dest='command', required=True)

    # list
    p_list = subparsers.add_parser('list', help='Список задач')
    p_list.add_argument('--state', default='open', choices=['open', 'closed', 'all'], help='Состояние задач')
    p_list.add_argument('--label', help='Фильтр по метке')
    p_list.add_argument('--limit', type=int, default=30, help='Лимит выборки')

    # view
    p_view = subparsers.add_parser('view', help='Детали задачи')
    p_view.add_argument('number', type=int, help='Номер задачи')

    # create
    p_create = subparsers.add_parser('create', help='Создать задачу')
    p_create.add_argument('title', help='Заголовок задачи')
    p_create.add_argument('--body', default='', help='Тело задачи')
    p_create.add_argument('--type', default='feature', help='Тип задачи (bug/feature/enhancement/...)')
    p_create.add_argument('--priority', default='medium', help='Приоритет (critical/high/medium/low)')
    p_create.add_argument('--component', default='core', help='Компонент (telemetry/network/windows/gui/ai/mcp/core)')
    p_create.add_argument('--assignee', default='@me', help='Исполнитель')

    # sync-labels
    subparsers.add_parser('sync-labels', help='Синхронизировать типовые метки AI-TC в репозитории')

    args = parser.parse_args()
    service = GitHubService()

    handlers = {
        'list': cmd_list,
        'view': cmd_view,
        'create': cmd_create,
        'sync-labels': cmd_sync_labels,
    }

    handler = handlers.get(args.command)
    if handler:
        handler(args, service)


if __name__ == '__main__':
    main()
