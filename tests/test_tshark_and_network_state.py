# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - TShark and Network State
# =============================================================================
# Description:
#   Модульные тесты для пакета apps.tshark и NetworkTerminalState.
#
# Usage Examples:
#   pytest tests/test_tshark_and_network_state.py
#
# File: test_tshark_and_network_state.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-20 13:41:00
# =============================================================================

from __future__ import annotations
"""Тесты функционала пакета apps.tshark, парсера интерфейсов и состояния сетевого терминала."""

import pytest
from apps.tshark import (
    AIDetector,
    AnomalyReport,
    CaptureFilter,
    NetworkInterface,
    PacketSummary,
    TSharkWrapper,
    TrafficAnalyzer,
    TrafficStats,
)
from apps.windows.sdk.modules.network.tui import NetworkTerminalState


def test_packet_summary_model() -> None:
    """Проверка создания PacketSummary и работы псевдонимов полей."""
    pkt = PacketSummary(
        packet_number=10,
        timestamp="2026-10-20T12:00:00Z",
        source="192.168.1.50",
        destination="1.1.1.1",
        protocol="DNS",
        length=75,
        source_port=53210,
        destination_port=53,
        info="Standard query A example.com",
    )
    assert pkt.packet_number == 10
    assert pkt.number == 10
    assert pkt.source_ip == "192.168.1.50"
    assert pkt.destination_ip == "1.1.1.1"
    assert pkt.protocol == "DNS"
    assert pkt.length == 75


def test_traffic_analyzer_compute_stats() -> None:
    """Проверка расчета суммарной статистики трафика."""
    analyzer = TrafficAnalyzer()
    packets = [
        PacketSummary(
            packet_number=1,
            timestamp="2026-10-20T12:00:00Z",
            source="10.0.0.2",
            destination="10.0.0.1",
            protocol="TCP",
            length=100,
            destination_port=80,
        ),
        PacketSummary(
            packet_number=2,
            timestamp="2026-10-20T12:00:01Z",
            source="10.0.0.2",
            destination="1.1.1.1",
            protocol="DNS",
            length=50,
            destination_port=53,
        ),
    ]
    stats = analyzer.compute_stats(packets)
    assert stats.total_packets == 2
    assert stats.total_bytes == 150
    assert stats.protocol_distribution.get("TCP") == 1
    assert stats.protocol_distribution.get("DNS") == 1
    assert stats.top_sources.get("10.0.0.2") == 2


def test_traffic_analyzer_heuristics() -> None:
    """Проверка детекции эвристических признаков аномалий."""
    analyzer = TrafficAnalyzer()
    packets = [
        PacketSummary(
            packet_number=i,
            timestamp="2026-10-20T12:00:00Z",
            source="192.168.1.100",
            destination="192.168.1.1",
            protocol="TCP",
            length=60,
            destination_port=1000 + i,
        )
        for i in range(20)
    ]
    heuristics = analyzer.detect_heuristics(packets)
    assert any("сканирование портов" in h.lower() for h in heuristics)


@pytest.mark.asyncio
async def test_ai_detector_diagnose() -> None:
    """Проверка формирования отчета безопасности AI детектором."""
    detector = AIDetector()
    analyzer = TrafficAnalyzer()
    packets = [
        PacketSummary(
            packet_number=1,
            timestamp="2026-10-20T12:00:00Z",
            source="192.168.1.20",
            destination="8.8.8.8",
            protocol="TLS",
            length=256,
            destination_port=443,
        )
    ]
    stats = analyzer.compute_stats(packets)
    report = await detector.diagnose_traffic(packets, stats, [])
    assert report.threat_level == "NORMAL"
    assert report.health_score == 100
    assert len(report.anomalies) == 0


def test_network_terminal_state_init() -> None:
    """Проверка инициализации NetworkTerminalState без исключений."""
    state = NetworkTerminalState(interface="1", display_filter="")
    assert state.interface == "1"
    assert state.wrapper is not None
    assert state.analyzer is not None
    assert state.total_packets_captured == 0

    pkt = PacketSummary(
        packet_number=1,
        timestamp="2026-10-20T12:00:00Z",
        source="127.0.0.1",
        destination="127.0.0.1",
        protocol="HTTP",
        length=200,
    )
    state.add_packet(pkt)
    assert state.total_packets_captured == 1
    assert state.total_bytes_captured == 200

    stats = state.compute_stats()
    assert stats.total_packets == 1
    state.evaluate_security()
    assert isinstance(state.latest_heuristics, list)


def test_tshark_wrapper_finds_bin_path(tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверка приоритетного обнаружения tshark в папке bin."""
    mock_bin_dir = tmp_path / "bin" / "tshark"
    mock_bin_dir.mkdir(parents=True)
    mock_exe = mock_bin_dir / "tshark.exe"
    mock_exe.write_text("dummy", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    wrapper = TSharkWrapper()
    assert wrapper.tshark_path is not None
    assert "tshark.exe" in wrapper.tshark_path.lower()


