from __future__ import annotations
import argparse
import asyncio
import sys
from pathlib import Path
_project_root = Path(__file__).resolve().parent.parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
from header import __root__
from src.version_manager import get_version_manager
from src.db.migrations import get_migration_manager
from logger import logger

def check_updates() -> dict:
    """Check if newer updates exist on remote git repository.

    Returns:
        dict: Information regarding current vs remote versions and update status.
    """
    vm = get_version_manager(__root__)
    return vm.check_updates()

def perform_update(branch: str='main', auto_backup: bool=True) -> dict:
    """Execute complete application update process including backup and migrations.

    Args:
        branch (str): Remote branch name to merge.
        auto_backup (bool): Create filesystem snapshot before merging.

    Returns:
        dict: Result summary of the update process.
    """
    vm = get_version_manager(__root__)
    return asyncio.run(vm.update_application(branch=branch, auto_backup=auto_backup))

def main() -> int:
    """CLI entry point for system-updater skill helper."""
    parser = argparse.ArgumentParser(description='AI Windows Admin System Updater')
    parser.add_argument('--check', action='store_true', help='Check for available updates')
    parser.add_argument('--apply', action='store_true', help='Apply application updates')
    parser.add_argument('--branch', type=str, default='main', help='Target git branch')
    parser.add_argument('--no-backup', action='store_true', help='Skip pre-update backup')
    parser.add_argument('--status-db', action='store_true', help='Check DB migrations status')
    args = parser.parse_args()
    if args.status_db:
        db_mgr = get_migration_manager(__root__)
        status = db_mgr.get_status()
        logger.console('\n--- DATABASE MIGRATION STATUS ---')
        for db, info in status.items():
            logger.console(f"[{db}] Up-to-date: {info['is_up_to_date']} | Applied: {info['applied_count']} | Pending: {info['pending_count']}")
            if info['pending_migrations']:
                logger.console(f"  Pending: {', '.join(info['pending_migrations'])}")
        logger.console('---------------------------------\n')
        return 0
    if args.check or not args.apply:
        res = check_updates()
        logger.console('\n--- SYSTEM VERSION & UPDATE STATUS ---')
        logger.console(f"Current version: {res.get('current_version')}")
        logger.console(f"Remote version:  {res.get('remote_version')}")
        logger.console(f"Update available: {res.get('is_update_available')}")
        logger.console(f"Status:          {res.get('status')}")
        logger.console('--------------------------------------\n')
        if not args.apply:
            return 0
    if args.apply:
        logger.console(f'Starting update (branch: {args.branch})...')
        res = perform_update(branch=args.branch, auto_backup=not args.no_backup)
        if res.get('success'):
            logger.console(f"✅ Update successful: {res.get('version')}")
            if res.get('backup_path'):
                logger.console(f"📦 Backup created at: {res.get('backup_path')}")
            return 0
        else:
            logger.console(f"❌ Update failed: {res.get('message')}")
            return 1
    return 0
if __name__ == '__main__':
    sys.exit(main())
