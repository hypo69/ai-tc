# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows API Routers - Telemetry
# =============================================================================
# Description:
#   Слой 7: Высокопроизводительный REST API роутер попроцессной телеметрии
#   и файловой активности (Per-PID Resource & Activity Telemetry Engine).
#
# Usage Examples:
#   GET /api/v1/telemetry/processes/1234
#   GET /api/v1/telemetry/processes/1234/file-activity?limit=50
#   POST /api/v1/telemetry/tracked-directories {"action": "add", "directory_path": "C:\\Projects"}
#
# File: router_telemetry.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 12:55:00
# =============================================================================

from __future__ import annotations

"""FastAPI роутер попроцессной телеметрии ресурсов, активности и отслеживания каталогов."""

import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
import psutil

from apps.windows.sdk.modules.defender.core.process_tree_watcher import ProcessTreeWatcher

try:
    from logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

from apps.windows.telemetry.directory_watcher import DirectoryWatchEngine
from apps.windows.telemetry.models import (
    CpuDetail,
    GpuDetail,
    IoDetail,
    MemoryDetail,
    NetworkDetail,
    ProcessDeepHistoryResponse,
    ProcessFileEventItem,
    ProcessPrivacySensorInfo,
    ProcessSocketConnection,
    ProcessTelemetryResponse,
    TrackedDirectoryRequest,
    TrackedDirectoryResponse,
)
from apps.windows.telemetry.sqlite import TelemetryStorage

router = APIRouter(prefix='/api/v1/telemetry', tags=['Per-PID Telemetry'])


@router.get('/processes/{pid}', response_model=ProcessTelemetryResponse)
async def get_process_telemetry(pid: int) -> ProcessTelemetryResponse:
    """Возвращает детальные метрики потребления ресурсов процессом по его PID (< 5 мс).

    Args:
        pid: Идентификатор процесса Windows.

    Returns:
        ProcessTelemetryResponse: Полный профиль потребления ресурсов (CPU, RAM, GPU, IO, Net).
    """
    storage = TelemetryStorage.get_instance(read_only=True)
    row = storage.get_process_pid_snapshot(pid=pid)

    if row:
        working_set_mb = round(float(row.get('working_set_bytes', 0)) / (1024 * 1024), 2)
        private_bytes_mb = round(float(row.get('private_bytes', 0)) / (1024 * 1024), 2)
        vram_mb = round(float(row.get('gpu_vram_bytes', 0)) / (1024 * 1024), 2)

        return ProcessTelemetryResponse(
            pid=int(row['pid']),
            process_name=str(row['process_name']),
            executable_path=row.get('executable_path'),
            cpu=CpuDetail(
                percent=float(row.get('cpu_percent', 0.0)),
                user_time_ms=int(row.get('user_time_ms', 0)),
                kernel_time_ms=int(row.get('kernel_time_ms', 0)),
                thread_count=int(row.get('thread_count', 1)),
            ),
            memory=MemoryDetail(
                working_set_mb=working_set_mb,
                private_bytes_mb=private_bytes_mb,
                page_faults=int(row.get('page_faults_count', 0)),
            ),
            gpu=GpuDetail(
                vram_dedicated_mb=vram_mb,
                utilization_percent=float(row.get('gpu_utilization', 0.0)),
            ),
            io=IoDetail(
                read_bytes_sec=int(row.get('read_bytes_total', 0)),
                write_bytes_sec=int(row.get('write_bytes_total', 0)),
                handles_count=int(row.get('handle_count', 0)),
                read_ops_total=int(row.get('read_ops_total', 0)),
                write_ops_total=int(row.get('write_ops_total', 0)),
            ),
            network=NetworkDetail(
                bytes_sent_sec=int(row.get('net_bytes_sent_total', 0)),
                bytes_recv_sec=int(row.get('net_bytes_recv_total', 0)),
                active_sockets=0,
            ),
            timestamp=str(row.get('timestamp') or datetime.now(timezone.utc).isoformat()),
        )

    # Fallback на оперативный сбор через psutil для активных процессов
    try:
        proc = psutil.Process(pid)
        mem_info = proc.memory_info()
        cpu_times = proc.cpu_times()
        io_cnt = proc.io_counters() if hasattr(proc, 'io_counters') else None
        num_h = proc.num_handles() if os.name == 'nt' and hasattr(proc, 'num_handles') else 0

        working_set_mb = round(float(getattr(mem_info, 'rss', 0)) / (1024 * 1024), 2)
        private_bytes_mb = round(float(getattr(mem_info, 'vms', 0) or getattr(mem_info, 'private', 0) or 0) / (1024 * 1024), 2)

        return ProcessTelemetryResponse(
            pid=pid,
            process_name=proc.name(),
            executable_path=proc.exe() if hasattr(proc, 'exe') else None,
            cpu=CpuDetail(
                percent=proc.cpu_percent(interval=None),
                user_time_ms=int(cpu_times.user * 1000) if cpu_times else 0,
                kernel_time_ms=int(cpu_times.system * 1000) if cpu_times else 0,
                thread_count=proc.num_threads(),
            ),
            memory=MemoryDetail(
                working_set_mb=working_set_mb,
                private_bytes_mb=private_bytes_mb,
                page_faults=int(getattr(mem_info, 'num_page_faults', 0)),
            ),
            gpu=GpuDetail(
                vram_dedicated_mb=0.0,
                utilization_percent=0.0,
            ),
            io=IoDetail(
                read_bytes_sec=int(getattr(io_cnt, 'read_bytes', 0)) if io_cnt else 0,
                write_bytes_sec=int(getattr(io_cnt, 'write_bytes', 0)) if io_cnt else 0,
                handles_count=num_h,
                read_ops_total=int(getattr(io_cnt, 'read_count', 0)) if io_cnt else 0,
                write_ops_total=int(getattr(io_cnt, 'write_count', 0)) if io_cnt else 0,
            ),
            network=NetworkDetail(
                bytes_sent_sec=0,
                bytes_recv_sec=0,
                active_sockets=len(proc.net_connections()) if hasattr(proc, 'net_connections') else 0,
            ),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        raise HTTPException(
            status_code=404,
            detail=f'Процесс с PID {pid} не найден или завершил выполнение'
        )


def _get_gui_resources(pid: int) -> tuple[int, int]:
    """Возвращает количество GDI и USER объектов процесса через Win32 API."""
    if os.name != 'nt':
        return 0, 0
    try:
        import ctypes
        kernel32 = getattr(ctypes.windll, 'kernel32', None)
        user32 = getattr(ctypes.windll, 'user32', None)
        if not (kernel32 and user32):
            return 0, 0
        h_process = kernel32.OpenProcess(0x0400 | 0x0010, False, pid)
        if not h_process:
            return 0, 0
        try:
            gdi = int(user32.GetGuiResources(h_process, 0))
            user = int(user32.GetGuiResources(h_process, 1))
            return max(0, gdi), max(0, user)
        finally:
            kernel32.CloseHandle(h_process)
    except Exception:
        return 0, 0


def _get_process_camera_mic_status(process_name: str, exe_path: Optional[str] = None) -> tuple[ProcessPrivacySensorInfo, ProcessPrivacySensorInfo]:
    """Проверяет статус обращения процесса к микрофону и веб-камере через Windows CapabilityAccessManager."""
    mic_info = ProcessPrivacySensorInfo(is_active_now=False, access_allowed=True)
    cam_info = ProcessPrivacySensorInfo(is_active_now=False, access_allowed=True)

    if os.name != 'nt':
        return mic_info, cam_info

    try:
        import winreg
    except ImportError:
        return mic_info, cam_info

    def _filetime_to_iso(ft: int) -> Optional[str]:
        if not ft:
            return None
        try:
            us = (ft - 116444736000000000) // 10
            if us < 0:
                return None
            return datetime.fromtimestamp(us / 1_000_000, tz=timezone.utc).isoformat()
        except Exception:
            return None

    def _check_capability(cap_name: str) -> ProcessPrivacySensorInfo:
        base_path = rf'Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\{cap_name}'
        norm_name = (process_name or '').lower().strip()
        norm_exe = (exe_path or '').lower().replace('/', '\\').strip()

        for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                with winreg.OpenKey(root, base_path, 0, winreg.KEY_READ) as key:
                    num_subkeys, _, _ = winreg.QueryInfoKey(key)
                    for i in range(num_subkeys):
                        sub_name = winreg.EnumKey(key, i)
                        if sub_name == 'NonPackaged':
                            np_path = rf'{base_path}\NonPackaged'
                            try:
                                with winreg.OpenKey(root, np_path, 0, winreg.KEY_READ) as np_key:
                                    np_count, _, _ = winreg.QueryInfoKey(np_key)
                                    for j in range(np_count):
                                        app_sub = winreg.EnumKey(np_key, j)
                                        clean_sub = app_sub.replace('#', '\\').lower()
                                        if norm_name in clean_sub or (norm_exe and (norm_exe in clean_sub or clean_sub in norm_exe)):
                                            try:
                                                with winreg.OpenKey(np_key, app_sub, 0, winreg.KEY_READ) as app_key:
                                                    stop_val, _ = winreg.QueryValueEx(app_key, 'LastUsedTimeStop')
                                                    start_val, _ = winreg.QueryValueEx(app_key, 'LastUsedTimeStart')
                                                    is_active = (stop_val == 0 and start_val > 0)
                                                    last_used_iso = _filetime_to_iso(start_val if is_active else stop_val)
                                                    return ProcessPrivacySensorInfo(
                                                        is_active_now=is_active,
                                                        last_used=last_used_iso,
                                                        access_allowed=True,
                                                        app_identifier=app_sub.replace('#', '\\')
                                                    )
                                            except Exception:
                                                continue
                            except Exception:
                                pass
                        else:
                            if norm_name in sub_name.lower():
                                try:
                                    with winreg.OpenKey(key, sub_name, 0, winreg.KEY_READ) as uwp_key:
                                        stop_val, _ = winreg.QueryValueEx(uwp_key, 'LastUsedTimeStop')
                                        start_val, _ = winreg.QueryValueEx(uwp_key, 'LastUsedTimeStart')
                                        is_active = (stop_val == 0 and start_val > 0)
                                        last_used_iso = _filetime_to_iso(start_val if is_active else stop_val)
                                        return ProcessPrivacySensorInfo(
                                            is_active_now=is_active,
                                            last_used=last_used_iso,
                                            access_allowed=True,
                                            app_identifier=sub_name
                                        )
                                except Exception:
                                    pass
            except Exception:
                pass
        return ProcessPrivacySensorInfo(is_active_now=False, access_allowed=True)

    mic_info = _check_capability('microphone')
    cam_info = _check_capability('webcam')
    return mic_info, cam_info


def _evaluate_process_suspicion(
    proc: Optional[psutil.Process],
    proc_name: str,
    cmd_line: Optional[str],
    parent_name: Optional[str],
    mic_status: ProcessPrivacySensorInfo,
    cam_status: ProcessPrivacySensorInfo,
    user_objects: int,
    gdi_objects: int,
) -> tuple[int, str, int, int, List[str]]:
    """Анализирует поведение процесса, порождение дочерних процессов и аномалии.

    Args:
        proc: Экземпляр psutil.Process (если доступен).
        proc_name: Имя исполняемого файла.
        cmd_line: Командная строка запуска.
        parent_name: Имя родительского процесса.
        mic_status: Телеметрия датчика микрофона.
        cam_status: Телеметрия датчика камеры.
        user_objects: Количество USER-дескрипторов.
        gdi_objects: Количество GDI-дескрипторов.

    Returns:
        tuple[int, str, int, int, List[str]]: Кортеж (score, level, powershell_count, suspicious_children_count, triggers).
    """
    triggers: List[str] = []
    score = 0
    p_name_lower = (proc_name or '').lower()
    cmd_lower = (cmd_line or '').lower()
    parent_lower = (parent_name or '').lower()

    # 1. Анализ дочерних процессов (порождение шеллов и лавины окон PowerShell)
    powershell_count = 0
    suspicious_children = 0
    if proc:
        try:
            children = proc.children(recursive=True)
            for ch in children:
                try:
                    cname = ch.name().lower()
                    if cname in ('powershell.exe', 'pwsh.exe'):
                        powershell_count += 1
                        suspicious_children += 1
                    elif cname in ('cmd.exe', 'wscript.exe', 'cscript.exe', 'mshta.exe', 'rundll32.exe', 'bitsadmin.exe', 'certutil.exe'):
                        suspicious_children += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass

    # Триггеры на порождение шеллов
    if powershell_count >= 3:
        triggers.append(f"Аномальное порождение процессов PowerShell: запущено {powershell_count} дочерних экземпляров (вероятен шторм скриптов / атака)")
        score += 40
    elif powershell_count in (1, 2):
        triggers.append(f"Порождение дочернего PowerShell ({powershell_count} экз.)")
        score += 15

    if suspicious_children > powershell_count:
        other_children = suspicious_children - powershell_count
        triggers.append(f"Порождение системных интерпретаторов/утилит (cmd/wscript/mshta/certutil): {other_children} экз.")
        score += 20

    # 2. Аномальные связки родитель -> потомок (по мотивам ProcessTreeWatcher)
    if parent_lower in ProcessTreeWatcher.SUSPICIOUS_PARENTS and p_name_lower in ProcessTreeWatcher.DANGEROUS_CHILDREN:
        parent_title = ProcessTreeWatcher.SUSPICIOUS_PARENTS.get(parent_lower, parent_lower)
        triggers.append(f"Опасный запуск: офисное приложение/ридер '{parent_title}' запустило интерпретатор '{proc_name}'")
        score += 45

    # 3. Подозрительные шаблоны командной строки
    for pattern, desc in ProcessTreeWatcher.SUSPICIOUS_CMD_PATTERNS:
        if pattern.search(cmd_line or ''):
            triggers.append(f"Опасная командная строка: {desc}")
            score += 35

    # Дополнительные шаблоны скрытия окон и аргументов
    hidden_pattern = re.compile(r'-(w|windowstyle)\s+(hidden|minimized)|-windowstyle\s+1', re.IGNORECASE)
    if hidden_pattern.search(cmd_lower):
        triggers.append("Запуск процесса в скрытом окне (-WindowStyle Hidden / Minimized)")
        score += 25

    if re.search(r'-(executionpolicy|ep)\s+bypass|-nop(rofile)?', cmd_lower):
        if not any('Bypass' in t for t in triggers):
            triggers.append("Обход политики безопасности PowerShell (-ExecutionPolicy Bypass / -NoProfile)")
            score += 20

    # 4. Скрытый доступ к микрофону / камере без оконного интерфейса
    known_media_apps = {
        'zoom.exe', 'teams.exe', 'discord.exe', 'obs64.exe', 'obs32.exe', 'chrome.exe',
        'msedge.exe', 'firefox.exe', 'telegram.exe', 'skype.exe', 'vlc.exe', 'audacity.exe'
    }
    if (mic_status.is_active_now or cam_status.is_active_now) and p_name_lower not in known_media_apps:
        if user_objects == 0 and gdi_objects == 0:
            sensor = "микрофону и камере" if (mic_status.is_active_now and cam_status.is_active_now) else ("микрофону" if mic_status.is_active_now else "камере")
            triggers.append(f"Скрытый фоновый захват доступа к {sensor} без графических окон (GDI/USER=0)")
            score += 50

    # 5. Итоговый балл и уровень
    score = min(100, score)
    if score >= 80:
        level = "CRITICAL"
    elif score >= 60:
        level = "HIGH"
    elif score >= 35:
        level = "MEDIUM"
    elif score >= 15:
        level = "LOW"
    else:
        level = "SAFE"

    return score, level, powershell_count, suspicious_children, triggers


@router.get('/processes/{pid}/deep-history', response_model=ProcessDeepHistoryResponse)
async def get_process_deep_history(pid: int) -> ProcessDeepHistoryResponse:
    """Возвращает полную историю жизненного цикла и накопленной телеметрии процесса.

    Включает:
      - Когда и кем запущен (start_time, uptime, user_name, ppid, parent_name, cmdline);
      - Накопленное потребление памяти (working_set, peak_working_set, private_bytes, page_faults);
      - Накопленный ввод-вывод диска (всего прочитано/записано байт и МБ, IOPS);
      - Накопленный процессор (суммарное user_time, kernel_time, total_time, потоки);
      - Сетевой трафик и список открытых сокетов;
      - Доступ к оборудованию конфиденциальности (камера, микрофон);
      - Дескрипторы ОС (Handles, GDI/USER objects).
    """
    proc: Optional[psutil.Process] = None
    try:
        proc = psutil.Process(pid)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass

    # Данные из базы SQLite телеметрии
    storage = TelemetryStorage.get_instance(read_only=True)
    sqlite_row = storage.get_process_pid_snapshot(pid=pid)

    # Если процесс завершился и нет в SQLite
    if not proc and not sqlite_row:
        raise HTTPException(
            status_code=404,
            detail=f'История процесса с PID {pid} не найдена (процесс завершен и отсутствует в базе телеметрии)'
        )

    # 1. Паспорт запуска
    proc_name = ''
    exe_path = None
    cmd_line = None
    start_time_iso = ''
    uptime_sec = 0.0
    user_name = None
    ppid_val = None
    parent_name_val = None
    session_id_val = None

    if proc:
        try:
            proc_name = proc.name()
        except Exception:
            proc_name = str(pid)
        try:
            exe_path = proc.exe()
        except Exception:
            pass
        try:
            cmd_line = " ".join(proc.cmdline())
        except Exception:
            pass
        try:
            c_time = proc.create_time()
            start_time_iso = datetime.fromtimestamp(c_time, tz=timezone.utc).isoformat()
            uptime_sec = max(0.0, round(time.time() - c_time, 1))
        except Exception:
            pass
        try:
            user_name = proc.username()
        except Exception:
            pass
        try:
            ppid_val = proc.ppid()
            p_obj = proc.parent()
            if p_obj:
                parent_name_val = p_obj.name()
        except Exception:
            pass
        try:
            session_id_val = getattr(proc, 'terminal', lambda: None)() or None
        except Exception:
            pass

    if sqlite_row:
        if not proc_name:
            proc_name = str(sqlite_row.get('process_name', pid))
        if not exe_path:
            exe_path = sqlite_row.get('executable_path')
        if not start_time_iso:
            start_time_iso = str(sqlite_row.get('timestamp') or '')

    # 2. Память
    ws_mb = 0.0
    peak_ws_mb = 0.0
    priv_mb = 0.0
    page_faults = 0

    if proc:
        try:
            mem = proc.memory_info()
            ws_mb = round(float(mem.rss) / (1024 * 1024), 2)
            peak_ws_mb = round(float(getattr(mem, 'peak_wset', mem.rss)) / (1024 * 1024), 2)
            priv_mb = round(float(getattr(mem, 'private', getattr(mem, 'vms', 0))) / (1024 * 1024), 2)
            page_faults = int(getattr(mem, 'num_page_faults', 0))
        except Exception:
            pass
    elif sqlite_row:
        ws_mb = round(float(sqlite_row.get('working_set_bytes', 0)) / (1024 * 1024), 2)
        peak_ws_mb = ws_mb
        priv_mb = round(float(sqlite_row.get('private_bytes', 0)) / (1024 * 1024), 2)
        page_faults = int(sqlite_row.get('page_faults_count', 0))

    # 3. Диск (накопленный I/O)
    read_bytes = 0
    write_bytes = 0
    read_ops = 0
    write_ops = 0

    if proc:
        try:
            io_cnt = proc.io_counters()
            if io_cnt:
                read_bytes = int(io_cnt.read_bytes)
                write_bytes = int(io_cnt.write_bytes)
                read_ops = int(io_cnt.read_count)
                write_ops = int(io_cnt.write_count)
        except Exception:
            pass
    elif sqlite_row:
        read_bytes = int(sqlite_row.get('read_bytes_total', 0))
        write_bytes = int(sqlite_row.get('write_bytes_total', 0))
        read_ops = int(sqlite_row.get('read_ops_total', 0))
        write_ops = int(sqlite_row.get('write_ops_total', 0))

    read_mb = round(float(read_bytes) / (1024 * 1024), 2)
    write_mb = round(float(write_bytes) / (1024 * 1024), 2)

    # 4. Процессор
    cpu_pct = 0.0
    u_time = 0.0
    k_time = 0.0
    threads_num = 1

    if proc:
        try:
            cpu_pct = float(proc.cpu_percent(interval=None))
            cpu_times = proc.cpu_times()
            if cpu_times:
                u_time = round(float(cpu_times.user), 2)
                k_time = round(float(cpu_times.system), 2)
            threads_num = int(proc.num_threads())
        except Exception:
            pass
    elif sqlite_row:
        cpu_pct = float(sqlite_row.get('cpu_percent', 0.0))
        u_time = round(float(sqlite_row.get('user_time_ms', 0)) / 1000.0, 2)
        k_time = round(float(sqlite_row.get('kernel_time_ms', 0)) / 1000.0, 2)
        threads_num = int(sqlite_row.get('thread_count', 1))

    total_cpu_time = round(u_time + k_time, 2)

    # 5. Сетевые сокеты и трафик
    net_sent = 0
    net_recv = 0
    if sqlite_row:
        net_sent = int(sqlite_row.get('net_bytes_sent_total', 0))
        net_recv = int(sqlite_row.get('net_bytes_recv_total', 0))

    active_sockets: List[ProcessSocketConnection] = []
    if proc:
        try:
            conns = proc.net_connections(kind='inet')
            for c in conns:
                l_addr = f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else ""
                r_addr = f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else ""
                proto = "TCP" if c.type == 1 else "UDP"
                active_sockets.append(ProcessSocketConnection(
                    protocol=proto,
                    local_address=l_addr,
                    remote_address=r_addr,
                    status=str(c.status or 'NONE')
                ))
        except Exception:
            pass

    # 6. Оборудование и приватность (микрофон, камера)
    mic_status, cam_status = _get_process_camera_mic_status(proc_name, exe_path)

    # 7. Дескрипторы и UI-объекты
    h_count = 0
    if proc:
        try:
            h_count = proc.num_handles()
        except Exception:
            pass
    elif sqlite_row:
        h_count = int(sqlite_row.get('handle_count', 0))

    gdi_objs, user_objs = _get_gui_resources(pid)

    # 8. Видео / GPU
    vram_mb = 0.0
    gpu_util = 0.0
    if sqlite_row:
        vram_mb = round(float(sqlite_row.get('gpu_vram_bytes', 0)) / (1024 * 1024), 2)
        gpu_util = float(sqlite_row.get('gpu_utilization', 0.0))

    # 9. Оценка подозрительности и аномалий поведения (Process Suspicion & Anomaly Analysis)
    susp_score, susp_level, ps_count, susp_child_count, susp_triggers = _evaluate_process_suspicion(
        proc=proc,
        proc_name=proc_name,
        cmd_line=cmd_line,
        parent_name=parent_name_val,
        mic_status=mic_status,
        cam_status=cam_status,
        user_objects=user_objs,
        gdi_objects=gdi_objs,
    )

    return ProcessDeepHistoryResponse(
        pid=pid,
        process_name=proc_name,
        executable_path=exe_path,
        command_line=cmd_line,
        start_time=start_time_iso,
        uptime_seconds=uptime_sec,
        user_name=user_name,
        ppid=ppid_val,
        parent_name=parent_name_val,
        session_id=session_id_val,
        memory_working_set_mb=ws_mb,
        memory_peak_working_set_mb=peak_ws_mb,
        memory_private_bytes_mb=priv_mb,
        memory_page_faults_total=page_faults,
        disk_read_bytes_total=read_bytes,
        disk_write_bytes_total=write_bytes,
        disk_read_mb_total=read_mb,
        disk_write_mb_total=write_mb,
        disk_read_ops_total=read_ops,
        disk_write_ops_total=write_ops,
        cpu_percent=cpu_pct,
        cpu_user_time_sec=u_time,
        cpu_kernel_time_sec=k_time,
        cpu_total_time_sec=total_cpu_time,
        thread_count=threads_num,
        gpu_vram_mb=vram_mb,
        gpu_load_percent=gpu_util,
        net_bytes_sent_total=net_sent,
        net_bytes_recv_total=net_recv,
        net_sent_mb_total=round(float(net_sent) / (1024 * 1024), 2),
        net_recv_mb_total=round(float(net_recv) / (1024 * 1024), 2),
        active_sockets_count=len(active_sockets),
        sockets=active_sockets,
        microphone=mic_status,
        camera=cam_status,
        handles_count=h_count,
        gdi_objects=gdi_objs,
        user_objects=user_objs,
        suspicion_score=susp_score,
        suspicion_level=susp_level,
        powershell_spawns_count=ps_count,
        suspicious_children_count=susp_child_count,
        suspicion_triggers=susp_triggers,
        sqlite_snapshots_count=1 if sqlite_row else 0,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.get('/processes/{pid}/file-activity', response_model=List[ProcessFileEventItem])
async def get_process_file_activity(
    pid: int,
    directory: Optional[str] = Query(None, description='Фильтр по целевой директории'),
    limit: int = Query(50, ge=1, le=500, description='Максимальное число событий')
) -> List[ProcessFileEventItem]:
    """Возвращает историю файловых операций, инициированных указанным PID.

    Args:
        pid: Идентификатор процесса.
        directory: Опциональный фильтр директории.
        limit: Лимит записей.

    Returns:
        List[ProcessFileEventItem]: Список файловых событий процесса из базы данных.
    """
    storage = TelemetryStorage.get_instance(read_only=True)
    events = storage.get_process_file_events(pid=pid, directory=directory, limit=limit)
    result: List[ProcessFileEventItem] = []
    for ev in events:
        result.append(ProcessFileEventItem(
            event_id=int(ev.get('event_id', ev.get('id', 0))),
            pid=int(ev.get('pid', pid)),
            process_name=str(ev.get('process_name', '')),
            action_type=str(ev.get('action_type', ev.get('action', 'MODIFY'))),
            target_directory=str(ev.get('target_directory', ev.get('target_folder', ''))),
            file_path=str(ev.get('file_path', '')),
            bytes_affected=int(ev.get('bytes_affected', ev.get('bytes_count', 0)) or 0),
            timestamp=str(ev.get('timestamp') or datetime.now(timezone.utc).isoformat()),
        ))
    return result


@router.post('/tracked-directories', response_model=TrackedDirectoryResponse)
async def manage_tracked_directories(request: TrackedDirectoryRequest) -> TrackedDirectoryResponse:
    """Управление списком отслеживаемых контролируемых директорий.

    Args:
        request: Запрос на добавление ('add') или удаление ('remove') директории.

    Returns:
        TrackedDirectoryResponse: Статус операции и обновленный список директорий.
    """
    engine = DirectoryWatchEngine.get_instance()
    action = request.action.lower().strip()
    path = request.directory_path.strip()

    if action == 'add':
        engine.add_directory(path)
    elif action == 'remove':
        engine.remove_directory(path)
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Недопустимое действие '{request.action}'. Используйте 'add' или 'remove'."
        )

    return TrackedDirectoryResponse(
        status='ok',
        action=action,
        directory_path=path,
        tracked_directories=engine.get_tracked_directories()
    )


@router.get('/tracked-directories')
async def list_tracked_directories() -> Dict[str, Any]:
    """Возвращает список всех зарегистрированных отслеживаемых директорий."""
    engine = DirectoryWatchEngine.get_instance()
    return {
        'status': 'ok',
        'tracked_directories': engine.get_tracked_directories()
    }


@router.get('/time-ranges')
async def get_telemetry_time_ranges() -> Dict[str, Any]:
    """Возвращает доступные временные интервалы (секунды, минуты, часы, дни, недели, месяцы, все) на основе возраста данных в БД."""
    try:
        storage = TelemetryStorage.get_instance(read_only=True)
        return storage.get_telemetry_time_ranges()
    except Exception as exc:
        logger.error(f"[router_telemetry] Ошибка вычисления доступных диапазонов времени: {exc}", exc_info=True)
        return {
            'status': 'error',
            'error': str(exc),
            'intervals': [
                {'id': 'seconds', 'label': 'Секунды', 'seconds': 120, 'is_available': True},
                {'id': 'all', 'label': 'Все', 'seconds': None, 'is_available': True},
            ],
            'available_ids': ['seconds', 'all']
        }


@router.get('/history')
async def get_telemetry_history(
    interval: str = Query('seconds', description="Временной интервал: seconds, minutes, hours, days, weeks, months, all"),
    metric: str = Query('all', description="Категория метрики: all, cpu, gpu, ram, net, storage"),
    limit: int = Query(120, ge=10, le=500, description="Максимальное количество точек")
) -> Dict[str, Any]:
    """Возвращает агрегированную историю метрик под выбранный временной интервал."""
    try:
        storage = TelemetryStorage.get_instance(read_only=True)
        rows = storage.get_history_by_interval(interval=interval, metric=metric, limit=limit)
        return {
            'status': 'ok',
            'interval': interval,
            'metric': metric,
            'count': len(rows),
            'history': rows
        }
    except Exception as exc:
        logger.error(f"[router_telemetry] Ошибка чтения истории телеметрии: {exc}", exc_info=True)
        return {
            'status': 'error',
            'interval': interval,
            'metric': metric,
            'error': str(exc),
            'history': []
        }


def init_router() -> APIRouter:
    """Возвращает сконфигурированный FastAPI APIRouter для Auto-Discovery."""
    return router


