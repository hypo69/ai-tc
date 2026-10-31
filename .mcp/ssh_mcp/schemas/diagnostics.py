# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Схемы диагностической телеметрии для RAG и ai-tc
# =============================================================================
# Description:
#   Определение структурированных диагностических пакетов оборудования, ОС,
#   дисковой подсистемы, сети и служб для сохранения в SQLite и передачи в RAG.
#
#   Зачем нужен этот модуль:
#     1. Унификация диагностического слепка Windows и Linux узлов.
#     2. Подготовка самодостаточных отчётов для корреляции с исторической
#        телеметрией ai-tc.
#
# Usage Examples:
#   Python API:
#     from ssh_mcp.schemas.diagnostics import DiagnosticPackage
#     pkg = DiagnosticPackage(report_id="diag-01", host_id="win-01", platform="windows")
#
# File: diagnostics.py
# Project: AI Windows Admin (ai-tc)
# Package: ssh_mcp.schemas
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-31 16:37:30
# =============================================================================

from datetime import datetime, timezone
from typing import Any, Dict, List
from pydantic import BaseModel, Field


class DiagnosticPackage(BaseModel):
    """Комплексный диагностический пакет узла для сохранения в БД и RAG.

    Attributes:
        report_id (str): Уникальный идентификатор диагностического отчёта.
        host_id (str): Идентификатор обследованного узла.
        platform (str): Платформа узла ('windows' или 'linux').
        collected_at (str): Время сбора телеметрии в формате UTC ISO-8601.
        os_info (Dict[str, Any]): Сведения о версии ядра, сборке ОС и аптайме.
        hardware (Dict[str, Any]): Метрики загрузки CPU, ядер и оперативной памяти.
        storage (List[Dict[str, Any]]): Состояние файловых систем и накопителей.
        network (Dict[str, Any]): Интерфейсы, маршруты и открытые сокеты.
        services (List[Dict[str, Any]]): Сводка критических и остановленных служб.
        recent_errors (List[Dict[str, Any]]): Последние ошибки из системных журналов.
        health_score (int): Расчётный индекс здоровья узла (0–100).

    Examples:
        >>> pkg = DiagnosticPackage(report_id="rep-1", host_id="srv-01", platform="linux")
        >>> pkg.health_score
        100
    """

    report_id: str
    host_id: str
    platform: str
    collected_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    os_info: Dict[str, Any] = Field(default_factory=dict)
    hardware: Dict[str, Any] = Field(default_factory=dict)
    storage: List[Dict[str, Any]] = Field(default_factory=list)
    network: Dict[str, Any] = Field(default_factory=dict)
    services: List[Dict[str, Any]] = Field(default_factory=list)
    recent_errors: List[Dict[str, Any]] = Field(default_factory=list)
    health_score: int = Field(default=100, ge=0, le=100)
