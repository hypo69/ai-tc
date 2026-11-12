# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - GitHub Issue Agent Unit Tests
# =============================================================================
# Description:
#   Модульные тесты для автономного агента разработки GitHubIssueAgent.
#
# Usage Examples:
#   pytest tests/test_github_issue_agent.py -v
#
# File: test_github_issue_agent.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 13:48:00
# =============================================================================

from __future__ import annotations
"""Тестирование автономного агента разработки GitHubIssueAgent."""

import pytest
from unittest.mock import MagicMock, patch
from src.github.models import Issue, IssueType, Priority, Component
from src.github.service import GitHubService
from src.github.task_parser import TaskParser
from src.ai.agents.github_issue_agent import GitHubIssueAgent


class TestGitHubIssueAgent:
    """Тестирование рабочего цикла агента."""

    @pytest.fixture
    def mock_service(self) -> MagicMock:
        """Фикстура мока сервиса GitHub."""
        service = MagicMock(spec=GitHubService)
        service.parser = TaskParser()
        sample_issue = Issue(
            number=125,
            title='Fix config parser crash',
            body='App crashes in `src/config.py`.\n- [ ] Fix json handling',
            labels=['bug', 'priority:high', 'component:core'],
            url='https://github.com/hypo69/AI-TC/issues/125'
        )
        service.get_issue.return_value = sample_issue
        service.checkout_branch_for_issue.return_value = 'fix/125-fix-config-parser-crash'
        return service

    def test_prepare_task(self, mock_service: MagicMock) -> None:
        """Проверка формирования ТЗ агентом."""
        # Реальный сервис для построения плана
        real_service = GitHubService(client=MagicMock())
        real_service.get_issue = mock_service.get_issue

        agent = GitHubIssueAgent(service=real_service)
        plan = agent.prepare_task(125)

        assert plan is not None
        assert plan.issue_number == 125
        assert plan.issue_type == IssueType.BUG
        assert plan.component == Component.CORE
        assert plan.priority == Priority.HIGH
        assert 'src/config.py' in plan.target_files

    def test_setup_workspace_branch(self, mock_service: MagicMock) -> None:
        """Проверка создания ветки под задачу."""
        agent = GitHubIssueAgent(service=mock_service)
        branch = agent.setup_workspace_branch(125)

        assert branch == 'fix/125-fix-config-parser-crash'
        mock_service.checkout_branch_for_issue.assert_called_once()

    def test_compose_pull_request_content(self, mock_service: MagicMock) -> None:
        """Проверка формирования содержимого Pull Request."""
        agent = GitHubIssueAgent(service=mock_service)
        content = agent.compose_pull_request_content(
            issue_number=125,
            implementation_summary='Добавлен безопасный парсер JSON'
        )

        assert content is not None
        assert 'fix: #125 Fix config parser crash' in content['title']
        assert 'Fixes #125' in content['body']
        assert 'Добавлен безопасный парсер JSON' in content['body']

    @patch('subprocess.run')
    def test_run_tests(self, mock_subproc: MagicMock, mock_service: MagicMock) -> None:
        """Проверка выполнения TDD тестов агентом."""
        mock_subproc.return_value = MagicMock(returncode=0, stdout='1 passed', stderr='')
        agent = GitHubIssueAgent(service=mock_service)
        res = agent.run_tests('tests/test_dummy.py')

        assert res['success'] is True
        assert res['returncode'] == 0
