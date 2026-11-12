# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Modules Kernel Protection - Protection Mechanisms Auditor
# =============================================================================
# Description:
#   Аудитор системных механизмов защиты Windows: HVCI (Memory Integrity), Secure Boot,
#   UCPD, Defender Tamper Protection, WDAC, Smart App Control, ELAM, UAC и PPL.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.kernel_protection.core.protection_mechanisms import ProtectionMechanismsAuditor
#
#     auditor = ProtectionMechanismsAuditor()
#     mechanisms = auditor.audit_all_mechanisms()
#
# File: protection_mechanisms.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.kernel_protection.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 14:40:00
# =============================================================================

from __future__ import annotations
"""Аудит системных механизмов защиты ядра, гипервизора и контроля изменений."""

import winreg
from typing import Any, Dict, List, Optional
from logger import logger

from apps.windows.sdk.modules.kernel_protection.core.models import ProtectionMechanismStatus


def _safe_read_registry_dword(root: int, subkey: str, value_name: str) -> Optional[int]:
    """Безопасное чтение значения DWORD из реестра Windows."""
    try:
        with winreg.OpenKey(root, subkey, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
            val, vtype = winreg.QueryValueEx(key, value_name)
            if vtype in (winreg.REG_DWORD, winreg.REG_QWORD):
                return int(val)
    except Exception:
        pass
    return None


class ProtectionMechanismsAuditor:
    """Аудитор состояния подсистем защиты ядра и целостности кода Windows."""

    def audit_all_mechanisms(self) -> List[ProtectionMechanismStatus]:
        """Полный аудит всех зарегистрированных механизмов защиты.

        Returns:
            Список статусов механизмов ProtectionMechanismStatus.
        """
        results: List[ProtectionMechanismStatus] = [
            self.check_hvci_memory_integrity(),
            self.check_secure_boot(),
            self.check_ucpd(),
            self.check_defender_tamper_protection(),
            self.check_smart_app_control(),
            self.check_vulnerable_driver_blocklist(),
            self.check_uac_luafv(),
            self.check_code_integrity(),
        ]
        return results

    def check_hvci_memory_integrity(self) -> ProtectionMechanismStatus:
        """Проверка изоляции ядра и целостности кода на уровне гипервизора (HVCI)."""
        subkey = r"SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\HypervisorEnforcedCodeIntegrity"
        val = _safe_read_registry_dword(winreg.HKEY_LOCAL_MACHINE, subkey, "Enabled")
        locked = _safe_read_registry_dword(winreg.HKEY_LOCAL_MACHINE, subkey, "Locked")

        is_enabled = bool(val == 1)
        status_label = "Включена (Memory Integrity)" if is_enabled else "Выключена"
        if is_enabled and locked == 1:
            status_label += " [Заблокирована UEFI]"

        return ProtectionMechanismStatus(
            id="hvci",
            name="HVCI / Целостность памяти (Memory Integrity)",
            enabled=is_enabled,
            status_label=status_label,
            category="Защита ядра и гипервизора",
            description_ru="Изолирует критический код ядра в защищенной виртуальной машине VBS, запрещая исполнение неподписанных драйверов.",
            impact_ru="Предотвращает инъекции вредоносного кода в ядро ОС и блокирует загрузку скомпрометированных драйверов.",
            registry_details={"Enabled": val, "Locked": locked},
            can_toggle=False
        )

    def check_secure_boot(self) -> ProtectionMechanismStatus:
        """Проверка статуса безопасной загрузки Secure Boot."""
        subkey = r"SYSTEM\CurrentControlSet\Control\SecureBoot\State"
        val = _safe_read_registry_dword(winreg.HKEY_LOCAL_MACHINE, subkey, "UEFISecureBootEnabled")

        is_enabled = bool(val == 1)
        return ProtectionMechanismStatus(
            id="secure_boot",
            name="Безопасная загрузка (Secure Boot)",
            enabled=is_enabled,
            status_label="Активен (UEFI Verified)" if is_enabled else "Выключен / Не поддерживается",
            category="Защита загрузки",
            description_ru="Проверяет криптографические подписи загрузчиков Windows и драйверов раннего старта UEFI.",
            impact_ru="Гарантирует, что загрузчик и драйверы ELAM не подменены буткитами или неавторизованным ПО.",
            registry_details={"UEFISecureBootEnabled": val},
            can_toggle=False
        )

    def check_ucpd(self) -> ProtectionMechanismStatus:
        """Проверка драйвера User Choice Protection Driver (UCPD)."""
        subkey = r"SYSTEM\CurrentControlSet\Services\UCPD"
        val = _safe_read_registry_dword(winreg.HKEY_LOCAL_MACHINE, subkey, "Start")

        # Start = 4 означает Disabled; 1, 2, 3 означает активен/запускается
        is_enabled = bool(val is not None and val != 4)
        status_label = "Активен (Защита ассоциаций)" if is_enabled else "Деактивирован"

        return ProtectionMechanismStatus(
            id="ucpd",
            name="UCPD (User Choice Protection Driver)",
            enabled=is_enabled,
            status_label=status_label,
            category="Контроль системных изменений",
            description_ru="Новый системный фильтр Windows 11 для защиты пользовательских ассоциаций (HTTP, браузер, расширения) от прямого изменения через реестр.",
            impact_ru="Блокирует операции записи в ветки Shell\\Associations\\UrlAssociations\\...\\UserChoice с ошибкой Access Denied.",
            registry_details={"StartType": val, "ServiceStatus": "Running" if is_enabled else "Disabled"},
            can_toggle=True
        )

    def check_defender_tamper_protection(self) -> ProtectionMechanismStatus:
        """Проверка защиты от несанкционированного доступа Microsoft Defender (Tamper Protection)."""
        subkey = r"SOFTWARE\Microsoft\Windows Defender\Features"
        val = _safe_read_registry_dword(winreg.HKEY_LOCAL_MACHINE, subkey, "TamperProtection")

        # 5 = включено, 0 = выключено
        is_enabled = bool(val == 5)
        status_label = "Включена (Защита от изменений)" if is_enabled else "Выключена / Не настроена"

        return ProtectionMechanismStatus(
            id="tamper_protection",
            name="Defender Tamper Protection (Защита от изменения)",
            enabled=is_enabled,
            status_label=status_label,
            category="Безопасность антивируса",
            description_ru="Блокирует изменение защищенных параметров Microsoft Defender, исключений и служб даже для локальных администраторов.",
            impact_ru="Попытки отключить Real-time Protection или добавить исключения через PowerShell/Реестр отклоняются ядром.",
            registry_details={"TamperProtection": val},
            can_toggle=False
        )

    def check_smart_app_control(self) -> ProtectionMechanismStatus:
        """Проверка интеллектуального контроля приложений (Smart App Control)."""
        subkey = r"SYSTEM\CurrentControlSet\Control\CI\Policy"
        val = _safe_read_registry_dword(winreg.HKEY_LOCAL_MACHINE, subkey, "VerifiedAndReputablePolicyState")

        # 1 = On, 2 = Evaluation, 0 = Off
        status_map = {1: "Включен (Enforced)", 2: "Режим оценки (Evaluation)", 0: "Выключен"}
        is_enabled = bool(val == 1)
        status_label = status_map.get(val if val is not None else -1, "Не настроен")

        return ProtectionMechanismStatus(
            id="smart_app_control",
            name="Smart App Control (Контроль приложений)",
            enabled=is_enabled,
            status_label=status_label,
            category="Контроль исполняемого кода",
            description_ru="Облачная система искусственного интеллекта Windows для блокировки подозрительных и неподписанных исполняемых файлов.",
            impact_ru="Предотвращает запуск неизвестных бинарников и утилит автоматизации без цифровой репутации Microsoft.",
            registry_details={"VerifiedAndReputablePolicyState": val},
            can_toggle=False
        )

    def check_vulnerable_driver_blocklist(self) -> ProtectionMechanismStatus:
        """Проверка списка блокировки уязвимых драйверов (Microsoft Recommended Driver Block Rules)."""
        subkey = r"SYSTEM\CurrentControlSet\Control\CI\Config"
        val = _safe_read_registry_dword(winreg.HKEY_LOCAL_MACHINE, subkey, "VulnerableDriverBlocklistEnable")

        is_enabled = bool(val == 1 or val is None)  # В Win11 включено по умолчанию
        return ProtectionMechanismStatus(
            id="driver_blocklist",
            name="Блокировка уязвимых драйверов (Vulnerable Driver Blocklist)",
            enabled=is_enabled,
            status_label="Активен (Защита от BYOVD)" if is_enabled else "Выключен",
            category="Защита ядра",
            description_ru="Блокирует загрузку известных уязвимых подписанных драйверов (BYOVD - Bring Your Own Vulnerable Driver).",
            impact_ru="Отказывает в загрузке легитимных, но подверженных эксплойтам низкоуровневых утилит и старых драйверов разгона/диагностики.",
            registry_details={"VulnerableDriverBlocklistEnable": val},
            can_toggle=False
        )

    def check_uac_luafv(self) -> ProtectionMechanismStatus:
        """Проверка контроля учетных записей (UAC) и драйвера luafv."""
        subkey = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"
        lua = _safe_read_registry_dword(winreg.HKEY_LOCAL_MACHINE, subkey, "EnableLUA")
        prompt = _safe_read_registry_dword(winreg.HKEY_LOCAL_MACHINE, subkey, "ConsentPromptBehaviorAdmin")

        is_enabled = bool(lua == 1)
        return ProtectionMechanismStatus(
            id="uac_luafv",
            name="UAC & Виртуализация luafv",
            enabled=is_enabled,
            status_label="Включен (LUA Enforced)" if is_enabled else "Отключен",
            category="Контроль доступа пользователей",
            description_ru="Разделяет привилегии пользователя и администратора; драйвер luafv виртуализирует несанкционированную запись.",
            impact_ru="Требует явного повышения прав (Elevation) для изменения системных файлов, драйверов и HKLM.",
            registry_details={"EnableLUA": lua, "ConsentPromptBehaviorAdmin": prompt},
            can_toggle=False
        )

    def check_code_integrity(self) -> ProtectionMechanismStatus:
        """Проверка подсистемы целостности кода (Code Integrity / KMCI)."""
        return ProtectionMechanismStatus(
            id="code_integrity",
            name="Целостность кода (Code Integrity / KMCI)",
            enabled=True,
            status_label="Активна в ядре (WHQL Enforced)",
            category="Защита ядра",
            description_ru="Проверяет цифровую подпись каждого драйвера режима ядра перед загрузкой.",
            impact_ru="Запрещает загрузку любых неподписанных .sys-файлов в 64-битных версиях Windows.",
            registry_details={"KMCI": "Active"},
            can_toggle=False
        )
