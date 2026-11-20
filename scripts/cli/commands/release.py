# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Scripts Cli Commands - Release & Update
# =============================================================================
# Description:
#   CLI-команды `update` и `release` для управления обновлениями и релизами
#   проекта ai-tc на базе Git-тегов (SemVer 2.0).
#
# Usage Examples:
#   CLI:
#     py manage_tools.py update check
#     py manage_tools.py update apply --tag v1.0.0
#     py manage_tools.py update rollback
#     py manage_tools.py release create --bump patch --push
#
# File: release.py
# Project: ai-tc
# Package: scripts.cli.commands
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20 21:10:00
# =============================================================================

"""CLI-команды `update` и `release` на базе Git-тегов (SemVer 2.0)."""

from __future__ import annotations

import argparse
import asyncio

from header import __root__
from logger import logger
from src.version_manager import get_version_manager


def register_update_parser(subparsers: argparse._SubParsersAction) -> None:
    """Регистрирует подпарсер команды `update`."""
    upd = subparsers.add_parser('update', help='Обновление приложения по релизным Git-тегам')
    sub = upd.add_subparsers(dest='subcommand', help='Подкоманды update')

    p_check = sub.add_parser('check', help='Проверить наличие новых релизных тегов')
    p_check.add_argument('--prerelease', action='store_true', help='Включить пререлизные теги (-rc, -beta)')

    p_list = sub.add_parser('list', help='Показать список доступных удалённых тегов')
    p_list.add_argument('--prerelease', action='store_true', help='Включить пререлизные теги')

    p_apply = sub.add_parser('apply', help='Обновить приложение до целевого или последнего тега')
    p_apply.add_argument('--tag', type=str, default=None, help='Целевой тег (например, v1.1.0)')
    p_apply.add_argument('--prerelease', action='store_true', help='Разрешить обновление до пререлиза')
    p_apply.add_argument('--no-backup', action='store_true', help='Пропустить резервное копирование')
    p_apply.add_argument('--allow-dirty', action='store_true', help='Разрешить обновление при незакоммиченных изменениях')

    p_rb = sub.add_parser('rollback', help='Откатить приложение на предыдущий бэкап или тег')
    p_rb.add_argument('--tag', type=str, default=None, help='Откатить на конкретный тег (например, v1.0.0)')


def register_release_parser(subparsers: argparse._SubParsersAction) -> None:
    """Регистрирует подпарсер команды `release`."""
    rel = subparsers.add_parser('release', help='Выпуск новых релизных SemVer-тегов')
    sub = rel.add_subparsers(dest='subcommand', help='Подкоманды release')

    p_create = sub.add_parser('create', help='Создать новый аннотированный SemVer-тег')
    p_create.add_argument('--tag', type=str, default=None, help='Явный тег (например, v1.0.0)')
    p_create.add_argument('--bump', choices=['patch', 'minor', 'major'], default='patch', help='Автоинкремент версии')
    p_create.add_argument('--prerelease', type=str, default=None, help='Суффикс пререлиза (например, rc.1)')
    p_create.add_argument('--message', '-m', type=str, default=None, help='Пользовательское сообщение релиза')
    p_create.add_argument('--push', action='store_true', help='Отправить созданный тег в удалённый репозиторий')

    p_list = sub.add_parser('list', help='Показать локальные релизные теги')
    p_list.add_argument('--prerelease', action='store_true', help='Включить пререлизные теги')


def run_update_command(args: argparse.Namespace) -> int:
    """Выполняет подкоманды `update`."""
    vm = get_version_manager(__root__)
    sub = getattr(args, 'subcommand', '')
    allow_pre = True if getattr(args, 'prerelease', False) else None

    if sub == 'check':
        res = vm.check_updates(allow_prerelease=allow_pre)
        logger.console('\n--- СТАТУС ОБНОВЛЕНИЙ (GIT TAGS) ---')
        logger.console(f"Канал:              {res.get('channel')}")
        logger.console(f"Текущая версия:     {res.get('current_version')}")
        logger.console(f"Последний тег:      {res.get('remote_version') or 'нет релизов'}")
        logger.console(f"Обновление доступно:{' Да' if res.get('is_update_available') else ' Нет'}")
        logger.console(f"Статус:             {res.get('status')}")
        logger.console('------------------------------------\n')
        return 0 if res.get('status') != 'error' else 1

    if sub == 'list':
        tags = vm.list_remote_tags(allow_prerelease=allow_pre)
        logger.console('\n--- ДОСТУПНЫЕ РЕЛИЗНЫЕ ТЕГИ (REMOTE) ---')
        if not tags:
            logger.console('  (релизные теги не найдены)')
        else:
            for t in tags:
                logger.console(f'  - {t}')
        logger.console('----------------------------------------\n')
        return 0

    if sub == 'apply':
        res = asyncio.run(
            vm.update_application(
                target_tag=getattr(args, 'tag', None),
                auto_backup=not getattr(args, 'no_backup', False),
                allow_dirty=getattr(args, 'allow_dirty', False),
                allow_prerelease=allow_pre,
            )
        )
        if res.get('success'):
            logger.console(f"[OK] {res.get('message')}")
            if res.get('backup_path'):
                logger.console(f"Резервная копия: {res.get('backup_path')}")
            return 0
        logger.console(f"[ERROR] {res.get('message')}")
        return 1

    if sub == 'rollback':
        res = vm.rollback(target_tag=getattr(args, 'tag', None))
        if res.get('success'):
            logger.console(f"[OK] {res.get('message')}")
            return 0
        logger.console(f"[ERROR] {res.get('message')}")
        return 1

    logger.console(f'Неизвестная подкоманда update: {sub}')
    return 1


def run_release_command(args: argparse.Namespace) -> int:
    """Выполняет подкоманды `release`."""
    vm = get_version_manager(__root__)
    sub = getattr(args, 'subcommand', '')

    if sub == 'list':
        allow_pre = True if getattr(args, 'prerelease', False) else None
        tags = vm.list_local_tags(allow_prerelease=allow_pre)
        logger.console('\n--- ЛОКАЛЬНЫЕ РЕЛИЗНЫЕ ТЕГИ ---')
        if not tags:
            logger.console('  (локальные теги отсутствуют)')
        else:
            for t in tags:
                logger.console(f'  - {t}')
        logger.console('-------------------------------\n')
        return 0

    if sub == 'create':
        res = vm.create_release(
            tag=getattr(args, 'tag', None),
            bump=getattr(args, 'bump', 'patch'),
            message=getattr(args, 'message', None),
            push=getattr(args, 'push', False),
            prerelease=getattr(args, 'prerelease', None),
        )
        if res.get('success'):
            logger.console(f"[OK] Создан релизный тег: {res.get('tag')} (push={res.get('pushed')})")
            if res.get('changelog'):
                logger.console('Изменения в релизе:\n' + res['changelog'])
            return 0
        logger.console(f"[ERROR] {res.get('message')}")
        return 1

    logger.console(f'Неизвестная подкоманда release: {sub}')
    return 1
