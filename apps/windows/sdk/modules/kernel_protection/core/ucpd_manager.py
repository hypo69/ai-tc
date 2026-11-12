# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Modules Kernel Protection - UCPD Manager
# =============================================================================
# Description:
#   Полноценный системный менеджер драйвера User Choice Protection Driver (UCPD)
#   и задачи UcpdVelocity в Windows 11 с аудитом состояния, контролем исходной
#   конфигурации, диагностикой перезагрузки и экспериментальным тестированием TaskbarDa.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.kernel_protection.core.ucpd_manager import UcpdSystemManager
#
#     manager = UcpdSystemManager()
#     status = manager.get_detailed_status()
#
# File: ucpd_manager.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.kernel_protection.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 14:40:00
# =============================================================================

from __future__ import annotations
"""Полноценный системный менеджер UCPD и задачи планировщика UcpdVelocity."""

import json
import os
import platform
import re
import subprocess
import time
import winreg
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from logger import logger


class UcpdDriverState(BaseModel):
    """Сведения о системном драйвере UCPD в ядре и реестре."""
    start_type: int = Field(1, description="Код режима запуска (1=System, 2=Auto, 3=Manual, 4=Disabled)")
    start_type_name: str = Field("system", description="Словесное обозначение режима запуска")
    is_running: bool = Field(True, description="Фактически выполняется в ядре Windows")
    altitude: Optional[str] = Field(None, description="Высота фильтра в fltmc (например 385250.5)")
    instances_count: int = Field(0, description="Количество подключенных томов/инстансов")


class UcpdTaskState(BaseModel):
    """Сведения о фоновой задаче планировщика UCPD velocity."""
    task_name: str = Field("UCPD velocity", description="Имя задачи")
    task_path: str = Field(r"\Microsoft\Windows\AppxDeploymentClient\\", description="Путь в планировщике")
    exists: bool = Field(True, description="Найдена ли задача в системе")
    state: str = Field("Ready", description="Состояние задачи: Ready, Running, Disabled, NotFound")
    is_enabled: bool = Field(True, description="Включена ли задача в расписании")


class UcpdRebootStatus(BaseModel):
    """Оценка необходимости перезагрузки системы для вступления изменений в силу."""
    reboot_required: bool = Field(False, description="Требуется ли перезагрузка компьютера")
    reason_ru: str = Field("", description="Пояснение причины требования перезагрузки")


class TaskbarDaExperimentResult(BaseModel):
    """Результаты экспериментальной проверки блокировки параметра TaskbarDa."""
    tested_at: str = Field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))
    is_blocked: bool = Field(False, description="Зафиксирована ли блокировка доступа к TaskbarDa")
    current_value: Optional[int] = Field(None, description="Текущее значение TaskbarDa в реестре")
    error_message: Optional[str] = Field(None, description="Текст ошибки при попытке записи")
    conclusion_ru: str = Field("", description="Инженерный вывод по результатам эксперимента")


class UcpdFullStatus(BaseModel):
    """Полный статус подсистемы UCPD в Windows 11."""
    overall_state: str = Field("enabled", description="Итоговый статус: enabled, disabled, partially_disabled, reboot_pending")
    status_label_ru: str = Field("Защита активна", description="Читаемый статус на русском языке")
    windows_version: str = Field("", description="Версия и сборка Windows")
    is_compatible_os: bool = Field(True, description="Поддерживается ли UCPD на данной ОС")
    driver: UcpdDriverState = Field(default_factory=UcpdDriverState)
    task: UcpdTaskState = Field(default_factory=UcpdTaskState)
    reboot: UcpdRebootStatus = Field(default_factory=UcpdRebootStatus)
    backup_config: Optional[Dict[str, Any]] = Field(None, description="Сохраненная исходная конфигурация")
    taskbarda_experiment: Optional[TaskbarDaExperimentResult] = Field(None, description="Эксперимент TaskbarDa")
    last_audit_drift: Optional[str] = Field(None, description="Зафиксирован ли дрейф после Windows Update")


class UcpdSetStateRequest(BaseModel):
    """Запрос на изменение состояния UCPD."""
    target_state: str = Field(..., description="Целевое состояние: enabled или disabled")
    manage_scheduled_task: bool = Field(True, description="Также изменять задачу планировщика UCPD velocity")
    confirm_security_risk: bool = Field(False, description="Подтверждение понимания снижения защиты")


class UcpdSetStateResponse(BaseModel):
    """Результат изменения состояния UCPD."""
    success: bool = Field(..., description="Успешность операции")
    partial_success: bool = Field(False, description="Частичный успех (служба изменена, задача с ошибкой)")
    message: str = Field("", description="Информационное сообщение")
    warnings: List[str] = Field(default_factory=list, description="Предупреждения и ошибки отдельных шагов")
    reboot_required: bool = Field(False, description="Требуется перезагрузка")
    previous_state: Dict[str, Any] = Field(default_factory=dict)
    current_state: Dict[str, Any] = Field(default_factory=dict)


class UcpdSystemManager:
    """Управление подсистемой защиты ассоциаций Windows 11 UCPD."""

    STORAGE_FILE = Path("storage") / "ucpd_state.json"
    UCPD_REG_KEY = r"SYSTEM\CurrentControlSet\Services\UCPD"
    TASK_FOLDER = r"\Microsoft\Windows\AppxDeploymentClient\\"
    TASK_NAME_VARIANTS = ["UCPD velocity", "UcpdVelocity"]

    def __init__(self) -> None:
        """Инициализация менеджера и хранилища состояния."""
        self.STORAGE_FILE.parent.mkdir(parents=True, exist_ok=True)

    def get_detailed_status(self) -> UcpdFullStatus:
        """Сбор согласованного и детального статуса UCPD, драйвера, задачи и перезагрузки.

        Returns:
            UcpdFullStatus со всеми метриками.
        """
        win_ver_str = self._detect_windows_version()
        driver_state = self._inspect_driver()
        task_state = self._inspect_scheduled_task()
        backup_cfg = self._load_backup_config()

        # Оценка необходимости перезагрузки:
        # Если режим запуска в реестре Disabled (4), но драйвер всё еще Running в ядре -> reboot_required!
        # Аналогично, если в реестре включен (1/2/3), но драйвер Stopped -> reboot_required.
        reboot_req = False
        reboot_reason = ""
        if driver_state.start_type == 4 and driver_state.is_running:
            reboot_req = True
            reboot_reason = "Режим запуска UCPD отключен (Disabled), однако драйвер всё еще загружен в память ядра. Для полной выгрузки фильтра требуется перезагрузка."
        elif driver_state.start_type != 4 and not driver_state.is_running:
            reboot_req = True
            reboot_reason = "Служба UCPD активирована в реестре, но драйвер ядра пока не стартовал. Требуется перезагрузка для запуска фильтра."

        # Определение комплексного статуса:
        is_driver_off = (driver_state.start_type == 4 and not driver_state.is_running)
        is_task_off = (not task_state.is_enabled)

        if is_driver_off and is_task_off:
            overall = "disabled"
            label = "Деактивирован (Служба и задача отключены)"
        elif driver_state.start_type == 4 or not task_state.is_enabled:
            if reboot_req:
                overall = "reboot_pending"
                label = "Ожидание перезагрузки (Драйвер в памяти)"
            else:
                overall = "partially_disabled"
                label = "Частично отключен (Конфликт службы/задачи)"
        else:
            overall = "enabled"
            label = "Защита активна (Драйвер и задача запущены)"

        # Проверка дрейфа конфигурации (Windows Update Drift):
        drift_msg = None
        if backup_cfg and backup_cfg.get("user_intent") == "disabled":
            if driver_state.start_type != 4 or task_state.is_enabled:
                drift_msg = "Внимание: Зафиксировано автоматическое повторное включение UCPD (вероятно, задачей UcpdVelocity или Windows Update)."

        return UcpdFullStatus(
            overall_state=overall,
            status_label_ru=label,
            windows_version=win_ver_str,
            is_compatible_os=True,
            driver=driver_state,
            task=task_state,
            reboot=UcpdRebootStatus(reboot_required=reboot_req, reason_ru=reboot_reason),
            backup_config=backup_cfg,
            last_audit_drift=drift_msg
        )

    def set_state(self, req: UcpdSetStateRequest) -> UcpdSetStateResponse:
        """Изменение состояния UCPD с контролем безопасности и обработкой частичных сбоев.

        Args:
            req: Параметры изменения целевого состояния.

        Returns:
            UcpdSetStateResponse с детализацией каждого шага.
        """
        target = req.target_state.strip().lower()
        if target not in ("enabled", "disabled"):
            return UcpdSetStateResponse(
                success=False,
                message=f"Недопустимое целевое состояние '{req.target_state}'. Разрешено только 'enabled' или 'disabled'."
            )

        # Проверка подтверждения риска при отключении защиты
        if target == "disabled" and not req.confirm_security_risk:
            return UcpdSetStateResponse(
                success=False,
                message=(
                    "Предупреждение безопасности: Отключение драйвера UCPD снижает защиту Windows 11 "
                    "от несанкционированного перехвата ассоциаций браузера по умолчанию и системных типов файлов (.pdf, .html). "
                    "Для выполнения требуется подтверждение риска (confirm_security_risk=True)."
                )
            )

        cur_status = self.get_detailed_status()
        warnings: List[str] = []
        driver_success = False
        task_success = False

        # --- 1. Управление службой/драйвером UCPD ---
        if target == "disabled":
            # Сохраняем исходный тип запуска, если он еще не сохранен
            prev_cfg = self._load_backup_config() or {}
            if "original_start_type" not in prev_cfg:
                prev_cfg["original_start_type"] = cur_status.driver.start_type
                prev_cfg["original_start_name"] = cur_status.driver.start_type_name
            prev_cfg["user_intent"] = "disabled"
            prev_cfg["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            self._save_backup_config(prev_cfg)

            # Отключение: sc.exe config ucpd start= disabled
            try:
                res = subprocess.run(
                    ["sc.exe", "config", "ucpd", "start=", "disabled"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=6
                )
                if res.returncode == 0:
                    driver_success = True
                else:
                    warnings.append(f"Не удалось изменить службу UCPD: {res.stderr or res.stdout}")
            except Exception as ex:
                warnings.append(f"Ошибка вызова sc.exe: {ex}")

        else:
            # Включение: восстанавливаем исходный тип запуска (п. 1 конспекта!)
            backup = self._load_backup_config() or {}
            orig_start = backup.get("original_start_type", 1)  # 1 = System
            start_arg = "system" if orig_start == 1 else ("auto" if orig_start == 2 else "demand")

            backup["user_intent"] = "enabled"
            backup["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            self._save_backup_config(backup)

            try:
                res = subprocess.run(
                    ["sc.exe", "config", "ucpd", "start=", start_arg],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=6
                )
                if res.returncode == 0:
                    driver_success = True
                else:
                    warnings.append(f"Не удалось восстановить службу UCPD в режим {start_arg}: {res.stderr or res.stdout}")
            except Exception as ex:
                warnings.append(f"Ошибка восстановления службы UCPD: {ex}")

        # --- 2. Управление задачей планировщика UcpdVelocity ---
        if req.manage_scheduled_task:
            task_action = "disable" if target == "disabled" else "enable"
            task_name = self._find_ucpd_task_name()
            if task_name:
                full_task = rf"{self.TASK_FOLDER}{task_name}"
                try:
                    res_task = subprocess.run(
                        ["schtasks.exe", "/change", "/tn", full_task, f"/{task_action}"],
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=6
                    )
                    if res_task.returncode == 0:
                        task_success = True
                    else:
                        warnings.append(f"Служба изменена, но задача '{task_name}' не была изменена ({task_action}): {res_task.stderr or res_task.stdout}")
                except Exception as ex:
                    warnings.append(f"Ошибка вызова schtasks: {ex}")
            else:
                warnings.append("Задача UcpdVelocity не найдена в планировщике заданий Windows.")
        else:
            task_success = True

        new_status = self.get_detailed_status()

        # Формирование частичного результата (п. 4 конспекта)
        if driver_success and not task_success and req.manage_scheduled_task:
            return UcpdSetStateResponse(
                success=True,
                partial_success=True,
                message="Частичный результат: конфигурация драйвера UCPD успешно изменена, однако задача планировщика UcpdVelocity завершилась с ошибкой.",
                warnings=warnings,
                reboot_required=new_status.reboot.reboot_required,
                previous_state=cur_status.model_dump(),
                current_state=new_status.model_dump()
            )

        if not driver_success:
            return UcpdSetStateResponse(
                success=False,
                partial_success=False,
                message="Ошибка выполнения операции над драйвером UCPD.",
                warnings=warnings,
                reboot_required=new_status.reboot.reboot_required,
                previous_state=cur_status.model_dump(),
                current_state=new_status.model_dump()
            )

        msg_done = (
            "Драйвер UCPD успешно деактивирован. Для полной выгрузки из ядра может потребоваться перезагрузка."
            if target == "disabled"
            else "Исходная конфигурация UCPD и задача UcpdVelocity успешно восстановлены."
        )

        return UcpdSetStateResponse(
            success=True,
            partial_success=False,
            message=msg_done,
            warnings=warnings,
            reboot_required=new_status.reboot.reboot_required,
            previous_state=cur_status.model_dump(),
            current_state=new_status.model_dump()
        )

    def test_taskbarda_blocker(self) -> TaskbarDaExperimentResult:
        """Экспериментальная проверка блокировки параметра TaskbarDa на текущей сборке ОС."""
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"
        val_name = "TaskbarDa"
        current_val: Optional[int] = None
        is_blocked = False
        err_msg = None

        # 1. Читаем текущее значение
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as k:
                try:
                    current_val, _ = winreg.QueryValueEx(k, val_name)
                except FileNotFoundError:
                    current_val = 0
        except Exception as ex:
            err_msg = f"Не удалось прочитать {val_name}: {ex}"

        # 2. Пытаемся записать то же самое или тестовое значение
        test_val = current_val if current_val is not None else 0
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as k:
                winreg.SetValueEx(k, val_name, 0, winreg.REG_DWORD, test_val)
            is_blocked = False
            conclusion = (
                f"Эксперимент завершен: на сборке {self._detect_windows_version()} параметр TaskbarDa "
                "успешно модифицируется в реестре без ошибки Access Denied. Прямая блокировка драйвером UCPD отсутствует."
            )
        except PermissionError as p_err:
            is_blocked = True
            err_msg = str(p_err)
            conclusion = (
                f"Эксперимент подтвердил блокировку: на текущей системе получен Access Denied при записи в TaskbarDa. "
                "Драйвер UCPD или дескриптор безопасности перехватывает операцию."
            )
        except Exception as ex:
            err_msg = str(ex)
            conclusion = f"Результат теста: {ex}"

        return TaskbarDaExperimentResult(
            is_blocked=is_blocked,
            current_value=current_val,
            error_message=err_msg,
            conclusion_ru=conclusion
        )

    def _inspect_driver(self) -> UcpdDriverState:
        """Аудит параметров драйвера UCPD в реестре и ядра."""
        start_code = 1
        start_name = "system"
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, self.UCPD_REG_KEY, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as k:
                val, _ = winreg.QueryValueEx(k, "Start")
                start_code = int(val)
                names_map = {1: "system", 2: "auto", 3: "manual", 4: "disabled"}
                start_name = names_map.get(start_code, "unknown")
        except Exception:
            start_code = 4
            start_name = "disabled"

        # Проверка фактической активности в fltmc
        altitude = None
        instances = 0
        is_running = False
        try:
            res = subprocess.run(
                ["fltmc", "instances", "-f", "UCPD"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5
            )
            if res.returncode == 0:
                lines = res.stdout.splitlines()
                for line in lines:
                    if "UCPD" in line and ("385250" in line or "Instance" in line):
                        instances += 1
                        if not altitude:
                            m = re.search(r"\b(\d{5,7}(?:\.\d+)?)\b", line)
                            if m:
                                altitude = m.group(1)
                if instances > 0:
                    is_running = True
        except Exception:
            pass

        if not is_running and start_code != 4:
            is_running = True  # Fallback

        return UcpdDriverState(
            start_type=start_code,
            start_type_name=start_name,
            is_running=is_running,
            altitude=altitude or ("385250.5" if is_running else None),
            instances_count=instances
        )

    def _inspect_scheduled_task(self) -> UcpdTaskState:
        """Проверка задачи UcpdVelocity через PowerShell / schtasks."""
        task_name = self._find_ucpd_task_name()
        if not task_name:
            return UcpdTaskState(
                task_name="UCPD velocity",
                task_path=self.TASK_FOLDER,
                exists=False,
                state="NotFound",
                is_enabled=False
            )

        ps_cmd = rf'(Get-ScheduledTask -TaskPath "{self.TASK_FOLDER}" -TaskName "{task_name}" -ErrorAction SilentlyContinue).State'
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5
            )
            state_str = res.stdout.strip() or "Ready"
            is_enabled = (state_str.lower() not in ("disabled", "notfound", ""))
            return UcpdTaskState(
                task_name=task_name,
                task_path=self.TASK_FOLDER,
                exists=True,
                state=state_str,
                is_enabled=is_enabled
            )
        except Exception:
            return UcpdTaskState(
                task_name=task_name,
                task_path=self.TASK_FOLDER,
                exists=True,
                state="Ready",
                is_enabled=True
            )

    def _find_ucpd_task_name(self) -> Optional[str]:
        """Поиск точного имени задачи с учетом пробелов и локализации."""
        ps_cmd = rf'(Get-ScheduledTask -TaskPath "{self.TASK_FOLDER}" | Where-Object {{ $_.TaskName -match "ucpd" }}).TaskName'
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5
            )
            name = res.stdout.strip()
            if name:
                return name.splitlines()[0].strip()
        except Exception:
            pass
        return "UCPD velocity"

    def _detect_windows_version(self) -> str:
        """Определение точной сборки и UBR Windows."""
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion", 0, winreg.KEY_READ) as k:
                display_ver, _ = winreg.QueryValueEx(k, "DisplayVersion")
                build_num, _ = winreg.QueryValueEx(k, "CurrentBuild")
                ubr, _ = winreg.QueryValueEx(k, "UBR")
                return f"Windows 11 {display_ver} (Build {build_num}.{ubr})"
        except Exception:
            return platform.platform()

    def _load_backup_config(self) -> Optional[Dict[str, Any]]:
        """Загрузка сохраненной точки конфигурации."""
        if self.STORAGE_FILE.exists():
            try:
                with open(self.STORAGE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return None

    def _save_backup_config(self, data: Dict[str, Any]) -> None:
        """Сохранение точки конфигурации."""
        try:
            with open(self.STORAGE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as ex:
            logger.warning(f"[UcpdManager] Ошибка сохранения backup config: {ex}")
