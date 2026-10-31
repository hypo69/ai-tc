# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Scripts Cli Commands - Telemetry
# =============================================================================
# Description:
#   Команды управления телеметрией и аудитом оборудования (telemetry).
#
# Usage Examples:
#   Python API:
#     from scripts.cli.commands.telemetry import register_telemetry_parser
#
#     res = register_telemetry_parser()
#
# File: telemetry.py
# Project: ai-windows-admin
# Package: scripts.cli.commands
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 22:22:44
# =============================================================================

from __future__ import annotations
from logger import logger
"""Команды управления телеметрией и аудитом оборудования (telemetry)."""

# -*- coding: utf-8 -*-
# Updated: 2026-10-10 22:22:44
"""Команды управления телеметрией и аудитом оборудования (telemetry)."""
import argparse


def register_telemetry_parser(subparsers: argparse._SubParsersAction) -> None:
    """Регистрация аргументов команды telemetry."""
    telemetry_parser = subparsers.add_parser('telemetry', help='System metrics 1Hz logging, hardware audit, drivers, and history archives')
    telemetry_subparsers = telemetry_parser.add_subparsers(dest='subcommand', help='Subcommands')
    telemetry_start = telemetry_subparsers.add_parser('start', help='Start 1Hz telemetry logging loop')
    telemetry_start.add_argument('--interval', '-i', type=float, default=1.0, help='Logging interval in seconds (default: 1.0)')
    telemetry_start.add_argument('--processes', '-p', type=int, default=20, help='Top processes limit (default: 20)')
    telemetry_subparsers.add_parser('status', help='View telemetry & hardware archives status')
    telemetry_init = telemetry_subparsers.add_parser('init-db', help='Initialize and verify SQLite database telemetry.db')
    telemetry_init.add_argument('--force', action='store_true', help='Force reinitialize structure')
    telemetry_init.add_argument('--db-path', type=str, default=None, help='Custom path to telemetry.db')
    telemetry_history = telemetry_subparsers.add_parser('history', help='View saved hardware archive snapshots')
    telemetry_history.add_argument('--limit', '-n', type=int, default=20, help='Limit snapshots count')
    telemetry_subparsers.add_parser('audit', help='Perform live deep hardware & driver audit with sensors')
    telemetry_subparsers.add_parser('changes', help='View hardware configuration changes timeline (Diff)')
    telemetry_subparsers.add_parser('archive', help='Force capture and archive current hardware state')
    telemetry_reboots = telemetry_subparsers.add_parser('reboots', help='Analyze Windows boot and shutdown causes (Reboot Analyzer)')
    telemetry_reboots.add_argument('--limit', '-n', type=int, default=10, help='Limit reboot sessions count (default: 10)')
    telemetry_reboots.add_argument('--json', action='store_true', help='Output in JSON format')
    telemetry_cleanup = telemetry_subparsers.add_parser('cleanup', help='Delete old telemetry records')
    telemetry_cleanup.add_argument('--days', '-d', type=int, default=7, help='Retention days (default: 7)')



def run_telemetry_command(args: argparse.Namespace) -> int:
    """Управление посекундным логированием системной телеметрии и процессами в SQLite."""
    from apps.windows.telemetry import HardwareHistoryManager, SystemCollector, TelemetryLoggerService
    history_mgr = HardwareHistoryManager()
    collector = SystemCollector()
    sub = args.subcommand
    if sub in ('init-db', 'init_db', 'build-db', 'init'):
        from apps.windows.telemetry.init_db import init_telemetry_database
        res = init_telemetry_database(
            db_path=getattr(args, 'db_path', None),
            force=getattr(args, 'force', False),
        )
        status_icon = '✅' if res['integrity_ok'] else '⚠️'
        logger.console(f"\n{status_icon} База данных телеметрии: {res['db_path']}")
        logger.console(f"   • Существует:     {res['exists']}")
        logger.console(f"   • Вновь создана:  {res['created']}")
        logger.console(f"   • Размер файла:   {res['size_mb']} МБ ({res['size_bytes']} байт)")
        logger.console(f"   • Таблиц в схеме: {res['tables_count']}")
        logger.console(f"   • Целостность:    {res['integrity_message']}\n")
        return 0 if res['integrity_ok'] else 1
    if sub == 'status':
        history_list = history_mgr.get_history(limit=5)
        latest = history_mgr.get_latest_archive()
        logger.console('\n--- СТАТУС ТЕЛЕМЕТРИИ И АРХИВОВ ОБОРУДОВАНИЯ ---')
        logger.console(f'Каталог архивов:        {history_mgr.archive_dir}')
        logger.console(f'Всего архивных записей: {len(history_list)}')
        if latest:
            logger.console(f'Последний архив:        {latest.archive_id} ({latest.timestamp})')
            logger.console(f'Устройств в архиве:     {latest.devices_count}')
            logger.console(f'Сводка:                 {latest.report.summary}')
        else:
            logger.console('Архивные снимки:        Пока не созданы')
        logger.console('------------------------------------------------\n')
        return 0
    if sub in ('history', 'list'):
        limit = getattr(args, 'limit', 20) or 20
        history_list = history_mgr.get_history(limit=limit)
        logger.console(f'\n--- ПОСЛЕДНИЕ {len(history_list)} АРХИВОВ ОБОРУДОВАНИЯ ---')
        logger.console(f"{'#ID АРХИВА':<32} | {'ВРЕМЯ (UTC)':<20} | {'УСТРОЙСТВ':<10} | {'ОШИБОК':<8} | {'ИЗМЕНЕНИЙ':<10}")
        logger.console('-' * 90)
        for h in history_list:
            ts = h.get('timestamp', '')[:19].replace('T', ' ')
            logger.console(f"{h.get('archive_id', ''):<32} | {ts:<20} | {h.get('devices_count', 0):<10} | {h.get('problem_devices_count', 0):<8} | {h.get('changes_count', 0):<10}")
        logger.console('----------------------------------------------------------\n')
        return 0
    if sub == 'audit':
        logger.console('\n[+] Запуск аудита аппаратного обеспечения, драйверов и сенсоров...')
        report = collector.get_hardware_audit()
        logger.console(f'\n--- РЕЗУЛЬТАТЫ АУДИТА ОБОРУДОВАНИЯ ({report.devices_count} устройств) ---')
        logger.console(f'Проблемных PnP: {report.problem_devices_count} | С устаревшими драйверами: {report.outdated_drivers_count}')
        logger.console('-' * 110)
        logger.console(f"{'УСТРОЙСТВО':<35} | {'КЛАСС':<12} | {'ДРАЙВЕР':<15} | {'ВЕРСИЯ':<15} | {'ДАТА / АКТУАЛЬНОСТЬ':<25}")
        logger.console('-' * 110)
        for dev in report.devices[:25]:
            d_name = dev.name[:33]
            cls_name = dev.device_class[:10]
            drv_name = (dev.driver.name if dev.driver else 'N/A')[:13]
            drv_ver = (dev.driver.driver_version if dev.driver else 'N/A')[:13]
            curr = f"{dev.driver.driver_date or ''} ({dev.driver.currency_status})" if dev.driver else 'N/A'
            logger.console(f'{d_name:<35} | {cls_name:<12} | {drv_name:<15} | {drv_ver:<15} | {curr[:25]:<25}')
        if len(report.devices) > 25:
            logger.console(f'... и ещё {len(report.devices) - 25} устройств.')
        logger.console('--------------------------------------------------------------------------------------------------------------\n')
        return 0
    if sub == 'changes':
        changes = history_mgr.get_change_timeline(limit=30)
        logger.console(f'\n--- ТАЙМЛАЙН ИЗМЕНЕНИЙ ОБОРУДОВАНИЯ ({len(changes)} событий) ---')
        if not changes:
            logger.console('Изменений аппаратной конфигурации пока не зафиксировано.')
        for c in changes:
            ts = c.timestamp[:19].replace('T', ' ')
            logger.console(f'[{ts}] [{c.change_type.upper()}] {c.description}')
        logger.console('-----------------------------------------------------------------\n')
        return 0
    if sub == 'archive':
        logger.console('\n[+] Фиксация текущего снимка оборудования в архив...')
        entry = collector.archive_hardware_state(auto_diff=True)
        logger.console(f'[OK] Создан архив: {entry.archive_id} (Устройств: {entry.devices_count}, Изменений: {entry.changes_count})\n')
        return 0
    if sub in ('reboots', 'reboot'):
        from apps.windows.telemetry.reboot_analyzer import WindowsRebootAnalyzer
        import json
        limit = getattr(args, 'limit', 10) or 10
        analyzer = WindowsRebootAnalyzer()
        report = analyzer.collect_reboot_history(limit=limit, persist_to_storage=True)
        if getattr(args, 'json', False):
            logger.console(json.dumps(report.model_dump(), ensure_ascii=False, indent=2))
            return 0
        logger.console('\n=== АНАЛИЗАТОР ПЕРЕЗАГРУЗОК И ВЫКЛЮЧЕНИЙ WINDOWS ===')
        logger.console(f"Хост: {report.hostname} | Текущий запуск: {report.current_boot_time} (Аптайм: {report.current_uptime_human})")
        logger.console(f"Статистика: {report.total_reboots_analyzed} перезапусков | Плановых: {report.planned_count} | Обновлений: {report.update_reboot_count} | Аварийных: {report.unexpected_count} | BSOD: {report.bsod_count}")
        logger.console(f"Индекс надежности: {report.stability_score}%/100%\n")
        logger.console('─' * 70)
        for s in report.sessions:
            logger.console(f"[{s.shutdown_type.value}] Сессия: {s.boot_id}")
            logger.console(f"  Запуск: {s.boot_time} | Предыдущий: {s.previous_boot_time or 'N/A'} | Аптайм сессии: {s.uptime_human or 'N/A'}")
            logger.console(f"  Заключение: {s.conclusion}")
            if s.initiating_process:
                logger.console(f"  Инициатор (1074): {s.initiating_process} (пользователь: {s.initiating_user or 'N/A'})")
            if s.reason_text:
                logger.console(f"  Причина: {s.reason_text} (код: {s.reason_code or 'N/A'})")
            if s.bugcheck_code:
                logger.console(f"  BSOD StopCode: {s.bugcheck_code}")
            if s.windows_update_kb:
                logger.console(f"  Обновление: {s.windows_update_kb}")
            if s.evidence:
                logger.console(f"  Улики: {' | '.join(s.evidence[:3])}")
            logger.console('─' * 70)
        return 0
    if sub == 'start':
        interval = getattr(args, 'interval', 1.0)
        processes = getattr(args, 'processes', 20)
        logger.console(f'\n[+] Запуск сервиса телеметрии с интервалом {interval}с, лимит процессов: {processes}...')
        try:
            service = TelemetryLoggerService(interval_sec=float(interval), top_processes=int(processes))
            service.start()
            logger.console(f"[OK] Телеметрия запущена (PID: {(service._thread.ident if service._thread else 'N/A')})\n")
            return 0
        except Exception as e:
            logger.console(f'[ERROR] Failed to start telemetry: {e}')
            return 1
    if sub == 'cleanup':
        days = getattr(args, 'days', 7)
        logger.console(f'\n[+] Удаление архивов старше {days} дней...')
        try:
            removed = history_mgr.cleanup_old_archives(days=int(days))
            logger.console(f'[OK] Удалено {removed} архивов\n')
            return 0
        except Exception as e:
            logger.console(f'[ERROR] Failed to cleanup archives: {e}')
            return 1
    logger.console(f'Неизвестная подкоманда telemetry: {sub}')
    return 1

