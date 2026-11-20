# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc CORE - Version Manager Module (Tag-Based Strategy)
# =============================================================================
# Description:
#   Менеджер версий, обновлений и релизов на базе Git-тегов (SemVer 2.0).
#   Обеспечивает безопасное переключение релизной ветки на целевой тег,
#   резервное копирование, автообновление зависимостей, миграции БД и откат.
#
# Usage Examples:
#   Python API:
#     from src.version_manager import get_version_manager
#
#     vm = get_version_manager()
#     status = vm.check_updates()
#
# File: version_manager.py
# Project: ai-tc
# Package: src
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20 21:08:00
# =============================================================================

"""Менеджер версий, обновлений и релизов на базе Git-тегов (SemVer 2.0)."""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from typing import Any, Dict, List, Optional, Tuple

from header import __root__
from logger import logger
from src.utils.versioning import (
    bump_version,
    choose_best_tag,
    compare_versions,
    is_valid_semver_tag,
    sort_tags,
)

DEFAULT_UPDATE_CONFIG: Dict[str, Any] = {
    'strategy': 'tags',
    'remote': 'origin',
    'channel': 'stable',
    'release_branch': 'release',
    'dev_branch': 'master',
    'tag_prefix': 'v',
    'auto_install_deps': True,
    'keep_backups': 5,
    'backup_items': ['config.json', '.env', 'requirements.txt', 'pyproject.toml'],
}


def _utc_now_iso() -> str:
    """Возвращает текущее время в строгом формате UTC ISO 8601."""
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
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


def _load_updates_config(repo_path: Path, override: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Загружает конфигурацию обновлений из `config.json` с наложением override."""
    cfg = dict(DEFAULT_UPDATE_CONFIG)
    config_file = repo_path / 'config.json'
    if config_file.exists():
        try:
            raw = json.loads(config_file.read_text(encoding='utf-8'))
            if isinstance(raw, dict) and isinstance(raw.get('updates'), dict):
                cfg.update(raw['updates'])
        except Exception as ex:
            logger.warning(f'Не удалось прочитать секцию updates из {config_file}: {ex}')
    if override:
        cfg.update(override)
    return cfg


class UpdateStatus(Enum):
    """Статусы проверки и применения обновлений приложения."""

    CURRENT = 'up_to_date'
    UPDATE_AVAILABLE = 'update_available'
    NO_RELEASES = 'no_releases'
    ERROR = 'error'
    UPDATING = 'updating'


@dataclass
class VersionInfo:
    """Структурированная информация о текущей и удалённой версиях."""

    current_version: str
    remote_version: str
    commit_hash: str
    remote_commit_hash: str
    is_update_available: bool
    update_status: str


class VersionManager:
    """Менеджер версий, обновлений и релизов на базе Git-тегов."""

    def __init__(
        self,
        repo_path: Optional[Path] = None,
        config: Optional[Dict[str, Any]] = None,
        backup_root: Optional[Path] = None,
    ):
        """Инициализирует менеджер версий.

        Args:
            repo_path: Путь к Git-репозиторию (по умолчанию `__root__`).
            config: Явное переопределение параметров секции `updates` (DI).
            backup_root: Корневая директория для бэкапов и логов обновлений.
        """
        self.repo_path: Path = Path(repo_path) if repo_path else __root__
        self.config: Dict[str, Any] = _load_updates_config(self.repo_path, config)
        self.remote_url: str = str(self.config['remote'])
        self.channel: str = str(self.config['channel'])
        self.release_branch: str = str(self.config['release_branch'])
        self.dev_branch: str = str(self.config['dev_branch'])
        self.tag_prefix: str = str(self.config['tag_prefix'])
        self.auto_install_deps: bool = bool(self.config['auto_install_deps'])
        self.keep_backups: int = int(self.config['keep_backups'])
        self.backup_items: List[str] = list(self.config['backup_items'])

        if backup_root is not None:
            base_tmp = Path(backup_root)
        else:
            app_name = os.environ.get('APP_NAME') or (__root__.name if __root__.exists() else 'ai-tc')
            appdata = os.environ.get('APPDATA')
            base_tmp = (Path(appdata) / app_name / 'tmp') if appdata else (Path(tempfile.gettempdir()) / app_name)

        self.temp_backup_dir: Path = base_tmp / 'backups'
        self.update_log_dir: Path = base_tmp / 'updates'
        self.current_version: str = '0.0.0'
        self._lock = threading.RLock()
        self.temp_backup_dir.mkdir(parents=True, exist_ok=True)
        self.update_log_dir.mkdir(parents=True, exist_ok=True)

    def _allow_prerelease(self, allow_prerelease: Optional[bool]) -> bool:
        """Определяет, разрешены ли пререлизные теги с учётом канала."""
        if allow_prerelease is not None:
            return allow_prerelease
        return self.channel.lower() in ('prerelease', 'beta', 'rc', 'canary')

    def _run_git_command(self, command: List[str], cwd: Optional[Path] = None, timeout: int = 30) -> Tuple[int, str, str]:
        """Выполняет команду Git с таймаутом и без создания консольного окна в Windows."""
        try:
            result = subprocess.run(
                command,
                cwd=str(cwd or self.repo_path),
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=timeout,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            )
            return (result.returncode, result.stdout.strip(), result.stderr.strip())
        except subprocess.TimeoutExpired:
            logger.error(f'Превышен таймаут выполнения команды git: {command}')
            return (-1, '', 'Timeout')
        except Exception as ex:
            logger.error(f'Ошибка выполнения команды git {command}: {ex}')
            return (-1, '', str(ex))

    def _get_git_state(self) -> Dict[str, str]:
        """Возвращает текущее состояние Git: ветку, полный хеш и точный тег."""
        _, commit, _ = self._run_git_command(['git', 'rev-parse', 'HEAD'])
        _, branch, _ = self._run_git_command(['git', 'rev-parse', '--abbrev-ref', 'HEAD'])
        rc_tag, exact_tag, _ = self._run_git_command(['git', 'describe', '--tags', '--exact-match'])
        return {
            'commit': commit or 'unknown',
            'branch': branch or 'HEAD',
            'tag': exact_tag if rc_tag == 0 else '',
        }

    def is_working_tree_clean(self) -> Tuple[bool, str]:
        """Проверяет отсутствие незакоммиченных изменений отслеживаемых файлов."""
        rc, stdout, stderr = self._run_git_command(['git', 'status', '--porcelain', '--untracked-files=no'])
        if rc != 0:
            return (False, stderr or 'Не удалось проверить статус Git')
        if stdout:
            return (False, stdout)
        return (True, '')

    def get_current_version(self) -> Optional[str]:
        """Возвращает текущий тег Git на HEAD или короткий хеш коммита."""
        rc, exact_tag, _ = self._run_git_command(['git', 'describe', '--tags', '--exact-match'])
        if rc == 0 and exact_tag:
            self.current_version = exact_tag
            return exact_tag
        rc, described, _ = self._run_git_command(['git', 'describe', '--tags', '--always'])
        if rc == 0 and described:
            self.current_version = described
            return described
        rc, short_hash, _ = self._run_git_command(['git', 'rev-parse', '--short', 'HEAD'])
        if rc == 0 and short_hash:
            self.current_version = short_hash
            return short_hash
        return None

    def list_local_tags(self, allow_prerelease: Optional[bool] = None) -> List[str]:
        """Возвращает отсортированный по убыванию список локальных SemVer-тегов."""
        rc, stdout, _ = self._run_git_command(['git', 'tag', '-l'])
        if rc != 0 or not stdout:
            return []
        raw_tags = [line.strip() for line in stdout.splitlines() if line.strip()]
        return sort_tags(raw_tags, allow_prerelease=self._allow_prerelease(allow_prerelease), prefix=self.tag_prefix)

    def _fetch_remote_tag_map(self) -> Dict[str, str]:
        """Получает отображение `{tag: commit_hash}` из удалённого репозитория."""
        rc, stdout, stderr = self._run_git_command(['git', 'ls-remote', '--tags', self.remote_url])
        if rc != 0:
            logger.error(f'Не удалось получить список тегов из {self.remote_url}: {stderr}')
            return {}
        tag_map: Dict[str, str] = {}
        for line in stdout.splitlines():
            parts = line.strip().split()
            if len(parts) < 2 or 'refs/tags/' not in parts[1]:
                continue
            commit_hash, ref = parts[0], parts[1]
            is_peeled = ref.endswith('^{}')
            tag_name = ref.replace('refs/tags/', '').replace('^{}', '')
            if not is_valid_semver_tag(tag_name, prefix=self.tag_prefix):
                continue
            if is_peeled or tag_name not in tag_map:
                tag_map[tag_name] = commit_hash
        return tag_map

    def list_remote_tags(self, allow_prerelease: Optional[bool] = None) -> List[str]:
        """Возвращает отсортированный по убыванию список удалённых SemVer-тегов."""
        tag_map = self._fetch_remote_tag_map()
        return sort_tags(list(tag_map.keys()), allow_prerelease=self._allow_prerelease(allow_prerelease), prefix=self.tag_prefix)

    def get_remote_version(self, allow_prerelease: Optional[bool] = None) -> Optional[str]:
        """Возвращает последний доступный SemVer-тег из удалённого репозитория."""
        tags = self.list_remote_tags(allow_prerelease=allow_prerelease)
        if not tags:
            return None
        best = choose_best_tag(tags, allow_prerelease=self._allow_prerelease(allow_prerelease))
        return best or None

    def check_updates(self, allow_prerelease: Optional[bool] = None) -> Dict[str, Any]:
        """Проверяет наличие новых релизных тегов в удалённом репозитории."""
        try:
            allow_pre = self._allow_prerelease(allow_prerelease)
            current = self.get_current_version() or 'unknown'
            state = self._get_git_state()
            tag_map = self._fetch_remote_tag_map()
            remote_tags = sort_tags(list(tag_map.keys()), allow_prerelease=allow_pre, prefix=self.tag_prefix)

            if not remote_tags:
                return {
                    'status': UpdateStatus.NO_RELEASES.value,
                    'strategy': 'tags',
                    'channel': 'prerelease' if allow_pre else 'stable',
                    'current_version': current,
                    'remote_version': None,
                    'current_commit': state['commit'],
                    'remote_commit': None,
                    'is_update_available': False,
                    'available_tags': [],
                    'timestamp': _utc_now_iso(),
                }

            latest_tag = remote_tags[0]
            remote_commit = tag_map.get(latest_tag, 'unknown')
            if is_valid_semver_tag(state['tag'], prefix=self.tag_prefix):
                is_update = compare_versions(state['tag'], latest_tag) < 0
            else:
                is_update = state['commit'] != remote_commit

            status = UpdateStatus.UPDATE_AVAILABLE if is_update else UpdateStatus.CURRENT
            return {
                'status': status.value,
                'strategy': 'tags',
                'channel': 'prerelease' if allow_pre else 'stable',
                'current_version': current,
                'remote_version': latest_tag,
                'current_commit': state['commit'],
                'remote_commit': remote_commit,
                'is_update_available': is_update,
                'available_tags': remote_tags[:10],
                'timestamp': _utc_now_iso(),
            }
        except Exception as ex:
            logger.error(f'Ошибка проверки обновлений: {ex}')
            return {'status': UpdateStatus.ERROR.value, 'message': str(ex)}

    def backup_files(self, files_to_backup: Optional[List[str]] = None) -> Optional[Path]:
        """Создаёт резервную копию конфигов и метаданных текущего состояния Git."""
        with self._lock:
            try:
                items = files_to_backup if files_to_backup is not None else self.backup_items
                stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
                backup_dir = self.temp_backup_dir / f'backup_{stamp}'
                backup_dir.mkdir(parents=True, exist_ok=True)
                copied: List[str] = []
                for rel_item in items:
                    src = self.repo_path / rel_item
                    if not src.exists():
                        continue
                    dst = backup_dir / rel_item
                    if src.is_dir():
                        shutil.copytree(src, dst, dirs_exist_ok=True)
                    else:
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src, dst)
                    copied.append(rel_item)

                state = self._get_git_state()
                backup_info = {
                    'timestamp': _utc_now_iso(),
                    'repo_path': str(self.repo_path),
                    'backed_up_files': copied,
                    'version': self.get_current_version() or state['commit'],
                    'previous_commit': state['commit'],
                    'previous_branch': state['branch'],
                    'previous_tag': state['tag'],
                }
                _atomic_write_json(backup_dir / '.backup_info.json', backup_info)
                logger.info(f'Резервная копия создана: {backup_dir}')
                return backup_dir
            except Exception as ex:
                logger.error(f'Ошибка создания резервной копии: {ex}')
                return None

    def restore_from_backup(self, backup_path: Path) -> bool:
        """Восстанавливает файлы конфигурации из указанной директории бэкапа."""
        with self._lock:
            try:
                if not backup_path.exists():
                    logger.error(f'Директория резервной копии не найдена: {backup_path}')
                    return False
                for item in backup_path.iterdir():
                    if item.name == '.backup_info.json' or item.name.endswith('.tmp'):
                        continue
                    dst = self.repo_path / item.name
                    if item.is_dir():
                        if dst.exists():
                            shutil.rmtree(dst)
                        shutil.copytree(item, dst, dirs_exist_ok=True)
                    else:
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(item, dst)
                return True
            except Exception as ex:
                logger.error(f'Ошибка восстановления из резервной копии: {ex}')
                return False

    def fetch_tags(self) -> Tuple[bool, str]:
        """Загружает все теги из удалённого репозитория."""
        rc, _, stderr = self._run_git_command(['git', 'fetch', self.remote_url, '--tags', '--force'])
        if rc != 0:
            logger.error(f'Ошибка загрузки тегов из {self.remote_url}: {stderr}')
            return (False, stderr)
        return (True, '')

    def checkout_tag(self, tag: str) -> Tuple[bool, str]:
        """Переключает локальную релизную ветку на указанный Git-тег."""
        if not is_valid_semver_tag(tag, prefix=self.tag_prefix):
            return (False, f'Некорректный формат SemVer-тега: {tag}')
        rc, _, stderr = self._run_git_command(['git', 'rev-parse', '-q', '--verify', f'refs/tags/{tag}'])
        if rc != 0:
            return (False, f'Тег {tag} не найден в локальном репозитории: {stderr}')
        rc, stdout, stderr = self._run_git_command(
            ['git', 'checkout', '-B', self.release_branch, f'refs/tags/{tag}']
        )
        if rc != 0:
            return (False, stderr or f'Не удалось переключиться на тег {tag}')
        return (True, stdout)

    def _install_dependencies_if_changed(self, old_ref: str, new_ref: str) -> Tuple[bool, str]:
        """Обновляет Python-зависимости, если `requirements.txt` изменился между версиями."""
        if not self.auto_install_deps:
            return (True, 'Автоустановка зависимостей отключена')
        req_file = self.repo_path / 'requirements.txt'
        if not req_file.exists():
            return (True, 'requirements.txt отсутствует')
        rc, diff_out, _ = self._run_git_command(['git', 'diff', '--name-only', old_ref, new_ref, '--', 'requirements.txt'])
        if rc != 0 or 'requirements.txt' not in diff_out:
            return (True, 'requirements.txt не изменился')
        logger.info('Обнаружены изменения в requirements.txt — выполняется установка зависимостей...')
        try:
            proc = subprocess.run(
                [sys.executable, '-m', 'pip', 'install', '-r', str(req_file), '--quiet'],
                cwd=str(self.repo_path),
                capture_output=True,
                text=True,
                timeout=300,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            )
            if proc.returncode != 0:
                return (False, proc.stderr.strip() or 'Ошибка pip install')
            return (True, 'Зависимости обновлены')
        except Exception as ex:
            return (False, str(ex))

    def _run_db_migrations(self) -> Dict[str, Any]:
        """Запускает миграции БД, если модуль MigrationManager доступен в проекте."""
        for module_path in ('src.db.migrations', 'src.db'):
            try:
                mod = __import__(module_path, fromlist=['get_migration_manager'])
                getter = getattr(mod, 'get_migration_manager', None)
                if callable(getter):
                    res = getter(self.repo_path).apply_all_pending()
                    return {'executed': True, 'result': res}
            except ImportError:
                continue
            except Exception as ex:
                logger.error(f'Ошибка применения миграций БД: {ex}')
                return {'executed': True, 'error': str(ex)}
        return {'executed': False, 'message': 'MigrationManager не установлен'}

    async def update_application(
        self,
        target_tag: Optional[str] = None,
        auto_backup: bool = True,
        allow_dirty: bool = False,
        allow_prerelease: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Выполняет полный цикл безопасного обновления до указанного или последнего тега."""
        with self._lock:
            try:
                if not allow_dirty:
                    clean, dirty_files = self.is_working_tree_clean()
                    if not clean:
                        return {
                            'success': False,
                            'status': UpdateStatus.ERROR.value,
                            'message': f'Рабочее дерево содержит незакоммиченные изменения:\n{dirty_files}',
                        }

                ok_fetch, fetch_err = self.fetch_tags()
                if not ok_fetch:
                    return {'success': False, 'status': UpdateStatus.ERROR.value, 'message': f'Ошибка git fetch: {fetch_err}'}

                state_before = self._get_git_state()
                from_version = self.get_current_version() or state_before['commit']
                chosen_tag = target_tag or self.get_remote_version(allow_prerelease=allow_prerelease)
                if not chosen_tag:
                    return {
                        'success': False,
                        'status': UpdateStatus.NO_RELEASES.value,
                        'message': 'В удалённом репозитории нет релизных SemVer-тегов',
                    }
                if not target_tag and state_before['tag'] == chosen_tag:
                    return {
                        'success': True,
                        'status': UpdateStatus.CURRENT.value,
                        'message': f'Уже установлена актуальная версия {chosen_tag}',
                        'version': chosen_tag,
                    }

                backup_path = self.backup_files() if auto_backup else None
                if auto_backup and not backup_path:
                    return {'success': False, 'status': UpdateStatus.ERROR.value, 'message': 'Не удалось создать резервную копию'}

                ok_co, co_msg = self.checkout_tag(chosen_tag)
                if not ok_co:
                    self._restore_git_state(state_before)
                    if backup_path:
                        self.restore_from_backup(backup_path)
                    return {'success': False, 'status': UpdateStatus.ERROR.value, 'message': co_msg}

                deps_ok, deps_msg = self._install_dependencies_if_changed(state_before['commit'], f'refs/tags/{chosen_tag}')
                if not deps_ok:
                    self._restore_git_state(state_before)
                    if backup_path:
                        self.restore_from_backup(backup_path)
                    return {'success': False, 'status': UpdateStatus.ERROR.value, 'message': f'Ошибка зависимостей: {deps_msg}'}

                mig_info = self._run_db_migrations()
                self.cleanup_old_backups(self.keep_backups)

                update_info = {
                    'timestamp': _utc_now_iso(),
                    'strategy': 'tags',
                    'from_version': from_version,
                    'to_version': chosen_tag,
                    'release_branch': self.release_branch,
                    'backup_path': str(backup_path) if backup_path else None,
                    'deps': deps_msg,
                    'migrations': mig_info,
                    'status': 'success',
                }
                log_file = self.update_log_dir / f"update_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
                _atomic_write_json(log_file, update_info)
                logger.info(f'Приложение обновлено по тегу: {from_version} -> {chosen_tag}')
                return {
                    'success': True,
                    'status': UpdateStatus.CURRENT.value,
                    'message': f'Обновление до {chosen_tag} выполнено успешно',
                    'from_version': from_version,
                    'version': chosen_tag,
                    'backup_path': str(backup_path) if backup_path else None,
                }
            except Exception as ex:
                logger.error(f'Критическая ошибка обновления приложения: {ex}')
                return {'success': False, 'status': UpdateStatus.ERROR.value, 'message': str(ex)}

    def _restore_git_state(self, state: Dict[str, str]) -> bool:
        """Возвращает Git в зафиксированное ранее состояние."""
        branch = state.get('branch', '')
        commit = state.get('commit', '')
        if branch and branch != 'HEAD':
            rc, _, _ = self._run_git_command(['git', 'checkout', '-B', branch, commit])
            return rc == 0
        if commit and commit != 'unknown':
            rc, _, _ = self._run_git_command(['git', 'checkout', '--detach', commit])
            return rc == 0
        return False

    def _get_latest_backup(self) -> Optional[Path]:
        """Возвращает путь к последней созданной резервной копии."""
        if not self.temp_backup_dir.exists():
            return None
        backups = sorted(
            [d for d in self.temp_backup_dir.iterdir() if d.is_dir() and (d / '.backup_info.json').exists()],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return backups[0] if backups else None

    def rollback(self, target_tag: Optional[str] = None, backup_path: Optional[Path] = None) -> Dict[str, Any]:
        """Откатывает приложение на указанный тег или на последнюю резервную копию."""
        with self._lock:
            if target_tag:
                ok_co, msg = self.checkout_tag(target_tag)
                if not ok_co:
                    return {'success': False, 'message': msg}
                return {'success': True, 'version': target_tag, 'message': f'Выполнен откат на тег {target_tag}'}

            bkp = backup_path or self._get_latest_backup()
            if not bkp or not (bkp / '.backup_info.json').exists():
                return {'success': False, 'message': 'Резервные копии для отката не найдены'}

            info = json.loads((bkp / '.backup_info.json').read_text(encoding='utf-8'))
            state = {
                'branch': info.get('previous_branch', self.release_branch),
                'commit': info.get('previous_commit', ''),
            }
            if not self._restore_git_state(state):
                return {'success': False, 'message': f"Не удалось восстановить Git-состояние {state['commit']}"}
            self.restore_from_backup(bkp)
            return {
                'success': True,
                'version': info.get('version', state['commit']),
                'backup_path': str(bkp),
                'message': f"Выполнен откат на {info.get('version', state['commit'])}",
            }

    def _sync_pyproject_version(self, tag: str) -> bool:
        """Синхронизирует поле `version` в `pyproject.toml` с новым релизным тегом."""
        pyproject = self.repo_path / 'pyproject.toml'
        if not pyproject.exists():
            return False
        clean_ver = tag[len(self.tag_prefix):] if self.tag_prefix and tag.startswith(self.tag_prefix) else tag
        text = pyproject.read_text(encoding='utf-8')
        new_text, count = re.subn(r'(?m)^version\s*=\s*"[^"]+"', f'version = "{clean_ver}"', text, count=1)
        if count > 0 and new_text != text:
            pyproject.write_text(new_text, encoding='utf-8')
            return True
        return False

    def create_release(
        self,
        tag: Optional[str] = None,
        bump: Optional[str] = None,
        message: Optional[str] = None,
        push: bool = False,
        prerelease: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Создаёт аннотированный SemVer-тег, обновляет `pyproject.toml` и при необходимости пушит тег."""
        with self._lock:
            existing_tags = self.list_local_tags(allow_prerelease=True)
            latest_local = existing_tags[0] if existing_tags else None
            if tag:
                new_tag = tag if tag.startswith(self.tag_prefix) else f'{self.tag_prefix}{tag}'
            else:
                new_tag = bump_version(latest_local, part=bump or 'patch', prefix=self.tag_prefix, prerelease=prerelease)

            if not is_valid_semver_tag(new_tag, prefix=self.tag_prefix):
                return {'success': False, 'message': f'Некорректный формат SemVer-тега: {new_tag}'}
            if new_tag in existing_tags:
                return {'success': False, 'message': f'Тег {new_tag} уже существует'}

            if self._sync_pyproject_version(new_tag):
                self._run_git_command(['git', 'add', 'pyproject.toml'])
                self._run_git_command(['git', 'commit', '-m', f'chore(release): {new_tag}'])

            log_range = f'{latest_local}..HEAD' if latest_local else 'HEAD'
            _, commits, _ = self._run_git_command(['git', 'log', log_range, '--oneline', '-n', '30'])
            tag_msg = message or f'Release {new_tag}\n\n{commits}'.strip()

            rc, _, stderr = self._run_git_command(['git', 'tag', '-a', new_tag, '-m', tag_msg])
            if rc != 0:
                return {'success': False, 'message': f'Не удалось создать тег {new_tag}: {stderr}'}

            pushed = False
            if push:
                rc_p, _, err_p = self._run_git_command(['git', 'push', self.remote_url, new_tag])
                if rc_p != 0:
                    return {'success': False, 'tag': new_tag, 'message': f'Тег создан локально, но ошибка push: {err_p}'}
                pushed = True

            logger.info(f'Создан релизный тег {new_tag} (pushed={pushed})')
            return {'success': True, 'tag': new_tag, 'previous_tag': latest_local, 'pushed': pushed, 'changelog': commits}

    def cleanup_old_backups(self, keep_count: Optional[int] = None) -> int:
        """Удаляет устаревшие резервные копии, сохраняя последние N копий."""
        keep = self.keep_backups if keep_count is None else keep_count
        with self._lock:
            if not self.temp_backup_dir.exists():
                return 0
            backups = sorted(
                [d for d in self.temp_backup_dir.iterdir() if d.is_dir()],
                key=lambda x: x.stat().st_mtime,
                reverse=True,
            )
            deleted = 0
            for backup in backups[keep:]:
                try:
                    shutil.rmtree(backup)
                    deleted += 1
                except Exception as ex:
                    logger.warning(f'Ошибка удаления резервной копии {backup.name}: {ex}')
            return deleted


version_manager: Optional[VersionManager] = None
_vm_lock = threading.RLock()


def get_version_manager(repo_path: Optional[Path] = None) -> VersionManager:
    """Возвращает глобальный экземпляр менеджера версий (потокобезопасный Singleton)."""
    global version_manager
    with _vm_lock:
        if version_manager is None:
            version_manager = VersionManager(repo_path)
        return version_manager
