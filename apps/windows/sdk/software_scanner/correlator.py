# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Software Scanner - Correlator
# =============================================================================
# Description:
#   Движок корреляции и классификации следов ПО: сведение разрозненных
#   свидетельств в единые карточки программ и расчет степени активности.
#
# File: correlator.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.software_scanner
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 19:20:00
# =============================================================================

from __future__ import annotations
"""Движок корреляции и классификации собранных следов программного обеспечения."""

from datetime import datetime, timezone
import hashlib
import os
import re
from typing import Dict, List, Tuple
from logger import logger
from apps.windows.sdk.software_scanner.models import (
    ConfidenceLevel,
    EvidenceItem,
    EvidenceType,
    SoftwareInventoryCard,
    SoftwareStatus,
)
from apps.windows.sdk.software_scanner.policies import ScannerPolicy


class EvidenceCorrelator:
    """Коррелятор и классификатор найденных артефактов ПО."""

    def __init__(self, policy: ScannerPolicy | None = None) -> None:
        self.policy = policy or ScannerPolicy()

    def correlate(
        self,
        evidence_list: List[EvidenceItem],
        orphan_items: List[EvidenceItem] | None = None,
    ) -> List[SoftwareInventoryCard]:
        """Объединение доказательств в итоговые карточки программного обеспечения."""
        orphan_set = {f"{it.source}:{it.path}" for it in (orphan_items or [])}
        groups: Dict[str, List[EvidenceItem]] = {}

        # 1. Группировка следов по нормализованному ключу программы
        for item in evidence_list:
            key = self._generate_group_key(item)
            if key not in groups:
                groups[key] = []
            groups[key].append(item)

        cards: List[SoftwareInventoryCard] = []

        # 2. Построение карточек для каждой группы
        for key, items in groups.items():
            card = self._build_card(key, items, orphan_set)
            if card:
                cards.append(card)

        # Сортировка: сначала спящие и сироты, затем по названию
        cards.sort(key=lambda c: (0 if c.status == SoftwareStatus.DORMANT else (1 if c.is_orphan else 2), c.name.lower()))
        return cards

    def _generate_group_key(self, item: EvidenceItem) -> str:
        """Генерация нормализованного ключа для объединения свидетельств."""
        raw_name = item.product_name or ""
        # Удаляем версии и мусорные суффиксы для агрегации
        clean_name = re.sub(r"\b(v?\d+(\.\d+)+|\(x86\)|\(x64\)|64-bit|32-bit)\b", "", raw_name, flags=re.IGNORECASE)
        clean_name = re.sub(r"[\W_]+", " ", clean_name).strip().lower()

        if clean_name and len(clean_name) >= 3:
            return clean_name

        # Fallback: группировка по родительскому каталогу
        if item.path and os.path.isabs(item.path):
            parent = os.path.dirname(item.path).lower()
            return f"dir_{hashlib.md5(parent.encode('utf-8')).hexdigest()[:8]}"

        return f"item_{hashlib.md5(item.path.encode('utf-8')).hexdigest()[:8]}"

    def _build_card(
        self,
        key: str,
        items: List[EvidenceItem],
        orphan_set: set,
    ) -> SoftwareInventoryCard | None:
        """Формирование карточки программы из списка сгруппированных свидетельств."""
        name = None
        publisher = None
        version = None
        install_location = None
        main_executable = None
        uninstall_string = None
        is_orphan = False
        orphan_reasons: List[str] = []
        components: List[str] = []

        latest_exec_dt: datetime | None = None
        total_run_count = 0
        total_focus_seconds = 0

        for item in items:
            # Определение основных атрибутов
            if not name and item.product_name:
                name = item.product_name
            if not publisher and item.publisher:
                publisher = item.publisher
            if not version and item.version:
                version = item.version
            if not install_location and item.evidence_type in (EvidenceType.REGISTRY, EvidenceType.PACKAGE, EvidenceType.DIRECTORY):
                install_location = item.path

            if item.evidence_type == EvidenceType.EXECUTABLE and not main_executable:
                main_executable = item.path

            if item.evidence_type == EvidenceType.REGISTRY and "uninstallstring" in item.raw_details:
                uninstall_string = item.raw_details["uninstallstring"]

            if f"{item.source}:{item.path}" in orphan_set:
                is_orphan = True
                orphan_reasons.append(f"След {item.source} признан осиротевшим")

            # Суммирование метрик выполнения
            total_run_count += item.run_count
            total_focus_seconds += item.focus_seconds

            if item.last_execution:
                try:
                    dt = datetime.fromisoformat(item.last_execution.replace("Z", "+00:00"))
                    if latest_exec_dt is None or dt > latest_exec_dt:
                        latest_exec_dt = dt
                except ValueError:
                    pass

            if item.path and item.path not in components:
                components.append(item.path)

        if not name:
            name = key.replace("dir_", "Папка: ").replace("item_", "Объект: ")

        # Расчет дней с последнего запуска и определение статуса
        days_since_run = None
        status = SoftwareStatus.NEVER_LAUNCHED

        if latest_exec_dt:
            now = datetime.now(timezone.utc)
            days_since_run = max(0, (now - latest_exec_dt).days)
            if days_since_run <= self.policy.active_threshold_days:
                status = SoftwareStatus.ACTIVE
            elif days_since_run >= self.policy.dormant_threshold_days:
                status = SoftwareStatus.DORMANT
            else:
                status = SoftwareStatus.ACTIVE
        elif is_orphan:
            status = SoftwareStatus.ORPHAN
        elif any(it.evidence_type == EvidenceType.PACKAGE for it in items):
            status = SoftwareStatus.STORE_APP
        elif any(it.evidence_type == EvidenceType.EXECUTABLE for it in items) and not any(it.evidence_type == EvidenceType.REGISTRY for it in items):
            status = SoftwareStatus.PORTABLE

        card_id = hashlib.md5(f"{name}_{install_location}".encode("utf-8")).hexdigest()[:12]

        return SoftwareInventoryCard(
            id=card_id,
            name=name,
            publisher=publisher,
            version=version,
            install_location=install_location,
            main_executable=main_executable,
            uninstall_string=uninstall_string,
            status=status,
            confidence=ConfidenceLevel.HIGH if len(items) > 1 else items[0].confidence,
            last_execution=latest_exec_dt.isoformat() if latest_exec_dt else None,
            run_count=total_run_count,
            focus_seconds=total_focus_seconds,
            days_since_last_run=days_since_run,
            is_orphan=is_orphan,
            orphan_reasons=orphan_reasons,
            evidence=items,
            components=components,
        )


__all__ = ["EvidenceCorrelator"]

