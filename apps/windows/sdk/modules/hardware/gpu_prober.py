# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Modules Hardware - Gpu Prober
# =============================================================================
# Description:
#   GPU hardware prober supporting NVIDIA (nvidia-smi), AMD (amd-smi), Intel Arc (xpu-smi) and WMI.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.hardware.gpu_prober import GpuDeviceTelemetry
#
#     service = GpuDeviceTelemetry()
#
# File: gpu_prober.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.hardware
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-16 21:01:00
# =============================================================================

from __future__ import annotations
"""GPU hardware prober supporting NVIDIA (nvidia-smi), AMD (amd-smi), Intel Arc (xpu-smi), WMI and WDDM Performance Counters."""

import json
import re
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from logger import logger

try:
    import pythoncom
    import win32com.client
    _HAS_WIN32COM = True
except ImportError:
    _HAS_WIN32COM = False

@dataclass
class GpuDeviceTelemetry:
    """Detailed GPU telemetry metrics with compute backends and capabilities."""
    index: int
    name: str
    vendor: str
    driver_version: str
    temperature_gpu_c: Optional[float] = None
    temperature_memory_c: Optional[float] = None
    utilization_gpu_pct: Optional[float] = None
    utilization_memory_pct: Optional[float] = None
    memory_used_mb: Optional[float] = None
    memory_total_mb: Optional[float] = None
    power_draw_w: Optional[float] = None
    power_limit_w: Optional[float] = None
    fan_speed_pct: Optional[float] = None
    throttle_reasons: List[str] = field(default_factory=list)
    engines: Dict[str, float] = field(default_factory=dict)
    shared_memory_used_mb: Optional[float] = None
    dedicated_memory_used_mb: Optional[float] = None
    gpu_type: str = "Discrete"  # 'Discrete' or 'Integrated'
    dedicated_memory_mb: Optional[float] = None
    shared_memory_mb: Optional[float] = None
    memory_type: str = "Dedicated VRAM"  # 'Dedicated GDDR/HBM' or 'Shared System Memory'
    directx_version: str = "DirectX 12 (FL 12_1)"
    has_cuda: bool = False
    has_rocm: bool = False
    has_oneapi: bool = False
    has_directml: bool = True
    has_vulkan: bool = True
    has_opencl: bool = True
    compute_apis: List[str] = field(default_factory=list)
    ai_backends: List[str] = field(default_factory=list)


@dataclass
class NpuDeviceTelemetry:
    """Detailed NPU accelerator telemetry metrics."""
    index: int
    name: str
    vendor: str
    driver_version: str = ""
    pnp_device_id: str = ""
    status: str = "OK (Активно)"
    tops: Optional[float] = None
    has_directml: bool = True
    has_qnn: bool = False
    has_openvino: bool = False
    ai_backends: List[str] = field(default_factory=list)


def determine_gpu_compute_backends(
    vendor: str,
    name: str,
    memory_total_mb: Optional[float] = None,
    dedicated_mb: Optional[float] = None,
    shared_mb: Optional[float] = None,
) -> Dict[str, Any]:
    """Определяет тип GPU (Integrated/Discrete), память, вычислительные API и AI бэкенды.

    Args:
        vendor: Название производителя (NVIDIA, AMD, Intel, Generic).
        name: Модель видеокарты.
        memory_total_mb: Общий объем памяти видеокарты.
        dedicated_mb: Выделенная память VRAM.
        shared_mb: Общая системная память GPU.

    Returns:
        Dict[str, Any]: Словарь структурированных характеристик GPU.
    """
    v_l = (vendor or '').lower()
    n_l = (name or '').lower()

    is_nvidia = 'nvidia' in v_l or 'geforce' in n_l or 'rtx' in n_l or 'gtx' in n_l or 'quadro' in n_l or 'tesla' in n_l
    is_amd = 'amd' in v_l or 'radeon' in n_l or 'advanced micro devices' in v_l or 'firepro' in n_l
    is_intel = 'intel' in v_l or 'arc' in n_l or 'iris' in n_l or 'uhd' in n_l or 'hd graphics' in n_l

    # Определение типа GPU (Integrated vs Discrete)
    if is_intel:
        if 'arc' in n_l:
            gpu_type = 'Discrete'
            memory_type = 'Dedicated GDDR6'
        else:
            gpu_type = 'Integrated'
            memory_type = 'Shared System Memory'
    elif is_amd:
        if 'radeon(tm) graphics' in n_l or 'vega' in n_l or 'integrated' in n_l:
            gpu_type = 'Integrated'
            memory_type = 'Shared System Memory'
        else:
            gpu_type = 'Discrete'
            memory_type = 'Dedicated GDDR6'
    elif is_nvidia:
        gpu_type = 'Discrete'
        memory_type = 'Dedicated GDDR'
    else:
        if (memory_total_mb and memory_total_mb <= 512) or (dedicated_mb and dedicated_mb <= 512):
            gpu_type = 'Integrated'
            memory_type = 'Shared System Memory'
        else:
            gpu_type = 'Discrete'
            memory_type = 'Dedicated VRAM'

    # Разделение памяти (Dedicated VRAM vs Shared System Memory)
    calc_dedicated_mb = dedicated_mb
    calc_shared_mb = shared_mb

    if gpu_type == 'Integrated':
        if calc_dedicated_mb is None or calc_dedicated_mb == 0:
            calc_dedicated_mb = 128.0
        if calc_shared_mb is None or calc_shared_mb == 0:
            calc_shared_mb = 8192.0
    else:
        if calc_dedicated_mb is None or calc_dedicated_mb == 0:
            calc_dedicated_mb = memory_total_mb or 2048.0
        if calc_shared_mb is None or calc_shared_mb == 0:
            calc_shared_mb = 16384.0

    has_cuda = is_nvidia
    has_rocm = is_amd
    has_oneapi = is_intel
    has_directml = True
    has_vulkan = True
    has_opencl = True
    directx_ver = "DirectX 12 (FL 12_1)"

    compute_apis: List[str] = []
    if has_cuda:
        compute_apis.append("CUDA")
    if has_rocm:
        compute_apis.append("ROCm / HIP")
    if has_oneapi:
        compute_apis.append("oneAPI")
    if has_directml:
        compute_apis.append("DirectML")
    if has_vulkan:
        compute_apis.append("Vulkan")
    if has_opencl:
        compute_apis.append("OpenCL")

    ai_backends: List[str] = []
    if has_cuda:
        ai_backends.append("CUDA")
    if has_rocm:
        ai_backends.append("ROCm / HIP")
    if has_oneapi:
        ai_backends.append("DirectML")
        ai_backends.append("Intel GPU runtime (oneAPI/OpenVINO)")
    elif has_directml:
        ai_backends.append("DirectML")
    if has_vulkan:
        ai_backends.append("Vulkan")
    ai_backends.append("CPU")

    resolved_vendor = 'NVIDIA' if is_nvidia else ('AMD' if is_amd else ('Intel' if is_intel else (vendor or 'Generic')))

    return {
        'vendor': resolved_vendor,
        'gpu_type': gpu_type,
        'memory_type': memory_type,
        'dedicated_memory_mb': calc_dedicated_mb,
        'shared_memory_mb': calc_shared_mb,
        'directx_version': directx_ver,
        'has_cuda': has_cuda,
        'has_rocm': has_rocm,
        'has_oneapi': has_oneapi,
        'has_directml': has_directml,
        'has_vulkan': has_vulkan,
        'has_opencl': has_opencl,
        'compute_apis': compute_apis,
        'ai_backends': ai_backends,
    }


def _normalize_name_tokens(name: str) -> set[str]:
    """Извлекает значимые буквенно-цифровые токены названия GPU для сопоставления."""
    cleaned = re.sub(r'[^a-zA-Z0-9]+', ' ', name.lower())
    ignore_tokens = {'corporation', 'corp', 'inc', 'graphics', 'series', 'display', 'adapter', 'video', 'controller'}
    return {t for t in cleaned.split() if t and t not in ignore_tokens}


def _is_same_gpu_device(name_a: str, name_b: str) -> bool:
    """Проверяет, относятся ли два строковых названия к одному и тому же GPU адаптеру."""
    toks_a = _normalize_name_tokens(name_a)
    toks_b = _normalize_name_tokens(name_b)
    if not toks_a or not toks_b:
        return False
    # Если одно является подмножеством другого или пересечение содержит ключевые номера моделей
    intersection = toks_a & toks_b
    # Ключевые модельные токены (например gt 710, 4080, uhd 630, rtx, rx)
    if len(intersection) >= 2:
        return True
    if toks_a.issubset(toks_b) or toks_b.issubset(toks_a):
        return True
    return False


class GpuProber:
    """Multi-vendor GPU telemetry collector with WDDM Direct3D counters."""

    def __init__(self) -> None:
        """Locate vendor SMI binaries."""
        self._nvidia_smi = shutil.which('nvidia-smi') or shutil.which('nvidia-smi.exe')
        self._amd_smi = shutil.which('amd-smi') or shutil.which('amd-smi.exe')
        self._xpu_smi = shutil.which('xpu-smi') or shutil.which('xpu-smi.exe')

    def probe(self) -> List[GpuDeviceTelemetry]:
        """Алиас для probe_all."""
        return self.probe_all()

    def probe_all(self) -> List[GpuDeviceTelemetry]:
        """Опрашивает все доступные GPU в системе (NVIDIA, AMD, Intel Arc, WMI и WDDM счетчики).

        Независимые внешние опросы выполняются параллельно в пуле потоков.

        Returns:
            List[GpuDeviceTelemetry]: Список обнаруженных видеокарт без дублирования.
        """
        gpus: List[GpuDeviceTelemetry] = []
        with ThreadPoolExecutor(max_workers=4, thread_name_prefix='gpu_probe') as pool:
            nvidia_future = pool.submit(self._probe_nvidia) if self._nvidia_smi else None
            amd_future = pool.submit(self._probe_amd) if self._amd_smi else None
            wmi_future = pool.submit(self._probe_wmi)
            wddm_future = pool.submit(self._query_wddm_counters)

            if nvidia_future:
                gpus.extend(nvidia_future.result() or [])
            if amd_future:
                gpus.extend(amd_future.result() or [])

            # WMI нужен для обнаружения встроенных видеокарт (например Intel UHD)
            for w_gpu in wmi_future.result():
                # Проверяем, не найдена ли уже эта видеокарта через SMI
                already_exists = any(_is_same_gpu_device(w_gpu.name, existing.name) for existing in gpus)
                if not already_exists:
                    gpus.append(w_gpu)

            # Обогащаем данными WDDM / Direct3D счетчиков производительности (движки 3D/Decode/Copy и память)
            luid_memory, luid_engines = wddm_future.result()
        self._enrich_wddm_performance(gpus, luid_memory, luid_engines)

        # Переиндексируем список
        for idx, g in enumerate(gpus):
            g.index = idx

        return gpus

    def _query_wddm_counters(self) -> Tuple[Dict[str, Dict[str, float]], Dict[str, Dict[str, float]]]:
        """Опрашивает счетчики WDDM/Direct3D: память адаптеров и загрузку графических движков.

        Выполняется напрямую через COM/WMI без вызова внешних процессов PowerShell.
        При недоступности COM используется резервный вызов PowerShell.

        Returns:
            Tuple[Dict, Dict]: (память по LUID, загрузка движков по LUID); пустые словари при ошибке.
        """
        luid_memory: Dict[str, Dict[str, float]] = {}
        luid_engines: Dict[str, Dict[str, float]] = {}

        if _HAS_WIN32COM:
            try:
                pythoncom.CoInitialize()
                wmi = win32com.client.GetObject('winmgmts:root\\cimv2')

                mem_rows = wmi.ExecQuery(
                    'SELECT Name, DedicatedUsage, SharedUsage, TotalCommitted '
                    'FROM Win32_PerfFormattedData_GPUPerformanceCounters_GPUAdapterMemory'
                )
                for m in mem_rows:
                    name = str(getattr(m, 'Name', ''))
                    if 'luid_' in name:
                        match = re.search(r'luid_(0x[0-9a-fA-F]+_0x[0-9a-fA-F]+)', name)
                        if match:
                            luid = match.group(1).lower()
                            ded = float(getattr(m, 'DedicatedUsage', 0) or 0.0) / (1024 ** 2)
                            shared = float(getattr(m, 'SharedUsage', 0) or 0.0) / (1024 ** 2)
                            tot = float(getattr(m, 'TotalCommitted', 0) or 0.0) / (1024 ** 2)
                            luid_memory[luid] = {'dedicated_mb': ded, 'shared_mb': shared, 'total_mb': tot}

                eng_rows = wmi.ExecQuery(
                    'SELECT Name, UtilizationPercentage '
                    'FROM Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine'
                )
                for it in eng_rows:
                    name = str(getattr(it, 'Name', ''))
                    if '_luid_' in name and '_engtype_' in name:
                        match = re.search(r'luid_(0x[0-9a-fA-F]+_0x[0-9a-fA-F]+)', name)
                        if match:
                            luid = match.group(1).lower()
                            eng_type = name.split('_engtype_')[-1].strip()
                            if eng_type:
                                val = float(getattr(it, 'UtilizationPercentage', 0) or 0.0)
                                luid_engines.setdefault(luid, {}).setdefault(eng_type, 0.0)
                                luid_engines[luid][eng_type] += val

                return luid_memory, luid_engines
            except Exception as com_exc:
                logger.debug(f'WDDM COM query error, falling back to PowerShell: {com_exc}')

        ps_mem = 'Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUAdapterMemory -ErrorAction SilentlyContinue | Select-Object Name, DedicatedUsage, SharedUsage, TotalCommitted | ConvertTo-Json -Compress'
        ps_eng = 'Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine -ErrorAction SilentlyContinue | Select-Object Name, UtilizationPercentage | ConvertTo-Json -Compress'
        try:
            with ThreadPoolExecutor(max_workers=2, thread_name_prefix='wddm_query') as pool:
                mem_future = pool.submit(subprocess.run, ['powershell', '-NoProfile', '-Command', ps_mem], capture_output=True, text=True, timeout=5)
                eng_future = pool.submit(subprocess.run, ['powershell', '-NoProfile', '-Command', ps_eng], capture_output=True, text=True, timeout=5)
                res_mem = mem_future.result()
                res_eng = eng_future.result()

            mems = json.loads(res_mem.stdout) if res_mem.stdout.strip() else []
            if isinstance(mems, dict):
                mems = [mems]
            for m in mems:
                name = str(m.get('Name', ''))
                if 'luid_' in name:
                    luid_match = re.search(r'luid_(0x[0-9a-fA-F]+_0x[0-9a-fA-F]+)', name)
                    if luid_match:
                        luid = luid_match.group(1).lower()
                        ded = float(m.get('DedicatedUsage') or 0.0) / (1024 ** 2)
                        shared = float(m.get('SharedUsage') or 0.0) / (1024 ** 2)
                        tot = float(m.get('TotalCommitted') or 0.0) / (1024 ** 2)
                        luid_memory[luid] = {'dedicated_mb': ded, 'shared_mb': shared, 'total_mb': tot}

            engs = json.loads(res_eng.stdout) if res_eng.stdout.strip() else []
            if isinstance(engs, dict):
                engs = [engs]
            for it in engs:
                name = str(it.get('Name', ''))
                if '_luid_' in name and '_engtype_' in name:
                    luid_match = re.search(r'luid_(0x[0-9a-fA-F]+_0x[0-9a-fA-F]+)', name)
                    if luid_match:
                        luid = luid_match.group(1).lower()
                        eng_type = name.split('_engtype_')[-1].strip()
                        if eng_type:
                            val = float(it.get('UtilizationPercentage') or 0.0)
                            luid_engines.setdefault(luid, {}).setdefault(eng_type, 0.0)
                            luid_engines[luid][eng_type] += val
        except Exception as exc:
            logger.debug(f'WDDM counters query error: {exc}')
        return luid_memory, luid_engines

    def _enrich_wddm_performance(
        self,
        gpus: List[GpuDeviceTelemetry],
        luid_memory: Dict[str, Dict[str, float]],
        luid_engines: Dict[str, Dict[str, float]],
    ) -> None:
        """Обогащает метрики видеокарт счетчиками WDDM/Direct3D (движки 3D/Video/Copy и память).

        Args:
            gpus: Список видеокарт для обогащения.
            luid_memory: Память адаптеров по LUID (результат _query_wddm_counters).
            luid_engines: Загрузка графических движков по LUID (результат _query_wddm_counters).
        """
        if not gpus:
            return
        try:

            # 3. Сопоставление LUID и адаптеров
            for g in gpus:
                g_vendor = g.vendor.lower()
                is_igpu = "intel" in g_vendor or "generic" in g_vendor or (g.memory_total_mb and g.memory_total_mb <= 2048 and "intel" in g.name.lower())

                matched_luid = None
                if is_igpu:
                    igpu_candidates = [
                        (luid, m['shared_mb']) for luid, m in luid_memory.items()
                        if m.get('dedicated_mb', 0.0) == 0.0
                    ]
                    if igpu_candidates:
                        igpu_candidates.sort(key=lambda x: x[1], reverse=True)
                        matched_luid = igpu_candidates[0][0]
                else:
                    discrete_candidates = [
                        (luid, m['dedicated_mb']) for luid, m in luid_memory.items()
                        if m.get('dedicated_mb', 0.0) > 0.0
                    ]
                    if discrete_candidates:
                        discrete_candidates.sort(key=lambda x: x[1], reverse=True)
                        matched_luid = discrete_candidates[0][0]

                if matched_luid:
                    mem_info = luid_memory.get(matched_luid, {})
                    g.dedicated_memory_used_mb = round(mem_info.get('dedicated_mb', 0.0), 1)
                    g.shared_memory_used_mb = round(mem_info.get('shared_mb', 0.0), 1)
                    if g.memory_used_mb is None:
                        g.memory_used_mb = g.shared_memory_used_mb if is_igpu else g.dedicated_memory_used_mb
                    if is_igpu and (g.memory_total_mb is None or g.memory_total_mb == 0):
                        g.memory_total_mb = round(mem_info.get('total_mb', 1024.0), 1)

                    eng_info = luid_engines.get(matched_luid, {})
                    normalized_engines: Dict[str, float] = {}
                    for eng_name, eng_pct in eng_info.items():
                        clean_eng = eng_name
                        if eng_name == "3D": clean_eng = "3D Engine"
                        elif eng_name == "VideoDecode": clean_eng = "Video Decode"
                        elif eng_name == "VideoProcessing": clean_eng = "Video Processing"
                        elif eng_name == "Copy": clean_eng = "Copy Engine"
                        elif eng_name == "GDI Render": clean_eng = "GDI Render"
                        normalized_engines[clean_eng] = round(eng_pct, 1)

                    if not normalized_engines and is_igpu:
                        normalized_engines = {
                            "3D Engine": 0.0,
                            "Video Decode": 0.0,
                            "Video Processing": 0.0,
                            "Copy Engine": 0.0
                        }

                    g.engines = normalized_engines

                    if g.utilization_gpu_pct is None and normalized_engines:
                        g.utilization_gpu_pct = max(normalized_engines.values())

        except Exception as exc:
            logger.debug(f'WDDM Performance enrichment error: {exc}')

    def _probe_nvidia(self) -> List[GpuDeviceTelemetry]:
        """Query nvidia-smi with CSV query flags."""
        results: List[GpuDeviceTelemetry] = []
        try:
            query = 'index,name,driver_version,temperature.gpu,utilization.gpu,utilization.memory,memory.used,memory.total,power.draw,power.limit,fan.speed'
            cmd = [str(self._nvidia_smi), f'--query-gpu={query}', '--format=csv,noheader,nounits']
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if res.returncode == 0 and res.stdout.strip():
                for line in res.stdout.strip().splitlines():
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) >= 11:
                        gpu_name = parts[1]
                        ram_mb = float(parts[7]) if parts[7] != '[N/A]' else None
                        used_ram_mb = float(parts[6]) if parts[6] != '[N/A]' else None
                        caps = determine_gpu_compute_backends('NVIDIA', gpu_name, memory_total_mb=ram_mb, dedicated_mb=ram_mb)
                        results.append(GpuDeviceTelemetry(
                            index=int(parts[0]) if parts[0].isdigit() else 0,
                            name=gpu_name,
                            vendor='NVIDIA',
                            driver_version=parts[2],
                            temperature_gpu_c=float(parts[3]) if parts[3] != '[N/A]' else None,
                            utilization_gpu_pct=float(parts[4]) if parts[4] != '[N/A]' else None,
                            utilization_memory_pct=float(parts[5]) if parts[5] != '[N/A]' else None,
                            memory_used_mb=used_ram_mb,
                            memory_total_mb=ram_mb,
                            power_draw_w=float(parts[8]) if parts[8] != '[N/A]' else None,
                            power_limit_w=float(parts[9]) if parts[9] != '[N/A]' else None,
                            fan_speed_pct=float(parts[10]) if parts[10] != '[N/A]' else None,
                            gpu_type=caps['gpu_type'],
                            dedicated_memory_mb=caps['dedicated_memory_mb'],
                            shared_memory_mb=caps['shared_memory_mb'],
                            memory_type=caps['memory_type'],
                            directx_version=caps['directx_version'],
                            has_cuda=caps['has_cuda'],
                            has_rocm=caps['has_rocm'],
                            has_oneapi=caps['has_oneapi'],
                            has_directml=caps['has_directml'],
                            has_vulkan=caps['has_vulkan'],
                            has_opencl=caps['has_opencl'],
                            compute_apis=caps['compute_apis'],
                            ai_backends=caps['ai_backends'],
                        ))
        except Exception as e:
            logger.error(f'Error querying nvidia-smi: {e}')
        return results

    def _probe_amd(self) -> List[GpuDeviceTelemetry]:
        """Query amd-smi with JSON output."""
        results: List[GpuDeviceTelemetry] = []
        try:
            cmd = [str(self._amd_smi), 'metric', '--json']
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if res.returncode == 0 and res.stdout.strip():
                data = json.loads(res.stdout)
                items = data if isinstance(data, list) else [data]
                for idx, item in enumerate(items):
                    gpu_name = str(item.get('card_model', 'AMD Radeon GPU'))
                    v_tot = item.get('vram_total')
                    caps = determine_gpu_compute_backends('AMD', gpu_name, memory_total_mb=v_tot, dedicated_mb=v_tot)
                    results.append(GpuDeviceTelemetry(
                        index=idx,
                        name=gpu_name,
                        vendor='AMD',
                        driver_version=str(item.get('driver_version', 'Unknown')),
                        temperature_gpu_c=item.get('temperature_edge'),
                        utilization_gpu_pct=item.get('gpu_utilization'),
                        memory_used_mb=item.get('vram_used'),
                        memory_total_mb=v_tot,
                        power_draw_w=item.get('power_usage'),
                        gpu_type=caps['gpu_type'],
                        dedicated_memory_mb=caps['dedicated_memory_mb'],
                        shared_memory_mb=caps['shared_memory_mb'],
                        memory_type=caps['memory_type'],
                        directx_version=caps['directx_version'],
                        has_cuda=caps['has_cuda'],
                        has_rocm=caps['has_rocm'],
                        has_oneapi=caps['has_oneapi'],
                        has_directml=caps['has_directml'],
                        has_vulkan=caps['has_vulkan'],
                        has_opencl=caps['has_opencl'],
                        compute_apis=caps['compute_apis'],
                        ai_backends=caps['ai_backends'],
                    ))
        except Exception as e:
            logger.error(f'Error querying amd-smi: {e}')
        return results

    def _probe_wmi(self) -> List[GpuDeviceTelemetry]:
        """Query WMI Win32_VideoController as fallback or multi-adapter prober via direct COM or PowerShell."""
        results: List[GpuDeviceTelemetry] = []

        if _HAS_WIN32COM:
            try:
                pythoncom.CoInitialize()
                wmi = win32com.client.GetObject('winmgmts:root\\cimv2')
                vcs = wmi.ExecQuery('SELECT Name, DriverVersion, AdapterRAM FROM Win32_VideoController')
                for idx, item in enumerate(vcs):
                    name = str(getattr(item, 'Name', 'Generic Display Adapter') or 'Generic Display Adapter').strip()
                    raw_ram = getattr(item, 'AdapterRAM', 0)
                    try:
                        ram_bytes = int(raw_ram or 0)
                        # В WMI AdapterRAM 32-битное поле может переполняться в отрицательное
                        if ram_bytes < 0:
                            ram_bytes = abs(ram_bytes)
                    except (ValueError, TypeError):
                        ram_bytes = 0
                    ram_mb = round(ram_bytes / 1024 ** 2, 1) if ram_bytes > 0 else None
                    caps = determine_gpu_compute_backends('', name, memory_total_mb=ram_mb, dedicated_mb=ram_mb)
                    results.append(GpuDeviceTelemetry(
                        index=idx,
                        name=name,
                        vendor=caps['vendor'],
                        driver_version=str(getattr(item, 'DriverVersion', 'N/A') or 'N/A'),
                        memory_total_mb=ram_mb,
                        gpu_type=caps['gpu_type'],
                        dedicated_memory_mb=caps['dedicated_memory_mb'],
                        shared_memory_mb=caps['shared_memory_mb'],
                        memory_type=caps['memory_type'],
                        directx_version=caps['directx_version'],
                        has_cuda=caps['has_cuda'],
                        has_rocm=caps['has_rocm'],
                        has_oneapi=caps['has_oneapi'],
                        has_directml=caps['has_directml'],
                        has_vulkan=caps['has_vulkan'],
                        has_opencl=caps['has_opencl'],
                        compute_apis=caps['compute_apis'],
                        ai_backends=caps['ai_backends'],
                    ))
                if results:
                    return results
            except Exception as com_exc:
                logger.debug(f'WMI GPU COM probe error, falling back to PowerShell: {com_exc}')

        try:
            ps_cmd = 'Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion, AdapterRAM | ConvertTo-Json -Compress'
            res = subprocess.run(['powershell', '-NoProfile', '-Command', ps_cmd], capture_output=True, text=True, timeout=5)
            if res.returncode == 0 and res.stdout.strip():
                raw = json.loads(res.stdout)
                items = [raw] if isinstance(raw, dict) else raw
                for idx, item in enumerate(items):
                    name = str(item.get('Name', 'Generic Display Adapter')).strip()
                    ram_bytes = int(item.get('AdapterRAM') or 0)
                    ram_mb = round(ram_bytes / 1024 ** 2, 1) if ram_bytes > 0 else None
                    caps = determine_gpu_compute_backends('', name, memory_total_mb=ram_mb, dedicated_mb=ram_mb)
                    results.append(GpuDeviceTelemetry(
                        index=idx,
                        name=name,
                        vendor=caps['vendor'],
                        driver_version=str(item.get('DriverVersion', 'N/A')),
                        memory_total_mb=ram_mb,
                        gpu_type=caps['gpu_type'],
                        dedicated_memory_mb=caps['dedicated_memory_mb'],
                        shared_memory_mb=caps['shared_memory_mb'],
                        memory_type=caps['memory_type'],
                        directx_version=caps['directx_version'],
                        has_cuda=caps['has_cuda'],
                        has_rocm=caps['has_rocm'],
                        has_oneapi=caps['has_oneapi'],
                        has_directml=caps['has_directml'],
                        has_vulkan=caps['has_vulkan'],
                        has_opencl=caps['has_opencl'],
                        compute_apis=caps['compute_apis'],
                        ai_backends=caps['ai_backends'],
                    ))
        except Exception as e:
            logger.error(f'WMI GPU probe error: {e}')
        return results

    def probe_npus(self) -> List[NpuDeviceTelemetry]:
        """Опрашивает систему на наличие специализированных нейропроцессоров (NPU / AI Accelerators).

        Returns:
            List[NpuDeviceTelemetry]: Список обнаруженных NPU ускорителей.
        """
        npus: List[NpuDeviceTelemetry] = []
        try:
            ps_cmd = (
                "Get-CimInstance Win32_PnPEntity -ErrorAction SilentlyContinue | Where-Object { "
                "($_.PNPClass -eq 'ComputeAccelerator') -or "
                "($_.Name -match '\\b(NPU|AI Boost|Hexagon)\\b' -and "
                "$_.Name -notmatch '(?i)(input|audio|cable|mouse|keyboard|hid|receiver|hub|controller|print|bluetooth|camera)') "
                "} | Select-Object Name, Manufacturer, DeviceID, PNPClass, Status | ConvertTo-Json -Compress"
            )
            res = subprocess.run(['powershell', '-NoProfile', '-Command', ps_cmd], capture_output=True, text=True, timeout=5)
            if res.returncode == 0 and res.stdout.strip():
                raw = json.loads(res.stdout)
                items = [raw] if isinstance(raw, dict) else raw
                blacklist_terms = (
                    'input', 'mouse', 'keyboard', 'cable', 'audio', 'sound', 'hid',
                    'receiver', 'touchpad', 'gamepad', 'hub', 'print', 'camera', 'microphone'
                )
                idx = 0
                for item in items:
                    name = str(item.get('Name', '')).strip()
                    mfg = str(item.get('Manufacturer', '')).strip()
                    dev_id = str(item.get('DeviceID', '')).strip().lower()
                    pnp_class = str(item.get('PNPClass', '')).strip().lower()
                    status = str(item.get('Status', 'OK')).strip() or 'OK (Активно)'
                    name_l = name.lower()
                    mfg_l = mfg.lower()

                    # Фильтрация периферии и ложных совпадений
                    if any(term in name_l for term in blacklist_terms):
                        continue
                    if any(term in dev_id for term in ('hid', 'kbd', 'mou', 'usb\\vid', 'bth')):
                        if pnp_class != 'computeaccelerator':
                            continue
                    if pnp_class in ('hidclass', 'keyboard', 'mouse', 'media', 'sound'):
                        continue

                    # Проверяем наличие явных NPU идентификаторов
                    is_npu = (
                        pnp_class == 'computeaccelerator'
                        or bool(re.search(r'\b(npu|ai boost|hexagon|snapdragon x|ryzen ai)\b', name_l))
                    )
                    if not is_npu:
                        continue

                    if 'intel' in name_l or 'intel' in mfg_l:
                        vendor = 'Intel'
                        ai_backends = ['DirectML', 'Intel OpenVINO NPU', 'ONNX DirectML']
                        has_openvino = True
                        has_qnn = False
                    elif 'qualcomm' in name_l or 'hexagon' in name_l or 'snapdragon' in name_l:
                        vendor = 'Qualcomm'
                        ai_backends = ['Qualcomm QNN', 'DirectML NPU', 'ONNX QNN']
                        has_openvino = False
                        has_qnn = True
                    elif 'amd' in name_l or 'ryzen' in name_l:
                        vendor = 'AMD'
                        ai_backends = ['AMD Ryzen AI (Vitis)', 'DirectML NPU', 'ONNX DirectML']
                        has_openvino = False
                        has_qnn = False
                    else:
                        vendor = mfg or 'Generic NPU'
                        ai_backends = ['DirectML NPU', 'ONNX DirectML']
                        has_openvino = False
                        has_qnn = False

                    npus.append(NpuDeviceTelemetry(
                        index=idx,
                        name=name,
                        vendor=vendor,
                        status=status,
                        has_directml=True,
                        has_qnn=has_qnn,
                        has_openvino=has_openvino,
                        ai_backends=ai_backends,
                    ))
                    idx += 1
        except Exception as exc:
            logger.debug(f'NPU probe error: {exc}')
        return npus

