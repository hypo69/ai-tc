# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Tests - PawnIO Provider
# =============================================================================
# Description:
#   Тесты read-only провайдера PawnIO (без реального драйвера).
#
# File: test_pawnio_provider.py
# Project: ai-tc
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-16 05:55:00
# =============================================================================

"""Тесты PawnIOProvider и политики read-only PawnIOClient."""

import pytest
from apps.windows.hardware.base import ProviderStatus, ProviderTier
from apps.windows.hardware.pawnio_client import PawnIOClient, PawnIOError
from apps.windows.hardware.providers import pawnio_provider as mod
from apps.windows.hardware.registry import HardwareProviderRegistry

def test_write_ioctl_rejected():
    """Любой ioctl вне белого списка отклоняется до обращения к драйверу."""
    client = PawnIOClient('x.dll', '.')
    client._lib = object()
    with pytest.raises(PawnIOError):
        client.execute('ioctl_write_msr', [0x1, 0x2])

def test_unavailable_without_dll():
    """Без DLL провайдер недоступен и не возвращает данных."""
    p = mod.PawnIOProvider(binary_path=None)
    assert not p.is_available() and p.status == ProviderStatus.NOT_FOUND
    assert p.probe_sensors() is None

class FakeClient:
    """Фейковый клиент: значения регистров по (ioctl, первый аргумент)."""

    def __init__(self, regs, energy=None):
        self.regs, self.energy = regs, energy or {}

    def execute(self, ioctl, args, out_qwords=1):
        key = (ioctl, args[0])
        if key[1] in self.energy and ioctl == 'ioctl_read_msr':
            return [next(self.energy[key[1]])]
        if key not in self.regs:
            raise PawnIOError('denied')
        return [self.regs[key]]

def _collect(reader, client, monkeypatch):
    monkeypatch.setattr(mod.time, 'sleep', lambda s: None)
    ticks = iter([0.0, 0.1])
    monkeypatch.setattr(mod.time, 'monotonic', lambda: next(ticks))
    out = {}
    reader(client, lambda n, k, v, u: out.__setitem__(n, float(v)))
    return out

def test_intel_msr_decoding(monkeypatch):
    """Intel: Tjmax 100, readout 10 → 90 °C, троттлинг, 50 Вт пакет и 10 Вт ядра; запрещённые MSR пропускаются."""
    m = 'ioctl_read_msr'
    regs = {(m, 0x1A2): 100 << 16, (m, 0x1B1): (10 << 16) | 1 | (1 << 10), (m, 0x606): 16 << 8, (m, 0x198): (40 << 8) | (8192 << 32)}
    client = FakeClient(regs, energy={0x611: iter([0, 50 * 65536 // 10]), 0x639: iter([100, 100 + 10 * 65536 // 10])})
    got = _collect(mod.PawnIOProvider('x.dll')._read_intel, client, monkeypatch)
    assert got == {'CPU Package Temperature': 90.0, 'CPU Thermal Throttling': 1.0, 'CPU Power Limit Throttling': 1.0, 'CPU Core Clock (ratio x 100 MHz)': 4000.0, 'CPU Core Voltage (VID)': 1.0, 'CPU Package Power': 50.0, 'CPU Cores Power': 10.0}

def test_amd_zen_decoding(monkeypatch):
    """Zen: SMN 0x59800 → 50 °C с range select -49; мощность пакета 20 Вт."""
    raw = (int((50 + 49) / 0.125) << 21) | 0x80000
    regs = {('ioctl_read_smn', mod.ZEN_SMN_THM_TCON_CUR_TMP): raw, ('ioctl_read_msr', mod.ZEN_MSR_PWR_UNIT): 16 << 8}
    got = _collect(mod.PawnIOProvider('x.dll')._read_amd_zen, FakeClient(regs, {mod.ZEN_MSR_PKG_ENERGY: iter([0, 20 * 65536 // 10])}), monkeypatch)
    assert got == {'CPU Tctl/Tdie Temperature': 50.0, 'CPU Package Power': 20.0}

def test_legacy_amd_decoding(monkeypatch):
    """K10 (0xA4, >>21 /8) и K8 (THERMTRIP >>16 -49) читают сокеты до первого отказа."""
    k10 = _collect(mod.PawnIOProvider('x.dll')._read_amd_k10, FakeClient({('ioctl_read_miscctl', 0): 400 << 21}), monkeypatch)
    k8 = _collect(mod.PawnIOProvider('x.dll')._read_amd_k8, FakeClient({('ioctl_get_thermtrip', 0): 90 << 16}), monkeypatch)
    assert k10 == {'CPU Socket 0 Temperature': 50.0} and k8 == {'CPU Socket 0 Temperature': 41.0}

def test_module_fallback(monkeypatch):
    """Неподходящий модуль пропускается, подходящий запоминается."""
    p = mod.PawnIOProvider('x.dll')
    monkeypatch.setattr(mod.sys, 'platform', 'win32')
    monkeypatch.setattr(mod.os.path, 'isfile', lambda f: True)
    monkeypatch.setattr(p, '_try_module', lambda m: mod.SensorSnapshot(sensors=[1]) if m == 'AMDFamily17' else None)
    assert p.probe_sensors() is not None and p._module == 'AMDFamily17' and p.status == ProviderStatus.RUNNING
    assert p._candidate_modules()[0] == 'AMDFamily17'
def test_registered_as_kernel_tier():
    """Провайдер зарегистрирован в реестре на уровне Tier 5."""
    p = HardwareProviderRegistry().get_provider('pawnio')
    assert p is not None and p.tier == ProviderTier.TIER_5_KERNEL

