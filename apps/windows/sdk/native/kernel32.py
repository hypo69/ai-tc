# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry Win32_Ffi - Kernel32
# =============================================================================
# Description:
#   kernel32.dll wrapper for process enumeration and snapshot operations.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.win32_ffi.kernel32 import PROCESSENTRY32
#
#     service = PROCESSENTRY32()
#
# File: kernel32.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.win32_ffi
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 00:16:00
# =============================================================================

"""kernel32.dll wrapper for process enumeration and snapshot operations."""

import ctypes
import ctypes.wintypes as wintypes
from typing import List, Optional, Tuple
from dataclasses import dataclass
TH32CS_SNAPPROCESS = 2
TH32CS_SNAPTHREAD = 4
TH32CS_SNAPMODULE = 8
TH32CS_SNAPMODULE32 = 16
ABOVE_NORMAL_PRIORITY_CLASS = 32768
BELOW_NORMAL_PRIORITY_CLASS = 16384
HIGH_PRIORITY_CLASS = 128
IDLE_PRIORITY_CLASS = 64
NORMAL_PRIORITY_CLASS = 32
REALTIME_PRIORITY_CLASS = 256

class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [('dwSize', wintypes.DWORD), ('th32ProcessID', wintypes.DWORD), ('th32ParentProcessID', wintypes.DWORD), ('dwPriority', wintypes.LONG), ('dwThreadCount', wintypes.DWORD), ('th32ModuleID', wintypes.DWORD), ('pcbUsage', wintypes.DWORD), ('th32AccessKey', wintypes.LPVOID), ('szExeFile', ctypes.c_char * 260)]

class THREADENTRY32(ctypes.Structure):
    _fields_ = [('dwSize', wintypes.DWORD), ('th32ThreadID', wintypes.DWORD), ('th32OwnerProcessID', wintypes.DWORD), ('tpBasePri', wintypes.LONG), ('tpDeltaPri', wintypes.LONG), ('dwFlags', wintypes.DWORD)]

class MODULEENTRY32(ctypes.Structure):
    _fields_ = [('dwSize', wintypes.DWORD), ('th32ModuleID', wintypes.DWORD), ('th32ProcessID', wintypes.DWORD), ('GlpvBase', wintypes.LPVOID), ('dwSize_', wintypes.DWORD), ('hModule', wintypes.HMODULE), ('szModule', ctypes.c_char * 256), ('szExePath', ctypes.c_char * 260)]

class FILETIME(ctypes.Structure):
    _fields_ = [('dwLowDateTime', wintypes.DWORD), ('dwHighDateTime', wintypes.DWORD)]

class IO_COUNTERS(ctypes.Structure):
    """Win32 IO_COUNTERS структура для сбора метрик операций ввода-вывода процесса."""
    _fields_ = [
        ('ReadOperationCount', ctypes.c_uint64),
        ('WriteOperationCount', ctypes.c_uint64),
        ('OtherOperationCount', ctypes.c_uint64),
        ('ReadTransferCount', ctypes.c_uint64),
        ('WriteTransferCount', ctypes.c_uint64),
        ('OtherTransferCount', ctypes.c_uint64),
    ]

@dataclass
class ProcessIOCounters:
    """Статистика дискового и файлового ввода-вывода процесса из Win32 IO_COUNTERS."""
    read_operation_count: int
    write_operation_count: int
    other_operation_count: int
    read_transfer_count: int   # bytes
    write_transfer_count: int  # bytes
    other_transfer_count: int  # bytes

@dataclass
class ProcessTimesInfo:
    """Временные метрики процессора процесса (Win32 GetProcessTimes)."""
    creation_time: float      # Unix timestamp создания
    exit_time: float          # Unix timestamp завершения (или 0.0 если работает)
    kernel_time_sec: float    # Время выполнения в режиме ядра (сек)
    user_time_sec: float      # Время выполнения в пользовательском режиме (сек)
    total_cpu_time_sec: float # Суммарное время CPU (сек)

@dataclass
class ProcessInfo:
    """Process snapshot information from Toolhelp32."""
    pid: int
    ppid: int
    name: str
    priority: int
    thread_count: int

@dataclass
class ThreadInfo:
    """Thread snapshot information from Toolhelp32."""
    tid: int
    pid: int
    base_priority: int
    delta_priority: int

@dataclass
class ModuleInfo:
    """Module snapshot information from Toolhelp32."""
    name: str
    path: str
    base_address: int
    size: int

class Kernel32API:
    """Wrapper for kernel32 process and thread enumeration functions."""

    def __init__(self):
        self.kernel32 = ctypes.windll.kernel32
        self._setup_function_signatures()

    def _setup_function_signatures(self):
        """Configure ctypes function signatures for proper type checking."""
        self.kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        self.kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        self.kernel32.Process32First.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32)]
        self.kernel32.Process32First.restype = wintypes.BOOL
        self.kernel32.Process32Next.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32)]
        self.kernel32.Process32Next.restype = wintypes.BOOL
        self.kernel32.Thread32First.argtypes = [wintypes.HANDLE, ctypes.POINTER(THREADENTRY32)]
        self.kernel32.Thread32First.restype = wintypes.BOOL
        self.kernel32.Thread32Next.argtypes = [wintypes.HANDLE, ctypes.POINTER(THREADENTRY32)]
        self.kernel32.Thread32Next.restype = wintypes.BOOL
        self.kernel32.Module32First.argtypes = [wintypes.HANDLE, ctypes.POINTER(MODULEENTRY32)]
        self.kernel32.Module32First.restype = wintypes.BOOL
        self.kernel32.Module32Next.argtypes = [wintypes.HANDLE, ctypes.POINTER(MODULEENTRY32)]
        self.kernel32.Module32Next.restype = wintypes.BOOL
        self.kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel32.CloseHandle.restype = wintypes.BOOL
        self.kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        self.kernel32.GetProcessTimes.argtypes = [wintypes.HANDLE, ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME)]
        self.kernel32.GetProcessTimes.restype = wintypes.BOOL
        self.kernel32.GetPriorityClass.argtypes = [wintypes.HANDLE]
        self.kernel32.GetPriorityClass.restype = wintypes.DWORD
        self.kernel32.GetProcessIoCounters.argtypes = [wintypes.HANDLE, ctypes.POINTER(IO_COUNTERS)]
        self.kernel32.GetProcessIoCounters.restype = wintypes.BOOL
        if hasattr(self.kernel32, 'QueryProcessCycleTime'):
            self.kernel32.QueryProcessCycleTime.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_uint64)]
            self.kernel32.QueryProcessCycleTime.restype = wintypes.BOOL

    def enumerate_processes(self) -> List[ProcessInfo]:
        """
        Enumerate all running processes using Toolhelp32.

        Returns:
            List of ProcessInfo objects
        """
        processes = []
        snapshot = self.kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if snapshot == -1:
            return processes
        try:
            pe = PROCESSENTRY32()
            pe.dwSize = ctypes.sizeof(PROCESSENTRY32)
            if self.kernel32.Process32First(snapshot, ctypes.byref(pe)):
                while True:
                    try:
                        process = ProcessInfo(pid=pe.th32ProcessID, ppid=pe.th32ParentProcessID, name=pe.szExeFile.decode('utf-8', errors='ignore'), priority=pe.dwPriority, thread_count=pe.dwThreadCount)
                        processes.append(process)
                    except Exception:
                        pass
                    if not self.kernel32.Process32Next(snapshot, ctypes.byref(pe)):
                        break
        finally:
            self.kernel32.CloseHandle(snapshot)
        return processes

    def enumerate_threads(self, pid: Optional[int]=None) -> List[ThreadInfo]:
        """
        Enumerate threads for a process or all threads if pid is None.

        Args:
            pid: Process ID to filter threads, or None for all threads

        Returns:
            List of ThreadInfo objects
        """
        threads = []
        snapshot = self.kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, pid or 0)
        if snapshot == -1:
            return threads
        try:
            te = THREADENTRY32()
            te.dwSize = ctypes.sizeof(THREADENTRY32)
            if self.kernel32.Thread32First(snapshot, ctypes.byref(te)):
                while True:
                    try:
                        if pid is None or te.th32OwnerProcessID == pid:
                            thread = ThreadInfo(tid=te.th32ThreadID, pid=te.th32OwnerProcessID, base_priority=te.tpBasePri, delta_priority=te.tpDeltaPri)
                            threads.append(thread)
                    except Exception:
                        pass
                    if not self.kernel32.Thread32Next(snapshot, ctypes.byref(te)):
                        break
        finally:
            self.kernel32.CloseHandle(snapshot)
        return threads

    def enumerate_modules(self, pid: int) -> List[ModuleInfo]:
        """
        Enumerate modules (DLLs) loaded in a process.

        Args:
            pid: Process ID

        Returns:
            List of ModuleInfo objects
        """
        modules = []
        snapshot = self.kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
        if snapshot == -1:
            return modules
        try:
            me = MODULEENTRY32()
            me.dwSize = ctypes.sizeof(MODULEENTRY32)
            if self.kernel32.Module32First(snapshot, ctypes.byref(me)):
                while True:
                    try:
                        module = ModuleInfo(name=me.szModule.decode('utf-8', errors='ignore'), path=me.szExePath.decode('utf-8', errors='ignore'), base_address=int(me.GlpvBase), size=me.dwSize_)
                        modules.append(module)
                    except Exception:
                        pass
                    if not self.kernel32.Module32Next(snapshot, ctypes.byref(me)):
                        break
        finally:
            self.kernel32.CloseHandle(snapshot)
        return modules

    def get_process_priority_class(self, pid: int) -> Optional[str]:
        """
        Get the priority class of a process.

        Args:
            pid: Process ID

        Returns:
            Priority class name or None if error
        """
        try:
            handle = ctypes.windll.kernel32.OpenProcess(1024, False, pid)
            if not handle:
                return None
            try:
                priority = self.kernel32.GetPriorityClass(handle)
                priority_map = {ABOVE_NORMAL_PRIORITY_CLASS: 'Above Normal', BELOW_NORMAL_PRIORITY_CLASS: 'Below Normal', HIGH_PRIORITY_CLASS: 'High', IDLE_PRIORITY_CLASS: 'Idle', NORMAL_PRIORITY_CLASS: 'Normal', REALTIME_PRIORITY_CLASS: 'Realtime'}
                return priority_map.get(priority, f'Unknown ({priority})')
            finally:
                self.kernel32.CloseHandle(handle)
        except Exception:
            return None

    def get_process_times(self, pid: int) -> Optional[Tuple[int, int]]:
        """
        Get process creation and exit times.

        Args:
            pid: Process ID

        Returns:
            Tuple of (creation_time_filetime, exit_time_filetime) or None
        """
        try:
            handle = ctypes.windll.kernel32.OpenProcess(1024, False, pid)
            if not handle:
                return None
            try:
                creation_time = FILETIME()
                exit_time = FILETIME()
                kernel_time = FILETIME()
                user_time = FILETIME()
                if self.kernel32.GetProcessTimes(handle, ctypes.byref(creation_time), ctypes.byref(exit_time), ctypes.byref(kernel_time), ctypes.byref(user_time)):
                    return (creation_time.dwLowDateTime, exit_time.dwLowDateTime)
                return None
            finally:
                self.kernel32.CloseHandle(handle)
        except Exception:
            return None

    def get_process_times_info(self, pid: int) -> Optional[ProcessTimesInfo]:
        """Получить детализированную информацию о времени CPU процесса (Kernel, User, Creation, Exit).

        Args:
            pid: Идентификатор процесса Windows (PID).

        Returns:
            Optional[ProcessTimesInfo]: Данные времени CPU или None при ошибке.
        """
        try:
            handle = ctypes.windll.kernel32.OpenProcess(1024, False, pid)
            if not handle:
                return None
            try:
                creation_time = FILETIME()
                exit_time = FILETIME()
                kernel_time = FILETIME()
                user_time = FILETIME()
                if self.kernel32.GetProcessTimes(handle, ctypes.byref(creation_time), ctypes.byref(exit_time), ctypes.byref(kernel_time), ctypes.byref(user_time)):
                    # Преобразование FILETIME (100-нс интервалы)
                    EPOCH_DIFFERENCE_100NS = 116444736000000000
                    raw_creation = (creation_time.dwHighDateTime << 32) | creation_time.dwLowDateTime
                    raw_exit = (exit_time.dwHighDateTime << 32) | exit_time.dwLowDateTime
                    raw_kernel = (kernel_time.dwHighDateTime << 32) | kernel_time.dwLowDateTime
                    raw_user = (user_time.dwHighDateTime << 32) | user_time.dwLowDateTime

                    c_ts = max(0.0, (raw_creation - EPOCH_DIFFERENCE_100NS) / 10_000_000.0) if raw_creation > EPOCH_DIFFERENCE_100NS else 0.0
                    e_ts = max(0.0, (raw_exit - EPOCH_DIFFERENCE_100NS) / 10_000_000.0) if raw_exit > EPOCH_DIFFERENCE_100NS else 0.0
                    k_sec = raw_kernel / 10_000_000.0
                    u_sec = raw_user / 10_000_000.0

                    return ProcessTimesInfo(
                        creation_time=c_ts,
                        exit_time=e_ts,
                        kernel_time_sec=k_sec,
                        user_time_sec=u_sec,
                        total_cpu_time_sec=k_sec + u_sec,
                    )
                return None
            finally:
                self.kernel32.CloseHandle(handle)
        except Exception:
            return None

    def get_process_io_counters(self, pid: int) -> Optional[ProcessIOCounters]:
        """Получить Win32 IO_COUNTERS процесса (число операций и переданных байт чтения/записи/прочих).

        Args:
            pid: Идентификатор процесса Windows (PID).

        Returns:
            Optional[ProcessIOCounters]: Структура счетчиков ввода-вывода или None.
        """
        try:
            handle = ctypes.windll.kernel32.OpenProcess(1024, False, pid)
            if not handle:
                return None
            try:
                io = IO_COUNTERS()
                if self.kernel32.GetProcessIoCounters(handle, ctypes.byref(io)):
                    return ProcessIOCounters(
                        read_operation_count=int(io.ReadOperationCount),
                        write_operation_count=int(io.WriteOperationCount),
                        other_operation_count=int(io.OtherOperationCount),
                        read_transfer_count=int(io.ReadTransferCount),
                        write_transfer_count=int(io.WriteTransferCount),
                        other_transfer_count=int(io.OtherTransferCount),
                    )
                return None
            finally:
                self.kernel32.CloseHandle(handle)
        except Exception:
            return None

    def get_process_cycle_time(self, pid: int) -> Optional[int]:
        """Получить общее количество процессорных тактов (cycles), затраченных процессом.

        Args:
            pid: Идентификатор процесса Windows (PID).

        Returns:
            Optional[int]: Число процессорных тактов или None при отсутствии поддержки.
        """
        if not hasattr(self.kernel32, 'QueryProcessCycleTime'):
            return None
        try:
            handle = ctypes.windll.kernel32.OpenProcess(1024, False, pid)
            if not handle:
                return None
            try:
                cycles = ctypes.c_uint64(0)
                if self.kernel32.QueryProcessCycleTime(handle, ctypes.byref(cycles)):
                    return int(cycles.value)
                return None
            finally:
                self.kernel32.CloseHandle(handle)
        except Exception:
            return None


Kernel32 = Kernel32API

__all__ = [
    "Kernel32API",
    "Kernel32",
    "ProcessInfo",
    "ThreadInfo",
    "ModuleInfo",
    "ProcessIOCounters",
    "ProcessTimesInfo",
    "IO_COUNTERS",
    "PROCESSENTRY32",
    "THREADENTRY32",
    "MODULEENTRY32",
]

