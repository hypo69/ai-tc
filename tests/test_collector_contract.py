# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - SystemCollector Characterization
# =============================================================================
# Description:
#   Характеризационные тесты публичного контракта SystemCollector.
#   Фиксируют типы и инварианты результатов перед декомпозицией коллектора
#   (этап 4 ТЗ оптимизации). Не привязаны к конкретным значениям системы.
#
# File: test_collector_contract.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-11 10:48:15
# =============================================================================

from __future__ import annotations

import pytest

from apps.windows.telemetry.collector import SystemCollector
from apps.windows.telemetry.network_activity import NetworkActivityCollector
from apps.windows.telemetry.process_metrics import ProcessMetricsCollector
from apps.windows.telemetry.models import (
    BatteryMetrics,
    DiskIoMetrics,
    DiskPartitionMetrics,
    MemoryMetrics,
    NetworkInterfaceMetrics,
    NetworkPortMetrics,
    ProcessNetworkActivity,
    SystemHealthAlerts,
    SystemSnapshot,
)


@pytest.fixture(scope='module')
def collector() -> SystemCollector:
    """Единый коллектор на модуль."""
    return SystemCollector()


@pytest.mark.parametrize(
    'parent, session, cmdline, expected',
    [
        ('services.exe', None, None, 'service'),
        ('svchost.exe', 0, None, 'service'),
        ('svchost.exe', 1, None, 'spawned_by_svchost'),
        ('taskhostw.exe', None, None, 'scheduled_task'),
        ('foo.exe', None, 'x.exe -Task run', 'scheduled_task'),
        ('explorer.exe', 1, None, 'shell_interactive'),
        ('powershell.exe', 1, None, 'terminal_cli'),
        ('code.exe', 1, None, 'ide_developer'),
        ('wininit.exe', 0, None, 'system_boot'),
        ('MyApp.EXE', 1, None, 'spawned_by_myapp'),
        (None, None, None, 'unknown'),
    ],
)
def test_classify_launch_reason(parent: str | None, session: int | None, cmdline: str | None, expected: str) -> None:
    """Классификация причины запуска по родителю, сессии и командной строке."""
    assert ProcessMetricsCollector._classify_launch_reason(parent, 'child.exe', session, cmdline) == expected


def test_classify_traffic_returns_triple() -> None:
    """Классификатор трафика всегда возвращает три непустые строки."""
    for args in [('python.exe', 8000, 'TCP', 'LISTEN', False),
                 ('chrome.exe', 443, 'TCP', 'ESTABLISHED', True),
                 ('unknown.exe', 12345, 'UDP', 'ESTABLISHED', True)]:
        result = NetworkActivityCollector._classify_traffic(*args)
        assert len(result) == 3 and all(isinstance(x, str) and x for x in result)


def test_memory_metrics(collector: SystemCollector) -> None:
    """Память: корректный тип, используемая не превышает общую."""
    mem = collector.get_memory_metrics()
    assert isinstance(mem, MemoryMetrics)
    assert mem.total_gb > 0
    assert 0 <= mem.used_gb <= mem.total_gb + 0.01


def test_disk_metrics(collector: SystemCollector) -> None:
    """Диски: список разделов и метрики ввода-вывода."""
    partitions, io = collector.get_disk_metrics()
    assert partitions and all(isinstance(p, DiskPartitionMetrics) for p in partitions)
    assert isinstance(io, DiskIoMetrics)
    assert io.read_bytes_per_sec >= 0 and io.write_bytes_per_sec >= 0


def test_network_metrics(collector: SystemCollector) -> None:
    """Сеть: интерфейсы с неотрицательными скоростями."""
    nets = collector.get_network_metrics()
    assert all(isinstance(n, NetworkInterfaceMetrics) for n in nets)
    assert all(n.bytes_sent_per_sec >= 0 and n.bytes_recv_per_sec >= 0 for n in nets)


def test_battery_metrics(collector: SystemCollector) -> None:
    """Батарея: при наличии процент в диапазоне 0..100."""
    batt = collector.get_battery_metrics()
    assert isinstance(batt, BatteryMetrics)
    if batt.has_battery and batt.percent is not None:
        assert 0 <= batt.percent <= 100


def test_health_alerts(collector: SystemCollector) -> None:
    """Оповещения: корректный тип и неотрицательный счётчик."""
    alerts = collector.get_health_alerts()
    assert isinstance(alerts, SystemHealthAlerts)
    assert alerts.critical_events_count >= 0


def test_listening_ports_limit(collector: SystemCollector) -> None:
    """Слушающие порты: лимит соблюдается, порты в допустимом диапазоне."""
    ports = collector.get_listening_ports(limit=5)
    assert len(ports) <= 5
    assert all(isinstance(p, NetworkPortMetrics) and 0 < p.port < 65536 for p in ports)


def test_process_network_activity_limit(collector: SystemCollector) -> None:
    """Сетевая активность процессов: лимит соблюдается."""
    acts = collector.get_process_network_activity(limit=5)
    assert len(acts) <= 5
    assert all(isinstance(a, ProcessNetworkActivity) for a in acts)


def test_system_identity_keys(collector: SystemCollector) -> None:
    """Идентичность системы содержит ключи, на которые опирается снапшот."""
    ident = collector.get_system_identity()
    assert ident.get('hostname')
    assert 'username' in ident and 'user_locale' in ident


@pytest.mark.slow
async def test_live_snapshot_contract(collector: SystemCollector) -> None:
    """Живой снапшот собирается и содержит ключевые разделы."""
    snap = await collector.get_snapshot(process_limit=10, force_live=True)
    assert isinstance(snap, SystemSnapshot)
    assert snap.hostname
    assert snap.uptime_seconds > 0
    assert snap.cpu is not None and snap.memory.total_gb > 0
    assert 0 < len(snap.top_processes) <= 10
    assert snap.disks and snap.gpus


async def test_hardware_tree_built_and_cached(collector: SystemCollector) -> None:
    """Дерево компонентов строится через HardwareTreeBuilder, содержит ключевые категории и кэшируется."""
    nodes = await collector.get_hardware_tree_async(force=True)
    categories = {n.category for n in nodes}
    assert {'System', 'Windows Updates'} <= categories
    assert nodes[0].category == 'System' and nodes[0].properties.get('Компьютер (Host)')
    cached = await collector.get_hardware_tree_async()
    assert cached is nodes

def test_software_info_contract(collector: SystemCollector) -> None:
    """Сведения о ПО возвращают корректные модели; Windows Update и Office кэшируются."""
    from apps.windows.telemetry.models import CloudStorageInfo, OfficeSuiteInfo, WindowsUpdateInfo

    updates = collector.get_updates_info()
    assert isinstance(updates, WindowsUpdateInfo)
    assert collector.get_updates_info() is updates
    office = collector.get_ms_office_info()
    assert isinstance(office, OfficeSuiteInfo)
    assert collector.get_ms_office_info() is office
    assert isinstance(collector.get_onedrive_info(), CloudStorageInfo)

def test_history_mixin_methods_present_and_read_only_calls_work(collector: SystemCollector) -> None:
    """Методы истории доступны через SystemCollector (миксин); чтения из хранилища возвращают списки."""
    from apps.windows.telemetry.history_mixin import TelemetryHistoryMixin

    assert isinstance(collector, TelemetryHistoryMixin)
    for name in ('get_hardware_audit', 'archive_hardware_state', 'get_startup_audit', 'get_process_lineage',
                 'get_reboot_report', 'get_extended_system_audit', 'get_process_provenance_history'):
        assert callable(getattr(collector, name))
    assert isinstance(collector.get_snapshots(limit=3), list)
    assert isinstance(collector.get_hardware_history(limit=3), list)
    assert isinstance(collector.get_startup_history(limit=3), list)
    assert isinstance(collector.get_hardware_changes(limit=3), list)

