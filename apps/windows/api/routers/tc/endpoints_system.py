# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api Routers - endpoints_system
# =============================================================================
# Description:
#   Эндпойнты состояния системы TC.
#   Вынесено из router_tc.py (этап 4 оптимизации).
#
# File: endpoints_system.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers.tc
# Author: hypo69
# Copyright: c 2026 hypo69
# Updated: 2026-10-12 06:20:00
# =============================================================================

from __future__ import annotations

import os
from typing import Any, Dict

from fastapi import APIRouter, Request

from apps.windows.api.auth import require_admin_user
from .models import TcCpuResponse
from .state import get_collector
from .state import get_diagnostician
from .state import get_storage


def register_system_endpoints(router: APIRouter) -> None:
    """Регистрирует эндпойнты состояния системы на роутере."""
    # =========================================================================
    # 4. Телеметрия и системная инспекция: /api/v1/tc/*
    # =========================================================================

    @router.get("/status")
    async def get_status(request: Request) -> Dict[str, Any]:
        """Получение текущего состояния системы и загрузки ресурсов из базы данных telemetry.db."""
        storage = get_storage()
        snaps = storage.get_snapshots(limit=1)
        if snaps:
            snap = snaps[0]
            raw_cpu = snap.get("cpu_percent") or 0.0
            raw_freq = snap.get("cpu_freq_mhz") or 0.0
            raw_mem_pct = snap.get("memory_percent") or 0.0
            raw_mem_used = snap.get("memory_used_gb") or 0.0
            raw_mem_total = snap.get("memory_total_gb") or 0.0
            procs = storage.get_snapshot_processes(snap.get("id") or 0)
            return {
                "hostname": snap.get("hostname") or os.getenv("COMPUTERNAME", "PC"),
                "os_name": snap.get("os_name") or "Windows",
                "uptime_seconds": snap.get("uptime_seconds") or 0.0,
                "cpu": {
                    "total_percent": raw_cpu,
                    "frequency_mhz": raw_freq,
                },
                "memory": {
                    "percent_used": raw_mem_pct,
                    "used_gb": raw_mem_used,
                    "total_gb": raw_mem_total,
                },
                "process_count": len(procs) if procs else int(snap.get("process_count") or 0),
            }

        collector = get_collector()
        snapshot = await collector.get_snapshot(process_limit=15)
        return {
            "hostname": snapshot.hostname,
            "os_name": snapshot.os_name,
            "uptime_seconds": snapshot.uptime_seconds,
            "cpu": snapshot.cpu.model_dump(),
            "memory": snapshot.memory.model_dump(),
            "process_count": len(snapshot.top_processes),
        }

    @router.get("/processes")
    async def get_processes(request: Request, limit: int = 20, sort_by: str = "cpu") -> Dict[str, Any]:
        """Получение списка активных процессов из базы данных SQLite (telemetry.db)."""
        storage = get_storage()
        procs = storage.get_latest_processes(limit=limit, sort_by=sort_by)
        if procs:
            return {"processes": procs, "sort_by": sort_by}

        collector = get_collector()
        snapshot = await collector.get_snapshot(process_limit=limit)
        processes = []
        for p in snapshot.top_processes:
            processes.append({
                "pid": p.pid,
                "name": p.name,
                "status": p.status,
                "cpu_percent": p.cpu_percent,
                "memory_mb": p.memory_mb,
                "memory_percent": p.memory_percent,
                "num_threads": p.num_threads,
                "username": p.username,
            })
        return {"processes": processes, "sort_by": sort_by}

    @router.get("/hardware")
    async def get_hardware(request: Request) -> Dict[str, Any]:
        """Получение данных спецификации оборудования и активных датчиков."""
        storage = get_storage()
        collector = get_collector()
        sensors = storage.get_latest_sensors()
        sensors_list = [{"name": s.get("name") or s.get("sensor_id"), "value": s.get("value"), "unit": s.get("unit")} for s in sensors]

        hardware = []
        try:
            nodes = await collector.get_hardware_tree_async()
            for n in nodes:
                hardware.append({
                    "category": n.category if hasattr(n, "category") else n.get("category", "Device"),
                    "name": n.name if hasattr(n, "name") else n.get("name", "Hardware"),
                    "properties": n.properties if hasattr(n, "properties") else n.get("properties", {}),
                })
        except Exception:
            latest_audit = storage.get_latest_hardware_audit() or storage.get_latest_extended_audit() or {}
            audit_data = latest_audit.get("data") if isinstance(latest_audit.get("data"), dict) else latest_audit
            devices = audit_data.get("devices") or latest_audit.get("devices") or []
            for d in devices:
                hardware.append({"category": d.get("device_class") or "Device", "name": d.get("name") or "Hardware", "properties": d})

        return {"hardware": hardware, "sensors": sensors_list}

    @router.get("/diagnostic")
    async def get_diagnostic(request: Request, process_limit: int = 20) -> Dict[str, Any]:
        """Получение AI отчета эвристической диагностики системы."""
        collector = get_collector()
        diagnostician = get_diagnostician()
        snapshot = await collector.get_snapshot(process_limit=process_limit)
        score, anomalies, recommendations = diagnostician.evaluate_heuristics(snapshot)
        return {
            "health_score": score,
            "summary": f"System Health: {score}/100. Telemetry stream nominal.",
            "ai_model_used": "Heuristic Monitor",
            "anomalies": [{"title": a.title, "description": a.description, "severity": a.severity} for a in anomalies],
            "recommendations": recommendations,
        }

    @router.get("/hardware/tree")
    async def get_hardware_tree(request: Request) -> Dict[str, Any]:
        """Получение иерархического дерева оборудования в стиле AIDA64."""
        storage = get_storage()
        collector = get_collector()
        tree = []
        try:
            nodes = await collector.get_hardware_tree_async()
            for n in nodes:
                tree.append({
                    "category": n.category if hasattr(n, "category") else n.get("category", "Device"),
                    "name": n.name if hasattr(n, "name") else n.get("name", "Hardware"),
                    "properties": n.properties if hasattr(n, "properties") else n.get("properties", {}),
                })
        except Exception:
            latest_audit = storage.get_latest_hardware_audit() or storage.get_latest_extended_audit() or {}
            audit_data = latest_audit.get("data") if isinstance(latest_audit.get("data"), dict) else latest_audit
            devices = audit_data.get("devices") or latest_audit.get("devices") or []
            for d in devices:
                tree.append({"category": d.get("device_class") or "Device", "name": d.get("name") or "Hardware", "properties": d})
        return {"tree": tree}

    @router.get("/hardware/sensors")
    async def get_hardware_sensors(request: Request) -> Dict[str, Any]:
        """Получение показаний системных датчиков из базы данных SQLite (telemetry.db)."""
        storage = get_storage()
        sensors = storage.get_latest_sensors()
        return {"sensors": [{"name": s.get("name") or s.get("sensor_id"), "value": s.get("value"), "unit": s.get("unit")} for s in sensors]}

    @router.get("/cpu", response_model=TcCpuResponse)
    @router.get("/cpu/load", response_model=TcCpuResponse)
    async def get_tc_cpu(request: Request) -> TcCpuResponse:
        """Получение текущей загрузки CPU из базы данных SQLite (telemetry.db)."""
        collector = get_collector()
        latest_cpu = collector.get_latest_cpu_from_db()

        phys_cores = os.cpu_count() or 6
        log_cores = os.cpu_count() or 12
        try:
            import psutil
            phys_cores = psutil.cpu_count(logical=False) or phys_cores
            log_cores = psutil.cpu_count(logical=True) or log_cores
        except Exception:
            pass

        cpu_model = "CPU"
        if os.name == "nt":
            try:
                import winreg

                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
                    val, _ = winreg.QueryValueEx(key, "ProcessorNameString")
                    if val and val.strip():
                        cpu_model = val.strip()
            except Exception:
                pass
        if not cpu_model or cpu_model == "CPU":
            try:
                import platform
                cpu_model = platform.processor() or f"{phys_cores}-Core Processor"
            except Exception:
                pass

        if latest_cpu and latest_cpu.get("cpu_total_percent") is not None:
            pct = float(latest_cpu["cpu_total_percent"])
            freq = float(latest_cpu.get("cpu_frequency_mhz") or 0.0)
            ts = str(latest_cpu.get("timestamp") or "")
            src = "telemetry.db"
        else:
            # Fallback: прямой запрос через collector
            cpu_m = await collector.get_cpu_metrics()
            pct = float(cpu_m.total_percent or 0.0)
            freq = float(cpu_m.frequency_mhz or 0.0)
            cpu_model = cpu_m.model or cpu_model
            ts = ""
            src = "live_collector"

        freq_txt = f"{int(freq)} MHz" if freq > 0 else ""
        return TcCpuResponse(
            total_percent=round(pct, 1),
            frequency_mhz=round(freq, 0),
            physical_cores=phys_cores,
            logical_cores=log_cores,
            model=cpu_model,
            display_val=f"{pct:.1f}%",
            display_cores=f"{phys_cores} Физических / {log_cores} Потоков",
            display_freq=freq_txt,
            timestamp=ts,
            source=src,
        )

    @router.get("/cpu/history")
    async def get_tc_cpu_history(request: Request, limit: int = 60) -> Dict[str, Any]:
        """Получение истории загрузки CPU из базы данных SQLite (telemetry.db)."""
        collector = get_collector()
        history = collector.get_cpu_history_from_db(limit=limit)
        return {
            "status": "ok",
            "count": len(history),
            "history": history,
            "source": "telemetry.db",
        }

    @router.post("/trigger-diagnostic")
    async def trigger_diagnostic(request: Request, process_limit: int = 20) -> Dict[str, Any]:
        """Ручной запуск разовой AI диагностики (требуются права администратора)."""
        require_admin_user(request)
        collector = get_collector()
        diagnostician = get_diagnostician()
        snapshot = await collector.get_snapshot(process_limit=process_limit)
        score, anomalies, recommendations = diagnostician.evaluate_heuristics(snapshot)
        return {
            "success": True,
            "health_score": score,
            "anomalies_count": len(anomalies),
            "recommendations_count": len(recommendations),
        }

