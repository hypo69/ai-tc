# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin GitHub - Core Service & Issue Manager
# =============================================================================
# Description:
#   Централизованный сервис управления GitHub Issues, Milestones, Projects,
#   метками задач и жизненным циклом разработки в рамках AI-TC.
#
# Usage Examples:
#   from src.github.service import GitHubService
#
#   service = GitHubService()
#   issues = service.get_issues(state='open')
#   for issue in issues:
#       print(issue.number, issue.title)
#
# File: service.py
# Project: ai-windows-admin
# Package: src.github
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 13:48:00
# =============================================================================

from __future__ import annotations
"""Центральный сервис управления жизненным циклом задач GitHub в проекте."""

import subprocess
from typing import Any, Dict, List, Optional
from logger import logger
from src.github.client import GitHubClient
from src.github.models import (
    Issue,
    IssueState,
    IssueType,
    Priority,
    Component,
    Milestone,
    ProjectColumn,
    AITaskPlan
)
from src.github.task_parser import TaskParser


class GitHubService:
    """Сервис управления GitHub задачами, проектами и Git-интеграцией."""

    # Реестр стандартных меток AI-TC с описанием и цветом
    STANDARD_LABELS: Dict[str, Dict[str, str]] = {
        # Типы задач
        'bug': {'color': 'd73a4a', 'description': 'Ошибка или дефект программы'},
        'feature': {'color': 'a2eeef', 'description': 'Новая функциональность'},
        'enhancement': {'color': 'a2eeef', 'description': 'Улучшение существующего компонента'},
        'documentation': {'color': '0075ca', 'description': 'Документация и руководства'},
        'refactoring': {'color': 'cfd3d7', 'description': 'Рефакторинг и оптимизация без изменения API'},
        'research': {'color': 'd4c5f9', 'description': 'Исследования, архитектура и бенчмаркинг'},
        # Приоритеты
        'priority:critical': {'color': 'b60205', 'description': 'Критический приоритет - немедленное исправление'},
        'priority:high': {'color': 'd93f0b', 'description': 'Высокий приоритет'},
        'priority:medium': {'color': 'fbca04', 'description': 'Средний приоритет'},
        'priority:low': {'color': '0e8a16', 'description': 'Низкий приоритет'},
        # Компоненты AI-TC
        'component:telemetry': {'color': '1d76db', 'description': 'Сбор метрик, датчики и системные процессы'},
        'component:network': {'color': '5319e7', 'description': 'Сетевые адаптеры, порты, соединения и анализ трафика'},
        'component:windows': {'color': '0052cc', 'description': 'Windows API, службы, хранилища и оборудование'},
        'component:gui': {'color': 'bfdadc', 'description': 'Пользовательский интерфейс WebGUI и TUI'},
        'component:ai': {'color': 'c5def5', 'description': 'Интеграция с LLM, ReAct агенты и RAG'},
        'component:mcp': {'color': 'bfd4f2', 'description': 'MCP-серверы и интеграционные протоколы'},
        'component:core': {'color': '555555', 'description': 'Ядро приложения, конфигурация и общие утилиты'}
    }

    def __init__(self, client: Optional[GitHubClient] = None, parser: Optional[TaskParser] = None) -> None:
        """Инициализация сервиса.

        Args:
            client: Экземпляр GitHubClient (по умолчанию создается стандартный).
            parser: Экземпляр TaskParser.
        """
        self.client = client or GitHubClient()
        self.parser = parser or TaskParser()

    def _dict_to_issue(self, raw: Dict[str, Any]) -> Issue:
        """Преобразование сырого словаря GitHub CLI в объект Issue.

        Args:
            raw: Словарь с полями из JSON вывода `gh`.

        Returns:
            Экземпляр Issue.
        """
        labels_raw = raw.get('labels', [])
        labels_list: List[str] = []
        for item in labels_raw:
            if isinstance(item, dict):
                labels_list.append(item.get('name', ''))
            elif isinstance(item, str):
                labels_list.append(item)

        assignees_raw = raw.get('assignees', [])
        assignees_list: List[str] = []
        for item in assignees_raw:
            if isinstance(item, dict):
                assignees_list.append(item.get('login', ''))
            elif isinstance(item, str):
                assignees_list.append(item)

        state_str = raw.get('state', 'OPEN').lower()
        state = IssueState.CLOSED if state_str == 'closed' else IssueState.OPEN

        milestone_data = raw.get('milestone')
        milestone = None
        if milestone_data and isinstance(milestone_data, dict):
            milestone = Milestone(
                number=milestone_data.get('number', 0),
                title=milestone_data.get('title', ''),
                description=milestone_data.get('description', '') or '',
                state=IssueState.OPEN if milestone_data.get('state', '').lower() != 'closed' else IssueState.CLOSED
            )

        return Issue(
            number=raw.get('number', 0),
            title=raw.get('title', ''),
            body=raw.get('body', '') or '',
            state=state,
            labels=labels_list,
            assignees=assignees_list,
            milestone=milestone,
            url=raw.get('url', '')
        )

    def get_issues(
        self,
        state: str = 'open',
        labels: Optional[List[str]] = None,
        limit: int = 50
    ) -> List[Issue]:
        """Получение списка задач с фильтрацией.

        Args:
            state: Состояние ('open', 'closed', 'all').
            labels: Список меток для фильтрации.
            limit: Максимальное количество задач.

        Returns:
            Список типизированных объектов Issue.
        """
        raw_list = self.client.list_issues(state=state, labels=labels, limit=limit)
        return [self._dict_to_issue(item) for item in raw_list]

    def get_issue(self, number: int) -> Optional[Issue]:
        """Получение задачи по ее номеру.

        Args:
            number: Номер Issue.

        Returns:
            Объект Issue или None.
        """
        raw = self.client.get_issue(number)
        if not raw:
            return None
        return self._dict_to_issue(raw)

    def create_issue(
        self,
        title: str,
        body: str,
        issue_type: IssueType = IssueType.FEATURE,
        priority: Priority = Priority.MEDIUM,
        component: Component = Component.CORE,
        extra_labels: Optional[List[str]] = None,
        assignee: Optional[str] = '@me',
        milestone: Optional[str] = None
    ) -> Optional[Issue]:
        """Создание новой задачи с типовыми метками.

        Args:
            title: Заголовок задачи.
            body: Описание задачи.
            issue_type: Тип (bug, feature, enhancement...).
            priority: Приоритет.
            component: Компонент системы.
            extra_labels: Дополнительные метки.
            assignee: Исполнитель.
            milestone: Название вехи.

        Returns:
            Объект созданной задачи или None.
        """
        labels = [issue_type.value, priority.value, component.value]
        if extra_labels:
            labels.extend(extra_labels)

        result = self.client.create_issue(
            title=title,
            body=body,
            labels=labels,
            assignee=assignee,
            milestone=milestone
        )
        if not result:
            return None

        logger.info(f'Создан GitHub Issue: {result.get("url")}')
        return Issue(
            number=0,
            title=title,
            body=body,
            labels=labels,
            url=result.get('url', '')
        )

    def close_issue(self, number: int, comment: Optional[str] = None) -> bool:
        """Закрытие задачи с фиксацией результата.

        Args:
            number: Номер задачи.
            comment: Итоговый комментарий.

        Returns:
            True при успешном закрытии.
        """
        success = self.client.close_issue(number, comment=comment)
        if success:
            logger.info(f'Issue #{number} успешно закрыт.')
        return success

    def create_task_plan(self, issue_number: int) -> Optional[AITaskPlan]:
        """Формирование ТЗ для AI-разработчика по номеру задачи.

        Args:
            issue_number: Номер задачи.

        Returns:
            AITaskPlan или None.
        """
        issue = self.get_issue(issue_number)
        if not issue:
            logger.error(f'Задача #{issue_number} не найдена для построения ТЗ.')
            return None
        return self.parser.build_task_plan(issue)

    def checkout_branch_for_issue(self, issue: Issue) -> str:
        """Создание и переключение на Git-ветку под задачу.

        Args:
            issue: Объект задачи.

        Returns:
            Имя созданной ветки.
        """
        branch_name = self.parser.generate_branch_name(issue)
        try:
            cmd = ['git', 'checkout', '-B', branch_name]
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if res.returncode == 0:
                logger.info(f'Переключено на ветку: {branch_name}')
            else:
                logger.warning(f'Предупреждение при переключении ветки: {res.stderr.strip()}')
        except Exception as e:
            logger.error(f'Ошибка создания Git-ветки {branch_name}: {e}')

        return branch_name

    def sync_standard_labels(self) -> int:
        """Синхронизация стандартных меток AI-TC в репозитории GitHub.

        Returns:
            Количество синхронизированных меток.
        """
        if not self.client.is_ready():
            logger.warning('GitHub CLI не готов к синхронизации меток.')
            return 0

        synced_count = 0
        for name, meta in self.STANDARD_LABELS.items():
            args = [
                'label', 'create', name,
                '--color', meta['color'],
                '--description', meta['description'],
                '--force'
            ]
            res = self.client._run_raw(args)
            if res['returncode'] == 0:
                synced_count += 1
            else:
                logger.debug(f'Метка {name} уже существует или обновлена.')

        logger.info(f'Синхронизировано стандартных меток: {synced_count}')
        return synced_count
