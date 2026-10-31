# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry - Collector
# =============================================================================
# Description:
#   Движок сбора системных метрик, аппаратной структуры и показателей производительности.
#
# Usage Examples:
#   Python API:
#     from apps.windows.telemetry.collector import SystemCollector
#
#     service = SystemCollector()
#
# File: collector.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-30 11:15:00
# =============================================================================

from __future__ import annotations
"""Движок сбора системных метрик, аппаратной структуры и показателей производительности."""

import asyncio
import ctypes
import getpass
import os
import platform
import socket
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False
from logger import logger
from .models import (
    BatteryMetrics,
    CloudStorageInfo,
    CpuMetrics,
    DiskIoMetrics,
    DiskPartitionMetrics,
    GpuMetrics,
    HardwareNode,
    HardwareSensor,
    MemoryMetrics,
    MonitorInfo,
    NetworkInterfaceMetrics,
    NetworkPortMetrics,
    NpuMetrics,
    OfficeSuiteInfo,
    PhysicalDiskHealth,
    ProcessLifecycleEvent,
    ProcessMetrics,
    ProcessNetworkActivity,
    ProcessProvenanceInfo,
    ProcessProvenanceReport,
    RamStickInfo,
    SystemCoreMetrics,
    SystemHardwareQuick,
    SystemHealthAlerts,
    SystemSnapshot,
    WindowsUpdateInfo,
)
from .sensors import get_hardware_sensors
from .hardware_collector import HardwareCollector
from apps.windows.analytics.hardware_auditor import HardwareAuditor
from apps.windows.analytics.hardware_history_manager import HardwareHistoryManager
from apps.windows.analytics.startup_history_manager import StartupHistoryManager
from .hardware_tree import HardwareTreeBuilder
from .history_mixin import TelemetryHistoryMixin
from .network_activity import NetworkActivityCollector
from .process_metrics import ProcessMetricsCollector
from .software_info import SoftwareInfoCollector
from .sqlite import TelemetryStorage

NPU_CACHE_TTL_SEC: float = 3600.0

class SystemCollector(TelemetryHistoryMixin):
    """Telemetry collector for system load, hardware devices, and processes."""

    def __init__(
        self,
        auditor: Optional[HardwareAuditor] = None,
        hardware_collector: Optional[HardwareCollector] = None,
        history_manager: Optional[HardwareHistoryManager] = None,
        startup_history_manager: Optional[StartupHistoryManager] = None,
        storage: Optional[TelemetryStorage] = None,
    ) -> None:
        """Initialize telemetry collector with timing, I/O baseline, hardware collector/auditor, startup history, and storage."""
        self._last_disk_io = psutil.disk_io_counters() if PSUTIL_AVAILABLE else None
        self._last_net_io = psutil.net_io_counters(pernic=True) if PSUTIL_AVAILABLE else None
        self._last_time = time.time()
        self._last_disk_time = self._last_time
        self._cpu_model_cached: Optional[str] = None
        self._identity_cached: Optional[Dict[str, Any]] = None
        self._monitors_cached: Optional[List[MonitorInfo]] = None
        self._ram_sticks_cached: Optional[List[RamStickInfo]] = None
        self._ram_sticks_cache_time: float = 0.0
        self._physical_disks_cached: Optional[List[PhysicalDiskHealth]] = None
        self._physical_disks_cache_time: float = 0.0
        self._npus_cached: Optional[List[NpuMetrics]] = None
        self._npus_cache_time: float = 0.0
        self._volume_meta_cache: Dict[str, Dict[str, Any]] = {}
        self._net_usage_collector: Optional[Any] = None
        self._last_net_adapter_stats: Dict[str, Any] = {}
        self._last_net_adapter_stats_time: float = 0.0
        self.storage = storage or TelemetryStorage.get_instance()
        self.hardware_collector = hardware_collector or HardwareCollector(storage=self.storage)
        self.auditor = auditor or HardwareAuditor(collector=self.hardware_collector, storage=self.storage)
        self.history_manager = history_manager or HardwareHistoryManager()
        self._hardware_tree_builder = HardwareTreeBuilder(self)
        self._process_collector = ProcessMetricsCollector()
        self._network_activity = NetworkActivityCollector()
        self._software_info = SoftwareInfoCollector()
        self.startup_history_manager = startup_history_manager or StartupHistoryManager()

    def get_system_identity(self) -> Dict[str, Any]:
        """Collect host identity, current user, system language, and locale parameters.

        Returns:
            Dict[str, Any]: Detailed system identity and localization dictionary.
        """
        if self._identity_cached:
            return self._identity_cached
        hostname = socket.gethostname()
        domain = os.environ.get('USERDOMAIN', '')
        username_raw = os.environ.get('USERNAME') or getpass.getuser()
        full_username = f'{domain}\\{username_raw}' if domain and domain != hostname else username_raw
        user_locale = 'ru-RU'
        system_locale = 'ru-RU'
        codepage = 'UTF-8'
        input_languages: List[str] = []
        if os.name == 'nt':
            try:
                buf = ctypes.create_unicode_buffer(100)
                if ctypes.windll.kernel32.GetUserDefaultLocaleName(buf, 100):
                    user_locale = buf.value or 'ru-RU'
                if ctypes.windll.kernel32.GetSystemDefaultLocaleName(buf, 100):
                    system_locale = buf.value or 'ru-RU'
                acp = ctypes.windll.kernel32.GetACP()
                oemcp = ctypes.windll.kernel32.GetOEMCP()
                codepage = f'ACP: {acp} | OEM: {oemcp} (UTF-8)'
                count = ctypes.windll.user32.GetKeyboardLayoutList(0, None)
                if count > 0:
                    hkls = (ctypes.c_void_p * count)()
                    ctypes.windll.user32.GetKeyboardLayoutList(count, hkls)
                    lang_map = {1049: 'Русский (RU)', 1033: 'English (US)', 1037: 'עברית (IL)', 1058: 'Українська (UA)', 1031: 'Deutsch (DE)', 1036: 'Français (FR)'}
                    for h in hkls:
                        lang_id = (h.value if hasattr(h, 'value') and h.value else int(h)) & 65535
                        lang_name = lang_map.get(lang_id, f'Layout 0x{lang_id:04X}')
                        if lang_name not in input_languages:
                            input_languages.append(lang_name)
            except Exception as ex:
                logger.debug(f'Failed to query native Windows locale: {ex}')
        if not input_languages:
            input_languages = ['Русский (RU)', 'English (US)']
        try:
            tz_offset = datetime.now().astimezone().strftime('%z')
            tz_name = datetime.now().astimezone().tzname() or time.tzname[0]
            timezone_str = f'{tz_name} (UTC{tz_offset[:3]}:{tz_offset[3:]})'
        except Exception:
            timezone_str = 'UTC+03:00'
        def _format_lang_display(locale_tag: str) -> str:
            if not locale_tag:
                return ''
            tag_clean = locale_tag.strip()
            tag_lower = tag_clean.lower()
            if 'ru' in tag_lower:
                return f'Русский (Россия) [{tag_clean}]'
            elif 'he' in tag_lower:
                return f'עברית (ישראל) [{tag_clean}]'
            elif 'en' in tag_lower:
                return f'English (United States) [{tag_clean}]'
            elif 'uk' in tag_lower:
                return f'Українська (Україна) [{tag_clean}]'
            elif 'de' in tag_lower:
                return f'Deutsch (Deutschland) [{tag_clean}]'
            elif 'fr' in tag_lower:
                return f'Français (France) [{tag_clean}]'
            elif 'es' in tag_lower:
                return f'Español (España) [{tag_clean}]'
            elif 'zh' in tag_lower:
                return f'中文 (China) [{tag_clean}]'
            elif 'ja' in tag_lower:
                return f'日本語 (Japan) [{tag_clean}]'
            return tag_clean

        sys_lang_display = _format_lang_display(user_locale)
        os_build = platform.version() or '10.0.26200'
        os_install_date = ''
        os_install_language = ''
        if os.name == 'nt':
            try:
                import winreg
                # Попытка получить оригинальный язык установки из реестра (InstallLanguage)
                for access in (winreg.KEY_READ | winreg.KEY_WOW64_64KEY, winreg.KEY_READ):
                    try:
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SYSTEM\CurrentControlSet\Control\Nls\Language', 0, access) as key:
                            val, _ = winreg.QueryValueEx(key, 'InstallLanguage')
                            if val:
                                lcid = int(str(val), 16)
                                buf_lcid = ctypes.create_unicode_buffer(100)
                                if ctypes.windll.kernel32.LCIDToLocaleName(lcid, buf_lcid, 100, 0):
                                    tag = buf_lcid.value
                                    if tag:
                                        os_install_language = _format_lang_display(tag)
                                        break
                    except Exception:
                        pass
                if not os_install_language:
                    sys_ui_lang = ctypes.windll.kernel32.GetSystemDefaultUILanguage()
                    buf_lcid = ctypes.create_unicode_buffer(100)
                    if ctypes.windll.kernel32.LCIDToLocaleName(sys_ui_lang, buf_lcid, 100, 0):
                        tag = buf_lcid.value
                        if tag:
                            os_install_language = _format_lang_display(tag)
            except Exception as ex:
                logger.debug(f'Failed to query Windows InstallLanguage: {ex}')

            try:
                import winreg
                for access in (winreg.KEY_READ | winreg.KEY_WOW64_64KEY, winreg.KEY_READ):
                    try:
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Windows NT\CurrentVersion', 0, access) as key:
                            try:
                                val, _ = winreg.QueryValueEx(key, 'InstallDate')
                                if val and int(val) > 0:
                                    os_install_date = datetime.fromtimestamp(int(val)).strftime('%d.%m.%Y %H:%M')
                                    break
                            except Exception:
                                pass
                            try:
                                val, _ = winreg.QueryValueEx(key, 'InstallTime')
                                if val and int(val) > 0:
                                    epoch_sec = (int(val) / 10000000.0) - 11644473600.0
                                    if epoch_sec > 0:
                                        os_install_date = datetime.fromtimestamp(epoch_sec).strftime('%d.%m.%Y %H:%M')
                                        break
                            except Exception:
                                pass
                    except Exception:
                        continue
            except Exception as ex:
                logger.debug(f'Failed to query Windows InstallDate from registry: {ex}')
        workgroup = 'WORKGROUP'
        if os.name == 'nt':
            try:
                from ctypes import wintypes
                netapi32 = ctypes.windll.netapi32
                lp_buf = wintypes.LPWSTR()
                join_stat = wintypes.DWORD()
                if netapi32.NetGetJoinInformation(None, ctypes.byref(lp_buf), ctypes.byref(join_stat)) == 0:
                    if lp_buf.value:
                        workgroup = lp_buf.value
                    netapi32.NetApiBufferFree(lp_buf)
            except Exception as ex:
                logger.debug(f'Failed to query Windows Workgroup: {ex}')
        self._identity_cached = {
            'hostname': hostname,
            'workgroup': workgroup,
            'username': full_username,
            'os_build': os_build,
            'os_install_date': os_install_date,
            'system_language': sys_lang_display,
            'os_install_language': os_install_language,
            'user_locale': user_locale,
            'system_locale': system_locale,
            'timezone': timezone_str,
            'codepage': codepage,
            'input_languages': input_languages
        }
        return self._identity_cached

    async def _resolve_cpu_model(self) -> str:
        """Resolve CPU brand/model name from registry, platform or WMI.

        Returns:
            str: Resolved CPU model name.
        """
        if self._cpu_model_cached:
            return self._cpu_model_cached
        model = ''
        if os.name == 'nt':
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'HARDWARE\DESCRIPTION\System\CentralProcessor\0') as key:
                    val, _ = winreg.QueryValueEx(key, 'ProcessorNameString')
                    if val and val.strip():
                        model = val.strip()
            except Exception:
                pass
        if not model:
            model = platform.processor() or ''
        if os.name == 'nt' and (not model or 'Intel64' in model or 'AMD64' in model):
            try:
                from src.utils.com_worker import com_worker

                def _get_cpu():
                    import pythoncom
                    pythoncom.CoInitialize()
                    import wmi
                    w = wmi.WMI()
                    cpus = w.Win32_Processor()
                    return str(cpus[0].Name).strip() if cpus else None
                res = await com_worker.run(_get_cpu)
                if res:
                    model = res
            except Exception:
                pass
        if not model:
            model = f'{platform.machine()} {os.cpu_count() or 1}-Core Processor'
        self._cpu_model_cached = model
        return model

    async def get_cpu_metrics(self) -> CpuMetrics:
        """Collect real-time CPU utilization and architecture details.

        Returns:
            CpuMetrics: Current CPU performance metrics.
        """
        logical_cores = os.cpu_count() or 1
        physical_cores = max(1, logical_cores // 2) if logical_cores > 1 else 1
        if PSUTIL_AVAILABLE:
            per_core = psutil.cpu_percent(interval=None, percpu=True)
            total = round(sum(per_core) / max(len(per_core), 1), 1) if per_core else 0.0
            physical = psutil.cpu_count(logical=False) or physical_cores
            logical = psutil.cpu_count(logical=True) or logical_cores
            freq_mhz = 0.0
            try:
                freq = psutil.cpu_freq()
                if freq:
                    freq_mhz = round(freq.current, 1)
            except Exception:
                pass
            return CpuMetrics(model=await self._resolve_cpu_model(), architecture=platform.machine(), physical_cores=physical, logical_cores=logical, total_percent=total, per_core_percent=per_core, frequency_mhz=freq_mhz)
        return CpuMetrics(model=await self._resolve_cpu_model(), architecture=platform.machine(), physical_cores=physical_cores, logical_cores=logical_cores, total_percent=10.0, per_core_percent=[10.0] * logical_cores, frequency_mhz=2400.0)

    def get_memory_metrics(self) -> MemoryMetrics:
        """Collect RAM, swap, Commit Charge, and Kernel Pool memory consumption.

        Использует нативный C-FFI вызов GetPerformanceInfo (psapi.dll) для получения
        объема выделенной виртуальной памяти (CommitTotal / CommitLimit) и пулов ядра
        (Paged / Non-Paged Pool) за < 0.02 мс.

        Returns:
            MemoryMetrics: Current memory usage statistics.
        """
        commit_total_gb: Optional[float] = None
        commit_limit_gb: Optional[float] = None
        commit_pct: Optional[float] = None
        pool_paged_mb: Optional[float] = None
        pool_nonpaged_mb: Optional[float] = None

        if os.name == 'nt':
            try:
                class PERFORMANCE_INFORMATION(ctypes.Structure):
                    _fields_ = [
                        ('cb', ctypes.c_ulong),
                        ('CommitTotal', ctypes.c_size_t),
                        ('CommitLimit', ctypes.c_size_t),
                        ('CommitPeak', ctypes.c_size_t),
                        ('PhysicalTotal', ctypes.c_size_t),
                        ('PhysicalAvailable', ctypes.c_size_t),
                        ('SystemCache', ctypes.c_size_t),
                        ('KernelTotal', ctypes.c_size_t),
                        ('KernelPaged', ctypes.c_size_t),
                        ('KernelNonpaged', ctypes.c_size_t),
                        ('PageSize', ctypes.c_size_t),
                        ('HandleCount', ctypes.c_ulong),
                        ('ProcessCount', ctypes.c_ulong),
                        ('ThreadCount', ctypes.c_ulong),
                    ]
                perf = PERFORMANCE_INFORMATION()
                perf.cb = ctypes.sizeof(PERFORMANCE_INFORMATION)
                if ctypes.windll.psapi.GetPerformanceInfo(ctypes.byref(perf), perf.cb):
                    page_sz = perf.PageSize or 4096
                    commit_total_gb = round((perf.CommitTotal * page_sz) / (1024 ** 3), 2)
                    commit_limit_gb = round((perf.CommitLimit * page_sz) / (1024 ** 3), 2)
                    if perf.CommitLimit > 0:
                        commit_pct = round((perf.CommitTotal / perf.CommitLimit) * 100.0, 1)
                    pool_paged_mb = round((perf.KernelPaged * page_sz) / (1024 ** 2), 1)
                    pool_nonpaged_mb = round((perf.KernelNonpaged * page_sz) / (1024 ** 2), 1)
            except Exception:
                pass

        if PSUTIL_AVAILABLE:
            vm = psutil.virtual_memory()
            sm = psutil.swap_memory()
            return MemoryMetrics(
                total_gb=round(vm.total / 1024 ** 3, 2),
                available_gb=round(vm.available / 1024 ** 3, 2),
                used_gb=round((vm.total - vm.available) / 1024 ** 3, 2),
                percent=round(vm.percent, 1),
                swap_total_gb=round(sm.total / 1024 ** 3, 2),
                swap_used_gb=round(sm.used / 1024 ** 3, 2),
                swap_percent=round(sm.percent, 1),
                commit_total_gb=commit_total_gb,
                commit_limit_gb=commit_limit_gb,
                commit_percent=commit_pct,
                pool_paged_mb=pool_paged_mb,
                pool_nonpaged_mb=pool_nonpaged_mb,
            )
        total_ram_gb = 16.0
        used_ram_gb = 8.0
        if os.name == 'nt':
            try:

                class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong), ('ullTotalPhys', ctypes.c_ulonglong), ('ullAvailPhys', ctypes.c_ulonglong), ('ullTotalPageFile', ctypes.c_ulonglong), ('ullAvailPageFile', ctypes.c_ulonglong), ('ullTotalVirtual', ctypes.c_ulonglong), ('ullAvailVirtual', ctypes.c_ulonglong), ('sullAvailExtendedVirtual', ctypes.c_ulonglong)]
                stat = MEMORYSTATUSEX()
                stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                    total_ram_gb = round(stat.ullTotalPhys / 1024 ** 3, 2)
                    avail_ram_gb = round(stat.ullAvailPhys / 1024 ** 3, 2)
                    used_ram_gb = round(total_ram_gb - avail_ram_gb, 2)
                    percent = round(stat.dwMemoryLoad, 1)
                    return MemoryMetrics(
                        total_gb=total_ram_gb,
                        available_gb=avail_ram_gb,
                        used_gb=used_ram_gb,
                        percent=percent,
                        swap_total_gb=round(stat.ullTotalPageFile / 1024 ** 3, 2),
                        swap_used_gb=round((stat.ullTotalPageFile - stat.ullAvailPageFile) / 1024 ** 3, 2),
                        swap_percent=round((1.0 - stat.ullAvailPageFile / max(stat.ullTotalPageFile, 1)) * 100, 1),
                        commit_total_gb=commit_total_gb,
                        commit_limit_gb=commit_limit_gb,
                        commit_percent=commit_pct,
                        pool_paged_mb=pool_paged_mb,
                        pool_nonpaged_mb=pool_nonpaged_mb,
                    )
            except Exception:
                pass
        return MemoryMetrics(
            total_gb=total_ram_gb,
            available_gb=total_ram_gb - used_ram_gb,
            used_gb=used_ram_gb,
            percent=50.0,
            swap_total_gb=16.0,
            swap_used_gb=2.0,
            swap_percent=12.5,
            commit_total_gb=commit_total_gb,
            commit_limit_gb=commit_limit_gb,
            commit_percent=commit_pct,
            pool_paged_mb=pool_paged_mb,
            pool_nonpaged_mb=pool_nonpaged_mb,
        )

    def get_gpu_metrics(self) -> List[GpuMetrics]:
        """Collect GPU accelerator load, VRAM, and capabilities.

        Returns:
            List[GpuMetrics]: Detected GPU devices with telemetry.
        """
        gpus: List[GpuMetrics] = []
        try:
            from apps.windows.sdk.modules.hardware.gpu_prober import GpuProber, determine_gpu_compute_backends
            prober = GpuProber()
            gpu_list = prober.probe_all()
            for g in gpu_list:
                vendor = getattr(g, 'vendor', '') or ''
                name = getattr(g, 'name', '') or ''
                caps = determine_gpu_compute_backends(
                    vendor,
                    name,
                    memory_total_mb=g.memory_total_mb,
                    dedicated_mb=g.dedicated_memory_mb or (g.memory_total_mb if getattr(g, 'gpu_type', '') == 'Discrete' else None),
                    shared_mb=g.shared_memory_mb,
                )
                gpus.append(GpuMetrics(
                    name=g.name,
                    vendor=caps['vendor'],
                    gpu_type=caps['gpu_type'],
                    memory_total_gb=round((g.memory_total_mb or 0.0) / 1024.0, 2),
                    memory_used_gb=round((g.memory_used_mb or 0.0) / 1024.0, 2),
                    dedicated_memory_mb=caps['dedicated_memory_mb'],
                    shared_memory_mb=caps['shared_memory_mb'],
                    memory_type=caps['memory_type'],
                    directx_version=caps['directx_version'],
                    load_percent=g.utilization_gpu_pct,
                    temperature_celsius=g.temperature_gpu_c,
                    has_cuda=caps['has_cuda'],
                    has_rocm=caps['has_rocm'],
                    has_oneapi=caps['has_oneapi'],
                    has_directml=caps['has_directml'],
                    has_vulkan=caps['has_vulkan'],
                    has_opencl=caps['has_opencl'],
                    compute_apis=caps['compute_apis'],
                    ai_backends=caps['ai_backends'],
                    engines=g.engines,
                ))
        except Exception as ex:
            logger.debug(f'Ошибка сбора метрик GPU через GpuProber: {ex}')
        if not gpus:
            gpus.append(GpuMetrics(
                name='Integrated Display Controller',
                vendor='Generic',
                gpu_type='Integrated',
                memory_total_gb=0.0,
                dedicated_memory_mb=128.0,
                shared_memory_mb=8192.0,
                memory_type='Shared System Memory',
                directx_version='DirectX 12 (FL 12_1)',
                has_cuda=False,
                has_rocm=False,
                has_oneapi=False,
                has_directml=True,
                has_vulkan=True,
                has_opencl=True,
                compute_apis=['DirectML', 'Vulkan', 'OpenCL'],
                ai_backends=['DirectML', 'Vulkan', 'CPU'],
            ))
        return gpus

    def get_npu_metrics(self) -> List[NpuMetrics]:
        """Collect NPU neural accelerator devices and AI capabilities.

        Результат кэшируется на NPU_CACHE_TTL_SEC секунд: набор NPU-устройств статичен,
        а PnP-опрос через PowerShell занимает ~0,6 с. При ошибке опроса кэш не заполняется.

        Returns:
            List[NpuMetrics]: Detected NPU devices.
        """
        now = time.time()
        if self._npus_cached is not None and now - self._npus_cache_time < NPU_CACHE_TTL_SEC:
            return list(self._npus_cached)
        npus: List[NpuMetrics] = []
        try:
            from apps.windows.sdk.modules.hardware.gpu_prober import GpuProber
            prober = GpuProber()
            npu_list = prober.probe_npus()
            for n in npu_list:
                npus.append(NpuMetrics(
                    name=n.name,
                    vendor=n.vendor,
                    driver_version=n.driver_version,
                    pnp_device_id=getattr(n, 'pnp_device_id', ''),
                    status=n.status,
                    tops=n.tops,
                    has_directml=n.has_directml,
                    has_qnn=n.has_qnn,
                    has_openvino=n.has_openvino,
                    ai_backends=n.ai_backends,
                ))
            self._npus_cached = npus
            self._npus_cache_time = now
        except Exception as ex:
            logger.debug(f'Ошибка сбора метрик NPU: {ex}')
        return list(npus)

    def get_disk_metrics(self) -> tuple[List[DiskPartitionMetrics], DiskIoMetrics]:
        """Collect disk partitions capacity, read/write rates, and average I/O latency (ms/op).

        Статические атрибуты разделов (метка тома, тип устройства через GetVolumeInformationW / QueryDosDeviceW)
        кэшируются в памяти для исключения лишних системных вызовов на каждом тике.

        Returns:
            tuple[List[DiskPartitionMetrics], DiskIoMetrics]: Partitions and I/O rates with latency.
        """
        partitions: List[DiskPartitionMetrics] = []
        io_metrics = DiskIoMetrics()
        if PSUTIL_AVAILABLE:
            for part in psutil.disk_partitions(all=False):
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    cached_meta = self._volume_meta_cache.get(part.mountpoint)
                    if cached_meta is None:
                        vol_name = ''
                        is_virtual = False
                        drive_type = 'Fixed'
                        if os.name == 'nt':
                            try:
                                vol_buf = ctypes.create_unicode_buffer(1024)
                                fs_buf = ctypes.create_unicode_buffer(1024)
                                mount_root = part.mountpoint if part.mountpoint.endswith('\\') else f'{part.mountpoint}\\'
                                if ctypes.windll.kernel32.GetVolumeInformationW(mount_root, vol_buf, 1024, None, None, None, fs_buf, 1024):
                                    vol_name = vol_buf.value
                                dos_buf = ctypes.create_unicode_buffer(1024)
                                clean_dev = part.device.rstrip('\\')
                                ctypes.windll.kernel32.QueryDosDeviceW(clean_dev, dos_buf, 1024)
                                dos_dev = dos_buf.value
                                if 'google' in vol_name.lower() or '@' in vol_name or 'onedrive' in vol_name.lower() or ('dropbox' in vol_name.lower()) or ('volume{' in dos_dev.lower() and 'harddiskvolume' not in dos_dev.lower()):
                                    is_virtual = True
                                    drive_type = 'Google Drive' if 'google' in vol_name.lower() or '@' in vol_name else 'Cloud / Virtual'
                            except Exception:
                                pass
                        cached_meta = {
                            'vol_name': vol_name or None,
                            'is_virtual': is_virtual,
                            'drive_type': drive_type,
                        }
                        self._volume_meta_cache[part.mountpoint] = cached_meta

                    partitions.append(DiskPartitionMetrics(
                        device=part.device,
                        mountpoint=part.mountpoint,
                        fstype=part.fstype,
                        total_gb=round(usage.total / 1024 ** 3, 2),
                        used_gb=round(usage.used / 1024 ** 3, 2),
                        free_gb=round(usage.free / 1024 ** 3, 2),
                        percent=round(usage.percent, 1),
                        volume_name=cached_meta['vol_name'],
                        is_virtual=cached_meta['is_virtual'],
                        drive_type=cached_meta['drive_type'],
                    ))
                except (PermissionError, OSError):
                    continue
            now = time.time()
            elapsed = max(now - getattr(self, '_last_disk_time', self._last_time), 0.1)
            current_io = psutil.disk_io_counters()
            if current_io and self._last_disk_io:
                delta_rb = max(0, current_io.read_bytes - self._last_disk_io.read_bytes)
                delta_wb = max(0, current_io.write_bytes - self._last_disk_io.write_bytes)
                delta_rc = max(0, current_io.read_count - self._last_disk_io.read_count)
                delta_wc = max(0, current_io.write_count - self._last_disk_io.write_count)
                delta_rt = max(0, getattr(current_io, 'read_time', 0) - getattr(self._last_disk_io, 'read_time', 0))
                delta_wt = max(0, getattr(current_io, 'write_time', 0) - getattr(self._last_disk_io, 'write_time', 0))

                io_metrics.read_bytes_per_sec = delta_rb / elapsed
                io_metrics.write_bytes_per_sec = delta_wb / elapsed
                io_metrics.read_count_per_sec = delta_rc / elapsed
                io_metrics.write_count_per_sec = delta_wc / elapsed
                if delta_rc > 0:
                    io_metrics.read_latency_ms = round(delta_rt / delta_rc, 2)
                if delta_wc > 0:
                    io_metrics.write_latency_ms = round(delta_wt / delta_wc, 2)
                total_io_ms = delta_rt + delta_wt
                io_metrics.busy_percent = round(min(100.0, (total_io_ms / (elapsed * 1000.0)) * 100.0), 1)
            self._last_disk_io = current_io
            self._last_disk_time = now
        else:
            drive = 'C:\\' if os.name == 'nt' else '/'
            try:
                import shutil
                total, used, free = shutil.disk_usage(drive)
                partitions.append(DiskPartitionMetrics(device='C:' if os.name == 'nt' else '/', mountpoint=drive, fstype='NTFS' if os.name == 'nt' else 'ext4', total_gb=round(total / 1024 ** 3, 2), used_gb=round(used / 1024 ** 3, 2), free_gb=round(free / 1024 ** 3, 2), percent=round(used / max(total, 1) * 100, 1)))
            except Exception:
                pass
        return (partitions, io_metrics)

    def get_network_metrics(self) -> List[NetworkInterfaceMetrics]:
        """Collect network interface statuses and throughput rates.

        Returns:
            List[NetworkInterfaceMetrics]: Network adapters metrics.
        """
        interfaces: List[NetworkInterfaceMetrics] = []
        now = time.time()
        from .telemetry_config import get_telemetry_config_manager
        net_stats_ttl = get_telemetry_config_manager().get_cache_ttl('network_adapter_stats_ttl_sec', 15.0)
        if not self._last_net_adapter_stats or (now - self._last_net_adapter_stats_time) >= net_stats_ttl:
            try:
                from apps.windows.network.network_usage import WindowsNetworkUsageCollector
                if self._net_usage_collector is None:
                    self._net_usage_collector = WindowsNetworkUsageCollector()
                stats_list = self._net_usage_collector.get_adapter_statistics()
                self._last_net_adapter_stats = {s.name.lower(): s for s in stats_list}
                self._last_net_adapter_stats_time = now
            except Exception as ex:
                logger.debug(f'Failed to fetch adapter stats in SystemCollector: {ex}')
        adapter_stats_map = self._last_net_adapter_stats

        if PSUTIL_AVAILABLE:
            addrs = psutil.net_if_addrs()
            stats = psutil.net_if_stats()
            current_net_io = psutil.net_io_counters(pernic=True)
            elapsed = max(now - self._last_time, 0.1)
            for name, addr_list in addrs.items():
                stat = stats.get(name)
                is_up = stat.isup if stat else True
                speed = stat.speed if stat else 0
                ips = [a.address for a in addr_list if a.family == socket.AF_INET]
                sent_rate = 0.0
                recv_rate = 0.0
                if current_net_io and name in current_net_io and self._last_net_io and (name in self._last_net_io):
                    cur = current_net_io[name]
                    prev = self._last_net_io[name]
                    sent_rate = max(0.0, (cur.bytes_sent - prev.bytes_sent) / elapsed)
                    recv_rate = max(0.0, (cur.bytes_recv - prev.bytes_recv) / elapsed)
                st_info = adapter_stats_map.get(name.lower())
                interfaces.append(NetworkInterfaceMetrics(name=name, is_up=is_up, speed_mbps=speed, bytes_sent_per_sec=sent_rate, bytes_recv_per_sec=recv_rate, ip_addresses=ips, statistics=st_info))
            self._last_net_io = current_net_io
        else:
            try:
                host_ip = socket.gethostbyname(socket.gethostname())
            except Exception:
                host_ip = '127.0.0.1'
            interfaces.append(NetworkInterfaceMetrics(name='Primary Network Adapter', is_up=True, speed_mbps=1000, bytes_sent_per_sec=0.0, bytes_recv_per_sec=0.0, ip_addresses=[host_ip]))
        return interfaces

    def get_network_profile_fast(self) -> Dict[str, Any]:
        """Быстрое получение профиля сетевого подключения и статуса обнаружения без внешних подпроцессов.

        Returns:
            Dict[str, Any]: Словарь с характеристиками текущей сети (категория, имя, статус обнаружения).
        """
        category = "Public"
        net_name = "Network"
        if os.name == "nt":
            try:
                import winreg
                key_path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\NetworkList\Profiles"
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                    cnt, _, _ = winreg.QueryInfoKey(key)
                    for i in range(cnt):
                        sub = winreg.EnumKey(key, i)
                        with winreg.OpenKey(key, sub) as sk:
                            pname, _ = winreg.QueryValueEx(sk, "ProfileName")
                            cat, _ = winreg.QueryValueEx(sk, "Category")
                            category = "Public" if cat == 0 else ("Private" if cat == 1 else "Domain")
                            net_name = pname
                            break
            except Exception:
                pass

        discovery_enabled = False
        if os.name == "nt" and PSUTIL_AVAILABLE:
            try:
                s = psutil.win_service_get("FDResPub")
                discovery_enabled = (s.status() == "running")
            except Exception:
                discovery_enabled = False

        return {
            "status": "ok",
            "current_category": category,
            "primary_interface_alias": net_name,
            "primary_interface_index": None,
            "is_discovery_enabled": discovery_enabled,
        }

    def get_network_usage_report(self, period_minutes: int = 1440):
        """Получить глубокий отчет сетевого потребления за период для AI диагностики.

        Args:
            period_minutes: Интервал отчета в минутах.

        Returns:
            NetworkUsagePeriodReport: Полная сводка сетевой статистики за период.
        """
        from apps.windows.network.network_usage import WindowsNetworkUsageCollector
        collector = WindowsNetworkUsageCollector()
        return collector.get_traffic_period_summary(period_minutes=period_minutes)

    def get_disk_usage_report(self, period_minutes: int = 1440, force_refresh_smart: bool = False):
        """Получить глубокий отчет использования дискового I/O и SMART за период для AI диагностики.

        Args:
            period_minutes: Интервал отчета в минутах (по умолчанию 1440 = 24 часа).
            force_refresh_smart: Принудительно опросить физические диски.

        Returns:
            DiskUsagePeriodReport: Полная сводка дискового I/O и SMART-показателей за период.
        """
        from apps.windows.telemetry.storage_usage import WindowsStorageUsageCollector
        collector = WindowsStorageUsageCollector()
        return collector.get_disk_usage_period_report(period_minutes=period_minutes, force_refresh_smart=force_refresh_smart)




    def get_top_processes(self, limit: Any = 25, sort_by: str = 'cpu') -> List[ProcessMetrics]:
        """Retrieve active processes sorted by resource consumption (делегирует ProcessMetricsCollector).

        Args:
            limit: Maximum processes to return (0 for all).
            sort_by: Attribute to sort by ('cpu', 'memory'/'ram', 'handles'/'descriptors').

        Returns:
            List[ProcessMetrics]: Ranked process metrics.
        """
        return self._process_collector.get_top_processes(limit=limit, sort_by=sort_by)

    def get_battery_metrics(self) -> BatteryMetrics:
        """Collect laptop or UPS battery charge level and AC power status.

        Returns:
            BatteryMetrics: Current battery and power status.
        """
        if PSUTIL_AVAILABLE and hasattr(psutil, 'sensors_battery'):
            try:
                bat = psutil.sensors_battery()
                if bat is not None:
                    return BatteryMetrics(has_battery=True, percent=round(bat.percent, 1), power_plugged=bat.power_plugged, secs_left=bat.secsleft if bat.secsleft > 0 else None, power_profile='AC / Battery')
            except Exception as ex:
                logger.debug(f'Battery probe failed: {ex}')
        return BatteryMetrics(has_battery=False, percent=None, power_plugged=True, secs_left=None, power_profile='AC Mains / Desktop')

    def get_physical_disks_health(self, force: bool = False) -> List[PhysicalDiskHealth]:
        """Собрать данные о физических дисках, SMART, типах носителей и здоровье.

        В сценариях API (tc.ps1) данные читаются строго из SQLite базы данных telemetry.db
        без вызова тяжелого опроса WMI/CIM.
        Прямой опрос оборудования через WindowsStorageSensor выполняется только при force=True (в демоне tlm.ps1).

        Args:
            force: Принудительное обновление данных накопителей через WindowsStorageSensor (только для tlm.ps1).

        Returns:
            List[PhysicalDiskHealth]: Список обнаруженных физических накопителей.
        """
        now = time.time()
        from .telemetry_config import get_telemetry_config_manager
        phys_disk_ttl = get_telemetry_config_manager().get_cache_ttl('physical_disks_health_ttl_sec', 43200.0)
        if not force and self._physical_disks_cached is not None and now - self._physical_disks_cache_time < phys_disk_ttl:
            return self._physical_disks_cached

        # 1. Попытка прочитать физические диски из базы данных SQLite
        if not force and self.storage:
            try:
                storage_data = self.storage.get_latest_storage_data()
                if storage_data and storage_data.get("physical_disks"):
                    disks: List[PhysicalDiskHealth] = []
                    for d in storage_data["physical_disks"]:
                        disks.append(PhysicalDiskHealth(
                            device_id=str(d.get("device_id") or f"Disk {len(disks)}"),
                            model=str(d.get("model") or d.get("friendly_name") or d.get("name") or "Physical Drive"),
                            serial_number=str(d.get("serial_number")) if d.get("serial_number") and d.get("serial_number") != "N/A" else None,
                            media_type=str(d.get("media_type") or "SSD"),
                            size_gb=round(float(d.get("size_gb") or 0.0), 1),
                            health_status=str(d.get("health_status") or "Healthy"),
                            operational_status=str(d.get("operational_status") or "OK"),
                            temperature_celsius=float(d.get("temperature_celsius") or d.get("temperature_c") or 0.0) if (d.get("temperature_celsius") is not None or d.get("temperature_c") is not None) else None,
                            interface_type=str(d.get("interface_type") or d.get("bus_type") or "NVMe"),
                            lifetime_read_bytes=d.get("lifetime_read_bytes"),
                            lifetime_write_bytes=d.get("lifetime_write_bytes"),
                            lifetime_read_tb=d.get("lifetime_read_tb"),
                            lifetime_write_tb=d.get("lifetime_write_tb"),
                            power_on_hours=d.get("power_on_hours"),
                            wear_percentage=d.get("wear_percentage"),
                        ))
                    if disks:
                        self._physical_disks_cached = disks
                        self._physical_disks_cache_time = now
                        return disks
            except Exception as ex:
                logger.debug(f"Не удалось прочитать physical_disks из БД: {ex}")

        # 2. Прямой опрос через WindowsStorageSensor при force=True или отсутствии дисков в БД
        disks: List[PhysicalDiskHealth] = []
        if os.name == 'nt':
            try:
                from apps.windows.sdk.modules.storage_manager.core.windows_storage_sensor import WindowsStorageSensor
                sensor = WindowsStorageSensor(ttl_sec=43200.0)
                phys_disks = sensor.get_physical_disks(force_refresh=force, sync=True)
                for d in phys_disks:
                    disks.append(PhysicalDiskHealth(
                        device_id=d.device_id,
                        model=d.model or d.friendly_name or 'Physical Drive',
                        serial_number=d.serial_number if d.serial_number and d.serial_number != 'N/A' else None,
                        media_type=d.media_type or 'SSD',
                        size_gb=round(d.size_gb, 1) if d.size_gb else 0.0,
                        health_status=d.health_status or 'Healthy',
                        operational_status=d.operational_status or 'OK',
                        temperature_celsius=d.temperature_c,
                        interface_type=d.bus_type or 'NVMe',
                        lifetime_read_bytes=d.lifetime_read_bytes,
                        lifetime_write_bytes=d.lifetime_write_bytes,
                        lifetime_read_tb=d.lifetime_read_tb,
                        lifetime_write_tb=d.lifetime_write_tb,
                        power_on_hours=d.power_on_hours,
                        wear_percentage=d.wear_percentage,
                    ))
            except Exception as ex:
                logger.debug(f'Ошибка сбора физических дисков через WindowsStorageSensor: {ex}')

        if not disks:
            disks.append(PhysicalDiskHealth(
                device_id='Disk 0',
                model='System Drive (NVMe/SSD)',
                serial_number=None,
                media_type='SSD',
                size_gb=512.0,
                health_status='Healthy',
                operational_status='OK',
                interface_type='NVMe',
            ))
        self._physical_disks_cached = disks
        self._physical_disks_cache_time = now
        return disks

    async def get_ram_sticks(self) -> List[RamStickInfo]:
        """Collect physical memory stick (SPD) details via WMI.

        Returns:
            List[RamStickInfo]: Installed physical RAM modules.
        """
        now = time.time()
        if self._ram_sticks_cached is not None and now - self._ram_sticks_cache_time < 60.0:
            return self._ram_sticks_cached
        sticks: List[RamStickInfo] = []
        if os.name == 'nt':
            from src.utils.com_worker import com_worker

            async def _probe():

                def _do_probe():
                    try:
                        import wmi
                    except ImportError:
                        return []
                    _sticks: List[RamStickInfo] = []
                    try:
                        w = wmi.WMI()
                        mems = w.Win32_PhysicalMemory()
                        type_map = {20: 'DDR', 21: 'DDR2', 24: 'DDR3', 26: 'DDR4', 34: 'DDR5'}
                        for m in mems:
                            cap_gb = round(int(m.Capacity or 0) / 1024 ** 3, 1)
                            speed = int(m.Speed or m.ConfiguredClockSpeed or 3200)
                            m_type = type_map.get(m.SMBIOSMemoryType, 'DDR4/DDR5')
                            _sticks.append(RamStickInfo(bank_label=str(m.BankLabel or m.DeviceLocator or 'DIMM').strip(), capacity_gb=cap_gb, speed_mhz=speed, manufacturer=str(m.Manufacturer or 'Generic').strip(), part_number=str(m.PartNumber or '').strip(), memory_type=m_type))
                    except Exception as err:
                        logger.debug(f'WMI Win32_PhysicalMemory query failed: {err}')
                    return _sticks
                return await com_worker.run(_do_probe)
            try:
                sticks = await _probe()
            except Exception as ex:
                logger.debug(f'Failed to query physical memory sticks: {ex}')
        self._ram_sticks_cached = sticks
        self._ram_sticks_cache_time = now
        return sticks

    def get_listening_ports(self, limit: int = 15) -> List[NetworkPortMetrics]:
        """Collect active listening TCP/UDP sockets (делегирует NetworkActivityCollector).

        Args:
            limit: Maximum listening ports to return.

        Returns:
            List[NetworkPortMetrics]: Active listening ports.
        """
        return self._network_activity.get_listening_ports(limit=limit)

    def get_process_network_activity(self, limit: int = 50, only_internet: bool = False) -> List[ProcessNetworkActivity]:
        """Collect per-process network connections (делегирует NetworkActivityCollector).

        Args:
            limit: Maximum connections to return.
            only_internet: Return only connections to external addresses.

        Returns:
            List[ProcessNetworkActivity]: Process network activity records.
        """
        return self._network_activity.get_process_network_activity(limit=limit, only_internet=only_internet)


    def get_health_alerts(self) -> SystemHealthAlerts:
        """Check system reliability indicators and pending reboot status.

        Returns:
            SystemHealthAlerts: Consolidated system health alert indicators.
        """
        reboot_pending = False
        if os.name == 'nt':
            try:
                import winreg
                reboot_keys = ['SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\WindowsUpdate\\Auto Update\\RebootRequired', 'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Component Based Servicing\\RebootPending']
                for k in reboot_keys:
                    try:
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, k):
                            reboot_pending = True
                            break
                    except OSError:
                        pass
            except Exception:
                pass
        alert_msg = 'Требуется перезагрузка для обновлений Windows' if reboot_pending else 'Система работает стабильно'
        return SystemHealthAlerts(reboot_pending=reboot_pending, critical_events_count=0, latest_alert=alert_msg)

    def get_monitors(self) -> List[MonitorInfo]:
        """Collect connected display monitors, resolutions and refresh rates.

        Returns:
            List[MonitorInfo]: Detected active display monitors.
        """
        if self._monitors_cached is not None:
            return self._monitors_cached
        monitors: List[MonitorInfo] = []
        if os.name == 'nt':
            try:
                import ctypes.wintypes
                user32 = ctypes.windll.user32

                class DISPLAY_DEVICEW(ctypes.Structure):
                    _fields_ = [('cb', ctypes.wintypes.DWORD), ('DeviceName', ctypes.wintypes.WCHAR * 32), ('DeviceString', ctypes.wintypes.WCHAR * 128), ('StateFlags', ctypes.wintypes.DWORD), ('DeviceID', ctypes.wintypes.WCHAR * 128), ('DeviceKey', ctypes.wintypes.WCHAR * 128)]
                # Опрос WMI WmiMonitorID для сопоставления точных EDID названий, производителей и серийных номеров
                wmi_monitors: List[Dict[str, str]] = []
                try:
                    import win32com.client
                    wmi = win32com.client.GetObject('winmgmts:\\\\.\\root\\wmi')
                    mfg_labels = {
                        'SAM': 'Samsung', 'DEL': 'Dell', 'GSM': 'LG Electronics', 'AOC': 'AOC',
                        'ACR': 'Acer', 'ASU': 'ASUS', 'BNQ': 'BenQ', 'PHL': 'Philips',
                        'HPN': 'HP', 'LEN': 'Lenovo', 'MSI': 'MSI'
                    }
                    def _dec_chars(chars: Any) -> str:
                        if not chars:
                            return ''
                        return ''.join(chr(c) for c in chars if c > 0).strip()

                    for m in wmi.InstancesOf('WmiMonitorID'):
                        m_name = _dec_chars(getattr(m, 'UserFriendlyName', None))
                        m_sn = _dec_chars(getattr(m, 'SerialNumberID', None))
                        m_mfg = _dec_chars(getattr(m, 'ManufacturerName', None))
                        m_inst = str(getattr(m, 'InstanceName', '') or '').strip()
                        wmi_monitors.append({
                            'name': m_name,
                            'sn': m_sn if m_sn != '0' else '',
                            'mfg': mfg_labels.get(m_mfg.upper(), m_mfg),
                            'instance': m_inst,
                        })
                except Exception as wmi_err:
                    logger.debug(f'WMI WmiMonitorID query warning: {wmi_err}')

                adapter_map: Dict[str, Dict[str, str]] = {}
                for i in range(16):
                    disp = DISPLAY_DEVICEW()
                    disp.cb = ctypes.sizeof(DISPLAY_DEVICEW)
                    if not user32.EnumDisplayDevicesW(None, i, ctypes.byref(disp), 0):
                        break
                    if disp.StateFlags & 1:
                        dev_name = disp.DeviceName
                        mon = DISPLAY_DEVICEW()
                        mon.cb = ctypes.sizeof(DISPLAY_DEVICEW)
                        mon_str = ''
                        mon_pnp = ''
                        if user32.EnumDisplayDevicesW(dev_name, 0, ctypes.byref(mon), 0):
                            mon_str = mon.DeviceString
                            mon_pnp = mon.DeviceID

                        mon_if = DISPLAY_DEVICEW()
                        mon_if.cb = ctypes.sizeof(DISPLAY_DEVICEW)
                        iface_id = ''
                        if user32.EnumDisplayDevicesW(dev_name, 0, ctypes.byref(mon_if), 1):
                            iface_id = mon_if.DeviceID

                        matched = None
                        if iface_id:
                            norm_iface = iface_id.upper().replace('#', '\\')
                            for wm in wmi_monitors:
                                base_inst = wm['instance'].upper().rsplit('_', 1)[0]
                                if base_inst in norm_iface:
                                    matched = wm
                                    break
                        if not matched and mon_pnp:
                            pnp_parts = mon_pnp.upper().split('\\')
                            if len(pnp_parts) > 1:
                                pnp_code = pnp_parts[1]
                                for wm in wmi_monitors:
                                    if f'\\{pnp_code}\\' in wm['instance'].upper() or wm['instance'].upper().startswith(f'DISPLAY\\{pnp_code}'):
                                        matched = wm
                                        break

                        edid_name = matched.get('name') if matched else ''
                        edid_mfg = matched.get('mfg') if matched else ''
                        edid_sn = matched.get('sn') if matched else ''

                        chosen_name = mon_str or edid_name or 'Display Monitor'
                        if ('generic' in chosen_name.lower() or not mon_str) and edid_name:
                            chosen_name = edid_name

                        adapter_map[dev_name] = {
                            'adapter': disp.DeviceString,
                            'mon_name': chosen_name,
                            'vendor': edid_mfg,
                            'serial_number': edid_sn,
                        }

                class MONITORINFOEXW(ctypes.Structure):
                    _fields_ = [('cbSize', ctypes.wintypes.DWORD), ('rcMonitor', ctypes.wintypes.RECT), ('rcWork', ctypes.wintypes.RECT), ('dwFlags', ctypes.wintypes.DWORD), ('szDevice', ctypes.wintypes.WCHAR * 32)]

                class DEVMODEW(ctypes.Structure):
                    _fields_ = [('dmDeviceName', ctypes.wintypes.WCHAR * 32), ('dmSpecVersion', ctypes.wintypes.WORD), ('dmDriverVersion', ctypes.wintypes.WORD), ('dmSize', ctypes.wintypes.WORD), ('dmDriverExtra', ctypes.wintypes.WORD), ('dmFields', ctypes.wintypes.DWORD), ('dmOrientation', ctypes.c_short), ('dmPaperSize', ctypes.c_short), ('dmPaperLength', ctypes.c_short), ('dmPaperWidth', ctypes.c_short), ('dmScale', ctypes.c_short), ('dmCopies', ctypes.c_short), ('dmDefaultSource', ctypes.c_short), ('dmPrintQuality', ctypes.c_short), ('dmColor', ctypes.c_short), ('dmDuplex', ctypes.c_short), ('dmYResolution', ctypes.c_short), ('dmTTOption', ctypes.c_short), ('dmCollate', ctypes.c_short), ('dmFormName', ctypes.wintypes.WCHAR * 32), ('dmLogPixels', ctypes.wintypes.WORD), ('dmBitsPerPel', ctypes.wintypes.DWORD), ('dmPelsWidth', ctypes.wintypes.DWORD), ('dmPelsHeight', ctypes.wintypes.DWORD), ('dmDisplayFlags', ctypes.wintypes.DWORD), ('dmDisplayFrequency', ctypes.wintypes.DWORD)]

                def _enum_cb(h_mon: Any, hdc: Any, lprc: Any, dw_data: Any) -> bool:
                    info = MONITORINFOEXW()
                    info.cbSize = ctypes.sizeof(MONITORINFOEXW)
                    user32.GetMonitorInfoW(h_mon, ctypes.byref(info))
                    dev = info.szDevice
                    w = info.rcMonitor.right - info.rcMonitor.left
                    h = info.rcMonitor.bottom - info.rcMonitor.top
                    is_prim = bool(info.dwFlags & 1)
                    freq = 60
                    bits = 32
                    dm = DEVMODEW()
                    dm.dmSize = ctypes.sizeof(DEVMODEW)
                    orient = 'вертикальная' if h > w else 'горизонтальная'
                    if user32.EnumDisplaySettingsW(dev, -1, ctypes.byref(dm)):
                        if dm.dmDisplayFrequency:
                            freq = dm.dmDisplayFrequency
                        if dm.dmBitsPerPel:
                            bits = dm.dmBitsPerPel
                        if dm.dmPelsWidth and dm.dmPelsHeight:
                            w, h = (dm.dmPelsWidth, dm.dmPelsHeight)
                        if hasattr(dm, 'dmOrientation') and dm.dmOrientation == 2:
                            orient = 'вертикальная'
                        elif hasattr(dm, 'dmOrientation') and dm.dmOrientation == 1:
                            orient = 'горизонтальная'
                    if h > w:
                        orient = 'вертикальная'
                    ad_info = adapter_map.get(dev, {})
                    monitors.append(MonitorInfo(device=dev, name=ad_info.get('mon_name', 'Display Monitor'), vendor=ad_info.get('vendor', ''), serial_number=ad_info.get('serial_number', ''), adapter=ad_info.get('adapter', ''), width=w, height=h, frequency_hz=freq, bits_per_pixel=bits, is_primary=is_prim, orientation=orient))
                    return True
                cb_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HMONITOR, ctypes.wintypes.HDC, ctypes.POINTER(ctypes.wintypes.RECT), ctypes.wintypes.LPARAM)
                user32.EnumDisplayMonitors(None, None, cb_type(_enum_cb), 0)
            except Exception as ex:
                logger.debug(f'Failed to query connected monitors: {ex}')
        if not monitors:
            monitors.append(MonitorInfo(device='\\\\.\\DISPLAY1', name='Primary Monitor', adapter='Display Adapter', width=1920, height=1080, frequency_hz=60, bits_per_pixel=32, is_primary=True, orientation='горизонтальная'))
        self._monitors_cached = monitors
        return monitors

    def get_updates_info(self) -> WindowsUpdateInfo:
        """Collect Windows Update status (делегирует SoftwareInfoCollector).

        Returns:
            WindowsUpdateInfo: Summary of updates status and installed KBs.
        """
        return self._software_info.get_updates_info()

    def get_ms_office_info(self) -> OfficeSuiteInfo:
        """Collect Microsoft Office suite info (делегирует SoftwareInfoCollector).

        Returns:
            OfficeSuiteInfo: Installed Office suite details.
        """
        return self._software_info.get_ms_office_info()

    def get_onedrive_info(self) -> CloudStorageInfo:
        """Collect OneDrive sync info (делегирует SoftwareInfoCollector).

        Returns:
            CloudStorageInfo: OneDrive accounts and quota.
        """
        return self._software_info.get_onedrive_info()

    async def get_core_metrics(self) -> SystemCoreMetrics:
        """Сверхбыстрый сбор базовой телеметрии без вызова тяжелых внешних утилит (< 0.2с).

        Returns:
            SystemCoreMetrics: Мгновенные показатели загрузки процессора, памяти, дисков и видеокарты.
        """
        now = time.time()
        uptime = round(now - (psutil.boot_time() if PSUTIL_AVAILABLE else now - 3600), 1)
        _, disk_io = self.get_disk_metrics()
        mems = self.get_memory_metrics()
        gpus = self.get_gpu_metrics()
        batt = self.get_battery_metrics()
        cpu_metrics = await self.get_cpu_metrics()
        self._last_time = now
        return SystemCoreMetrics(cpu=cpu_metrics, memory=mems, gpus=gpus, disk_io=disk_io, battery=batt, uptime_seconds=uptime)

    async def get_hardware_quick(self) -> SystemHardwareQuick:
        """Сбор сводки физических компонентов (диски, слоты памяти, порты, алерты).

        Returns:
            SystemHardwareQuick: Состояние накопителей, планок RAM и сетевых сокетов.
        """
        ram_sticks = await self.get_ram_sticks()
        phys_disks = self.get_physical_disks_health()
        ports = self.get_listening_ports()
        alerts = self.get_health_alerts()
        return SystemHardwareQuick(ram_sticks=ram_sticks, physical_disks=phys_disks, listening_ports=ports, alerts=alerts)

    def get_snapshot_from_db(self, process_limit: Any = 20) -> Optional[SystemSnapshot]:
        """Считывает последний зафиксированный снимок системы из базы данных SQLite (telemetry.db).

        Args:
            process_limit: Ограничение количества верхних процессов.

        Returns:
            Optional[SystemSnapshot]: Объект снимка системы или None, если БД пуста.
        """
        if not self.storage:
            return None
        try:
            limit = process_limit.default if hasattr(process_limit, "default") else (int(process_limit) if isinstance(process_limit, (int, float, str)) and str(process_limit).isdigit() else 20)
            snap_dict = self.storage.get_latest_snapshot_full()
            if not snap_dict:
                return None
            snap_obj = SystemSnapshot.model_validate(snap_dict)
            if not snap_obj.monitors:
                try:
                    snap_obj.monitors = self.get_monitors()
                except Exception:
                    pass
            else:
                for m in snap_obj.monitors:
                    if not getattr(m, 'orientation', None):
                        m.orientation = 'вертикальная' if (m.height or 0) > (m.width or 0) else 'горизонтальная'
            if limit and snap_obj.top_processes and len(snap_obj.top_processes) > limit:
                snap_obj.top_processes = snap_obj.top_processes[:limit]
            return snap_obj
        except Exception as ex:
            logger.debug(f"[SystemCollector] Ошибка загрузки снимка из SQLite: {ex}")
            return None

    async def get_snapshot(self, process_limit: Any = 20, force_live: bool = False) -> SystemSnapshot:
        """Capture point-in-time system telemetry snapshot.

        По умолчанию считывает снимок напрямую из базы данных SQLite (telemetry.db),
        что устраняет задержки, исключает скачки нагрузки на CPU/OS и гарантирует согласованность.
        При отсутствии данных в БД или при force_live=True выполняет сбор вживую.

        Args:
            process_limit: Количество процессов для включения в снимок.
            force_live: Принудительный сбор метрик напрямую из ОС.

        Returns:
            SystemSnapshot: Сводный снимок телеметрии системы.
        """
        limit = process_limit.default if hasattr(process_limit, "default") else (int(process_limit) if isinstance(process_limit, (int, float, str)) and str(process_limit).isdigit() else 20)
        if not force_live:
            db_snap = self.get_snapshot_from_db(process_limit=limit)
            if db_snap is not None:
                return db_snap

        def _collect_sync_telemetry() -> Dict[str, Any]:
            now = time.time()
            uptime = round(now - (psutil.boot_time() if PSUTIL_AVAILABLE else now - 3600), 1)
            partitions, disk_io = self.get_disk_metrics()
            net_metrics = self.get_network_metrics()
            sensors: List[HardwareSensor] = []
            if self.storage:
                try:
                    db_sensors = self.storage.get_latest_sensors()
                    for item in db_sensors:
                        sensors.append(
                            HardwareSensor(
                                sensor_id=str(item.get('sensor_id') or item.get('name') or 'unknown'),
                                name=str(item.get('name') or item.get('sensor_id') or 'sensor'),
                                sensor_type=str(item.get('sensor_type') or 'temperature'),
                                value=float(item.get('value') or 0.0),
                                unit=str(item.get('unit') or '°C'),
                            )
                        )
                except Exception:
                    sensors = []
            top_procs = self.get_top_processes(limit=process_limit)
            ident = self.get_system_identity()
            mems = self.get_memory_metrics()
            gpu_list = self.get_gpu_metrics()
            npu_list = self.get_npu_metrics()
            mon_list = self.get_monitors()
            upd_info = self.get_updates_info()
            off_info = self.get_ms_office_info()
            od_info = self.get_onedrive_info()
            phys_disks = self.get_physical_disks_health()
            ports = self.get_listening_ports()
            net_activity = self.get_process_network_activity(limit=40)
            batt = self.get_battery_metrics()
            alerts = self.get_health_alerts()
            net_profile = self.get_network_profile_fast()
            self._last_time = now
            return {'now': now, 'uptime': uptime, 'partitions': partitions, 'disk_io': disk_io, 'net_metrics': net_metrics, 'sensors': sensors, 'top_procs': top_procs, 'ident': ident, 'memory': mems, 'gpus': gpu_list, 'npus': npu_list, 'monitors': mon_list, 'updates': upd_info, 'office': off_info, 'onedrive': od_info, 'physical_disks': phys_disks, 'listening_ports': ports, 'net_activity': net_activity, 'battery': batt, 'alerts': alerts, 'net_profile': net_profile}
        cpu_task = asyncio.create_task(self.get_cpu_metrics())
        ram_task = asyncio.create_task(self.get_ram_sticks())
        sync_task = asyncio.create_task(asyncio.to_thread(_collect_sync_telemetry))
        cpu_metrics, ram_sticks, sync_data = await asyncio.gather(cpu_task, ram_task, sync_task)
        ident = sync_data['ident']
        # Читаем последний зафиксированный аудит оборудования из базы данных (без живого опроса PnP/реестра/WMI)
        hardware_audit_dict: Dict[str, Any] = {}
        if self.storage:
            try:
                latest_audit = self.storage.get_latest_hardware_audit() or self.storage.get_latest_extended_audit()
                if latest_audit:
                    hardware_audit_dict = latest_audit
            except Exception:
                pass
        return SystemSnapshot(
            hostname=ident.get('hostname') or socket.gethostname(),
            workgroup=ident.get('workgroup') or 'WORKGROUP',
            username=ident.get('username') or '',
            os_name=f'{platform.system()} {platform.release()}',
            os_build=ident.get('os_build') or platform.version(),
            system_language=ident.get('system_language') or '',
            os_install_language=ident.get('os_install_language') or '',
            user_locale=ident.get('user_locale') or '',
            system_locale=ident.get('system_locale') or '',
            timezone=ident.get('timezone') or '',
            codepage=ident.get('codepage') or '',
            input_languages=ident.get('input_languages') or [],
            os_install_date=ident.get('os_install_date') or '',
            uptime_seconds=sync_data['uptime'],
            cpu=cpu_metrics,
            memory=sync_data['memory'],
            ram_sticks=ram_sticks,
            gpus=sync_data['gpus'],
            npus=sync_data.get('npus', []),
            monitors=sync_data['monitors'],
            updates=sync_data['updates'],
            office=sync_data['office'],
            onedrive=sync_data['onedrive'],
            disks=sync_data['partitions'],
            physical_disks=sync_data['physical_disks'],
            disk_io=sync_data['disk_io'],
            network=sync_data['net_metrics'],
            listening_ports=sync_data['listening_ports'],
            network_activity=sync_data['net_activity'],
            battery=sync_data['battery'],
            alerts=sync_data['alerts'],
            sensors=sync_data['sensors'],
            top_processes=sync_data['top_procs'],
            network_profile=sync_data.get('net_profile', {}),
            hardware_audit=hardware_audit_dict
        )

    def get_hardware_sensors(self) -> List[HardwareSensor]:
        """Collect real-time hardware sensors readings.

        Returns:
            List[HardwareSensor]: Hardware sensors and temperatures.
        """
        return get_hardware_sensors()

    async def get_hardware_tree_async(self, force: bool = False) -> List[HardwareNode]:
        """Generate AIDA64-like hierarchical component specification tree (Async).

        Состояние оборудования сканируется 1 раз при запуске процесса или по отдельному запросу (force=True).
        Построение делегируется HardwareTreeBuilder.

        Args:
            force: Принудительный повторный опрос оборудования.

        Returns:
            List[HardwareNode]: Hardware devices grouped by category.
        """
        return await self._hardware_tree_builder.build(force=force)

    def get_hardware_tree(self, force: bool = False) -> List[HardwareNode]:
        """Generate AIDA64-like hierarchical component specification tree.

        Args:
            force: Принудительный повторный опрос оборудования.

        Returns:
            List[HardwareNode]: Hardware devices grouped by category.
        """
        import asyncio
        return asyncio.run(self.get_hardware_tree_async(force=force))










    def save_snapshot_to_db(self, snapshot: Optional[SystemSnapshot]=None, top_n: int=20) -> int:
        """Collect and save system telemetry snapshot directly into SQLite database.

        Args:
            snapshot: Optional existing SystemSnapshot (if None, collected synchronously).
            top_n: Top processes count.

        Returns:
            int: Created snapshot ID in database.
        """
        snap = snapshot
        if snap is None:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = None
            if loop and loop.is_running():
                snap = asyncio.run_coroutine_threadsafe(self.get_snapshot(process_limit=top_n), loop).result(timeout=5.0)
            else:
                snap = asyncio.run(self.get_snapshot(process_limit=top_n))
        return self.storage.save_snapshot(snap, top_n=top_n)









    def get_process_provenance_report(
        self,
        pid: Optional[int] = None,
        name_filter: Optional[str] = None,
        user_filter: Optional[str] = None,
        limit: int = 100,
    ) -> ProcessProvenanceReport:
        """Сформировать сводный отчет о происхождении и цепочках запуска активных процессов.

        Args:
            pid: Опциональный фильтр по PID.
            name_filter: Опциональный фильтр по имени процесса.
            user_filter: Опциональный фильтр по пользователю/SID.
            limit: Максимальное количество процессов в отчете.

        Returns:
            ProcessProvenanceReport: Полный отчет с детальным анализом происхождения процессов.
        """
        all_procs = self.get_top_processes(limit=0, sort_by='cpu')
        filtered_items: List[ProcessProvenanceInfo] = []

        for p in all_procs:
            if pid is not None and p.pid != pid:
                continue
            if name_filter and name_filter.lower() not in (p.name or '').lower():
                continue
            if user_filter and user_filter.lower() not in (p.username or '').lower() and user_filter.lower() not in (p.sid or '').lower():
                continue

            chain_list = [node.strip() for node in (p.ancestor_chain or "").split(" → ") if node.strip()]
            user_display = p.username or "Unknown"
            sid_display = p.sid or "N/A"
            session_display = f"Session {p.session_id}" if p.session_id is not None else "Session N/A"
            who_runs = f"{user_display} ({sid_display}, {session_display})"
            who_created = f"{p.parent_name or 'Unknown'} (PPID: {p.ppid})"
            why_created = p.launch_reason or "unknown"

            item = ProcessProvenanceInfo(
                pid=p.pid,
                ppid=p.ppid,
                name=p.name,
                executable_path=p.executable_path,
                command_line=p.cmdline,
                user=p.username,
                sid=p.sid,
                session_id=p.session_id,
                integrity_level=p.integrity_level,
                elevation=bool(p.elevation) if p.elevation is not None else None,
                creation_time=p.creation_time,
                process_guid=p.process_guid or f"proc_{p.pid}",
                parent_name=p.parent_name,
                ancestor_chain=chain_list,
                ancestor_chain_str=p.ancestor_chain or "",
                who_runs_it=who_runs,
                who_created_it=who_created,
                why_was_it_created=why_created,
            )
            filtered_items.append(item)
            if limit and len(filtered_items) >= limit:
                break

        now_iso = datetime.now(timezone.utc).isoformat()
        recent_evs: List[ProcessLifecycleEvent] = []
        try:
            for ev in self.storage.get_process_provenance_history(limit=20):
                if isinstance(ev, dict):
                    recent_evs.append(ProcessLifecycleEvent(
                        event_id=str(ev.get("event_id") or ""),
                        timestamp=str(ev.get("timestamp") or now_iso),
                        event_type=str(ev.get("event_type") or "ProcessCreated"),
                        pid=int(ev.get("pid") or 0),
                        ppid=int(ev["parent_pid"]) if ev.get("parent_pid") is not None else None,
                        process_guid=str(ev.get("process_guid") or ""),
                        parent_guid=ev.get("parent_guid"),
                        name=str(ev.get("name") or "unknown"),
                        executable_path=ev.get("executable_path"),
                        command_line=ev.get("command_line"),
                        user=ev.get("user"),
                        sid=ev.get("sid"),
                        session_id=int(ev["session_id"]) if ev.get("session_id") is not None else None,
                        integrity_level=ev.get("integrity_level"),
                        elevation=bool(ev.get("elevation")) if ev.get("elevation") is not None else None,
                        parent_name=ev.get("parent_name"),
                        ancestor_chain=ev.get("ancestor_chain"),
                        launch_reason=ev.get("launch_reason"),
                        source=str(ev.get("source") or "system"),
                        raw_json=str(ev.get("details_json")) if ev.get("details_json") else None,
                    ))
        except Exception as ex:
            logger.debug(f"Не удалось извлечь недавние события provenance для отчета: {ex}")

        summary = f"Всего активных процессов: {len(all_procs)}. Проанализировано происхождение для {len(filtered_items)} процессов."
        return ProcessProvenanceReport(
            timestamp=now_iso,
            total_processes=len(all_procs),
            active_provenance=filtered_items,
            recent_events=recent_evs,
            summary=summary,
        )





