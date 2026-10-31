# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Failures Analyzer Test
# =============================================================================
# Description:
#   Модульные тесты комплексного анализатора сбоев FailuresAnalyzer
#   (питание, BSOD, ошибки драйверов и подозрительная активность телеметрии).
#
# Usage Examples:
#   pytest tests/test_failures_analyzer.py -v
#
# File: test_failures_analyzer.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 12:50:00
# =============================================================================

from __future__ import annotations
"""Модульные тесты анализатора сбоев FailuresAnalyzer."""

import pytest
from apps.windows.telemetry.failures_analyzer import FailuresAnalyzer


def test_failures_analyzer_initialization():
    """Тест корректной инициализации анализатора сбоев."""
    analyzer = FailuresAnalyzer()
    assert analyzer is not None
    assert analyzer.wevtapi is not None
    assert analyzer.power_engine is not None
    assert analyzer.driver_collector is not None


def test_failures_analyzer_summary_structure():
    """Тест формирования структуры сводки сбоев."""
    analyzer = FailuresAnalyzer()
    summary = analyzer.get_comprehensive_summary(hours=24)

    assert summary['status'] == 'ok'
    assert 'generated_at' in summary
    assert 'metrics' in summary
    assert 'power_failures' in summary
    assert 'bsod_incidents' in summary
    assert 'driver_errors' in summary
    assert 'suspicious_activity' in summary

    metrics = summary['metrics']
    assert 'power_failures_count' in metrics
    assert 'bsod_count' in metrics
    assert 'driver_errors_count' in metrics
    assert 'suspicious_activity_count' in metrics
    assert 'clean_shutdown_ratio' in metrics
    assert 'total_sessions' in metrics
    assert 'overall_risk' in metrics
    assert metrics['overall_risk'] in ('ok', 'warning', 'critical')


def test_failures_analyzer_empty_handling():
    """Тест корректной работы с нулевым периодом выборки."""
    analyzer = FailuresAnalyzer()
    summary = analyzer.get_comprehensive_summary(hours=1)
    assert summary['status'] == 'ok'
    assert isinstance(summary['power_failures'], list)
    assert isinstance(summary['bsod_incidents'], list)
    assert isinstance(summary['driver_errors'], list)
    assert isinstance(summary['suspicious_activity'], list)

