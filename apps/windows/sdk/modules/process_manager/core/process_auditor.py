# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Modules Process_Manager Core - Process Auditor
# =============================================================================
# Description:
#   Высокопроизводительный сборщик глубокого аудита процесса по PID (CPU, RAM,
#   дисковый I/O, сетевые соединения и сокеты, переключения контекста и память).
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.process_manager.core.process_auditor import ProcessAuditor
#
#     auditor = ProcessAuditor()
#     sample = auditor.audit_process(pid=1234)
#
# File: process_auditor.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.process_manager.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 00:35:00
# =============================================================================

from __future__ import annotations
"""Высокопроизводительный инструмент аудита отдельного процесса по PID."""

import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False

from logger import logger
from apps.windows.sdk.native.kernel32 import Kernel32, ProcessIOCounters, ProcessTimesInfo
from apps.windows.sdk.native.nethelper import IPHelperAPI, NetworkSocketInfo
from apps.windows.sdk.native.psapi import ProcessMemoryInfoEx, Psapi


@dataclass
class ProcessCpuAudit:
    """Метрики процессора и потоков целевого процесса."""
    cpu_percent: float = 0.0
    user_time_sec: float = 0.0
    kernel_time_sec: float = 0.0
    total_cpu_time_sec: float = 0.0
    num_threads: int = 1
    context_switches_voluntary: int = 0
    context_switches_involuntary: int = 0
    total_context_switches: int = 0
    cpu_cycles: Optional[int] = None


@dataclass
class ProcessMemoryAudit:
    """Метрики оперативной и виртуальной памяти целевого процесса (высокая наблюдаемость)."""
    working_set_bytes: int = 0
    working_set_mb: float = 0.0
    peak_working_set_bytes: int = 0
    peak_working_set_mb: float = 0.0
    private_bytes: int = 0
    private_mb: float = 0.0
    commit_size_bytes: int = 0
    commit_size_mb: float = 0.0
    peak_commit_size_bytes: int = 0
    peak_commit_size_mb: float = 0.0
    page_faults: int = 0
    paged_pool_bytes: int = 0
    nonpaged_pool_bytes: int = 0


@dataclass
class ProcessIoAudit:
    """Метрики файлового и дискового ввода-вывода целевого процесса."""
    read_operations: int = 0
    write_operations: int = 0
    other_operations: int = 0
    total_operations: int = 0
    read_bytes: int = 0
    write_bytes: int = 0
    other_bytes: int = 0
    total_bytes: int = 0
    read_bytes_sec: float = 0.0
    write_bytes_sec: float = 0.0
    read_ops_sec: float = 0.0
    write_ops_sec: float = 0.0
    open_files_count: int = 0
    open_files: List[str] = field(default_factory=list)


@dataclass
class ProcessNetworkAudit:
    """Метрики сетевых подключений и сокетов целевого процесса."""
    tcp_connections_count: int = 0
    udp_sockets_count: int = 0
    total_connections_count: int = 0
    established_count: int = 0
    listening_count: int = 0
    connections: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ProcessAuditSample:
    """Полный снимок глубокого аудита процесса по PID и уникальной сессии instance_id."""
    pid: int
    name: str
    timestamp: str
    created_at: float
    status: str
    is_alive: bool
    creation_time: float
    exit_time: float
    num_handles: int
    executable: Optional[str]
    cmdline: Optional[str]
    username: Optional[str]
    instance_id: str = ""
    ppid: int = 0
    parent_name: Optional[str] = None
    parent_executable: Optional[str] = None
    initiator_type: str = "unknown"
    uptime_sec: float = 0.0
    cpu: ProcessCpuAudit = field(default_factory=ProcessCpuAudit)
    memory: ProcessMemoryAudit = field(default_factory=ProcessMemoryAudit)
    io: ProcessIoAudit = field(default_factory=ProcessIoAudit)
    network: ProcessNetworkAudit = field(default_factory=ProcessNetworkAudit)

    def to_dict(self) -> Dict[str, Any]:
        """Сериализация в словарь для JSON и базы данных."""
        return asdict(self)


class ProcessAuditor:
    """Инструмент глубокого аудита процесса по PID на основе нативного SDK (kernel32, psapi, iphlpapi)."""

    def __init__(self) -> None:
        """Инициализация подсистем Win32 SDK."""
        self._kernel32 = Kernel32() if os.name == 'nt' else None
        self._psapi = Psapi() if os.name == 'nt' else None
        self._iphlpapi = IPHelperAPI() if os.name == 'nt' else None
        self._history_baselines: Dict[int, Dict[str, Any]] = {}

    def audit_process(self, pid: int) -> Optional[ProcessAuditSample]:
        """Собрать мгновенный снимок аудита по указанному PID.

        Args:
            pid: Идентификатор процесса Windows (PID).

        Returns:
            Optional[ProcessAuditSample]: Снимок аудита или None, если процесс не найден.
        """
        now_ts = time.time()
        now_iso = datetime.now(timezone.utc).isoformat()

        # Проверка существования процесса
        proc: Optional[psutil.Process] = None
        if PSUTIL_AVAILABLE:
            try:
                proc = psutil.Process(pid)
                if not proc.is_running():
                    return None
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                if not self._is_pid_alive_native(pid):
                    return None

        # 1. Основные метаданные процесса
        name = 'unknown'
        status = 'running'
        is_alive = True
        creation_time = 0.0
        exit_time = 0.0
        num_handles = 0
        executable = None
        cmdline = None
        username = None
        ppid = 0
        parent_name = None
        parent_executable = None
        initiator_type = "unknown"

        if proc:
            try:
                name = proc.name()
                status = proc.status()
                num_handles = proc.num_handles() if hasattr(proc, 'num_handles') else 0
                executable = proc.exe() if hasattr(proc, 'exe') else None
                cmdline = ' '.join(proc.cmdline()) if hasattr(proc, 'cmdline') else None
                username = proc.username() if hasattr(proc, 'username') else None
                ppid = proc.ppid() if hasattr(proc, 'ppid') else 0
                creation_time = float(proc.create_time()) if hasattr(proc, 'create_time') else 0.0

                if ppid > 0:
                    try:
                        p_parent = psutil.Process(ppid)
                        parent_name = p_parent.name()
                        parent_executable = p_parent.exe()
                    except Exception:
                        pass
            except Exception:
                pass

        if not creation_time and self._kernel32:
            times_info = self._kernel32.get_process_times_info(pid)
            if times_info:
                creation_time = times_info.creation_time
                exit_time = times_info.exit_time

        instance_id = f"{pid}_{int(creation_time * 1000)}" if creation_time > 0 else f"{pid}_0"
        uptime_sec = max(0.0, round(now_ts - creation_time, 2)) if creation_time > 0 else 0.0

        if parent_name:
            p_low = parent_name.lower()
            if p_low in ('explorer.exe', 'windowsterminal.exe', 'wt.exe', 'powershell.exe', 'cmd.exe'):
                initiator_type = "user_interactive"
            elif p_low in ('services.exe', 'svchost.exe'):
                initiator_type = "system_service"
            elif p_low in ('taskhostw.exe', 'taskhost.exe', 'taskeng.exe'):
                initiator_type = "task_scheduler"
            elif p_low in ('python.exe', 'node.exe'):
                initiator_type = "script_runner"
            else:
                initiator_type = "application_child"

        # 2. Аудит CPU через Win32 API и psutil
        cpu_audit = self._collect_cpu_audit(pid, proc, now_ts)

        # 3. Аудит памяти (Working Set, Private Bytes, Commit Size, Page Faults)
        memory_audit = self._collect_memory_audit(pid, proc)

        # 4. Аудит дискового ввода-вывода (IO_COUNTERS)
        io_audit = self._collect_io_audit(pid, proc, now_ts)

        # 5. Аудит сети (IP Helper API)
        network_audit = self._collect_network_audit(pid)

        # Сохранение базовых значений для расчета дельт
        self._history_baselines[pid] = {
            'timestamp': now_ts,
            'total_cpu_time': cpu_audit.total_cpu_time_sec,
            'read_bytes': io_audit.read_bytes,
            'write_bytes': io_audit.write_bytes,
            'read_ops': io_audit.read_operations,
            'write_ops': io_audit.write_operations,
        }

        return ProcessAuditSample(
            pid=pid,
            name=name,
            timestamp=now_iso,
            created_at=now_ts,
            status=status,
            is_alive=is_alive,
            creation_time=creation_time,
            exit_time=exit_time,
            num_handles=num_handles,
            executable=executable,
            cmdline=cmdline,
            username=username,
            instance_id=instance_id,
            ppid=ppid,
            parent_name=parent_name,
            parent_executable=parent_executable,
            initiator_type=initiator_type,
            uptime_sec=uptime_sec,
            cpu=cpu_audit,
            memory=memory_audit,
            io=io_audit,
            network=network_audit,
        )

    def _is_pid_alive_native(self, pid: int) -> bool:
        """Проверка существования процесса через Toolhelp32/kernel32."""
        if not self._kernel32:
            return False
        try:
            for p in self._kernel32.enumerate_processes():
                if p.pid == pid:
                    return True
        except Exception:
            pass
        return False

    def _collect_cpu_audit(
        self, pid: int, proc: Optional[psutil.Process], now_ts: float
    ) -> ProcessCpuAudit:
        """Сбор процессорных метрик: % CPU, время ядра/пользователя, потоки, переключения контекста."""
        user_sec = 0.0
        kernel_sec = 0.0
        total_cpu_sec = 0.0
        cpu_percent = 0.0
        num_threads = 1
        vol_ctx = 0
        invol_ctx = 0
        cycles: Optional[int] = None

        if self._kernel32:
            times_info = self._kernel32.get_process_times_info(pid)
            if times_info:
                user_sec = times_info.user_time_sec
                kernel_sec = times_info.kernel_time_sec
                total_cpu_sec = times_info.total_cpu_time_sec

            cycles = self._kernel32.get_process_cycle_time(pid)

        # Вычисление % CPU по дельте времени процесса к физическому времени
        prev = self._history_baselines.get(pid)
        if prev and now_ts > prev['timestamp']:
            dt = max(0.001, now_ts - prev['timestamp'])
            dcpu = max(0.0, total_cpu_sec - prev.get('total_cpu_time', 0.0))
            num_cpus = os.cpu_count() or 1
            cpu_percent = round((dcpu / dt) * 100.0 / num_cpus, 2)
        elif proc:
            try:
                cpu_percent = float(proc.cpu_percent(interval=None) or 0.0)
            except Exception:
                pass

        if proc:
            try:
                num_threads = proc.num_threads()
                ctx = proc.num_ctx_switches()
                vol_ctx = ctx.voluntary
                invol_ctx = ctx.involuntary
                if total_cpu_sec == 0.0:
                    cpu_times = proc.cpu_times()
                    user_sec = cpu_times.user
                    kernel_sec = cpu_times.system
                    total_cpu_sec = user_sec + kernel_sec
            except Exception:
                pass

        return ProcessCpuAudit(
            cpu_percent=cpu_percent,
            user_time_sec=round(user_sec, 4),
            kernel_time_sec=round(kernel_sec, 4),
            total_cpu_time_sec=round(total_cpu_sec, 4),
            num_threads=num_threads,
            context_switches_voluntary=vol_ctx,
            context_switches_involuntary=invol_ctx,
            total_context_switches=vol_ctx + invol_ctx,
            cpu_cycles=cycles,
        )

    def _collect_memory_audit(
        self, pid: int, proc: Optional[psutil.Process]
    ) -> ProcessMemoryAudit:
        """Сбор памяти через Win32 PSAPI (GetProcessMemoryInfo) с Private Bytes и Commit Size."""
        ws_bytes = 0
        peak_ws_bytes = 0
        priv_bytes = 0
        commit_bytes = 0
        peak_commit_bytes = 0
        page_faults = 0
        paged_pool = 0
        nonpaged_pool = 0

        if self._psapi:
            mem_ex = self._psapi.get_process_memory_info_ex(pid)
            if mem_ex:
                ws_bytes = mem_ex.working_set
                peak_ws_bytes = mem_ex.peak_working_set
                priv_bytes = mem_ex.private_usage
                commit_bytes = mem_ex.pagefile_usage
                peak_commit_bytes = mem_ex.pagefile_peak
                page_faults = mem_ex.page_faults
                paged_pool = mem_ex.paged_pool_usage
                nonpaged_pool = mem_ex.nonpaged_pool_usage

        # Fallback на psutil при отсутствии нативных данных
        if ws_bytes == 0 and proc:
            try:
                mi = proc.memory_info()
                ws_bytes = getattr(mi, 'rss', 0)
                commit_bytes = getattr(mi, 'vms', 0)
                priv_bytes = getattr(mi, 'private', 0) or commit_bytes
                peak_ws_bytes = getattr(mi, 'peak_wset', ws_bytes)
                peak_commit_bytes = getattr(mi, 'peak_paged_pool', commit_bytes)
            except Exception:
                pass

        mb_factor = 1024.0 * 1024.0
        return ProcessMemoryAudit(
            working_set_bytes=ws_bytes,
            working_set_mb=round(ws_bytes / mb_factor, 2),
            peak_working_set_bytes=peak_ws_bytes,
            peak_working_set_mb=round(peak_ws_bytes / mb_factor, 2),
            private_bytes=priv_bytes,
            private_mb=round(priv_bytes / mb_factor, 2),
            commit_size_bytes=commit_bytes,
            commit_size_mb=round(commit_bytes / mb_factor, 2),
            peak_commit_size_bytes=peak_commit_bytes,
            peak_commit_size_mb=round(peak_commit_bytes / mb_factor, 2),
            page_faults=page_faults,
            paged_pool_bytes=paged_pool,
            nonpaged_pool_bytes=nonpaged_pool,
        )

    def _collect_io_audit(
        self, pid: int, proc: Optional[psutil.Process], now_ts: float
    ) -> ProcessIoAudit:
        """Сбор дискового/файлового I/O через Win32 IO_COUNTERS."""
        r_ops = 0
        w_ops = 0
        o_ops = 0
        r_bytes = 0
        w_bytes = 0
        o_bytes = 0
        r_bytes_sec = 0.0
        w_bytes_sec = 0.0
        r_ops_sec = 0.0
        w_ops_sec = 0.0
        open_files: List[str] = []

        if self._kernel32:
            io_cnt = self._kernel32.get_process_io_counters(pid)
            if io_cnt:
                r_ops = io_cnt.read_operation_count
                w_ops = io_cnt.write_operation_count
                o_ops = io_cnt.other_operation_count
                r_bytes = io_cnt.read_transfer_count
                w_bytes = io_cnt.write_transfer_count
                o_bytes = io_cnt.other_transfer_count

        if r_ops == 0 and w_ops == 0 and proc:
            try:
                io_counters = proc.io_counters()
                r_ops = io_counters.read_count
                w_ops = io_counters.write_count
                r_bytes = io_counters.read_bytes
                w_bytes = io_counters.write_bytes
                o_ops = getattr(io_counters, 'other_count', 0)
                o_bytes = getattr(io_counters, 'other_bytes', 0)
            except Exception:
                pass

        if proc:
            try:
                open_files = [f.path for f in proc.open_files() if hasattr(f, 'path')]
            except Exception:
                pass

        # Расчет скоростей по отношению к предыдущему замеру
        prev = self._history_baselines.get(pid)
        if prev and now_ts > prev['timestamp']:
            dt = max(0.001, now_ts - prev['timestamp'])
            r_bytes_sec = max(0.0, (r_bytes - prev.get('read_bytes', 0)) / dt)
            w_bytes_sec = max(0.0, (w_bytes - prev.get('write_bytes', 0)) / dt)
            r_ops_sec = max(0.0, (r_ops - prev.get('read_ops', 0)) / dt)
            w_ops_sec = max(0.0, (w_ops - prev.get('write_ops', 0)) / dt)

        return ProcessIoAudit(
            read_operations=r_ops,
            write_operations=w_ops,
            other_operations=o_ops,
            total_operations=r_ops + w_ops + o_ops,
            read_bytes=r_bytes,
            write_bytes=w_bytes,
            other_bytes=o_bytes,
            total_bytes=r_bytes + w_bytes + o_bytes,
            read_bytes_sec=round(r_bytes_sec, 2),
            write_bytes_sec=round(w_bytes_sec, 2),
            read_ops_sec=round(r_ops_sec, 2),
            write_ops_sec=round(w_ops_sec, 2),
            open_files_count=len(open_files),
            open_files=open_files[:50],
        )

    def _collect_network_audit(self, pid: int) -> ProcessNetworkAudit:
        """Сбор активных TCP и UDP сетевых сокетов процесса через IP Helper API."""
        connections_list: List[Dict[str, Any]] = []
        tcp_count = 0
        udp_count = 0
        established_count = 0
        listening_count = 0

        if self._iphlpapi:
            try:
                sockets = self._iphlpapi.get_process_network_connections(pid)
                for sock in sockets:
                    conn_dict = sock.to_dict()
                    connections_list.append(conn_dict)
                    if sock.protocol == 'TCP':
                        tcp_count += 1
                        if sock.state == 'ESTABLISHED':
                            established_count += 1
                        elif sock.state == 'LISTEN':
                            listening_count += 1
                    elif sock.protocol == 'UDP':
                        udp_count += 1
                        if sock.state == 'LISTEN':
                            listening_count += 1
            except Exception as ex:
                logger.debug(f'Ошибка аудита сетевых сокетов для PID {pid}: {ex}')

        return ProcessNetworkAudit(
            tcp_connections_count=tcp_count,
            udp_sockets_count=udp_count,
            total_connections_count=tcp_count + udp_count,
            established_count=established_count,
            listening_count=listening_count,
            connections=connections_list,
        )

