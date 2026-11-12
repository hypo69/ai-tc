# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin GitHub - Data Models
# =============================================================================
# Description:
#   Типизированные модели данных, перечисления и структуры для GitHub Issues,
#   Projects, Milestones и интеграции жизненного цикла задач с AI-агентами.
#
# Usage Examples:
#   from src.github.models import Issue, IssueType, Priority, Component
#
#   issue = Issue(
#       number=125,
#       title="Исправить загрузку config.json",
#       body="Падает при отсутствии файла",
#       issue_type=IssueType.BUG,
#       priority=Priority.HIGH,
#       component=Component.CORE
#   )
#
# File: models.py
# Project: ai-windows-admin
# Package: src.github
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 13:48:00
# =============================================================================

from __future__ import annotations
"""Модели данных для GitHub Issues, меток, вех и задач AI-разработки."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class IssueState(str, Enum):
    """Основные состояния задачи GitHub."""
    OPEN = 'open'
    CLOSED = 'closed'


class IssueType(str, Enum):
    """Типы задач согласно стандарту проекта."""
    BUG = 'bug'
    FEATURE = 'feature'
    ENHANCEMENT = 'enhancement'
    DOCUMENTATION = 'documentation'
    REFACTORING = 'refactoring'
    RESEARCH = 'research'

    @classmethod
    def from_str(cls, val: str) -> IssueType:
        """Безопасное преобразование строки в тип задачи."""
        val_clean = val.lower().strip().replace('[', '').replace(']', '')
        for item in cls:
            if item.value == val_clean or item.name.lower() == val_clean:
                return item
        if 'bug' in val_clean:
            return cls.BUG
        if 'feat' in val_clean:
            return cls.FEATURE
        if 'doc' in val_clean:
            return cls.DOCUMENTATION
        return cls.ENHANCEMENT


class Priority(str, Enum):
    """Уровни приоритета задачи."""
    CRITICAL = 'priority:critical'
    HIGH = 'priority:high'
    MEDIUM = 'priority:medium'
    LOW = 'priority:low'

    @classmethod
    def from_str(cls, val: str) -> Priority:
        """Безопасное преобразование строки в приоритет."""
        v = val.lower()
        if 'crit' in v:
            return cls.CRITICAL
        if 'high' in v:
            return cls.HIGH
        if 'low' in v:
            return cls.LOW
        return cls.MEDIUM


class Component(str, Enum):
    """Компоненты кодовой базы AI-TC."""
    TELEMETRY = 'component:telemetry'
    NETWORK = 'component:network'
    WINDOWS = 'component:windows'
    GUI = 'component:gui'
    AI = 'component:ai'
    MCP = 'component:mcp'
    CORE = 'component:core'

    @classmethod
    def from_str(cls, val: str) -> Component:
        """Безопасное преобразование строки в компонент."""
        v = val.lower()
        for item in cls:
            if item.value.split(':')[-1] in v:
                return item
        return cls.CORE


class ProjectColumn(str, Enum):
    """Колонки Kanban-доски проекта."""
    BACKLOG = 'Backlog'
    TODO = 'Todo'
    IN_PROGRESS = 'In Progress'
    REVIEW = 'Review'
    TESTING = 'Testing'
    DONE = 'Done'


@dataclass
class Milestone:
    """Модель этапа релиза (Milestone)."""
    number: int
    title: str
    description: str = ''
    state: IssueState = IssueState.OPEN
    open_issues: int = 0
    closed_issues: int = 0
    url: str = ''

    @property
    def total_issues(self) -> int:
        """Общее количество задач в вехе."""
        return self.open_issues + self.closed_issues

    @property
    def progress_pct(self) -> float:
        """Процент выполнения задач этапа."""
        if self.total_issues == 0:
            return 0.0
        return round((self.closed_issues / self.total_issues) * 100.0, 1)


@dataclass
class Issue:
    """Модель GitHub Issue."""
    number: int
    title: str
    body: str = ''
    state: IssueState = IssueState.OPEN
    labels: List[str] = field(default_factory=list)
    assignees: List[str] = field(default_factory=list)
    milestone: Optional[Milestone] = None
    project_column: ProjectColumn = ProjectColumn.TODO
    url: str = ''

    @property
    def issue_type(self) -> IssueType:
        """Определение типа задачи по меткам или заголовку."""
        for label in self.labels:
            try:
                return IssueType(label.lower())
            except ValueError:
                pass
        return IssueType.from_str(self.title)

    @property
    def priority(self) -> Priority:
        """Определение приоритета задачи по меткам."""
        for label in self.labels:
            if label.startswith('priority:'):
                return Priority.from_str(label)
        return Priority.MEDIUM

    @property
    def component(self) -> Component:
        """Определение целевого компонента AI-TC по меткам."""
        for label in self.labels:
            if label.startswith('component:'):
                return Component.from_str(label)
        return Component.CORE


@dataclass
class BranchInfo:
    """Данные Git-ветки, привязанной к задаче."""
    issue_number: int
    branch_name: str
    branch_type: str
    slug: str


@dataclass
class AITaskPlan:
    """План технического задания для автономного AI-разработчика."""
    issue_number: int
    title: str
    issue_type: IssueType
    component: Component
    priority: Priority
    target_files: List[str] = field(default_factory=list)
    requirements: List[str] = field(default_factory=list)
    test_cases: List[str] = field(default_factory=list)
    suggested_branch: str = ''
    closing_keyword: str = 'Fixes'
