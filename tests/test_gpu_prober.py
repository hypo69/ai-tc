# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - GPU Prober
# =============================================================================
# Description:
#   Тесты GpuProber.probe_all: слияние источников без дублей, применение
#   WDDM-счётчиков, параллельность внешних опросов и устойчивость к ошибкам.
#
# File: test_gpu_prober.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-11 04:40:00
# =============================================================================

from __future__ import annotations

import threading
import time

import pytest

from apps.windows.sdk.modules.hardware.gpu_prober import GpuDeviceTelemetry, GpuProber

LUID = '0x00000000_0x0000abcd'


def _prober(monkeypatch: pytest.MonkeyPatch, nvidia: bool = True) -> GpuProber:
    """Создаёт GpuProber с управляемым наличием nvidia-smi."""
    prober = GpuProber()
    monkeypatch.setattr(prober, '_nvidia_smi', 'nvidia-smi' if nvidia else None)
    monkeypatch.setattr(prober, '_amd_smi', None)
    return prober


def test_merge_deduplicates_wmi_and_applies_wddm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Дубль из WMI отбрасывается, встроенная карта добавляется, WDDM-данные применяются к дискретной."""
    prober = _prober(monkeypatch)
    nv = GpuDeviceTelemetry(index=0, name='NVIDIA GeForce RTX 4070', vendor='NVIDIA', driver_version='1')
    wmi_dup = GpuDeviceTelemetry(index=0, name='NVIDIA GeForce RTX 4070', vendor='NVIDIA', driver_version='1')
    wmi_igpu = GpuDeviceTelemetry(index=1, name='Intel(R) UHD Graphics', vendor='Intel', driver_version='2')
    monkeypatch.setattr(prober, '_probe_nvidia', lambda: [nv])
    monkeypatch.setattr(prober, '_probe_wmi', lambda: [wmi_dup, wmi_igpu])
    monkeypatch.setattr(
        prober, '_query_wddm_counters',
        lambda: ({LUID: {'dedicated_mb': 512.0, 'shared_mb': 64.0, 'total_mb': 576.0}},
                 {LUID: {'3D': 42.0}}),
    )

    gpus = prober.probe_all()

    assert [g.name for g in gpus] == ['NVIDIA GeForce RTX 4070', 'Intel(R) UHD Graphics']
    assert [g.index for g in gpus] == [0, 1]
    assert gpus[0].dedicated_memory_used_mb == 512.0
    assert gpus[0].engines == {'3D Engine': 42.0}
    assert gpus[0].utilization_gpu_pct == 42.0


def test_probes_run_in_parallel(monkeypatch: pytest.MonkeyPatch) -> None:
    """Внешние опросы стартуют одновременно: общее время ≈ одной задержки, а не суммы."""
    prober = _prober(monkeypatch)
    started: list[float] = []
    barrier_lock = threading.Lock()

    def slow(result):
        def _inner():
            with barrier_lock:
                started.append(time.perf_counter())
            time.sleep(0.4)
            return result
        return _inner

    monkeypatch.setattr(prober, '_probe_nvidia', slow([]))
    monkeypatch.setattr(prober, '_probe_wmi', slow([]))
    monkeypatch.setattr(prober, '_query_wddm_counters', slow(({}, {})))

    t0 = time.perf_counter()
    prober.probe_all()
    elapsed = time.perf_counter() - t0

    assert len(started) == 3
    assert elapsed < 0.9  # последовательно было бы >= 1.2 с


def test_wddm_error_does_not_break_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    """Пустые WDDM-счётчики не мешают вернуть карты из других источников."""
    prober = _prober(monkeypatch, nvidia=False)
    igpu = GpuDeviceTelemetry(index=0, name='Intel(R) UHD Graphics', vendor='Intel', driver_version='2')
    monkeypatch.setattr(prober, '_probe_wmi', lambda: [igpu])
    monkeypatch.setattr(prober, '_query_wddm_counters', lambda: ({}, {}))
    gpus = prober.probe_all()
    assert [g.name for g in gpus] == ['Intel(R) UHD Graphics']

