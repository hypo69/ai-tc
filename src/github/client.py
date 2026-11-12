# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin GitHub - CLI & API Client
# =============================================================================
# Description:
#   Интерфейс для прямого выполнения операций GitHub через официальный GitHub CLI (gh)
#   с надежной изоляцией, таймаутами и структурированным JSON-парсингом.
#
# Usage Examples:
#   from src.github.client import GitHubClient
#
#   client = GitHubClient()
#   if client.is_ready():
#       issues = client.list_issues(limit=10)
#
# File: client.py
# Project: ai-windows-admin
# Package: src.github
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 13:48:00
# =============================================================================

from __future__ import annotations
"""Клиент для выполнения команд GitHub CLI (gh) и взаимодействия с репозиторием."""

import json
import shutil
import subprocess
from typing import Any, Dict, List, Optional
from logger import logger


class GitHubClient:
    """Обертка над GitHub CLI (`gh`) для автоматизации операций."""

    def __init__(self, repo: Optional[str] = None, timeout_seconds: int = 30) -> None:
        """Инициализация GitHubClient.

        Args:
            repo: Опциональное имя репозитория в формате 'owner/repo'.
            timeout_seconds: Таймаут выполнения консольных команд в секундах.
        """
        self.repo = repo
        self.timeout_seconds = timeout_seconds
        self._gh_path = shutil.which('gh')

    def is_installed(self) -> bool:
        """Проверка наличия утилиты `gh` в системе."""
        return self._gh_path is not None

    def is_authenticated(self) -> bool:
        """Проверка статуса авторизации в GitHub CLI."""
        if not self.is_installed():
            return False
        res = self._run_raw(['auth', 'status'])
        return res.get('returncode', -1) == 0

    def is_ready(self) -> bool:
        """Проверка полной готовности клиента к работе."""
        return self.is_installed() and self.is_authenticated()

    def _run_raw(self, args: List[str]) -> Dict[str, Any]:
        """Выполнение сырой команды `gh` с таймаутом.

        Args:
            args: Аргументы для вызова `gh`.

        Returns:
            Словарь с returncode, stdout, stderr.
        """
        if not self._gh_path:
            return {
                'returncode': -1,
                'stdout': '',
                'stderr': 'GitHub CLI (gh) не найден в PATH системы.'
            }

        cmd = [self._gh_path] + args
        if self.repo and '--repo' not in args:
            cmd.extend(['--repo', self.repo])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=self.timeout_seconds,
                check=False
            )
            return {
                'returncode': result.returncode,
                'stdout': result.stdout.strip(),
                'stderr': result.stderr.strip()
            }
        except subprocess.TimeoutExpired:
            logger.error(f'Таймаут выполнения команды: {" ".join(cmd)}')
            return {
                'returncode': -2,
                'stdout': '',
                'stderr': f'Command timed out after {self.timeout_seconds}s'
            }
        except Exception as e:
            logger.error(f'Ошибка запуска gh: {e}')
            return {
                'returncode': -3,
                'stdout': '',
                'stderr': str(e)
            }

    def list_issues(
        self,
        state: str = 'open',
        labels: Optional[List[str]] = None,
        limit: int = 30
    ) -> List[Dict[str, Any]]:
        """Получение списка Issues в формате JSON.

        Args:
            state: Состояние ('open', 'closed', 'all').
            labels: Список меток для фильтрации.
            limit: Максимальное количество записей.

        Returns:
            Список словарей с данными задач.
        """
        args = [
            'issue', 'list',
            '--state', state,
            '--limit', str(limit),
            '--json', 'number,title,body,state,labels,assignees,milestone,url'
        ]
        if labels:
            for lbl in labels:
                args.extend(['--label', lbl])

        res = self._run_raw(args)
        if res['returncode'] != 0:
            logger.warning(f'Не удалось получить список issues: {res["stderr"]}')
            return []

        try:
            return json.loads(res['stdout']) if res['stdout'] else []
        except json.JSONDecodeError as err:
            logger.error(f'Ошибка разбора JSON от gh issue list: {err}')
            return []

    def get_issue(self, number: int) -> Optional[Dict[str, Any]]:
        """Получение детальной информации по номеру задачи.

        Args:
            number: Номер Issue.

        Returns:
            Словарь с данными задачи или None.
        """
        args = [
            'issue', 'view', str(number),
            '--json', 'number,title,body,state,labels,assignees,milestone,url,comments'
        ]
        res = self._run_raw(args)
        if res['returncode'] != 0:
            logger.warning(f'Issue #{number} не найден: {res["stderr"]}')
            return None

        try:
            return json.loads(res['stdout'])
        except json.JSONDecodeError as err:
            logger.error(f'Ошибка разбора JSON для issue #{number}: {err}')
            return None

    def create_issue(
        self,
        title: str,
        body: str,
        labels: Optional[List[str]] = None,
        assignee: Optional[str] = None,
        milestone: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Создание новой задачи в репозитории.

        Args:
            title: Заголовок задачи.
            body: Подробное описание.
            labels: Список меток.
            assignee: Исполнитель (например, '@me').
            milestone: Название этапа/вехи.

        Returns:
            Словарь с url созданной задачи или None.
        """
        args = ['issue', 'create', '--title', title, '--body', body]
        if labels:
            for lbl in labels:
                args.extend(['--label', lbl])
        if assignee:
            args.extend(['--assignee', assignee])
        if milestone:
            args.extend(['--milestone', milestone])

        res = self._run_raw(args)
        if res['returncode'] != 0:
            logger.error(f'Ошибка создания Issue: {res["stderr"]}')
            return None

        url = res['stdout'].splitlines()[-1] if res['stdout'] else ''
        return {'url': url, 'raw': res['stdout']}

    def edit_issue(
        self,
        number: int,
        title: Optional[str] = None,
        body: Optional[str] = None,
        add_labels: Optional[List[str]] = None,
        remove_labels: Optional[List[str]] = None,
        add_assignee: Optional[str] = None
    ) -> bool:
        """Редактирование атрибутов задачи.

        Args:
            number: Номер Issue.
            title: Новый заголовок (если требуется изменить).
            body: Новое тело (если требуется изменить).
            add_labels: Список добавляемых меток.
            remove_labels: Список удаляемых меток.
            add_assignee: Добавляемый исполнитель.

        Returns:
            True при успешном изменении.
        """
        args = ['issue', 'edit', str(number)]
        if title:
            args.extend(['--title', title])
        if body:
            args.extend(['--body', body])
        if add_labels:
            for lbl in add_labels:
                args.extend(['--add-label', lbl])
        if remove_labels:
            for lbl in remove_labels:
                args.extend(['--remove-label', lbl])
        if add_assignee:
            args.extend(['--add-assignee', add_assignee])

        res = self._run_raw(args)
        return res['returncode'] == 0

    def close_issue(self, number: int, reason: str = 'completed', comment: Optional[str] = None) -> bool:
        """Закрытие Issue.

        Args:
            number: Номер Issue.
            reason: Причина закрытия ('completed' или 'not planned').
            comment: Итоговый комментарий при закрытии.

        Returns:
            True при успешном закрытии.
        """
        args = ['issue', 'close', str(number), '--reason', reason]
        if comment:
            args.extend(['--comment', comment])
        res = self._run_raw(args)
        return res['returncode'] == 0

    def reopen_issue(self, number: int, comment: Optional[str] = None) -> bool:
        """Повторное открытие Issue.

        Args:
            number: Номер задачи.
            comment: Комментарий при повторном открытии.

        Returns:
            True при успешном открытии.
        """
        args = ['issue', 'reopen', str(number)]
        if comment:
            args.extend(['--comment', comment])
        res = self._run_raw(args)
        return res['returncode'] == 0

    def add_comment(self, number: int, comment: str) -> bool:
        """Добавление комментария в Issue.

        Args:
            number: Номер задачи.
            comment: Текст комментария.

        Returns:
            True при успехе.
        """
        args = ['issue', 'comment', str(number), '--body', comment]
        res = self._run_raw(args)
        return res['returncode'] == 0

    def create_pull_request(
        self,
        title: str,
        body: str,
        head_branch: Optional[str] = None,
        base_branch: str = 'main'
    ) -> Optional[Dict[str, Any]]:
        """Создание Pull Request.

        Args:
            title: Заголовок PR.
            body: Описание PR (содержит Fixes #...).
            head_branch: Имя ветки с изменениями.
            base_branch: Целевая ветка (обычно 'main' или 'master').

        Returns:
            Словарь с URL созданного PR или None.
        """
        args = ['pr', 'create', '--title', title, '--body', body, '--base', base_branch]
        if head_branch:
            args.extend(['--head', head_branch])

        res = self._run_raw(args)
        if res['returncode'] != 0:
            logger.error(f'Ошибка создания PR: {res["stderr"]}')
            return None

        url = res['stdout'].splitlines()[-1] if res['stdout'] else ''
        return {'url': url, 'raw': res['stdout']}
