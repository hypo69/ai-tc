# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Log_Intelligence Tests - Test Intelligence Pipeline
# =============================================================================
# Description:
#   Комплексные тесты Log Intelligence: Data Researcher, Decision Gate,
#   In-Memory RAM AdaptiveLogRAG семантического поиска по системным журналам.
#
# Usage Examples:
#   pytest apps/windows/log_intelligence/tests/ -v
#
# File: test_intelligence_pipeline.py
# Project: ai-windows-admin
# Package: apps.windows.log_intelligence.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-13 16:25:00
# =============================================================================

"""Тесты Log Intelligence и In-Memory RAG семантического поиска по логам Windows."""

from pathlib import Path
import pytest
from apps.windows.log_intelligence.src.models import DataProfileReport, IngestionDecision, IngestionStrategy, LogEntry, LogSeverity
from apps.windows.log_intelligence.src.data_researcher import LogDataResearcher
from apps.windows.log_intelligence.src.decision_gate import DecisionGate
from apps.windows.log_intelligence.src.adaptive_rag import AdaptiveLogRAG, get_default_storage_dir
from apps.windows.log_intelligence.src.pipeline import LogIntelligencePipeline


def test_data_researcher_profiling() -> None:
    """Проверка работы Data Researcher: подсчет Redundancy Ratio, Health Score и детекция всплесков."""
    researcher = LogDataResearcher()
    entries = [
        LogEntry(timestamp='2026-09-16 15:00:01', level='Information', provider='Service', event_id=7036, message='Service started'),
        LogEntry(timestamp='2026-09-16 15:00:02', level='Information', provider='Service', event_id=7036, message='Service started'),
        LogEntry(timestamp='2026-09-16 15:00:03', level='Information', provider='Service', event_id=7036, message='Service started'),
        LogEntry(timestamp='2026-09-16 15:05:00', level='Error', provider='Kernel-Power', event_id=41, message='Reboot without shutdown'),
        LogEntry(timestamp='2026-09-16 15:05:01', level='Warning', provider='rt640x64', event_id=1, message='Network disconnected'),
    ]
    profile = researcher.profile_data(entries, channel='System')
    assert profile.total_events == 5
    assert profile.unique_templates_count < 5
    assert profile.redundancy_ratio_pct > 0.0
    assert profile.error_count == 1
    assert profile.warning_count == 1
    assert profile.health_score < 100.0


def test_decision_gate_strategies() -> None:
    """Проверка выбора стратегий в Decision Gate."""
    gate = DecisionGate()
    err_profile = DataProfileReport(channel='System', total_events=100, unique_templates_count=20, redundancy_ratio_pct=80.0, health_score=65.0, error_count=2)
    dec1 = gate.evaluate(err_profile)
    assert dec1.strategy == IngestionStrategy.INCIDENT_FOCUSED

    healthy_profile = DataProfileReport(channel='System', total_events=100, unique_templates_count=15, redundancy_ratio_pct=85.0, health_score=100.0, error_count=0, warning_count=0)
    dec2 = gate.evaluate(healthy_profile)
    assert dec2.strategy == IngestionStrategy.SNAPSHOT_ONLY

    noisy_profile = DataProfileReport(channel='System', total_events=500, unique_templates_count=5, redundancy_ratio_pct=99.0, health_score=98.0, dominant_noise_provider='Kernel-PnP')
    dec3 = gate.evaluate(noisy_profile)
    assert dec3.strategy == IngestionStrategy.NOISE_MASKED


def test_in_memory_adaptive_rag_pipeline(tmp_path: Path) -> None:
    """Проверка полного цикла In-Memory RAG с семантическим поиском в оперативной памяти."""
    rag = AdaptiveLogRAG()
    entries = [
        {'channel': 'System', 'provider': 'rt640x64', 'event_id': 1, 'level': 'Warning', 'timestamp': '2026-10-10 12:00:00', 'message': 'Realtek PCIe GbE Family Controller network link is down'},
        {'channel': 'System', 'provider': 'Microsoft-Windows-Kernel-Power', 'event_id': 41, 'level': 'Critical', 'timestamp': '2026-10-10 12:05:00', 'message': 'The system has rebooted without cleanly shutting down first'},
        {'channel': 'Application', 'provider': 'Microsoft-Windows-DistributedCOM', 'event_id': 10016, 'level': 'Error', 'timestamp': '2026-10-10 12:10:00', 'message': 'The application-specific permission settings do not grant Local Activation permission for COM Server'},
    ]
    indexed = rag.index_events(entries)
    assert indexed == 3

    status = rag.get_status()
    assert status['storage_mode'] == 'RAM_IN_MEMORY'
    assert status['total_events'] == 3

    # 1. Поиск по концепции "сеть" (русский синоним к "network link down")
    net_res = rag.search('отвал сети и адаптера')
    assert len(net_res) > 0
    assert net_res[0]['provider'] == 'rt640x64' or 'Realtek' in net_res[0]['message']

    # 2. Поиск по концепции "перезагрузка и сбой питания"
    power_res = rag.search('перезагрузка сбой питания')
    assert len(power_res) > 0
    assert any(r['event_id'] == 41 for r in power_res)

    # 3. Поиск по конкретному Event ID
    dcom_res = rag.search('10016')
    assert len(dcom_res) > 0
    assert dcom_res[0]['event_id'] == 10016


def test_multi_channel_rag_indexing() -> None:
    """Проверка сбора и индексации событий за сутки со всех доступных каналов Windows."""
    rag = AdaptiveLogRAG()
    report = rag.index_all_system_logs(hours=24, limit_per_channel=30)
    assert report['status'] == 'ok'
    assert report['storage_mode'] == 'RAM_IN_MEMORY'
    assert report['scanned_channels'] > 0
    assert report['indexed_events'] > 0

    # Проверка семантического поиска по живому массиву событий в RAM
    search_res = rag.search('ошибка сбой error warning', top_k=5)
    assert isinstance(search_res, list)


def test_wevtapi_channel_enumeration() -> None:
    """Проверка нативного перечисления каналов через WevtAPI."""
    from apps.windows.sdk.win32_ffi.wevtapi import WevtAPI
    api = WevtAPI()
    channels = api.enumerate_channels()
    assert len(channels) >= 10
    names = [c.channel_name.lower() for c in channels]
    assert 'system' in names
    assert 'application' in names


def test_log_discovery_engine_sources() -> None:
    """Проверка обнаружения всех источников логов в системе через LogDiscoveryEngine."""
    from apps.windows.sdk.core.audits.log_discovery_engine import LogDiscoveryEngine
    engine = LogDiscoveryEngine()
    sources = engine.discover_all_sources()
    assert len(sources) > 50
    categories = {s.category for s in sources}
    assert 'Windows Event Log' in categories

