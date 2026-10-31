# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Services - Sysmon Inspector
# =============================================================================
# Description:
#   Инспектор статуса службы Microsoft Sysmon. Исключает ложноотрицательный
#   статус "Не установлен", выполняя проверку доступности и активности канала
#   Windows Event Log «Microsoft-Windows-Sysmon/Operational» через win32evtlog.
#
# Usage Examples:
#   Python API:
#     from apps.windows.api.services.sysmon_inspector import SysmonInspector
#
#     inspector = SysmonInspector()
#     status = inspector.get_status()
#
# File: sysmon_inspector.py
# Project: ai-windows-admin
# Package: apps.windows.api.services
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-16 23:58:00
# =============================================================================

from __future__ import annotations
"""Инспектор статуса службы Sysmon с валидацией канала Windows Event Log."""

import subprocess
import sys
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from logger import logger

# Попытка импорта win32evtlog
try:
    import win32evtlog  # type: ignore
except ImportError:
    win32evtlog = None


class SysmonStatusInfo(BaseModel):
    """Модель статуса службы и телеметрии Sysmon."""
    is_installed: bool = Field(default=False, description="Установлен ли Sysmon")
    is_running: bool = Field(default=False, description="Запущена ли служба Sysmon")
    channel_active: bool = Field(default=False, description="Активен ли канал журнала Sysmon")
    channel_name: str = Field(default="Microsoft-Windows-Sysmon/Operational", description="Имя журнала")
    status_text: str = Field(default="Не установлен", description="Человекопонятный статус")
    details: Dict[str, Any] = Field(default_factory=dict, description="Дополнительные диагностические данные")


class SysmonInspector:
    """Диагностический инспектор службы и канала телеметрии Sysmon."""

    CHANNEL_NAME = "Microsoft-Windows-Sysmon/Operational"
    SERVICE_NAMES = ("Sysmon", "Sysmon64", "SysmonDrv")

    def __init__(self, evtlog_module: Optional[Any] = None) -> None:
        """Инициализация инспектора Sysmon.

        Args:
            evtlog_module: Опциональный модуль win32evtlog для мока в тестах.
        """
        self.evtlog = evtlog_module if evtlog_module is not None else win32evtlog

    def check_channel_via_win32evtlog(self) -> bool:
        """Проверяет существование и доступность канала Sysmon через win32evtlog.

        Returns:
            bool: True, если канал существует и доступен для чтения.
        """
        if self.evtlog is None:
            return False

        # Вариант 1: EvtOpenChannelConfig
        if hasattr(self.evtlog, "EvtOpenChannelConfig"):
            try:
                handle = self.evtlog.EvtOpenChannelConfig(None, self.CHANNEL_NAME, 0)
                if handle:
                    if hasattr(self.evtlog, "EvtClose"):
                        self.evtlog.EvtClose(handle)
                    return True
            except Exception as err:
                logger.debug(f"[SysmonInspector] EvtOpenChannelConfig({self.CHANNEL_NAME}) ошибка: {err}")

        # Вариант 2: OpenEventLog / OpenBackupEventLog
        if hasattr(self.evtlog, "OpenEventLog"):
            try:
                handle = self.evtlog.OpenEventLog(None, self.CHANNEL_NAME)
                if handle:
                    if hasattr(self.evtlog, "CloseEventLog"):
                        self.evtlog.CloseEventLog(handle)
                    return True
            except Exception as err:
                logger.debug(f"[SysmonInspector] OpenEventLog({self.CHANNEL_NAME}) ошибка: {err}")

        return False

    def check_service_in_scm(self) -> Dict[str, bool]:
        """Проверяет наличие и запуск службы в Windows Service Control Manager."""
        result = {"installed": False, "running": False}
        if sys.platform != "win32":
            return result

        try:
            for s_name in self.SERVICE_NAMES:
                cmd = ["sc.exe", "query", s_name]
                cp = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding="oem",
                    errors="replace",
                    timeout=3,
                    check=False
                )
                if cp.returncode == 0:
                    result["installed"] = True
                    if "RUNNING" in (cp.stdout or "").upper():
                        result["running"] = True
                        break
        except Exception as sc_err:
            logger.debug(f"[SysmonInspector] sc.exe query ошибка: {sc_err}")

        return result

    def inspect(self) -> SysmonStatusInfo:
        """Выполняет комплексный аудит статуса Sysmon.

        Если служба не обнаружена через SCM, но канал журнала событий активен
        через win32evtlog, статус признается установленным и активным.

        Returns:
            SysmonStatusInfo: Структура с флагами готовности.
        """
        scm_stat = self.check_service_in_scm()
        channel_active = self.check_channel_via_win32evtlog()

        # Если канал событий активен через win32evtlog — Sysmon гарантированно установлен
        is_installed = scm_stat["installed"] or channel_active
        is_running = scm_stat["running"] or channel_active

        if is_running and channel_active:
            status_text = "Активна (Журнал подключен)"
        elif is_installed:
            status_text = "Установлена (Остановлена)"
        else:
            status_text = "Не установлен"

        return SysmonStatusInfo(
            is_installed=is_installed,
            is_running=is_running,
            channel_active=channel_active,
            channel_name=self.CHANNEL_NAME,
            status_text=status_text,
            details={
                "scm_detected": scm_stat["installed"],
                "scm_running": scm_stat["running"],
                "channel_verified": channel_active,
            }
        )

