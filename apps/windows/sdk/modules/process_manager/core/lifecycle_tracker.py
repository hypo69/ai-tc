# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Modules Process_Manager Core - Lifecycle Tracker
# =============================================================================
# Description:
#   Диспетчер жизненного цикла процессов Windows: точное отслеживание времени
#   рождения (create_time), завершения (exit_time), инициаторов (родительских
#   процессов, служб, пользователей) и ресурсного следа каждого запуска.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.process_manager.core.lifecycle_tracker import ProcessLifecycleTracker
#
#     tracker = ProcessLifecycleTracker()
#     delta = tracker.scan_processes_delta()
#     summary = tracker.get_app_summary(app_name="python.exe")
#
# File: lifecycle_tracker.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.process_manager.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 00:32:00
# =============================================================================

from __future__ import annotations
"""Диспетчер жизненного цикла процессов, идентификации инициаторов и учета ресурсов."""

import hashlib
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False

from logger import logger
from apps.windows.sdk.native.kernel32 import Kernel32
from apps.windows.sdk.native.psapi import Psapi
from apps.windows.sdk.native.nethelper import IPHelperAPI
from apps.windows.sdk.modules.process_manager.core.classifier import (
    KNOWN_APP_FRIENDLY_NAMES,
    WINDOWS_SYSTEM_PROCESS_NAMES,
)


@dataclass
class ProcessSessionRecord:
    """Уникальная сессия жизненного цикла процесса Windows."""
    instance_id: str                      # Уникальный ключ: {pid}_{created_ts_ms}
    pid: int                              # Идентификатор процесса
    ppid: int = 0                         # Идентификатор процесса-родителя
    name: str = "unknown"                 # Имя бинарника (e.g. powershell.exe)
    friendly_name: str = "Unknown"        # Читаемое название приложения
    exe_path: Optional[str] = None        # Полный путь к исполняемому файлу
    binary_hash: Optional[str] = None     # SHA256 хеш исполняемого файла
    cmdline: Optional[str] = None         # Командная строка запуска
    username: Optional[str] = None        # Пользователь (DOMAIN\User)
    parent_name: Optional[str] = None     # Имя родительского процесса
    parent_exe: Optional[str] = None      # Путь к родительскому файлу
    initiator_type: str = "unknown"       # Тип инициатора (user_interactive, system_service, etc.)
    created_at: str = ""                  # ISO дата/время старта
    created_ts: float = 0.0               # Unix timestamp создания
    terminated_at: Optional[str] = None   # ISO дата/время завершения
    terminated_ts: Optional[float] = None # Unix timestamp завершения
    is_alive: bool = True                 # Флаг текущей активности
    lifetime_sec: float = 0.0             # Длительность жизни в секундах
    exit_code: Optional[int] = None       # Код возврата процесса
    # Ресурсный след ("что и сколько делал в системе")
    cpu_time_user_sec: float = 0.0
    cpu_time_kernel_sec: float = 0.0
    cpu_time_total_sec: float = 0.0
    cpu_cycles: Optional[int] = None
    peak_working_set_mb: float = 0.0
    peak_private_mb: float = 0.0
    io_read_bytes: int = 0
    io_write_bytes: int = 0
    io_read_ops: int = 0
    io_write_ops: int = 0
    files_accessed: List[str] = field(default_factory=list)
    remote_endpoints: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Преобразует запись сессии в словарь."""
        return asdict(self)


@dataclass
class ProcessLifecycleDelta:
    """Срез изменений жизненного цикла процессов между двумя сканированиями."""
    timestamp: str
    created_sessions: List[ProcessSessionRecord] = field(default_factory=list)
    terminated_sessions: List[ProcessSessionRecord] = field(default_factory=list)
    active_count: int = 0


class ProcessLifecycleTracker:
    """Трекер жизненного цикла процессов, идентификации инициаторов и учета ресурсов."""

    def __init__(self) -> None:
        """Инициализация трекера жизненного цикла."""
        self._kernel32 = Kernel32() if os.name == 'nt' else None
        self._psapi = Psapi() if os.name == 'nt' else None
        self._iphlpapi = IPHelperAPI() if os.name == 'nt' else None

        # Кэш активных сессий по PID: pid -> ProcessSessionRecord
        self._active_sessions: Dict[int, ProcessSessionRecord] = {}
        # Полная история завершенных сессий: instance_id -> ProcessSessionRecord
        self._history_sessions: Dict[str, ProcessSessionRecord] = {}
        # Кэш хешей бинарных файлов: exe_path -> sha256
        self._hash_cache: Dict[str, str] = {}

    def scan_processes_delta(self) -> ProcessLifecycleDelta:
        """Выполняет сканирование процессов и определяет родившиеся и умершие процессы.

        Returns:
            ProcessLifecycleDelta: Дельта событий жизненного цикла (старт / завершение).
        """
        now_ts = time.time()
        now_iso = datetime.now(timezone.utc).isoformat()
        current_pids: Set[int] = set()

        created_sessions: List[ProcessSessionRecord] = []
        terminated_sessions: List[ProcessSessionRecord] = []

        if not PSUTIL_AVAILABLE:
            return ProcessLifecycleDelta(timestamp=now_iso)

        # 1. Сбор текущих активных процессов
        for proc in psutil.process_iter(['pid', 'ppid', 'name', 'exe', 'cmdline', 'username', 'create_time']):
            try:
                info = proc.info
                pid = info.get('pid')
                if not pid or pid == 0:
                    continue
                current_pids.add(pid)

                raw_create = float(info.get('create_time') or 0.0)
                instance_id = f"{pid}_{int(raw_create * 1000)}"

                existing = self._active_sessions.get(pid)
                if existing and existing.instance_id == instance_id:
                    # Процесс тот же самый — обновляем его потребление
                    self._update_session_metrics(existing, proc, now_ts)
                else:
                    if existing:
                        # PID совпал, но instance_id изменился (старый процесс умер, новый занял PID)
                        self._terminate_session(existing, now_ts, now_iso)
                        terminated_sessions.append(existing)

                    # Рождение нового процесса
                    new_session = self._create_session_record(proc, info, raw_create, instance_id, now_iso)
                    self._update_session_metrics(new_session, proc, now_ts)
                    self._active_sessions[pid] = new_session
                    created_sessions.append(new_session)

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # 2. Обнаружение завершившихся процессов (были в _active_sessions, но исчезли)
        for old_pid, old_session in list(self._active_sessions.items()):
            if old_pid not in current_pids:
                self._terminate_session(old_session, now_ts, now_iso)
                terminated_sessions.append(old_session)
                del self._active_sessions[old_pid]

        return ProcessLifecycleDelta(
            timestamp=now_iso,
            created_sessions=created_sessions,
            terminated_sessions=terminated_sessions,
            active_count=len(self._active_sessions),
        )

    def _create_session_record(
        self,
        proc: psutil.Process,
        info: Dict[str, Any],
        raw_create: float,
        instance_id: str,
        now_iso: str,
    ) -> ProcessSessionRecord:
        """Создает начальную запись сессии процесса с атрибуцией инициатора."""
        pid = int(info.get('pid') or 0)
        ppid = int(info.get('ppid') or 0)
        name = str(info.get('name') or "unknown")
        exe = info.get('exe')
        cmdline = " ".join(info.get('cmdline') or []) if info.get('cmdline') else None
        username = info.get('username')

        # Дружественное имя
        friendly_name = KNOWN_APP_FRIENDLY_NAMES.get(name.lower(), name)

        # Вычисление хеша бинарного файла
        binary_hash = self._get_binary_hash(exe) if exe else None

        # Идентификация родителя и типа инициатора
        parent_name, parent_exe, initiator_type = self._resolve_initiator(ppid)

        # ISO время создания
        c_iso = datetime.fromtimestamp(raw_create, tz=timezone.utc).isoformat() if raw_create > 0 else now_iso

        return ProcessSessionRecord(
            instance_id=instance_id,
            pid=pid,
            ppid=ppid,
            name=name,
            friendly_name=friendly_name,
            exe_path=exe,
            binary_hash=binary_hash,
            cmdline=cmdline,
            username=username,
            parent_name=parent_name,
            parent_exe=parent_exe,
            initiator_type=initiator_type,
            created_at=c_iso,
            created_ts=raw_create,
            is_alive=True,
            lifetime_sec=0.0,
        )

    def _resolve_initiator(self, ppid: int) -> tuple[Optional[str], Optional[str], str]:
        """Определяет родительский процесс и классифицирует тип инициатора."""
        if ppid <= 0:
            return None, None, "system_kernel"

        parent_name: Optional[str] = None
        parent_exe: Optional[str] = None

        # 1. Поиск родителя в активных сессиях
        if ppid in self._active_sessions:
            p_sess = self._active_sessions[ppid]
            parent_name = p_sess.name
            parent_exe = p_sess.exe_path

        # 2. Если не найден в кэше — опрос системы
        if not parent_name and PSUTIL_AVAILABLE:
            try:
                parent_proc = psutil.Process(ppid)
                parent_name = parent_proc.name()
                parent_exe = parent_proc.exe()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # 3. Классификация типа инициатора
        initiator_type = "unknown"
        if parent_name:
            p_lower = parent_name.lower()
            if p_lower in ('explorer.exe', 'windowsterminal.exe', 'wt.exe', 'powershell.exe', 'cmd.exe', 'bash.exe'):
                initiator_type = "user_interactive"
            elif p_lower in ('services.exe', 'svchost.exe'):
                initiator_type = "system_service"
            elif p_lower in ('taskhostw.exe', 'taskhost.exe', 'taskeng.exe'):
                initiator_type = "task_scheduler"
            elif p_lower in ('python.exe', 'pythonw.exe', 'node.exe'):
                initiator_type = "script_runner"
            elif p_lower in WINDOWS_SYSTEM_PROCESS_NAMES:
                initiator_type = "system_kernel"
            else:
                initiator_type = "application_child"

        return parent_name, parent_exe, initiator_type

    def _update_session_metrics(
        self, session: ProcessSessionRecord, proc: psutil.Process, now_ts: float
    ) -> None:
        """Обновляет аккумулированные показатели использования ресурсов процессом."""
        # Время жизни
        if session.created_ts > 0:
            session.lifetime_sec = max(0.0, round(now_ts - session.created_ts, 2))

        # CPU
        try:
            cpu_times = proc.cpu_times()
            session.cpu_time_user_sec = round(float(cpu_times.user), 4)
            session.cpu_time_kernel_sec = round(float(cpu_times.system), 4)
            session.cpu_time_total_sec = round(session.cpu_time_user_sec + session.cpu_time_kernel_sec, 4)
        except Exception:
            pass

        # Такты процессора
        if self._kernel32:
            cycles = self._kernel32.get_process_cycle_time(session.pid)
            if cycles is not None:
                session.cpu_cycles = cycles

        # Память (Working Set и Private Bytes)
        if self._psapi:
            mem_ex = self._psapi.get_process_memory_info_ex(session.pid)
            if mem_ex:
                ws_mb = round(mem_ex.working_set_size / (1024 ** 2), 2)
                priv_mb = round(mem_ex.private_usage / (1024 ** 2), 2)
                session.peak_working_set_mb = max(session.peak_working_set_mb, ws_mb)
                session.peak_private_mb = max(session.peak_private_mb, priv_mb)

        # I/O счетчики
        if self._kernel32:
            io_cnt = self._kernel32.get_process_io_counters(session.pid)
            if io_cnt:
                session.io_read_bytes = io_cnt.read_transfer_count
                session.io_write_bytes = io_cnt.write_transfer_count
                session.io_read_ops = io_cnt.read_operation_count
                session.io_write_ops = io_cnt.write_operation_count

    def _terminate_session(
        self, session: ProcessSessionRecord, now_ts: float, now_iso: str
    ) -> None:
        """Фиксирует факт завершения процесса."""
        session.is_alive = False
        session.terminated_ts = now_ts
        session.terminated_at = now_iso
        if session.created_ts > 0:
            session.lifetime_sec = max(0.0, round(now_ts - session.created_ts, 2))
        self._history_sessions[session.instance_id] = session

    def _get_binary_hash(self, exe_path: str) -> Optional[str]:
        """Кэшируемое вычисление SHA256 хеша исполняемого файла."""
        if not exe_path or not os.path.isfile(exe_path):
            return None
        if exe_path in self._hash_cache:
            return self._hash_cache[exe_path]

        try:
            hasher = hashlib.sha256()
            with open(exe_path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    hasher.update(chunk)
            val = hasher.hexdigest()
            self._hash_cache[exe_path] = val
            return val
        except Exception:
            return None

    def get_active_sessions(self) -> List[ProcessSessionRecord]:
        """Возвращает список всех текущих активных сессий процессов."""
        return list(self._active_sessions.values())

    def get_session_by_instance_id(self, instance_id: str) -> Optional[ProcessSessionRecord]:
        """Поиск сессии по уникальному instance_id."""
        for s in self._active_sessions.values():
            if s.instance_id == instance_id:
                return s
        return self._history_sessions.get(instance_id)

    def get_app_summary(
        self,
        app_name: Optional[str] = None,
        username: Optional[str] = None,
        initiator_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Формирует сводный отчет по приложениям и пользователям: когда запускались и что делали.

        Args:
            app_name: Фильтр по имени процесса (например, 'cmd.exe', 'python.exe').
            username: Фильтр по пользователю (например, 'DELL-VOSTRO\\onela').
            initiator_type: Фильтр по типу инициатора ('user_interactive', 'system_service').

        Returns:
            Dict[str, Any]: Аналитическая сводка запусков и ресурсного следа.
        """
        all_sessions = list(self._active_sessions.values()) + list(self._history_sessions.values())

        filtered: List[ProcessSessionRecord] = []
        for s in all_sessions:
            if app_name and app_name.lower() not in s.name.lower():
                continue
            if username and (not s.username or username.lower() not in s.username.lower()):
                continue
            if initiator_type and initiator_type.lower() != s.initiator_type.lower():
                continue
            filtered.append(s)

        total_runs = len(filtered)
        active_now = sum(1 for s in filtered if s.is_alive)
        total_lifetime = sum(s.lifetime_sec for s in filtered)
        total_cpu = sum(s.cpu_time_total_sec for s in filtered)
        total_read_mb = round(sum(s.io_read_bytes for s in filtered) / (1024 ** 2), 2)
        total_write_mb = round(sum(s.io_write_bytes for s in filtered) / (1024 ** 2), 2)
        peak_ws_mb = max((s.peak_working_set_mb for s in filtered), default=0.0)

        initiators_count: Dict[str, int] = {}
        users_count: Dict[str, int] = {}
        for s in filtered:
            init_key = s.parent_name or s.initiator_type
            initiators_count[init_key] = initiators_count.get(init_key, 0) + 1
            u_key = s.username or "Unknown"
            users_count[u_key] = users_count.get(u_key, 0) + 1

        return {
            "filter_app": app_name,
            "filter_user": username,
            "total_launches": total_runs,
            "active_now": active_now,
            "total_lifetime_sec": round(total_lifetime, 2),
            "total_cpu_time_sec": round(total_cpu, 2),
            "peak_memory_mb": peak_ws_mb,
            "total_io_read_mb": total_read_mb,
            "total_io_write_mb": total_write_mb,
            "initiators_distribution": initiators_count,
            "users_distribution": users_count,
            "recent_sessions": [s.to_dict() for s in sorted(filtered, key=lambda x: x.created_ts, reverse=True)[:50]],
        }

