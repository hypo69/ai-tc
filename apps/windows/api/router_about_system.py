# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Api - Router About System
# =============================================================================
# Description:
#   Реализует эндпоинт, возвращающий агрегированный набор данных о системе.
#
# File: router_about_system.py
# Project: ai-windows-admin
# Package: apps.windows.api
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-13 23:50:00
# =============================================================================

"""Router, предоставляющий "bundle" о системе.

Эндпоинт: ``GET /api/v1/about-system/bundle``

Возвращает словарь, содержащий сведения о системе, полученные из
`TelemetryStorage`. Данные включают:

- ``summary`` – сводка о состоянии системы;
- ``hardware`` – дерево аппаратных компонентов;
- ``kpi`` – ключевые показатели производительности;
- ``storage_battery`` – информация о батарейных и хранилищных ресурсах;
- ``backup`` – статус резервного копирования;
- ``control_status`` – состояние управления (например, службы).

Все сообщения выводятся в консоль через ``logger.console``.
"""

from __future__ import annotations

from fastapi import APIRouter
from logger import logger
from apps.windows.telemetry.sqlite.storage import TelemetryStorage

router = APIRouter(prefix="/api/v1/about-system", tags=["About System"])


@router.get("/bundle")
async def get_about_system_bundle() -> dict:
    """Возвращает агрегированный набор данных о системе.

    Данные извлекаются из ``TelemetryStorage`` в режиме только‑для‑чтения.
    При ошибке возвращается пустой словарь и сообщение в лог.
    """
    try:
        storage = TelemetryStorage.get_instance(read_only=True)
        reader = storage.reader
        # Сводка
        summary = reader.get_summary()
        # Дерево аппаратных компонентов
        hardware = reader.get_hardware_tree()
        # KPI
        kpi = reader.get_kpi()
        # Информация о батарее и хранилище
        storage_battery = reader.get_storage_battery()
        # Резервные копии
        backup = reader.get_backup()
        # Состояние управления
        control_status = reader.get_control_status()
        result = {
            "summary": summary,
            "hardware": hardware,
            "kpi": kpi,
            "storage_battery": storage_battery,
            "backup": backup,
            "control_status": control_status,
        }
        logger.console("Сформирован bundle о системе")
        return result
    except Exception as exc:  # pragma: no cover
        logger.error(f"Ошибка при формировании about‑system bundle: {exc}")
        return {}


def init_router() -> APIRouter:
    """Возвращает инициализированный роутер.
    """
    return router

__all__ = ["router", "init_router"]

