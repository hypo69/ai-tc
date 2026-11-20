# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc TESTS - Tag-Based Version Manager Tests
# =============================================================================
# Description:
#   Юнит- и интеграционные тесты стратегии обновлений и релизов через Git-теги
#   (src.utils.versioning и src.version_manager.VersionManager).
#
# Usage Examples:
#   CLI:
#     pytest tests/test_version_manager_tags.py -v
#
# File: test_version_manager_tags.py
# Project: ai-tc
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20 21:15:00
# =============================================================================

"""Тесты стратегии обновлений и релизов через Git-теги (SemVer 2.0)."""

import asyncio
from pathlib import Path
import subprocess
from typing import Tuple

import pytest

from src.utils.versioning import (
    bump_version,
    choose_best_tag,
    compare_versions,
    is_prerelease_tag,
    is_valid_semver_tag,
    sort_tags,
)
from src.version_manager import UpdateStatus, VersionManager


def _git(cwd: Path, *args: str) -> str:
    """Выполняет git-команду в тестовом репозитории и проверяет код возврата."""
    proc = subprocess.run(
        ['git', *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding='utf-8',
        check=True,
    )
    return proc.stdout.strip()


def _create_git_env(tmp_path: Path) -> Tuple[Path, Path, Path]:
    """Создаёт bare remote, репозиторий разработчика (dev) и клиентский клон (client)."""
    remote = tmp_path / 'remote.git'
    dev = tmp_path / 'dev'
    client = tmp_path / 'client'

    remote.mkdir()
    _git(remote, 'init', '--bare')

    dev.mkdir()
    _git(dev, 'init', '-b', 'master')
    _git(dev, 'config', 'user.email', 'test@example.com')
    _git(dev, 'config', 'user.name', 'Test User')
    _git(dev, 'remote', 'add', 'origin', str(remote))

    (dev / 'app.txt').write_text('v1.0.0 content\n', encoding='utf-8')
    (dev / 'pyproject.toml').write_text('[project]\nname = "ai-tc"\nversion = "1.0.0"\n', encoding='utf-8')
    (dev / 'config.json').write_text('{"updates": {"channel": "stable", "auto_install_deps": false}}\n', encoding='utf-8')
    _git(dev, 'add', '.')
    _git(dev, 'commit', '-m', 'Initial commit')
    _git(dev, 'tag', '-a', 'v1.0.0', '-m', 'Release v1.0.0')
    _git(dev, 'push', 'origin', 'master', '--tags')

    _git(tmp_path, 'clone', str(remote), str(client))
    _git(client, 'config', 'user.email', 'client@example.com')
    _git(client, 'config', 'user.name', 'Client User')
    _git(client, 'checkout', '-B', 'release', 'refs/tags/v1.0.0')
    return remote, dev, client


def test_versioning_semver_helpers() -> None:
    """Проверяет валидацию, сортировку и инкремент SemVer-тегов."""
    assert is_valid_semver_tag('v1.0.0')
    assert is_valid_semver_tag('v2.3.4-rc.1')
    assert not is_valid_semver_tag('1.0.0')
    assert not is_valid_semver_tag('checkpoint-2026')

    assert is_prerelease_tag('v1.1.0-rc.1')
    assert not is_prerelease_tag('v1.1.0')

    tags = ['v1.0.0', 'v1.2.0-rc.1', 'v1.1.0', 'v1.0.2', 'not-a-tag']
    assert sort_tags(tags, allow_prerelease=False) == ['v1.1.0', 'v1.0.2', 'v1.0.0']
    assert sort_tags(tags, allow_prerelease=True) == ['v1.2.0-rc.1', 'v1.1.0', 'v1.0.2', 'v1.0.0']
    assert choose_best_tag(tags, allow_prerelease=False) == 'v1.1.0'
    assert compare_versions('v1.0.0', 'v1.1.0') == -1

    assert bump_version('v1.0.0', part='patch') == 'v1.0.1'
    assert bump_version('v1.0.1', part='minor') == 'v1.1.0'
    assert bump_version('v1.1.0', part='major') == 'v2.0.0'
    assert bump_version('v1.1.0', part='minor', prerelease='rc.1') == 'v1.2.0-rc.1'
    assert bump_version(None, part='patch') == 'v1.0.0'


def test_check_updates_ignores_master_checkpoints_and_respects_channel(tmp_path: Path) -> None:
    """Проверяет, что клиент игнорирует незатегированные коммиты в master и фильтрует prerelease."""
    _, dev, client = _create_git_env(tmp_path)
    vm = VersionManager(repo_path=client, backup_root=tmp_path / 'bkp')

    # 1. Изначально клиент на v1.0.0 — обновлений нет
    res = vm.check_updates()
    assert res['status'] == UpdateStatus.CURRENT.value
    assert res['is_update_available'] is False

    # 2. В master добавляется checkpoint-коммит без тега — клиент не должен видеть обновление
    (dev / 'app.txt').write_text('wip checkpoint\n', encoding='utf-8')
    _git(dev, 'add', 'app.txt')
    _git(dev, 'commit', '-m', 'checkpoint')
    _git(dev, 'push', 'origin', 'master')
    res_wip = vm.check_updates()
    assert res_wip['is_update_available'] is False

    # 3. Пушится prerelease тег v1.1.0-rc.1 — канал stable его игнорирует, prerelease видит
    _git(dev, 'tag', '-a', 'v1.1.0-rc.1', '-m', 'RC 1')
    _git(dev, 'push', 'origin', 'v1.1.0-rc.1')
    assert vm.check_updates(allow_prerelease=False)['is_update_available'] is False
    res_pre = vm.check_updates(allow_prerelease=True)
    assert res_pre['is_update_available'] is True
    assert res_pre['remote_version'] == 'v1.1.0-rc.1'


def test_update_and_rollback_by_tags(tmp_path: Path) -> None:
    """Проверяет полный цикл обновления на новый тег, защиту грязного дерева и откат."""
    _, dev, client = _create_git_env(tmp_path)
    vm = VersionManager(repo_path=client, backup_root=tmp_path / 'bkp')

    # Выпускаем релиз v1.1.0 в dev
    (dev / 'app.txt').write_text('v1.1.0 stable content\n', encoding='utf-8')
    _git(dev, 'add', 'app.txt')
    _git(dev, 'commit', '-m', 'feat: v1.1.0')
    _git(dev, 'tag', '-a', 'v1.1.0', '-m', 'Release v1.1.0')
    _git(dev, 'push', 'origin', 'master', '--tags')

    # Грязное рабочее дерево должно блокировать обновление
    (client / 'app.txt').write_text('dirty local edit\n', encoding='utf-8')
    blocked = asyncio.run(vm.update_application())
    assert blocked['success'] is False
    assert 'незакоммиченные' in blocked['message'].lower()
    _git(client, 'checkout', '--', 'app.txt')

    # Успешное обновление до v1.1.0
    updated = asyncio.run(vm.update_application())
    assert updated['success'] is True
    assert updated['version'] == 'v1.1.0'
    assert (client / 'app.txt').read_text(encoding='utf-8').strip() == 'v1.1.0 stable content'
    assert _git(client, 'rev-parse', '--abbrev-ref', 'HEAD') == 'release'
    assert vm.get_current_version() == 'v1.1.0'

    # Откат по последнему бэкапу возвращает v1.0.0
    rolled = vm.rollback()
    assert rolled['success'] is True
    assert vm.get_current_version() == 'v1.0.0'
    assert (client / 'app.txt').read_text(encoding='utf-8').strip() == 'v1.0.0 content'

    # Прямой откат/переход на указанный тег v1.1.0
    rolled_tag = vm.rollback(target_tag='v1.1.0')
    assert rolled_tag['success'] is True
    assert vm.get_current_version() == 'v1.1.0'


def test_create_release_bumps_and_syncs_pyproject(tmp_path: Path) -> None:
    """Проверяет создание аннотированного релиза, синхронизацию pyproject.toml и push тега."""
    _, dev, _ = _create_git_env(tmp_path)
    vm = VersionManager(repo_path=dev, backup_root=tmp_path / 'bkp')

    (dev / 'app.txt').write_text('new feature\n', encoding='utf-8')
    _git(dev, 'add', 'app.txt')
    _git(dev, 'commit', '-m', 'feat: add new feature')

    rel = vm.create_release(bump='minor', push=True)
    assert rel['success'] is True
    assert rel['tag'] == 'v1.1.0'
    assert rel['pushed'] is True
    assert 'version = "1.1.0"' in (dev / 'pyproject.toml').read_text(encoding='utf-8')
    assert 'v1.1.0' in vm.list_remote_tags()
