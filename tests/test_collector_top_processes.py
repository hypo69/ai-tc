# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Collector Top Processes
# =============================================================================
# Description:
#   Тесты SystemCollector.get_top_processes: лимит, сортировка и ленивое
#   чтение командной строки только для процессов из топ-N.
#
# File: test_collector_top_processes.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-11 04:25:19
# =============================================================================

from __future__ import annotations

import psutil
import pytest

from apps.windows.telemetry.collector import SystemCollector


@pytest.fixture(scope='module')
def collector() -> SystemCollector:
    """Единый коллектор на модуль (инициализация недешёвая)."""
    return SystemCollector()


def test_limit_respected(collector: SystemCollector) -> None:
    """Возвращается не больше limit процессов."""
    assert 0 < len(collector.get_top_processes(limit=5)) <= 5


def test_zero_limit_returns_all(collector: SystemCollector) -> None:
    """limit=0 возвращает все процессы (больше, чем топ-5)."""
    assert len(collector.get_top_processes(limit=0)) > 5


@pytest.mark.parametrize('sort_by, attr', [('memory', 'memory_mb'), ('handles', 'num_handles'), ('cpu', 'cpu_percent')])
def test_sorted_descending(collector: SystemCollector, sort_by: str, attr: str) -> None:
    """Результат отсортирован по убыванию выбранного ключа."""
    values = [getattr(p, attr) for p in collector.get_top_processes(limit=15, sort_by=sort_by)]
    assert values == sorted(values, reverse=True)


def test_cmdline_requested_only_for_top(collector: SystemCollector, monkeypatch: pytest.MonkeyPatch) -> None:
    """cmdline запрашивается точечно: число вызовов не превышает limit."""
    calls: list[int] = []
    original = psutil.Process.cmdline

    def counting(self: psutil.Process) -> list[str]:
        calls.append(self.pid)
        return original(self)

    monkeypatch.setattr(psutil.Process, 'cmdline', counting)
    collector.get_top_processes(limit=5)
    assert len(calls) <= 5 + 2  # +2: внутренние вызовы psutil (exe() для pid 0)

def test_npu_metrics_cached(collector: SystemCollector, monkeypatch: pytest.MonkeyPatch) -> None:
    """Повторный get_npu_metrics в пределах TTL не запускает повторный опрос оборудования."""
    from apps.windows.sdk.modules.hardware import gpu_prober

    probes: list[int] = []
    monkeypatch.setattr(gpu_prober.GpuProber, 'probe_npus', lambda self: probes.append(1) or [])
    collector._npus_cached = None
    first = collector.get_npu_metrics()
    second = collector.get_npu_metrics()
    assert first == second == []
    assert len(probes) == 1


def test_npu_metrics_error_not_cached(collector: SystemCollector, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ошибка опроса NPU не кэшируется: следующий вызов повторяет опрос."""
    from apps.windows.sdk.modules.hardware import gpu_prober

    def boom(self) -> list:
        raise RuntimeError('probe failed')

    monkeypatch.setattr(gpu_prober.GpuProber, 'probe_npus', boom)
    collector._npus_cached = None
    assert collector.get_npu_metrics() == []
    assert collector._npus_cached is None

