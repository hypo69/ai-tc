# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin UTILS - Scheduler Module
# =============================================================================
# Description:
#   Асинхронный фоновый планировщик периодических задач (RAG, проверка почты).
#
# Usage Examples:
#   Python API:
#     from src.utils.scheduler import BackgroundScheduler
#
#     service = BackgroundScheduler()
#     service.load_from_config()
#
# File: scheduler.py
# Project: ai-windows-admin
# Package: src.utils
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 14:38:00
# =============================================================================

from __future__ import annotations

"""Асинхронный фоновый планировщик периодических задач."""

import asyncio
from datetime import datetime, timezone
import sys
from typing import Any, Dict, List, Optional

from header import __root__
from logger import logger

try:
    from src.user_manager import user_manager
except ImportError:
    user_manager = None

try:
    from src.rag.user_workspace_rag import user_workspace_rag_manager
except ImportError:
    user_workspace_rag_manager = None

_MAX_UNREAD_CACHE = 50


class BackgroundScheduler:
    """Асинхронный планировщик фоновых периодических задач."""

    def __init__(self) -> None:
        """Инициализирует фоновый планировщик."""
        self._running: bool = False
        self._tasks: List[asyncio.Task] = []
        self.enabled: bool = True
        self.rag_enabled: bool = True
        self._rag_interval_seconds: float = 24 * 3600.0
        self.email_enabled: bool = True
        self._email_interval_seconds: float = 5 * 60.0
        self._last_rag_run: Optional[datetime] = None
        self._last_email_run: Optional[datetime] = None
        self._latest_unread_emails: List[Dict[str, Any]] = []
        self.load_from_config()

    def load_from_config(self) -> None:
        """Перезагружает параметры планировщика из глобальной конфигурации."""
        try:
            from src.config import schedulers_cfg
            has_schedulers = hasattr(schedulers_cfg, 'enabled') or bool(getattr(schedulers_cfg, '__dict__', {}))
            if not has_schedulers:
                self.enabled = False
                self.rag_enabled = False
                self.email_enabled = False
                return
            self.enabled = bool(getattr(schedulers_cfg, 'enabled', False))
            rag_cfg = getattr(schedulers_cfg, 'rag_reindex', getattr(schedulers_cfg, 'rag', None))
            email_cfg = getattr(schedulers_cfg, 'email_check', getattr(schedulers_cfg, 'email', None))
            self.rag_enabled = bool(getattr(rag_cfg, 'enabled', False)) if rag_cfg is not None else False
            rag_hours = getattr(rag_cfg, 'interval_hours', 24) if rag_cfg is not None else 24
            self._rag_interval_seconds = max(60.0, float(rag_hours) * 3600.0)
            self.email_enabled = bool(getattr(email_cfg, 'enabled', False)) if email_cfg is not None else False
            email_minutes = getattr(email_cfg, 'interval_minutes', 5) if email_cfg is not None else 5
            self._email_interval_seconds = max(10.0, float(email_minutes) * 60.0)
        except Exception as ex:
            logger.error(f'[Scheduler] Ошибка загрузки конфигурации: {ex}')
            self.enabled = False
            self.rag_enabled = False
            self.email_enabled = False

    async def restart(self) -> None:
        """Перезагружает конфигурацию и перезапускает активные фоновые задачи."""
        was_running = self._running
        if was_running:
            await self.stop()
        self.load_from_config()
        if self.enabled:
            await self.start()

    @property
    def is_running(self) -> bool:
        """Возвращает True, если фоновый планировщик активен."""
        return self._running

    @property
    def status(self) -> Dict[str, Any]:
        """Возвращает диагностический статус запланированных задач."""
        return {
            'running': self._running,
            'enabled': self.enabled,
            'rag_enabled': self.rag_enabled,
            'rag_interval_hours': self._rag_interval_seconds / 3600.0,
            'email_enabled': self.email_enabled,
            'email_interval_minutes': self._email_interval_seconds / 60.0,
            'last_rag_run': self._last_rag_run.strftime('%Y-%m-%dT%H:%M:%SZ') if self._last_rag_run else None,
            'last_email_run': self._last_email_run.strftime('%Y-%m-%dT%H:%M:%SZ') if self._last_email_run else None,
            'unread_emails_count': len(self._latest_unread_emails),
            'latest_unread_emails': self._latest_unread_emails[:5],
        }

    async def start(self) -> None:
        """Запускает периодические фоновые задачи."""
        if self._running or not self.enabled:
            return
        self._running = True
        logger.info(
            f'Запуск BackgroundScheduler (RAG={self.rag_enabled} [{self._rag_interval_seconds / 3600:.1f}ч], '
            f'Email={self.email_enabled} [{self._email_interval_seconds / 60:.1f}м])...'
        )
        if self.rag_enabled:
            self._tasks.append(asyncio.create_task(self._run_rag_periodically()))
        if self.email_enabled:
            self._tasks.append(asyncio.create_task(self._run_email_check_periodically()))

    async def stop(self) -> None:
        """Корректно останавливает все запущенные фоновые задачи."""
        self._running = False
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        logger.info('BackgroundScheduler остановлен.')

    async def _run_rag_periodically(self) -> None:
        """Периодически выполняет проверку и перестроение RAG-индексов."""
        while self._running:
            try:
                await self.recheck_and_update_all_rags()
                self._last_rag_run = datetime.now(timezone.utc)
            except asyncio.CancelledError:
                break
            except Exception as ex:
                logger.error(f'[Scheduler] Ошибка периодического обновления RAG: {ex}')
            try:
                await asyncio.sleep(self._rag_interval_seconds)
            except asyncio.CancelledError:
                break

    async def _run_email_check_periodically(self) -> None:
        """Периодически проверяет непрочитанные письма в Gmail."""
        while self._running:
            try:
                await self.check_emails()
                self._last_email_run = datetime.now(timezone.utc)
            except asyncio.CancelledError:
                break
            except Exception as ex:
                logger.error(f'[Scheduler] Ошибка периодической проверки почты: {ex}')
            try:
                await asyncio.sleep(self._email_interval_seconds)
            except asyncio.CancelledError:
                break

    async def recheck_and_update_all_rags(self) -> Dict[str, Any]:
        """Сканирует все пользовательские коллекции RAG и обновляет индексы.

        Returns:
            Dict[str, Any]: Сводка по переиндексированным коллекциям.
        """
        logger.info('[Scheduler] Запуск проверки и обновления пользовательских RAG-индексов...')
        if user_manager is None or user_workspace_rag_manager is None:
            logger.warning('[Scheduler] Менеджеры пользователей или RAG недоступны.')
            return {'updated_count': 0, 'details': []}
        users = await asyncio.to_thread(user_manager.get_all_users)
        updated_count = 0
        details = []
        for user in users:
            user_id = user.get('id')
            if not user_id:
                continue
            try:
                collections = await asyncio.to_thread(user_workspace_rag_manager.list_collections, user_id)
                for col in collections:
                    rag_id = col.get('id')
                    if not rag_id:
                        continue
                    logger.info(f"[Scheduler] Обновление RAG-коллекции '{rag_id}' для пользователя {user_id}")
                    res = await asyncio.to_thread(
                        user_workspace_rag_manager.build_collection,
                        user_id=user_id,
                        rag_id=rag_id,
                        provider=col.get('provider', 'local_tfidf'),
                    )
                    updated_count += 1
                    details.append({
                        'user_id': user_id,
                        'rag_id': rag_id,
                        'status': res.get('status', 'ok'),
                        'chunks_count': res.get('chunks_count', 0),
                    })
            except Exception as ex:
                logger.error(f'[Scheduler] Не удалось обновить RAG для пользователя {user_id}: {ex}')
        logger.info(f'[Scheduler] Переиндексация RAG завершена. Обновлено коллекций: {updated_count}.')
        return {'updated_count': updated_count, 'details': details}

    async def check_emails(self, account_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Проверяет наличие непрочитанных писем в Gmail через google-workspace.

        Args:
            account_name (Optional[str]): Имя конкретного аккаунта из пула.

        Returns:
            List[Dict[str, Any]]: Список сводок непрочитанных сообщений.
        """
        scripts_dir = __root__ / '.agents' / 'skills' / 'user-skills' / 'google-workspace' / 'scripts'
        if not scripts_dir.exists():
            scripts_dir = __root__ / '.agents' / 'skills' / 'google-workspace' / 'scripts'
        if scripts_dir.exists() and str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))

        def _fetch_messages() -> List[Dict[str, Any]]:
            try:
                from gmail_manager import GmailManager
                manager = GmailManager(account_name=account_name)
                if not manager.service:
                    return []
                return manager.search_messages(query='is:unread', max_results=10)
            except Exception as ex:
                logger.warning(f'[Scheduler] Проверка почты пропущена или завершилась сбоем: {ex}')
                return []

        messages = await asyncio.to_thread(_fetch_messages)
        if messages:
            self._latest_unread_emails = list(messages)[:_MAX_UNREAD_CACHE]
            logger.info(f'[Scheduler] Найдено непрочитанных писем в Gmail: {len(messages)}.')
        return messages


scheduler = BackgroundScheduler()
