# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin AI - GitHub Issue & Task Agent Module
# =============================================================================
# Description:
#   Автономный агент для выполнения задач по техническим заданиям GitHub Issues.
#   Реализует полный цикл: анализ ТЗ, подготовка Git-ветки, генерация плана TDD,
#   верификация тестами и подготовка Pull Request с автоматическим закрытием Issue.
#
# Usage Examples:
#   from src.ai.agents.github_issue_agent import GitHubIssueAgent
#
#   agent = GitHubIssueAgent()
#   task_plan = agent.prepare_task(issue_number=125)
#   branch = agent.setup_workspace_branch(issue_number=125)
#
# File: github_issue_agent.py
# Project: ai-windows-admin
# Package: src.ai.agents
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 13:48:00
# =============================================================================

from __future__ import annotations
"""Автономный агент разработки на основе GitHub Issues и Task API."""

import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
from logger import logger
from src.github.models import Issue, IssueType, AITaskPlan, Component
from src.github.service import GitHubService


class GitHubIssueAgent:
    """Агент сквозной реализации задач по ТЗ из GitHub Issues."""

    def __init__(self, service: Optional[GitHubService] = None, ai_model: Any = None) -> None:
        """Инициализация агента.

        Args:
            service: Сервис управления GitHub (по умолчанию создается новый).
            ai_model: Опциональный инстанс AI-модели для генерации кода.
        """
        self.service = service or GitHubService()
        self.ai_model = ai_model

    def fetch_task(self, issue_number: int) -> Optional[Issue]:
        """Получение задачи из репозитория.

        Args:
            issue_number: Номер GitHub Issue.

        Returns:
            Объект задачи Issue или None.
        """
        issue = self.service.get_issue(issue_number)
        if not issue:
            logger.error(f'Задача #{issue_number} не найдена в GitHub.')
            return None
        return issue

    def prepare_task(self, issue_number: int) -> Optional[AITaskPlan]:
        """Преобразование Issue в формализованное ТЗ для AI-разработчика.

        Args:
            issue_number: Номер GitHub Issue.

        Returns:
            AITaskPlan с требованиями, файлами и тестовыми сценариями.
        """
        plan = self.service.create_task_plan(issue_number)
        if not plan:
            logger.error(f'Не удалось сформировать план задачи для #{issue_number}')
            return None

        logger.info(
            f'Сформировано ТЗ для #{issue_number}: '
            f'Тип={plan.issue_type.value}, Компонент={plan.component.value}, Ветка={plan.suggested_branch}'
        )
        return plan

    def setup_workspace_branch(self, issue_number: int) -> Optional[str]:
        """Создание и переключение на изолированную Git-ветку под задачу.

        Args:
            issue_number: Номер задачи.

        Returns:
            Имя созданной ветки или None.
        """
        issue = self.fetch_task(issue_number)
        if not issue:
            return None

        branch_name = self.service.checkout_branch_for_issue(issue)
        logger.info(f'Рабочее пространство переключено на ветку {branch_name}')
        return branch_name

    def run_tests(self, test_path: str = 'tests/') -> Dict[str, Any]:
        """Запуск проверочных тестов (TDD валидация).

        Args:
            test_path: Путь к директории или конкретному файлу тестов.

        Returns:
            Словарь с результатом выполнения тестов.
        """
        logger.info(f'Запуск тестов: pytest {test_path}')
        try:
            cmd = ['pytest', test_path, '-q', '--no-header']
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
            passed = res.returncode == 0
            return {
                'success': passed,
                'returncode': res.returncode,
                'stdout': res.stdout.strip(),
                'stderr': res.stderr.strip()
            }
        except Exception as e:
            logger.error(f'Ошибка запуска тестов: {e}')
            return {
                'success': False,
                'returncode': -1,
                'stdout': '',
                'stderr': str(e)
            }

    def compose_pull_request_content(
        self,
        issue_number: int,
        implementation_summary: str,
        test_results: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, str]]:
        """Генерация заголовка и тела Pull Request со ссылкой на Issue.

        Args:
            issue_number: Номер исходной задачи.
            implementation_summary: Текстовое описание изменений.
            test_results: Результаты прогона тестов.

        Returns:
            Словарь с 'title' и 'body' для PR или None.
        """
        issue = self.fetch_task(issue_number)
        if not issue:
            return None

        test_msg = 'Все модульные тесты успешно пройдены.'
        if test_results and not test_results.get('success', False):
            test_msg = f'Внимание: обнаружены ошибки в тестах:\n```\n{test_results.get("stderr")}\n```'

        body = self.service.parser.generate_pull_request_body(
            issue=issue,
            implementation_summary=implementation_summary,
            test_summary=test_msg
        )

        title_prefix = 'fix' if issue.issue_type == IssueType.BUG else 'feat'
        pr_title = f'{title_prefix}: #{issue.number} {issue.title}'

        return {
            'title': pr_title,
            'body': body
        }

    def submit_pull_request(
        self,
        issue_number: int,
        implementation_summary: str,
        test_results: Optional[Dict[str, Any]] = None,
        base_branch: str = 'main'
    ) -> Optional[str]:
        """Создание Pull Request в GitHub через CLI.

        Args:
            issue_number: Номер задачи.
            implementation_summary: Описание изменений.
            test_results: Результаты тестов.
            base_branch: Целевая ветка.

        Returns:
            URL созданного PR или None.
        """
        content = self.compose_pull_request_content(issue_number, implementation_summary, test_results)
        if not content:
            return None

        result = self.service.client.create_pull_request(
            title=content['title'],
            body=content['body'],
            base_branch=base_branch
        )

        if result and result.get('url'):
            pr_url = result['url']
            logger.info(f'Создан Pull Request: {pr_url}')
            # Добавление комментария в Issue со ссылкой на PR
            self.service.client.add_comment(
                issue_number,
                f'🤖 AI-разработчик завершил реализацию задачи. Создан Pull Request: {pr_url}'
            )
            return pr_url
        return None
