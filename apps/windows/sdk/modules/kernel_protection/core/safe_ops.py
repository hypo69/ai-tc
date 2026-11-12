# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Modules Kernel Protection - SafeOps Manager
# =============================================================================
# Description:
#   Безопасное управление драйверами и компонентами защиты Windows с оценкой рисков,
#   блокировкой опасных воздействий на ядро и автоматическим резервным копированием состояния.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.kernel_protection.core.safe_ops import KernelSafeOpsManager
#     from apps.windows.sdk.modules.kernel_protection.core.models import SafeOpsActionRequest
#
#     manager = KernelSafeOpsManager()
#     res = manager.execute_action(SafeOpsActionRequest(
#         action="disable_ucpd",
#         component_name="ucpd",
#         confirm_risk=True
#     ))
#
# File: safe_ops.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.kernel_protection.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 14:40:00
# =============================================================================

from __future__ import annotations
"""Безопасное управление драйверами ядра и защита от сбоев системы (SafeOps)."""

import subprocess
import time
import uuid
import winreg
from typing import Any, Dict, Optional
from logger import logger

from apps.windows.sdk.modules.kernel_protection.core.driver_inventory import KNOWN_PROTECTION_DRIVERS
from apps.windows.sdk.modules.kernel_protection.core.models import (
    ComponentCriticality,
    SafeOpsActionRequest,
    SafeOpsActionResult,
)


class KernelSafeOpsManager:
    """Менеджер контролируемых и безопасных операций с драйверами Windows."""

    def __init__(self) -> None:
        """Инициализация менеджера и хранилища точек отката."""
        self._backups: Dict[str, Dict[str, Any]] = {}

    def execute_action(self, req: SafeOpsActionRequest) -> SafeOpsActionResult:
        """Выполнение валидированного безопасного действия над компонентом.

        Args:
            req: Запрос на действие (действие, имя компонента, подтверждение).

        Returns:
            Результат SafeOpsActionResult.
        """
        comp_name = req.component_name.strip().lower()
        action = req.action.strip().lower()

        # 1. Валидация критичности: запрет отключения критических драйверов
        meta = KNOWN_PROTECTION_DRIVERS.get(comp_name)
        if meta:
            if meta.get("criticality") == ComponentCriticality.CRITICAL:
                logger.warning(f"[KernelSafeOps] Попытка модификации критического драйвера ядра: {comp_name}")
                return SafeOpsActionResult(
                    success=False,
                    message=(
                        f"Драйвер '{comp_name}' имеет критический уровень защиты ядра (CRITICAL). "
                        "Его отключение запрещено политикой безопасности AI-TC во избежание сбоя системы (BSOD/Boot Failure)."
                    ),
                    rollback_available=False
                )

            if not meta.get("can_disable", False) and action in ("disable", "stop"):
                return SafeOpsActionResult(
                    success=False,
                    message=f"Компонент '{comp_name}' не поддерживает отключение из-за системных зависимостей.",
                    rollback_available=False
                )

        # 2. Выполнение безопасных сценариев
        if action == "disable_ucpd" or (comp_name == "ucpd" and action in ("disable", "stop")):
            return self._handle_disable_ucpd(req.confirm_risk)
        elif action == "enable_ucpd" or (comp_name == "ucpd" and action in ("enable", "start")):
            return self._handle_enable_ucpd()
        elif action == "restore" and req.component_name in self._backups:
            return self.restore_configuration(req.component_name)
        else:
            return SafeOpsActionResult(
                success=False,
                message=f"Неизвестное или неподдерживаемое действие '{action}' над компонентом '{comp_name}'.",
                rollback_available=False
            )

    def _handle_disable_ucpd(self, confirm_risk: bool) -> SafeOpsActionResult:
        """Безопасная временная деактивация драйвера UCPD для настройки ассоциаций."""
        if not confirm_risk:
            return SafeOpsActionResult(
                success=False,
                message="Требуется подтверждение риска (confirm_risk=True) для модификации службы UCPD.",
                rollback_available=False
            )

        # Сохранение текущей точки отката
        backup_id = f"ucpd_backup_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        prev_start = None
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Services\UCPD", 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
                prev_start, _ = winreg.QueryValueEx(key, "Start")
        except Exception:
            prev_start = 2  # Значение по умолчанию: Auto

        self._backups[backup_id] = {
            "component": "ucpd",
            "previous_start": prev_start,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        # Изменение режима запуска на Disabled (4)
        try:
            res = subprocess.run(
                ["sc.exe", "config", "ucpd", "start=", "disabled"],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=5
            )
            if res.returncode == 0:
                logger.info("[KernelSafeOps] Служба UCPD успешно переведена в режим Disabled.")
                return SafeOpsActionResult(
                    success=True,
                    message="Служба UCPD успешно деактивирована. Теперь доступно изменение ассоциаций браузера и реестра.",
                    rollback_available=True,
                    backup_id=backup_id,
                    details={"previous_state": prev_start, "current_state": "disabled", "backup_id": backup_id}
                )
            else:
                return SafeOpsActionResult(
                    success=False,
                    message=f"Ошибка выполнения sc.exe: {res.stderr or res.stdout}",
                    rollback_available=False
                )
        except Exception as ex:
            logger.error(f"[KernelSafeOps] Исключение при деактивации UCPD: {ex}")
            return SafeOpsActionResult(
                success=False,
                message=f"Сбой выполнения операции: {ex}",
                rollback_available=False
            )

    def _handle_enable_ucpd(self) -> SafeOpsActionResult:
        """Восстановление штатной активности драйвера UCPD."""
        try:
            res = subprocess.run(
                ["sc.exe", "config", "ucpd", "start=", "auto"],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=5
            )
            if res.returncode == 0:
                logger.info("[KernelSafeOps] Служба UCPD переведена в штатный режим запуска (auto).")
                return SafeOpsActionResult(
                    success=True,
                    message="Служба UCPD успешно включена в штатный режим автоматического старта.",
                    rollback_available=False,
                    details={"current_state": "auto"}
                )
            else:
                return SafeOpsActionResult(
                    success=False,
                    message=f"Ошибка включения UCPD: {res.stderr or res.stdout}",
                    rollback_available=False
                )
        except Exception as ex:
            return SafeOpsActionResult(
                success=False,
                message=f"Сбой выполнения операции: {ex}",
                rollback_available=False
            )

    def restore_configuration(self, backup_id: str) -> SafeOpsActionResult:
        """Откат конфигурации по идентификатору точки отката."""
        backup = self._backups.get(backup_id)
        if not backup:
            return SafeOpsActionResult(
                success=False,
                message=f"Точка отката '{backup_id}' не найдена в памяти сессии.",
                rollback_available=False
            )

        if backup.get("component") == "ucpd":
            prev = backup.get("previous_start", 2)
            start_str = "auto" if prev == 2 else "demand"
            try:
                subprocess.run(["sc.exe", "config", "ucpd", "start=", start_str], check=True, timeout=5)
                del self._backups[backup_id]
                return SafeOpsActionResult(
                    success=True,
                    message=f"Конфигурация UCPD успешно восстановлена в исходное состояние (start={start_str}).",
                    rollback_available=False
                )
            except Exception as ex:
                return SafeOpsActionResult(
                    success=False,
                    message=f"Ошибка восстановления конфигурации: {ex}",
                    rollback_available=True,
                    backup_id=backup_id
                )

        return SafeOpsActionResult(
            success=False,
            message="Неподдерживаемый компонент в точке отката.",
            rollback_available=False
        )
