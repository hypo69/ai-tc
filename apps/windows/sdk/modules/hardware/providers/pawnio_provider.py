# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Apps Windows Modules Hardware - PawnIO Provider
# =============================================================================
# Description:
#   Опциональный провайдер Kernel Hardware Access (PawnIO). Автоопределение CPU:
#   Intel (IntelMSR), AMD Zen (AMDFamily17), AMD K10 (AMDFamily10), AMD K8 (AMDFamily0F).
#   Только чтение; каждый датчик читается независимо, недоступные пропускаются.
#   Инвентаризацию не выполняет (её дают native/HWiNFO/AIDA64/CPU-Z).
#
# Usage Examples:
#   Python API:
#     from apps.windows.hardware.providers.pawnio_provider import PawnIOProvider
#
#     snapshot = PawnIOProvider(binary_path=dll_path).probe_sensors()
#
# File: pawnio_provider.py
# Project: ai-tc
# Package: apps.windows.sdk.modules.hardware.providers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-16 05:55:00
# =============================================================================

from __future__ import annotations
"""Опциональный read-only провайдер PawnIO: датчики CPU Intel и AMD любых поколений."""

import os
import sys
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional
from logger import logger
from apps.windows.hardware.base import BaseHardwareProvider, ProviderCapability, ProviderStatus, ProviderTier
from apps.windows.hardware.models import SensorReading, SensorSnapshot, SystemHardwareInventory
from apps.windows.hardware.pawnio_client import PawnIOClient, PawnIOError

ENERGY_SAMPLE_INTERVAL_SEC = 0.1
ENERGY_COUNTER_MASK = 0xFFFFFFFF
READ_MSR = 'ioctl_read_msr'
INTEL_RAPL_DOMAINS = {0x611: 'CPU Package Power', 0x639: 'CPU Cores Power', 0x641: 'CPU Graphics Power', 0x619: 'DRAM Power', 0x64D: 'Platform Power'}
ZEN_SMN_THM_TCON_CUR_TMP = 0x59800
ZEN_MSR_PWR_UNIT = 0xC0010299
ZEN_MSR_PKG_ENERGY = 0xC001029B
LEGACY_AMD_MAX_SOCKETS = 4
K10_REPORTED_TEMPERATURE_CONTROL = 0xA4
K8_TEMPERATURE_OFFSET_C = -49

class PawnIOProvider(BaseHardwareProvider):
    """Опциональный провайдер PawnIO: read-only телеметрия CPU."""

    def __init__(self, binary_path: Optional[str]=None) -> None:
        """Инициализация провайдера.

        Args:
            binary_path: Путь к PawnIOLib.dll официальной поставки (None — PawnIO не установлен).
        """
        super().__init__(name='PawnIO', tier=ProviderTier.TIER_5_KERNEL, binary_path=binary_path)
        self._module: Optional[str] = None
        self._warned = False
        self._readers: Dict[str, Callable[[PawnIOClient, Callable[..., None]], None]] = {'IntelMSR': self._read_intel, 'AMDFamily17': self._read_amd_zen, 'AMDFamily10': self._read_amd_k10, 'AMDFamily0F': self._read_amd_k8}

    def is_available(self) -> bool:
        """Проверить наличие PawnIOLib.dll (только Windows). Отсутствие — штатная ситуация."""
        if sys.platform == 'win32' and self.binary_path and os.path.isfile(self.binary_path):
            if self._status == ProviderStatus.NOT_FOUND:
                self._status = ProviderStatus.AVAILABLE
            return True
        self._status = ProviderStatus.NOT_FOUND
        return False

    def get_capabilities(self) -> List[ProviderCapability]:
        """Возможности: только живые датчики."""
        return [ProviderCapability.LIVE_SENSORS]

    def probe_inventory(self) -> Optional[SystemHardwareInventory]:
        """Инвентаризация не поддерживается; всегда возвращает None."""
        return None

    def probe_sensors(self) -> Optional[SensorSnapshot]:
        """Прочитать все доступные датчики подходящего модуля.

        Returns:
            Снимок датчиков или None, если PawnIO не установлен либо ни один модуль
            не подошёл процессору (причина логируется один раз).
        """
        if not self.is_available():
            return None
        for module in self._candidate_modules():
            snapshot = self._try_module(module)
            if snapshot is not None:
                self._module = module
                self._status = ProviderStatus.RUNNING
                return snapshot
        self._module = None
        self._status = ProviderStatus.ERROR
        (logger.debug if self._warned else logger.warning)('PawnIO: ни один модуль не подошёл процессору либо драйвер не установлен/недоступен')
        self._warned = True
        return None

    def _candidate_modules(self) -> List[str]:
        """Порядок опроса модулей: запомненный, затем по вендору процессора."""
        ident = os.environ.get('PROCESSOR_IDENTIFIER', '')
        order = ['AMDFamily17', 'AMDFamily10', 'AMDFamily0F', 'IntelMSR'] if 'AMD' in ident else ['IntelMSR', 'AMDFamily17', 'AMDFamily10', 'AMDFamily0F']
        if self._module in order:
            order.remove(self._module)
            order.insert(0, self._module)
        return order

    def _try_module(self, module: str) -> Optional[SensorSnapshot]:
        """Загрузить модуль и считать датчики; None, если модуль не подходит или датчиков нет."""
        dll_dir = Path(self.binary_path).parent
        modules_dir = dll_dir / 'modules' if (dll_dir / 'modules').is_dir() else dll_dir
        snapshot = SensorSnapshot(source_provider=self.name)
        add = lambda name, kind, value, unit: snapshot.sensors.append(SensorReading(name=name, sensor_type=kind, value=float(value), unit=unit, hardware_name='CPU', hardware_type='CPU'))
        try:
            with PawnIOClient(self.binary_path, str(modules_dir)) as client:
                client.load_module(module)
                self._readers[module](client, add)
        except PawnIOError as e:
            logger.debug(f'PawnIO: модуль {module} недоступен: {e}')
            return None
        return snapshot if snapshot.sensors else None

    @staticmethod
    def _try_read(client: PawnIOClient, ioctl: str, *args: int) -> Optional[int]:
        """Выполнить read-ioctl; None, если регистр недоступен (отклонён модулем/драйвером)."""
        try:
            return client.execute(ioctl, list(args))[0]
        except (PawnIOError, IndexError):
            return None

    def _rapl_power(self, client: PawnIOClient, domains: Dict[int, str], energy_unit_j: float, add: Callable[..., None]) -> None:
        """Мощность доменов по двум замерам 32-битных счётчиков энергии (MSR)."""
        e0 = {m: self._try_read(client, READ_MSR, m) for m in domains}
        e0 = {m: v & ENERGY_COUNTER_MASK for m, v in e0.items() if v is not None}
        if not e0:
            return
        t0 = time.monotonic()
        time.sleep(ENERGY_SAMPLE_INTERVAL_SEC)
        e1 = {m: self._try_read(client, READ_MSR, m) for m in e0}
        dt = time.monotonic() - t0
        for msr, start in e0.items():
            end = e1[msr]
            if end is None or (start == 0 and end & ENERGY_COUNTER_MASK == 0):
                continue
            add(domains[msr], 'Power', round(((end & ENERGY_COUNTER_MASK) - start) % (ENERGY_COUNTER_MASK + 1) * energy_unit_j / dt, 2), 'W')

    def _read_intel(self, client: PawnIOClient, add: Callable[..., None]) -> None:
        """Intel: температура, троттлинг, множитель/напряжение, лимит PL1, мощности RAPL."""
        rd = lambda msr: self._try_read(client, READ_MSR, msr)
        tjmax = ((rd(0x1A2) or 0) >> 16) & 0xFF
        therm = rd(0x1B1)
        if therm is not None:
            if tjmax:
                add('CPU Package Temperature', 'Temperature', tjmax - ((therm >> 16) & 0x7F), '°C')
            add('CPU Thermal Throttling', 'Flag', therm & 1, '')
            add('CPU Power Limit Throttling', 'Flag', (therm >> 10) & 1, '')
        perf = rd(0x198)
        if perf is not None:
            add('CPU Core Clock (ratio x 100 MHz)', 'Clock', ((perf >> 8) & 0xFF) * 100, 'MHz')
            add('CPU Core Voltage (VID)', 'Voltage', round(((perf >> 32) & 0xFFFF) / 8192, 4), 'V')
        unit = rd(0x606)
        if unit is not None:
            pl1 = rd(0x610)
            if pl1 is not None:
                add('CPU PL1 Power Limit', 'Power', (pl1 & 0x7FFF) / (1 << (unit & 0xF)), 'W')
            self._rapl_power(client, INTEL_RAPL_DOMAINS, 1.0 / (1 << ((unit >> 8) & 0x1F)), add)

    def _read_amd_zen(self, client: PawnIOClient, add: Callable[..., None]) -> None:
        """AMD Zen (Family 17h+): температура Tctl/Tdie через SMN, мощность пакета."""
        raw = self._try_read(client, 'ioctl_read_smn', ZEN_SMN_THM_TCON_CUR_TMP)
        if raw is not None:
            temp = (raw >> 21) * 0.125 - (49 if raw & 0x80000 else 0)
            add('CPU Tctl/Tdie Temperature', 'Temperature', round(temp, 3), '°C')
        unit = self._try_read(client, READ_MSR, ZEN_MSR_PWR_UNIT)
        if unit is not None:
            self._rapl_power(client, {ZEN_MSR_PKG_ENERGY: 'CPU Package Power'}, 1.0 / (1 << ((unit >> 8) & 0x1F)), add)

    def _read_amd_k10(self, client: PawnIOClient, add: Callable[..., None]) -> None:
        """AMD K10/K11/K12/K14/K15: температура сокетов через MISCCTL."""
        for cpu in range(LEGACY_AMD_MAX_SOCKETS):
            raw = self._try_read(client, 'ioctl_read_miscctl', cpu, K10_REPORTED_TEMPERATURE_CONTROL)
            if raw is None:
                break
            add(f'CPU Socket {cpu} Temperature', 'Temperature', ((raw >> 21) & 0x7FF) / 8.0, '°C')

    def _read_amd_k8(self, client: PawnIOClient, add: Callable[..., None]) -> None:
        """AMD K8: температура сокетов через THERMTRIP (ядро 0)."""
        for cpu in range(LEGACY_AMD_MAX_SOCKETS):
            raw = self._try_read(client, 'ioctl_get_thermtrip', cpu, 0)
            if raw is None:
                break
            add(f'CPU Socket {cpu} Temperature', 'Temperature', ((raw >> 16) & 0xFF) + K8_TEMPERATURE_OFFSET_C, '°C')
