# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Modules Kernel Protection - TUI / CLI
# =============================================================================
# Description:
#   Консольный интерфейс (CLI/TUI) для автономного агента управления защитой ядра,
#   инвентаризации драйверов и проведения диагностики блокировок (Blocker Detection).
#
# Usage Examples:
#   py -m apps.windows.sdk.modules.kernel_protection.tui summary
#   py -m apps.windows.sdk.modules.kernel_protection.tui investigate "Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice"
#
# File: tui.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.kernel_protection
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-01 14:40:00
# =============================================================================

from __future__ import annotations
"""Консольная утилита управления защитой ядра и драйверами Windows."""

import argparse
import json
import sys
from logger import logger

from apps.windows.sdk.modules.kernel_protection.core import (
    BlockerInvestigationRequest,
    BlockerTargetType,
    DriverInventoryManager,
    KernelSafeOpsManager,
    OperationBlockerDetector,
    ProtectionMechanismsAuditor,
    SafeOpsActionRequest,
)


def print_summary() -> None:
    """Вывод сводного отчета о драйверах и защите ядра."""
    auditor = ProtectionMechanismsAuditor()
    inventory = DriverInventoryManager()

    mechanisms = auditor.audit_all_mechanisms()
    minifilters = inventory.get_active_minifilters()
    sec_drivers = inventory.get_security_and_filter_drivers()

    logger.console("\n=======================================================", text_color="cyan")
    logger.console(" 🛡️ WINDOWS KERNEL PROTECTION & ENFORCEMENT REPORT", text_color="cyan")
    logger.console("=======================================================\n", text_color="cyan")

    logger.console("--- [1. МЕХАНИЗМЫ ЗАЩИТЫ ЯДРА] ---", text_color="yellow")
    for m in mechanisms:
        status_color = "green" if m.enabled else "gray"
        if m.id == "ucpd" and m.enabled:
            status_color = "yellow"
        logger.console(f" • {m.name:45}: [{m.status_label}]", text_color=status_color)

    logger.console("\n--- [2. АКТИВНЫЕ ФАЙЛОВЫЕ МИНИФИЛЬТРЫ (fltmc)] ---", text_color="yellow")
    for f in minifilters:
        logger.console(f" • {f.name:15} | Alt: {f.altitude:8} | {f.altitude_group_ru} ({f.vendor})", text_color="white")

    logger.console(f"\n--- [3. КЛЮЧЕВЫЕ ДРАЙВЕРЫ ЗАЩИТЫ ({len(sec_drivers)})] ---", text_color="yellow")
    for d in sec_drivers[:10]:
        crit_color = "red" if d.criticality == "critical" else "cyan"
        logger.console(f" • {d.name:12}.sys [{d.state:7}] | Критичность: {d.criticality.value:8} | {d.purpose_ru[:50]}", text_color=crit_color)


def run_investigation(target_path: str, target_type: str = "registry_key") -> None:
    """Проведение расследования блокировки операции."""
    detector = OperationBlockerDetector()
    ttype = BlockerTargetType.REGISTRY_KEY
    if target_type == "file_path":
        ttype = BlockerTargetType.FILE_PATH
    elif target_type == "service":
        ttype = BlockerTargetType.SERVICE

    req = BlockerInvestigationRequest(
        target_type=ttype,
        target_path=target_path,
        operation="modify"
    )

    logger.console(f"\n[Operation Blocker Detection] Запуск расследования: {target_path}...", text_color="cyan")
    verdict = detector.investigate_blocker(req)

    v_color = "red" if verdict.is_blocked else "green"
    logger.console(f"\nВЕРДИКТ: {verdict.culprit_title_ru} (Уверенность: {int(verdict.confidence * 100)}%)", text_color=v_color)
    logger.console(f"РЕЗЮМЕ : {verdict.summary_ru}\n", text_color="white")

    logger.console("Шаги расследования:", text_color="yellow")
    for f in verdict.findings:
        icon = "✅" if f.passed else "🛑"
        logger.console(f"  {icon} {f.stage:35}: {f.details_ru}", text_color="gray" if f.passed else "red")

    logger.console("\nРекомендации SafeOps:", text_color="yellow")
    for step in verdict.remediation_steps_ru:
        logger.console(f"  -> {step}", text_color="cyan")


def main() -> None:
    """Главная точка входа TUI/CLI."""
    parser = argparse.ArgumentParser(description="Windows Kernel Protection & Enforcement Agent CLI")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("summary", help="Сводный отчет о механизмах защиты и драйверах")
    subparsers.add_parser("minifilters", help="Список файловых минифильтров fltmc")

    inv_p = subparsers.add_parser("investigate", help="Диагностика причины блокировки (Access Denied)")
    inv_p.add_argument("target_path", help="Путь к ключу реестра, файлу или службе")
    inv_p.add_argument("--type", default="registry_key", choices=["registry_key", "file_path", "service"])

    safe_p = subparsers.add_parser("safe-action", help="Выполнение безопасного действия SafeOps")
    safe_p.add_argument("action", choices=["disable_ucpd", "enable_ucpd"])
    safe_p.add_argument("--confirm", action="store_true", help="Подтверждение риска")

    args = parser.parse_args()

    if args.command == "summary" or not args.command:
        print_summary()
    elif args.command == "minifilters":
        inv = DriverInventoryManager()
        filters = inv.get_active_minifilters()
        for f in filters:
            logger.console(f"{f.name:15} | Alt: {f.altitude:8} | Inst: {f.instances_count} | {f.purpose_ru}")
    elif args.command == "investigate":
        run_investigation(args.target_path, args.type)
    elif args.command == "safe-action":
        mgr = KernelSafeOpsManager()
        comp = "ucpd"
        res = mgr.execute_action(SafeOpsActionRequest(
            action=args.action,
            component_name=comp,
            confirm_risk=args.confirm
        ))
        status_col = "green" if res.success else "red"
        logger.console(f"Результат SafeOps: {res.message}", text_color=status_col)


if __name__ == "__main__":
    main()
