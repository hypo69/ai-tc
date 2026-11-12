# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - GitHub Issue Manager Unit Tests
# =============================================================================
# Description:
#   Модульные тесты для моделей данных, парсера задач, клиента и сервиса GitHub.
#
# Usage Examples:
#   pytest tests/test_github_issue_manager.py -v
#
# File: test_github_issue_manager.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 13:48:00
# =============================================================================

from __future__ import annotations
"""Модульные тесты модуля управления задачами GitHub."""

import pytest
from unittest.mock import MagicMock
from src.github.models import (
    Issue,
    IssueState,
    IssueType,
    Priority,
    Component,
    Milestone,
    ProjectColumn
)
from src.github.task_parser import TaskParser
from src.github.service import GitHubService
from src.github.client import GitHubClient


class TestGitHubModels:
    """Тестирование моделей данных и перечислений."""

    def test_issue_type_parsing(self) -> None:
        """Проверка безопасного распознавания типов задач."""
        assert IssueType.from_str('bug') == IssueType.BUG
        assert IssueType.from_str('[BUG] Ошибка') == IssueType.BUG
        assert IssueType.from_str('feature') == IssueType.FEATURE
        assert IssueType.from_str('feat') == IssueType.FEATURE
        assert IssueType.from_str('documentation') == IssueType.DOCUMENTATION
        assert IssueType.from_str('неизвестный') == IssueType.ENHANCEMENT

    def test_priority_parsing(self) -> None:
        """Проверка безопасного распознавания приоритетов."""
        assert Priority.from_str('critical') == Priority.CRITICAL
        assert Priority.from_str('priority:high') == Priority.HIGH
        assert Priority.from_str('low') == Priority.LOW
        assert Priority.from_str('normal') == Priority.MEDIUM

    def test_component_parsing(self) -> None:
        """Проверка распознавания компонентов AI-TC."""
        assert Component.from_str('telemetry') == Component.TELEMETRY
        assert Component.from_str('component:windows') == Component.WINDOWS
        assert Component.from_str('network') == Component.NETWORK
        assert Component.from_str('gui') == Component.GUI
        assert Component.from_str('unknown') == Component.CORE

    def test_milestone_progress(self) -> None:
        """Проверка расчета прогресса выполнения вехи."""
        m = Milestone(
            number=1,
            title='v0.5 — Telemetry',
            open_issues=3,
            closed_issues=4
        )
        assert m.total_issues == 7
        assert m.progress_pct == 57.1

        empty_m = Milestone(number=2, title='v0.6')
        assert empty_m.progress_pct == 0.0

    def test_issue_properties(self) -> None:
        """Проверка автоматического определения типа и приоритета из меток."""
        issue = Issue(
            number=125,
            title='Исправить загрузку config.json',
            labels=['bug', 'priority:high', 'component:core']
        )
        assert issue.issue_type == IssueType.BUG
        assert issue.priority == Priority.HIGH
        assert issue.component == Component.CORE


class TestTaskParser:
    """Тестирование парсера ТЗ и веток."""

    @pytest.fixture
    def parser(self) -> TaskParser:
        """Фикстура создания парсера."""
        return TaskParser()

    def test_slugify(self, parser: TaskParser) -> None:
        """Проверка транслитерации и генерации слага."""
        slug = parser.slugify('Исправить загрузку config.json')
        assert 'ispravit' in slug
        assert 'config' in slug

    def test_generate_branch_name_for_bug(self, parser: TaskParser) -> None:
        """Проверка имени ветки для ошибки."""
        issue = Issue(
            number=125,
            title='Fix config loading',
            labels=['bug']
        )
        branch = parser.generate_branch_name(issue)
        assert branch.startswith('fix/125-')
        assert 'config-loading' in branch

    def test_generate_branch_name_for_feature(self, parser: TaskParser) -> None:
        """Проверка имени ветки для новой функции."""
        issue = Issue(
            number=201,
            title='Network Monitor Panel',
            labels=['feature']
        )
        branch = parser.generate_branch_name(issue)
        assert branch.startswith('feat/201-')

    def test_extract_target_files(self, parser: TaskParser) -> None:
        """Проверка извлечения путей файлов из текста задачи."""
        body = """
        При падении в `src/config.py` или `apps/windows/core.py`.
        Также проверьте "settings.json".
        """
        files = parser.extract_target_files(body)
        assert 'src/config.py' in files
        assert 'apps/windows/core.py' in files
        assert 'settings.json' in files

    def test_extract_requirements(self, parser: TaskParser) -> None:
        """Проверка извлечения требований и чек-листов."""
        body = """
        ## Шаги:
        1. Открыть приложение
        2. Проверить соединение
        
        ## Чек-лист:
        - [ ] Добавить обработчик исключений
        - [x] Написать тесты
        """
        reqs = parser.extract_requirements(body)
        assert 'Открыть приложение' in reqs
        assert 'Проверить соединение' in reqs
        assert 'Добавить обработчик исключений' in reqs
        assert 'Написать тесты' in reqs

    def test_generate_pull_request_body(self, parser: TaskParser) -> None:
        """Проверка формирования описания PR со связкой Fixes #."""
        issue = Issue(
            number=125,
            title='Crash in config loader',
            labels=['bug', 'component:core']
        )
        pr_body = parser.generate_pull_request_body(
            issue=issue,
            implementation_summary='Добавлена проверка наличия файла'
        )
        assert 'Fixes #125' in pr_body
        assert '`component:core`' in pr_body
        assert 'Добавлена проверка наличия файла' in pr_body


class TestGitHubService:
    """Тестирование сервиса с мокированным клиентом."""

    def test_get_issue_mapping(self) -> None:
        """Проверка корректной сборки объекта Issue из данных клиента."""
        mock_client = MagicMock(spec=GitHubClient)
        mock_client.get_issue.return_value = {
            'number': 125,
            'title': 'Test Issue',
            'body': 'Some description with `src/app.py`',
            'state': 'OPEN',
            'labels': [{'name': 'bug'}, {'name': 'priority:critical'}],
            'assignees': [{'login': 'hypo69'}],
            'url': 'https://github.com/hypo69/AI-TC/issues/125'
        }

        service = GitHubService(client=mock_client)
        issue = service.get_issue(125)

        assert issue is not None
        assert issue.number == 125
        assert issue.title == 'Test Issue'
        assert issue.issue_type == IssueType.BUG
        assert issue.priority == Priority.CRITICAL
        assert issue.assignees == ['hypo69']

    def test_create_task_plan(self) -> None:
        """Проверка сборки плана ТЗ через сервис."""
        mock_client = MagicMock(spec=GitHubClient)
        mock_client.get_issue.return_value = {
            'number': 42,
            'title': 'New Feature',
            'body': 'Need to modify `src/ai.py`\n- [ ] Write logic',
            'state': 'OPEN',
            'labels': [{'name': 'feature'}, {'name': 'component:ai'}],
            'assignees': [],
            'url': ''
        }

        service = GitHubService(client=mock_client)
        plan = service.create_task_plan(42)

        assert plan is not None
        assert plan.issue_number == 42
        assert plan.issue_type == IssueType.FEATURE
        assert plan.component == Component.AI
        assert 'src/ai.py' in plan.target_files
        assert plan.closing_keyword == 'Closes'
