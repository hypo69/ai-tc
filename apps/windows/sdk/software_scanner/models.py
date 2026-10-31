# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Software Scanner - Models
# =============================================================================
# Description:
#   Модели данных для глубокого сканера следов программного обеспечения.
#   Включает модели свидетельств (Evidence), карточек ПО (SoftwareInventoryCard),
#   режимов сканирования, метрик и итогового отчета.
#
# File: models.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.software_scanner
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 19:20:00
# =============================================================================

from __future__ import annotations
"""Модели данных подсистемы глубокого сканирования ПО."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ScanMode(str, Enum):
    """Режимы сканирования программного обеспечения."""
    QUICK = "quick"          # Быстрый опрос реестра, служб, задач и пакетов
    DEEP = "deep"            # Рекурсивный обход каталогов, PE-метаданные
    FORENSIC = "forensic"    # Глубокий обход + артефакты UserAssist, Prefetch, Recent
    TARGETED = "targeted"    # Целевой поиск следов конкретного приложения
    ORPHANS = "orphans"      # Поиск сирот, битых служб и остатков


class EvidenceType(str, Enum):
    """Типы обнаруженных следов программ."""
    EXECUTABLE = "executable"
    REGISTRY = "registry"
    SERVICE = "service"
    TASK = "task"
    PACKAGE = "package"
    PREFETCH = "prefetch"
    USERASSIST = "userassist"
    SHORTCUT = "shortcut"
    DIRECTORY = "directory"
    UNKNOWN = "unknown"


class SoftwareStatus(str, Enum):
    """Статус активности и целостности программы."""
    ACTIVE = "active"                  # Активно запускается (< 60 дней)
    DORMANT = "dormant"                # Давно не запускалась (> 90 дней или без запусков)
    NEVER_LAUNCHED = "never_launched"  # Установлена, но запусков не обнаружено
    ORPHAN = "orphan"                  # Остаток / битая ссылка / отсутствующий EXE
    PORTABLE = "portable"              # Портативное приложение без инсталлятора
    STORE_APP = "store_app"            # Пакет Microsoft Store / MSIX


class ConfidenceLevel(str, Enum):
    """Степень достоверности обнаруженного следа."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class EvidenceItem:
    """Атомарное свидетельство присутствия программы в системе."""
    evidence_type: EvidenceType
    source: str
    path: str
    product_name: Optional[str] = None
    publisher: Optional[str] = None
    version: Optional[str] = None
    sha256: Optional[str] = None
    first_seen: Optional[str] = None
    last_observed: Optional[str] = None
    last_execution: Optional[str] = None
    run_count: int = 0
    focus_seconds: int = 0
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    access_status: str = "readable"
    raw_details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SoftwareInventoryCard:
    """Агрегированная карточка обнаруженной программы."""
    id: str
    name: str
    publisher: Optional[str] = None
    version: Optional[str] = None
    install_location: Optional[str] = None
    main_executable: Optional[str] = None
    uninstall_string: Optional[str] = None
    status: SoftwareStatus = SoftwareStatus.DORMANT
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH
    last_execution: Optional[str] = None
    run_count: int = 0
    focus_seconds: int = 0
    days_since_last_run: Optional[int] = None
    is_orphan: bool = False
    orphan_reasons: List[str] = field(default_factory=list)
    evidence: List[EvidenceItem] = field(default_factory=list)
    components: List[str] = field(default_factory=list)


@dataclass
class ScanErrorItem:
    """Информация об ошибке или пропущенном пути при сканировании."""
    path: str
    error_type: str
    message: str


@dataclass
class ScanStats:
    """Статистика выполнения сессии сканирования."""
    total_evidence_found: int = 0
    total_software_identified: int = 0
    active_count: int = 0
    dormant_count: int = 0
    orphan_count: int = 0
    errors_count: int = 0
    duration_ms: float = 0.0
    evidence_by_type: Dict[str, int] = field(default_factory=dict)


@dataclass
class ScanReport:
    """Полный сводный отчет сессии сканирования."""
    scan_id: str
    mode: ScanMode
    started_at: str
    completed_at: str
    stats: ScanStats
    inventory: List[SoftwareInventoryCard] = field(default_factory=list)
    orphan_items: List[EvidenceItem] = field(default_factory=list)
    unknown_artifacts: List[EvidenceItem] = field(default_factory=list)
    errors: List[ScanErrorItem] = field(default_factory=list)


__all__ = [
    "ScanMode",
    "EvidenceType",
    "SoftwareStatus",
    "ConfidenceLevel",
    "EvidenceItem",
    "SoftwareInventoryCard",
    "ScanErrorItem",
    "ScanStats",
    "ScanReport",
]

