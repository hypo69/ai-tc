# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - Router Storage Load
# =============================================================================
# Description:
#   GET /api/v1/panel/storage-load — детальные параметры и метрики всех дисков
#   и накопителей (NVMe, SSD, HDD, USB) без жесткого кодирования (Zero-Hardcode):
#   динамическое слияние Windows CIM/WMI (WindowsStorageSensor) и системных разделов psutil.
#
# Usage Examples:
#   Python API:
#     from apps.windows.api.routers.router_storage_load import init_router
#     app.include_router(init_router())
#
# File: router_storage_load.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 16:10:00
# =============================================================================

from __future__ import annotations
"""Роутер панели «Параметры накопителей (Диски SSD/HDD/NVMe)»: метрики хранилища."""

import os
import re
import time
from typing import Any, Dict, List, Optional
from fastapi import APIRouter
from pydantic import BaseModel, Field

try:
    import psutil
except ImportError:
    psutil = None

from logger import logger
from apps.windows.sdk.modules.storage_manager.core.windows_storage_sensor import WindowsStorageSensor
from apps.windows.api.routers.about_system.query_diagnostics import _resolve_disk_num_to_letters_map


class DiskDriveMetric(BaseModel):
    """Метрика физического накопителя (SSD, HDD, NVMe)."""
    id: str = Field(default="", description="Идентификатор накопителя (напр. Disk0)")
    name: str = Field(..., description="Модель или наименование диска")
    media_type: str = Field(default="SSD", description="Тип носителя: NVMe, SSD, HDD, External")
    interface_type: Optional[str] = Field(default=None, description="Интерфейс: SATA, NVMe, USB, PCIe")
    serial_number: Optional[str] = Field(default=None, description="Серийный номер диска")
    health_status: Optional[str] = Field(default="Healthy", description="Состояние здоровья (SMART)")
    total_gb: Optional[float] = Field(default=None, description="Полный объем накопителя, GB")
    used_gb: Optional[float] = Field(default=None, description="Занятый объем, GB")
    free_gb: Optional[float] = Field(default=None, description="Свободный объем, GB")
    used_percent: Optional[float] = Field(default=None, description="Заполненность накопителя, %")
    temperature_c: Optional[float] = Field(default=None, description="Температура накопителя, °C")
    activity_percent: Optional[float] = Field(default=None, description="Общая интенсивность обращений (активность), %")
    read_activity_percent: Optional[float] = Field(default=None, description="Активность чтения, %")
    write_activity_percent: Optional[float] = Field(default=None, description="Активность записи, %")
    read_rate_raw: Optional[str] = Field(default=None, description="Скорость чтения")
    write_rate_raw: Optional[str] = Field(default=None, description="Скорость записи")
    data_written_gb: Optional[float] = Field(default=None, description="Объем записанных данных, GB")
    data_written_raw: Optional[str] = Field(default=None, description="Форматированный объем записанных данных")
    data_read_gb: Optional[float] = Field(default=None, description="Объем прочитанных данных, GB")
    data_read_raw: Optional[str] = Field(default=None, description="Форматированный объем прочитанных данных")
    read_bytes: Optional[int] = Field(default=None, description="Байт прочитано")
    write_bytes: Optional[int] = Field(default=None, description="Байт записано")
    read_count: Optional[int] = Field(default=None, description="Количество операций чтения")
    write_count: Optional[int] = Field(default=None, description="Количество операций записи")
    life_percent: Optional[float] = Field(default=None, description="Остаточный ресурс SSD (Life), %")
    power_on_hours: Optional[float] = Field(default=None, description="Время наработки (Power-on Hours)")
    power_on_count: Optional[float] = Field(default=None, description="Количество циклов включения")
    partitions: List[str] = Field(default_factory=list, description="Связанные буквы дисков / разделы")


class DiskPartitionMetric(BaseModel):
    """Метрика логического диска / раздела."""
    device: str = Field(..., description="Устройство (буква диска, напр. C:\\)")
    mountpoint: str = Field(..., description="Точка монтирования")
    fstype: str = Field(default="", description="Файловая система (NTFS, FAT32)")
    total_gb: float = Field(default=0.0, description="Полный объем раздела, GB")
    used_gb: float = Field(default=0.0, description="Занятый объем раздела, GB")
    free_gb: float = Field(default=0.0, description="Свободный объем раздела, GB")
    used_percent: float = Field(default=0.0, description="Процент заполнения раздела, %")


class StorageSummary(BaseModel):
    """Сводка по всему хранилищу."""
    total_gb: float = Field(default=0.0, description="Суммарный объем всех дисков, GB")
    used_gb: float = Field(default=0.0, description="Суммарно занятый объем, GB")
    free_gb: float = Field(default=0.0, description="Суммарно свободный объем, GB")
    used_percent: float = Field(default=0.0, description="Общий процент занятого пространства, %")
    max_temperature_c: Optional[float] = Field(default=None, description="Максимальная температура среди дисков, °C")
    avg_temperature_c: Optional[float] = Field(default=None, description="Средняя температура дисков, °C")
    drives_count: Optional[int] = Field(default=None, description="Количество физических дисков")
    partitions_count: Optional[int] = Field(default=None, description="Количество разделов")


class StorageLoadResponse(BaseModel):
    """Ответ GET /api/v1/panel/storage-load."""
    status: str = Field(default="ok", description="Статус ответа")
    summary: StorageSummary = Field(default_factory=StorageSummary, description="Общая сводка хранилища")
    drives: List[DiskDriveMetric] = Field(default_factory=list, description="Физические накопители")
    partitions: List[DiskPartitionMetric] = Field(default_factory=list, description="Логические разделы")
    meta: Dict[str, Any] = Field(default_factory=dict, description="Метаданные ответа")


def _get_val(obj: Any, key: str, default: Any = None) -> Any:
    """Извлекает значение поля из словаря или атрибута объекта."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        val = obj.get(key)
        return val if val is not None else default
    return getattr(obj, key, default)


def _detect_media_type(name: str) -> str:
    """Определяет тип диска (NVMe, SSD, HDD) по названию модели."""
    n = name.lower()
    if "nvme" in n or "990" in n or "980" in n or "970" in n or "optane" in n:
        return "NVMe"
    if "ssd" in n or "flash" in n or "solid" in n or "crucial" in n:
        return "SSD"
    return "HDD"


def _find_matching_key(drives_map: Dict[str, Dict[str, Any]], name: str) -> Optional[str]:
    """Находит ключ накопителя в словаре по частичному совпадению модели."""
    nl = name.lower().strip()
    for k in drives_map:
        kl = k.lower().strip()
        if nl in kl or kl in nl:
            return k
    return None


def extract_smart_temperature(cd: Any) -> Optional[float]:
    """Извлекает температуру накопителя из SMART-атрибутов 190 и 194.

    Поддерживает диски TOSHIBA, WDC, Crucial и др., где температура
    передается через Airflow Temperature (190) или Temperature Celsius (194).
    """
    if cd is None:
        return None
    # Проверка прямых полей объекта/словаря
    for field in ("temperature_c", "temperature_celsius", "temp_c", "temperature"):
        v = getattr(cd, field, None) if not isinstance(cd, dict) else cd.get(field)
        if isinstance(v, (int, float)) and 5 < v <= 120:
            return float(v)
    # Проверка вложенных структур SMART
    smart_sources = []
    for key in ("smart_attributes", "smart_attrs", "smart_data", "raw_storage_data", "raw_smart"):
        val = getattr(cd, key, None) if not isinstance(cd, dict) else cd.get(key)
        if isinstance(val, dict):
            smart_sources.append(val)
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, dict):
                    smart_sources.append(item)
    for s_dict in smart_sources:
        for attr_id in (194, 190, "194", "190"):
            if attr_id in s_dict:
                item = s_dict[attr_id]
                raw_val = None
                if isinstance(item, dict):
                    raw_val = item.get("raw") or item.get("raw_value") or item.get("val") or item.get("value")
                elif isinstance(item, (int, float)):
                    raw_val = item
                if raw_val is not None:
                    try:
                        temp_num = float(int(raw_val) & 0xFF if isinstance(raw_val, int) else raw_val)
                        if 5 < temp_num <= 120:
                            return temp_num
                    except (ValueError, TypeError):
                        pass
    return None


_LAST_PERDISK_IO: Dict[str, Any] = {}
_LAST_PERDISK_TIME: float = 0.0


def _format_bytes_rate(bytes_sec: float) -> str:
    """Форматирует скорость передачи данных в байт/с в человекочитаемый вид."""
    if bytes_sec <= 0:
        return "0 B/s"
    if bytes_sec >= 1024 ** 3:
        return f"{bytes_sec / (1024 ** 3):.2f} GB/s"
    if bytes_sec >= 1024 ** 2:
        return f"{bytes_sec / (1024 ** 2):.1f} MB/s"
    if bytes_sec >= 1024:
        return f"{bytes_sec / 1024:.0f} KB/s"
    return f"{int(bytes_sec)} B/s"


def build_storage_load(
    sensors: Optional[List[Dict[str, Any]]] = None,
    physical_disks: Optional[List[Any]] = None,
    partitions_data: Optional[List[Dict[str, Any]]] = None,
) -> StorageLoadResponse:
    """Собирает структурированные данные о всех дисках и разделах.

    Параметры:
        sensors: (оставлен для совместимости) список показаний аппаратных сенсоров. При отсутствии передаем пустой список.
        physical_disks: Список физических дисков из WindowsStorageSensor (CIM/WMI).
        partitions_data: Опциональный список готовых данных по разделам для тестов.

    Возвращает:
        StorageLoadResponse: Структура с физическими накопителями и разделами.
    """
    if sensors is None:
        sensors = []
    if physical_disks is None:
        physical_disks = []
    if partitions_data is None and psutil is not None and hasattr(psutil, "disk_partitions"):
        partitions_data = []
        for p in psutil.disk_partitions(all=False):
            try:
                u = psutil.disk_usage(p.mountpoint)
                partitions_data.append({
                    "device": p.device,
                    "mountpoint": p.mountpoint,
                    "fstype": p.fstype,
                    "total_gb": round(u.total / (1024**3), 2),
                    "used_gb": round(u.used / (1024**3), 2),
                    "free_gb": round(u.free / (1024**3), 2),
                    "percent": round(u.percent, 1),
                })
            except Exception:
                pass

    drives_map: Dict[str, Dict[str, Any]] = {}

    # 1. Загрузка физических дисков (из SQLite снимка или WindowsStorageSensor)
    if physical_disks:
        for idx, cd in enumerate(physical_disks):
            m = _get_val(cd, "model") or _get_val(cd, "friendly_name") or _get_val(cd, "name") or f"Physical Drive {idx}"
            dev_id = _get_val(cd, "device_id") or f"Disk{idx}"
            media_type = _get_val(cd, "media_type")
            detected = _detect_media_type(m)
            if not media_type or (media_type.lower() in ("unspecified", "ssd") and detected == "NVMe"):
                media_type = "NVMe"
            elif not media_type or media_type.lower() == "unspecified":
                media_type = detected

            temp = extract_smart_temperature(cd)
            if temp is None:
                temp = _get_val(cd, "temperature_c") or _get_val(cd, "temperature_celsius")
            if temp is not None:
                try:
                    temp = float(temp)
                    if temp <= 5 or temp > 120:
                        temp = None
                except (ValueError, TypeError):
                    temp = None

            wear = _get_val(cd, "wear_percentage")
            life = None
            if wear is not None:
                try:
                    w_num = float(wear)
                    if w_num >= 0:
                        life = max(0.0, 100.0 - w_num)
                except (ValueError, TypeError):
                    pass

            lifetime_w_tb = _get_val(cd, "lifetime_write_tb")
            lifetime_r_tb = _get_val(cd, "lifetime_read_tb")
            lifetime_w_b = _get_val(cd, "lifetime_write_bytes")
            lifetime_r_b = _get_val(cd, "lifetime_read_bytes")

            raw_size = _get_val(cd, "size_gb")
            total_gb = None
            if raw_size is not None:
                try:
                    total_gb = round(float(raw_size), 1)
                except (ValueError, TypeError):
                    total_gb = None

            poh = _get_val(cd, "power_on_hours")
            power_on_hours = None
            if poh is not None:
                try:
                    power_on_hours = round(float(poh), 0)
                except (ValueError, TypeError):
                    power_on_hours = None

            drive_key = f"{dev_id}_{idx}"
            drives_map[drive_key] = {
                "id": dev_id,
                "name": m,
                "media_type": media_type,
                "interface_type": _get_val(cd, "interface_type") or _get_val(cd, "bus_type") or ("NVMe" if media_type == "NVMe" else "SATA"),
                "serial_number": _get_val(cd, "serial_number"),
                "health_status": _get_val(cd, "health_status", "Healthy") or "Healthy",
                "total_gb": total_gb,
                "temperature_c": round(float(temp), 1) if temp is not None else None,
                "power_on_hours": power_on_hours,
                "life_percent": life,
                "data_written_gb": round(float(lifetime_w_tb) * 1024.0, 1) if lifetime_w_tb else None,
                "data_read_gb": round(float(lifetime_r_tb) * 1024.0, 1) if lifetime_r_tb else None,
                "write_bytes": int(lifetime_w_b) if lifetime_w_b else None,
                "read_bytes": int(lifetime_r_b) if lifetime_r_b else None,
                "partitions": [],
                "used_gb": 0.0,
                "free_gb": total_gb or 0.0,
                "used_percent": 0.0,
            }

    # 2. Обогащение данными операций ввода/вывода (из psutil perdisk счетчиков)
    global _LAST_PERDISK_IO, _LAST_PERDISK_TIME
    now_io = time.time()
    elapsed_io = max(0.1, now_io - _LAST_PERDISK_TIME) if _LAST_PERDISK_TIME > 0 else 0.0
    io_counters: Dict[str, Any] = {}
    if psutil is not None and hasattr(psutil, "disk_io_counters"):
        try:
            io_counters = psutil.disk_io_counters(perdisk=True) or {}
        except Exception as io_err:
            logger.debug(f"[router_storage_load] Ошибка сбора perdisk IO counters: {io_err}")

    for k, d in drives_map.items():
        dev_id = str(d.get("id", ""))
        digits = re.findall(r"\d+", dev_id)
        if digits:
            phys_key = f"PhysicalDrive{digits[0]}"
            if phys_key in io_counters:
                io_stat = io_counters[phys_key]
                if d.get("read_bytes") is None or d.get("read_bytes") == 0:
                    d["read_bytes"] = io_stat.read_bytes
                if d.get("write_bytes") is None or d.get("write_bytes") == 0:
                    d["write_bytes"] = io_stat.write_bytes
                if d.get("read_count") is None or d.get("read_count") == 0:
                    d["read_count"] = io_stat.read_count
                if d.get("write_count") is None or d.get("write_count") == 0:
                    d["write_count"] = io_stat.write_count

                # Расчет скоростей чтения и записи
                prev_stat = _LAST_PERDISK_IO.get(phys_key)
                if prev_stat and elapsed_io > 0:
                    r_rate = max(0.0, (io_stat.read_bytes - prev_stat.read_bytes) / elapsed_io)
                    w_rate = max(0.0, (io_stat.write_bytes - prev_stat.write_bytes) / elapsed_io)
                    d["read_rate_raw"] = _format_bytes_rate(r_rate)
                    d["write_rate_raw"] = _format_bytes_rate(w_rate)
                elif d.get("read_rate_raw") is None:
                    d["read_rate_raw"] = "0 B/s"
                if d.get("write_rate_raw") is None:
                    d["write_rate_raw"] = "0 B/s"

        # Форматирование data_written_raw
        w_gb = d.get("data_written_gb")
        w_b = d.get("write_bytes")
        if w_gb and w_gb > 0:
            if w_gb >= 1000:
                d["data_written_raw"] = f"{w_gb / 1024.0:.2f} TB"
            else:
                d["data_written_raw"] = f"{w_gb:,.0f} GB"
        elif w_b and w_b > 0:
            if w_b >= 1024**4:
                d["data_written_raw"] = f"{w_b / (1024**4):.2f} TB"
            elif w_b >= 1024**3:
                d["data_written_raw"] = f"{w_b / (1024**3):.2f} GB"
            else:
                d["data_written_raw"] = f"{w_b / (1024**2):.1f} MB"

        # Форматирование data_read_raw
        r_gb = d.get("data_read_gb")
        r_b = d.get("read_bytes")
        if r_gb and r_gb > 0:
            if r_gb >= 1000:
                d["data_read_raw"] = f"{r_gb / 1024.0:.2f} TB"
            else:
                d["data_read_raw"] = f"{r_gb:,.0f} GB"
        elif r_b and r_b > 0:
            if r_b >= 1024**4:
                d["data_read_raw"] = f"{r_b / (1024**4):.2f} TB"
            elif r_b >= 1024**3:
                d["data_read_raw"] = f"{r_b / (1024**3):.2f} GB"
            else:
                d["data_read_raw"] = f"{r_b / (1024**2):.1f} MB"

    if io_counters:
        _LAST_PERDISK_IO = io_counters
        _LAST_PERDISK_TIME = now_io

    # 3. Сбор логических разделов
    partitions_list: List[DiskPartitionMetric] = []
    if partitions_data is not None:
        for p in partitions_data:
            if isinstance(p, dict):
                p_dev = p.get("device") or p.get("mountpoint") or ""
                p_mount = p.get("mountpoint") or p.get("device") or ""
                p_fstype = str(p.get("fstype", "") or "")
                p_tot = float(p.get("total_gb", 0.0) or 0.0)
                p_used = float(p.get("used_gb", 0.0) or 0.0)
                p_free = float(p.get("free_gb", 0.0) or 0.0)
                p_pct = float(p.get("used_percent") if p.get("used_percent") is not None else (p.get("percent", 0.0) or 0.0))
                partitions_list.append(
                    DiskPartitionMetric(
                        device=p_dev,
                        mountpoint=p_mount,
                        fstype=p_fstype,
                        total_gb=p_tot,
                        used_gb=p_used,
                        free_gb=p_free,
                        used_percent=round(p_pct, 1),
                    )
                )
            elif isinstance(p, DiskPartitionMetric):
                partitions_list.append(p)

    # 4. Привязка разделов к накопителям и вычисление емкости
    # Карта номеров дисков -> ключи накопителей в drives_map
    disk_num_to_keys: Dict[str, List[str]] = {}
    for key, d in drives_map.items():
        dev_id = str(d.get("id", ""))
        digits = re.findall(r"\d+", dev_id)
        if digits:
            disk_num_to_keys.setdefault(digits[0], []).append(key)

    # Карта привязки букв томов к номерам физических дисков через Win32 IOCTL
    disk_letters_map, _ = _resolve_disk_num_to_letters_map()
    letter_to_disk_num: Dict[str, str] = {}
    for dn_str, letters in disk_letters_map.items():
        for let in letters:
            clean_let = let.upper().rstrip("\\")
            letter_to_disk_num[clean_let] = dn_str

    assigned_part_devices = set()

    # 4.1. Привязка разделов по карте IOCTL
    for part in partitions_list:
        clean_dev = part.device.upper().rstrip("\\")
        if not clean_dev.endswith(":"):
            clean_dev = f"{clean_dev}:"
        dn = letter_to_disk_num.get(clean_dev)
        if dn and dn in disk_num_to_keys:
            assigned_part_devices.add(part.device)
            part_label = part.device.rstrip('\\') + '\\'
            for k in disk_num_to_keys[dn]:
                d = drives_map[k]
                if part_label not in d["partitions"]:
                    d["partitions"].append(part_label)
                d["used_gb"] = round(d["used_gb"] + part.used_gb, 1)

    # 4.2. Fallback для несопоставленных разделов (по размеру)
    for part in partitions_list:
        if part.device in assigned_part_devices:
            continue
        part_label = part.device.rstrip('\\') + '\\'
        for d in drives_map.values():
            tot = d.get("total_gb")
            if tot is not None and abs(tot - part.total_gb) <= 5.0 and not d["partitions"]:
                d["partitions"].append(part_label)
                d["used_gb"] = round(d["used_gb"] + part.used_gb, 1)
                assigned_part_devices.add(part.device)
                break

    # 4.3. Вычисление финальных free_gb и used_percent для каждого диска
    for d in drives_map.values():
        tot = d.get("total_gb")
        used = d.get("used_gb", 0.0)
        if tot is not None and tot > 0:
            used_clamped = min(used, tot)
            d["used_gb"] = round(used_clamped, 1)
            d["free_gb"] = round(max(tot - used_clamped, 0.0), 1)
            d["used_percent"] = round((used_clamped / tot) * 100.0, 1)
        else:
            d["used_gb"] = round(used, 1) if used > 0 else None
            d["free_gb"] = None
            d["used_percent"] = None

    def _drive_sort_key(d: Dict[str, Any]) -> int:
        digits = re.findall(r"\d+", str(d.get("id", "")))
        return int(digits[0]) if digits else 999

    drives_list: List[DiskDriveMetric] = [
        DiskDriveMetric(**d) for d in sorted(drives_map.values(), key=_drive_sort_key)
    ]

    # 5. Расчет суммарной сводки по хранилищу
    if drives_list and any(d.total_gb for d in drives_list):
        sum_total = sum(d.total_gb for d in drives_list if d.total_gb is not None)
        sum_used = sum(d.used_gb for d in drives_list if d.used_gb is not None)
        sum_free = max(0.0, sum_total - sum_used)
    elif partitions_list:
        sum_total = sum(p.total_gb for p in partitions_list)
        sum_used = sum(p.used_gb for p in partitions_list)
        sum_free = sum(p.free_gb for p in partitions_list)
    else:
        sum_total = 0.0
        sum_used = 0.0
        sum_free = 0.0

    sum_pct = round((sum_used / sum_total * 100.0), 1) if sum_total > 0 else 0.0

    temps = [d.temperature_c for d in drives_list if d.temperature_c is not None]
    max_temp = max(temps) if temps else None
    avg_temp = round(sum(temps) / len(temps), 1) if temps else None

    summary = StorageSummary(
        total_gb=round(sum_total, 1),
        used_gb=round(sum_used, 1),
        free_gb=round(sum_free, 1),
        used_percent=sum_pct,
        max_temperature_c=max_temp,
        avg_temperature_c=avg_temp,
        drives_count=len(drives_list),
        partitions_count=len(partitions_list),
    )

    return StorageLoadResponse(
        summary=summary,
        drives=drives_list,
        partitions=partitions_list,
        meta={
            "drives_count": len(drives_list),
            "partitions_count": len(partitions_list),
            "source": "cim+psutil",
        },
    )


_CACHED_PHYSICAL_DISKS: List[Any] = []
_LAST_PHYSICAL_DISKS_TIME: float = 0.0
_PHYSICAL_DISKS_CACHE_TTL: float = 60.0


def init_router(
    storage_sensor: Optional[WindowsStorageSensor] = None,
) -> APIRouter:
    """Создаёт роутер /api/v1/panel/storage-load.

    Args:
        storage_sensor: Сенсор дисков WindowsStorageSensor (CIM/WMI).

    Returns:
        APIRouter: Роутер с эндпоинтом GET /api/v1/panel/storage-load.
    """
    router = APIRouter(tags=["Storage Load Panel"])

    @router.get("/api/v1/panel/storage-load", response_model=StorageLoadResponse)
    async def get_panel_storage_load() -> StorageLoadResponse:
        """Возвращает детальную загрузку, температуру и емкость всех накопителей из телеметрии БД."""
        global _CACHED_PHYSICAL_DISKS, _LAST_PHYSICAL_DISKS_TIME
        try:
            sensors: List[Dict[str, Any]] = []
            physical_disks: List[Any] = []
            partitions_data: Optional[List[Dict[str, Any]]] = None
            now = time.time()

            # 1. Проверяем свежий кэш накопителей в памяти
            if _CACHED_PHYSICAL_DISKS and (now - _LAST_PHYSICAL_DISKS_TIME) < _PHYSICAL_DISKS_CACHE_TTL:
                physical_disks = list(_CACHED_PHYSICAL_DISKS)

            # 2. Попытка прочитать актуальные данные дисков и разделов из SQLite телеметрии
            try:
                from apps.windows.telemetry.sqlite import TelemetryStorage
                storage = TelemetryStorage.get_instance(read_only=True)
                storage_data = storage.get_latest_storage_data()
                if not physical_disks and storage_data.get("physical_disks"):
                    physical_disks = storage_data["physical_disks"]
                if storage_data.get("partitions"):
                    partitions_data = storage_data["partitions"]

                if not physical_disks:
                    snap = storage.get_latest_snapshot_full() or {}
                    if snap.get("physical_disks"):
                        physical_disks = snap["physical_disks"]
                    if not partitions_data and snap.get("disks"):
                        partitions_data = snap["disks"]
            except Exception as db_err:
                logger.debug(f"[router_storage_load] Не удалось прочитать накопители из SQLite: {db_err}")

            # 3. Если снимков еще нет — извлекаем инвентарь дисков из SQLite БД или живого WindowsStorageSensor
            if not physical_disks:
                try:
                    physical_disks = storage.get_disk_inventory() or []
                except Exception:
                    physical_disks = []

            if not physical_disks:
                try:
                    sensor = storage_sensor or WindowsStorageSensor()
                    physical_disks = sensor.get_physical_disks(sync=True) or []
                except Exception as ex:
                    logger.debug(f"[router_storage_load] Fallback WindowsStorageSensor error: {ex}")

            if physical_disks:
                _CACHED_PHYSICAL_DISKS = list(physical_disks)
                _LAST_PHYSICAL_DISKS_TIME = now

            return build_storage_load(
                sensors=sensors,
                physical_disks=physical_disks,
                partitions_data=partitions_data,
            )
        except Exception as exc:
            logger.error(f"[router_storage_load] Ошибка опроса накопителей: {exc}", exc_info=True)
            return build_storage_load(sensors=[], physical_disks=[])

    return router


__all__ = [
    "init_router",
    "build_storage_load",
    "DiskDriveMetric",
    "DiskPartitionMetric",
    "StorageSummary",
    "StorageLoadResponse",
    "_detect_media_type",
    "_find_matching_key",
    "extract_smart_temperature",
]

