# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Software Scanner - Orphan Detector
# =============================================================================
# Description:
#   Детектор остатков (сирот) программного обеспечения: выявление битых служб,
#   задач планировщика, некорректных записей деинсталлятора и оставшихся папок.
#
# File: orphan_detector.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.software_scanner
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 19:20:00
# =============================================================================

from __future__ import annotations
"""Детектор сирот и остаточных следов удаленного ПО в Windows."""

import os
from typing import List, Tuple
from logger import logger
from apps.windows.sdk.software_scanner.models import (
    ConfidenceLevel,
    EvidenceItem,
    EvidenceType,
)


class OrphanDetector:
    """Детектор осиротевших записей, отсутствующих бинарников и остатков ПО."""

    def find_orphans(self, evidence_list: List[EvidenceItem]) -> Tuple[List[EvidenceItem], List[str]]:
        """Анализ списка собранных следов на наличие осиротевших компонентов.

        Args:
            evidence_list: Полный список найденных свидетельств.

        Returns:
            Tuple[List[EvidenceItem], List[str]]:
                - Список свидетельств, признанных сиротами (остатками);
                - Список текстовых описаний найденных проблем.
        """
        orphans: List[EvidenceItem] = []
        reasons: List[str] = []

        for item in evidence_list:
            # 1. Проверка служб с отсутствующим исполняемым файлом
            if item.evidence_type == EvidenceType.SERVICE:
                target_path = item.path
                if target_path and not os.path.isfile(target_path) and not target_path.lower().startswith("system32"):
                    # Исключаем встроенные псевдо-драйверы ядра без пути
                    if not target_path.endswith(".sys") and "\\" in target_path:
                        item.confidence = ConfidenceLevel.HIGH
                        orphans.append(item)
                        reasons.append(f"Служба '{item.product_name}' указывает на несуществующий файл: {target_path}")

            # 2. Проверка задач планировщика с отсутствующим действием
            elif item.evidence_type == EvidenceType.TASK:
                target_path = item.path
                if target_path and not os.path.isfile(target_path) and "\\" in target_path:
                    item.confidence = ConfidenceLevel.HIGH
                    orphans.append(item)
                    reasons.append(f"Задача планировщика '{item.product_name}' ссылается на удаленный EXE: {target_path}")

            # 3. Проверка записей деинсталлятора (Uninstall)
            elif item.evidence_type == EvidenceType.REGISTRY and "uninstall" in item.source.lower():
                install_loc = item.raw_details.get("installlocation")
                if install_loc and os.path.isabs(install_loc) and not os.path.exists(install_loc):
                    orphans.append(item)
                    reasons.append(f"Программа '{item.product_name}' зарегистрирована в Uninstall, но каталог {install_loc} удален")

        return orphans, reasons


__all__ = ["OrphanDetector"]

