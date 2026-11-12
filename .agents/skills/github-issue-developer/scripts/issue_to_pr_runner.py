# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Skill - Issue to PR Automation Runner
# =============================================================================
# Description:
#   Консольный оркестратор для сквозного выполнения задач по GitHub Issue:
#   разбор ТЗ, создание ветки Git, верификация через pytest и генерация Pull Request.
#
# Usage Examples:
#   py issue_to_pr_runner.py plan 125
#   py issue_to_pr_runner.py start-branch 125
#   py issue_to_pr_runner.py verify-and-pr 125 --summary "Исправлена ошибка загрузки"
#
# File: issue_to_pr_runner.py
# Project: ai-windows-admin
# Package: .agents.skills.github-issue-developer.scripts
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 13:48:00
# =============================================================================

from __future__ import annotations
"""Оркестратор автоматизированной разработки по техническим заданиям GitHub Issues."""

import argparse
import sys
from pathlib import Path

# Обеспечение доступности корневых пакетов
root_dir = Path(__file__).resolve().parents[4]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from logger import logger
from src.ai.agents.github_issue_agent import GitHubIssueAgent


def cmd_plan(args: argparse.Namespace, agent: GitHubIssueAgent) -> None:
    """Генерация и отображение структурированного плана реализации задачи."""
    plan = agent.prepare_task(args.issue_number)
    if not plan:
        logger.console(f'Не удалось получить задачу #{args.issue_number}')
        return

    logger.console(f'\n=== План реализации задачи #{plan.issue_number} ===')
    logger.console(f'Заголовок:         {plan.title}')
    logger.console(f'Тип задачи:        {plan.issue_type.value}')
    logger.console(f'Компонент:         {plan.component.value}')
    logger.console(f'Приоритет:         {plan.priority.value}')
    logger.console(f'Целевая ветка:     {plan.suggested_branch}')
    logger.console(f'Ключевое слово PR: {plan.closing_keyword}')

    if plan.target_files:
        logger.console('\nЗатронутые файлы:')
        for f in plan.target_files:
            logger.console(f'  - {f}')

    if plan.requirements:
        logger.console('\nТребования из ТЗ:')
        for r in plan.requirements:
            logger.console(f'  [ ] {r}')

    if plan.test_cases:
        logger.console('\nСценарии проверки (TDD):')
        for t in plan.test_cases:
            logger.console(f'  * {t}')


def cmd_start_branch(args: argparse.Namespace, agent: GitHubIssueAgent) -> None:
    """Создание рабочей ветки Git под задачу."""
    branch = agent.setup_workspace_branch(args.issue_number)
    if branch:
        logger.console(f'Успешно подготовлена ветка: {branch}')
    else:
        logger.console('Ошибка создания ветки.')


def cmd_verify_and_pr(args: argparse.Namespace, agent: GitHubIssueAgent) -> None:
    """Проверка тестов и формирование Pull Request."""
    logger.console('Запуск валидационных тестов...')
    test_results = agent.run_tests(args.tests)

    if not test_results['success']:
        logger.console('ВНИМАНИЕ: Тесты завершились с ошибкой!')
        logger.console(test_results['stderr'] or test_results['stdout'])
        if not args.force:
            logger.console('Создание PR прервано. Используйте --force для принудительного создания.')
            return

    logger.console('Формирование Pull Request...')
    pr_url = agent.submit_pull_request(
        issue_number=args.issue_number,
        implementation_summary=args.summary,
        test_results=test_results,
        base_branch=args.base
    )

    if pr_url:
        logger.console(f'Pull Request успешно создан: {pr_url}')
    else:
        logger.console('Ошибка при создании Pull Request через gh CLI.')


def main() -> None:
    """Главная точка входа утилиты."""
    parser = argparse.ArgumentParser(description='Оркестратор разработки по GitHub Issues для AI-разработчиков')
    subparsers = parser.add_subparsers(dest='command', required=True)

    # plan
    p_plan = subparsers.add_parser('plan', help='Построить ТЗ и план задачи')
    p_plan.add_argument('issue_number', type=int, help='Номер задачи')

    # start-branch
    p_branch = subparsers.add_parser('start-branch', help='Создать и переключиться на ветку задачи')
    p_branch.add_argument('issue_number', type=int, help='Номер задачи')

    # verify-and-pr
    p_pr = subparsers.add_parser('verify-and-pr', help='Проверить тесты и создать Pull Request')
    p_pr.add_argument('issue_number', type=int, help='Номер задачи')
    p_pr.add_argument('--summary', required=True, help='Краткое описание выполненных изменений')
    p_pr.add_argument('--tests', default='tests/', help='Путь к тестам (по умолчанию tests/)')
    p_pr.add_argument('--base', default='main', help='Целевая ветка')
    p_pr.add_argument('--force', action='store_true', help='Игнорировать сбои тестов')

    args = parser.parse_args()
    agent = GitHubIssueAgent()

    handlers = {
        'plan': cmd_plan,
        'start-branch': cmd_start_branch,
        'verify-and-pr': cmd_verify_and_pr,
    }

    handler = handlers.get(args.command)
    if handler:
        handler(args, agent)


if __name__ == '__main__':
    main()
