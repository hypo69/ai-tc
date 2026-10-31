# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Software Scanner - Controller
# =============================================================================
# Description:
#   Главный контроллер и оркестратор глубокого сканирования ПО: запуск зондов,
#   сбор доказательств, выявление сирот, корреляция и формирование отчетов.
#
# File: controller.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.software_scanner
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 19:20:00
# =============================================================================

from __future__ import annotations
"""Контроллер оркестрации глубокого сканирования программного обеспечения."""

from datetime import datetime, timezone
import time
import uuid
from typing import List, Optional
from logger import logger
from apps.windows.sdk.software_scanner.correlator import EvidenceCorrelator
from apps.windows.sdk.software_scanner.models import (
    EvidenceItem,
    ScanErrorItem,
    ScanMode,
    ScanReport,
    ScanStats,
    SoftwareStatus,
)
from apps.windows.sdk.software_scanner.orphan_detector import OrphanDetector
from apps.windows.sdk.software_scanner.policies import ScannerPolicy
from apps.windows.sdk.software_scanner.probes import (
    ExecutionEvidenceProbe,
    FilesystemProbe,
    PackagesProbe,
    RegistryProbe,
    ServicesProbe,
    TasksProbe,
)


class DeepSoftwareScanner:
    """Главный координатор глубокого сканирования программного обеспечения Windows."""

    def __init__(self, policy: ScannerPolicy | None = None) -> None:
        self.policy = policy or ScannerPolicy()
        self.registry_probe = RegistryProbe()
        self.fs_probe = FilesystemProbe(self.policy)
        self.services_probe = ServicesProbe()
        self.tasks_probe = TasksProbe()
        self.packages_probe = PackagesProbe()
        self.execution_probe = ExecutionEvidenceProbe()
        self.orphan_detector = OrphanDetector()
        self.correlator = EvidenceCorrelator(self.policy)

    def run_scan(
        self,
        mode: ScanMode = ScanMode.DEEP,
        target_name: Optional[str] = None,
        custom_roots: Optional[List[str]] = None,
    ) -> ScanReport:
        """Запуск сессии сканирования в указанном режиме.

        Args:
            mode: Режим сканирования (quick, deep, forensic, targeted, orphans).
            target_name: Имя целевой программы для режима targeted.
            custom_roots: Пользовательские директории для обхода.

        Returns:
            ScanReport: Сводный отчет сканирования.
        """
        scan_id = str(uuid.uuid4())[:8]
        start_time = time.perf_counter()
        started_at = datetime.now(timezone.utc).isoformat()

        logger.info(f"[DeepSoftwareScanner] Старт сканирования id={scan_id}, mode={mode.value}")

        evidence_items: List[EvidenceItem] = []
        errors: List[ScanErrorItem] = []

        # 1. Быстрый сбор регистраций из реестра (всегда выполняется)
        evidence_items.extend(self.registry_probe.scan_all())

        # 2. Сбор служб и задач
        if mode in (ScanMode.QUICK, ScanMode.DEEP, ScanMode.FORENSIC, ScanMode.ORPHANS):
            evidence_items.extend(self.services_probe.scan_services())
            evidence_items.extend(self.tasks_probe.scan_tasks())

        # 3. Сбор пакетов современных пакетных менеджеров
        if mode in (ScanMode.QUICK, ScanMode.DEEP, ScanMode.FORENSIC):
            evidence_items.extend(self.packages_probe.scan_all())

        # 4. Обход файловой системы
        if mode in (ScanMode.DEEP, ScanMode.FORENSIC, ScanMode.TARGETED):
            fs_items, fs_errors = self.fs_probe.scan(custom_roots=custom_roots)
            evidence_items.extend(fs_items)
            errors.extend(fs_errors)

        # 5. Доказательства запусков (UserAssist, Prefetch, Recent)
        if mode in (ScanMode.DEEP, ScanMode.FORENSIC, ScanMode.TARGETED):
            evidence_items.extend(self.execution_probe.scan_all())

        # 6. Фильтрация по цели для targeted-режима
        if mode == ScanMode.TARGETED and target_name:
            t_lower = target_name.lower()
            evidence_items = [
                it for it in evidence_items
                if (it.product_name and t_lower in it.product_name.lower())
                or (it.path and t_lower in it.path.lower())
            ]

        # 7. Детекция сирот и остатков
        orphan_items, _ = self.orphan_detector.find_orphans(evidence_items)

        # 8. Корреляция свидетельств в карточки ПО
        inventory = self.correlator.correlate(evidence_items, orphan_items)

        # 9. Подсчет статистики
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        completed_at = datetime.now(timezone.utc).isoformat()

        evidence_by_type: dict[str, int] = {}
        for it in evidence_items:
            t_name = it.evidence_type.value
            evidence_by_type[t_name] = evidence_by_type.get(t_name, 0) + 1

        stats = ScanStats(
            total_evidence_found=len(evidence_items),
            total_software_identified=len(inventory),
            active_count=sum(1 for c in inventory if c.status == SoftwareStatus.ACTIVE),
            dormant_count=sum(1 for c in inventory if c.status in (SoftwareStatus.DORMANT, SoftwareStatus.NEVER_LAUNCHED)),
            orphan_count=len(orphan_items),
            errors_count=len(errors),
            duration_ms=duration_ms,
            evidence_by_type=evidence_by_type,
        )

        logger.info(
            f"[DeepSoftwareScanner] Сканирование {scan_id} завершено за {duration_ms:.1f} мс: "
            f"найдено {len(inventory)} программ ({stats.dormant_count} спящих, {stats.orphan_count} сирот)"
        )

        return ScanReport(
            scan_id=scan_id,
            mode=mode,
            started_at=started_at,
            completed_at=completed_at,
            stats=stats,
            inventory=inventory,
            orphan_items=orphan_items,
            unknown_artifacts=[],
            errors=errors,
        )


__all__ = ["DeepSoftwareScanner"]

