# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc TESTS - Startup Auto-Updater Tests
# =============================================================================
# Description:
#   Тесты автоматической проверки, установки обновлений по Git-тегам и
#   безопасного перезапуска при старте приложения (src.startup_updater).
#
# Usage Examples:
#   CLI:
#     pytest tests/test_startup_updater.py -v
#
# File: test_startup_updater.py
# Project: ai-tc
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-20 22:08:00
# =============================================================================

"""Тесты автоматического обновления при старте приложения."""

from pathlib import Path
from typing import Dict, List

import pytest

from src.startup_updater import SKIP_UPDATE_ENV_VAR, run_startup_update
from tests.test_version_manager_tags import _create_git_env, _git


def test_startup_update_skips_with_flag_or_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет пропуск автообновления по флагу skip и переменной окружения."""
    _, _, client = _create_git_env(tmp_path)

    res_flag = run_startup_update(repo_path=client, skip=True, backup_root=tmp_path / 'bkp')
    assert res_flag.checked is False
    assert res_flag.should_exit is False

    monkeypatch.setenv(SKIP_UPDATE_ENV_VAR, '1')
    res_env = run_startup_update(repo_path=client, skip=False, backup_root=tmp_path / 'bkp')
    assert res_env.checked is False
    assert res_env.should_exit is False


def test_startup_update_applies_new_tag_and_restarts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверяет автоустановку нового тега при старте и перезапуск с защитой от цикла."""
    monkeypatch.delenv(SKIP_UPDATE_ENV_VAR, raising=False)
    _, dev, client = _create_git_env(tmp_path)

    # Публикуем новый релиз v1.1.0 на remote
    (dev / 'app.txt').write_text('v1.1.0 auto content\n', encoding='utf-8')
    _git(dev, 'add', 'app.txt')
    _git(dev, 'commit', '-m', 'feat: release v1.1.0')
    _git(dev, 'tag', '-a', 'v1.1.0', '-m', 'Release v1.1.0')
    _git(dev, 'push', 'origin', 'master', '--tags')

    captured: Dict[str, object] = {}

    def _fake_restart(cmd: List[str], env: Dict[str, str]) -> int:
        captured['cmd'] = cmd
        captured['env'] = env
        return 0

    res = run_startup_update(
        repo_path=client,
        argv=['main.py', '--headless'],
        backup_root=tmp_path / 'bkp',
        restart_fn=_fake_restart,
    )

    assert res.checked is True
    assert res.updated is True
    assert res.should_exit is True
    assert res.exit_code == 0
    assert res.from_version == 'v1.0.0'
    assert res.to_version == 'v1.1.0'
    assert (client / 'app.txt').read_text(encoding='utf-8').strip() == 'v1.1.0 auto content'
    assert captured['env'][SKIP_UPDATE_ENV_VAR] == '1'
    assert captured['cmd'][-2:] == ['main.py', '--headless']


def test_startup_update_does_not_block_on_dirty_tree_or_no_updates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Проверяет, что грязное дерево или отсутствие обновлений не мешают запуску."""
    monkeypatch.delenv(SKIP_UPDATE_ENV_VAR, raising=False)
    _, dev, client = _create_git_env(tmp_path)

    # 1. Нет обновлений — обычный запуск
    res_current = run_startup_update(repo_path=client, backup_root=tmp_path / 'bkp')
    assert res_current.checked is True
    assert res_current.updated is False
    assert res_current.should_exit is False

    # 2. Есть обновление v1.1.0, но клиент имеет незакоммиченные изменения — не блокирует старт
    (dev / 'app.txt').write_text('v1.1.0 content\n', encoding='utf-8')
    _git(dev, 'add', 'app.txt')
    _git(dev, 'commit', '-m', 'feat: v1.1.0')
    _git(dev, 'tag', '-a', 'v1.1.0', '-m', 'Release v1.1.0')
    _git(dev, 'push', 'origin', 'master', '--tags')

    (client / 'app.txt').write_text('local uncommitted edit\n', encoding='utf-8')
    res_dirty = run_startup_update(repo_path=client, backup_root=tmp_path / 'bkp')
    assert res_dirty.checked is True
    assert res_dirty.updated is False
    assert res_dirty.should_exit is False
    assert 'незакоммиченных' in res_dirty.message.lower()
