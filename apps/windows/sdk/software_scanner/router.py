# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Software Scanner - FastAPI Router
# =============================================================================
# Description:
#   REST API маршруты для запуска глубокого сканирования установленного и спящего
#   ПО по требованию, получения отчетов, списка сирот и спящих программ из базы данных telemetry.db.
#
# File: router.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.software_scanner
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-20 20:20:00
# =============================================================================

from __future__ import annotations
"""FastAPI роутер подсистемы глубокого сканирования ПО и выборки данных из telemetry.db."""

import asyncio
import json
from typing import Any, Dict, Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from apps.windows.sdk.software_scanner.controller import DeepSoftwareScanner
from apps.windows.sdk.software_scanner.models import ScanMode, SoftwareStatus
from apps.windows.sdk.software_scanner.report import ReportFormatter
from apps.windows.telemetry.sqlite import TelemetryStorage

router = APIRouter(prefix="/software-scanner", tags=["software-scanner"])
scanner = DeepSoftwareScanner()


class ScanRequest(BaseModel):
    """Параметры запроса на сканирование ПО."""
    mode: ScanMode = Field(default=ScanMode.DEEP, description="Режим сканирования")
    target_name: Optional[str] = Field(default=None, description="Имя программы для целевого поиска")


@router.post("/scan")
async def trigger_scan(req: ScanRequest) -> Dict[str, Any]:
    """Запуск глубокого сканирования ПО по требованию с сохранением результатов в telemetry.db."""
    report = await asyncio.to_thread(scanner.run_scan, mode=req.mode, target_name=req.target_name)
    try:
        storage = TelemetryStorage.get_instance(read_only=False)
        storage.save_software_scanner_report(report)
    except Exception as db_err:
        from logger import logger
        logger.debug(f"Ошибка сохранения отчета сканера в telemetry.db: {db_err}")
    return ReportFormatter.to_dict(report)


@router.get("/latest-report")
async def get_latest_report() -> Dict[str, Any]:
    """Получение последнего отчета сканирования исключительно из базы данных telemetry.db."""
    try:
        storage = TelemetryStorage.get_instance(read_only=True)
        db_report = storage.get_latest_software_scanner_report()
        if db_report and isinstance(db_report, dict) and db_report.get("inventory"):
            return db_report
    except Exception as ex:
        from logger import logger
        logger.debug(f"Ошибка чтения отчета сканера из telemetry.db: {ex}")

    # Если отчета еще нет в telemetry.db, выполняем первичный прогрев и сохраняем его в telemetry.db
    report = await asyncio.to_thread(scanner.run_scan, mode=ScanMode.QUICK)
    try:
        storage_rw = TelemetryStorage.get_instance(read_only=False)
        storage_rw.save_software_scanner_report(report)
    except Exception:
        pass
    return ReportFormatter.to_dict(report)


@router.get("/dormant")
async def get_dormant_software(min_days: int = Query(90, ge=1)) -> Dict[str, Any]:
    """Получение списка давно не запускавшихся (спящих) программ из telemetry.db."""
    try:
        storage = TelemetryStorage.get_instance(read_only=True)
        dormant = storage.get_dormant_software_from_db(min_days=min_days)
        if dormant:
            return {
                "count": len(dormant),
                "min_days_threshold": min_days,
                "items": dormant,
            }
    except Exception:
        pass

    rep = await get_latest_report()
    inventory = rep.get("inventory") or []
    dormant = [
        card for card in inventory
        if card.get("status") in ("dormant", "never_launched")
        or (card.get("days_since_last_run") is not None and card.get("days_since_last_run") >= min_days)
    ]
    return {
        "count": len(dormant),
        "min_days_threshold": min_days,
        "items": dormant,
    }


@router.get("/orphans")
async def get_orphan_software() -> Dict[str, Any]:
    """Получение списка обнаруженных сирот, битых служб и остатков ПО из telemetry.db."""
    try:
        storage = TelemetryStorage.get_instance(read_only=True)
        orphans = storage.get_orphan_software_from_db()
        if orphans:
            return {
                "orphan_count": len(orphans),
                "items": orphans,
            }
    except Exception:
        pass

    rep = await get_latest_report()
    orphans = rep.get("orphan_items") or []
    return {
        "orphan_count": len(orphans),
        "items": orphans,
    }


def init_router() -> APIRouter:
    """Инициализация и получение роутера глубокого сканирования ПО."""
    return router


__all__ = ["router", "init_router"]

