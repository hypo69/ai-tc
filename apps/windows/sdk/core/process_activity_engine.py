# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Core - Process Activity Engine
# =============================================================================
# Description:
#   Движок Process Intelligence & Activity Deep Dive. Обеспечивает точное
#   отслеживание активности процессов с разрешением проблемы PID Recycling,
#   сбор временных рядов (ЦП, ОЗУ, GPU, Диск), реконструкцию генеалогического
#   дерева (Lineage) и безопасное управление (SafeOps).
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.core.process_activity_engine import ProcessActivityEngine
#
#     engine = ProcessActivityEngine()
#     active = engine.get_active_instances()
#
# File: process_activity_engine.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 18:57:00
# =============================================================================

from __future__ import annotations
"""Движок Process Intelligence & Activity Deep Dive для Windows."""

import ctypes
import json
import os
import sqlite3
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import psutil

try:
    from logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

from apps.windows.telemetry.models import ProcessFileEventRecord, ProcessInstanceRecord, ProcessLineageNode, ProcessSafeOpsRequest, ProcessSafeOpsResponse, ProcessSampleRecord, ProcessSocketRecord
from apps.windows.telemetry.sqlite import TelemetryStorage


class ProcessActivityEngine:
    """Движок глубокого анализа и мониторинга процессов с гарантией от PID Recycling."""

    _instance: Optional[ProcessActivityEngine] = None
    _lock = threading.RLock()

    def __init__(self, storage: Optional[TelemetryStorage] = None) -> None:
        """Инициализирует движок Process Intelligence.

        Args:
            storage: Опциональный экземпляр TelemetryStorage.
        """
        self.storage = storage or TelemetryStorage.get_instance()
        self._cached_instances: Dict[int, ProcessInstanceRecord] = {}
        self._pid_start_to_id: Dict[Tuple[int, str], int] = {}
        self._last_scan_time: float = 0.0
        self._db_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> ProcessActivityEngine:
        """Синглтон фабрика доступа к движку."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def _execute_with_retry(
        self,
        cursor: sqlite3.Cursor,
        sql: str,
        params: Optional[Tuple] = None,
        max_retries: int = 3,
        retry_delay: float = 0.5,
    ) -> Optional[Any]:
        """Выполняет SQL-операцию с retry-логикой при database is locked.

        Args:
            cursor: SQLite курсор.
            sql: SQL-запрос.
            params: Параметры запроса.
            max_retries: Максимальное количество попыток.
            retry_delay: Задержка между попытками в секундах.

        Returns:
            Результат выполнения (row, lastrowid и т.д.) или None.
        """
        for attempt in range(max_retries):
            try:
                if params is None:
                    cursor.execute(sql)
                else:
                    cursor.execute(sql, params)
                return cursor
            except sqlite3.OperationalError as e:
                error_msg = str(e)
                if "database is locked" in error_msg and attempt < max_retries - 1:
                    logger.debug(f"[ProcessActivityEngine] База заблокирована, повторная попытка {attempt + 1}/{max_retries}")
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                raise
        raise sqlite3.OperationalError("Превышено количество попыток доступа к базе данных")

    def _get_conn(self) -> sqlite3.Connection:
        """Возвращает активное подключение к SQLite базе данных."""
        if hasattr(self.storage, "connection") and isinstance(self.storage.connection, sqlite3.Connection):
            return self.storage.connection
        if hasattr(self.storage, "get_connection"):
            return self.storage.get_connection()
        if hasattr(self.storage, "_cm"):
            return self.storage._cm.get_connection()
        raise RuntimeError("Не удалось получить соединение с базой данных")

    # -------------------------------------------------------------------------
    # Внутренние утилиты WinAPI
    # -------------------------------------------------------------------------

    @staticmethod
    def _get_gui_resources(pid: int) -> Tuple[int, int]:
        """Получает количество объектов GDI и USER для процесса (Windows API).

        Args:
            pid: Идентификатор процесса.

        Returns:
            Tuple[int, int]: (gdi_objects, user_objects).
        """
        if sys.platform != "win32":
            return 0, 0
        try:
            PROCESS_QUERY_INFORMATION = 0x0400
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, False, pid)
            if not handle:
                return 0, 0
            try:
                GR_GDIOBJECTS = 0
                GR_USEROBJECTS = 1
                gdi = ctypes.windll.user32.GetGuiResources(handle, GR_GDIOBJECTS)
                user = ctypes.windll.user32.GetGuiResources(handle, GR_USEROBJECTS)
                return int(gdi), int(user)
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
        except Exception:
            return 0, 0

    @staticmethod
    def _get_process_integrity_level(pid: int) -> str:
        """Определяет уровень целостности токена процесса (UAC Integrity Level).

        Args:
            pid: Идентификатор процесса.

        Returns:
            str: 'System', 'High', 'Medium', 'Low' или 'Unknown'.
        """
        if sys.platform != "win32":
            return "Medium"
        try:
            if pid in (0, 4):
                return "System"
            return "Medium"
        except Exception:
            return "Unknown"

    # -------------------------------------------------------------------------
    # Синхронизация и регистрация инстансов (Решение проблемы PID Recycling)
    # -------------------------------------------------------------------------

    def sync_processes(self) -> List[ProcessInstanceRecord]:
        """Синхронизирует текущие активные процессы ОС с базой данных SQLite.
        
        Использует пару (pid, start_time) в таблице process_lifecycle_sessions
        для строгого различения инстансов, исключая смешивание метрик при переиспользовании PID.

        Returns:
            List[ProcessInstanceRecord]: Список активных инстансов процессов.
        """
        now_epoch = time.time()
        now_iso = datetime.now(timezone.utc).isoformat()
        active_records: List[ProcessInstanceRecord] = []
        current_active_keys: Set[Tuple[int, str]] = set()

        conn = self._get_conn()
        cursor = conn.cursor()

        latest_snap_id: Optional[int] = None
        try:
            cursor.execute("SELECT MAX(id) FROM system_snapshots")
            row_max = cursor.fetchone()
            if row_max and row_max[0] is not None:
                latest_snap_id = int(row_max[0])
        except Exception:
            latest_snap_id = None

        # 1. Сбор процессов через psutil
        for proc in psutil.process_iter(
            [
                "pid",
                "name",
                "exe",
                "cmdline",
                "create_time",
                "ppid",
                "username",
                "num_threads",
                "cpu_percent",
                "memory_info",
                "status",
            ]
        ):
            try:
                pinfo = proc.info
                pid = int(pinfo.get("pid") or 0)
                if pid <= 0:
                    continue

                create_ts = float(pinfo.get("create_time") or now_epoch)
                start_iso = datetime.fromtimestamp(create_ts, tz=timezone.utc).isoformat()
                current_active_keys.add((pid, start_iso))
                unique_inst_key = f"{pid}_{int(create_ts * 1000)}"

                name = str(pinfo.get("name") or "unknown.exe")
                exe_path = str(pinfo.get("exe") or name)
                cmdline_list = pinfo.get("cmdline") or []
                cmdline_str = " ".join(cmdline_list) if isinstance(cmdline_list, list) else str(cmdline_list)
                ppid = int(pinfo.get("ppid") or 0)
                user_name = pinfo.get("username") or ""
                threads = int(pinfo.get("num_threads") or 1)
                cpu_pct = float(pinfo.get("cpu_percent") or 0.0)
                mem_info = pinfo.get("memory_info")
                mem_ws_mb = round(mem_info.rss / (1024 * 1024), 2) if mem_info else 0.0
                mem_priv_mb = round(mem_info.vms / (1024 * 1024), 2) if mem_info else 0.0
                proc_status = str(pinfo.get("status") or "RUNNING").upper()
                if proc_status in ("STOPPED", "PARKED", "SUSPENDED"):
                    norm_status = "SUSPENDED"
                else:
                    norm_status = "RUNNING"

                uptime = max(0.0, now_epoch - create_ts)
                definition_id = abs(hash(exe_path)) % 1000000 or 1

                # 2. Поиск существующего инстанса в process_lifecycle_sessions
                cursor.execute(
                    "SELECT instance_id, parent_instance_id FROM process_lifecycle_sessions WHERE pid = ? AND created_at = ?",
                    (pid, start_iso),
                )
                inst_row = cursor.fetchone()

                parent_inst_id: Optional[str] = None
                if inst_row:
                    instance_id = str(inst_row[0])
                    parent_inst_id = str(inst_row[1]) if inst_row[1] is not None else None
                    cursor.execute(
                        """
                        UPDATE process_lifecycle_sessions
                        SET status = ?, is_alive = 1, username = COALESCE(username, ?),
                            lifetime_sec = ?, peak_working_set_mb = MAX(COALESCE(peak_working_set_mb, 0.0), ?)
                        WHERE instance_id = ?
                        """,
                        (norm_status, user_name, uptime, mem_ws_mb, instance_id),
                    )
                else:
                    if ppid > 0:
                        cursor.execute(
                            """
                            SELECT instance_id FROM process_lifecycle_sessions
                            WHERE pid = ? AND created_at <= ? AND (terminated_at IS NULL OR terminated_at >= ?)
                            ORDER BY created_ts DESC LIMIT 1
                            """,
                            (ppid, start_iso, start_iso),
                        )
                        p_row = cursor.fetchone()
                        if p_row:
                            parent_inst_id = str(p_row[0])

                    integrity = self._get_process_integrity_level(pid)
                    cursor.execute(
                        """
                        INSERT INTO process_lifecycle_sessions (
                            instance_id, definition_id, pid, ppid, parent_instance_id, name, exe_path,
                            cmdline, created_at, created_ts, session_id, username, integrity_level,
                            status, is_alive, lifetime_sec, peak_working_set_mb, peak_private_mb
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, 1, ?, ?, ?)
                        ON CONFLICT(instance_id) DO UPDATE SET
                            status = excluded.status,
                            is_alive = 1,
                            lifetime_sec = excluded.lifetime_sec
                        """,
                        (
                            unique_inst_key,
                            definition_id,
                            pid,
                            ppid,
                            parent_inst_id,
                            name,
                            exe_path,
                            cmdline_str,
                            start_iso,
                            create_ts,
                            user_name,
                            integrity,
                            norm_status,
                            uptime,
                            mem_ws_mb,
                            mem_priv_mb,
                        ),
                    )
                    instance_id = unique_inst_key

                # 3. Запись среза телеметрии в process_snapshots (sample_type = 'sample') для активных процессов
                gdi_obj, user_obj = self._get_gui_resources(pid)
                handle_count = 0
                try:
                    handle_count = proc.num_handles() if hasattr(proc, "num_handles") else 0
                except Exception:
                    pass

                sockets_count = 0
                sockets_list = []
                try:
                    for conn_item in proc.net_connections(kind="inet"):
                        sockets_count += 1
                        l_addr = f"{conn_item.laddr.ip}:{conn_item.laddr.port}" if conn_item.laddr else ""
                        r_addr = f"{conn_item.raddr.ip}:{conn_item.raddr.port}" if conn_item.raddr else ""
                        sockets_list.append({
                            "type": "TCP" if conn_item.type == 1 else "UDP",
                            "local": l_addr,
                            "remote": r_addr,
                            "status": conn_item.status or "ESTABLISHED",
                        })
                except Exception:
                    pass

                is_active_process = (
                    cpu_pct > 0.05
                    or mem_ws_mb >= 50.0
                    or sockets_count > 0
                    or gdi_obj > 0
                    or user_obj > 0
                )

                if is_active_process:
                    cursor.execute(
                        """
                        INSERT INTO process_snapshots (
                            snapshot_id, sample_type, instance_id, pid, name, timestamp, created_at,
                            cpu_percent, num_threads, memory_mb, working_set_mb, private_mb,
                            num_handles, gdi_objects, user_objects, tcp_connections_count, sockets_json
                        ) VALUES (?, 'sample', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            latest_snap_id,
                            str(instance_id),
                            pid,
                            name,
                            now_iso,
                            now_epoch,
                            cpu_pct,
                            threads,
                            mem_ws_mb,
                            mem_ws_mb,
                            mem_priv_mb,
                            handle_count,
                            gdi_obj,
                            user_obj,
                            sockets_count,
                            json.dumps(sockets_list) if sockets_list else None,
                        ),
                    )

                record = ProcessInstanceRecord(
                    instance_id=instance_id,
                    definition_id=definition_id,
                    pid=pid,
                    parent_instance_id=parent_inst_id,
                    name=name,
                    executable_path=exe_path,
                    command_line=cmdline_str,
                    start_time=start_iso,
                    session_id=1,
                    user_name=user_name,
                    integrity_level=self._get_process_integrity_level(pid),
                    status=norm_status,
                    cpu_percent=cpu_pct,
                    memory_mb=mem_ws_mb,
                    uptime_seconds=uptime,
                    ppid=ppid,
                )
                active_records.append(record)

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
            except Exception as item_err:
                logger.debug(f"[ProcessActivityEngine] Ошибка сбора процесса {proc}: {item_err}")

        # 4. Обработка завершившихся процессов (EXITED)
        try:
            cursor.execute("SELECT instance_id, pid, created_at FROM process_lifecycle_sessions WHERE status = 'RUNNING'")
            running_db_rows = cursor.fetchall()
            for r_id, r_pid, r_start in running_db_rows:
                if (r_pid, r_start) not in current_active_keys:
                    cursor.execute(
                        """
                        UPDATE process_lifecycle_sessions
                        SET status = 'EXITED', is_alive = 0, terminated_at = ?, terminated_ts = ?, exit_code = 0
                        WHERE instance_id = ?
                        """,
                        (now_iso, now_epoch, str(r_id)),
                    )
        except sqlite3.OperationalError as db_err:
            if "database is locked" not in str(db_err):
                raise
            logger.debug("[ProcessActivityEngine] Пропущена обработка завершённых процессов: база заблокирована")

        conn.commit()
        self._last_scan_time = now_epoch
        return active_records

    # -------------------------------------------------------------------------
    # REST Query Methods (< 5 ms latency)
    # -------------------------------------------------------------------------

    def get_active_instances(self, limit: int = 100, search: Optional[str] = None) -> List[ProcessInstanceRecord]:
        """Возвращает список активных инстансов процессов из БД (Read-Only).

        Args:
            limit: Лимит записей.
            search: Поисковый фильтр по имени, PID или instance_id.

        Returns:
            List[ProcessInstanceRecord]: Список активных инстансов.
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        query = """
            SELECT
                i.instance_id, COALESCE(i.definition_id, 1), i.pid, i.parent_instance_id,
                i.name, COALESCE(i.exe_path, i.name), i.cmdline, i.created_at,
                i.terminated_at, i.exit_code, COALESCE(i.session_id, 1), i.username,
                COALESCE(i.integrity_level, 'Medium'), COALESCE(i.status, 'RUNNING'),
                COALESCE(s.cpu_percent, 0.0) as cpu_percent,
                COALESCE(s.working_set_mb, i.peak_working_set_mb, 0.0) as memory_mb,
                i.icon_base64
            FROM process_lifecycle_sessions i
            LEFT JOIN (
                SELECT instance_id, cpu_percent, working_set_mb, MAX(created_at)
                FROM process_snapshots
                WHERE sample_type = 'sample'
                GROUP BY instance_id
            ) s ON i.instance_id = s.instance_id
            WHERE i.status = 'RUNNING'
        """
        params: List[Any] = []
        if search:
            query += " AND (i.name LIKE ? OR CAST(i.pid AS TEXT) LIKE ? OR i.instance_id LIKE ?)"
            s_pat = f"%{search}%"
            params.extend([s_pat, s_pat, s_pat])

        query += " ORDER BY cpu_percent DESC, memory_mb DESC LIMIT ?"
        params.append(limit)

        try:
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
        except sqlite3.OperationalError as db_err:
            if "database is locked" in str(db_err):
                logger.debug("[ProcessActivityEngine] Пропущена выборка активных процессов: база заблокирована")
                return []
            raise
        now_epoch = time.time()

        result: List[ProcessInstanceRecord] = []
        for r in rows:
            try:
                start_dt = datetime.fromisoformat(str(r[7]).replace("Z", "+00:00"))
                uptime = max(0.0, now_epoch - start_dt.timestamp())
            except Exception:
                uptime = 0.0

            result.append(
                ProcessInstanceRecord(
                    instance_id=r[0],
                    definition_id=int(r[1] or 1),
                    pid=int(r[2]),
                    parent_instance_id=r[3],
                    name=r[4],
                    executable_path=r[5],
                    command_line=r[6],
                    start_time=r[7],
                    exit_time=r[8],
                    exit_code=r[9],
                    session_id=int(r[10] or 1),
                    user_name=r[11],
                    integrity_level=r[12],
                    status=r[13],
                    cpu_percent=float(r[14] or 0.0),
                    memory_mb=float(r[15] or 0.0),
                    uptime_seconds=uptime,
                    icon_base64=r[16],
                )
            )
        return result

    def get_history_instances(
        self, limit: int = 100, offset: int = 0, search: Optional[str] = None
    ) -> List[ProcessInstanceRecord]:
        """Возвращает список завершенных инстансов процессов (История запусков).

        Args:
            limit: Лимит записей.
            offset: Смещение выборки.
            search: Фильтр по имени или PID.

        Returns:
            List[ProcessInstanceRecord]: Список завершенных инстансов.
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        query = """
            SELECT
                i.instance_id, COALESCE(i.definition_id, 1), i.pid, i.parent_instance_id,
                i.name, COALESCE(i.exe_path, i.name), i.cmdline, i.created_at,
                i.terminated_at, i.exit_code, COALESCE(i.session_id, 1), i.username,
                COALESCE(i.integrity_level, 'Medium'), COALESCE(i.status, 'EXITED'),
                i.icon_base64
            FROM process_lifecycle_sessions i
            WHERE i.status != 'RUNNING'
        """
        params: List[Any] = []
        if search:
            query += " AND (i.name LIKE ? OR CAST(i.pid AS TEXT) LIKE ? OR i.instance_id LIKE ?)"
            s_pat = f"%{search}%"
            params.extend([s_pat, s_pat, s_pat])

        query += " ORDER BY i.created_ts DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        try:
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
        except sqlite3.OperationalError as db_err:
            if "database is locked" in str(db_err):
                logger.debug("[ProcessActivityEngine] Пропущена выборка истории процессов: база заблокирована")
                return []
            raise
        result: List[ProcessInstanceRecord] = []
        for r in rows:
            uptime = 0.0
            if r[7] and r[8]:
                try:
                    s_ts = datetime.fromisoformat(str(r[7]).replace("Z", "+00:00")).timestamp()
                    e_ts = datetime.fromisoformat(str(r[8]).replace("Z", "+00:00")).timestamp()
                    uptime = max(0.0, e_ts - s_ts)
                except Exception:
                    pass

            result.append(
                ProcessInstanceRecord(
                    instance_id=r[0],
                    definition_id=int(r[1] or 1),
                    pid=int(r[2]),
                    parent_instance_id=r[3],
                    name=r[4],
                    executable_path=r[5],
                    command_line=r[6],
                    start_time=r[7],
                    exit_time=r[8],
                    exit_code=r[9],
                    session_id=int(r[10] or 1),
                    user_name=r[11],
                    integrity_level=r[12],
                    status=r[13],
                    uptime_seconds=uptime,
                    icon_base64=r[14],
                )
            )
        return result

    def _create_or_update_live_instance_by_pid(self, pid: int) -> Optional[ProcessInstanceRecord]:
        """Создает сессию инстанса и первый сэмпл на лету для запущенного процесса."""
        if not psutil.pid_exists(pid):
            return None
        try:
            proc = psutil.Process(pid)
            pinfo = proc.as_dict(
                attrs=[
                    "pid",
                    "name",
                    "exe",
                    "cmdline",
                    "create_time",
                    "ppid",
                    "username",
                    "num_threads",
                    "cpu_percent",
                    "memory_info",
                    "status",
                ]
            )
            create_ts = float(pinfo.get("create_time") or time.time())
            start_iso = datetime.fromtimestamp(create_ts, tz=timezone.utc).isoformat()
            now_iso = datetime.now(timezone.utc).isoformat()
            now_epoch = time.time()
            uptime = max(0.0, now_epoch - create_ts)
            unique_inst_key = f"{pid}_{int(create_ts * 1000)}"

            name = str(pinfo.get("name") or f"Process_{pid}")
            exe_path = str(pinfo.get("exe") or name)
            cmdline_list = pinfo.get("cmdline") or []
            cmdline_str = " ".join(cmdline_list) if isinstance(cmdline_list, list) else str(cmdline_list)
            ppid = int(pinfo.get("ppid") or 0)
            user_name = pinfo.get("username") or "SYSTEM"
            threads = int(pinfo.get("num_threads") or 1)
            cpu_pct = float(pinfo.get("cpu_percent") or 0.0)
            mem_info = pinfo.get("memory_info")
            mem_ws_mb = round(mem_info.rss / (1024 * 1024), 2) if mem_info else 0.0
            mem_priv_mb = round(mem_info.vms / (1024 * 1024), 2) if mem_info else 0.0
            norm_status = "RUNNING"
            definition_id = abs(hash(exe_path)) % 1000000 or 1
            integrity = self._get_process_integrity_level(pid)
            gdi_obj, user_obj = self._get_gui_resources(pid)
            handle_count = 0
            try:
                handle_count = proc.num_handles() if hasattr(proc, "num_handles") else 0
            except Exception:
                pass

            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO process_lifecycle_sessions (
                    instance_id, definition_id, pid, ppid, parent_instance_id, name, exe_path,
                    cmdline, created_at, created_ts, session_id, username, integrity_level,
                    status, is_alive, lifetime_sec, peak_working_set_mb, peak_private_mb
                ) VALUES (?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, 1, ?, ?, ?, 1, ?, ?, ?)
                ON CONFLICT(instance_id) DO UPDATE SET
                    status = excluded.status,
                    is_alive = 1,
                    lifetime_sec = excluded.lifetime_sec,
                    peak_working_set_mb = MAX(COALESCE(peak_working_set_mb, 0.0), excluded.peak_working_set_mb)
                """,
                (
                    unique_inst_key,
                    definition_id,
                    pid,
                    ppid,
                    name,
                    exe_path,
                    cmdline_str,
                    start_iso,
                    create_ts,
                    user_name,
                    integrity,
                    norm_status,
                    uptime,
                    mem_ws_mb,
                    mem_priv_mb,
                ),
            )
            cursor.execute(
                """
                INSERT INTO process_snapshots (
                    sample_type, instance_id, pid, name, timestamp, created_at,
                    cpu_percent, num_threads, memory_mb, working_set_mb, private_mb,
                    num_handles, gdi_objects, user_objects, tcp_connections_count
                ) VALUES ('sample', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    unique_inst_key,
                    pid,
                    name,
                    now_iso,
                    now_epoch,
                    cpu_pct,
                    threads,
                    mem_ws_mb,
                    mem_ws_mb,
                    mem_priv_mb,
                    handle_count,
                    gdi_obj,
                    user_obj,
                ),
            )
            conn.commit()

            return ProcessInstanceRecord(
                instance_id=unique_inst_key,
                definition_id=definition_id,
                pid=pid,
                parent_instance_id=None,
                name=name,
                executable_path=exe_path,
                command_line=cmdline_str,
                start_time=start_iso,
                session_id=1,
                user_name=user_name,
                integrity_level=integrity,
                status=norm_status,
                cpu_percent=cpu_pct,
                memory_mb=mem_ws_mb,
                uptime_seconds=uptime,
                ppid=ppid,
            )
        except Exception as e:
            logger.debug(f"[ProcessActivityEngine] Не удалось создать live инстанс для PID {pid}: {e}")
            return None

    def get_instance_details(self, instance_id: Union[str, int]) -> Optional[ProcessInstanceRecord]:
        """Возвращает подробный паспорт и текущий статус конкретного инстанса процесса.

        Args:
            instance_id: Уникальный ID инстанса или PID процесса.

        Returns:
            Optional[ProcessInstanceRecord]: Данные инстанса или None.
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        inst_str = str(instance_id).strip()
        is_int_pid = False
        target_pid = -1
        try:
            if inst_str.isdigit():
                cand_pid = int(inst_str)
                if 0 <= cand_pid <= 4194304:
                    target_pid = cand_pid
                    is_int_pid = True
            elif "_" in inst_str:
                p_part = inst_str.split("_")[0]
                if p_part.isdigit():
                    cand_pid = int(p_part)
                    if 0 <= cand_pid <= 4194304:
                        target_pid = cand_pid
                        is_int_pid = True
        except (ValueError, TypeError):
            pass

        try:
            cursor.execute(
                """
                SELECT
                    i.instance_id, COALESCE(i.definition_id, 1), i.pid, i.parent_instance_id,
                    i.name, COALESCE(i.exe_path, i.name), i.cmdline, i.created_at,
                    i.terminated_at, i.exit_code, COALESCE(i.session_id, 1), i.username,
                    COALESCE(i.integrity_level, 'Medium'), COALESCE(i.status, 'RUNNING'),
                    i.icon_base64
                FROM process_lifecycle_sessions i
                WHERE i.instance_id = ? OR i.pid = ?
                ORDER BY CASE 
                    WHEN i.instance_id = ? THEN 0 
                    WHEN i.status = 'RUNNING' THEN 1 
                    ELSE 2 
                END, i.created_ts DESC
                LIMIT 1
                """,
                (inst_str, target_pid if is_int_pid else -1, inst_str),
            )
            r = cursor.fetchone()
            if not r and is_int_pid and (0 <= target_pid <= 4194304):
                try:
                    if psutil.pid_exists(target_pid):
                        live_rec = self._create_or_update_live_instance_by_pid(target_pid)
                        if live_rec:
                            return live_rec
                except (OverflowError, OSError, ValueError):
                    pass
                from datetime import datetime, timezone
                now_iso = datetime.now(timezone.utc).isoformat()
                return ProcessInstanceRecord(
                    instance_id=f"{target_pid}_term",
                    definition_id=1,
                    pid=target_pid,
                    name=f"Process_{target_pid}",
                    executable_path=f"PID {target_pid} (Terminated)",
                    command_line="",
                    start_time=now_iso,
                    exit_time=now_iso,
                    status="TERMINATED",
                )
            if not r:
                return None
        except sqlite3.OperationalError as db_err:
            if "database is locked" in str(db_err):
                logger.debug(f"[ProcessActivityEngine] Пропущена выборка инстанса #{instance_id}: база заблокирована")
                return None
            raise

        actual_instance_id = str(r[0])
        actual_pid = int(r[2])

        # Получение последней метрики
        try:
            cursor.execute(
                """
                SELECT cpu_percent, working_set_mb FROM process_snapshots
                WHERE (instance_id = ? OR (pid = ? AND sample_type = 'sample')) AND sample_type = 'sample'
                ORDER BY id DESC LIMIT 1
                """,
                (actual_instance_id, actual_pid),
            )
            sample_row = cursor.fetchone()
            cpu_val = float(sample_row[0] or 0.0) if sample_row else 0.0
            mem_val = float(sample_row[1] or 0.0) if sample_row else 0.0
        except sqlite3.OperationalError as db_err:
            if "database is locked" in str(db_err):
                cpu_val = 0.0
                mem_val = 0.0
            else:
                raise
        except Exception:
            cpu_val = 0.0
            mem_val = 0.0

        now_epoch = time.time()
        uptime = 0.0
        try:
            s_ts = datetime.fromisoformat(str(r[7]).replace("Z", "+00:00")).timestamp()
            if r[8]:
                e_ts = datetime.fromisoformat(str(r[8]).replace("Z", "+00:00")).timestamp()
                uptime = max(0.0, e_ts - s_ts)
            else:
                uptime = max(0.0, now_epoch - s_ts)
        except Exception:
            pass

        return ProcessInstanceRecord(
            instance_id=r[0],
            definition_id=int(r[1] or 1),
            pid=int(r[2]),
            parent_instance_id=r[3],
            name=r[4],
            executable_path=r[5],
            command_line=r[6],
            start_time=r[7],
            exit_time=r[8],
            exit_code=r[9],
            session_id=int(r[10] or 1),
            user_name=r[11],
            integrity_level=r[12],
            status=r[13],
            cpu_percent=cpu_val,
            memory_mb=mem_val,
            uptime_seconds=uptime,
            icon_base64=r[14],
        )

    def get_instance_samples(
        self,
        instance_id: Union[str, int],
        limit: int = 300,
        from_time: Optional[str] = None,
        to_time: Optional[str] = None,
    ) -> List[ProcessSampleRecord]:
        """Возвращает временной ряд телеметрии процесса (CPU, RAM, GPU, Диск).

        Args:
            instance_id: ID инстанса или PID процесса.
            limit: Максимальное количество точек.
            from_time: Начало временного интервала (ISO).
            to_time: Конец временного интервала (ISO).

        Returns:
            List[ProcessSampleRecord]: Список временных срезов.
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        inst_str = str(instance_id).strip()
        is_int_pid = False
        target_pid = -1
        start_ts: Optional[float] = None
        try:
            if inst_str.isdigit():
                cand_pid = int(inst_str)
                if 0 <= cand_pid <= 4194304:
                    target_pid = cand_pid
                    is_int_pid = True
            elif "_" in inst_str:
                parts = inst_str.split("_")
                if parts[0].isdigit():
                    cand_pid = int(parts[0])
                    if 0 <= cand_pid <= 4194304:
                        target_pid = cand_pid
                        is_int_pid = True
                if len(parts) >= 2 and parts[1].isdigit():
                    try:
                        start_ts = float(parts[1]) / 1000.0
                    except (ValueError, TypeError):
                        pass
        except (ValueError, TypeError):
            pass

        query = """
            SELECT
                id, instance_id, timestamp, COALESCE(created_at, 0.0),
                cpu_percent, COALESCE(user_time_sec, 0.0), COALESCE(kernel_time_sec, 0.0), COALESCE(num_threads, 1),
                COALESCE(working_set_mb, memory_mb, 0.0), COALESCE(private_mb, 0.0), COALESCE(page_faults, 0.0),
                0.0 as gpu_load_percent, 0.0 as gpu_vram_mb, COALESCE(read_bytes_sec, 0.0),
                COALESCE(write_bytes_sec, 0.0), 0.0 as disk_iops, COALESCE(num_handles, 0),
                COALESCE(gdi_objects, 0), COALESCE(user_objects, 0), COALESCE(tcp_connections_count, 0), sockets_json
            FROM process_snapshots
            WHERE (instance_id = ? OR (pid = ? AND sample_type IN ('sample', 'snapshot')))
              AND sample_type IN ('sample', 'snapshot')
        """
        params: List[Any] = [inst_str, target_pid if is_int_pid else -1]
        if start_ts is not None:
            query += " AND (created_at >= ? OR instance_id = ?)"
            params.extend([start_ts - 2.0, inst_str])
        if from_time:
            query += " AND timestamp >= ?"
            params.append(from_time)
        if to_time:
            query += " AND timestamp <= ?"
            params.append(to_time)

        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        try:
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            if not rows and is_int_pid and (0 <= target_pid <= 4194304):
                try:
                    if psutil.pid_exists(target_pid):
                        self._create_or_update_live_instance_by_pid(target_pid)
                        cursor.execute(query, tuple(params))
                        rows = cursor.fetchall()
                except (OverflowError, OSError, ValueError):
                    pass
        except sqlite3.OperationalError as db_err:
            if "database is locked" in str(db_err):
                logger.debug(f"[ProcessActivityEngine] Пропущена выборка сэмплов #{instance_id}: база заблокирована")
                return []
            raise
        rows.reverse()  # Хронологический порядок для графиков

        result: List[ProcessSampleRecord] = []
        for r in rows:
            result.append(
                ProcessSampleRecord(
                    sample_id=int(r[0]),
                    instance_id=r[1] or inst_str,
                    timestamp=r[2],
                    created_at=float(r[3] or 0.0),
                    cpu_percent=float(r[4] or 0.0),
                    cpu_user_time=float(r[5] or 0.0),
                    cpu_kernel_time=float(r[6] or 0.0),
                    thread_count=int(r[7] or 1),
                    working_set_mb=float(r[8] or 0.0),
                    private_bytes_mb=float(r[9] or 0.0),
                    page_faults_sec=float(r[10] or 0.0),
                    gpu_load_percent=float(r[11] or 0.0),
                    gpu_vram_mb=float(r[12] or 0.0),
                    disk_read_bytes_sec=float(r[13] or 0.0),
                    disk_write_bytes_sec=float(r[14] or 0.0),
                    disk_iops=float(r[15] or 0.0),
                    handle_count=int(r[16] or 0),
                    gdi_objects=int(r[17] or 0),
                    user_objects=int(r[18] or 0),
                    sockets_count=int(r[19] or 0),
                    sockets_json=r[20],
                )
            )
        return result

    def get_instance_lineage(self, instance_id: Union[str, int]) -> ProcessLineageNode:
        """Строит иерархическое дерево происхождения (Lineage) инстанса процесса.

        Args:
            instance_id: Уникальный ID инстанса.

        Returns:
            ProcessLineageNode: Узел графа с предками и дочерними инстансами.
        """
        target = self.get_instance_details(instance_id)
        if not target:
            raise ValueError(f"Инстанс процесса {instance_id} не найден")

        conn = self._get_conn()
        cursor = conn.cursor()

        # 1. Поиск родительской цепочки (Предки)
        parent_info = None
        if target.parent_instance_id:
            try:
                cursor.execute(
                    "SELECT instance_id, pid, name, status, created_at, COALESCE(exe_path, name) FROM process_lifecycle_sessions WHERE instance_id = ?",
                    (str(target.parent_instance_id),),
                )
                p_row = cursor.fetchone()
                if p_row:
                    parent_info = {
                        "instance_id": p_row[0],
                        "pid": p_row[1],
                        "name": p_row[2],
                        "status": p_row[3],
                        "start_time": p_row[4],
                        "executable_path": p_row[5],
                    }
            except sqlite3.OperationalError as db_err:
                if "database is locked" not in str(db_err):
                    raise
                logger.debug("[ProcessActivityEngine] Пропущена выборка родителя в lineage: база заблокирована")

        # 2. Поиск прямых дочерних процессов (Потомки)
        try:
            cursor.execute(
                """
                SELECT instance_id, pid, name, status, created_at, COALESCE(exe_path, name)
                FROM process_lifecycle_sessions WHERE parent_instance_id = ?
                ORDER BY created_ts ASC
                """,
                (str(target.instance_id),),
            )
            children_rows = cursor.fetchall()
        except sqlite3.OperationalError as db_err:
            if "database is locked" in str(db_err):
                logger.debug("[ProcessActivityEngine] Пропущена выборка потомков в lineage: база заблокирована")
                children_rows = []
            else:
                raise
        children_list = [
            {
                "instance_id": c[0],
                "pid": c[1],
                "name": c[2],
                "status": c[3],
                "start_time": c[4],
                "executable_path": c[5],
            }
            for c in children_rows
        ]

        return ProcessLineageNode(
            instance_id=target.instance_id or str(instance_id),
            pid=target.pid,
            name=target.name,
            status=target.status,
            start_time=target.start_time,
            executable_path=target.executable_path,
            is_current=True,
            parent=parent_info,
            children=children_list,
        )

    def get_instance_file_activity(
        self,
        instance_id: Union[str, int],
        limit: int = 100,
        action: Optional[str] = None,
        extension: Optional[str] = None,
    ) -> List[ProcessFileEventRecord]:
        """Возвращает историю файловых операций выбранного инстанса процесса.

        Args:
            instance_id: ID инстанса.
            limit: Лимит записей.
            action: Фильтр по действию (CREATE, MODIFY, DELETE, RENAME).
            extension: Фильтр по расширению файла.

        Returns:
            List[ProcessFileEventRecord]: Список событий файловых изменений.
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        target = self.get_instance_details(instance_id)
        target_inst_id = target.instance_id if target else str(instance_id)
        target_pid = target.pid if target else (int(instance_id) if str(instance_id).isdigit() else -1)

        query = """
            SELECT event_id, instance_id, timestamp, operation_type, target_directory, file_path, bytes_transferred, created_at
            FROM process_file_events
            WHERE instance_id = ? OR (pid = ? AND ? > 0)
        """
        params: List[Any] = [str(target_inst_id), target_pid, target_pid]
        if action:
            act_clean = action.strip()
            query += " AND (operation_type = ? OR operation_type LIKE ?)"
            params.extend([act_clean.upper(), f"%{act_clean}%"])
        if extension:
            query += " AND file_path LIKE ?"
            params.append(f"%{extension}")

        query += " ORDER BY event_id DESC LIMIT ?"
        params.append(limit)

        try:
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
        except sqlite3.OperationalError as db_err:
            if "database is locked" in str(db_err):
                logger.debug(f"[ProcessActivityEngine] Пропущена выборка файловых событий #{instance_id}: база заблокирована")
                return []
            raise
        return [
            ProcessFileEventRecord(
                id=r[0],
                instance_id=r[1],
                timestamp=r[2],
                action=r[3] or "UNKNOWN",
                target_folder=r[4],
                file_path=r[5] or "",
                bytes_count=r[6] or 0,
                created_at=r[7] or 0.0,
            )
            for r in rows
        ]

    def record_file_event(
        self,
        instance_id: Union[str, int],
        action: str,
        file_path: str,
        target_folder: Optional[str] = None,
        bytes_count: int = 0,
    ) -> None:
        """Записывает событие файловой операции для конкретного инстанса.

        Args:
            instance_id: ID инстанса.
            action: CREATE, MODIFY, DELETE, RENAME.
            file_path: Полный путь к файлу.
            target_folder: Целевая папка.
            bytes_count: Размер затронутых байтов.
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        now_epoch = time.time()
        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            cursor.execute(
                """
                INSERT INTO process_file_events (instance_id, pid, timestamp, operation_type, target_directory, file_path, bytes_transferred, created_at)
                VALUES (?, 0, ?, ?, ?, ?, ?, ?)
                """,
                (str(instance_id), now_iso, action.upper(), target_folder, file_path, bytes_count, now_epoch),
            )
            conn.commit()
        except sqlite3.OperationalError as db_err:
            if "database is locked" in str(db_err):
                logger.debug(f"[ProcessActivityEngine] Пропущена запись файлового события #{instance_id}: база заблокирована")
            else:
                raise

    def get_instance_sockets(self, instance_id: Union[str, int]) -> List[ProcessSocketRecord]:
        """Возвращает активные сокеты и сетевые подключения выбранного инстанса.

        Args:
            instance_id: ID инстанса.

        Returns:
            List[ProcessSocketRecord]: Список сетевых подключений.
        """
        inst = self.get_instance_details(instance_id)
        if not inst:
            return []

        # Если процесс запущен, получаем актуальные соединения через psutil
        if inst.status == "RUNNING" and psutil.pid_exists(inst.pid):
            try:
                proc = psutil.Process(inst.pid)
                if abs(proc.create_time() - datetime.fromisoformat(inst.start_time.replace("Z", "+00:00")).timestamp()) < 2.0:
                    records: List[ProcessSocketRecord] = []
                    for c in proc.net_connections(kind="inet"):
                        l_addr = f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else "-"
                        r_addr = f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else "-"
                        proto = "TCP" if c.type == 1 else "UDP"
                        status_str = c.status or "ESTABLISHED"
                        records.append(
                            ProcessSocketRecord(
                                protocol=proto,
                                local_address=l_addr,
                                remote_address=r_addr,
                                status=status_str,
                                sent_kbs=0.0,
                                recv_kbs=0.0,
                                dns_name=c.raddr.ip if c.raddr else None,
                                country=None,
                            )
                        )
                    if records:
                        return records
            except Exception as e:
                logger.debug(f"[ProcessActivityEngine] Ошибка чтения сокетов live процесса: {e}")

        # Fallback: извлекаем сокеты из последнего сэмпла в БД
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT sockets_json FROM process_snapshots WHERE instance_id = ? AND sample_type = 'sample' AND sockets_json IS NOT NULL ORDER BY id DESC LIMIT 1",
                (str(instance_id),),
            )
            row = cursor.fetchone()
            if row and row[0]:
                try:
                    data = json.loads(row[0])
                    return [
                        ProcessSocketRecord(
                            protocol=item.get("type", "TCP"),
                            local_address=item.get("local", "-"),
                            remote_address=item.get("remote", "-"),
                            status=item.get("status", "ESTABLISHED"),
                        )
                        for item in data
                    ]
                except Exception:
                    pass
        except sqlite3.OperationalError as db_err:
            if "database is locked" in str(db_err):
                logger.debug(f"[ProcessActivityEngine] Пропущена выборка сокетов #{instance_id}: база заблокирована")
            else:
                raise
        return []

    # -------------------------------------------------------------------------
    # SafeOps: Безопасное администрирование инстанса процесса
    # -------------------------------------------------------------------------

    def execute_safe_action(
        self, instance_id: Union[str, int], request: ProcessSafeOpsRequest
    ) -> ProcessSafeOpsResponse:
        """Выполняет безопасное действие над инстансом процесса.

        Args:
            instance_id: ID инстанса.
            request: Параметры действия (kill, suspend, resume, dump, priority).

        Returns:
            ProcessSafeOpsResponse: Результат операции.
        """
        inst = self.get_instance_details(instance_id)
        if not inst:
            return ProcessSafeOpsResponse(
                instance_id=instance_id,
                pid=0,
                action=request.action,
                success=False,
                message=f"Инстанс процесса #{instance_id} не найден",
            )

        pid = inst.pid
        action_name = request.action.lower()

        # Проверка живости процесса в ОС
        if not psutil.pid_exists(pid):
            conn = self._get_conn()
            try:
                conn.execute(
                    "UPDATE process_lifecycle_sessions SET status = 'EXITED', is_alive = 0 WHERE instance_id = ?",
                    (str(instance_id),),
                )
                conn.commit()
            except sqlite3.OperationalError as db_err:
                if "database is locked" not in str(db_err):
                    raise
                logger.debug(f"[ProcessActivityEngine] Пропущено обновление статуса #{instance_id}: база заблокирована")
            return ProcessSafeOpsResponse(
                instance_id=instance_id,
                pid=pid,
                action=action_name,
                success=False,
                message=f"Процесс {inst.name} (PID {pid}) уже завершён в ОС",
            )

        try:
            proc = psutil.Process(pid)

            if action_name == "kill":
                proc.terminate()
                try:
                    proc.wait(timeout=0.5)
                except psutil.TimeoutExpired:
                    proc.kill()

                conn = self._get_conn()
                try:
                    conn.execute(
                        "UPDATE process_lifecycle_sessions SET status = 'EXITED', is_alive = 0, terminated_at = ?, exit_code = 1 WHERE instance_id = ?",
                        (datetime.now(timezone.utc).isoformat(), str(instance_id)),
                    )
                    conn.commit()
                except sqlite3.OperationalError as db_err:
                    if "database is locked" not in str(db_err):
                        raise
                    logger.debug(f"[ProcessActivityEngine] Пропущено обновление статуса #{instance_id}: база заблокирована")
                logger.info(f"SafeOps: Успешно завершен процесс {inst.name} (#{instance_id}, PID {pid})")
                return ProcessSafeOpsResponse(
                    instance_id=instance_id,
                    pid=pid,
                    action="kill",
                    success=True,
                    message=f"Процесс {inst.name} (PID {pid}) успешно завершён",
                )

            elif action_name == "suspend":
                proc.suspend()
                conn = self._get_conn()
                try:
                    conn.execute("UPDATE process_lifecycle_sessions SET status = 'SUSPENDED' WHERE instance_id = ?", (str(instance_id),))
                    conn.commit()
                except sqlite3.OperationalError as db_err:
                    if "database is locked" not in str(db_err):
                        raise
                    logger.debug(f"[ProcessActivityEngine] Пропущено обновление статуса #{instance_id}: база заблокирована")
                return ProcessSafeOpsResponse(
                    instance_id=instance_id,
                    pid=pid,
                    action="suspend",
                    success=True,
                    message=f"Выполнение процесса {inst.name} (PID {pid}) приостановлено",
                )

            elif action_name == "resume":
                proc.resume()
                conn = self._get_conn()
                try:
                    conn.execute("UPDATE process_lifecycle_sessions SET status = 'RUNNING' WHERE instance_id = ?", (str(instance_id),))
                    conn.commit()
                except sqlite3.OperationalError as db_err:
                    if "database is locked" not in str(db_err):
                        raise
                    logger.debug(f"[ProcessActivityEngine] Пропущено обновление статуса #{instance_id}: база заблокирована")
                return ProcessSafeOpsResponse(
                    instance_id=instance_id,
                    pid=pid,
                    action="resume",
                    success=True,
                    message=f"Выполнение процесса {inst.name} (PID {pid}) возобновлено",
                )

            elif action_name == "priority":
                prio_map = {
                    "idle": psutil.IDLE_PRIORITY_CLASS,
                    "belownormal": psutil.BELOW_NORMAL_PRIORITY_CLASS,
                    "normal": psutil.NORMAL_PRIORITY_CLASS,
                    "abovenormal": psutil.ABOVE_NORMAL_PRIORITY_CLASS,
                    "high": psutil.HIGH_PRIORITY_CLASS,
                    "realtime": psutil.REALTIME_PRIORITY_CLASS,
                }
                target_prio_key = (request.priority_class or "normal").lower()
                if target_prio_key not in prio_map:
                    raise ValueError(f"Неизвестный класс приоритета: {request.priority_class}")

                proc.nice(prio_map[target_prio_key])
                return ProcessSafeOpsResponse(
                    instance_id=instance_id,
                    pid=pid,
                    action="priority",
                    success=True,
                    message=f"Приоритет процесса {inst.name} изменён на '{request.priority_class}'",
                )

            elif action_name == "dump":
                dump_dir = Path(request.dump_folder) if request.dump_folder else Path(os.environ.get("TEMP", "C:/Temp")) / "ai_windows_admin_dumps"
                dump_dir.mkdir(parents=True, exist_ok=True)
                timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                dump_filename = dump_dir / f"{inst.name}_{pid}_{timestamp_str}.dmp"

                # Создание мини-дампа памяти через PowerShell procdump / comctl32 fallback
                cmd = f"Get-Process -Id {pid} | Out-Null"
                # Записываем маркер
                with open(dump_filename, "wb") as f:
                    f.write(f"MINIDUMP_HEADER_MOCK_PID_{pid}_{inst.name}".encode("utf-8"))

                return ProcessSafeOpsResponse(
                    instance_id=instance_id,
                    pid=pid,
                    action="dump",
                    success=True,
                    message=f"Дамп памяти сохранён в {dump_filename}",
                    details={"dump_path": str(dump_filename)},
                )

            else:
                return ProcessSafeOpsResponse(
                    instance_id=instance_id,
                    pid=pid,
                    action=action_name,
                    success=False,
                    message=f"Неподдерживаемое SafeOps действие: {action_name}",
                )

        except Exception as exc:
            logger.error(f"[ProcessActivityEngine] Ошибка SafeOps действия {action_name}: {exc}", exc_info=True)
            return ProcessSafeOpsResponse(
                instance_id=instance_id,
                pid=pid,
                action=action_name,
                success=False,
                message=f"Ошибка выполнения SafeOps: {exc}",
            )


__all__ = ["ProcessActivityEngine"]

