# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry Sqlite - Schema Core
# =============================================================================
# Description:
#   DDL-определения базового ядра телеметрии (5 из 12 таблиц):
#   system_snapshots, sensor_polls, telemetry_rollups, process_snapshots,
#   process_file_events.
#
# File: schema_core.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry.sqlite
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-16 12:55:00
# =============================================================================

from __future__ import annotations

"""DDL-определения базового ядра телеметрии (срезы системы, сенсоры, агрегаты и процессы)."""

from typing import Tuple

CORE_SCHEMA_DDL: Tuple[str, ...] = (
    # 1. Снимки телеметрии хоста, ОС, CPU, RAM, GPU, Дисков и Сети
    '''
    CREATE TABLE IF NOT EXISTS system_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        created_at REAL NOT NULL,
        hostname TEXT,
        username TEXT,
        uptime_seconds REAL,
        os_name TEXT,
        os_build TEXT,
        os_install_date TEXT,
        system_language TEXT,
        os_install_language TEXT,
        user_locale TEXT,
        system_locale TEXT,
        timezone TEXT,
        codepage TEXT,
        input_languages_json TEXT,
        disks_json TEXT,
        physical_disks_json TEXT,
        monitors_json TEXT,
        updates_json TEXT,
        office_json TEXT,
        onedrive_json TEXT,
        battery_json TEXT,
        ram_sticks_json TEXT,
        listening_ports_json TEXT,
        alerts_json TEXT,
        cpu_total_percent REAL,
        cpu_frequency_mhz REAL,
        cpu_temp_c REAL,
        cpu_power_w REAL,
        memory_total_gb REAL,
        memory_used_gb REAL,
        memory_percent REAL,
        swap_percent REAL,
        gpu_load_percent REAL,
        gpu_temp_c REAL,
        gpu_vram_used_mb REAL,
        disk_read_bytes_sec REAL,
        disk_write_bytes_sec REAL,
        disk_read_count_sec REAL,
        disk_write_count_sec REAL,
        network_sent_bytes_sec REAL,
        network_recv_bytes_sec REAL,
        throttling_json TEXT,
        vss_snapshots_count INTEGER DEFAULT 0,
        hardware_audit TEXT,
        raw_json TEXT
    );
    ''',
    # 2. Универсальная таблица опросов аппаратных сенсоров, ACPI зон и SMART
    '''
    CREATE TABLE IF NOT EXISTS sensor_polls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sensor_id TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        created_at REAL NOT NULL,
        hardware_name TEXT,
        hardware_type TEXT,
        sensor_category TEXT,
        sensor_type TEXT,
        sensor_name TEXT,
        value REAL,
        value_numeric REAL,
        min_val REAL,
        max_val REAL,
        unit TEXT,
        status TEXT DEFAULT 'OK',
        raw_json TEXT
    );
    ''',
    # 3. Единая таблица агрегированных рядов телеметрии и профилей сессий Live Stream
    '''
    CREATE TABLE IF NOT EXISTS telemetry_rollups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tier TEXT NOT NULL,
        sensor_id TEXT NOT NULL DEFAULT '__system__',
        bucket_start REAL NOT NULL DEFAULT 0.0,
        bucket_end REAL,
        period_start TEXT,
        period_end TEXT,
        period_start_epoch REAL,
        period_end_epoch REAL,
        hardware_type TEXT,
        sensor_category TEXT,
        sensor_name TEXT,
        unit TEXT,
        sample_count INTEGER DEFAULT 1,
        value_min REAL,
        value_max REAL,
        value_avg REAL,
        value_sum REAL,
        value_sum_sq REAL,
        value_stddev REAL,
        value_first REAL,
        value_last REAL,
        min_val REAL,
        max_val REAL,
        avg_val REAL,
        p95_val REAL,
        sum_val REAL,
        last_val REAL,
        cpu_avg REAL,
        cpu_max REAL,
        cpu_p95 REAL,
        ram_avg REAL,
        ram_max REAL,
        ram_used_gb_avg REAL,
        disk_read_bps_avg REAL,
        disk_write_bps_avg REAL,
        disk_read_bps_max REAL,
        disk_write_bps_max REAL,
        net_sent_bps_avg REAL,
        net_recv_bps_avg REAL,
        gpu_load_avg REAL,
        gpu_temp_max REAL,
        session_id TEXT,
        payload_json TEXT,
        created_at REAL NOT NULL DEFAULT 0.0,
        UNIQUE(tier, sensor_id, bucket_start)
    );
    ''',
    # 6. Единая таблица снимков, аудита, утечек и сетевой активности процессов
    '''
    CREATE TABLE IF NOT EXISTS process_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        snapshot_id INTEGER,
        sample_type TEXT NOT NULL DEFAULT 'snapshot',
        instance_id TEXT,
        timestamp TEXT NOT NULL,
        created_at REAL,
        pid INTEGER NOT NULL,
        name TEXT NOT NULL,
        status TEXT,
        cpu_percent REAL,
        memory_mb REAL,
        memory_percent REAL,
        working_set_mb REAL,
        private_mb REAL,
        peak_working_set_mb REAL,
        commit_size_mb REAL,
        page_faults INTEGER,
        num_threads INTEGER,
        num_handles INTEGER,
        gdi_objects INTEGER DEFAULT 0,
        user_objects INTEGER DEFAULT 0,
        username TEXT,
        read_bytes_sec REAL,
        write_bytes_sec REAL,
        read_bytes INTEGER,
        write_bytes INTEGER,
        read_operations INTEGER,
        write_operations INTEGER,
        integrity_level TEXT,
        elevation INTEGER,
        ppid INTEGER,
        parent_name TEXT,
        executable TEXT,
        cmdline TEXT,
        sid TEXT,
        session_id INTEGER,
        creation_time REAL,
        exit_time REAL,
        is_alive INTEGER DEFAULT 1,
        process_guid TEXT,
        ancestor_chain TEXT,
        launch_reason TEXT,
        user_time_sec REAL,
        kernel_time_sec REAL,
        total_cpu_time_sec REAL,
        total_context_switches INTEGER,
        cpu_cycles INTEGER,
        open_files_count INTEGER DEFAULT 0,
        tcp_connections_count INTEGER DEFAULT 0,
        udp_sockets_count INTEGER DEFAULT 0,
        sockets_json TEXT,
        open_files_json TEXT,
        leak_risk_score TEXT,
        is_outlier INTEGER DEFAULT 0,
        raw_json TEXT,
        FOREIGN KEY (snapshot_id) REFERENCES system_snapshots (id) ON DELETE CASCADE
    );
    ''',
    # 8. События файловой и дисковой активности процессов
    '''
    CREATE TABLE IF NOT EXISTS process_file_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        instance_id INTEGER,
        pid INTEGER NOT NULL DEFAULT 0,
        process_name TEXT,
        timestamp TEXT NOT NULL,
        created_at REAL NOT NULL,
        operation_type TEXT NOT NULL,
        file_path TEXT NOT NULL,
        target_directory TEXT,
        bytes_transferred INTEGER DEFAULT 0,
        io_rate_bytes_sec REAL DEFAULT 0.0,
        details_json TEXT
    );
    ''',
)

CORE_INDEX_DDL: Tuple[str, ...] = (
    'CREATE INDEX IF NOT EXISTS idx_snapshots_created ON system_snapshots(created_at DESC);',
    'CREATE INDEX IF NOT EXISTS idx_snapshots_ts ON system_snapshots(timestamp DESC);',
    'CREATE INDEX IF NOT EXISTS idx_sensors_id_created ON sensor_polls(sensor_id, created_at DESC);',
    'CREATE INDEX IF NOT EXISTS idx_sensors_category ON sensor_polls(sensor_category, created_at DESC);',
    'CREATE INDEX IF NOT EXISTS idx_sensors_hw_type ON sensor_polls(hardware_type, created_at DESC);',
    'CREATE INDEX IF NOT EXISTS idx_rollups_tier_bucket ON telemetry_rollups(tier, bucket_start DESC);',
    'CREATE INDEX IF NOT EXISTS idx_rollups_tier_epoch ON telemetry_rollups(tier, period_start_epoch DESC);',
    'CREATE INDEX IF NOT EXISTS idx_rollups_session ON telemetry_rollups(session_id) WHERE session_id IS NOT NULL;',
    'CREATE INDEX IF NOT EXISTS idx_proc_snap_id ON process_snapshots(snapshot_id);',
    'CREATE INDEX IF NOT EXISTS idx_proc_pid_ts ON process_snapshots(pid, timestamp DESC);',
    'CREATE INDEX IF NOT EXISTS idx_proc_name_ts ON process_snapshots(name, timestamp DESC);',
    'CREATE INDEX IF NOT EXISTS idx_proc_type_created ON process_snapshots(sample_type, created_at DESC);',
    'CREATE INDEX IF NOT EXISTS idx_pfe_pid_time ON process_file_events(pid, created_at DESC);',
    'CREATE INDEX IF NOT EXISTS idx_pfe_dir_time ON process_file_events(target_directory, created_at DESC);',
)

