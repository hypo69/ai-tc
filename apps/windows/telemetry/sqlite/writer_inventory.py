# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry Sqlite - TelemetryInventoryWriterMixin
# =============================================================================
# Description:
#   Миксин записи инвентаризации и сэмплов оборудования (CPU, RAM, GPU, Диски,
#   Тома, Сеть, PnP-устройства, компоненты) в консолидированные таблицы:
#   hardware_components, hardware_component_history, sensor_polls,
#   process_file_events и incidents.
#
# File: writer_inventory.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry.sqlite
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-20 20:40:00
# =============================================================================

from __future__ import annotations

"""Миксин записи инвентаризации и сэмплов оборудования в консолидированные таблицы SQLite."""

import json
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _upsert_hw_component_row(
    cursor: sqlite3.Cursor,
    category: str,
    component_key: str,
    name: str,
    vendor: str = "",
    model: str = "",
    serial_number: str = "",
    status: str = "OK",
    health_status: str = "Healthy",
    temperature_c: Any = None,
    capacity_bytes: int = 0,
    free_bytes: int = 0,
    specs: Optional[Dict[str, Any]] = None,
) -> int:
    """Универсальный UPSERT компонента оборудования в таблицу hardware_components."""
    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()
    now_epoch = now_dt.timestamp()
    specs_dict = specs or {}
    specs_json = json.dumps(specs_dict, ensure_ascii=False, default=str)

    cursor.execute(
        '''
        INSERT INTO hardware_components (
            category, component_key, name, vendor, model, serial_number,
            status, health_status, temperature_c, capacity_bytes, free_bytes,
            first_seen, last_seen, updated_at, specs_json, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(category, component_key) DO UPDATE SET
            name = excluded.name,
            vendor = excluded.vendor,
            model = excluded.model,
            serial_number = COALESCE(NULLIF(excluded.serial_number, ''), hardware_components.serial_number),
            status = excluded.status,
            health_status = excluded.health_status,
            temperature_c = COALESCE(excluded.temperature_c, hardware_components.temperature_c),
            capacity_bytes = CASE WHEN excluded.capacity_bytes > 0 THEN excluded.capacity_bytes ELSE hardware_components.capacity_bytes END,
            free_bytes = excluded.free_bytes,
            last_seen = excluded.last_seen,
            updated_at = excluded.updated_at,
            specs_json = excluded.specs_json,
            raw_json = excluded.raw_json;
        ''',
        (
            category,
            component_key,
            name,
            vendor,
            model,
            serial_number,
            status,
            health_status,
            float(temperature_c) if temperature_c is not None else None,
            int(capacity_bytes or 0),
            int(free_bytes or 0),
            now_iso,
            now_iso,
            now_epoch,
            specs_json,
            specs_json,
        ),
    )
    return 1


class TelemetryInventoryWriterMixin:
    """Миксин записи инвентаризации и телеметрии оборудования в 12 базовых таблиц."""

    def upsert_device_inventory(
        self,
        cursor: sqlite3.Cursor,
        device_instance_id: str,
        friendly_name: Optional[str] = None,
        device_class: Optional[str] = None,
        install_date: Optional[str] = None,
    ) -> int:
        """Обновляет или вставляет запись об аппаратном PnP-устройстве в hardware_components."""
        if isinstance(device_instance_id, dict):
            dev = device_instance_id
            dev_id = str(dev.get("device_id") or dev.get("device_instance_id") or "")
            fname = str(dev.get("friendly_name") or dev.get("name") or "Unknown Device")
            dclass = str(dev.get("device_class") or dev.get("pnp_class") or dev.get("category") or "Other")
            inst_date = dev.get("install_date")
            extra = dict(dev)
        else:
            dev_id = str(device_instance_id or "")
            fname = str(friendly_name or dev_id or "Unknown Device")
            dclass = str(device_class or "Other")
            inst_date = install_date
            extra = {}

        if not dev_id:
            return 0

        now_iso = datetime.now(timezone.utc).isoformat()
        specs = {
            **extra,
            "device_id": dev_id,
            "device_instance_id": dev_id,
            "friendly_name": fname,
            "device_class": dclass,
            "category": extra.get("category") or dclass,
            "install_date": inst_date or now_iso,
            "first_seen": inst_date or now_iso,
            "last_seen": now_iso,
        }
        return _upsert_hw_component_row(
            cursor=cursor,
            category="pnp_device",
            component_key=dev_id,
            name=fname,
            vendor=str(extra.get("manufacturer") or ""),
            model=dclass,
            status=str(extra.get("status") or "OK"),
            health_status="Problem" if extra.get("has_problem") else "OK",
            specs=specs,
        )

    def insert_disk_io_event(self, cursor: sqlite3.Cursor, data: Any) -> int:
        """Записывает событие дискового ввода-вывода в таблицу process_file_events."""
        io_data = data if isinstance(data, dict) else (data.model_dump() if hasattr(data, "model_dump") else {})
        now_dt = datetime.now(timezone.utc)
        ts_str = io_data.get("timestamp") or now_dt.isoformat()
        created_at = float(io_data.get("created_at") or now_dt.timestamp())
        file_path = str(io_data.get("file_path") or io_data.get("device") or "")
        target_dir = str(io_data.get("target_directory") or (file_path.rsplit("\\", 1)[0] if "\\" in file_path else ""))

        details = {
            "disk_index": io_data.get("disk_index") if io_data.get("disk_index") is not None else io_data.get("disk_id"),
            "volume_letter": io_data.get("volume_letter") or io_data.get("device"),
            "iops": float(io_data.get("iops") or 0.0),
            "latency_ms": float(io_data.get("latency_ms") or 0.0),
            "source": io_data.get("source") or "etw",
            "details": io_data.get("details"),
        }
        cursor.execute(
            '''
            INSERT INTO process_file_events (
                pid, process_name, timestamp, created_at, operation_type,
                file_path, target_directory, bytes_transferred, io_rate_bytes_sec, details_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            ''',
            (
                int(io_data.get("pid") or 0),
                io_data.get("name") or io_data.get("process_name") or "",
                ts_str,
                created_at,
                str(io_data.get("operation") or io_data.get("operation_type") or io_data.get("event_type") or "io"),
                file_path,
                target_dir,
                int(io_data.get("bytes_count") or io_data.get("bytes_transferred") or 0),
                float(io_data.get("io_rate_bytes_sec") or 0.0),
                json.dumps(details, ensure_ascii=False, default=str),
            ),
        )
        return 1

    def upsert_disk_inventory(self, cursor: sqlite3.Cursor, data: Any) -> int:
        """Обновляет или вставляет паспорт физического накопителя в hardware_components."""
        disk = data if isinstance(data, dict) else (data.model_dump() if hasattr(data, "model_dump") else {})
        disk_idx = int(disk.get("disk_index") if disk.get("disk_index") is not None else (disk.get("disk_id") if disk.get("disk_id") is not None else -1))
        serial = str(disk.get("serial_number") or f"disk_{disk_idx}")
        comp_key = f"{disk_idx}|{serial}"
        specs = {
            **disk,
            "disk_index": disk_idx,
            "disk_id": disk_idx,
            "model": disk.get("model") or "Unknown Disk",
            "serial_number": serial,
            "firmware_revision": disk.get("firmware_revision") or "",
            "interface_type": disk.get("interface_type") or "",
            "bus_type": disk.get("bus_type") or "",
            "media_type": disk.get("media_type") or "SSD",
            "size_bytes": int(disk.get("size_bytes") or 0),
            "size_gb": float(disk.get("size_gb") or 0.0),
            "partition_style": disk.get("partition_style") or "GPT",
            "partition_count": int(disk.get("partition_count") or 0),
            "status": disk.get("status") or "OK",
            "health_status": disk.get("health_status") or "Healthy",
            "is_system_disk": 1 if disk.get("is_system_disk") else 0,
        }
        return _upsert_hw_component_row(
            cursor=cursor,
            category="disk",
            component_key=comp_key,
            name=specs["model"],
            model=specs["model"],
            serial_number=serial,
            status=specs["status"],
            health_status=specs["health_status"],
            capacity_bytes=specs["size_bytes"],
            specs=specs,
        )

    def upsert_volume_inventory(self, cursor: sqlite3.Cursor, data: Any) -> int:
        """Обновляет или вставляет запись о логическом разделе/томе в hardware_components."""
        vol = data if isinstance(data, dict) else (data.model_dump() if hasattr(data, "model_dump") else {})
        vol_id = str(vol.get("volume_id") or vol.get("drive_letter") or vol.get("mount_point") or "")
        if not vol_id:
            return 0
        specs = {
            **vol,
            "volume_id": vol_id,
            "drive_letter": vol.get("drive_letter") or "",
            "label": vol.get("label") or "",
            "file_system": vol.get("file_system") or "NTFS",
            "disk_index": vol.get("disk_index"),
            "partition_index": vol.get("partition_index"),
            "total_bytes": int(vol.get("total_bytes") or 0),
            "free_bytes": int(vol.get("free_bytes") or 0),
            "used_bytes": int(vol.get("used_bytes") or 0),
            "percent_used": float(vol.get("percent_used") or 0.0),
            "is_system": 1 if vol.get("is_system") else 0,
            "is_boot": 1 if vol.get("is_boot") else 0,
            "is_pagefile": 1 if vol.get("is_pagefile") else 0,
            "bitlocker_status": vol.get("bitlocker_status") or "Off",
            "mount_point": vol.get("mount_point") or vol.get("drive_letter") or "",
        }
        return _upsert_hw_component_row(
            cursor=cursor,
            category="volume",
            component_key=vol_id,
            name=specs["drive_letter"] or specs["label"] or vol_id,
            model=specs["file_system"],
            status=specs["bitlocker_status"],
            capacity_bytes=specs["total_bytes"],
            free_bytes=specs["free_bytes"],
            specs=specs,
        )

    def insert_disk_health_snapshot(self, cursor: sqlite3.Cursor, data: Any) -> int:
        """Записывает снимок SMART и здоровья накопителя в sensor_polls."""
        health = data if isinstance(data, dict) else (data.model_dump() if hasattr(data, "model_dump") else {})
        now_dt = datetime.now(timezone.utc)
        ts_str = health.get("timestamp") or now_dt.isoformat()
        created_at = float(health.get("created_at") or now_dt.timestamp())
        disk_idx = int(health.get("disk_index") if health.get("disk_index") is not None else (health.get("disk_id") or 0))
        temp_c = health.get("temperature_c")
        val = float(temp_c) if temp_c is not None else float(health.get("wear_level_pct") or 0.0)
        raw_payload = dict(health)
        raw_payload["disk_index"] = disk_idx
        raw_payload["disk_id"] = disk_idx
        cursor.execute(
            '''
            INSERT INTO sensor_polls (
                sensor_id, timestamp, created_at, hardware_name, hardware_type,
                sensor_category, sensor_type, sensor_name, value, value_numeric,
                unit, status, raw_json
            ) VALUES (?, ?, ?, ?, 'storage', 'smart', 'Temperature', ?, ?, ?, 'C', ?, ?);
            ''',
            (
                f"smart_disk_{disk_idx}",
                ts_str,
                created_at,
                str(health.get("model") or f"Disk {disk_idx}"),
                f"SMART Disk {disk_idx}",
                val,
                val,
                str(health.get("health_status") or "Healthy"),
                json.dumps(raw_payload, ensure_ascii=False, default=str),
            ),
        )
        return 1

    def insert_disk_performance_sample(self, cursor: sqlite3.Cursor, data: Any) -> int:
        """Записывает замер производительности диска в sensor_polls."""
        perf = data if isinstance(data, dict) else (data.model_dump() if hasattr(data, "model_dump") else {})
        now_dt = datetime.now(timezone.utc)
        ts_str = perf.get("timestamp") or now_dt.isoformat()
        created_at = float(perf.get("created_at") or now_dt.timestamp())
        disk_idx = perf.get("disk_index")
        vol_let = perf.get("volume_letter") or perf.get("disk_name") or ""
        val = float(perf.get("read_bytes_sec") or 0.0) + float(perf.get("write_bytes_sec") or 0.0)
        cursor.execute(
            '''
            INSERT INTO sensor_polls (
                sensor_id, timestamp, created_at, hardware_name, hardware_type,
                sensor_category, sensor_type, sensor_name, value, value_numeric,
                unit, status, raw_json
            ) VALUES (?, ?, ?, ?, 'storage', 'disk_perf', 'Throughput', ?, ?, ?, 'B/s', 'OK', ?);
            ''',
            (
                f"disk_perf_{disk_idx if disk_idx is not None else vol_let}",
                ts_str,
                created_at,
                f"Disk {disk_idx}" if disk_idx is not None else str(vol_let),
                "Disk Performance",
                val,
                val,
                json.dumps(dict(perf), ensure_ascii=False, default=str),
            ),
        )
        return 1

    def upsert_cpu_inventory(self, cursor: sqlite3.Cursor, data: Any) -> int:
        """Обновляет или вставляет спецификацию процессора в hardware_components."""
        cpu = data if isinstance(data, dict) else (data.model_dump() if hasattr(data, "model_dump") else {})
        proc_id = int(cpu.get("processor_id") or 0)
        features = cpu.get("features") or cpu.get("features_json")
        if isinstance(features, (list, dict)):
            features_json = json.dumps(features, ensure_ascii=False)
        else:
            features_json = str(features) if features else "[]"

        specs = {
            **cpu,
            "processor_id": proc_id,
            "name": cpu.get("name") or cpu.get("model") or "Unknown CPU",
            "vendor": cpu.get("vendor") or "",
            "architecture": cpu.get("architecture") or "",
            "physical_cores": int(cpu.get("physical_cores") or cpu.get("cores_physical") or 0),
            "logical_cores": int(cpu.get("logical_cores") or cpu.get("cores_logical") or 0),
            "base_frequency_mhz": float(cpu.get("base_frequency_mhz") or cpu.get("frequency_mhz") or 0.0),
            "max_frequency_mhz": float(cpu.get("max_frequency_mhz") or cpu.get("frequency_max_mhz") or 0.0),
            "l1_cache_kb": int(cpu.get("l1_cache_kb") or 0),
            "l2_cache_kb": int(cpu.get("l2_cache_kb") or 0),
            "l3_cache_kb": int(cpu.get("l3_cache_kb") or 0),
            "socket": cpu.get("socket") or "",
            "stepping": str(cpu.get("stepping") or ""),
            "virtualization_enabled": 1 if cpu.get("virtualization_enabled", True) else 0,
            "features_json": features_json,
        }
        return _upsert_hw_component_row(
            cursor=cursor,
            category="cpu",
            component_key=str(proc_id),
            name=specs["name"],
            vendor=specs["vendor"],
            model=specs["architecture"],
            specs=specs,
        )

    def insert_cpu_telemetry_sample(self, cursor: sqlite3.Cursor, data: Any) -> int:
        """Записывает замер телеметрии процессора в sensor_polls."""
        sample = data if isinstance(data, dict) else (data.model_dump() if hasattr(data, "model_dump") else {})
        now_dt = datetime.now(timezone.utc)
        ts_str = sample.get("timestamp") or now_dt.isoformat()
        created_at = float(sample.get("created_at") or now_dt.timestamp())
        proc_id = int(sample.get("processor_id") or 0)
        val = float(sample.get("total_percent") or 0.0)
        cursor.execute(
            '''
            INSERT INTO sensor_polls (
                sensor_id, timestamp, created_at, hardware_name, hardware_type,
                sensor_category, sensor_type, sensor_name, value, value_numeric,
                unit, status, raw_json
            ) VALUES (?, ?, ?, 'CPU', 'cpu', 'cpu_telemetry', 'Load', 'CPU Total', ?, ?, '%', 'OK', ?);
            ''',
            (
                f"cpu_sample_{proc_id}",
                ts_str,
                created_at,
                val,
                val,
                json.dumps(dict(sample), ensure_ascii=False, default=str),
            ),
        )
        return 1

    def upsert_ram_module_inventory(self, cursor: sqlite3.Cursor, data: Any) -> int:
        """Обновляет или вставляет запись о физической планке RAM в hardware_components."""
        mod = data if isinstance(data, dict) else (data.model_dump() if hasattr(data, "model_dump") else {})
        bank = str(mod.get("bank_label") or mod.get("slot") or "BANK0")
        locator = str(mod.get("device_locator") or mod.get("locator") or "DIMM0")
        comp_key = f"{bank}|{locator}"
        cap_bytes = int(mod.get("capacity_bytes") or 0)
        cap_gb = float(mod.get("capacity_gb") or (cap_bytes / (1024 ** 3) if cap_bytes else 0.0))
        specs = {
            **mod,
            "bank_label": bank,
            "device_locator": locator,
            "manufacturer": mod.get("manufacturer") or "Unknown",
            "part_number": (mod.get("part_number") or "").strip(),
            "serial_number": (mod.get("serial_number") or "").strip(),
            "capacity_bytes": cap_bytes,
            "capacity_gb": round(cap_gb, 2),
            "speed_mhz": int(mod.get("speed_mhz") or mod.get("speed") or 0),
            "configured_speed_mhz": int(mod.get("configured_speed_mhz") or mod.get("speed_mhz") or 0),
            "memory_type": mod.get("memory_type") or mod.get("type") or "",
            "form_factor": mod.get("form_factor") or "DIMM",
            "voltage_mv": int(mod.get("voltage_mv") or 0),
        }
        return _upsert_hw_component_row(
            cursor=cursor,
            category="ram",
            component_key=comp_key,
            name=f"{bank} {locator}",
            vendor=specs["manufacturer"],
            model=specs["part_number"],
            serial_number=specs["serial_number"],
            capacity_bytes=cap_bytes,
            specs=specs,
        )

    def insert_ram_telemetry_sample(self, cursor: sqlite3.Cursor, data: Any) -> int:
        """Записывает замер состояния оперативной памяти и подкачки в sensor_polls."""
        sample = data if isinstance(data, dict) else (data.model_dump() if hasattr(data, "model_dump") else {})
        now_dt = datetime.now(timezone.utc)
        ts_str = sample.get("timestamp") or now_dt.isoformat()
        created_at = float(sample.get("created_at") or now_dt.timestamp())
        val = float(sample.get("percent_used") or sample.get("percent") or 0.0)
        cursor.execute(
            '''
            INSERT INTO sensor_polls (
                sensor_id, timestamp, created_at, hardware_name, hardware_type,
                sensor_category, sensor_type, sensor_name, value, value_numeric,
                unit, status, raw_json
            ) VALUES ('ram_sample', ?, ?, 'RAM', 'memory', 'ram_telemetry', 'Load', 'Memory Used', ?, ?, '%', 'OK', ?);
            ''',
            (
                ts_str,
                created_at,
                val,
                val,
                json.dumps(dict(sample), ensure_ascii=False, default=str),
            ),
        )
        return 1

    def upsert_gpu_inventory(self, cursor: sqlite3.Cursor, data: Any) -> int:
        """Обновляет или вставляет спецификацию видеокарты (GPU) в hardware_components."""
        gpu = data if isinstance(data, dict) else (data.model_dump() if hasattr(data, "model_dump") else {})
        gpu_idx = int(gpu.get("gpu_index") or gpu.get("gpu_id") or 0)
        name = str(gpu.get("name") or f"GPU {gpu_idx}")
        vendor_val = str(gpu.get("vendor") or "").strip()

        # Формируем канонический ключ устройства, независимый от индекса перечисления
        pnp_id = str(gpu.get("pnp_device_id") or "").strip()
        if pnp_id:
            comp_key = f"pnp:{pnp_id.lower()}"
        else:
            vendor_str = vendor_val.lower()
            norm_name = re.sub(r"\((r|tm)\)", "", name, flags=re.IGNORECASE).lower().strip()
            if vendor_str and vendor_str not in norm_name:
                norm_name = f"{vendor_str} {norm_name}"
            clean_key = re.sub(r"[^a-z0-9]+", "_", norm_name).strip("_")
            comp_key = f"gpu_{clean_key}" if clean_key else f"gpu_{gpu_idx}"

        # Удаляем устаревшие дублирующиеся записи с числовыми префиксами в ключе
        try:
            cursor.execute(
                """
                DELETE FROM hardware_components
                WHERE category = 'gpu'
                  AND (
                      component_key IN (?, ?, ?, ?)
                      OR (name = ? AND component_key != ?)
                  )
                """,
                (f"{gpu_idx}|{name}", f"0|{name}", f"1|{name}", f"2|{name}", name, comp_key),
            )
        except Exception:
            pass

        vram_mb = float(gpu.get("vram_total_mb") or gpu.get("memory_total_mb") or 0.0)
        vram_bytes = int(gpu.get("vram_total_bytes") or (vram_mb * 1024 * 1024))
        specs = {
            **gpu,
            "gpu_index": gpu_idx,
            "gpu_id": gpu_idx,
            "name": name,
            "vendor": vendor_val,
            "driver_version": gpu.get("driver_version") or "",
            "driver_date": gpu.get("driver_date") or "",
            "pnp_device_id": pnp_id,
            "vram_total_mb": vram_mb,
            "vram_total_bytes": vram_bytes,
            "adapter_dac_type": gpu.get("adapter_dac_type") or "",
            "current_resolution": gpu.get("current_resolution") or "",
            "refresh_rate_hz": int(gpu.get("refresh_rate_hz") or 0),
            "status": gpu.get("status") or "OK",
        }
        return _upsert_hw_component_row(
            cursor=cursor,
            category="gpu",
            component_key=comp_key,
            name=name,
            vendor=specs["vendor"],
            model=specs["driver_version"],
            status=specs["status"],
            capacity_bytes=vram_bytes,
            specs=specs,
        )

    def insert_gpu_telemetry_sample(self, cursor: sqlite3.Cursor, data: Any) -> int:
        """Записывает замер телеметрии GPU в sensor_polls."""
        sample = data if isinstance(data, dict) else (data.model_dump() if hasattr(data, "model_dump") else {})
        now_dt = datetime.now(timezone.utc)
        ts_str = sample.get("timestamp") or now_dt.isoformat()
        created_at = float(sample.get("created_at") or now_dt.timestamp())
        gpu_idx = int(sample.get("gpu_index") or sample.get("gpu_id") or 0)
        val = float(sample.get("load_percent") or 0.0)
        cursor.execute(
            '''
            INSERT INTO sensor_polls (
                sensor_id, timestamp, created_at, hardware_name, hardware_type,
                sensor_category, sensor_type, sensor_name, value, value_numeric,
                unit, status, raw_json
            ) VALUES (?, ?, ?, ?, 'gpu', 'gpu_telemetry', 'Load', 'GPU Core', ?, ?, '%', 'OK', ?);
            ''',
            (
                f"gpu_sample_{gpu_idx}",
                ts_str,
                created_at,
                str(sample.get("name") or f"GPU {gpu_idx}"),
                val,
                val,
                json.dumps(dict(sample), ensure_ascii=False, default=str),
            ),
        )
        return 1

    def upsert_network_adapter_inventory(self, cursor: sqlite3.Cursor, data: Any) -> int:
        """Обновляет или вставляет запись о сетевом адаптере в hardware_components."""
        adapter = data if isinstance(data, dict) else (data.model_dump() if hasattr(data, "model_dump") else {})
        iface = str(adapter.get("interface_name") or adapter.get("name") or "")
        if not iface:
            return 0
        ip4 = adapter.get("ipv4_addresses") or adapter.get("ipv4_addresses_json")
        ip6 = adapter.get("ipv6_addresses") or adapter.get("ipv6_addresses_json")
        dns = adapter.get("dns_servers") or adapter.get("dns_servers_json")
        specs = {
            **adapter,
            "interface_name": iface,
            "description": adapter.get("description") or iface,
            "mac_address": adapter.get("mac_address") or "",
            "ipv4_addresses_json": json.dumps(ip4, ensure_ascii=False) if isinstance(ip4, list) else (ip4 or "[]"),
            "ipv6_addresses_json": json.dumps(ip6, ensure_ascii=False) if isinstance(ip6, list) else (ip6 or "[]"),
            "gateway": adapter.get("gateway") or "",
            "dns_servers_json": json.dumps(dns, ensure_ascii=False) if isinstance(dns, list) else (dns or "[]"),
            "speed_mbps": int(adapter.get("speed_mbps") or 0),
            "mtu": int(adapter.get("mtu") or 1500),
            "is_up": 1 if adapter.get("is_up", True) else 0,
            "is_dhcp": 1 if adapter.get("is_dhcp", True) else 0,
            "adapter_type": adapter.get("adapter_type") or "Ethernet",
        }
        return _upsert_hw_component_row(
            cursor=cursor,
            category="network",
            component_key=iface,
            name=iface,
            model=specs["description"],
            serial_number=specs["mac_address"],
            status="UP" if specs["is_up"] else "DOWN",
            specs=specs,
        )

    def insert_network_adapter_sample(self, cursor: sqlite3.Cursor, data: Any) -> int:
        """Записывает замер трафика сетевого интерфейса в sensor_polls."""
        sample = data if isinstance(data, dict) else (data.model_dump() if hasattr(data, "model_dump") else {})
        now_dt = datetime.now(timezone.utc)
        ts_str = sample.get("timestamp") or now_dt.isoformat()
        created_at = float(sample.get("created_at") or now_dt.timestamp())
        iface = str(sample.get("interface_name") or sample.get("adapter_name") or "Total")
        val = float(sample.get("bytes_recv_sec") or 0.0) + float(sample.get("bytes_sent_sec") or 0.0)
        cursor.execute(
            '''
            INSERT INTO sensor_polls (
                sensor_id, timestamp, created_at, hardware_name, hardware_type,
                sensor_category, sensor_type, sensor_name, value, value_numeric,
                unit, status, raw_json
            ) VALUES (?, ?, ?, ?, 'network', 'net_telemetry', 'Throughput', 'Network Traffic', ?, ?, 'B/s', 'OK', ?);
            ''',
            (
                f"net_sample_{iface}",
                ts_str,
                created_at,
                iface,
                val,
                val,
                json.dumps(dict(sample), ensure_ascii=False, default=str),
            ),
        )
        return 1

    def upsert_hardware_component(self, cursor: sqlite3.Cursor, comp: Dict[str, Any]) -> int:
        """Сохраняет или обновляет карточку аппаратного компонента в hardware_components и фиксирует историю."""
        now_dt = datetime.now(timezone.utc)
        now_iso = now_dt.isoformat()
        now_epoch = now_dt.timestamp()
        cat = str(comp.get("category") or "general")
        key = str(comp.get("component_key") or comp.get("name") or f"{cat}_0")
        name = str(comp.get("name") or key)

        existing = cursor.execute(
            "SELECT id, status, specs_json FROM hardware_components WHERE category = ? AND component_key = ?;",
            (cat, key),
        ).fetchone()

        old_specs = {}
        if existing and existing["specs_json"]:
            try:
                old_specs = json.loads(existing["specs_json"])
            except Exception:
                old_specs = {}

        was_present = int(old_specs.get("is_present", 1)) if existing else 0
        inst_cnt = int(old_specs.get("install_count", 1)) + (1 if existing and not was_present else 0)
        specs = {
            **old_specs,
            **(comp.get("specs") if isinstance(comp.get("specs"), dict) else {}),
            **comp,
            "is_present": 1,
            "removed_at": None,
            "install_count": inst_cnt if existing else 1,
            "ai_enrichment_status": comp.get("ai_enrichment_status") or old_specs.get("ai_enrichment_status") or "pending",
        }
        specs_json = json.dumps(specs, ensure_ascii=False, default=str)

        if not existing:
            cursor.execute(
                '''
                INSERT INTO hardware_components (
                    category, component_key, name, vendor, model, serial_number,
                    status, health_status, capacity_bytes, first_seen, last_seen,
                    updated_at, specs_json, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'Healthy', ?, ?, ?, ?, ?, ?);
                ''',
                (
                    cat, key, name,
                    comp.get("vendor") or "",
                    comp.get("model") or "",
                    comp.get("serial_number") or "",
                    comp.get("status") or "OK",
                    int(comp.get("capacity_bytes") or 0),
                    now_iso, now_iso, now_epoch,
                    specs_json, specs_json,
                ),
            )
            row_id = cursor.lastrowid or 1
            cursor.execute(
                '''
                INSERT INTO hardware_component_history (
                    timestamp, created_at, component_type, change_type,
                    component_name, old_config_json, new_config_json, summary
                ) VALUES (?, ?, ?, 'ADDED', ?, NULL, ?, ?);
                ''',
                (
                    now_iso, now_epoch, cat.upper(), name,
                    specs_json, f"Установлен компонент {name} ({key})",
                ),
            )
            return row_id

        cursor.execute(
            '''
            UPDATE hardware_components SET
                name = ?, vendor = ?, model = ?,
                serial_number = COALESCE(NULLIF(?, ''), serial_number),
                capacity_bytes = CASE WHEN ? > 0 THEN ? ELSE capacity_bytes END,
                status = ?, last_seen = ?, updated_at = ?,
                specs_json = ?, raw_json = ?
            WHERE id = ?;
            ''',
            (
                name,
                comp.get("vendor") or "",
                comp.get("model") or "",
                comp.get("serial_number") or "",
                int(comp.get("capacity_bytes") or 0),
                int(comp.get("capacity_bytes") or 0),
                comp.get("status") or "OK",
                now_iso, now_epoch,
                specs_json, specs_json,
                existing["id"],
            ),
        )
        if not was_present:
            cursor.execute(
                '''
                INSERT INTO hardware_component_history (
                    timestamp, created_at, component_type, change_type,
                    component_name, old_config_json, new_config_json, summary
                ) VALUES (?, ?, ?, 'ADDED', ?, NULL, ?, ?);
                ''',
                (
                    now_iso, now_epoch, cat.upper(), name,
                    specs_json, f"Повторно подключен компонент {name} ({key})",
                ),
            )
        return int(existing["id"])

    def mark_missing_hardware_components_removed(
        self,
        cursor: sqlite3.Cursor,
        active_keys: List[str],
        categories: Optional[List[str]] = None,
    ) -> List[str]:
        """Помечает отсутствующие в текущем сканировании компоненты как отключенные (is_present = 0 в specs_json)."""
        if not categories:
            return []
        now_dt = datetime.now(timezone.utc)
        now_iso = now_dt.isoformat()
        now_epoch = now_dt.timestamp()
        cat_placeholders = ",".join("?" for _ in categories)
        cursor.execute(
            f"SELECT id, category, component_key, name, specs_json FROM hardware_components WHERE category IN ({cat_placeholders});",
            tuple(categories),
        )
        active_set = set(active_keys)
        removed_keys: List[str] = []
        for row in cursor.fetchall():
            key = row["component_key"]
            specs = json.loads(row["specs_json"]) if row["specs_json"] else {}
            if not specs.get("is_present", 1):
                continue
            if key not in active_set:
                removed_keys.append(key)
                specs["is_present"] = 0
                specs["removed_at"] = now_iso
                specs_str = json.dumps(specs, ensure_ascii=False, default=str)
                cursor.execute(
                    "UPDATE hardware_components SET status = 'REMOVED', specs_json = ?, updated_at = ? WHERE id = ?;",
                    (specs_str, now_epoch, row["id"]),
                )
                cursor.execute(
                    '''
                    INSERT INTO hardware_component_history (
                        timestamp, created_at, component_type, change_type,
                        component_name, old_config_json, new_config_json, summary
                    ) VALUES (?, ?, ?, 'REMOVED', ?, ?, NULL, ?);
                    ''',
                    (
                        now_iso, now_epoch, str(row["category"]).upper(),
                        row["name"] or key, specs_str,
                        f"Отключен компонент {row['name'] or key} ({key})",
                    ),
                )
        return removed_keys

    def record_hardware_component_event(
        self,
        component_key: str,
        event_type: str,
        details: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None,
    ) -> int:
        """Записывает событие жизненного цикла компонента в hardware_component_history."""
        now_dt = datetime.now(timezone.utc)
        ts_str = timestamp or now_dt.isoformat()
        now_epoch = now_dt.timestamp()
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            comp = cursor.execute(
                "SELECT category, name FROM hardware_components WHERE component_key = ? LIMIT 1;",
                (component_key,),
            ).fetchone()
            cat = comp["category"] if comp else "general"
            name = comp["name"] if comp else component_key
            payload_str = json.dumps(
                {**(details or {}), "component_key": component_key, "event_type": event_type},
                ensure_ascii=False,
                default=str,
            )
            cursor.execute(
                '''
                INSERT INTO hardware_component_history (
                    timestamp, created_at, component_type, change_type,
                    component_name, old_config_json, new_config_json, summary
                ) VALUES (?, ?, ?, ?, ?, NULL, ?, ?);
                ''',
                (
                    ts_str, now_epoch, str(cat).upper(), event_type.upper(),
                    name, payload_str, f"{event_type}: {name} ({component_key})",
                ),
            )
            row_id = cursor.lastrowid or 1
            conn.commit()
            return row_id

    def update_hardware_component_links(
        self,
        component_key: str,
        vendor_url: Optional[str] = None,
        status: str = "completed",
    ) -> bool:
        """Обновляет ссылку на страницу производителя и статус обогащения в hardware_components."""
        now_epoch = datetime.now(timezone.utc).timestamp()
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            row = cursor.execute(
                "SELECT id, specs_json FROM hardware_components WHERE component_key = ? LIMIT 1;",
                (component_key,),
            ).fetchone()
            if not row:
                return False
            specs = json.loads(row["specs_json"]) if row["specs_json"] else {}
            if vendor_url is not None:
                specs["vendor_url"] = vendor_url
            specs["ai_enrichment_status"] = status
            cursor.execute(
                "UPDATE hardware_components SET specs_json = ?, updated_at = ? WHERE id = ?;",
                (json.dumps(specs, ensure_ascii=False, default=str), now_epoch, row["id"]),
            )
            conn.commit()
            return True

    def update_hardware_component_production_date(
        self,
        component_key: str,
        production_date: Optional[str] = None,
        source: Optional[str] = None,
        status: str = "completed",
    ) -> bool:
        """Обновляет дату производства компонента и статус декодирования в hardware_components."""
        now_epoch = datetime.now(timezone.utc).timestamp()
        with self._cm.lock, self._cm.get_connection() as conn:
            cursor = conn.cursor()
            row = cursor.execute(
                "SELECT id, specs_json FROM hardware_components WHERE component_key = ? LIMIT 1;",
                (component_key,),
            ).fetchone()
            if not row:
                return False
            specs = json.loads(row["specs_json"]) if row["specs_json"] else {}
            if production_date is not None:
                specs["production_date"] = production_date
            if source is not None:
                specs["production_date_source"] = source
            specs["production_date_status"] = status
            cursor.execute(
                "UPDATE hardware_components SET specs_json = ?, updated_at = ? WHERE id = ?;",
                (json.dumps(specs, ensure_ascii=False, default=str), now_epoch, row["id"]),
            )
            conn.commit()
            return True



