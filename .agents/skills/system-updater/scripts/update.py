# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Skill - System Updater CLI
# =============================================================================
# Description:
#   Скрипт навыка system-updater для проверки, применения и отката обновлений
#   проекта ai-tc по релизным Git-тегам (SemVer 2.0).
#
# Usage Examples:
#   CLI:
#     py .agents/skills/system-updater/scripts/update.py --check
#     py .agents/skills/system-updater/scripts/update.py --apply --tag v1.0.0
#     py .agents/skills/system-updater/scripts/update.py --rollback
#
# File: update.py
# Project: ai-tc
# Package: skills.system-updater.scripts
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20 21:12:00
# =============================================================================

"""Скрипт навыка system-updater на базе релизных Git-тегов."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from header import __root__
from logger import logger
from src.version_manager import get_version_manager


def main() -> int:
    """Точка входа CLI-скрипта навыка system-updater."""
    parser = argparse.ArgumentParser(description='ai-tc System Updater (Git Tags Strategy)')
    parser.add_argument('--check', action='store_true', help='Проверить наличие новых релизных тегов')
    parser.add_argument('--list-tags', action='store_true', help='Вывести список доступных удалённых тегов')
    parser.add_argument('--apply', action='store_true', help='Применить обновление до последнего или указанного тега')
    parser.add_argument('--rollback', action='store_true', help='Откатиться на предыдущий бэкап или указанный тег')
    parser.add_argument('--tag', type=str, default=None, help='Целевой SemVer-тег (например, v1.1.0)')
    parser.add_argument('--prerelease', action='store_true', help='Включить пререлизные теги (-rc, -beta)')
    parser.add_argument('--no-backup', action='store_true', help='Пропустить резервное копирование')
    parser.add_argument('--allow-dirty', action='store_true', help='Разрешить обновление с незакоммиченными файлами')
    args = parser.parse_args()

    vm = get_version_manager(__root__)
    allow_pre = True if args.prerelease else None

    if args.list_tags:
        tags = vm.list_remote_tags(allow_prerelease=allow_pre)
        logger.console('\n--- ДОСТУПНЫЕ РЕЛИЗНЫЕ ТЕГИ ---')
        for t in tags or ['(нет релизных тегов)']:
            logger.console(f'  {t}')
        logger.console('-------------------------------\n')
        return 0

    if args.rollback:
        res = vm.rollback(target_tag=args.tag)
        if res.get('success'):
            logger.console(f"[OK] {res.get('message')}")
            return 0
        logger.console(f"[ERROR] {res.get('message')}")
        return 1

    if args.apply:
        res = asyncio.run(
            vm.update_application(
                target_tag=args.tag,
                auto_backup=not args.no_backup,
                allow_dirty=args.allow_dirty,
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

    res = vm.check_updates(allow_prerelease=allow_pre)
    logger.console('\n--- СТАТУС ВЕРСИИ И ОБНОВЛЕНИЙ ---')
    logger.console(f"Канал:               {res.get('channel')}")
    logger.console(f"Текущая версия:      {res.get('current_version')}")
    logger.console(f"Удалённый тег:       {res.get('remote_version') or 'нет релизов'}")
    logger.console(f"Обновление доступно: {res.get('is_update_available')}")
    logger.console(f"Статус:              {res.get('status')}")
    logger.console('----------------------------------\n')
    return 0 if res.get('status') != 'error' else 1


if __name__ == '__main__':
    sys.exit(main())
