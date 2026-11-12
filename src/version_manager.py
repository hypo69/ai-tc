# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin CORE - Version Manager Module
# =============================================================================
# Description:
#   Менеджер версий и обработчик автоматических обновлений приложения.
#
# Usage Examples:
#   Python API:
#     from src.version_manager import UpdateStatus, get_version_manager
#
#     vm = get_version_manager()
#
# File: version_manager.py
# Project: ai-windows-admin
# Package: src
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-10 18:15:00
# =============================================================================

"""Менеджер версий и обработчик автоматических обновлений приложения.

Ключевые функции:
- Проверка версии в Git-репозитории
- Загрузка обновленных файлов
- Создание резервных копий перед обновлением (атомарное сохранение метаданных)
- Кроссплатформенная поддержка (Windows, Linux, macOS)
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
from typing import Dict, List, Optional, Tuple

from header import __root__
from logger import logger


def _utc_now_iso() -> str:
    """Возвращает текущее время в строгом формате UTC ISO 8601."""
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _atomic_write_json(path: Path, data: Dict) -> None:
    """Атомарно записывает JSON-файл через временный файл .tmp и os.replace()."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + '.tmp')
    try:
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise


class UpdateStatus(Enum):
    """Статусы обновления приложения."""
    CURRENT = 'up_to_date'
    UPDATE_AVAILABLE = 'update_available'
    ERROR = 'error'
    UPDATING = 'updating'


@dataclass
class VersionInfo:
    """Информация о версии приложения."""
    current_version: str
    remote_version: str
    commit_hash: str
    remote_commit_hash: str
    is_update_available: bool
    update_status: str


class VersionManager:
    """Менеджер версий и обновлений приложения.

    Реализует функциональность:
    - Проверка текущей версии в Git
    - Проверка доступных обновлений в удаленном репозитории
    - Загрузка и применение обновлений
    - Создание резервных копий перед обновлением
    - Восстановление из резервной копии в случае сбоя
    """

    def __init__(self, repo_path: Optional[Path] = None):
        """Инициализирует менеджер версий.

        Args:
            repo_path: Путь к репозиторию (по умолчанию __root__).
        """
        self.repo_path: Path = repo_path or __root__
        app_name = os.environ.get('APP_NAME') or (__root__.name if __root__.exists() else 'ai-windows-admin')
        appdata = os.environ.get('APPDATA')
        base_tmp = (Path(appdata) / app_name / 'tmp') if appdata else (Path(tempfile.gettempdir()) / app_name)
        self.temp_backup_dir: Path = base_tmp / 'backups'
        self.update_log_dir: Path = base_tmp / 'updates'
        self.current_version: str = '1.0.0'
        self.remote_url: str = 'origin'
        self._lock = threading.RLock()
        self.temp_backup_dir.mkdir(parents=True, exist_ok=True)
        self.update_log_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f'VersionManager инициализирован. Репозиторий: {self.repo_path}')
        logger.info(f'Директория резервных копий: {self.temp_backup_dir}')

    def _run_git_command(self, command: List[str], cwd: Optional[Path] = None) -> Tuple[int, str, str]:
        """Безопасно выполняет команду git с явным таймаутом.

        Args:
            command: Список аргументов для команды git.
            cwd: Рабочая директория (по умолчанию repo_path).

        Returns:
            Кортеж (код возврата, stdout, stderr).
        """
        try:
            cwd = cwd or self.repo_path
            result = subprocess.run(
                command,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            )
            return (result.returncode, result.stdout.strip(), result.stderr.strip())
        except subprocess.TimeoutExpired:
            logger.error('Превышен таймаут выполнения команды git')
            return (-1, '', 'Timeout')
        except Exception as ex:
            logger.error(f'Ошибка выполнения команды git: {ex}')
            return (-1, '', str(ex))

    def get_current_version(self) -> Optional[str]:
        """Получает текущую версию из тега git или короткого хеша коммита.

        Returns:
            Строка версии или None при ошибке.
        """
        try:
            rc, stdout, _ = self._run_git_command(['git', 'describe', '--tags', '--always'])
            if rc == 0 and stdout:
                self.current_version = stdout
                logger.info(f'Текущая версия: {self.current_version}')
                return self.current_version
            rc, stdout, _ = self._run_git_command(['git', 'rev-parse', '--short', 'HEAD'])
            if rc == 0 and stdout:
                self.current_version = stdout
                logger.info(f'Текущая версия (хеш): {self.current_version}')
                return self.current_version
            logger.warning('Не удалось определить текущую версию')
            return None
        except Exception as ex:
            logger.error(f'Ошибка получения текущей версии: {ex}')
            return None

    def get_remote_version(self) -> Optional[str]:
        """Получает актуальную версию из удаленного репозитория.

        Returns:
            Строка версии или None при ошибке.
        """
        try:
            from src.utils.versioning import choose_best_tag
            rc, stdout, _ = self._run_git_command(['git', 'ls-remote', '--tags', self.remote_url])
            if rc == 0 and stdout:
                lines = [line.strip() for line in stdout.split('\n') if line.strip()]
                tags = [
                    line.split()[-1].replace('refs/tags/', '').replace('^{}', '')
                    for line in lines
                    if 'refs/tags/' in line
                ]
                tags = [t for t in tags if t]
                if tags:
                    remote_version = choose_best_tag(tags)
                    if remote_version:
                        logger.info(f'Удаленная версия: {remote_version}')
                        return remote_version
            rc, stdout, _ = self._run_git_command(['git', 'ls-remote', self.remote_url, 'HEAD'])
            if rc == 0 and stdout:
                remote_hash = stdout.split()[0][:7]
                logger.info(f'Удаленная версия (HEAD): {remote_hash}')
                return remote_hash
            logger.warning('Не удалось определить удаленную версию')
            return None
        except Exception as ex:
            logger.error(f'Ошибка получения удаленной версии: {ex}')
            return None

    def check_updates(self) -> Dict:
        """Проверяет наличие доступных обновлений.

        Returns:
            Словарь с информацией о статусе обновлений.
        """
        try:
            current = self.get_current_version()
            remote = self.get_remote_version()
            if not current or not remote:
                logger.warning('Не удалось проверить наличие обновлений')
                return {'status': UpdateStatus.ERROR.value, 'message': 'Could not get version information'}
            rc1, curr_hash, _ = self._run_git_command(['git', 'rev-parse', 'HEAD'])
            rc2, remote_ls, _ = self._run_git_command(['git', 'ls-remote', self.remote_url, 'HEAD'])
            remote_hash = remote_ls.split()[0] if rc2 == 0 and remote_ls else 'unknown'
            curr_hash = curr_hash if rc1 == 0 else 'unknown'
            if curr_hash != 'unknown' and remote_hash != 'unknown':
                if curr_hash == remote_hash or curr_hash.startswith(remote_hash) or remote_hash.startswith(curr_hash):
                    is_update_available = False
                elif current != remote and (not (curr_hash.startswith(remote) or remote.startswith(curr_hash[:7]))):
                    is_update_available = True
                else:
                    is_update_available = curr_hash[:7] != remote_hash[:7]
            else:
                is_update_available = current != remote
            status = UpdateStatus.UPDATE_AVAILABLE if is_update_available else UpdateStatus.CURRENT
            result = {
                'status': status.value,
                'current_version': current,
                'remote_version': remote,
                'current_commit': curr_hash,
                'remote_commit': remote_hash,
                'is_update_available': is_update_available,
                'timestamp': _utc_now_iso(),
            }
            logger.info(f"Результат проверки обновлений: {result['status']}")
            return result
        except Exception as ex:
            logger.error(f'Ошибка проверки обновлений: {ex}')
            return {'status': UpdateStatus.ERROR.value, 'message': str(ex)}

    def backup_files(self, files_to_backup: Optional[List[str]] = None) -> Optional[Path]:
        """Создает резервную копию файлов перед обновлением.

        Args:
            files_to_backup: Список файлов и папок для резервного копирования.

        Returns:
            Путь к директории резервной копии или None при ошибке.
        """
        with self._lock:
            try:
                if files_to_backup is None:
                    files_to_backup = ['config.json', '.env', 'src', 'requirements.txt']
                backup_dir = self.temp_backup_dir / f"backup_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
                backup_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f'Создание резервной копии в: {backup_dir}')
                backup_count = 0
                for file_item in files_to_backup:
                    src = self.repo_path / file_item
                    if not src.exists():
                        logger.warning(f'Файл для резервной копии не найден: {src}')
                        continue
                    dst = backup_dir / file_item
                    try:
                        if src.is_dir():
                            if dst.exists():
                                shutil.rmtree(dst)
                            shutil.copytree(src, dst, dirs_exist_ok=True)
                        else:
                            dst.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(src, dst)
                        backup_count += 1
                        logger.debug(f'Скопировано в бэкап: {file_item}')
                    except Exception as ex:
                        logger.warning(f'Ошибка копирования {file_item}: {ex}')
                if backup_count == 0:
                    logger.error('Не удалось создать резервную копию (нет файлов)')
                    return None
                backup_info = {
                    'timestamp': _utc_now_iso(),
                    'repo_path': str(self.repo_path),
                    'backed_up_files': files_to_backup,
                    'backed_up_count': backup_count,
                    'version': self.current_version,
                }
                info_file = backup_dir / '.backup_info.json'
                _atomic_write_json(info_file, backup_info)
                logger.info(f'Резервная копия создана: {backup_dir}')
                return backup_dir
            except Exception as ex:
                logger.error(f'Ошибка создания резервной копии: {ex}')
                return None

    def restore_from_backup(self, backup_path: Path) -> bool:
        """Восстанавливает файлы из резервной копии.

        Args:
            backup_path: Путь к директории резервной копии.

        Returns:
            True при успешном восстановлении, иначе False.
        """
        with self._lock:
            try:
                if not backup_path.exists():
                    logger.error(f'Директория резервной копии не найдена: {backup_path}')
                    return False
                logger.info(f'Восстановление из резервной копии: {backup_path}')
                restore_count = 0
                for item in backup_path.iterdir():
                    if item.name == '.backup_info.json' or item.name.endswith('.tmp'):
                        continue
                    dst = self.repo_path / item.name
                    try:
                        if item.is_dir():
                            if dst.exists():
                                shutil.rmtree(dst)
                            shutil.copytree(item, dst, dirs_exist_ok=True)
                        else:
                            dst.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(item, dst)
                        restore_count += 1
                        logger.debug(f'Восстановлено: {item.name}')
                    except Exception as ex:
                        logger.warning(f'Ошибка восстановления {item.name}: {ex}')
                logger.info(f'Восстановлено элементов: {restore_count}')
                return restore_count > 0
            except Exception as ex:
                logger.error(f'Ошибка восстановления из резервной копии: {ex}')
                return False

    def fetch_updates(self) -> bool:
        """Загружает обновления из удаленного репозитория через git fetch.

        Returns:
            True при успешной загрузке, иначе False.
        """
        try:
            logger.info(f'Загрузка обновлений из {self.remote_url}...')
            rc, _, stderr = self._run_git_command(['git', 'fetch', self.remote_url])
            if rc != 0:
                logger.error(f'Ошибка git fetch: {stderr}')
                return False
            logger.info('Обновления успешно загружены')
            return True
        except Exception as ex:
            logger.error(f'Ошибка загрузки обновлений: {ex}')
            return False

    def merge_updates(self, branch: str = 'main') -> Tuple[bool, str]:
        """Выполняет слияние обновлений из удаленной ветки.

        Args:
            branch: Имя ветки (по умолчанию main).

        Returns:
            Кортеж (успех, сообщение).
        """
        try:
            logger.info(f'Слияние обновлений из {self.remote_url}/{branch}...')
            rc, stdout, stderr = self._run_git_command(['git', 'merge', f'{self.remote_url}/{branch}'])
            if rc != 0:
                if 'conflict' in stderr.lower():
                    logger.warning(f'Конфликт слияния: {stderr}')
                    return (False, f'Conflict during merge: {stderr}')
                logger.error(f'Ошибка git merge: {stderr}')
                return (False, f'Error merging: {stderr}')
            logger.info('Обновления успешно объединены')
            return (True, stdout)
        except Exception as ex:
            logger.error(f'Ошибка слияния обновлений: {ex}')
            return (False, str(ex))

    async def update_application(self, branch: str = 'main', auto_backup: bool = True) -> Dict:
        """Выполняет полный цикл обновления приложения.

        Args:
            branch: Ветка для обновления.
            auto_backup: Создавать ли резервную копию перед обновлением.

        Returns:
            Словарь с результатом обновления.
        """
        try:
            logger.info('Запуск процесса обновления приложения...')
            check_result = self.check_updates()
            if check_result['status'] == UpdateStatus.ERROR.value:
                return {'success': False, 'status': UpdateStatus.ERROR.value, 'message': 'Could not check for updates'}
            if not check_result.get('is_update_available'):
                logger.info('Приложение уже обновлено до последней версии')
                return {'success': False, 'status': UpdateStatus.CURRENT.value, 'message': 'No updates available'}
            backup_path = None
            if auto_backup:
                backup_path = self.backup_files()
                if not backup_path:
                    return {'success': False, 'status': UpdateStatus.ERROR.value, 'message': 'Could not create backup'}
            if not self.fetch_updates():
                if backup_path:
                    self.restore_from_backup(backup_path)
                return {'success': False, 'status': UpdateStatus.ERROR.value, 'message': 'Error downloading updates'}
            merge_ok, merge_msg = self.merge_updates(branch)
            if not merge_ok:
                if backup_path:
                    self.restore_from_backup(backup_path)
                return {'success': False, 'status': UpdateStatus.ERROR.value, 'message': f'Error merging: {merge_msg}'}
            try:
                from apps.helpdesk.db.migrations import get_migration_manager
                db_mgr = get_migration_manager(self.repo_path)
                mig_res = db_mgr.apply_all_pending()
                if not mig_res.get('success', False):
                    logger.warning(f'Миграции БД завершились с предупреждениями при обновлении: {mig_res}')
                else:
                    logger.info(f"Миграции БД применены: {mig_res.get('applied_total', 0)}")
            except Exception as mig_ex:
                logger.error(f'Ошибка применения миграций БД при обновлении: {mig_ex}')
            update_info = {
                'timestamp': _utc_now_iso(),
                'from_version': check_result.get('current_version'),
                'to_version': check_result.get('remote_version'),
                'backup_path': str(backup_path) if backup_path else None,
                'branch': branch,
                'status': 'success',
            }
            update_log_file = self.update_log_dir / f"update_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
            _atomic_write_json(update_log_file, update_info)
            logger.info(f"Приложение обновлено: {check_result.get('current_version')} → {check_result.get('remote_version')}")
            return {
                'success': True,
                'status': UpdateStatus.CURRENT.value,
                'message': 'Update completed successfully',
                'version': check_result.get('remote_version'),
                'backup_path': str(backup_path) if backup_path else None,
            }
        except Exception as ex:
            logger.error(f'Ошибка обновления приложения: {ex}')
            return {'success': False, 'status': UpdateStatus.ERROR.value, 'message': str(ex)}

    def cleanup_old_backups(self, keep_count: int = 5) -> int:
        """Удаляет устаревшие резервные копии, сохраняя последние N копий.

        Args:
            keep_count: Количество последних резервных копий для сохранения.

        Returns:
            Количество удаленных резервных копий.
        """
        with self._lock:
            try:
                if not self.temp_backup_dir.exists():
                    return 0
                backups = sorted(
                    [d for d in self.temp_backup_dir.iterdir() if d.is_dir()],
                    key=lambda x: x.stat().st_mtime,
                    reverse=True,
                )
                deleted_count = 0
                for backup in backups[keep_count:]:
                    try:
                        shutil.rmtree(backup)
                        deleted_count += 1
                        logger.debug(f'Удалена старая резервная копия: {backup.name}')
                    except Exception as ex:
                        logger.warning(f'Ошибка удаления резервной копии: {ex}')
                if deleted_count > 0:
                    logger.info(f'Удалено устаревших резервных копий: {deleted_count}')
                return deleted_count
            except Exception as ex:
                logger.error(f'Ошибка очистки резервных копий: {ex}')
                return 0


version_manager: Optional[VersionManager] = None
_vm_lock = threading.RLock()


def get_version_manager(repo_path: Optional[Path] = None) -> VersionManager:
    """Возвращает глобальный экземпляр менеджера версий (потокобезопасный Singleton).

    Args:
        repo_path: Путь к репозиторию.

    Returns:
        Экземпляр VersionManager.
    """
    global version_manager
    with _vm_lock:
        if version_manager is None:
            version_manager = VersionManager(repo_path)
        return version_manager
