# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Analytics - Hardware Auditor
# =============================================================================
# Description:
#   Аналитический движок аудита аппаратного обеспечения, оценки рисков драйверов
#   и проверки деградации компонентов на базе собранной телеметрии.
#
# Usage Examples:
#   Python API:
#     from apps.windows.analytics.hardware_auditor import HardwareAuditor
#
#     auditor = HardwareAuditor()
#     report = auditor.audit_hardware()
#
# File: hardware_auditor.py
# Project: ai-windows-admin
# Package: apps.windows.analytics
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 08:00:00
# =============================================================================

from __future__ import annotations
"""Аналитический движок аудита аппаратного обеспечения и оценки драйверов."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from apps.windows.telemetry.hardware_collector import HardwareCollector
from apps.windows.telemetry.models import DriverInfo, HardwareAuditReport, HardwareDeviceAudit, HardwareSensor


class HardwareAuditor:
    """Аналитический аудитор аппаратного обеспечения и параметров драйверов."""

    def __init__(
        self,
        collector: Optional[HardwareCollector] = None,
        setupapi_client: Optional[Any] = None,
        storage: Optional[Any] = None
    ) -> None:
        """Инициализация аудитора оборудования.

        Args:
            collector: Экземпляр коллектора телеметрии оборудования.
            setupapi_client: Опциональный клиент SetupAPI (для сборщика).
            storage: Опциональное хранилище TelemetryStorage.
        """
        self._collector = collector or HardwareCollector(
            setupapi_client=setupapi_client,
            storage=storage
        )

    def evaluate_driver_currency(
        self,
        driver_date_dt: Optional[datetime],
        provider: str,
        device_class: str
    ) -> tuple[str, Optional[int]]:
        """Расчет актуальности драйвера на основе даты выпуска и поставщика.

        Args:
            driver_date_dt: Дата выпуска драйвера.
            provider: Поставщик драйвера (NVIDIA, Intel, Microsoft и др.).
            device_class: Класс оборудования (Display, Net, Processor и др.).

        Returns:
            tuple[str, Optional[int]]: (Статус актуальности, возраст в днях).
        """
        now = datetime.now(timezone.utc)
        age_days: Optional[int] = None
        if driver_date_dt:
            age_days = max(0, (now - driver_date_dt).days)
        is_ms_inbox = 'microsoft' in provider.lower()
        if age_days is not None:
            if age_days > 1825:
                if is_ms_inbox and device_class in ('System', 'Volume', 'Processor'):
                    return ('Стандартный системный драйвер', age_days)
                return ('Критически устарел (> 5 лет)', age_days)
            elif age_days > 730:
                if is_ms_inbox and device_class in ('System', 'Volume', 'Processor'):
                    return ('Стандартный системный драйвер', age_days)
                return ('Устарел (> 2 лет)', age_days)
            else:
                return ('Актуален', age_days)
        if is_ms_inbox:
            return ('Базовый драйвер ОС', age_days)
        return ('Не определена', age_days)

    def analyze_devices(self, devices: List[HardwareDeviceAudit]) -> HardwareAuditReport:
        """Аналитическая обработка готового списка устройств телеметрии.

        Args:
            devices: Список собранных устройств телеметрии.

        Returns:
            HardwareAuditReport: Итоговый аналитический отчет с оценками рисков.
        """
        problem_count = 0
        outdated_count = 0

        for dev in devices:
            if dev.status == 'Problem' or (dev.problem_code and dev.problem_code != 0):
                problem_count += 1

            if dev.driver:
                dt: Optional[datetime] = None
                if dev.driver.driver_date:
                    try:
                        dt = datetime.strptime(dev.driver.driver_date, '%Y-%m-%d').replace(tzinfo=timezone.utc)
                    except Exception:
                        dt = None
                currency_status, age_days = self.evaluate_driver_currency(
                    driver_date_dt=dt,
                    provider=dev.driver.provider,
                    device_class=dev.device_class
                )
                dev.driver.currency_status = currency_status
                dev.driver.age_days = age_days
                if 'устарел' in currency_status.lower():
                    outdated_count += 1

        summary_msg = (
            f'Аудит завершен: проверено устройств: {len(devices)}, '
            f'проблемных PnP: {problem_count}, с устаревшими драйверами: {outdated_count}'
        )
        return HardwareAuditReport(
            devices_count=len(devices),
            problem_devices_count=problem_count,
            outdated_drivers_count=outdated_count,
            devices=devices,
            summary=summary_msg
        )

    def audit_hardware(self, sensors: Optional[List[HardwareSensor]] = None) -> HardwareAuditReport:
        """Проведение полного аналитического аудита оборудования.

        Сбор данных делегируется HardwareCollector слоя телеметрии,
        после чего выполняется аналитическая оценка рисков и статусов.

        Args:
            sensors: Опциональный список предварительно собранных сенсоров.

        Returns:
            HardwareAuditReport: Полный аналитический отчет по оборудованию.
        """
        devices = self._collector.collect_devices(sensors=sensors)
        return self.analyze_devices(devices)

