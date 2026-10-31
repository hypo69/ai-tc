# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Cloudflared Monitor FastAPI Router
# =============================================================================
# Description:
#   FastAPI REST эндпоинты для мониторинга туннеля Cloudflare (kino.davidka.net),
#   телеметрии, хвоста логов, проверки доступности эндпоинта, диагностики
#   и управления жизненным циклом демона.
#
# Examples:
#   >>> from fastapi import FastAPI
#   >>> from apps.cloudflared_monitor.router import init_router
#   >>> app = FastAPI()
#   >>> app.include_router(init_router())
#
# File: router.py
# Project: ai-windows-admin
# Package: apps.cloudflared_monitor
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-30 14:00:00
# =============================================================================

"""FastAPI роутер для мониторинга и управления Cloudflare Tunnel."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, Request

from apps.windows.api.auth import require_admin_user
from apps.common.csv_logger import AppCsvLogger
from .src.state import CloudflaredState

router = APIRouter(prefix="/api/cloudflared", tags=["cloudflared"])
_state: Optional[CloudflaredState] = None
_csv_logger = AppCsvLogger("cloudflared_monitor")


def get_state() -> CloudflaredState:
    """Возвращает или создает singleton экземпляр CloudflaredState.

    Returns:
        CloudflaredState: Активный экземпляр состояния.
    """
    global _state
    if _state is None:
        _state = CloudflaredState()
    return _state


@router.get("/status")
async def get_status(request: Request) -> Dict[str, Any]:
    """Возвращает статус и телеметрию туннеля Cloudflare.

    Returns:
        Dict[str, Any]: Состояние процесса, токена и доступности публичного URL.
    """
    state = get_state()
    state.refresh(probe_network=False)

    res = {
        "is_running": state.process.is_running,
        "pid": state.process.pid,
        "uptime_seconds": state.process.uptime_seconds,
        "cpu_percent": state.process.cpu_percent,
        "memory_mb": state.process.memory_mb,
        "memory_percent": state.process.memory_percent,
        "num_threads": state.process.num_threads,
        "has_token": state.has_token,
        "token_preview": state.token_preview,
        "exe_path": state.exe_path,
        "public_url": state.public_url,
        "endpoint_reachable": state.endpoint.is_reachable,
        "endpoint_status_code": state.endpoint.status_code,
        "endpoint_latency_ms": state.endpoint.response_time_ms,
        "active_connections": state.active_connections_count,
        "total_errors": state.total_errors_in_log,
        "total_warnings": state.total_warnings_in_log,
        "health_score": state.report.health_score if state.report else 0,
        "health_status": state.report.status if state.report else "UNKNOWN",
        "last_refreshed": state.last_refreshed,
    }
    _csv_logger.log_poll(
        poll_type="tunnel_status",
        metric_name="is_running",
        value=state.process.is_running,
        unit="bool",
        status="OK" if state.process.is_running else "STOPPED",
        details={"pid": state.process.pid, "cpu": state.process.cpu_percent, "mem_mb": state.process.memory_mb},
        filename="cloudflared_status_polls.csv",
    )
    return res


@router.get("/logs")
async def get_logs(
    request: Request,
    limit: int = Query(default=50, ge=1, le=500),
    level: Optional[str] = None,
    search: Optional[str] = None,
) -> Dict[str, Any]:
    """Возвращает последние распарсенные записи из журнала cloudflared.log.

    Args:
        request: Входящий FastAPI запрос.
        limit: Лимит записей.
        level: Фильтр по уровню (ERROR, WARN, INFO).
        search: Текстовый поиск.

    Returns:
        Dict[str, Any]: Отфильтрованные записи журнала.
    """
    state = get_state()
    entries = state.tail_logs(limit=limit)

    if level:
        lvl_upper = level.upper()
        entries = [e for e in entries if e.level == lvl_upper]

    if search:
        s_lower = search.lower()
        entries = [e for e in entries if s_lower in e.message.lower() or s_lower in e.raw.lower()]

    return {
        "count": len(entries),
        "total_errors": state.total_errors_in_log,
        "total_warnings": state.total_warnings_in_log,
        "logs": [
            {
                "timestamp": e.timestamp,
                "level": e.level,
                "message": e.message,
                "connection_id": e.connection_id,
                "raw": e.raw,
            }
            for e in entries
        ],
    }


@router.get("/metrics")
async def get_metrics(request: Request) -> Dict[str, Any]:
    """Возвращает детальную телеметрию процесса и сети.

    Returns:
        Dict[str, Any]: Численные показатели для графиков.
    """
    state = get_state()
    state.refresh(probe_network=False)

    return {
        "process": {
            "is_running": state.process.is_running,
            "pid": state.process.pid,
            "cpu_percent": state.process.cpu_percent,
            "memory_mb": state.process.memory_mb,
            "memory_percent": state.process.memory_percent,
            "threads": state.process.num_threads,
            "uptime_seconds": state.process.uptime_seconds,
        },
        "network": {
            "public_url": state.public_url,
            "is_reachable": state.endpoint.is_reachable,
            "status_code": state.endpoint.status_code,
            "latency_ms": state.endpoint.response_time_ms,
            "last_checked": state.endpoint.last_checked,
        },
        "log_stats": {
            "errors": state.total_errors_in_log,
            "warnings": state.total_warnings_in_log,
            "active_connectors": state.active_connections_count,
        },
    }


@router.get("/diagnostic")
async def get_diagnostic(request: Request) -> Dict[str, Any]:
    """Возвращает эвристическую и ИИ диагностику состояния туннеля.

    Returns:
        Dict[str, Any]: Оценка здоровья, аномалии и рекомендации.
    """
    state = get_state()
    state.refresh(probe_network=False)
    report = state.evaluate_diagnostics()

    _csv_logger.log_event(
        event_type="diagnostics_evaluated",
        status=report.status,
        details={"health_score": report.health_score, "anomalies_count": len(report.anomalies)},
        filename="cloudflared_diagnostic_events.csv",
    )

    return {
        "health_score": report.health_score,
        "status": report.status,
        "summary": report.summary,
        "anomalies": [
            {
                "title": a.title,
                "description": a.description,
                "severity": a.severity,
            }
            for a in report.anomalies
        ],
        "recommendations": report.recommendations,
        "evaluated_at": report.evaluated_at,
    }


@router.post("/test-endpoint")
async def test_endpoint(request: Request) -> Dict[str, Any]:
    """Выполняет немедленный HTTP-опрос публичного URL туннеля.

    Returns:
        Dict[str, Any]: Результат проверки доступности и задержки.
    """
    state = get_state()
    health = state.probe_endpoint()

    _csv_logger.log_poll(
        poll_type="endpoint_probe",
        metric_name="reachability",
        value=health.is_reachable,
        unit="bool",
        status="REACHABLE" if health.is_reachable else "UNREACHABLE",
        details={"status_code": health.status_code, "latency_ms": health.response_time_ms, "url": health.url},
        filename="cloudflared_endpoint_probes.csv",
    )

    return {
        "url": health.url,
        "is_reachable": health.is_reachable,
        "status_code": health.status_code,
        "response_time_ms": health.response_time_ms,
        "error_message": health.error_message,
        "last_checked": health.last_checked,
    }


@router.post("/start")
async def start_tunnel(request: Request) -> Dict[str, Any]:
    """Запускает процесс cloudflared (требуются права администратора)."""
    require_admin_user(request)
    state = get_state()
    success, msg = state.start_tunnel()
    _csv_logger.log_event(
        event_type="start_tunnel",
        status="SUCCESS" if success else "FAILED",
        details=msg,
        filename="cloudflared_service_events.csv",
    )
    if not success:
        raise HTTPException(status_code=500, detail=msg)
    return {"success": True, "message": msg}


@router.post("/stop")
async def stop_tunnel(request: Request) -> Dict[str, Any]:
    """Останавливает процесс cloudflared (требуются права администратора)."""
    require_admin_user(request)
    state = get_state()
    success, msg = state.stop_tunnel()
    _csv_logger.log_event(
        event_type="stop_tunnel",
        status="SUCCESS" if success else "FAILED",
        details=msg,
        filename="cloudflared_service_events.csv",
    )
    return {"success": True, "message": msg}


@router.post("/restart")
async def restart_tunnel(request: Request) -> Dict[str, Any]:
    """Перезапускает процесс cloudflared (требуются права администратора)."""
    require_admin_user(request)
    state = get_state()
    success, msg = state.restart_tunnel()
    _csv_logger.log_event(
        event_type="restart_tunnel",
        status="SUCCESS" if success else "FAILED",
        details=msg,
        filename="cloudflared_service_events.csv",
    )
    if not success:
        raise HTTPException(status_code=500, detail=msg)
    return {"success": True, "message": msg}


def init_router() -> APIRouter:
    """Инициализирует и возвращает настроенный экземпляр APIRouter для Cloudflared.

    Returns:
        APIRouter: Экземпляр роутера.
    """
    return router


__all__ = [
    "init_router",
    "router",
    "get_state",
]
