# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Software Scanner - Unit Tests
# =============================================================================
# Description:
#   Модульные тесты для подсистемы глубокого сканирования ПО: проверка моделей,
#   политик, зондов реестра/файлов/служб/задач, детектора сирот, коррелятора
#   и генератора отчетов.
#
# File: test_software_scanner.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.software_scanner.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 19:20:00
# =============================================================================

import os
from unittest.mock import MagicMock, patch
import pytest

from apps.windows.sdk.software_scanner.models import (
    ConfidenceLevel,
    EvidenceItem,
    EvidenceType,
    ScanMode,
    SoftwareInventoryCard,
    SoftwareStatus,
)
from apps.windows.sdk.software_scanner.policies import ScannerPolicy
from apps.windows.sdk.software_scanner.scope import ScannerScope
from apps.windows.sdk.software_scanner.metadata_extractor import PEMetadataExtractor
from apps.windows.sdk.software_scanner.orphan_detector import OrphanDetector
from apps.windows.sdk.software_scanner.correlator import EvidenceCorrelator
from apps.windows.sdk.software_scanner.controller import DeepSoftwareScanner
from apps.windows.sdk.software_scanner.report import ReportFormatter


def test_models_instantiation():
    """Тест создания моделей EvidenceItem и SoftwareInventoryCard."""
    item = EvidenceItem(
        evidence_type=EvidenceType.EXECUTABLE,
        source="Filesystem",
        path=r"C:\Tools\app.exe",
        product_name="TestApp",
        publisher="TestVendor",
        version="1.0.0",
    )
    assert item.product_name == "TestApp"
    assert item.confidence == ConfidenceLevel.MEDIUM

    card = SoftwareInventoryCard(
        id="abc123",
        name="TestApp",
        status=SoftwareStatus.DORMANT,
        evidence=[item],
    )
    assert card.name == "TestApp"
    assert card.status == SoftwareStatus.DORMANT


def test_scanner_scope_filtering():
    """Тест фильтрации исключенных директорий и получения корней."""
    policy = ScannerPolicy()
    scope = ScannerScope(policy)

    assert scope.is_excluded_dir("winsxs") is True
    assert scope.is_excluded_dir("node_modules") is True
    assert scope.is_excluded_dir("my_custom_app") is False

    roots = scope.get_system_install_roots()
    assert isinstance(roots, list)


def test_metadata_extractor_sha256(tmp_path):
    """Тест вычисления хеша SHA-256 для файла."""
    dummy_file = tmp_path / "test_bin.exe"
    dummy_file.write_bytes(b"HELLO_WORLD_BINARY_DATA")

    digest = PEMetadataExtractor.compute_sha256(str(dummy_file))
    assert digest is not None
    assert len(digest) == 64


def test_orphan_detector():
    """Тест обнаружения битых служб и некорректных записей деинсталляторов."""
    detector = OrphanDetector()

    broken_service = EvidenceItem(
        evidence_type=EvidenceType.SERVICE,
        source="Services_SCM",
        path=r"C:\NonExistentDir\NonExistentService.exe",
        product_name="GhostService",
    )

    valid_item = EvidenceItem(
        evidence_type=EvidenceType.EXECUTABLE,
        source="Filesystem",
        path=r"C:\Windows\explorer.exe",
        product_name="Explorer",
    )

    orphans, reasons = detector.find_orphans([broken_service, valid_item])
    assert len(orphans) == 1
    assert orphans[0].product_name == "GhostService"
    assert len(reasons) == 1


def test_correlator_dormant_and_active():
    """Тест классификации программ по активности запусков."""
    correlator = EvidenceCorrelator()

    # Свежий запуск (активная)
    fresh_evidence = EvidenceItem(
        evidence_type=EvidenceType.USERASSIST,
        source="UserAssist_ROT13",
        path=r"C:\Apps\ActiveApp.exe",
        product_name="ActiveApp",
        last_execution="2026-10-09T12:00:00+00:00",
        run_count=42,
    )

    # Старый запуск (dormant)
    old_evidence = EvidenceItem(
        evidence_type=EvidenceType.USERASSIST,
        source="UserAssist_ROT13",
        path=r"C:\Apps\DormantApp.exe",
        product_name="DormantApp",
        last_execution="2025-01-01T12:00:00+00:00",
        run_count=2,
    )

    cards = correlator.correlate([fresh_evidence, old_evidence])
    assert len(cards) == 2

    card_map = {c.name: c for c in cards}
    assert card_map["ActiveApp"].status == SoftwareStatus.ACTIVE
    assert card_map["DormantApp"].status == SoftwareStatus.DORMANT


def test_controller_quick_scan():
    """Тест контроллера глубокого сканера в режиме Quick."""
    scanner = DeepSoftwareScanner()
    report = scanner.run_scan(mode=ScanMode.QUICK)

    assert report.scan_id is not None
    assert report.mode == ScanMode.QUICK
    assert report.stats.total_evidence_found >= 0

    markdown_summary = ReportFormatter.format_summary_markdown(report)
    assert "Отчет глубокого аудита ПО" in markdown_summary
    assert report.scan_id in markdown_summary

