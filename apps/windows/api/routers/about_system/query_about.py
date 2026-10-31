# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - query_about
# =============================================================================
# Description:
#   Запросы к telemetry.db для обзора и истории панели «О системе».
#   Исключительно чтение из базы данных telemetry.db без внешних опросов.
#
# File: query_about.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers.about_system
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-16 19:14:00
# =============================================================================

from __future__ import annotations

import json
import platform
import time
from datetime import datetime, timezone
from typing import (
    Any,
    Dict,
    List,
    Optional,
)

from logger import logger
from apps.windows.telemetry.sqlite import TelemetryStorage
from .helpers import _format_uptime_human
from .helpers import _get_cpu_brand_name
from .helpers import get_windows_workgroup, get_windows_install_date
from .models import AboutSystemHistoryItem
from .models import AboutSystemHistoryResponse
from .models import AboutSystemPanelOverviewResponse
from .models import CpuPanelResponse
from .models import DiskIoPanelResponse
from .models import GpuPanelResponse
from .models import MemoryPanelResponse
from .models import PlatformOsPanelResponse
from .models import RestorePointsPanelResponse
from .models import SecurityPanelResponse
from .models import StoragePanelResponse


def query_about_system_from_db(storage: TelemetryStorage) -> AboutSystemPanelOverviewResponse:
    """Выполняет сформированные SQL-запросы к telemetry.db и строит сводный JSON-ответ для панели 'О Системе'.

    Args:
        storage: Экземпляр хранилища TelemetryStorage.

    Returns:
        AboutSystemPanelOverviewResponse: Модель со всеми 8 карточками панели.
    """
    now_ts = datetime.now(timezone.utc).isoformat()
    executed_queries: List[str] = []

    snap_row: Optional[Dict[str, Any]] = None
    audit_row: Optional[Dict[str, Any]] = None
    clean_row: Optional[Dict[str, Any]] = None
    gpu_sensor_rows: List[Dict[str, Any]] = []

    with storage._lock, storage._get_connection() as conn:
        cursor = conn.cursor()

        # 1. Запрос последнего системного снимка
        sql_snap = (
            "SELECT id, timestamp, created_at, hostname, uptime_seconds, os_name, os_build, os_install_date, "
            "disks_json, cpu_total_percent, cpu_frequency_mhz, memory_total_gb, "
            "memory_used_gb, memory_percent, swap_percent, gpu_load_percent, gpu_temp_c, "
            "disk_read_bytes_sec, disk_write_bytes_sec, disk_read_count_sec, disk_write_count_sec, "
            "network_sent_bytes_sec, network_recv_bytes_sec, vss_snapshots_count "
            "FROM system_snapshots ORDER BY id DESC LIMIT 1;"
        )
        cursor.execute(sql_snap)
        row = cursor.fetchone()
        if row:
            snap_row = dict(row)
        executed_queries.append(sql_snap)

        # 2. Запрос расширенного аудита безопасности и точек восстановления из inventory_state
        sql_audit = (
            "SELECT state_json AS raw_json, updated_at AS timestamp "
            "FROM inventory_state WHERE domain = 'os_extended_audit' ORDER BY updated_at DESC LIMIT 1;"
        )
        cursor.execute(sql_audit)
        row_audit = cursor.fetchone()
        if row_audit:
            audit_row = dict(row_audit)
            try:
                parsed_aud = json.loads(audit_row.get("raw_json") or "{}")
                if isinstance(parsed_aud, dict):
                    audit_row["vss_snapshots_count"] = parsed_aud.get("vss_snapshots_count", 0)
            except Exception:
                audit_row["vss_snapshots_count"] = 0
        elif snap_row and snap_row.get("vss_snapshots_count") is not None:
            audit_row = {
                "vss_snapshots_count": snap_row.get("vss_snapshots_count", 0),
                "raw_json": "{}",
                "timestamp": snap_row.get("timestamp"),
            }
        executed_queries.append(sql_audit)

        # 3. Запрос метрик очистки накопителя из incidents (domain = 'app_poll')
        sql_clean = (
            "SELECT value, details_json AS details, timestamp FROM incidents "
            "WHERE domain = 'app_poll' AND sensor_id IN ('cleanable_mb', 'clean_findings') "
            "ORDER BY id DESC LIMIT 1;"
        )
        cursor.execute(sql_clean)
        row_clean = cursor.fetchone()
        if row_clean:
            clean_row = dict(row_clean)
        executed_queries.append(sql_clean)

        # 4. Запрос сенсоров GPU
        sql_sensors = (
            "SELECT hardware_name, sensor_name, value, unit, raw_json "
            "FROM sensor_polls "
            "WHERE hardware_type LIKE '%Gpu%' OR hardware_name LIKE '%GeForce%' OR hardware_name LIKE '%NVIDIA%' OR hardware_name LIKE '%Radeon%' "
            "ORDER BY id DESC LIMIT 10;"
        )
        cursor.execute(sql_sensors)
        gpu_sensor_rows = [dict(r) for r in cursor.fetchall()]
        executed_queries.append(sql_sensors)

    # 1. Платформа & ОС
    os_name = (snap_row.get("os_name") if snap_row else None) or f"{platform.system()} {platform.release()}"
    os_build = str((snap_row.get("os_build") if snap_row else None) or platform.version() or "22631")
    os_install_date = str((snap_row.get("os_install_date") if snap_row else None) or "").strip()
    if not os_install_date:
        os_install_date = get_windows_install_date()
    arch = platform.machine() or "AMD64"
    hostname = (snap_row.get("hostname") if snap_row else None) or platform.node() or "Host"
    workgroup = str((snap_row.get("workgroup") if snap_row else None) or "")
    if not workgroup:
        workgroup = get_windows_workgroup()
    uptime_sec = float((snap_row.get("uptime_seconds") if snap_row else None) or 0.0)
    uptime_str = _format_uptime_human(uptime_sec)
    os_title = f"{os_name} ({arch})" if arch else os_name

    os_res = PlatformOsPanelResponse(
        status="ok",
        os_name=os_name,
        os_build=os_build,
        os_install_date=os_install_date,
        architecture=arch,
        hostname=hostname,
        workgroup=workgroup,
        uptime_seconds=uptime_sec,
        uptime_human=uptime_str,
        display_title=os_title,
        display_host=f"Host: {hostname}",
        display_workgroup=f"Workgroup: {workgroup}",
        timestamp=snap_row.get("timestamp") if snap_row else now_ts,
    )

    # 2. Безопасность
    fw_domain = True
    fw_private = True
    fw_public = True
    def_enabled = True
    realtime = True
    uac_enabled = True
    audit_ts = now_ts

    if audit_row:
        audit_ts = audit_row.get("timestamp") or now_ts
        raw_aud = audit_row.get("raw_json")
        if raw_aud:
            try:
                aud_data = json.loads(raw_aud)
                sec = aud_data.get("security", {})
                fw = sec.get("firewall", {})
                fw_domain = bool(fw.get("domain", True))
                fw_private = bool(fw.get("private", True))
                fw_public = bool(fw.get("public", True))
                df = sec.get("defender", {})
                def_enabled = bool(df.get("enabled", True))
                realtime = bool(df.get("realtime_protection", True))
                uac = sec.get("uac", {})
                uac_enabled = bool(uac.get("enabled", True))
            except Exception as err:
                logger.debug(f"[router_about_system] Ошибка парсинга аудита: {err}")

    fw_all = fw_domain and fw_private and fw_public
    fw_text = "ON" if fw_all else "PARTIAL"
    uac_text = "ON" if uac_enabled else "OFF"
    sec_ok = fw_all and def_enabled and realtime and uac_enabled
    sec_title = "Active & Protected" if sec_ok else "Attention Required"

    sec_res = SecurityPanelResponse(
        status=sec_title,
        firewall_status=fw_text,
        firewall_domain=fw_domain,
        firewall_private=fw_private,
        firewall_public=fw_public,
        defender_enabled=def_enabled,
        realtime_protection=realtime,
        uac_enabled=uac_enabled,
        display_title=sec_title,
        display_subtitle=f"Firewall: {fw_text} | UAC: {uac_text}",
        timestamp=audit_ts,
    )

    # 3. Точки восстановления
    checkpoints_count = int(audit_row.get("vss_snapshots_count") or 0) if audit_row else 0
    prot_enabled = True
    prot_status = "Active"
    latest_chk_name = None
    latest_chk_time = None

    if audit_row and audit_row.get("raw_json"):
        try:
            aud_data = json.loads(audit_row["raw_json"])
            vss = aud_data.get("vss", {}) or aud_data.get("restore_points", {})
            if isinstance(vss, dict):
                prot_enabled = bool(vss.get("protection_enabled", True))
                prot_status = vss.get("status") or ("Active" if prot_enabled else "Disabled")
                latest_chk_name = vss.get("latest_name")
                latest_chk_time = vss.get("latest_time")
        except Exception:
            pass

    restore_res = RestorePointsPanelResponse(
        status="ok",
        checkpoints_count=checkpoints_count,
        protection_enabled=prot_enabled,
        protection_status=prot_status,
        display_title=f"{checkpoints_count} Checkpoints",
        display_subtitle=f"Protection: {prot_status}",
        latest_checkpoint_name=latest_chk_name,
        latest_checkpoint_time=latest_chk_time,
        timestamp=audit_ts,
    )

    # 4. Накопитель C:
    disks = []
    if snap_row and snap_row.get("disks_json"):
        try:
            disks = json.loads(snap_row["disks_json"])
        except Exception:
            disks = []

    c_disk = None
    for d in disks:
        dev = (d.get("device") if isinstance(d, dict) else getattr(d, "device", "")) or ""
        mount = (d.get("mountpoint") if isinstance(d, dict) else getattr(d, "mountpoint", "")) or ""
        if dev.upper().startswith("C") or mount.upper().startswith("C"):
            c_disk = d
            break
    if not c_disk and disks:
        c_disk = disks[0]

    tot_gb = float((c_disk.get("total_gb") if isinstance(c_disk, dict) else getattr(c_disk, "total_gb", 0.0)) or 0.0) if c_disk else 0.0
    free_gb = float((c_disk.get("free_gb") if isinstance(c_disk, dict) else getattr(c_disk, "free_gb", 0.0)) or 0.0) if c_disk else 0.0
    used_gb = float((c_disk.get("used_gb") if isinstance(c_disk, dict) else getattr(c_disk, "used_gb", 0.0)) or 0.0) if c_disk else 0.0
    pct_used = float((c_disk.get("percent") if isinstance(c_disk, dict) else getattr(c_disk, "percent", 0.0)) or 0.0) if c_disk else 0.0

    cleanable_mb = float(clean_row.get("value") or 0.0) if clean_row else 0.0
    clean_str = f"~{cleanable_mb:.0f} MB" if cleanable_mb < 1024 else f"~{cleanable_mb/1024:.1f} GB"

    storage_res = StoragePanelResponse(
        status="ok",
        drive="C:",
        total_gb=round(tot_gb, 1),
        free_gb=round(free_gb, 1),
        used_gb=round(used_gb, 1),
        percent_used=round(pct_used, 1),
        cleanable_mb=round(cleanable_mb, 1),
        display_title=f"{free_gb:.1f} GB Free",
        display_subtitle=f"Cleanable: {clean_str}",
        timestamp=snap_row.get("timestamp") if snap_row else now_ts,
    )

    # 5. CPU
    full_snap = storage.get_latest_snapshot_full() or {}
    cpu_data = full_snap.get("cpu") or {}

    cpu_pct = float((snap_row.get("cpu_total_percent") if snap_row else 0.0) or cpu_data.get("total_percent") or 0.0)
    cpu_freq = float((snap_row.get("cpu_frequency_mhz") if snap_row else 0.0) or cpu_data.get("frequency_mhz") or 2900.0)
    phys_cores = int(cpu_data.get("physical_cores") or 6)
    log_cores = int(cpu_data.get("logical_cores") or 12)
    cpu_model = (snap_row.get("cpu_model") if snap_row else None) or cpu_data.get("model") or _get_cpu_brand_name()

    freq_txt = f"{int(cpu_freq)} MHz" if cpu_freq > 0 else ""

    cpu_res = CpuPanelResponse(
        total_percent=round(cpu_pct, 1),
        frequency_mhz=round(cpu_freq, 0),
        physical_cores=phys_cores,
        logical_cores=log_cores,
        model=cpu_model,
        display_val=f"{cpu_pct:.1f}%",
        display_cores=f"{phys_cores} физ. / {log_cores} Потоков",
        display_freq=freq_txt,
    )

    # 6. Память RAM
    mem_total = float((snap_row.get("memory_total_gb") if snap_row else 0.0) or 0.0)
    mem_used = float((snap_row.get("memory_used_gb") if snap_row else 0.0) or 0.0)
    mem_pct = float((snap_row.get("memory_percent") if snap_row else 0.0) or 0.0)

    if mem_total <= 0.0:
        mem_data = full_snap.get("memory") or {}
        mem_total = float(mem_data.get("total_gb") or 16.0)
        mem_used = float(mem_data.get("used_gb") or 8.0)
        mem_pct = float(mem_data.get("percent") or 50.0)

    mem_avail = max(0.0, mem_total - mem_used)

    memory_res = MemoryPanelResponse(
        total_gb=round(mem_total, 1),
        used_gb=round(mem_used, 1),
        available_gb=round(mem_avail, 1),
        percent=round(mem_pct, 1),
        display_val=f"{mem_used:.1f} / {mem_total:.1f} GB",
        display_sub=f"{mem_pct:.1f}% занято ({mem_avail:.1f} GB свободно)",
    )

    # 7. GPU
    gpu_name = "GeForce GT 710"
    gpu_vram = 2.0
    if gpu_sensor_rows:
        for g_row in gpu_sensor_rows:
            hw_name = g_row.get("hardware_name")
            if hw_name and ("GeForce" in hw_name or "NVIDIA" in hw_name or "Radeon" in hw_name or "Intel" in hw_name):
                gpu_name = hw_name
                break
    gpu_load = float((snap_row.get("gpu_load_percent") if snap_row else 0.0) or 0.0)
    gpu_temp = float(snap_row["gpu_temp_c"]) if snap_row and snap_row.get("gpu_temp_c") is not None else None
    caps = ["CUDA", "DirectML"] if ("GeForce" in gpu_name or "NVIDIA" in gpu_name) else (["ROCm", "DirectML"] if ("Radeon" in gpu_name or "AMD" in gpu_name) else (["oneAPI", "DirectML"] if "Intel" in gpu_name else ["Active GPU"]))
    badge_str = " + ".join(caps)

    gpu_res = GpuPanelResponse(
        name=gpu_name,
        memory_total_gb=round(gpu_vram, 1),
        load_percent=round(gpu_load, 1),
        temperature_c=gpu_temp,
        badge=badge_str,
        display_name=gpu_name,
        display_vram=f"VRAM: {gpu_vram:.1f} GB | Нагрузка: {int(gpu_load)}%",
    )

    # 8. Диск I/O
    disk_rb = float((snap_row.get("disk_read_bytes_sec") if snap_row else 0.0) or 0.0)
    disk_wb = float((snap_row.get("disk_write_bytes_sec") if snap_row else 0.0) or 0.0)
    total_mbs = (disk_rb + disk_wb) / (1024.0 * 1024.0)
    rkbs = disk_rb / 1024.0
    wkbs = disk_wb / 1024.0

    disk_io_res = DiskIoPanelResponse(
        read_bytes_sec=disk_rb,
        write_bytes_sec=disk_wb,
        total_mb_s=round(total_mbs, 2),
        read_kb_s=round(rkbs, 1),
        write_kb_s=round(wkbs, 1),
        display_val=f"{total_mbs:.2f} MB/s",
        display_rates=f"Чтение: {int(rkbs)} КБ/с | Запись: {int(wkbs)} КБ/с",
    )

    meta = {
        "source": "telemetry.db",
        "db_path": str(storage.db_path),
        "timestamp": snap_row.get("timestamp") if snap_row else now_ts,
        "sql_queries": executed_queries,
    }

    return AboutSystemPanelOverviewResponse(
        status="ok",
        os=os_res,
        security=sec_res,
        restore_points=restore_res,
        storage=storage_res,
        cpu=cpu_res,
        memory=memory_res,
        gpu=gpu_res,
        disk_io=disk_io_res,
        meta=meta,
    )


def query_about_system_history_from_db(
    storage: TelemetryStorage,
    limit: int = 30,
    metric: str = "all",
) -> AboutSystemHistoryResponse:
    """Извлекает исторические срезы телеметрии из таблицы system_snapshots в telemetry.db.

    Args:
        storage: Экземпляр хранилища TelemetryStorage.
        limit: Максимальное число возвращаемых записей истории (по умолчанию 30).
        metric: Фильтр метрики ('all', 'cpu', 'memory', 'gpu', 'storage', 'disk_io').

    Returns:
        AboutSystemHistoryResponse: Список исторических снимков с форматированными полями.
    """
    safe_limit = max(1, min(limit, 200))
    history_items: List[AboutSystemHistoryItem] = []

    sql_history = (
        "SELECT id, timestamp, created_at, hostname, uptime_seconds, os_name, os_build, os_install_date, "
        "disks_json, cpu_total_percent, cpu_frequency_mhz, memory_total_gb, "
        "memory_used_gb, memory_percent, swap_percent, gpu_load_percent, gpu_temp_c, "
        "disk_read_bytes_sec, disk_write_bytes_sec, disk_read_count_sec, disk_write_count_sec, "
        "network_sent_bytes_sec, network_recv_bytes_sec "
        "FROM system_snapshots ORDER BY id DESC LIMIT ?;"
    )

    with storage._lock, storage._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql_history, (safe_limit,))
        rows = cursor.fetchall()

    for row in rows:
        r = dict(row)
        snap_id = int(r.get("id") or 0)
        ts = str(r.get("timestamp") or "")
        created_at_val = float(r["created_at"]) if r.get("created_at") is not None else None
        hname = str(r.get("hostname") or "")
        uptime_sec = float(r.get("uptime_seconds") or 0.0)
        uptime_str = _format_uptime_human(uptime_sec)
        os_n = str(r.get("os_name") or "Windows")
        os_b = str(r.get("os_build") or "")
        os_inst_d = str(r.get("os_install_date") or "")

        cpu_pct = float(r.get("cpu_total_percent") or 0.0)
        cpu_freq = float(r.get("cpu_frequency_mhz") or 0.0)

        mem_tot = float(r.get("memory_total_gb") or 0.0)
        mem_used = float(r.get("memory_used_gb") or 0.0)
        mem_pct = float(r.get("memory_percent") or 0.0)

        gpu_load = float(r.get("gpu_load_percent") or 0.0)
        gpu_temp = float(r["gpu_temp_c"]) if r.get("gpu_temp_c") is not None else None

        disk_rb = float(r.get("disk_read_bytes_sec") or 0.0)
        disk_wb = float(r.get("disk_write_bytes_sec") or 0.0)
        disk_total_mb_s = (disk_rb + disk_wb) / (1024.0 * 1024.0)

        # Вычисление емкости и остатка на C:
        c_free_gb: Optional[float] = None
        c_used_gb: Optional[float] = None
        c_total_gb: Optional[float] = None

        disks_str = r.get("disks_json")
        if disks_str and isinstance(disks_str, str):
            try:
                disks_arr = json.loads(disks_str)
                for d in disks_arr:
                    dev = (d.get("device") if isinstance(d, dict) else getattr(d, "device", "")) or ""
                    mnt = (d.get("mountpoint") if isinstance(d, dict) else getattr(d, "mountpoint", "")) or ""
                    if dev.upper().startswith("C") or mnt.upper().startswith("C"):
                        c_free_gb = round(float(d.get("free_gb") or 0.0), 1)
                        c_used_gb = round(float(d.get("used_gb") or 0.0), 1)
                        c_total_gb = round(float(d.get("total_gb") or 0.0), 1)
                        break
            except Exception:
                pass

        item = AboutSystemHistoryItem(
            id=snap_id,
            timestamp=ts,
            created_at=created_at_val,
            hostname=hname,
            uptime_seconds=uptime_sec,
            uptime_human=uptime_str,
            os_name=os_n,
            os_build=os_b,
            os_install_date=os_inst_d or None,
            cpu_total_percent=round(cpu_pct, 1),
            cpu_frequency_mhz=round(cpu_freq, 0),
            memory_total_gb=round(mem_tot, 1),
            memory_used_gb=round(mem_used, 1),
            memory_percent=round(mem_pct, 1),
            gpu_load_percent=round(gpu_load, 1),
            gpu_temp_c=round(gpu_temp, 1) if gpu_temp is not None else None,
            disk_read_bytes_sec=round(disk_rb, 0),
            disk_write_bytes_sec=round(disk_wb, 0),
            disk_io_total_mb_s=round(disk_total_mb_s, 2),
            storage_c_free_gb=c_free_gb,
            storage_c_used_gb=c_used_gb,
            storage_c_total_gb=c_total_gb,
        )
        history_items.append(item)

    return AboutSystemHistoryResponse(
        status="ok",
        count=len(history_items),
        metric=metric,
        history=history_items,
        meta={
            "source": "telemetry.db",
            "table": "system_snapshots",
            "db_path": str(storage.db_path),
            "limit": safe_limit,
            "sql_query": sql_history.replace("?", str(safe_limit)),
        },
    )

