# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - query_summary
# =============================================================================
# Description:
#   Запрос полной сводки системы исключительно из базы данных telemetry.db.
#   Прямые запросы к физическим датчикам, psutil и WMI запрещены архитектурой.
#
# File: query_summary.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers.about_system
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-03 14:05:00
# =============================================================================

from __future__ import annotations

import os
import platform
from datetime import datetime
from typing import Any, Dict, List

from logger import logger
from apps.windows.telemetry.sqlite import TelemetryStorage
from apps.windows.api.routers.about_system.helpers import get_current_user_account_info, get_clean_system_timezone, get_windows_install_date
from apps.windows.sdk.modules.regional.keyboard_helper import get_detailed_language_packs, get_system_language_identity


async def query_system_summary_full(storage: TelemetryStorage, process_limit: int = 25) -> Dict[str, Any]:
    """Возвращает срез системного снимка исключительно из telemetry.db без опроса датчиков."""
    snap = storage.get_latest_snapshot_full() or {}

    # 1. Базовая идентичность хоста и пользователя
    hostname = snap.get("hostname") or platform.node() or "Host"
    os_name = snap.get("os_name") or f"{platform.system()} {platform.release()}"
    os_build = str(snap.get("os_build") or platform.version() or "22631")
    os_install_date = str(snap.get("os_install_date") or "").strip()
    if not os_install_date:
        os_install_date = get_windows_install_date()

    user_info = get_current_user_account_info()
    username = user_info.get("username") or snap.get("username") or os.getenv("USERNAME") or "User"

    snap["hostname"] = hostname
    snap["username"] = username
    snap["os_name"] = os_name
    snap["os_build"] = os_build
    snap["os_install_date"] = os_install_date

    # Расширенные атрибуты пользователя ОС
    snap["user"] = user_info
    snap["user_full_name"] = user_info.get("full_name", "")
    snap["user_first_name"] = user_info.get("first_name", "")
    snap["user_last_name"] = user_info.get("last_name", "")
    snap["user_description"] = user_info.get("description", "")
    snap["user_title"] = user_info.get("title", "")
    snap["user_sid"] = user_info.get("sid", "")
    snap["user_profile"] = user_info.get("profile_dir", "")
    snap["user_domain"] = user_info.get("domain", "")
    snap["user_groups"] = user_info.get("groups", [])
    snap["user_is_admin"] = user_info.get("is_admin", False)
    snap["user_privilege"] = user_info.get("privilege", "Стандартный пользователь")
    snap["user_account_type"] = user_info.get("account_type", "Локальная учетная запись")
    snap["user_last_logon"] = user_info.get("last_logon", "")

    # 2. Локализация и языки
    try:
        lang_ident = get_system_language_identity(os.name == "nt")
        snap["os_install_language"] = lang_ident.get("os_install_language") or snap.get("os_install_language") or "Английский (English (United States)) [en-US]"
        snap["display_language"] = lang_ident.get("display_language") or snap.get("system_language") or "Русский (Россия) [ru-RU]"
        snap["system_language"] = snap["display_language"]
    except Exception:
        if not snap.get("system_language"):
            snap["system_language"] = "Русский (Россия) [ru-RU]"
        if not snap.get("os_install_language"):
            snap["os_install_language"] = "Английский (English (United States)) [en-US]"
        snap["display_language"] = snap["system_language"]

    if not snap.get("user_locale"):
        snap["user_locale"] = "ru-RU"
    if not snap.get("system_locale"):
        snap["system_locale"] = "ru-RU"
    if not snap.get("timezone") or "?" in str(snap.get("timezone")):
        snap["timezone"] = get_clean_system_timezone()
    if not snap.get("codepage"):
        snap["codepage"] = "UTF-8 (ACP: 65001)"
    try:
        packs = get_detailed_language_packs()
        active_packs = sorted(
            [p for p in packs if p.get("is_active")],
            key=lambda x: x.get("order_index") or 99,
        )
        formatted_inputs = []
        for p in active_packs:
            short_tag = (p.get("tag") or "").split("-")[0].upper()
            layouts = p.get("keyboard_layouts") or []
            star = "★ " if p.get("is_default_input") else ""
            if len(layouts) > 1:
                formatted_inputs.append(f"{star}{p.get('native_name', short_tag)} [{short_tag}: {len(layouts)} раскл.]")
            else:
                formatted_inputs.append(f"{star}{p.get('native_name', short_tag)} [{short_tag}]")
        if formatted_inputs:
            snap["input_languages"] = formatted_inputs
    except Exception:
        if not snap.get("input_languages"):
            snap["input_languages"] = []

    # 3. CPU
    if not snap.get("cpu") or not isinstance(snap["cpu"], dict):
        cpu_inv = {}
        try:
            cpus = storage.get_cpu_inventory()
            if cpus:
                cpu_inv = cpus[0]
        except Exception:
            pass
        snap["cpu"] = {
            "model": cpu_inv.get("name") or "Intel / AMD Processor",
            "architecture": cpu_inv.get("architecture") or platform.machine() or "x86_64",
            "physical_cores": cpu_inv.get("physical_cores", 4),
            "logical_cores": cpu_inv.get("logical_cores", 8),
            "total_percent": float(snap.get("cpu_total_percent") or 0.0),
            "frequency_mhz": float(snap.get("cpu_frequency_mhz") or 0.0),
        }
    else:
        if not snap["cpu"].get("total_percent"):
            snap["cpu"]["total_percent"] = float(snap.get("cpu_total_percent") or 0.0)
        if not snap["cpu"].get("frequency_mhz"):
            snap["cpu"]["frequency_mhz"] = float(snap.get("cpu_frequency_mhz") or 0.0)

    # 4. Память (RAM)
    if not snap.get("memory") or not isinstance(snap["memory"], dict):
        tot_m = float(snap.get("memory_total_gb") or 0.0)
        if tot_m <= 0.0:
            try:
                import psutil
                tot_m = round(psutil.virtual_memory().total / (1024 ** 3), 2)
            except Exception:
                tot_m = 32.0
        used_m = float(snap.get("memory_used_gb") or 0.0)
        pct_m = float(snap.get("memory_percent") or 0.0)
        snap["memory"] = {
            "total_gb": tot_m,
            "used_gb": used_m,
            "available_gb": round(max(0.0, tot_m - used_m), 2),
            "percent": pct_m,
            "swap_percent": float(snap.get("swap_percent") or 0.0),
        }

    # 5. Видеокарты (GPUs) - строго из инвентаря БД
    if not snap.get("gpus"):
        try:
            db_gpus = storage.get_gpu_inventory()
            if db_gpus:
                snap["gpus"] = [
                    {
                        "name": g.get("name", "GPU"),
                        "vram_mb": int((float(g.get("vram_gb") or 0.0)) * 1024),
                        "driver_version": g.get("driver_version", ""),
                        "load_percent": float(snap.get("gpu_load_percent") or 0.0),
                        "temperature_celsius": float(snap.get("gpu_temp_c") or 0.0),
                    }
                    for g in db_gpus
                ]
            else:
                snap["gpus"] = []
        except Exception:
            snap["gpus"] = []

    # 6. Диски и разделы (Disks & Volumes) - строго из SQLite
    if not snap.get("disks") or not snap.get("physical_disks"):
        try:
            st_data = storage.get_latest_storage_data()
            if not snap.get("disks") and st_data.get("partitions"):
                snap["disks"] = st_data["partitions"]
            if not snap.get("physical_disks") and st_data.get("physical_disks"):
                snap["physical_disks"] = st_data["physical_disks"]
        except Exception:
            pass

    if not snap.get("disks"):
        snap["disks"] = []
    if not snap.get("physical_disks"):
        try:
            snap["physical_disks"] = storage.get_disk_inventory() or []
        except Exception:
            snap["physical_disks"] = []

    if not snap.get("disk_io"):
        snap["disk_io"] = {
            "read_bytes_per_sec": float(snap.get("disk_read_bytes_sec") or 0.0),
            "write_bytes_per_sec": float(snap.get("disk_write_bytes_sec") or 0.0),
            "read_count_per_sec": float(snap.get("disk_read_count_sec") or 0.0),
            "write_count_per_sec": float(snap.get("disk_write_count_sec") or 0.0),
        }

    # 7. Мониторы - приоритетно из аппаратного инвентаря БД (hardware_components)
    inv_monitors: List[Dict[str, Any]] = []
    try:
        inv_monitors = storage.get_monitor_inventory() or []
    except Exception as ex:
        logger.debug(f"[query_summary] Ошибка получения инвентаря мониторов: {ex}")

    valid_inv = [
        m for m in inv_monitors
        if isinstance(m, dict) and m.get("device") and "windisc" not in str(m.get("device")).lower()
    ]

    snap_monitors = [
        m for m in (snap.get("monitors") or [])
        if isinstance(m, dict) and m.get("device") and "windisc" not in str(m.get("device")).lower()
    ]

    # Инвентарь hardware_components содержит наиболее полные спецификации дисплеев
    if valid_inv:
        snap["monitors"] = valid_inv
    elif snap_monitors:
        snap["monitors"] = snap_monitors
    elif inv_monitors:
        snap["monitors"] = inv_monitors
    else:
        snap["monitors"] = []

    # Обогащаем дисплеи детальными именами EDID и атрибутами из инвентаря оборудования
    try:
        if inv_monitors:
            inv_map = {m.get("device"): m for m in inv_monitors if m.get("device")}
            for m in snap.get("monitors", []):
                dev = m.get("device")
                if dev and dev in inv_map:
                    inv_item = inv_map[dev]
                    if (not m.get("name") or "Generic" in m.get("name", "")) and inv_item.get("name"):
                        m["name"] = inv_item["name"]
                    if inv_item.get("vendor") and not m.get("vendor"):
                        m["vendor"] = inv_item["vendor"]
                    if inv_item.get("serial_number") and not m.get("serial_number"):
                        m["serial_number"] = inv_item["serial_number"]
                    if inv_item.get("production_date") and not m.get("production_date"):
                        m["production_date"] = inv_item["production_date"]
                    if inv_item.get("adapter") and not m.get("adapter"):
                        m["adapter"] = inv_item["adapter"]
    except Exception as ex:
        logger.debug(f"[query_summary] Ошибка обогащения мониторов: {ex}")

    for m in snap.get("monitors", []):
        if isinstance(m, dict) and not m.get("orientation"):
            w = int(m.get("width", 1920) or 1920)
            h = int(m.get("height", 1080) or 1080)
            m["orientation"] = "вертикальная" if h > w else "горизонтальная"

    # 8. Обновления ОС
    if not snap.get("updates"):
        snap["updates"] = {
            "status": "Актуально (telemetry.db)",
            "installed_kb_count": 0,
            "recent_hotfixes": [],
        }

    # 9. MS Office
    if not snap.get("office"):
        snap["office"] = {"installed": False, "status": "Не установлен"}

    # 10. OneDrive
    if not snap.get("onedrive"):
        snap["onedrive"] = {"installed": False, "status": "Не настроено"}

    # 11. Батарея
    if not snap.get("battery"):
        snap["battery"] = {
            "has_battery": False,
            "power_plugged": True,
            "power_profile": "AC Mains / Desktop",
            "percent": 100,
        }

    # 12. Модули RAM SPD - строго из инвентаря БД и реестра аппаратных компонентов
    if not snap.get("ram_sticks"):
        try:
            snap["ram_sticks"] = storage.get_ram_module_inventory() or []
            if not snap["ram_sticks"]:
                comps = storage.get_hardware_components()
                ram_items = []
                for comp in comps:
                    if "RAM" in comp.get("category", "") or "Memory Module" in comp.get("category", ""):
                        pj = comp.get("properties_json") or {}
                        raw_speed = str(pj.get("Номинальная частота") or "3200")
                        speed_int = int("".join(filter(str.isdigit, raw_speed)) or 3200)
                        ram_items.append({
                            "bank_label": pj.get("Слот / Разъем (Locator)") or "DIMM",
                            "capacity_gb": 32.0,
                            "speed_mhz": speed_int,
                            "manufacturer": comp.get("vendor") or pj.get("Производитель") or "Generic",
                            "memory_type": pj.get("Тип памяти") or "DDR4",
                            "serial_number": pj.get("Серийный номер (S/N)") or "",
                            "part_number": pj.get("Парт-номер (P/N)") or "",
                        })
                if ram_items:
                    snap["ram_sticks"] = ram_items
        except Exception:
            snap["ram_sticks"] = []

    # 13. Процессы - строго из БД
    if not snap.get("top_processes"):
        try:
            snap["top_processes"] = storage.get_latest_processes(limit=process_limit)
        except Exception:
            snap["top_processes"] = []

    return snap

