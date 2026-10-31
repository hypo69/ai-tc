# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry Tests - Change-Only Inventory
# =============================================================================
# Description:
#   TDD-тесты Change-Only хранения: DeltaInventory (службы, брандмауэр),
#   пропуск неизменившихся аудитов оборудования/автозапуска, восстановление
#   дельта-трекера из БД после рестарта и LOCF-якоря при очистке.
#
# Usage Examples:
#   pytest apps/windows/telemetry/tests/test_delta_inventory.py
#
# File: test_delta_inventory.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-14 02:15:00
# =============================================================================

from __future__ import annotations

"""Проверка, что в telemetry.db пишутся только дельты относительно прошлых значений."""

import gc
import shutil
import sqlite3
import tempfile
from pathlib import Path

import pytest

from apps.windows.telemetry.sqlite import TelemetryStorage
from apps.windows.telemetry.sqlite.delta_inventory import INVENTORY_SCHEMA_SQL, DeltaInventory
from apps.windows.telemetry.models import CpuMetrics, MemoryMetrics, SystemSnapshot


@pytest.fixture
def cursor():
    """Курсор in-memory БД со схемой инвентаризации."""
    conn = sqlite3.connect(':memory:')
    conn.executescript(INVENTORY_SCHEMA_SQL)
    yield conn.cursor()
    conn.close()


@pytest.fixture
def db_path():
    """Путь к временной БД телеметрии."""
    tmpdir = tempfile.mkdtemp()
    yield Path(tmpdir) / 'delta.db'
    gc.collect()
    shutil.rmtree(tmpdir, ignore_errors=True)


def _changes_count(cur: sqlite3.Cursor) -> int:
    return cur.execute('SELECT COUNT(*) FROM inventory_changes').fetchone()[0]


def test_first_sync_records_added_with_detection_date(cursor):
    """Первый опрос: все элементы фиксируются как 'added' с датой обнаружения."""
    stats = DeltaInventory.sync(cursor, 'svc', {'A': {'s': 1}, 'B': {'s': 2}}, detected_at='T1')
    assert stats == {'added': 2, 'removed': 0, 'modified': 0}
    active = DeltaInventory.get_active(cursor, 'svc')
    assert [a['first_seen'] for a in active] == ['T1', 'T1']


def test_unchanged_sync_writes_nothing(cursor):
    """Повторный опрос без изменений не пишет в БД ни одной строки."""
    DeltaInventory.sync(cursor, 'svc', {'A': {'s': 1}}, detected_at='T1')
    before = _changes_count(cursor)
    stats = DeltaInventory.sync(cursor, 'svc', {'A': {'s': 1}}, detected_at='T2')
    assert stats == {'added': 0, 'removed': 0, 'modified': 0}
    assert _changes_count(cursor) == before


def test_removed_and_modified_are_logged(cursor):
    """Исчезновение и изменение фиксируются с датой обнаружения."""
    DeltaInventory.sync(cursor, 'svc', {'A': {'s': 1}, 'B': {'s': 2}}, detected_at='T1')
    stats = DeltaInventory.sync(cursor, 'svc', {'A': {'s': 9}}, detected_at='T2')
    assert stats == {'added': 0, 'removed': 1, 'modified': 1}
    changes = {c['entity_key']: c for c in reversed(DeltaInventory.get_changes(cursor, 'svc'))}
    assert changes['B']['change_type'] == 'removed' and changes['B']['detected_at'] == 'T2'
    assert changes['A']['old'] == {'s': 1} and changes['A']['new'] == {'s': 9}
    assert [a['entity_key'] for a in DeltaInventory.get_active(cursor, 'svc')] == ['A']


def test_returned_entity_is_added_again(cursor):
    """Вернувшийся элемент снова фиксируется как 'added' с новой датой обнаружения."""
    DeltaInventory.sync(cursor, 'svc', {'A': {'s': 1}}, detected_at='T1')
    DeltaInventory.sync(cursor, 'svc', {}, detected_at='T2')
    stats = DeltaInventory.sync(cursor, 'svc', {'A': {'s': 1}}, detected_at='T3')
    assert stats['added'] == 1
    assert DeltaInventory.get_active(cursor, 'svc')[0]['first_seen'] == 'T3'


def test_services_snapshot_restart_writes_nothing(db_path):
    """Рестарт сервиса (новый экземпляр хранилища) с теми же службами не пишет дельт."""
    services = [{'name': 'Spooler', 'status': 'RUNNING'}, {'name': 'WinDefend', 'status': 'RUNNING'}]
    s1 = TelemetryStorage(db_path=db_path, buffer_mode='direct')
    assert s1.save_services_snapshot('run1', services) == 2
    s1.close()
    s2 = TelemetryStorage(db_path=db_path, buffer_mode='direct')
    assert s2.save_services_snapshot('run2', services) == 0
    assert len(s2.get_latest_services_list()) == 2
    assert s2.save_services_snapshot('run3', services[:1]) == 1
    assert s2.get_inventory_changes('services', limit=1)[0]['change_type'] == 'removed'
    s2.close()


def test_firewall_rule_state_update_is_delta(db_path):
    """Изменение состояния правила брандмауэра фиксируется как 'modified'."""
    s = TelemetryStorage(db_path=db_path, buffer_mode='direct')
    rules = [{'name': 'R1', 'direction': 'Inbound', 'enabled': True}]
    assert s.save_firewall_snapshot('fw1', {}, rules) == 2
    assert s.save_firewall_snapshot('fw2', {}, rules) == 0
    assert s.update_firewall_rule_state('R1', False) is True
    assert s.get_latest_firewall_rules()[0]['enabled'] == 0
    assert s.get_inventory_changes('firewall_rules', limit=1)[0]['change_type'] == 'modified'
    s.close()


def test_unchanged_hardware_and_startup_archives_are_skipped(db_path):
    """Аудиты без изменений (changes_count == 0) после базового снимка не пишутся."""
    s = TelemetryStorage(db_path=db_path, buffer_mode='direct')
    s.save_hardware_archive({'archive_id': 'h1', 'changes_count': 0, 'devices_count': 5})
    s.save_hardware_archive({'archive_id': 'h2', 'changes_count': 0, 'devices_count': 5})
    s.save_startup_archive({'archive_id': 'st1', 'changes_count': 0})
    s.save_startup_archive({'archive_id': 'st2', 'changes_count': 0})
    s.save_startup_archive({'archive_id': 'st3', 'changes_count': 1})
    assert [a['archive_id'] for a in s.get_hardware_audits()] == ['h1']
    assert sorted(a['archive_id'] for a in s.get_startup_archives()) == ['st1', 'st3']
    s.close()


def _snap(cpu: float) -> SystemSnapshot:
    return SystemSnapshot(
        hostname='HOST', username='u', os_name='Windows 11', os_build='26100', uptime_seconds=cpu,
        cpu=CpuMetrics(total_percent=cpu, frequency_mhz=3000.0),
        memory=MemoryMetrics(total_gb=32.0, used_gb=8.0, percent=25.0),
    )


def test_snapshot_static_fields_not_rewritten_after_restart(db_path):
    """После рестарта статические поля и raw_json не перезаписываются, метрики — пишутся."""
    s1 = TelemetryStorage(db_path=db_path, buffer_mode='direct')
    s1.save_snapshot(_snap(10.0))
    s1.save_snapshot(_snap(20.0))
    s1.close()
    s2 = TelemetryStorage(db_path=db_path, buffer_mode='direct')
    s2.save_snapshot(_snap(30.0))
    with s2.get_connection() as conn:
        rows = conn.execute('SELECT hostname, os_build, raw_json, cpu_total_percent FROM system_snapshots ORDER BY id').fetchall()
    assert rows[0]['hostname'] == 'HOST' and rows[0]['raw_json']
    for r in rows[1:]:
        assert r['hostname'] is None and r['os_build'] is None and r['raw_json'] is None
    assert [r['cpu_total_percent'] for r in rows] == [10.0, 20.0, 30.0]
    full = s2.get_latest_snapshot_full()
    assert full['hostname'] == 'HOST' and full['cpu']['total_percent'] == 30.0
    s2.close()


def test_cleanup_keeps_locf_anchors(db_path):
    """Очистка по сроку давности не удаляет строки с последними значениями статических полей."""
    s = TelemetryStorage(db_path=db_path, buffer_mode='direct')
    s.save_snapshot(_snap(10.0))
    s.save_snapshot(_snap(20.0))
    s.maintenance.cleanup_old_records(retention_days=0)
    full = s.get_latest_snapshot_full()
    assert full['hostname'] == 'HOST' and full['os_build'] == '26100'
    s.close()

