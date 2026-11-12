# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin GitHub - Task Parser & Specification Builder
# =============================================================================
# Description:
#   Преобразование GitHub Issues в структурированные технические задания (ТЗ)
#   для автономных AI-разработчиков, генерация веток Git и формирование PR.
#
# Usage Examples:
#   from src.github.task_parser import TaskParser
#   from src.github.models import Issue
#
#   parser = TaskParser()
#   plan = parser.build_task_plan(issue)
#   branch_name = parser.generate_branch_name(issue)
#
# File: task_parser.py
# Project: ai-windows-admin
# Package: src.github
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 13:48:00
# =============================================================================

from __future__ import annotations
"""Парсер задач GitHub Issue в структурированные ТЗ для AI-агентов."""

import re
from typing import List, Dict, Any, Optional
from src.github.models import (
    Issue,
    IssueType,
    Priority,
    Component,
    AITaskPlan,
    BranchInfo
)


class TaskParser:
    """Инструмент синтаксического анализа и декомпозиции задач GitHub."""

    # Регулярные выражения для поиска упоминаний файлов проекта
    _FILE_PATTERN = re.compile(r'[`"]([a-zA-Z0-9_\-\./\\]+\.[a-zA-Z0-9_]+)[`"]')

    @staticmethod
    def slugify(text: str, max_length: int = 40) -> str:
        """Генерация безопасного URL/Git-слага из произвольного текста.

        Args:
            text: Исходный заголовок или строка.
            max_length: Максимальная длина слага.

        Returns:
            Нормализованная строка без спецсимволов.
        """
        # Замена кириллицы на транслит или удаление лишних знаков
        cyr_map = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
            'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
            'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
            'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
            'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
        }
        res = []
        for ch in text.lower():
            if ch in cyr_map:
                res.append(cyr_map[ch])
            elif ch.isalnum() or ch in ('-', '_'):
                res.append(ch)
            elif ch.isspace():
                res.append('-')

        slug = re.sub(r'[\-_]+', '-', ''.join(res)).strip('-')
        return slug[:max_length] if slug else 'task'

    def generate_branch_name(self, issue: Issue) -> str:
        """Формирование имени Git-ветки в соответствии со стандартами разработки.

        Формат:
          - Ошибки: fix/<issue_number>-<slug>
          - Новые функции: feat/<issue_number>-<slug>
          - Улучшения: enhance/<issue_number>-<slug>
          - Документация: docs/<issue_number>-<slug>
          - Рефакторинг: refactor/<issue_number>-<slug>

        Args:
            issue: Объект задачи.

        Returns:
            Строка имени ветки.
        """
        prefix_map = {
            IssueType.BUG: 'fix',
            IssueType.FEATURE: 'feat',
            IssueType.ENHANCEMENT: 'enhance',
            IssueType.DOCUMENTATION: 'docs',
            IssueType.REFACTORING: 'refactor',
            IssueType.RESEARCH: 'research'
        }
        prefix = prefix_map.get(issue.issue_type, 'task')
        slug = self.slugify(issue.title)
        return f'{prefix}/{issue.number}-{slug}'

    def extract_target_files(self, body: str) -> List[str]:
        """Извлечение путей к файлам, упомянутым в тексте Issue.

        Args:
            body: Текст описания Issue.

        Returns:
            Список найденных путей к файлам.
        """
        if not body:
            return []
        matches = self._FILE_PATTERN.findall(body)
        valid_extensions = ('.py', '.json', '.md', '.html', '.js', '.css', '.ps1', '.yml', '.yaml')
        files = [
            f.replace('\\', '/') for f in matches
            if any(f.lower().endswith(ext) for ext in valid_extensions)
        ]
        return list(dict.fromkeys(files))

    def extract_requirements(self, body: str) -> List[str]:
        """Извлечение требований и шагов из Markdown-структуры задачи.

        Args:
            body: Текст описания.

        Returns:
            Список пунктов требований.
        """
        if not body:
            return []
        reqs = []
        for line in body.splitlines():
            line_str = line.strip()
            # Поиск списков задач `- [ ] ...`, маркированных списков `* ` или `1. `
            if line_str.startswith(('- [ ]', '- [x]', '* ', '- ')):
                cleaned = re.sub(r'^(\-\s*\[[ xX]\]|\*|\-)\s*', '', line_str).strip()
                if cleaned and not cleaned.startswith('#'):
                    reqs.append(cleaned)
            elif re.match(r'^\d+\.\s+', line_str):
                cleaned = re.sub(r'^\d+\.\s+', '', line_str).strip()
                if cleaned:
                    reqs.append(cleaned)
        return reqs

    def build_task_plan(self, issue: Issue) -> AITaskPlan:
        """Построение формализованного плана ТЗ для AI-агента.

        Args:
            issue: Исходная задача GitHub.

        Returns:
            Структурированный план AITaskPlan.
        """
        files = self.extract_target_files(issue.body)
        requirements = self.extract_requirements(issue.body)
        branch = self.generate_branch_name(issue)

        # Выбор ключевого слова автоматического закрытия
        closing_keyword = 'Fixes' if issue.issue_type == IssueType.BUG else 'Closes'

        # Формирование базовых проверочных сценариев
        test_cases = [
            f'Проверка корректности работы для компонента {issue.component.value}',
            'Отсутствие регрессий в существующих модульных тестах (pytest)',
            'Валидация типов и стандартов кодирования проекта'
        ]

        return AITaskPlan(
            issue_number=issue.number,
            title=issue.title,
            issue_type=issue.issue_type,
            component=issue.component,
            priority=issue.priority,
            target_files=files,
            requirements=requirements,
            test_cases=test_cases,
            suggested_branch=branch,
            closing_keyword=closing_keyword
        )

    def generate_pull_request_body(
        self,
        issue: Issue,
        implementation_summary: str,
        test_summary: str = 'Все модульные тесты успешно пройдены.'
    ) -> str:
        """Формирование стандартного текста описания Pull Request со связью к Issue.

        Args:
            issue: Связанная задача.
            implementation_summary: Описание выполненных изменений.
            test_summary: Отчет о результатах тестирования.

        Returns:
            Markdown текст для Pull Request.
        """
        keyword = 'Fixes' if issue.issue_type == IssueType.BUG else 'Closes'
        return f"""## Связанная задача
{keyword} #{issue.number}

## Описание изменений
{implementation_summary}

## Компонент
- `{issue.component.value}`

## Результаты тестирования
{test_summary}

## Чек-лист проверки
- [x] Код соответствует стандарту PEP 8 и архитектуре проекта
- [x] Все комментарии и docstrings на русском языке
- [x] Добавлены необходимые тесты
"""
