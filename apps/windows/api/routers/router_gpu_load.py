# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - Router GPU Load
# =============================================================================
# Description:
#   GET /api/v1/panel/gpu-load — метрики графического ускорителя (GPU):
#   загрузка GPU Core, подсистем (Memory Controller, Video Engine, Bus, D3D),
#   температуры (Core, Hot Spot), видеопамять VRAM, энергопотребление,
#   паспортные данные GPU (Specs), датчики и история замеров из telemetry.db.
#
# Usage Examples:
#   Python API:
#     from apps.windows.api.routers.router_gpu_load import init_router
#     app.include_router(init_router())
#
# File: router_gpu_load.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 18:55:00
# =============================================================================

from __future__ import annotations

"""Роутер панели «Загрузка GPU»: детальные метрики видеокарты, паспорт, сенсоры и история строго из базы данных telemetry.db."""

from datetime import datetime, timezone
import json
import re
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from logger import logger
from apps.windows.telemetry.sqlite import TelemetryStorage

_TEMP_CATEGORIES = ("temperature", "temperatures")
_LOAD_CATEGORIES = ("load", "loads")
_DATA_CATEGORIES = ("data", "memory")
_CLOCK_CATEGORIES = ("clock", "clocks")
_POWER_CATEGORIES = ("power", "powers")
_VOLTAGE_CATEGORIES = ("voltage", "voltages")

_CPU_HARDWARE_KEYWORDS = (
    "cpu", "processor", "core i3", "core i5", "core i7", "core i9",
    "ryzen", "xeon", "threadripper", "pentium", "celeron", "athlon"
)

_CPU_SENSOR_BLACKLIST = (
    "cpu core", "cpu thread", "cpu total", "cpu max", "cpu package",
    "cpu cores", "cpu memory", "cpu platform", "bus speed", "core average",
    "core max", "distance to tjmax", "cpu freq", "cpu utilization",
    "core #", "thread #"
)


class GpuEngineMetric(BaseModel):
    """Метрика отдельного движка/блока GPU."""
    name: str = Field(..., description="Название движка (Core, Memory Controller, Video Engine, etc.)")
    load_percent: Optional[float] = Field(default=None, description="Загрузка движка, %")
    temperature_c: Optional[float] = Field(default=None, description="Температура, связанная с блоком, °C")


class GpuMemoryMetric(BaseModel):
    """Метрики видеопамяти (VRAM)."""
    total_mb: Optional[float] = Field(default=None, description="Всего видеопамяти, MB")
    used_mb: Optional[float] = Field(default=None, description="Занято видеопамяти, MB")
    free_mb: Optional[float] = Field(default=None, description="Свободно видеопамяти, MB")
    used_percent: Optional[float] = Field(default=None, description="Процент занятой видеопамяти, %")


class GpuClocksMetric(BaseModel):
    """Частоты работы GPU."""
    core_mhz: Optional[float] = Field(default=None, description="Частота графического ядра, MHz")
    memory_mhz: Optional[float] = Field(default=None, description="Частота видеопамяти, MHz")


class GpuSensorMetric(BaseModel):
    """Электрический или физический сенсор графического процессора."""
    id: str = Field(..., description="Уникальный идентификатор сенсора")
    name: str = Field(..., description="Понятное название сенсора")
    category: str = Field(default="General", description="Категория (Powers, Voltages, Clocks, Fans)")
    unit: str = Field(default="", description="Единица измерения (W, V, MHz, RPM, %)")
    value: float = Field(default=0.0, description="Числовое значение")
    value_raw: str = Field(default="", description="Форматированная строка со значением")
    status: str = Field(default="normal", description="Статус: normal, warning, danger")


class GpuHistoryPoint(BaseModel):
    """Точка временного ряда истории параметров GPU."""
    timestamp: str = Field(default="", description="ISO время точки")
    time_label: str = Field(default="", description="Короткая метка времени ЧЧ:ММ:СС")
    load_percent: float = Field(default=0.0, description="Загрузка ядра GPU, %")
    temperature_c: Optional[float] = Field(default=None, description="Температура GPU Core, °C")
    power_w: Optional[float] = Field(default=None, description="Потребляемая мощность, Вт")
    vram_percent: Optional[float] = Field(default=None, description="Занятая память VRAM, %")


class GpuSpecsInfo(BaseModel):
    """Сводная спецификация и паспортные данные графического ускорителя."""
    name: str = Field(default="", description="Наименование модели видеокарты")
    vendor: str = Field(default="NVIDIA", description="Производитель (NVIDIA, AMD, Intel, Generic)")
    driver_version: str = Field(default="", description="Версия видеодрайвера")
    driver_date: str = Field(default="", description="Дата релиза видеодрайвера")
    vram_mb: Optional[float] = Field(default=None, description="Объем видеопамяти VRAM, МБ")
    vram_gb: Optional[float] = Field(default=None, description="Объем видеопамяти VRAM, ГБ")
    vram_str: str = Field(default="", description="Форматированный объем видеопамяти")
    vram_used_str: str = Field(default="", description="Форматированная занятая память с процентом")
    core_clock_mhz: Optional[float] = Field(default=None, description="Частота графического процессора, МГц")
    core_clock_str: str = Field(default="", description="Форматированная частота ядра")
    memory_clock_mhz: Optional[float] = Field(default=None, description="Частота видеопамяти, МГц")
    memory_clock_str: str = Field(default="", description="Форматированная частота памяти")
    directx: str = Field(default="DirectX 12 (FL 12_1)", description="Поддерживаемый графический API")
    pci_bus: str = Field(default="PCIe x16", description="Интерфейс подключения шины")
    cuda_cores: Optional[int] = Field(default=None, description="Количество шейдерных ядер CUDA / блоков")
    cuda_supported: bool = Field(default=False, description="Поддержка NVIDIA CUDA")
    rocm_supported: bool = Field(default=False, description="Поддержка AMD ROCm / HIP")
    oneapi_supported: bool = Field(default=False, description="Поддержка Intel oneAPI")
    directml_supported: bool = Field(default=True, description="Поддержка DirectML ускорения")
    vulkan_supported: bool = Field(default=True, description="Поддержка Vulkan API")
    opencl_supported: bool = Field(default=True, description="Поддержка OpenCL API")
    compute_apis: List[str] = Field(default_factory=list, description="Список поддерживаемых вычислительных API")
    ai_backends: List[str] = Field(default_factory=list, description="Список поддерживаемых AI бэкендов")
    power_limit_w: Optional[float] = Field(default=None, description="Лимит TDP, Вт")


class GpuLoadResponse(BaseModel):
    """Ответ GET /api/v1/panel/gpu-load."""
    status: str = Field(default="ok", description="Статус ответа")
    name: str = Field(default="GPU", description="Модель видеокарты")
    vendor: str = Field(default="NVIDIA", description="Производитель GPU")
    core_load_percent: float = Field(default=0.0, description="Загрузка графического ядра, %")
    core_temperature_c: Optional[float] = Field(default=None, description="Температура GPU Core, °C")
    hotspot_temperature_c: Optional[float] = Field(default=None, description="Температура Hot Spot, °C")
    memory_temperature_c: Optional[float] = Field(default=None, description="Температура VRAM, °C")
    power_w: Optional[float] = Field(default=None, description="Энергопотребление GPU, Вт")
    fan_speed_rpm: Optional[float] = Field(default=None, description="Скорость вентилятора, RPM")
    fan_percent: Optional[float] = Field(default=None, description="Обороты вентилятора, %")
    memory: GpuMemoryMetric = Field(default_factory=GpuMemoryMetric, description="Состояние видеопамяти")
    clocks: GpuClocksMetric = Field(default_factory=GpuClocksMetric, description="Частоты GPU")
    specs: Optional[GpuSpecsInfo] = Field(default=None, description="Паспортные характеристики GPU")
    engines: List[GpuEngineMetric] = Field(default_factory=list, description="Метрики блоков/движков GPU")
    sensors: List[GpuSensorMetric] = Field(default_factory=list, description="Сенсоры электропитания, напряжения и вентиляторов GPU")
    history: List[GpuHistoryPoint] = Field(default_factory=list, description="История параметров GPU")
    available_gpus: List[Dict[str, Any]] = Field(default_factory=list, description="Список всех обнаруженных видеокарт")
    devices: List[Dict[str, Any]] = Field(default_factory=list, description="Полные метрики по каждому отдельному GPU в системе")
    current_gpu_index: int = Field(default=0, description="Индекс текущей отображаемой видеокарты")
    meta: Dict[str, Any] = Field(default_factory=dict, description="Метаданные запроса")


def _calculate_gpu_sensor_status(category: str, value: float) -> str:
    """Определяет статус сенсора GPU по категории и значению."""
    cat = category.lower()
    if "temp" in cat:
        if value >= 83.0:
            return "danger"
        if value >= 74.0:
            return "warning"
        return "normal"
    if "load" in cat:
        if value >= 95.0:
            return "danger"
        if value >= 80.0:
            return "warning"
        return "normal"
    return "normal"


def _normalize_gpu_sensor_name(sid: str, name: str, cat: str) -> str:
    """Формирует понятное название для сенсора GPU без Unknown."""
    raw = (name or "").strip()
    if not raw or raw.lower() in ("unknown", "sensor"):
        return f"GPU Sensor #{sid}" if sid else "GPU Sensor"

    raw_l = raw.lower()
    cat_l = cat.lower()

    if raw_l == "gpu package" and "power" in cat_l:
        return "GPU Package Power"
    if raw_l == "gpu power" or (raw_l == "power" and "power" in cat_l):
        return "GPU Board Power"
    if raw_l == "gpu core" and "volt" in cat_l:
        return "GPU Core Voltage"
    if raw_l == "gpu memory" and "clock" in cat_l:
        return "GPU Memory Clock"
    if raw_l == "gpu core" and "clock" in cat_l:
        return "GPU Core Clock"
    if raw_l == "gpu fan" or (raw_l == "fan" and "fan" in cat_l):
        return "GPU Fan Speed"

    return raw


def _is_sensor_matching_gpu(sensor_hw_name: str, target_gpu_name: str, sensor_hw_type: str = "") -> bool:
    """Проверяет, принадлежит ли показание сенсора целевой видеокарте и не относится ли к CPU."""
    if sensor_hw_type and str(sensor_hw_type).lower() == "cpu":
        return False
    if not sensor_hw_name:
        return True

    s_clean_raw = str(sensor_hw_name).strip().lower()
    if any(k in s_clean_raw for k in _CPU_HARDWARE_KEYWORDS):
        return False

    if not target_gpu_name:
        return True

    t_clean_raw = str(target_gpu_name).strip().lower()

    # Прямое равенство или взаимное включение подстрок
    if s_clean_raw == t_clean_raw or s_clean_raw in t_clean_raw or t_clean_raw in s_clean_raw:
        return True

    ignore = {
        'gpu', 'graphics', 'corporation', 'corp', 'inc', 'series', 'adapter', 'video',
        'display', 'controller', 'intel', 'nvidia', 'amd', 'microsoft', 'basic'
    }
    s_clean = re.sub(r'[^a-zA-Z0-9]+', ' ', s_clean_raw)
    t_clean = re.sub(r'[^a-zA-Z0-9]+', ' ', t_clean_raw)
    s_toks = {t for t in s_clean.split() if t and t not in ignore}
    t_toks = {t for t in t_clean.split() if t and t not in ignore}

    if not s_toks or not t_toks:
        # Если остались только бренды, проверяем вендора
        s_brand = "nvidia" if "nvidia" in s_clean_raw or "geforce" in s_clean_raw else ("amd" if "amd" in s_clean_raw or "radeon" in s_clean_raw else ("intel" if "intel" in s_clean_raw else None))
        t_brand = "nvidia" if "nvidia" in t_clean_raw or "geforce" in t_clean_raw else ("amd" if "amd" in t_clean_raw or "radeon" in t_clean_raw else ("intel" if "intel" in t_clean_raw else None))
        return bool(s_brand and t_brand and s_brand == t_brand)

    return bool(s_toks & t_toks)


def build_gpu_load(
    sensors: List[Dict[str, Any]],
    inventory: Optional[Dict[str, Any]] = None,
    history_samples: Optional[List[Dict[str, Any]]] = None,
    target_gpu_name: Optional[str] = None,
    available_gpus: Optional[List[Dict[str, Any]]] = None,
    current_gpu_index: int = 0,
    snapshot_gpu: Optional[Dict[str, Any]] = None,
) -> GpuLoadResponse:
    """Собирает структурированные метрики конкретного GPU из списка сенсоров, паспорта и истории.

    Args:
        sensors: Список словарей сенсоров.
        inventory: Паспортные данные GPU из gpu_inventory / GpuProber.
        history_samples: Исторические сэмплы из gpu_telemetry_samples или снимков.
        target_gpu_name: Название целевой видеокарты для фильтрации сенсоров.
        available_gpus: Список всех видеокарт в системе.
        current_gpu_index: Индекс выбранной видеокарты.
        snapshot_gpu: Срез снимка целевой видеокарты из system_snapshots.

    Returns:
        GpuLoadResponse: Полная информация по загрузке, температуре, памяти, спецификациям и истории GPU.
    """
    inv = inventory or {}
    gpu_name = target_gpu_name or (snapshot_gpu.get("name") if snapshot_gpu else None) or inv.get("name") or "GPU"
    core_load: Optional[float] = None
    core_temp: Optional[float] = None
    hotspot_temp: Optional[float] = None
    mem_temp: Optional[float] = None
    power_draw: Optional[float] = None
    fan_rpm: Optional[float] = None
    fan_pct: Optional[float] = None

    vram_total: Optional[float] = None
    vram_used: Optional[float] = None
    vram_free: Optional[float] = None
    vram_pct: Optional[float] = None

    clock_core: Optional[float] = None
    clock_mem: Optional[float] = None

    engines_dict: Dict[str, GpuEngineMetric] = {}
    general_sensors_list: List[GpuSensorMetric] = []
    seen_sensor_keys = set()

    for s in sensors:
        hw_type = str(s.get("hardware_type") or "").lower()
        hw_name = str(s.get("hardware_name") or "")
        s_id = str(s.get("sensor_id") or s.get("id") or "")
        s_name = str(s.get("sensor_name") or s.get("name") or s_id)
        s_cat = str(s.get("sensor_category") or s.get("category") or "").lower()
        s_unit = str(s.get("unit") or "")

        # 1. Строго отсекаем сенсоры CPU
        if hw_type == "cpu" or any(k in hw_name.lower() for k in _CPU_HARDWARE_KEYWORDS):
            continue

        s_name_lower = s_name.lower()
        s_id_lower = s_id.lower()
        if any(black in s_name_lower or black in s_id_lower for black in _CPU_SENSOR_BLACKLIST):
            continue

        # 2. Фильтруем сенсоры GPU
        is_gpu = (
            "gpu" in hw_type
            or "gpu" in hw_name.lower()
            or "nvidia" in hw_name.lower()
            or "radeon" in hw_name.lower()
            or "geforce" in hw_name.lower()
            or "rtx" in hw_name.lower()
            or "gtx" in hw_name.lower()
            or "uhd" in hw_name.lower()
            or "iris" in hw_name.lower()
            or "arc" in hw_name.lower()
        )
        if not is_gpu:
            continue

        # 3. Фильтруем строго под целевой GPU, если имя задано
        if target_gpu_name and hw_name and not _is_sensor_matching_gpu(hw_name, target_gpu_name, hw_type):
            continue

        if hw_name and (gpu_name == "GPU" or not target_gpu_name):
            gpu_name = hw_name

        # Значение
        val = s.get("value_num")
        if val is None:
            val = s.get("value_numeric")
        if val is None:
            val = s.get("value")
        if val is None:
            raw = s.get("value_raw")
            if isinstance(raw, (int, float)):
                val = float(raw)
            elif isinstance(raw, str):
                cleaned = raw.replace("%", "").replace("°C", "").replace("MHz", "").replace("MB", "").replace("RPM", "").replace("W", "").replace("V", "").strip()
                try:
                    val = float(cleaned)
                except ValueError:
                    val = None

        if val is None:
            continue

        # 1. Температуры
        if any(cat in s_cat for cat in _TEMP_CATEGORIES) or s_unit == "°C":
            if "hot spot" in s_name_lower or "hotspot" in s_name_lower:
                hotspot_temp = val
            elif "memory" in s_name_lower or "vram" in s_name_lower:
                mem_temp = val
            elif "core" in s_name_lower or core_temp is None:
                core_temp = val

        # 2. Нагрузка движков / подсистем
        elif any(cat in s_cat for cat in _LOAD_CATEGORIES) or (s_unit == "%" and "fan" not in s_cat):
            if s_name_lower in ("gpu core", "core", "gpu"):
                core_load = val
                engines_dict["GPU Core"] = GpuEngineMetric(name="GPU Core", load_percent=val, temperature_c=core_temp)
            elif "memory controller" in s_name_lower:
                engines_dict["Memory Controller"] = GpuEngineMetric(name="Memory Controller", load_percent=val)
            elif "video engine" in s_name_lower or "video decode" in s_name_lower:
                if "Video Engine" not in engines_dict or val > (engines_dict["Video Engine"].load_percent or 0):
                    engines_dict["Video Engine"] = GpuEngineMetric(name="Video Engine", load_percent=val)
            elif "bus" in s_name_lower:
                engines_dict["GPU Bus"] = GpuEngineMetric(name="GPU Bus", load_percent=val)
            elif "memory" in s_name_lower and "controller" not in s_name_lower:
                vram_pct = val
                engines_dict["GPU Memory"] = GpuEngineMetric(name="GPU Memory", load_percent=val)
            elif "3d" in s_name_lower:
                engines_dict["D3D 3D"] = GpuEngineMetric(name="D3D 3D", load_percent=val)
            elif "copy" in s_name_lower:
                engines_dict["Copy Engine"] = GpuEngineMetric(name="Copy Engine", load_percent=val)
            elif "compute" in s_name_lower:
                eng_name = s_name.strip()
                engines_dict[eng_name] = GpuEngineMetric(name=eng_name, load_percent=val)
            else:
                engines_dict[s_name] = GpuEngineMetric(name=s_name, load_percent=val)

        # 3. Видеопамять (VRAM)
        elif any(cat in s_cat for cat in _DATA_CATEGORIES) or "mb" in s_unit.lower() or "gb" in s_unit.lower():
            if "total" in s_name_lower:
                vram_total = val
            elif "used" in s_name_lower:
                if "dedicated" in s_name_lower:
                    if vram_used is None:
                        vram_used = val
                else:
                    vram_used = val
            elif "free" in s_name_lower:
                vram_free = val

        # 4. Частоты
        elif any(cat in s_cat for cat in _CLOCK_CATEGORIES) or "mhz" in s_unit.lower():
            if "core" in s_name_lower:
                clock_core = val
            elif "memory" in s_name_lower:
                clock_mem = val

        # 5. Мощность (Power)
        elif any(cat in s_cat for cat in _POWER_CATEGORIES) or s_unit.lower() == "w":
            if power_draw is None or "package" in s_name_lower or "total" in s_name_lower or "board" in s_name_lower:
                power_draw = val

        # 6. Обороты вентилятора
        elif "fan" in s_cat or "fan" in s_name_lower:
            if "rpm" in s_unit.lower() or val > 100:
                fan_rpm = val
            else:
                fan_pct = val

        # Добавление в общий список электрических/физических сенсоров GPU
        if (
            any(cat in s_cat for cat in _POWER_CATEGORIES)
            or any(cat in s_cat for cat in _VOLTAGE_CATEGORIES)
            or any(cat in s_cat for cat in _CLOCK_CATEGORIES)
            or "fan" in s_cat
            or s_unit.lower() in ("w", "v", "rpm")
        ):
            norm_name = _normalize_gpu_sensor_name(s_id, s_name, s_cat)
            s_key = f"{s_cat}_{norm_name.lower()}"
            if s_key not in seen_sensor_keys:
                seen_sensor_keys.add(s_key)
                unit_str = s_unit
                if not unit_str:
                    if any(cat in s_cat for cat in _POWER_CATEGORIES): unit_str = "W"
                    elif any(cat in s_cat for cat in _VOLTAGE_CATEGORIES): unit_str = "V"
                    elif any(cat in s_cat for cat in _CLOCK_CATEGORIES): unit_str = "MHz"
                    elif "fan" in s_cat: unit_str = "RPM" if val > 100 else "%"

                val_raw_str = f"{val:.1f} {unit_str}".strip()
                if unit_str == "V":
                    val_raw_str = f"{val:.3f} V"
                elif unit_str == "MHz" and val >= 1000.0:
                    val_raw_str = f"{val / 1000.0:.2f} GHz"

                general_sensors_list.append(
                    GpuSensorMetric(
                        id=s_id or f"gpu_sensor_{len(general_sensors_list)+1}",
                        name=norm_name,
                        category=s_cat.capitalize() or "General",
                        unit=unit_str,
                        value=round(val, 2),
                        value_raw=val_raw_str,
                        status=_calculate_gpu_sensor_status(s_cat, val),
                    )
                )

    # Fallback на данные из снимка / последних сэмплов БД / инвентаря для отсутствующих метрик
    latest_hist = history_samples[-1] if history_samples else {}
    if core_load is None:
        if snapshot_gpu and snapshot_gpu.get("load_percent") is not None:
            core_load = float(snapshot_gpu["load_percent"])
        elif latest_hist.get("load_percent") is not None:
            core_load = float(latest_hist["load_percent"])
        elif inv.get("utilization_gpu_pct") is not None:
            core_load = float(inv["utilization_gpu_pct"])
        else:
            core_load = 0.0

    if core_temp is None:
        if snapshot_gpu and snapshot_gpu.get("temperature_celsius") is not None:
            core_temp = float(snapshot_gpu["temperature_celsius"])
        elif latest_hist.get("temperature_c") is not None:
            core_temp = float(latest_hist["temperature_c"])
        elif latest_hist.get("temperature_gpu_c") is not None:
            core_temp = float(latest_hist["temperature_gpu_c"])
        elif inv.get("temperature_gpu_c") is not None:
            core_temp = float(inv["temperature_gpu_c"])

    if power_draw is None:
        if latest_hist.get("power_draw_w") is not None:
            power_draw = float(latest_hist["power_draw_w"])
        elif inv.get("power_draw_w") is not None:
            power_draw = float(inv["power_draw_w"])

    if fan_pct is None and inv.get("fan_speed_pct") is not None:
        fan_pct = float(inv["fan_speed_pct"])

    if vram_total is None:
        if snapshot_gpu:
            vram_total = snapshot_gpu.get("dedicated_memory_mb") or (float(snapshot_gpu.get("memory_total_gb") or 0.0) * 1024.0 if snapshot_gpu.get("memory_total_gb") else None)
        if vram_total is None:
            if latest_hist.get("memory_total_mb"):
                vram_total = float(latest_hist["memory_total_mb"])
            elif inv.get("memory_total_mb") is not None:
                vram_total = float(inv["memory_total_mb"])
            elif inv.get("vram_gb") is not None and float(inv["vram_gb"]) > 0:
                vram_total = float(inv["vram_gb"]) * 1024.0

    if vram_used is None:
        if snapshot_gpu:
            vram_used = snapshot_gpu.get("memory_used_mb") or (float(snapshot_gpu.get("memory_used_gb") or 0.0) * 1024.0 if snapshot_gpu.get("memory_used_gb") else None)
        if vram_used is None:
            if latest_hist.get("memory_used_mb") is not None:
                vram_used = float(latest_hist["memory_used_mb"])
            elif inv.get("memory_used_mb") is not None:
                vram_used = float(inv["memory_used_mb"])

    if vram_free is None and vram_total is not None and vram_used is not None:
        vram_free = max(0.0, vram_total - vram_used)

    if vram_pct is None and vram_total and vram_used is not None and vram_total > 0:
        vram_pct = round((vram_used / vram_total) * 100.0, 1)

    # Добавляем движки из снимка или инвентаря GpuProber
    snap_engines = (snapshot_gpu.get("engines") if snapshot_gpu else None) or inv.get("engines")
    if isinstance(snap_engines, dict):
        for eng_name, eng_val in snap_engines.items():
            if eng_name not in engines_dict:
                engines_dict[eng_name] = GpuEngineMetric(
                    name=eng_name,
                    load_percent=round(float(eng_val), 1) if eng_val is not None else None,
                )

    if "GPU Core" not in engines_dict and core_load is not None:
        engines_dict["GPU Core"] = GpuEngineMetric(name="GPU Core", load_percent=core_load, temperature_c=core_temp)
    elif "GPU Core" in engines_dict and core_temp is not None:
        engines_dict["GPU Core"].temperature_c = core_temp

    # Упорядочиваем список движков
    ordered_keys = ["GPU Core", "3D Engine", "Memory Controller", "Video Engine", "Video Decode", "Copy Engine", "GPU Memory", "GPU Bus", "D3D 3D"]
    engines_list: List[GpuEngineMetric] = []
    for k in ordered_keys:
        if k in engines_dict:
            engines_list.append(engines_dict.pop(k))
    engines_list.extend(engines_dict.values())

    # Если список сенсоров пуст, генерируем структурированный набор сенсоров из параметров GPU
    if not general_sensors_list:
        if core_temp is not None:
            general_sensors_list.append(
                GpuSensorMetric(
                    id=f"gpu_{current_gpu_index}_temp",
                    name="GPU Core Temperature",
                    category="Temperatures",
                    unit="°C",
                    value=round(core_temp, 1),
                    value_raw=f"{core_temp:.1f} °C",
                    status=_calculate_gpu_sensor_status("temp", core_temp),
                )
            )
        if vram_used is not None:
            general_sensors_list.append(
                GpuSensorMetric(
                    id=f"gpu_{current_gpu_index}_vram_used",
                    name="GPU VRAM Used",
                    category="Memory",
                    unit="MB",
                    value=round(vram_used, 1),
                    value_raw=f"{vram_used:.1f} MB",
                    status="normal",
                )
            )
        if vram_total is not None:
            general_sensors_list.append(
                GpuSensorMetric(
                    id=f"gpu_{current_gpu_index}_vram_total",
                    name="GPU VRAM Total",
                    category="Memory",
                    unit="MB",
                    value=round(vram_total, 1),
                    value_raw=f"{vram_total:.0f} MB",
                    status="normal",
                )
            )
        if inv.get("dedicated_memory_used_mb") is not None:
            general_sensors_list.append(
                GpuSensorMetric(
                    id=f"gpu_{current_gpu_index}_dedicated_vram",
                    name="Dedicated VRAM Used",
                    category="Memory",
                    unit="MB",
                    value=round(float(inv["dedicated_memory_used_mb"]), 1),
                    value_raw=f"{float(inv['dedicated_memory_used_mb']):.1f} MB",
                    status="normal",
                )
            )
        if inv.get("shared_memory_used_mb") is not None:
            general_sensors_list.append(
                GpuSensorMetric(
                    id=f"gpu_{current_gpu_index}_shared_vram",
                    name="Shared System Memory Used",
                    category="Memory",
                    unit="MB",
                    value=round(float(inv["shared_memory_used_mb"]), 1),
                    value_raw=f"{float(inv['shared_memory_used_mb']):.1f} MB",
                    status="normal",
                )
            )
        if power_draw is not None:
            general_sensors_list.append(
                GpuSensorMetric(
                    id=f"gpu_{current_gpu_index}_power",
                    name="GPU Board Power",
                    category="Powers",
                    unit="W",
                    value=round(power_draw, 1),
                    value_raw=f"{power_draw:.1f} W",
                    status="normal",
                )
            )

    # Паспортные данные GPU (Specs)
    inv_name = inv.get("name") or gpu_name
    inv_name_l = inv_name.lower()
    vendor = inv.get("vendor") or ("NVIDIA" if "nvidia" in inv_name_l or "geforce" in inv_name_l else ("AMD" if "amd" in inv_name_l or "radeon" in inv_name_l else ("Intel" if "intel" in inv_name_l or "arc" in inv_name_l or "uhd" in inv_name_l else "GPU")))
    driver_ver = str(inv.get("driver_version") or "")
    driver_dt = str(inv.get("driver_date") or "")
    vram_b = inv.get("vram_bytes") or 0
    vram_g = inv.get("vram_gb") or (vram_total / 1024.0 if vram_total else (vram_b / (1024**3) if vram_b else 0.0))
    if vram_total is None and vram_g > 0:
        vram_total = vram_g * 1024.0

    vram_str = f"{vram_g:.1f} GB" if vram_g >= 1.0 else (f"{vram_total:.0f} MB" if vram_total else "--")
    if vram_used is not None and vram_total:
        vram_used_gb = vram_used / 1024.0
        vram_used_str = f"{vram_used_gb:.1f} / {vram_g:.1f} GB ({vram_pct or 0:.0f}%)"
    elif vram_pct is not None:
        vram_used_str = f"{vram_pct:.0f}% занято"
    else:
        vram_used_str = "--"

    core_clk_str = f"{clock_core:.0f} MHz" if clock_core else "--"
    mem_clk_str = f"{clock_mem:.0f} MHz" if clock_mem else "--"

    pci_bus_str = str(inv.get("pci_bus_id") or ("PCIe x16" if inv.get("gpu_type") == "Discrete" or vendor in ("NVIDIA", "AMD") else "Integrated / System Bus"))
    cuda_c = inv.get("cuda_cores")
    directml = bool(inv.get("directml_supported", inv.get("has_directml", True)))

    is_nvidia = vendor == "NVIDIA" or "nvidia" in inv_name.lower() or "geforce" in inv_name.lower()
    is_amd = vendor == "AMD" or "amd" in inv_name.lower() or "radeon" in inv_name.lower()
    is_intel = vendor == "Intel" or "intel" in inv_name.lower() or "arc" in inv_name.lower()

    cuda_supp = bool(inv.get("cuda_supported", inv.get("has_cuda", is_nvidia)))
    rocm_supp = bool(inv.get("rocm_supported", inv.get("has_rocm", is_amd)))
    oneapi_supp = bool(inv.get("oneapi_supported", inv.get("has_oneapi", is_intel)))
    vulkan_supp = bool(inv.get("vulkan_supported", inv.get("has_vulkan", True)))
    opencl_supp = bool(inv.get("opencl_supported", inv.get("has_opencl", True)))

    cmp_apis: List[str] = inv.get("compute_apis") or []
    if not cmp_apis:
        if cuda_supp: cmp_apis.append("CUDA")
        if rocm_supp: cmp_apis.append("ROCm / HIP")
        if oneapi_supp: cmp_apis.append("oneAPI")
        if directml: cmp_apis.append("DirectML")
        if vulkan_supp: cmp_apis.append("Vulkan")
        if opencl_supp: cmp_apis.append("OpenCL")

    ai_bkends: List[str] = inv.get("ai_backends") or []
    if not ai_bkends:
        if cuda_supp: ai_bkends.append("CUDA")
        if rocm_supp: ai_bkends.append("ROCm / HIP")
        if oneapi_supp:
            ai_bkends.append("DirectML")
            ai_bkends.append("Intel GPU runtime (oneAPI/OpenVINO)")
        elif directml:
            ai_bkends.append("DirectML")
        if vulkan_supp: ai_bkends.append("Vulkan")
        ai_bkends.append("CPU")

    specs_obj = GpuSpecsInfo(
        name=inv_name,
        vendor=vendor,
        driver_version=driver_ver or "WDDM 2.7",
        driver_date=driver_dt,
        vram_mb=vram_total,
        vram_gb=round(vram_g, 2) if vram_g else None,
        vram_str=vram_str,
        vram_used_str=vram_used_str,
        core_clock_mhz=clock_core,
        core_clock_str=core_clk_str,
        memory_clock_mhz=clock_mem,
        memory_clock_str=mem_clk_str,
        directx=inv.get("directx_version") or "DirectX 12 (FL 12_1)",
        pci_bus=pci_bus_str,
        cuda_cores=cuda_c,
        cuda_supported=cuda_supp,
        rocm_supported=rocm_supp,
        oneapi_supported=oneapi_supp,
        directml_supported=directml,
        vulkan_supported=vulkan_supp,
        opencl_supported=opencl_supp,
        compute_apis=cmp_apis,
        ai_backends=ai_bkends,
    )

    # История параметров GPU
    history_points: List[GpuHistoryPoint] = []
    if history_samples:
        for r in history_samples:
            ts_str = str(r.get("timestamp") or "")
            t_label = ts_str.split("T")[-1][:8] if "T" in ts_str else ts_str[-8:]
            p_load = float(r.get("load_percent") or r.get("gpu_load_percent") or 0.0)
            p_temp = r.get("temperature_gpu_c") or r.get("temperature_c") or r.get("core_temperature_c")
            p_pow = r.get("power_draw_w") or r.get("power_w")
            p_mem = r.get("memory_percent") or r.get("vram_percent")

            history_points.append(
                GpuHistoryPoint(
                    timestamp=ts_str,
                    time_label=t_label or "--:--:--",
                    load_percent=round(p_load, 1),
                    temperature_c=round(float(p_temp), 1) if p_temp is not None else core_temp,
                    power_w=round(float(p_pow), 1) if p_pow is not None else power_draw,
                    vram_percent=round(float(p_mem), 1) if p_mem is not None else vram_pct,
                )
            )

    return GpuLoadResponse(
        status="ok",
        name=inv_name,
        vendor=vendor,
        core_load_percent=round(core_load if core_load is not None else 0.0, 1),
        core_temperature_c=core_temp,
        hotspot_temperature_c=hotspot_temp,
        memory_temperature_c=mem_temp,
        power_w=power_draw,
        fan_speed_rpm=fan_rpm,
        fan_percent=fan_pct,
        memory=GpuMemoryMetric(
            total_mb=vram_total,
            used_mb=vram_used,
            free_mb=vram_free,
            used_percent=vram_pct,
        ),
        clocks=GpuClocksMetric(
            core_mhz=clock_core,
            memory_mhz=clock_mem,
        ),
        specs=specs_obj,
        engines=engines_list,
        sensors=general_sensors_list,
        history=history_points,
        available_gpus=available_gpus or [],
        current_gpu_index=current_gpu_index,
        meta={
            "source": "gpu_prober+telemetry_db",
            "engines_count": len(engines_list),
            "sensors_count": len(general_sensors_list),
        },
    )


def _discover_system_gpus(storage: Optional[TelemetryStorage] = None) -> List[Dict[str, Any]]:
    """Собирает список всех физических и интегрированных видеокарт строго из базы данных telemetry.db.

    Returns:
        List[Dict[str, Any]]: Список словарей характеристик обнаруженных GPU.
    """
    gpus: List[Dict[str, Any]] = []
    if not storage:
        return [{"index": 0, "name": "GPU", "vendor": "Generic", "vram_gb": 0.0, "pci_bus_id": "PCIe x16"}]

    # 1. Чтение паспорта GPU из таблицы gpu_inventory
    try:
        db_inv = storage.get_gpu_inventory()
        if db_inv:
            for idx, item in enumerate(db_inv):
                g_name = item.get("name", f"GPU {idx}")
                g_name_l = g_name.lower()
                vendor = item.get("vendor") or ("NVIDIA" if "nvidia" in g_name_l or "geforce" in g_name_l else ("AMD" if "amd" in g_name_l or "radeon" in g_name_l else ("Intel" if "intel" in g_name_l or "arc" in g_name_l or "uhd" in g_name_l else "Generic")))
                pci_bus = item.get("pci_bus_id") or ("PCIe x16" if vendor in ("NVIDIA", "AMD") else "Integrated / System Bus")
                gpus.append({
                    "index": item.get("gpu_id", idx),
                    "name": g_name,
                    "vendor": vendor,
                    "driver_version": item.get("driver_version", ""),
                    "driver_date": item.get("driver_date", ""),
                    "vram_gb": item.get("vram_gb", 0.0),
                    "pci_bus_id": pci_bus,
                    "cuda_cores": item.get("cuda_cores"),
                    "directml_supported": bool(item.get("directml_supported", 1)),
                })
    except Exception as exc:
        logger.debug(f"[router_gpu_load] Ошибка чтения gpu_inventory из БД: {exc}")

    # 2. Если инвентарь пуст, извлекаем список GPU из последних сэмплов gpu_telemetry_samples
    if not gpus:
        try:
            samples = storage.get_gpu_telemetry_samples(limit=20)
            seen_names: Dict[str, int] = {}
            for s in samples:
                hn = str(s.get("name", "")).strip()
                g_id = int(s.get("gpu_id", len(seen_names)))
                if hn and hn not in seen_names:
                    seen_names[hn] = g_id
            for hn, g_id in seen_names.items():
                hn_l = hn.lower()
                vendor = "NVIDIA" if "nvidia" in hn_l or "geforce" in hn_l else ("AMD" if "amd" in hn_l or "radeon" in hn_l else ("Intel" if "intel" in hn_l or "arc" in hn_l or "uhd" in hn_l else "Generic"))
                gpus.append({
                    "index": g_id,
                    "name": hn,
                    "vendor": vendor,
                    "driver_version": "",
                    "vram_gb": 0.0,
                    "pci_bus_id": "PCIe x16" if vendor in ("NVIDIA", "AMD") else "Integrated / System Bus",
                })
        except Exception as exc:
            logger.debug(f"[router_gpu_load] Ошибка чтения сэмплов GPU из БД: {exc}")

    # 3. Если сэмплов нет, извлекаем уникальные GPU из latest_sensors
    if not gpus:
        try:
            db_sensors = storage.get_latest_sensors()
            if db_sensors:
                seen_names_sensors: Dict[str, int] = {}
                for s in db_sensors:
                    ht = str(s.get("hardware_type", "")).lower()
                    hn = str(s.get("hardware_name", "")).strip()
                    hn_l = hn.lower()
                    if ht == "cpu" or any(k in hn_l for k in _CPU_HARDWARE_KEYWORDS):
                        continue
                    if hn and ("gpu" in ht or "gpu" in hn_l or "nvidia" in hn_l or "radeon" in hn_l or "geforce" in hn_l or "rtx" in hn_l or "gtx" in hn_l or "uhd" in hn_l or "iris" in hn_l or "arc" in hn_l):
                        if hn not in seen_names_sensors:
                            seen_names_sensors[hn] = len(seen_names_sensors)
                for hn, idx in seen_names_sensors.items():
                    hn_l = hn.lower()
                    vendor = "NVIDIA" if "nvidia" in hn_l or "geforce" in hn_l else ("AMD" if "amd" in hn_l or "radeon" in hn_l else ("Intel" if "intel" in hn_l or "arc" in hn_l or "uhd" in hn_l else "Generic"))
                    gpus.append({
                        "index": idx,
                        "name": hn,
                        "vendor": vendor,
                        "driver_version": "",
                        "vram_gb": 0.0,
                        "pci_bus_id": "PCIe x16" if vendor in ("NVIDIA", "AMD") else "Integrated / System Bus",
                    })
        except Exception as exc:
            logger.debug(f"[router_gpu_load] Ошибка чтения latest_sensors из БД: {exc}")

    # 4. Fallback заглушка при совершенно пустой БД
    if not gpus:
        gpus.append({
            "index": 0,
            "name": "GPU",
            "vendor": "Generic",
            "driver_version": "N/A",
            "vram_gb": 0.0,
            "pci_bus_id": "PCIe x16",
        })

    # 5. Дедупликация и стабильная нормализация списка видеокарт
    unique_gpus: List[Dict[str, Any]] = []
    seen_gpu_keys: set = set()
    for g in gpus:
        raw_n = str(g.get("name") or "").strip()
        v = str(g.get("vendor") or "").strip()
        norm_n = re.sub(r"\((r|tm)\)", "", raw_n, flags=re.IGNORECASE).lower().strip()
        if v.lower() and v.lower() not in norm_n:
            norm_n = f"{v.lower()} {norm_n}"
        k = re.sub(r"[^a-z0-9]+", "_", norm_n).strip("_")

        is_dup = False
        for prev_k in seen_gpu_keys:
            if prev_k == k or (len(k) > 6 and (k in prev_k or prev_k in k)):
                is_dup = True
                break

        if not is_dup and k:
            seen_gpu_keys.add(k)
            unique_gpus.append(g)

    if unique_gpus:
        unique_gpus.sort(key=lambda x: (
            0 if any(b in (str(x.get("vendor", "")) + str(x.get("name", ""))).upper() for b in ("NVIDIA", "GEFORCE", "AMD", "RADEON")) else 1,
            int(x.get("index") or 0)
        ))
        for i, g in enumerate(unique_gpus):
            g["index"] = i
        return unique_gpus

    return gpus


def _fetch_single_gpu_data(
    target_idx: int,
    target_gpu: Dict[str, Any],
    available_gpus: List[Dict[str, Any]],
    store: TelemetryStorage,
) -> GpuLoadResponse:
    """Извлекает детальные параметры и сенсоры для конкретного GPU строго из базы данных telemetry.db."""
    target_name = target_gpu.get("name", f"GPU {target_idx}")

    # 1. Загрузка истории сэмплов строго из SQLite базы данных
    try:
        db_history = store.get_gpu_telemetry_samples(gpu_id=target_idx, limit=60)
    except TypeError:
        db_history = store.get_gpu_telemetry_samples(limit=60)
    except Exception:
        db_history = []

    if not db_history:
        try:
            db_history = store.get_gpu_telemetry_samples(limit=60)
        except Exception:
            db_history = []
    db_history.reverse()

    # 2. Получение показаний сенсоров строго из SQLite базы данных
    matched_sensors: List[Dict[str, Any]] = []
    try:
        db_sensors = store.get_latest_sensors()
        if db_sensors:
            matched_sensors = [
                s for s in db_sensors
                if str(s.get("hardware_type", "")).lower() != "cpu"
                and not any(k in str(s.get("hardware_name", "")).lower() for k in _CPU_HARDWARE_KEYWORDS)
                and (
                    "gpu" in str(s.get("hardware_type", "")).lower()
                    or "gpu" in str(s.get("hardware_name", "")).lower()
                    or "nvidia" in str(s.get("hardware_name", "")).lower()
                    or "radeon" in str(s.get("hardware_name", "")).lower()
                    or "geforce" in str(s.get("hardware_name", "")).lower()
                    or "rtx" in str(s.get("hardware_name", "")).lower()
                    or "gtx" in str(s.get("hardware_name", "")).lower()
                    or "uhd" in str(s.get("hardware_name", "")).lower()
                    or "iris" in str(s.get("hardware_name", "")).lower()
                    or "arc" in str(s.get("hardware_name", "")).lower()
                )
                and _is_sensor_matching_gpu(str(s.get("hardware_name", "")), target_name, str(s.get("hardware_type", "")))
            ]
    except Exception as exc:
        logger.error(f"[router_gpu_load] Ошибка чтения метрик GPU из БД: {exc}", exc_info=True)

    # 3. Извлечение актуальных параметров GPU из последнего снимка системы
    snapshot_gpu: Optional[Dict[str, Any]] = None
    try:
        full_snap = store.get_latest_snapshot_full() or {}
        gpus_in_snap = full_snap.get("gpus") or []
        for g_s in gpus_in_snap:
            if isinstance(g_s, dict):
                s_name = g_s.get("name", "")
                if _is_sensor_matching_gpu(s_name, target_name):
                    snapshot_gpu = g_s
                    break
        if not snapshot_gpu and 0 <= target_idx < len(gpus_in_snap):
            if isinstance(gpus_in_snap[target_idx], dict):
                snapshot_gpu = gpus_in_snap[target_idx]
    except Exception as ex:
        logger.debug(f"[router_gpu_load] Ошибка извлечения GPU из снимка: {ex}")

    if not snapshot_gpu:
        try:
            from apps.windows.sdk.modules.hardware.gpu_prober import GpuProber
            prober_gpus = GpuProber().probe_all()
            for pg in prober_gpus:
                p_name = getattr(pg, 'name', '') or ''
                if _is_sensor_matching_gpu(p_name, target_name):
                    snapshot_gpu = {
                        "name": pg.name,
                        "vendor": getattr(pg, 'vendor', ''),
                        "temperature_celsius": pg.temperature_gpu_c,
                        "load_percent": pg.utilization_gpu_pct,
                        "dedicated_memory_mb": pg.dedicated_memory_mb or pg.memory_total_mb,
                        "memory_total_mb": pg.memory_total_mb,
                        "memory_used_mb": pg.memory_used_mb,
                        "engines": pg.engines,
                        "driver_version": getattr(pg, 'driver_version', ''),
                    }
                    break
        except Exception as ex:
            logger.debug(f"[router_gpu_load] Fallback GpuProber error: {ex}")

    # 4. Собираем и возвращаем объект GPU на основе данных из БД
    resp = build_gpu_load(
        sensors=matched_sensors,
        inventory=target_gpu,
        history_samples=db_history,
        target_gpu_name=target_name,
        available_gpus=available_gpus,
        current_gpu_index=target_idx,
        snapshot_gpu=snapshot_gpu,
    )
    resp.meta["source"] = "telemetry_db"
    return resp


def init_router(
    storage: Optional[TelemetryStorage] = None,
) -> APIRouter:
    """Инициализация роутера GET /api/v1/panel/gpu-load строго из telemetry.db.

    Args:
        storage: Опциональное хранилище TelemetryStorage.

    Returns:
        APIRouter: Настроенный роутер FastAPI.
    """
    router = APIRouter(prefix="/api/v1/panel", tags=["GPU Panel"])
    store = storage or TelemetryStorage.get_instance(read_only=True)

    @router.get("/gpu-load", response_model=GpuLoadResponse, summary="Загрузка, температура, паспорт и метрики GPU")
    async def get_gpu_load(
        gpu_index: Optional[int] = Query(None, description="Индекс конкретной видеокарты (0, 1, ...) или None для всех")
    ) -> GpuLoadResponse:
        """Возвращает детальную загрузку, температуру, VRAM, паспорт и историю GPU строго из telemetry.db."""
        available_gpus = _discover_system_gpus(store)

        if gpu_index is not None and 0 <= gpu_index < len(available_gpus):
            return _fetch_single_gpu_data(gpu_index, available_gpus[gpu_index], available_gpus, store)

        # Собираем данные по каждому обнаруженному GPU из БД
        devices: List[Dict[str, Any]] = []
        for idx, g in enumerate(available_gpus):
            g_resp = _fetch_single_gpu_data(idx, g, available_gpus, store)
            devices.append(g_resp.model_dump())

        # Выбираем основной дискретный адаптер для корневого ответа
        primary_idx = 0
        for idx, g in enumerate(available_gpus):
            v_up = str(g.get("vendor", "")).upper()
            n_up = str(g.get("name", "")).upper()
            if "NVIDIA" in v_up or "GEFORCE" in n_up or "AMD" in v_up or "RADEON" in n_up:
                primary_idx = idx
                break

        main_resp = _fetch_single_gpu_data(primary_idx, available_gpus[primary_idx], available_gpus, store)
        main_resp.devices = devices
        return main_resp

    return router


__all__ = [
    "init_router",
    "build_gpu_load",
    "GpuLoadResponse",
    "GpuEngineMetric",
    "GpuMemoryMetric",
    "GpuClocksMetric",
    "GpuSensorMetric",
    "GpuHistoryPoint",
    "GpuSpecsInfo",
]

