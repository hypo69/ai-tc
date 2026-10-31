# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry Tests - Delta & LOCF
# =============================================================================
# Description:
#   Модульные тесты TDD для проверки дельта-хранения телеметрии (только изменившиеся данные)
#   и алгоритма реконструкции верхних срезов LOCF (Last Observation Carried Forward).
#
# Usage Examples:
#   pytest apps/windows/telemetry/tests/test_delta_storage_and_locf.py
#
# File: test_delta_storage_and_locf.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 19:41:00
# =============================================================================

from __future__ import annotations
"""Тестирование сохранения только изменившихся параметров и LOCF-реконструкции срезов."""

import gc
import os
import sqlite3
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List
import pytest

from apps.windows.telemetry.sqlite import TelemetryStorage
from apps.windows.telemetry.models import (
    CpuMetrics,
    DiskIoMetrics,
    DiskPartitionMetrics,
    GpuMetrics,
    MemoryMetrics,
    NetworkInterfaceMetrics,
    ProcessMetrics,
    SystemSnapshot,
)


@pytest.fixture
def temp_db_storage():
    """Создает временный экземпляр TelemetryStorage в изолированной базе SQLite."""
    tmpdir = tempfile.mkdtemp()
    db_file = Path(tmpdir) / "test_delta_telemetry.db"
    storage = TelemetryStorage(db_path=db_file, buffer_mode="direct")
    try:
        yield storage
    finally:
        storage.close()
        del storage
        gc.collect()
        try:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass


def test_delta_snapshot_storage_and_locf_reconstruction(temp_db_storage: TelemetryStorage):
    """Проверяет сохранение дельт в БД и полное восстановление срезов через LOCF."""
    storage = temp_db_storage

    # Тик 1: Первичная полная фиксация состояния
    snap1 = SystemSnapshot(
        hostname="WORKSTATION-01",
        username="admin",
        os_name="Windows 11 Pro",
        os_build="26100.1742",
        uptime_seconds=100.0,
        cpu=CpuMetrics(total_percent=15.0, frequency_mhz=3600.0),
        memory=MemoryMetrics(total_gb=32.0, used_gb=12.0, percent=37.5),
        disk_io=DiskIoMetrics(read_bytes_per_sec=1024.0, write_bytes_per_sec=2048.0),
        disks=[DiskPartitionMetrics(device="C:", mountpoint="C:\\", total_gb=1000.0, used_gb=350.0, percent=35.0)],
        network=[NetworkInterfaceMetrics(name="Ethernet", bytes_sent_sec=5000.0, bytes_recv_sec=10000.0)],
        top_processes=[
            ProcessMetrics(pid=1000, name="explorer.exe", cpu_percent=2.5, memory_mb=250.0),
            ProcessMetrics(pid=2000, name="code.exe", cpu_percent=8.0, memory_mb=800.0),
        ],
    )
    storage.save_snapshot(snap1)

    # Проверяем в сырой БД: в первой строке записаны все параметры
    with storage.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT hostname, os_build, cpu_total_percent, memory_used_gb, disks_json FROM system_snapshots WHERE id = 1")
        row1 = cursor.fetchone()
        assert row1[0] == "WORKSTATION-01"
        assert row1[1] == "26100.1742"
        assert row1[2] == 15.0
        assert row1[3] == 12.0
        assert row1[4] is not None

    # Тик 2: Изменились только CPU и RAM. Статические поля (hostname, os_build, disks) не изменились.
    snap2 = SystemSnapshot(
        hostname="WORKSTATION-01",
        username="admin",
        os_name="Windows 11 Pro",
        os_build="26100.1742",
        uptime_seconds=101.0,
        cpu=CpuMetrics(total_percent=25.0, frequency_mhz=3600.0),
        memory=MemoryMetrics(total_gb=32.0, used_gb=12.5, percent=39.0),
        disk_io=DiskIoMetrics(read_bytes_per_sec=1024.0, write_bytes_per_sec=2048.0),
        disks=[DiskPartitionMetrics(device="C:", mountpoint="C:\\", total_gb=1000.0, used_gb=350.0, percent=35.0)],
        network=[NetworkInterfaceMetrics(name="Ethernet", bytes_sent_sec=5000.0, bytes_recv_sec=10000.0)],
    )
    storage.save_snapshot(snap2)

    # В сырой БД во второй строке неизменившиеся поля должны быть NULL (дельта)
    with storage.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT hostname, os_build, cpu_total_percent, memory_used_gb, disks_json FROM system_snapshots WHERE id = 2")
        row2 = cursor.fetchone()
        assert row2[0] is None or row2[0] == ""  # hostname не дублируется
        assert row2[1] is None or row2[1] == ""  # os_build не дублируется
        assert row2[2] == 25.0                    # изменившийся CPU записан
        assert row2[3] == 12.5                    # изменившаяся память записана
        assert row2[4] is None                   # disks_json не дублируется в сырой строке

    # ТЕПЕРЬ ПРОВЕРЯЕМ ЧТЕНИЕ СРЕЗА ЧЕРЕЗ API / READER (LOCF-РЕКОНСТРУКЦИЯ)
    # Запрос последнего среза должен вернуть ВСЕ параметры, подтянув недостающие из тика 1!
    full_latest = storage.reader.get_latest_snapshot_full()
    assert full_latest is not None
    assert full_latest["hostname"] == "WORKSTATION-01"
    assert full_latest["os_build"] == "26100.1742"
    assert full_latest["cpu"]["total_percent"] == 25.0
    assert full_latest["memory"]["used_gb"] == 12.5
    assert full_latest["memory"]["total_gb"] == 32.0
    assert len(full_latest["disks"]) == 1
    assert full_latest["disks"][0]["device"] == "C:"
    assert full_latest["disk_io"]["read_bytes_per_sec"] == 1024.0


def test_locf_history_reconstruction(temp_db_storage: TelemetryStorage):
    """Проверяет восстановление временного ряда срезов через LOCF."""
    storage = temp_db_storage

    # Создаем серию тиков с изменениями отдельных метрик
    base_snap = SystemSnapshot(
        hostname="SERVER-PROD",
        username="svc_admin",
        cpu=CpuMetrics(total_percent=10.0, frequency_mhz=3000.0),
        memory=MemoryMetrics(total_gb=64.0, used_gb=20.0, percent=31.25),
        disk_io=DiskIoMetrics(read_bytes_per_sec=500.0, write_bytes_per_sec=500.0),
    )
    storage.save_snapshot(base_snap)

    # Тик 2: изменилась только нагрузка на CPU
    snap_t2 = SystemSnapshot(
        hostname="SERVER-PROD",
        username="svc_admin",
        cpu=CpuMetrics(total_percent=45.0, frequency_mhz=3000.0),
        memory=MemoryMetrics(total_gb=64.0, used_gb=20.0, percent=31.25),
        disk_io=DiskIoMetrics(read_bytes_per_sec=500.0, write_bytes_per_sec=500.0),
    )
    storage.save_snapshot(snap_t2)

    # Тик 3: изменилась только нагрузка на диск
    snap_t3 = SystemSnapshot(
        hostname="SERVER-PROD",
        username="svc_admin",
        cpu=CpuMetrics(total_percent=45.0, frequency_mhz=3000.0),
        memory=MemoryMetrics(total_gb=64.0, used_gb=20.0, percent=31.25),
        disk_io=DiskIoMetrics(read_bytes_per_sec=8000.0, write_bytes_per_sec=12000.0),
    )
    storage.save_snapshot(snap_t3)

    # Читаем историю срезов: каждый исторический срез должен быть полным
    snapshots = storage.reader.get_snapshots(limit=10)
    assert len(snapshots) == 3

    # Проверяем последний срез (t3)
    s3 = snapshots[0]  # ORDER BY id DESC -> s3 первый
    assert s3["cpu_total_percent"] == 45.0
    assert s3["disk_read_bytes_sec"] == 8000.0
    assert s3["hostname"] == "SERVER-PROD"
    assert s3["memory_total_gb"] == 64.0
    assert s3["memory_used_gb"] == 20.0

    # Проверяем срез t2
    s2 = snapshots[1]
    assert s2["cpu_total_percent"] == 45.0
    assert s2["disk_read_bytes_sec"] == 500.0
    assert s2["hostname"] == "SERVER-PROD"
    assert s2["memory_total_gb"] == 64.0


def test_get_latest_cpu_and_storage_locf(temp_db_storage: TelemetryStorage):
    """Проверяет точечные методы чтения (latest cpu, latest storage) при дельта-записи."""
    storage = temp_db_storage

    # Тик 1: полный снимок с дисками и CPU
    snap1 = SystemSnapshot(
        hostname="WORKSTATION-LOCF",
        cpu=CpuMetrics(total_percent=12.0, frequency_mhz=3200.0),
        disks=[DiskPartitionMetrics(device="D:", mountpoint="D:\\", total_gb=500.0, used_gb=200.0, percent=40.0)],
    )
    storage.save_snapshot(snap1)

    # Тик 2: изменился только CPU (диски опущены / не менялись)
    snap2 = SystemSnapshot(
        hostname="WORKSTATION-LOCF",
        cpu=CpuMetrics(total_percent=88.0, frequency_mhz=4200.0),
    )
    storage.save_snapshot(snap2)

    # Latest CPU должен вернуть актуальные значения из тика 2
    cpu_latest = storage.reader.get_latest_cpu()
    assert cpu_latest is not None
    assert cpu_latest["cpu_total_percent"] == 88.0
    assert cpu_latest["cpu_frequency_mhz"] == 4200.0

    # Latest Storage должен подтянуть неизменившуюся конфигурацию дисков из тика 1!
    storage_data = storage.reader.get_latest_storage_data()
    assert storage_data is not None
    assert len(storage_data["partitions"]) == 1
    assert storage_data["partitions"][0]["device"] == "D:"
    assert storage_data["partitions"][0]["total_gb"] == 500.0


def test_delta_tracker_unit_logic():
    """Тестирует непосредственно компонент DeltaStateTracker и LocfReconstructor."""
    from apps.windows.telemetry.sqlite.delta_tracker import DeltaStateTracker, LocfReconstructor

    tracker = DeltaStateTracker()

    # Проверка сенсоров: первый замер сохраняется, повторный одинаковый фильтруется
    assert tracker.filter_sensor_poll("sensor_cpu_temp", 45.0) is True
    assert tracker.filter_sensor_poll("sensor_cpu_temp", 45.0) is False  # без изменений
    assert tracker.filter_sensor_poll("sensor_cpu_temp", 47.5) is True   # изменилось

    # Проверка app_polls
    assert tracker.filter_app_poll("network_monitor", "active_sockets", 10, "ok") is True
    assert tracker.filter_app_poll("network_monitor", "active_sockets", 10, "ok") is False
    assert tracker.filter_app_poll("network_monitor", "active_sockets", 15, "ok") is True
    assert tracker.filter_app_poll("network_monitor", "active_sockets", 15, "warning") is True


def test_memory_buffering_with_5s_batch_flush():
    """Проверяет накопление тиков в RAM и пакетный сброс (flush раз в 5с) с дельта-записью."""
    import tempfile
    import gc
    import shutil

    tmpdir = tempfile.mkdtemp()
    db_file = Path(tmpdir) / "test_buffered_delta.db"

    # Буферный режим в памяти с таймером 5.0с
    storage = TelemetryStorage(
        db_path=db_file,
        buffer_mode="memory",
        buffer_size=100,
        flush_interval_seconds=5.0,
        auto_flush=False,  # управляем flush вручную в тесте
    )

    try:
        # Накапливаем 5 тиков за 5 секунд в оперативной памяти
        for tick in range(1, 6):
            snap = SystemSnapshot(
                hostname="SRV-BUFFERED",
                os_name="Windows Server 2025",
                cpu=CpuMetrics(total_percent=10.0 + tick * 2.0, frequency_mhz=3000.0),
                memory=MemoryMetrics(total_gb=128.0, used_gb=30.0 + tick * 0.5, percent=25.0),
                disks=[DiskPartitionMetrics(device="C:", mountpoint="C:\\", total_gb=2000.0, used_gb=500.0, percent=25.0)],
            )
            storage.save_snapshot(snap)

        # До сброса в БД: все 5 записей находятся в оперативной памяти
        assert storage.get_buffered_count() == 5

        # Выполняем 5-секундный пакетный сброс (flush)
        flushed = storage.flush()
        assert flushed == 5
        assert storage.get_buffered_count() == 0

        # Проверяем сырые строки в SQLite: тик 1 сохранил статические поля, тики 2..5 сохранили только дельты
        with storage.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, hostname, os_name, cpu_total_percent, memory_used_gb, disks_json FROM system_snapshots ORDER BY id ASC")
            rows = cursor.fetchall()
            assert len(rows) == 5

            # Тик 1: полный
            assert rows[0][1] == "SRV-BUFFERED"
            assert rows[0][2] == "Windows Server 2025"
            assert rows[0][3] == 12.0
            assert rows[0][5] is not None

            # Тик 2..5: дельты (неизменившиеся поля = NULL)
            for i in range(1, 5):
                assert rows[i][1] is None or rows[i][1] == ""  # hostname = NULL
                assert rows[i][2] is None or rows[i][2] == ""  # os_name = NULL
                assert rows[i][3] == 10.0 + (i + 1) * 2.0      # изменившийся CPU
                assert rows[i][5] is None                      # disks_json = NULL

        # Проверяем LOCF-реконструкцию: при чтении все 5 срезов восстанавливаются со 100% полнотой
        all_snapshots = storage.reader.get_snapshots(limit=10)
        assert len(all_snapshots) == 5
        for s in all_snapshots:
            assert s["hostname"] == "SRV-BUFFERED"
            assert s["os_name"] == "Windows Server 2025"
            assert s["memory_total_gb"] == 128.0
            assert s["disks_json"] is not None

    finally:
        storage.close()
        del storage
        gc.collect()
        shutil.rmtree(tmpdir, ignore_errors=True)



