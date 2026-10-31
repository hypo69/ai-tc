# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Commands - Windows Settings Command Executor
# =============================================================================
# Description:
#   Единый исполнитель команд управления системой Windows (Command Executor):
#   валидация параметров, выбор адаптера через SettingsResolver, фиксация снимка
#   до изменения, выполнение, верификация фактического результата и откат (Rollback).
#
# Usage Examples:
#   Python API:
#     from apps.windows.commands.windows_settings import WindowsSettingsExecutor
#
#     executor = WindowsSettingsExecutor()
#     res = executor.execute("TASKBAR.SET_ALIGNMENT", {"alignment": "center"})
#     print(res.success, res.actual)
#
# File: windows_settings.py
# Project: ai-windows-admin
# Package: apps.windows.commands
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 13:00:00
# =============================================================================

from __future__ import annotations
"""Единый диспетчер и исполнитель команд Windows Control Plane."""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from logger import logger
from apps.windows.sdk.display.display_config import DisplayConfigManager
from apps.windows.sdk.display.display_models import DisplayOrientation
from apps.windows.sdk.shell.taskbar_config import TaskbarConfigManager
from apps.windows.sdk.settings.catalog import WINDOWS_SETTINGS
from apps.windows.sdk.settings.resolver import SettingsResolver
from apps.windows.sdk.settings.verification import SettingsVerification


class CommandExecutionRequest(BaseModel):
    """Единый контракт запроса на выполнение системной команды."""
    command: str = Field(..., description="Идентификатор команды (например, MONITOR.ROTATE)")
    params: Dict[str, Any] = Field(default_factory=dict, description="Параметры выполнения команды")


class CommandExecutionResult(BaseModel):
    """Единый структурированный контракт ответа выполнения системной команды."""
    success: bool = Field(..., description="Признак успешного завершения")
    command: str = Field(..., description="Имя выполненной команды")
    requested: Dict[str, Any] = Field(default_factory=dict, description="Запрошенные параметры")
    actual: Dict[str, Any] = Field(default_factory=dict, description="Фактические параметры после выполнения")
    error: Optional[str] = Field(None, description="Текст ошибки при наличии")
    rollback_supported: bool = Field(True, description="Поддерживается ли откат операции")
    previous_state: Optional[Any] = Field(None, description="Предыдущее состояние параметра до применения")


class WindowsSettingsExecutor:
    """Центральный исполнитель команд управления настройками Windows."""

    def __init__(self) -> None:
        """Инициализация исполнителя и вспомогательных адаптеров."""
        self.resolver = SettingsResolver()
        self.verification = SettingsVerification()
        self.display_mgr = DisplayConfigManager()
        self.taskbar_mgr = TaskbarConfigManager()
        # История для поддержки отката: command_id -> previous_state
        self._history: Dict[str, Any] = {}

    def validate(self, command: str, params: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Проверяет валидность команды и её параметров на текущей ОС."""
        resolution = self.resolver.resolve(command)
        if resolution.status == "unsupported":
            return False, f"Команда '{command}' не поддерживается на текущей версии Windows: {resolution.reason}"

        cmd_def = WINDOWS_SETTINGS.get(command)
        if not cmd_def:
            return False, f"Команда '{command}' не зарегистрирована в каталоге"

        allowed_values = cmd_def.get("values", [])

        # Проверка параметров для конкретных команд
        if command == "MONITOR.ROTATE":
            orientation = params.get("orientation")
            if not orientation:
                return False, "Параметр 'orientation' обязателен для команды MONITOR.ROTATE"
            if str(orientation).lower() not in allowed_values:
                return False, f"Недопустимое значение ориентации '{orientation}'. Допустимо: {allowed_values}"

        elif command == "TASKBAR.SET_ALIGNMENT":
            alignment = params.get("alignment")
            if alignment is None:
                return False, "Параметр 'alignment' обязателен для команды TASKBAR.SET_ALIGNMENT"
            val_str = "center" if str(alignment) in ("1", "center") else "left"
            if val_str not in allowed_values:
                return False, f"Недопустимое значение выравнивания '{alignment}'. Допустимо: {allowed_values}"

        elif command == "TASKBAR.SET_POSITION":
            position = params.get("position")
            if not position:
                return False, "Параметр 'position' обязателен для команды TASKBAR.SET_POSITION"
            if str(position).lower() not in allowed_values:
                return False, f"Недопустимое значение позиции '{position}'. Допустимо: {allowed_values}"

        elif command == "TASKBAR.SET_AUTOHIDE":
            if "enabled" not in params and "auto_hide" not in params:
                return False, "Параметр 'enabled' или 'auto_hide' обязателен для TASKBAR.SET_AUTOHIDE"

        return True, None

    def execute(self, command: str, params: Optional[Dict[str, Any]] = None) -> CommandExecutionResult:
        """Выполняет команду по единому контракту: validate -> snapshot -> apply -> verify."""
        p = params or {}
        is_valid, val_err = self.validate(command, p)
        if not is_valid:
            logger.warning(f"[CommandExecutor] Ошибка валидации {command}: {val_err}")
            return CommandExecutionResult(
                success=False,
                command=command,
                requested=p,
                actual={},
                error=val_err,
                rollback_supported=self.verification.supports_rollback(command),
            )

        # 1. Фиксация снимка до изменения
        prev_state = self.verification.get_current_state(command, p)
        self._history[command] = {
            "previous_state": prev_state,
            "params": dict(p),
        }

        # 2. Выполнение изменения через подходящий адаптер
        actual_val = None
        err_msg = None

        try:
            if command == "MONITOR.ROTATE":
                disp_id = p.get("display_id")
                if not disp_id:
                    displays = self.display_mgr.list_displays()
                    disp_id = displays[0].id if displays else r"\\.\DISPLAY1"
                orientation_str = p.get("orientation", "landscape")
                timeout = int(p.get("timeout_seconds", 15))
                auto_rollback = bool(p.get("auto_rollback", True))

                rot_res = self.display_mgr.rotate_display(
                    disp_id,
                    orientation_str,
                    timeout_seconds=timeout,
                    auto_rollback=auto_rollback,
                )
                if rot_res.success:
                    actual_val = {"orientation": rot_res.actual_orientation.value, "display_id": disp_id}
                else:
                    err_msg = rot_res.error or "Сбой смены ориентации"

            elif command == "TASKBAR.SET_ALIGNMENT":
                align_raw = p.get("alignment", "center")
                res = self.taskbar_mgr.set_alignment(align_raw)
                if res.get("success"):
                    actual_val = {"alignment": res.get("alignment")}
                else:
                    err_msg = "Не удалось применить выравнивание значков панели задач"

            elif command == "TASKBAR.SET_POSITION":
                pos_raw = p.get("position", "bottom")
                res = self.taskbar_mgr.set_position(pos_raw)
                if res.get("success"):
                    actual_val = {"position": res.get("position")}
                else:
                    err_msg = res.get("error", "Не удалось изменить положение панели задач")

            elif command == "TASKBAR.SET_AUTOHIDE":
                enabled = bool(p.get("enabled", p.get("auto_hide", False)))
                res = self.taskbar_mgr.set_auto_hide(enabled)
                if res.get("success"):
                    actual_val = {"auto_hide": enabled}
                else:
                    err_msg = "Не удалось изменить статус автоскрытия панели задач"

            else:
                err_msg = f"Обработчик для команды '{command}' не реализован"

        except Exception as exc:
            err_msg = f"Исключение при выполнении команды {command}: {exc}"
            logger.error(f"[CommandExecutor] {err_msg}")

        success = err_msg is None
        return CommandExecutionResult(
            success=success,
            command=command,
            requested=p,
            actual=actual_val or {},
            error=err_msg,
            rollback_supported=self.verification.supports_rollback(command),
            previous_state=prev_state,
        )

    def rollback(self, command: str) -> CommandExecutionResult:
        """Откатывает последнюю выполненную операцию к предыдущему значению."""
        hist = self._history.get(command)
        if not hist:
            return CommandExecutionResult(
                success=False,
                command=command,
                requested={},
                actual={},
                error=f"Нет сохраненного состояния для отката команды '{command}'",
                rollback_supported=True,
            )

        prev_state = hist.get("previous_state")
        prev_params = hist.get("params", {})

        # Формируем параметры отката
        rollback_params = dict(prev_params)
        if command == "MONITOR.ROTATE":
            rollback_params["orientation"] = prev_state
            rollback_params["auto_rollback"] = False
        elif command == "TASKBAR.SET_ALIGNMENT":
            rollback_params["alignment"] = prev_state
        elif command == "TASKBAR.SET_POSITION":
            rollback_params["position"] = prev_state
        elif command == "TASKBAR.SET_AUTOHIDE":
            rollback_params["enabled"] = prev_state

        logger.info(f"[CommandExecutor] Запуск отката {command} к состоянию: {prev_state}")
        res = self.execute(command, rollback_params)
        del self._history[command]
        return res

