# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - Router Processes Load Inspector
# =============================================================================
# Description:
#   FastAPI REST эндпоинты для веб-вкладки «Инспектор нагрузки процессов»
#   (tab-processes-load-inspector). Объединяет и координирует маршруты панелей:
#   - Топ процессов хоста (panel-top-processes)
#   - Диспетчер процессов и приложений (panel-process-manager)
#   - Сетевая активность и мониторинг файлов (panel-network-activity, panel-file-watcher)
#   - Аудит утечек ресурсов и дескрипторов (panel-leak-hunter)
#   - Углубленный анализ инстанса (panel-deep-dive)
#   - ИИ-расследование источников нагрузки (panel-ai-audit)
#
# Usage Examples:
#   Python API:
#     from apps.windows.api.routers.router_processes_load_inspector import init_router
#
#     app.include_router(init_router())
#
# File: router_processes_load_inspector.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-18 08:25:00
# =============================================================================

from __future__ import annotations
"""FastAPI REST эндпоинты для вкладки инспектора нагрузки процессов хоста."""

import asyncio
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

try:
    from logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

from apps.windows.telemetry.sqlite import TelemetryStorage
from apps.windows.sdk.core.process_activity_engine import ProcessActivityEngine
from apps.windows.sdk.modules.process_manager.core.classifier import ProcessClassifier
from apps.windows.sdk.modules.process_manager.core.manager import ProcessManager
from apps.windows.sdk.modules.process_manager.core.models import (
    CategorizedProcessReport,
    ProcessItem,
    ProcessKillRequest,
    ProcessReport,
)
from apps.windows.sdk.modules.process_manager.router import _perform_powershell_investigation
from apps.windows.api.routers.about_system.query_diagnostics import query_process_leaks_from_db
from apps.windows.telemetry.models import (
    ProcessFileEventRecord,
    ProcessInstanceRecord,
    ProcessLineageNode,
    ProcessSafeOpsRequest,
    ProcessSafeOpsResponse,
    ProcessSampleRecord,
    ProcessSocketRecord,
)

_manager = ProcessManager()


def init_router(prefix: str = "/api/v1/tab-processes-load-inspector", **kwargs: Any) -> APIRouter:
    """Инициализирует и возвращает FastAPI APIRouter для вкладки инспектора нагрузки процессов.

    Args:
        prefix: Базовый префикс маршрутов вкладки.

    Returns:
        APIRouter: Сконфигурированный роутер FastAPI.
    """
    router = APIRouter(prefix=prefix, tags=["Processes Load Inspector"])

    # =========================================================================
    # 1. Панель: Топ процессов хоста (panel-top-processes)
    # =========================================================================
    @router.get("/panel-top-processes", response_model=List[Dict[str, Any]])
    @router.get("/panel-top-stream", response_model=List[Dict[str, Any]], include_in_schema=False)
    async def get_panel_top_processes(
        limit: int = Query(30, ge=1, le=500, description="Количество процессов в выборке"),
        sort_by: str = Query("cpu", description="Поле сортировки: cpu, memory, handles, name, pid"),
    ) -> List[Dict[str, Any]]:
        """Возвращает список наиболее ресурсоемких процессов хоста из SQLite телеметрии."""
        try:
            storage = TelemetryStorage.get_instance(read_only=True)
            return await asyncio.to_thread(storage.get_latest_processes, limit=limit, sort_by=sort_by)
        except Exception as exc:
            logger.error(f"[ProcessesLoadInspector] Ошибка получения top-processes: {exc}", exc_info=True)
            return []

    # =========================================================================
    # 2. Панель: Диспетчер процессов и приложений (panel-process-manager)
    # =========================================================================
    @router.get("/panel-process-manager", response_model=CategorizedProcessReport)
    @router.get("/panel-process-manager/categorized", response_model=CategorizedProcessReport, include_in_schema=False)
    async def get_panel_process_manager_categorized() -> CategorizedProcessReport:
        """Детальный отчет о процессах, разделенный на Apps, Background и Windows."""
        try:
            return await asyncio.to_thread(_manager.generate_categorized_report)
        except Exception as exc:
            logger.error(f"[ProcessesLoadInspector] Ошибка генерации categorized отчета: {exc}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(exc))

    @router.get("/panel-process-manager/summary", response_model=ProcessReport)
    @router.get("/panel-process-manager/report", response_model=ProcessReport, include_in_schema=False)
    async def get_panel_process_manager_summary() -> ProcessReport:
        """Сводный отчет о процессах хоста с агрегатами и структурой категорий."""
        try:
            return await asyncio.to_thread(_manager.generate_report)
        except Exception as exc:
            logger.error(f"[ProcessesLoadInspector] Ошибка генерации summary отчета: {exc}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(exc))

    @router.get("/panel-process-manager/list", response_model=List[ProcessItem])
    async def list_panel_process_manager_processes(
        name: Optional[str] = Query(None, description="Фильтр по имени процесса"),
        sort_by: str = Query("cpu_percent", description="Поле сортировки: cpu_percent, memory_mb, name, pid"),
        limit: int = Query(0, description="Лимит возвращаемых процессов (0 = все)"),
    ) -> List[ProcessItem]:
        """Список всех активных процессов из SQLite (< 5 мс) или через psutil fallback."""
        try:
            storage = TelemetryStorage.get_instance(read_only=True)
            raw_list = storage.get_latest_processes(limit=limit, sort_by=sort_by)
            if raw_list:
                items: List[ProcessItem] = []
                for p in raw_list:
                    mem_b = p.get("memory_rss_bytes") or 0
                    mem_mb = round(mem_b / (1024 * 1024), 2) if mem_b else float(p.get("memory_mb") or 0.0)
                    cmd_ = p.get("cmdline") or p.get("command_line")
                    p_name_ = str(p.get("name") or "unknown")
                    items.append(
                        ProcessItem(
                            pid=int(p.get("pid", 0)),
                            ppid=int(p["ppid"]) if p.get("ppid") else None,
                            name=p_name_,
                            username=p.get("username"),
                            cpu_percent=float(p.get("cpu_percent") or 0.0),
                            memory_mb=mem_mb,
                            num_threads=int(p.get("num_threads") or 1),
                            create_time=str(p.get("created_at") or p.get("creation_time") or p.get("timestamp") or ""),
                            exe_path=p.get("exe_path") or p.get("executable"),
                            command_line=cmd_,
                            launch_summary=ProcessClassifier._extract_launch_summary(p_name_, cmd_),
                            parent_name=p.get("parent_name"),
                            real_parent=p.get("parent_name"),
                        )
                    )
                if name:
                    n_lower = name.lower()
                    items = [p for p in items if n_lower in p.name.lower()]
                return items
        except Exception as ex:
            logger.debug(f"[ProcessesLoadInspector] Ошибка извлечения процессов из SQLite: {ex}")

        processes = await asyncio.to_thread(_manager.list_processes)
        if name:
            n_lower = name.lower()
            processes = [p for p in processes if n_lower in p.name.lower()]
        return processes

    @router.post("/panel-process-manager/action")
    @router.post("/panel-process-manager/kill")
    async def kill_panel_process(payload: ProcessKillRequest) -> Dict[str, Any]:
        """Завершение процесса по PID с точечной валидацией."""
        return await _manager.kill_process(payload)

    # =========================================================================
    # 3. Панель: Сеть и мониторинг файлов (panel-network-activity, panel-file-watcher)
    # =========================================================================
    @router.get("/panel-network-activity", response_model=List[Dict[str, Any]])
    @router.get("/panel-network-files/network-activity", response_model=List[Dict[str, Any]], include_in_schema=False)
    async def get_panel_network_activity(
        limit: int = Query(100, ge=1, le=1000, description="Максимальное число соединений"),
        only_internet: bool = Query(False, description="Фильтровать только внешние соединения"),
    ) -> List[Dict[str, Any]]:
        """Возвращает список активных сетевых соединений программ и процессов из SQLite."""
        try:
            storage = TelemetryStorage.get_instance(read_only=True)
            db_activity = storage.get_latest_process_network_activity(limit=limit, only_internet=only_internet)
            return db_activity if db_activity else []
        except Exception as exc:
            logger.debug(f"[ProcessesLoadInspector] Ошибка чтения сетевой активности: {exc}")
            return []

    @router.get("/panel-file-watcher/events", response_model=List[Dict[str, Any]])
    @router.get("/panel-network-files/file-watcher/events", response_model=List[Dict[str, Any]], include_in_schema=False)
    async def get_panel_file_watcher_events(
        limit: int = Query(50, ge=1, le=500, description="Лимит последних файловых событий"),
        pid: Optional[int] = Query(None, description="Фильтр по PID процесса"),
    ) -> List[Dict[str, Any]]:
        """Возвращает последние события файловой активности для живого мониторинга."""
        try:
            storage = TelemetryStorage.get_instance(read_only=True)
            raw_events = await asyncio.to_thread(storage.get_process_file_events, pid=pid, limit=limit)
            normalized: List[Dict[str, Any]] = []
            for ev in raw_events:
                action_name = ev.get("action_type") or ev.get("action") or "MODIFY"
                path_str = ev.get("file_path") or ev.get("target_directory") or ""
                normalized.append({
                    "event_id": ev.get("event_id"),
                    "pid": ev.get("pid", 0),
                    "process_name": ev.get("process_name", "System"),
                    "action": action_name,
                    "action_type": action_name,
                    "path": path_str,
                    "file_path": path_str,
                    "target_directory": ev.get("target_directory", ""),
                    "timestamp": ev.get("timestamp"),
                    "created_at": ev.get("created_at"),
                    "bytes_affected": ev.get("bytes_affected", 0),
                    "instance_id": ev.get("instance_id"),
                })
            return normalized
        except Exception as exc:
            logger.error(f"[ProcessesLoadInspector] Ошибка получения file-watcher events: {exc}", exc_info=True)
            return []

    # =========================================================================
    # 4. Панель: Аудит утечек ресурсов (panel-leak-hunter)
    # =========================================================================
    @router.get("/panel-leak-hunter", response_model=Dict[str, Any])
    @router.get("/panel-process-leaks", response_model=Dict[str, Any], include_in_schema=False)
    @router.get("/panel-leaks", response_model=Dict[str, Any], include_in_schema=False)
    async def get_panel_leak_hunter(
        limit: int = Query(100, ge=1, le=500, description="Лимит процессов"),
    ) -> Dict[str, Any]:
        """Получение сводки и списка утечек ресурсов процессов из SQLite телеметрии."""
        try:
            storage = TelemetryStorage.get_instance(read_only=True)
            return query_process_leaks_from_db(storage, limit=limit)
        except Exception as exc:
            logger.error(f"[ProcessesLoadInspector] Ошибка получения утечек ресурсов: {exc}", exc_info=True)
            return {}

    @router.post("/panel-leak-hunter/refresh", response_model=Dict[str, Any])
    @router.post("/panel-process-leaks/refresh", response_model=Dict[str, Any], include_in_schema=False)
    async def refresh_panel_leak_hunter(
        limit: int = Query(100, ge=1, le=500, description="Лимит процессов"),
    ) -> Dict[str, Any]:
        """Актуализация и срез утечек ресурсов процессов."""
        try:
            storage = TelemetryStorage.get_instance(read_only=True)
            return query_process_leaks_from_db(storage, limit=limit)
        except Exception as exc:
            logger.error(f"[ProcessesLoadInspector] Ошибка обновления утечек ресурсов: {exc}", exc_info=True)
            return {}

    # =========================================================================
    # 5. Панель: Deep Dive (panel-deep-dive)
    # =========================================================================
    @router.get("/panel-deep-dive/active", response_model=List[ProcessInstanceRecord])
    async def get_panel_deep_dive_active(
        limit: int = Query(100, ge=1, le=500, description="Лимит возвращаемых процессов"),
        search: Optional[str] = Query(None, description="Поисковый запрос по имени, PID или instance_id"),
    ) -> List[ProcessInstanceRecord]:
        """Получение списка всех активных процессов текущей сессии."""
        try:
            eng = ProcessActivityEngine.get_instance()
            return await asyncio.to_thread(eng.get_active_instances, limit=limit, search=search)
        except Exception as exc:
            logger.error(f"[ProcessesLoadInspector] Ошибка получения активных инстансов: {exc}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(exc))

    @router.get("/panel-deep-dive/history", response_model=List[ProcessInstanceRecord])
    async def get_panel_deep_dive_history(
        limit: int = Query(50, ge=1, le=500, description="Лимит записей"),
        offset: int = Query(0, ge=0, description="Смещение выборки"),
        search: Optional[str] = Query(None, description="Поисковый запрос по имени или PID"),
    ) -> List[ProcessInstanceRecord]:
        """Получение списка завершенных инстансов процессов (исторические срезы)."""
        try:
            eng = ProcessActivityEngine.get_instance()
            return await asyncio.to_thread(eng.get_history_instances, limit=limit, offset=offset, search=search)
        except Exception as exc:
            logger.error(f"[ProcessesLoadInspector] Ошибка получения истории инстансов: {exc}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(exc))

    @router.get("/panel-deep-dive/{instance_id}", response_model=ProcessInstanceRecord)
    async def get_panel_deep_dive_instance_details(instance_id: str) -> ProcessInstanceRecord:
        """Получение подробного паспорта и текущего статуса конкретного инстанса."""
        try:
            eng = ProcessActivityEngine.get_instance()
            record = await asyncio.to_thread(eng.get_instance_details, instance_id=instance_id)
            if not record:
                raise HTTPException(status_code=404, detail=f"Инстанс процесса #{instance_id} не найден")
            return record
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(f"[ProcessesLoadInspector] Ошибка получения инстанса #{instance_id}: {exc}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(exc))

    @router.get("/panel-deep-dive/{instance_id}/samples", response_model=List[ProcessSampleRecord])
    async def get_panel_deep_dive_samples(
        instance_id: str,
        limit: int = Query(300, ge=1, le=2000, description="Лимит точек данных"),
        from_time: Optional[str] = Query(None, description="Начало временного интервала (ISO-8601)"),
        to_time: Optional[str] = Query(None, description="Конец временного интервала (ISO-8601)"),
    ) -> List[ProcessSampleRecord]:
        """Получение временного ряда метрик (CPU, RAM, GPU, IO) за интервал."""
        try:
            eng = ProcessActivityEngine.get_instance()
            return await asyncio.to_thread(
                eng.get_instance_samples,
                instance_id=instance_id,
                limit=limit,
                from_time=from_time,
                to_time=to_time,
            )
        except Exception as exc:
            logger.error(f"[ProcessesLoadInspector] Ошибка получения сэмплов #{instance_id}: {exc}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(exc))

    @router.get("/panel-deep-dive/{instance_id}/lineage", response_model=ProcessLineageNode)
    async def get_panel_deep_dive_lineage(instance_id: str) -> ProcessLineageNode:
        """Получение интерактивного дерева предков и потомков инстанса процесса."""
        try:
            eng = ProcessActivityEngine.get_instance()
            return await asyncio.to_thread(eng.get_instance_lineage, instance_id=instance_id)
        except ValueError as val_err:
            raise HTTPException(status_code=404, detail=str(val_err))
        except Exception as exc:
            logger.error(f"[ProcessesLoadInspector] Ошибка получения lineage #{instance_id}: {exc}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(exc))

    @router.get("/panel-deep-dive/{instance_id}/file-activity", response_model=List[ProcessFileEventRecord])
    async def get_panel_deep_dive_file_activity(
        instance_id: str,
        limit: int = Query(100, ge=1, le=1000, description="Лимит событий"),
        action: Optional[str] = Query(None, description="Фильтр по типу: CREATE, MODIFY, DELETE, RENAME"),
        extension: Optional[str] = Query(None, description="Фильтр по расширению файла"),
    ) -> List[ProcessFileEventRecord]:
        """Получение файловых событий по instance_id."""
        try:
            eng = ProcessActivityEngine.get_instance()
            return await asyncio.to_thread(
                eng.get_instance_file_activity,
                instance_id=instance_id,
                limit=limit,
                action=action,
                extension=extension,
            )
        except Exception as exc:
            logger.error(f"[ProcessesLoadInspector] Ошибка получения файловых событий #{instance_id}: {exc}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(exc))

    @router.get("/panel-deep-dive/{instance_id}/sockets", response_model=List[ProcessSocketRecord])
    async def get_panel_deep_dive_sockets(instance_id: str) -> List[ProcessSocketRecord]:
        """Получение активных сетевых сокетов и удаленных соединений процесса."""
        try:
            eng = ProcessActivityEngine.get_instance()
            return await asyncio.to_thread(eng.get_instance_sockets, instance_id=instance_id)
        except Exception as exc:
            logger.error(f"[ProcessesLoadInspector] Ошибка получения сокетов #{instance_id}: {exc}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(exc))

    @router.post("/panel-deep-dive/{instance_id}/action", response_model=ProcessSafeOpsResponse)
    async def execute_panel_deep_dive_safeops_action(
        instance_id: str, payload: ProcessSafeOpsRequest
    ) -> ProcessSafeOpsResponse:
        """Выполнение SafeOps действий над процессом (kill, suspend, resume, dump, priority)."""
        try:
            eng = ProcessActivityEngine.get_instance()
            return await asyncio.to_thread(eng.execute_safe_action, instance_id=instance_id, request=payload)
        except Exception as exc:
            logger.error(f"[ProcessesLoadInspector] Ошибка SafeOps действия #{instance_id}: {exc}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(exc))

    @router.post("/panel-deep-dive/{instance_id}/priority")
    async def set_panel_deep_dive_priority(instance_id: str, payload: Dict[str, Any]) -> ProcessSafeOpsResponse:
        """Изменение приоритета выполнения процесса."""
        req = ProcessSafeOpsRequest(
            action="priority",
            priority=payload.get("priority", "NORMAL"),
            confirmed_by_user=True,
        )
        eng = ProcessActivityEngine.get_instance()
        return await asyncio.to_thread(eng.execute_safe_action, instance_id=instance_id, request=req)

    @router.post("/panel-deep-dive/{instance_id}/suspend")
    async def suspend_panel_deep_dive_instance(instance_id: str) -> ProcessSafeOpsResponse:
        """Приостановка выполнения процесса."""
        req = ProcessSafeOpsRequest(action="suspend", confirmed_by_user=True)
        eng = ProcessActivityEngine.get_instance()
        return await asyncio.to_thread(eng.execute_safe_action, instance_id=instance_id, request=req)

    @router.post("/panel-deep-dive/{instance_id}/resume")
    async def resume_panel_deep_dive_instance(instance_id: str) -> ProcessSafeOpsResponse:
        """Возобновление выполнения процесса."""
        req = ProcessSafeOpsRequest(action="resume", confirmed_by_user=True)
        eng = ProcessActivityEngine.get_instance()
        return await asyncio.to_thread(eng.execute_safe_action, instance_id=instance_id, request=req)

    @router.post("/panel-deep-dive/{instance_id}/dump")
    async def dump_panel_deep_dive_instance(instance_id: str) -> ProcessSafeOpsResponse:
        """Создание дампа памяти процесса."""
        req = ProcessSafeOpsRequest(action="dump", confirmed_by_user=True)
        eng = ProcessActivityEngine.get_instance()
        return await asyncio.to_thread(eng.execute_safe_action, instance_id=instance_id, request=req)

    # =========================================================================
    # 6. Панель: ИИ-Аудит и расследование (panel-ai-audit)
    # =========================================================================
    @router.get("/panel-ai-audit/powershell", response_model=Dict[str, Any])
    @router.get("/panel-ai-audit/investigate/powershell", response_model=Dict[str, Any], include_in_schema=False)
    async def get_panel_ai_audit_powershell() -> Dict[str, Any]:
        """Автоматическое расследование скрытых и повторяющихся запусков PowerShell."""
        return await asyncio.to_thread(_perform_powershell_investigation)

    return router


__all__ = ["init_router"]

