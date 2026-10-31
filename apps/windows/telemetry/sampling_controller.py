# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry - Sampling Controller
# =============================================================================
# Description:
#   Контроллер адаптивного изменения частоты сбора телеметрии (Sampling Controller).
#
# Usage Examples:
#   Python API:
#     from apps.windows.telemetry.sampling_controller import SamplingController
#
#     service = SamplingController()
#
# File: sampling_controller.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-20 09:14:00
# =============================================================================

from __future__ import annotations
"""Контроллер адаптивного изменения частоты сбора телеметрии (Sampling Controller)."""

import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:
    import psutil
    BOOT_TIME = psutil.boot_time()
except Exception:
    BOOT_TIME = time.time()

try:
    from logger import logger
except ImportError:
    from logger import logger

from .models import SamplingMode
from .telemetry_config import TelemetryConfigManager, get_telemetry_config_manager


class SamplingController:
    """Контроллер режимов сбора телеметрии и адаптивного интервала."""

    def __init__(
        self,
        initial_mode: SamplingMode = SamplingMode.BOOT_AGGRESSIVE,
        boot_epoch: Optional[float] = None,
        config_manager: Optional[TelemetryConfigManager] = None,
    ) -> None:
        """Инициализирует контроллер режимов сбора.

        Args:
            initial_mode: Начальный режим работы (по умолчанию BOOT_AGGRESSIVE).
            boot_epoch: Время старта ОС или сервиса в секундах Unix epoch.
            config_manager: Экземпляр TelemetryConfigManager для загрузки интервалов.
        """
        self._mode = initial_mode
        self._boot_epoch = boot_epoch if boot_epoch is not None else BOOT_TIME
        self._start_epoch = time.time()
        self._incident_expiry_epoch: Optional[float] = None
        self._previous_mode: SamplingMode = SamplingMode.MONITORING
        self._config_manager = config_manager or get_telemetry_config_manager()

    def _cfg(self) -> Dict[str, float]:
        """Возвращает актуальный словарь настроек контроллера из конфигурации."""
        return self._config_manager.get_sampling_controller_config()

    @property
    def mode(self) -> SamplingMode:
        """Возвращает текущий режим сбора с учетом авто-истечения инцидентов."""
        self._check_incident_expiration()
        return self._mode

    def set_mode(self, mode: SamplingMode) -> None:
        """Принудительно устанавливает режим сбора телеметрии.

        Args:
            mode: Новый режим работы.
        """
        self._mode = mode
        if mode not in (SamplingMode.INCIDENT, SamplingMode.FORENSIC):
            self._incident_expiry_epoch = None
        logger.info(f"Режим сбора телеметрии переключен на: {self._mode.value}")

    def trigger_incident_mode(self, duration_seconds: Optional[float] = None) -> None:
        """Переводит сборщик в режим INCIDENT на заданную в конфигурации длительность.

        Args:
            duration_seconds: Длительность удержания режима инцидента (если не передано — из config.json).
        """
        dur = duration_seconds if duration_seconds is not None else self._cfg().get("incident_duration_sec", 1200.0)
        if self._mode not in (SamplingMode.INCIDENT, SamplingMode.FORENSIC):
            self._previous_mode = self._mode
        self._mode = SamplingMode.INCIDENT
        self._incident_expiry_epoch = time.time() + max(0.01, dur)
        logger.warning(f"Активирован режим INCIDENT на {dur} сек.")

    def trigger_forensic_mode(self, duration_seconds: Optional[float] = None) -> None:
        """Переводит сборщик в режим FORENSIC на заданную в конфигурации длительность.

        Args:
            duration_seconds: Длительность удержания форензик-режима в секундах (если не передано — из config.json).
        """
        dur = duration_seconds if duration_seconds is not None else self._cfg().get("forensic_duration_sec", 300.0)
        if self._mode not in (SamplingMode.INCIDENT, SamplingMode.FORENSIC):
            self._previous_mode = self._mode
        self._mode = SamplingMode.FORENSIC
        self._incident_expiry_epoch = time.time() + max(0.01, dur)
        logger.warning(f"Активирован высокоскоростной режим FORENSIC на {dur} сек.")

    def get_current_interval(self) -> float:
        """Возвращает текущий рекомендуемый интервал опроса телеметрии в секундах из конфигурации.

        Returns:
            float: Интервал в секундах.
        """
        self._check_incident_expiration()
        cfg = self._cfg()

        if self._mode == SamplingMode.FORENSIC:
            return cfg.get("forensic_interval_sec", 0.25)

        if self._mode == SamplingMode.INCIDENT:
            return cfg.get("incident_interval_sec", 1.0)

        if self._mode == SamplingMode.BOOT_AGGRESSIVE:
            uptime = time.time() - self._boot_epoch
            if uptime < 0:
                uptime = time.time() - self._start_epoch

            if uptime <= cfg.get("boot_phase1_max_uptime_sec", 600.0):
                return cfg.get("boot_phase1_interval_sec", 1.0)
            if uptime <= cfg.get("boot_phase2_max_uptime_sec", 3600.0):
                return cfg.get("boot_phase2_interval_sec", 5.0)
            if uptime <= cfg.get("boot_phase3_max_uptime_sec", 86400.0):
                return cfg.get("boot_phase3_interval_sec", 30.0)
            return cfg.get("normal_interval_sec", 60.0)

        if self._mode == SamplingMode.MONITORING:
            return cfg.get("monitoring_interval_sec", 30.0)

        if self._mode == SamplingMode.NORMAL:
            return cfg.get("normal_interval_sec", 60.0)

        return cfg.get("monitoring_interval_sec", 30.0)

    def get_effective_interval(self, base_interval: Optional[float] = None) -> float:
        """Возвращает эффективный интервал опроса (совместимый алиас для get_current_interval)."""
        if self._mode in (SamplingMode.FORENSIC, SamplingMode.INCIDENT, SamplingMode.BOOT_AGGRESSIVE):
            return self.get_current_interval()
        if base_interval is not None and base_interval > 0:
            return float(base_interval)
        return self.get_current_interval()

    def should_collect_per_process_details(self) -> bool:
        """Определяет, требуется ли собирать глубокий срез по всем процессам на текущем тике."""
        return True

    def _check_incident_expiration(self) -> None:
        """Проверяет истечение времени режима инцидента/форензики и возвращает предыдущий режим."""
        if self._mode in (SamplingMode.INCIDENT, SamplingMode.FORENSIC) and self._incident_expiry_epoch is not None:
            if time.time() >= self._incident_expiry_epoch:
                logger.info("Время фиксации инцидента/форензики истекло. Возврат в штатный режим.")
                self._mode = self._previous_mode
                self._incident_expiry_epoch = None

    def get_status(self) -> Dict[str, Any]:
        """Возвращает статус контроллера опроса.

        Returns:
            Dict[str, Any]: Словарь с текущим режимом, интервалом и временем старта.
        """
        return {
            "mode": self.mode.value,
            "current_interval_sec": self.get_current_interval(),
            "boot_epoch": self._boot_epoch,
            "incident_active": self._mode in (SamplingMode.INCIDENT, SamplingMode.FORENSIC),
            "incident_remaining_sec": max(0.0, (self._incident_expiry_epoch - time.time())) if self._incident_expiry_epoch else 0.0,
        }

