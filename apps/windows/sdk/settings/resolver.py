# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Settings SDK - Settings Resolver
# =============================================================================
# Description:
#   Резолвер системных настроек Windows: проверка совместимости параметров
#   с версией и сборкой ОС (Windows 10 vs Windows 11), выбор оптимального
#   бэкенда (Win32, Registry, Shell, PowerShell) и выдача статусов доступности.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.settings.resolver import SettingsResolver
#
#     resolver = SettingsResolver()
#     info = resolver.resolve("TASKBAR.SET_POSITION")
#     print(info["status"])  # "version_dependent"
#
# File: resolver.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.settings
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 13:00:00
# =============================================================================

from __future__ import annotations
"""Резолвер совместимости параметров и выбора реализации для текущей версии Windows."""

import sys
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from apps.windows.sdk.settings.catalog import WINDOWS_SETTINGS, SettingDefinition


class ResolutionResult(BaseModel):
    """Результат проверки совместимости настройки для текущей ОС."""
    command_id: str = Field(..., description="Идентификатор команды")
    status: str = Field(..., description="Статус: supported, version_dependent, unsupported")
    is_supported: bool = Field(..., description="Доступна ли операция на текущей системе")
    recommended_backend: str = Field(..., description="Рекомендуемый механизм выполнения")
    supported_values: List[Any] = Field(default_factory=list, description="Список поддерживаемых значений")
    build_number: int = Field(0, description="Номер сборки Windows")
    is_win11: bool = Field(False, description="Признак Windows 11")
    reason: str = Field("", description="Пояснение совместимости для пользователя")


class SettingsResolver:
    """Резолвер доступности настроек на основе версии ОС и возможностей платформы."""

    def __init__(self) -> None:
        """Инициализация резолвера с определением версии и сборки Windows."""
        try:
            win_ver = sys.getwindowsversion()
            self.build_number = win_ver.build
            self.major = win_ver.major
            self.minor = win_ver.minor
            self.is_win11 = self.build_number >= 22000
        except Exception:
            self.build_number = 22000
            self.major = 10
            self.minor = 0
            self.is_win11 = True

    def resolve(self, command_id: str) -> ResolutionResult:
        """Определяет совместимость и рекомендуемый бэкенд для указанной команды."""
        cmd_meta = WINDOWS_SETTINGS.get(command_id)
        if not cmd_meta:
            return ResolutionResult(
                command_id=command_id,
                status="unsupported",
                is_supported=False,
                recommended_backend="unknown",
                build_number=self.build_number,
                is_win11=self.is_win11,
                reason=f"Команда '{command_id}' не описана в каталоге настроек",
            )

        all_values = list(cmd_meta.get("values", []))
        backend = cmd_meta.get("backend", "shell")

        # 1. Поворот экрана (MONITOR.ROTATE)
        if command_id == "MONITOR.ROTATE":
            return ResolutionResult(
                command_id=command_id,
                status="supported",
                is_supported=True,
                recommended_backend="display_config",
                supported_values=all_values,
                build_number=self.build_number,
                is_win11=self.is_win11,
                reason="Поддерживается через Win32 ChangeDisplaySettingsExW на всех версиях Windows",
            )

        # 2. Выравнивание значков панели задач (TASKBAR.SET_ALIGNMENT)
        if command_id == "TASKBAR.SET_ALIGNMENT":
            if self.is_win11:
                return ResolutionResult(
                    command_id=command_id,
                    status="supported",
                    is_supported=True,
                    recommended_backend="shell",
                    supported_values=["left", "center"],
                    build_number=self.build_number,
                    is_win11=self.is_win11,
                    reason="Поддерживается в Windows 11 через ключ Explorer Advanced TaskbarAl",
                )
            else:
                return ResolutionResult(
                    command_id=command_id,
                    status="unsupported",
                    is_supported=False,
                    recommended_backend="shell",
                    supported_values=["left"],
                    build_number=self.build_number,
                    is_win11=self.is_win11,
                    reason="В Windows 10 значки панели задач всегда зафиксированы по левому краю",
                )

        # 3. Расположение панели задач (TASKBAR.SET_POSITION)
        if command_id == "TASKBAR.SET_POSITION":
            if self.is_win11:
                return ResolutionResult(
                    command_id=command_id,
                    status="version_dependent",
                    is_supported=True,
                    recommended_backend="shell",
                    supported_values=["bottom"],
                    build_number=self.build_number,
                    is_win11=self.is_win11,
                    reason="В Windows 11 (build 22000+) Microsoft зафиксировала панель задач снизу. Изменение положения наверх или вбок частично заблокировано оболочкой Explorer.",
                )
            else:
                return ResolutionResult(
                    command_id=command_id,
                    status="supported",
                    is_supported=True,
                    recommended_backend="shell",
                    supported_values=["bottom", "top", "left", "right"],
                    build_number=self.build_number,
                    is_win11=self.is_win11,
                    reason="В Windows 10 поддерживается полноценное перемещение панели задач ко всем 4 краям экрана через StuckRects3.",
                )

        # 4. Автоскрытие панели задач (TASKBAR.SET_AUTOHIDE)
        if command_id == "TASKBAR.SET_AUTOHIDE":
            return ResolutionResult(
                command_id=command_id,
                status="supported",
                is_supported=True,
                recommended_backend="shell",
                supported_values=[True, False],
                build_number=self.build_number,
                is_win11=self.is_win11,
                reason="Поддерживается через SHAppBarMessage(ABM_SETSTATE) и StuckRects3",
            )

        # 5. Фокус за курсором (WINDOW.FOCUS_TRACKING)
        if command_id == "WINDOW.FOCUS_TRACKING":
            return ResolutionResult(
                command_id=command_id,
                status="supported",
                is_supported=True,
                recommended_backend="win32",
                supported_values=[True, False],
                build_number=self.build_number,
                is_win11=self.is_win11,
                reason="Поддерживается через Win32 SystemParametersInfoW (SPI_SETACTIVEWINDOWTRACKING)",
            )

        # По умолчанию
        return ResolutionResult(
            command_id=command_id,
            status="supported",
            is_supported=True,
            recommended_backend=backend,
            supported_values=all_values,
            build_number=self.build_number,
            is_win11=self.is_win11,
            reason="Стандартный системный параметр",
        )

