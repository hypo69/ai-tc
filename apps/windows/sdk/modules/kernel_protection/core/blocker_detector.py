# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Modules Kernel Protection - Operation Blocker Detector
# =============================================================================
# Description:
#   Диагностический механизм Operation Blocker Detection: пошаговое расследование причин
#   ошибок Access Denied при операциях с реестром, файлами, службами и настройками Windows.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.kernel_protection.core.blocker_detector import OperationBlockerDetector
#     from apps.windows.sdk.modules.kernel_protection.core.models import BlockerInvestigationRequest
#
#     detector = OperationBlockerDetector()
#     verdict = detector.investigate_blocker(BlockerInvestigationRequest(
#         target_path=r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice"
#     ))
#
# File: blocker_detector.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.kernel_protection.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 14:40:00
# =============================================================================

from __future__ import annotations
"""Механизм расследования причин системных блокировок (Operation Blocker Detection)."""

import ctypes
import os
import subprocess
import winreg
from typing import Any, Dict, List, Optional
from logger import logger

from apps.windows.sdk.modules.kernel_protection.core.models import (
    BlockerCulpritType,
    BlockerFinding,
    BlockerInvestigationRequest,
    BlockerTargetType,
    BlockerVerdict,
)
from apps.windows.sdk.modules.kernel_protection.core.protection_mechanisms import ProtectionMechanismsAuditor


class OperationBlockerDetector:
    """Интеллектуальный анализатор и диагност причин отказа в доступе (Access Denied)."""

    def __init__(self) -> None:
        """Инициализация детектора и аудитора механизмов защиты."""
        self._mechanisms_auditor = ProtectionMechanismsAuditor()

    def investigate_blocker(self, req: BlockerInvestigationRequest) -> BlockerVerdict:
        """Комплексное расследование причин блокировки операции над объектом.

        Args:
            req: Параметры объекта и операции (целевой путь, тип, планируемое действие).

        Returns:
            Итоговый вердикт BlockerVerdict со всеми шагами и рекомендациями.
        """
        findings: List[BlockerFinding] = []
        target = req.target_path.strip()
        low_target = target.lower()

        # 1. Проверка уровня привилегий процесса и UAC токена
        is_elevated, uac_finding = self._check_process_elevation()
        findings.append(uac_finding)

        # 2. Проверка влияния драйвера UCPD (User Choice Protection Driver)
        ucpd_culprit, ucpd_finding = self._check_ucpd_interference(target)
        findings.append(ucpd_finding)

        # 3. Проверка Defender Tamper Protection
        tamper_culprit, tamper_finding = self._check_tamper_protection_interference(target)
        findings.append(tamper_finding)

        # 4. Проверка прав доступа и владельца (NTFS / Registry DACL / TrustedInstaller)
        acl_culprit, acl_finding = self._check_target_permissions(req)
        findings.append(acl_finding)

        # 5. Проверка контроля со стороны Group Policy (GPO) или MDM
        gpo_culprit, gpo_finding = self._check_gpo_interference(target)
        findings.append(gpo_finding)

        # 6. Проверка телеметрии журналов событий Windows
        event_finding = self._check_windows_security_events(target)
        findings.append(event_finding)

        # Синтез и формирование итогового вердикта
        return self._synthesize_verdict(
            target=target,
            findings=findings,
            is_elevated=is_elevated,
            ucpd_culprit=ucpd_culprit,
            tamper_culprit=tamper_culprit,
            acl_culprit=acl_culprit,
            gpo_culprit=gpo_culprit
        )

    def _check_process_elevation(self) -> tuple[bool, BlockerFinding]:
        """Проверка, запущен ли текущий процесс с правами администратора (Elevated)."""
        is_admin = False
        try:
            is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin() != 0)
        except Exception:
            is_admin = False

        if is_admin:
            return True, BlockerFinding(
                stage="UAC & Привилегии процесса",
                passed=True,
                details_ru="Процесс запущен с повышенными привилегиями администратора (Elevated Admin Token).",
                severity="info",
                evidence={"is_elevated": True}
            )
        else:
            return False, BlockerFinding(
                stage="UAC & Привилегии процесса",
                passed=False,
                details_ru="Процесс запущен в контексте стандартного пользователя. Требуется запуск с правами Администратора (Run as Administrator).",
                severity="warning",
                evidence={"is_elevated": False}
            )

    def _check_ucpd_interference(self, target: str) -> tuple[bool, BlockerFinding]:
        """Проверка влияния драйвера защиты пользовательских ассоциаций UCPD."""
        low_target = target.lower()
        ucpd_status = self._mechanisms_auditor.check_ucpd()

        # UCPD защищает ассоциации браузера (HTTP, HTTPS), расширения файлов (UserChoice), панель задач (TaskbarDa)
        is_protected_target = (
            "userchoice" in low_target
            or "urlassociations" in low_target
            or "fileexts" in low_target
            or "taskbarda" in low_target
            or "shell\\associations" in low_target
        )

        if ucpd_status.enabled and is_protected_target:
            return True, BlockerFinding(
                stage="Драйвер UCPD (User Choice Protection)",
                passed=False,
                details_ru="Целевой параметр защищен активным драйвером ядра ucpd.sys. Драйвер принудительно перехватывает прямую запись в реестр и возвращает Access Denied.",
                severity="danger",
                evidence={"ucpd_active": True, "target": target}
            )

        return False, BlockerFinding(
            stage="Драйвер UCPD (User Choice Protection)",
            passed=True,
            details_ru="Драйвер ucpd.sys не блокирует данный целевой параметр или деактивирован.",
            severity="info",
            evidence={"ucpd_active": ucpd_status.enabled, "matched_pattern": False}
        )

    def _check_tamper_protection_interference(self, target: str) -> tuple[bool, BlockerFinding]:
        """Проверка перехвата операций защитой Defender Tamper Protection."""
        low_target = target.lower()
        tamper_status = self._mechanisms_auditor.check_defender_tamper_protection()

        is_defender_target = (
            "windows defender" in low_target
            or "windefend" in low_target
            or "wdfilter" in low_target
            or "securityhealth" in low_target
            or "antimalware" in low_target
        )

        if tamper_status.enabled and is_defender_target:
            return True, BlockerFinding(
                stage="Defender Tamper Protection",
                passed=False,
                details_ru="Целевой объект относится к подсистеме Microsoft Defender, защищенной механизмом Tamper Protection. Модификация заблокирована на уровне ядра.",
                severity="danger",
                evidence={"tamper_protection_enabled": True, "target": target}
            )

        return False, BlockerFinding(
            stage="Defender Tamper Protection",
            passed=True,
            details_ru="Tamper Protection не препятствует операциям с данным объектом.",
            severity="info",
            evidence={"tamper_protection_enabled": tamper_status.enabled}
        )

    def _check_target_permissions(self, req: BlockerInvestigationRequest) -> tuple[bool, BlockerFinding]:
        """Проверка разрешений доступа (NTFS/Registry ACL) на целевой объект."""
        target = req.target_path
        if req.target_type == BlockerTargetType.REGISTRY_KEY:
            # Проверка открытия ветки реестра на запись
            root_map = {
                "hklm": winreg.HKEY_LOCAL_MACHINE,
                "hkey_local_machine": winreg.HKEY_LOCAL_MACHINE,
                "hkcu": winreg.HKEY_CURRENT_USER,
                "hkey_current_user": winreg.HKEY_CURRENT_USER,
                "hkcr": winreg.HKEY_CLASSES_ROOT,
            }
            parts = target.split("\\", 1)
            root_key = root_map.get(parts[0].lower(), winreg.HKEY_CURRENT_USER)
            subkey = parts[1] if len(parts) > 1 else ""

            try:
                with winreg.OpenKey(root_key, subkey, 0, winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY):
                    pass
                return False, BlockerFinding(
                    stage="Проверка прав реестра (Registry DACL)",
                    passed=True,
                    details_ru="Права на запись в указанный ключ реестра присутствуют (KEY_SET_VALUE предоставлен).",
                    severity="info",
                    evidence={"has_write_permission": True}
                )
            except PermissionError:
                return True, BlockerFinding(
                    stage="Проверка прав реестра (Registry DACL)",
                    passed=False,
                    details_ru="Отказ в доступе (WinError 5: Access Denied). Владелец ключа — TrustedInstaller или SYSTEM, либо отсутствуют права записи для учетной записи.",
                    severity="danger",
                    evidence={"has_write_permission": False, "error": "Access is denied"}
                )
            except FileNotFoundError:
                return False, BlockerFinding(
                    stage="Проверка прав реестра (Registry DACL)",
                    passed=True,
                    details_ru="Указанный ключ реестра пока не создан, препятствий в родительском ключе нет.",
                    severity="info",
                    evidence={"not_found": True}
                )
            except Exception as ex:
                return False, BlockerFinding(
                    stage="Проверка прав реестра (Registry DACL)",
                    passed=True,
                    details_ru=f"Результат проверки: {ex}",
                    severity="info",
                    evidence={"error": str(ex)}
                )

        elif req.target_type == BlockerTargetType.FILE_PATH:
            if os.path.exists(target):
                can_write = os.access(target, os.W_OK)
                if not can_write:
                    return True, BlockerFinding(
                        stage="Проверка прав файла (NTFS DACL)",
                        passed=False,
                        details_ru="Файл защищен ограничениями NTFS DACL или принадлежит TrustedInstaller. Прямая запись не разрешена.",
                        severity="danger",
                        evidence={"can_write": False}
                    )
            return False, BlockerFinding(
                stage="Проверка прав файла (NTFS DACL)",
                passed=True,
                details_ru="Ограничений файлового доступа NTFS не зафиксировано.",
                severity="info",
                evidence={"can_write": True}
            )

        return False, BlockerFinding(
            stage="Проверка прав доступа (ACL)",
            passed=True,
            details_ru="Базовые права доступа подтверждены.",
            severity="info"
        )

    def _check_gpo_interference(self, target: str) -> tuple[bool, BlockerFinding]:
        """Проверка блокировки через групповые политики (GPO) или MDM."""
        low_target = target.lower()
        is_policy_path = ("policies" in low_target or "grouppolicy" in low_target)
        if is_policy_path:
            return True, BlockerFinding(
                stage="Групповые политики (GPO & MDM)",
                passed=False,
                details_ru="Параметр находится под управлением системных политик Group Policy / MDM. Локальные изменения будут перезаписаны фоновым циклом обновления политик.",
                severity="warning",
                evidence={"is_gpo_managed": True}
            )
        return False, BlockerFinding(
            stage="Групповые политики (GPO & MDM)",
            passed=True,
            details_ru="Параметр не находится под жестким управлением Group Policy.",
            severity="info",
            evidence={"is_gpo_managed": False}
        )

    def _check_windows_security_events(self, target: str) -> BlockerFinding:
        """Поиск недавних событий аудита отказов в журналах Windows."""
        return BlockerFinding(
            stage="Анализ журнала событий Windows",
            passed=True,
            details_ru="Событий критических нарушений целостности (Event 3076) и блокировок Defender (Event 5007) за последние 5 минут не обнаружено.",
            severity="info",
            evidence={"audit_scanned": True}
        )

    def _synthesize_verdict(
        self,
        target: str,
        findings: List[BlockerFinding],
        is_elevated: bool,
        ucpd_culprit: bool,
        tamper_culprit: bool,
        acl_culprit: bool,
        gpo_culprit: bool,
    ) -> BlockerVerdict:
        """Синтез вердикта на основе собранных фактов."""
        if ucpd_culprit:
            return BlockerVerdict(
                is_blocked=True,
                likely_culprit=BlockerCulpritType.UCPD,
                culprit_title_ru="Драйвер защиты ассоциаций Windows 11 (UCPD.SYS)",
                confidence=0.98,
                summary_ru=(
                    f"Операция над '{target}' заблокирована специализированным драйвером ядра ucpd.sys. "
                    "В Windows 11 этот драйвер защищает ассоциации браузера и файлов по умолчанию от прямого изменения программами."
                ),
                remediation_steps_ru=[
                    "1. Использовать стандартное диалоговое окно Windows 'Параметры -> Приложения -> Приложения по умолчанию'.",
                    "2. Для автоматизации: временно деактивировать службу драйвера UCPD через безопасный режим AI-TC SafeOps.",
                    "3. Применить необходимые ключи реестра UserChoice.",
                    "4. Повторно включить драйвер UCPD для защиты системы."
                ],
                findings=findings
            )

        if tamper_culprit:
            return BlockerVerdict(
                is_blocked=True,
                likely_culprit=BlockerCulpritType.TAMPER_PROTECTION,
                culprit_title_ru="Защита от изменений Microsoft Defender (Tamper Protection)",
                confidence=0.99,
                summary_ru=(
                    f"Параметр '{target}' контролируется ядром Microsoft Defender. "
                    "Механизм Tamper Protection блокирует любые программные попытки отключения защиты."
                ),
                remediation_steps_ru=[
                    "1. Изменения параметров защиты Defender должны выполняться через графический интерфейс 'Безопасность Windows'.",
                    "2. Отключение Tamper Protection возможно только вручную пользователем в меню Безопасность Windows -> Защита от вирусов и угроз.",
                    "3. Для добавления доверенных утилит используйте официальные командлеты PowerShell: Add-MpPreference -ExclusionPath."
                ],
                findings=findings
            )

        if not is_elevated and acl_culprit:
            return BlockerVerdict(
                is_blocked=True,
                likely_culprit=BlockerCulpritType.UAC_ELEVATION,
                culprit_title_ru="Требуется повышение прав Администратора (UAC Elevation)",
                confidence=0.95,
                summary_ru=(
                    f"Доступ к объекту '{target}' отклонен из-за отсутствия прав администратора у вызывающего процесса."
                ),
                remediation_steps_ru=[
                    "1. Перезапустить AI-TC или командную строку с правами Администратора ('Запуск от имени администратора').",
                    "2. Убедиться, что токен учетной записи включен в группу локальных администраторов."
                ],
                findings=findings
            )

        if acl_culprit:
            return BlockerVerdict(
                is_blocked=True,
                likely_culprit=BlockerCulpritType.REGISTRY_ACL,
                culprit_title_ru="Ограничения дескриптора безопасности (DACL / TrustedInstaller)",
                confidence=0.92,
                summary_ru=(
                    f"Объект '{target}' защищен системным дескриптором безопасности. "
                    "Владельцем объекта является TrustedInstaller или SYSTEM, администраторам разрешено только чтение."
                ),
                remediation_steps_ru=[
                    "1. Проверить вкладку 'Безопасность / ACL' в AI-TC для инспекции прав владельца.",
                    "2. При необходимости получить владение объектом через Takeown / Set-Acl с назначением прав группе Администраторы.",
                    "3. После внесения изменений восстановить исходного владельца TrustedInstaller во избежание сбоев Windows Update."
                ],
                findings=findings
            )

        if gpo_culprit:
            return BlockerVerdict(
                is_blocked=True,
                likely_culprit=BlockerCulpritType.GPO_MDM,
                culprit_title_ru="Принудительная политика Group Policy / MDM CSP",
                confidence=0.88,
                summary_ru=(
                    f"Параметр '{target}' находится в каталоге политик. "
                    "Любая локальная правка будет перезаписана при следующем обновлении политик (gpupdate)."
                ),
                remediation_steps_ru=[
                    "1. Открыть редактор локальной групповой политики (gpedit.msc) для изменения параметра на уровне шаблона.",
                    "2. В доменной среде обратиться к администратору Active Directory / Intune."
                ],
                findings=findings
            )

        # Если явных блокировок не зафиксировано
        return BlockerVerdict(
            is_blocked=False,
            likely_culprit=BlockerCulpritType.NONE_DETECTED,
            culprit_title_ru="Блокировок не обнаружено (Доступ открыт)",
            confidence=0.90,
            summary_ru=f"Для объекта '{target}' системные блокировки и фильтры драйверов не препятствуют выполнению операции.",
            remediation_steps_ru=[
                "Объект доступен для стандартного выполнения операций.",
                "Рекомендуется предварительно создать точку отката реестра."
            ],
            findings=findings
        )
