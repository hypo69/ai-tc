# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Telemetry Optimization & On-the-fly Logs
# =============================================================================
# Description:
#   Тестирование переосмысленной логики телеметрии:
#   1. Отказ от хранения журналов событий Windows в базе данных телеметрии SQLite.
#   2. Чтение системных журналов на лету (on-the-fly) через WevtAPI в веб-интерфейсе.
#   3. Контроль размера БД и усечение устаревших данных.
#
# File: test_telemetry_refactor_and_logs.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-13 19:15:00
# =============================================================================

from __future__ import annotations

import gc
import os
import shutil
import tempfile
from pathlib import Path
import pytest

from apps.windows.telemetry.sqlite import TelemetryStorage
from apps.windows.telemetry.telemetry_config import TelemetryConfigManager
from apps.windows.api.routers.router_system_logs import get_events, scan_sources


@pytest.fixture
def temp_telemetry_storage():
    """Временное изолированное хранилище SQLite для проверки лимитов и очистки."""
    tmp_dir = tempfile.mkdtemp()
    db_path = Path(tmp_dir) / 'test_telemetry.db'
    storage = TelemetryStorage(db_path=db_path, buffer_mode='direct')
    try:
        yield storage
    finally:
        storage.close()
        del storage
        gc.collect()
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_log_collection_disabled_in_config():
    """Проверяет, что сбор журналов событий выключен в конфигурации телеметрии."""
    cfg_mgr = TelemetryConfigManager()
    cfg = cfg_mgr.get_config()

    # Журналы событий в w64_collector отключены
    w64_cfg = cfg.get('w64_collector', {})
    assert w64_cfg.get('enable_event_log_monitoring', False) is False

    # Security events отключены из тяжелых сборщиков
    heavy = cfg_mgr.get_heavy_collectors()
    assert heavy.get('security_events', False) is False


def test_maintenance_purge_and_limits(temp_telemetry_storage):
    """Проверяет усечение таблиц журналов и контроль лимита размера БД."""
    storage = temp_telemetry_storage

    # Эмулируем остаточные записи логов
    storage.save_security_events([
        {
            'event_id': 4624,
            'timestamp': '2026-10-13T12:00:00Z',
            'created_at': 1000.0,
            'channel': 'Security',
            'subject_user': 'SYSTEM',
        }
    ])
    assert len(storage.get_security_events()) == 1

    # Запускаем purge_log_tables
    stats = storage._maintenance.purge_log_tables(vacuum=False)
    assert stats.get('security_events', 0) >= 1
    assert len(storage.get_security_events()) == 0

    # Проверяем лимиты размера
    prune_res = storage.enforce_size_limit(max_size_mb=100.0)
    assert 'pruned' in prune_res


@pytest.mark.asyncio
async def test_web_interface_reads_logs_on_the_fly():
    """Проверяет, что веб-интерфейс считывает события напрямую из Windows Event Log."""
    if os.name != 'nt':
        pytest.skip('WevtAPI поддерживается только в Windows')

    # Сканирование источников каналов
    scan = await scan_sources(force=False)
    assert scan.get('total_sources', 0) > 0

    # Чтение событий на лету
    res = await get_events(channel='System', limit=5, hours=24)
    assert 'events' in res
    assert 'total' in res
    assert isinstance(res['events'], list)

