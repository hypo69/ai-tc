# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry - CLI Controller
# =============================================================================
# Description:
#   Консольный контроллер AITelemetryCtl для мониторинга, управления службой
#   Windows Service, проверки базы данных и выполнения диагностики.
#
# Usage Examples:
#   CLI:
#     AITelemetryCtl.exe status
#     AITelemetryCtl.exe start
#     AITelemetryCtl.exe stop
#     AITelemetryCtl.exe restart
#     AITelemetryCtl.exe diagnose
#     AITelemetryCtl.exe database
#
# File: ctl.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-16 23:58:00
# =============================================================================

from __future__ import annotations
"""Консольная утилита управления и диагностики службы AITelemetry."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_current_dir = Path(__file__).resolve().parent
_project_root = str(_current_dir.parents[2]) if len(_current_dir.parents) >= 3 else str(_current_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

try:
    from logger import logger
except ImportError:
    import logging
    logger = logging.getLogger("AITelemetryCtl")
    logger.console = print  # type: ignore


def get_service_status_scm(service_name: str = 'AITelemetry') -> Dict[str, Any]:
    """Запрашивает состояние службы через Windows SCM (sc.exe).

    Args:
        service_name: Имя службы в диспетчере Windows.

    Returns:
        Dict[str, Any]: Словарь со статусом и деталями службы.
    """
    try:
        res = subprocess.run(
            ['sc.exe', 'query', service_name],
            capture_output=True,
            text=True,
            encoding='oem',
            errors='replace',
            timeout=5,
            check=False
        )
        output = res.stdout or ''
        is_installed = res.returncode == 0
        state = 'UNKNOWN'
        if 'RUNNING' in output:
            state = 'RUNNING'
        elif 'STOPPED' in output:
            state = 'STOPPED'
        elif 'START_PENDING' in output:
            state = 'START_PENDING'
        elif 'STOP_PENDING' in output:
            state = 'STOP_PENDING'
        elif not is_installed:
            state = 'NOT_INSTALLED'

        return {
            'installed': is_installed,
            'state': state,
            'raw_output': output.strip()
        }
    except Exception as ex:
        return {'installed': False, 'state': 'ERROR', 'error': str(ex)}


def cmd_status() -> int:
    """Выводит подробный статус службы и базы данных."""
    logger.console("=" * 60)
    logger.console("       AITelemetry - Статус службы и мониторинга")
    logger.console("=" * 60)

    scm_status = get_service_status_scm('AITelemetry')
    state = scm_status.get('state', 'UNKNOWN')
    state_icon = "🟢" if state == 'RUNNING' else ("🔴" if state == 'STOPPED' else "⚪")
    logger.console(f"Служба Windows (SCM):   {state_icon} {state}")
    logger.console(f"Установлена в системе: {'Да' if scm_status.get('installed') else 'Нет'}")

    try:
        from apps.windows.telemetry.telemetry_config import TelemetryConfigManager
        cfg_mgr = TelemetryConfigManager()
        cfg_path = cfg_mgr.config_path
        logger.console(f"Файл конфигурации:     {cfg_path} (существует: {cfg_path.exists()})")
        logger.console(f"Режим работы:          {cfg_mgr.get_mode()}")
        logger.console(f"Интервал замеров:      {cfg_mgr.get_interval_seconds()} сек")
    except Exception as ex:
        logger.console(f"Конфигурация:          Ошибка чтения ({ex})")

    try:
        from apps.windows.telemetry.sqlite import TelemetryStorage
        storage = TelemetryStorage.get_instance(read_only=True)
        db_path = storage.db_path
        logger.console(f"База данных SQLite:    {db_path} (размер: {db_path.stat().st_size / 1024 / 1024:.2f} МБ)")
        stats = storage.get_storage_stats()
        logger.console(f"Всего снимков (polls): {stats.get('snapshots_count', 0)}")
        logger.console(f"Метрик процессов:      {stats.get('process_metrics_count', 0)}")
        logger.console(f"Событий (events):      {stats.get('events_count', 0)}")
    except Exception as ex:
        logger.console(f"База данных:           Недоступна ({ex})")

    logger.console("=" * 60)
    return 0


def cmd_control(action: str) -> int:
    """Управляет службой через sc.exe / net.exe.

    Args:
        action: Действие ('start', 'stop', 'restart').

    Returns:
        int: Код возврата команды.
    """
    if action == 'start':
        logger.console("Запуск службы AITelemetry...")
        res = subprocess.run(['net.exe', 'start', 'AITelemetry'])
        return res.returncode
    elif action == 'stop':
        logger.console("Остановка службы AITelemetry...")
        res = subprocess.run(['net.exe', 'stop', 'AITelemetry'])
        return res.returncode
    elif action == 'restart':
        logger.console("Перезапуск службы AITelemetry...")
        subprocess.run(['net.exe', 'stop', 'AITelemetry'])
        res = subprocess.run(['net.exe', 'start', 'AITelemetry'])
        return res.returncode
    return 1


def cmd_database() -> int:
    """Выводит детальную статистику таблиц SQLite."""
    try:
        from apps.windows.telemetry.sqlite import TelemetryStorage
        storage = TelemetryStorage.get_instance(read_only=True)
        stats = storage.get_storage_stats()
        logger.console(json.dumps(stats, indent=2, ensure_ascii=False))
        return 0
    except Exception as ex:
        logger.console(f"Ошибка чтения базы данных: {ex}")
        return 1


def cmd_diagnose() -> int:
    """Выполняет экспресс-диагностику системных метрик."""
    logger.console("Выполнение глубокой диагностики системы...")
    try:
        from apps.windows.telemetry.collector import SystemCollector
        collector = SystemCollector()
        snapshot = collector.collect_snapshot(top_processes_limit=10)
        logger.console(f"CPU: {snapshot.cpu.usage_percent:.1f}%")
        logger.console(f"Память: {snapshot.memory.percent_used:.1f}% (Свободно: {snapshot.memory.available_mb / 1024:.2f} ГБ)")
        logger.console(f"Количество процессов: {len(snapshot.processes)}")
        logger.console("Диагностика успешно выполнена.")
        return 0
    except Exception as ex:
        logger.console(f"Ошибка при диагностике: {ex}")
        return 1


def cmd_security(args: argparse.Namespace) -> int:
    """Обработчик группы команд ait security."""
    from apps.windows.telemetry.security_collector import WindowsSecurityCollector
    collector = WindowsSecurityCollector()
    action = getattr(args, 'sec_action', 'status')

    if action == 'status':
        status = collector.check_access_and_audit()
        logger.console("=" * 60)
        logger.console("       AITelemetry - Windows Security Event Subsystem")
        logger.console("=" * 60)
        acc_str = "🟢 Доступен" if status.accessible else f"🔴 Недоступен ({status.error})"
        logger.console(f"Журнал Security:       {acc_str}")
        logger.console(f"Всего событий в журнале ОС: {status.record_count:,}")
        logger.console(f"Событий в telemetry.db:     {status.total_ingested_events:,}")
        logger.console(f"Последний EventRecordID:    {status.last_record_id:,}")
        cmd_audit_str = "🟢 Включен" if status.command_line_audit_enabled else "⚪ Отключен (ProcessCreationIncludeCmdLine_Enabled)"
        logger.console(f"Аудит командной строки 4688: {cmd_audit_str}")
        logger.console("=" * 60)
        return 0

    elif action == 'tail':
        limit = getattr(args, 'limit', 20) or 20
        eid = getattr(args, 'event_id', None)
        search = getattr(args, 'search', '') or ''
        events = collector.get_live_tail(limit=limit, event_id=eid, search=search)
        logger.console(f"\n[+] Последние {len(events)} событий Security (Live Tail):")
        for ev in reversed(events):
            logger.console(f"  [{ev.timestamp}] Event {ev.event_id:<4} | {ev.message}")
        return 0

    elif action == 'search':
        eid = int(args.target) if str(args.target).isdigit() else None
        limit = getattr(args, 'limit', 50) or 50
        events = collector.storage.get_security_events(event_id=eid, limit=limit)
        logger.console(f"\n[+] Найдено {len(events)} событий для Event ID {eid}:")
        for ev in events:
            logger.console(f"  [{ev.get('timestamp')}] ID {ev.get('event_id')} | {ev.get('message')}")
        return 0

    elif action == 'user':
        username = args.target
        limit = getattr(args, 'limit', 50) or 50
        events = collector.storage.get_security_events(user=username, limit=limit)
        logger.console(f"\n[+] События безопасности для пользователя '{username}' ({len(events)} записей):")
        for ev in events:
            logger.console(f"  [{ev.get('timestamp')}] Event {ev.get('event_id')} | {ev.get('message')}")
        return 0

    elif action == 'process':
        pname = args.target
        limit = getattr(args, 'limit', 50) or 50
        events = collector.storage.get_security_process_creations(process_name=pname, limit=limit)
        logger.console(f"\n[+] Запуски процесса '{pname}' ({len(events)} записей):")
        for ev in events:
            logger.console(f"  [{ev.get('timestamp')}] PID: {ev.get('process_id')} | User: {ev.get('subject_user')} | {ev.get('command_line') or ev.get('process_name')}")
        return 0

    elif action == 'failed-logons':
        hours = getattr(args, 'hours', 24) or 24
        events = collector.storage.get_security_failed_logons(hours=hours)
        logger.console(f"\n[+] Неудачные попытки входа за последние {hours} ч ({len(events)} записей):")
        for ev in events:
            logger.console(f"  [{ev.get('timestamp')}] User: {ev.get('target_user')} | IP: {ev.get('source_ip')} | {ev.get('message')}")
        return 0

    elif action == 'collect':
        batch_size = getattr(args, 'batch', 500) or 500
        max_records = getattr(args, 'max', 5000) or 5000
        save_raw = getattr(args, 'raw', False)
        logger.console(f"Запуск инкрементального сбора Security... (batch={batch_size}, max={max_records})")
        report = collector.collect_incremental(batch_size=batch_size, max_records=max_records, save_raw=save_raw)
        logger.console(f"[+] Сбор завершен. Сохранено {report.total_events_ingested} событий. Последний RecordID: {report.last_record_id}")
        if report.events_by_id:
            logger.console("    Распределение по типам событий:")
            for eid, count in sorted(report.events_by_id.items(), key=lambda x: x[1], reverse=True)[:8]:
                logger.console(f"      Event {eid:<4}: {count} событий")
        return 0

    elif action == 'correlate':
        pid = getattr(args, 'pid', None)
        user = getattr(args, 'user', None)
        corrs = collector.correlate_security_with_telemetry(pid=pid, user=user)
        logger.console(f"\n[+] Корреляция событий безопасности с телеметрией ({len(corrs)} цепочек):")
        for c in corrs[:20]:
            notes_str = "; ".join(c.notes) if c.notes else "нормальная активность"
            logger.console(f"  * [{c.timestamp}] {c.event_type} | {c.user} -> {c.process_name} (PID {c.pid}) | {notes_str}")
        return 0

    return 0


def cmd_logs(args: argparse.Namespace) -> int:
    """Обрабатывает подкоманды каталога журналов событий Windows."""
    from apps.windows.telemetry.catalog.event_catalog import WindowsEventCatalogEngine
    engine = WindowsEventCatalogEngine()
    action = getattr(args, 'logs_action', None) or 'domains'

    if action == 'domains':
        summary = engine.get_domains_summary()
        logger.console("\n" + "=" * 65)
        logger.console("     7 ДОМЕНОВ ТЕЛЕМЕТРИИ WINDOWS EVENT LOGS")
        logger.console("=" * 65)
        logger.console(f"Всего провайдеров в каталоге: {summary.get('total_registered_providers')}")
        logger.console(f"Служба Sysmon:                {'🟢 Активна' if summary.get('sysmon_installed') else '⚪ Не обнаружена'}\n")
        for dom in summary.get('domains', []):
            logger.console(f"  * {dom.get('title')} [{dom.get('status')}]")
            logger.console(f"    Каналов: {dom.get('channels_count')} | Записей: {dom.get('total_records'):,} | ID: {dom.get('key_events')}")
            logger.console(f"    {dom.get('description')}\n")
        return 0

    elif action == 'catalog':
        catalog = engine.get_full_catalog()
        logger.console("\n" + "=" * 65)
        logger.console(f"   КАТАЛОГ ПРОВАЙДЕРОВ WINDOWS EVENT LOG ({len(catalog)} источников)")
        logger.console("=" * 65)
        for entry in catalog:
            logger.console(f"  [{entry.domain.value}] {entry.provider} -> {entry.channel}")
            logger.console(f"    Объем: {entry.volume_rating:<7} | Записей: {entry.record_count:<8,} | ID: {list(entry.key_events.keys())}")
            logger.console(f"    {entry.description}\n")
        return 0

    elif action == 'provenance':
        proc = getattr(args, 'process', None)
        pid = getattr(args, 'pid', None)
        graph = engine.reconstruct_process_provenance(process_name=proc, pid=pid)
        logger.console("\n" + "=" * 65)
        logger.console("   ДЕРЕВО ПРОИСХОЖДЕНИЯ ПРОЦЕССОВ (PROCESS PROVENANCE)")
        logger.console("=" * 65)
        logger.console(f"Узлов: {graph.get('total_nodes')}, Связей: {graph.get('total_links')}\n")
        for node in graph.get('nodes', []):
            logger.console(f"  * [{node.get('type')}] {node.get('name')} (PID {node.get('pid')}) | User: {node.get('user')}")
            if node.get('command_line'):
                logger.console(f"      CMD: {node.get('command_line')}")
        for link in graph.get('links', []):
            logger.console(f"    -> {link.get('source')} ===[{link.get('relationship')}]===> {link.get('target')}")
        return 0

    elif action == 'lifecycle':
        hours = getattr(args, 'hours', 72) or 72
        timeline = engine.reconstruct_power_lifecycle(hours=hours)
        logger.console("\n" + "=" * 65)
        logger.console(f"   ЖИЗНЕННЫЙ ЦИКЛ ПИТАНИЯ ОС ЗА ПОСЛЕДНИЕ {hours} Ч ({len(timeline)} событий)")
        logger.console("=" * 65)
        for item in timeline:
            logger.console(f"  {item.get('icon')} [{item.get('timestamp')}] {item.get('phase'):<18} | Event {item.get('event_id')} ({item.get('provider')}) | {item.get('message')}")
        return 0

    elif action == 'sysmon':
        status = engine.check_sysmon_status()
        logger.console("\n" + "=" * 65)
        logger.console("   СТАТУС И ВОЗМОЖНОСТИ SYSMON OBSERVABILITY LAYER")
        logger.console("=" * 65)
        logger.console(f"Установлен:   {'🟢 Да' if status.get('installed') else '⚪ Нет'}")
        logger.console(f"Канал логов:  {status.get('channel_name')}")
        logger.console(f"Записей:      {status.get('record_count'):,}")
        logger.console(f"Возможности:  {', '.join(status.get('capabilities', [])) or 'N/A'}")
        logger.console(f"Рекомендации: {status.get('recommended_config')}")
        return 0

    return 0


def cmd_mode(args: Any) -> int:
    """Управление режимами телеметрии: стриминг, аудит или оба процесса."""
    from apps.windows.telemetry.telemetry_config import TelemetryConfigManager
    cfg_mgr = TelemetryConfigManager()

    target_mode = getattr(args, 'mode_name', None)
    if not target_mode:
        logger.console("=" * 65)
        logger.console("       AITelemetry - Режимы работы телеметрии")
        logger.console("=" * 65)
        logger.console(f"Текущий режим:        {cfg_mgr.get_telemetry_mode()}")
        logger.console(f"Стриминг метрик:      {'🟢 Включен' if cfg_mgr.is_streaming_enabled() else '⚪ Отключен'}")
        logger.console(f"Аудит системы:        {'🟢 Включен' if cfg_mgr.is_audit_enabled() else '⚪ Отключен'}")
        logger.console(f"Целевой PID аудита:   {cfg_mgr.get_audit_target_pid() or 'Все процессы'}")
        logger.console(f"Интервал аудита:      {cfg_mgr.get_audit_interval_sec()}с")
        logger.console(f"Интервал стриминга:   {cfg_mgr.get_interval_seconds()}с")
        logger.console("=" * 65)
        return 0

    mode_clean = str(target_mode).lower().strip()
    pid = getattr(args, 'pid', None)
    interval = getattr(args, 'interval', None)

    if mode_clean in ('both', 'all', 'streaming_and_audit'):
        cfg_mgr.activate_both_mode(pid=pid, interval_sec=interval)
        logger.console("✅ Активированы оба процесса: Стриминг и Аудит")
    elif mode_clean in ('audit', 'process_audit'):
        cfg_mgr.activate_audit_mode(pid=pid, interval_sec=interval)
        cfg_mgr.deactivate_streaming_mode()
        logger.console(f"✅ Режим изменен на 'audit': Аудит активен (PID={pid or 'Все'}), стриминг отключен")
    elif mode_clean in ('live_stream', 'streaming', 'live'):
        cfg_mgr.activate_streaming_mode(interval_sec=interval)
        logger.console("✅ Режим изменен на стриминг (Аудит также продолжает работу на старте и в фоне)")
    elif mode_clean in ('stop_streaming', 'no_streaming'):
        cfg_mgr.deactivate_streaming_mode()
        logger.console("✅ Стриминг отключен отдельно от аудита. Аудит продолжает работу.")
    else:
        logger.console(f"❌ Неизвестный режим: {target_mode}. Доступны: both, live_stream, streaming, audit, stop_streaming")
        return 1

    return 0


def cmd_purge_live_stream() -> int:
    """Очищает все таблицы стримингового режима live stream и выполняет сжатие БД."""
    from apps.windows.telemetry.sqlite import TelemetryStorage
    logger.console("🧹 Запуск очистки таблиц режима live stream...")
    storage = TelemetryStorage.get_instance(read_only=False)
    purged = storage.purge_live_stream_tables(vacuum=True)
    total_purged = sum(purged.values())
    logger.console(f"✅ Очистка завершена: удалено {total_purged} записей из {len(purged)} таблиц.")
    for tbl, count in sorted(purged.items()):
        logger.console(f"  * {tbl:<30}: {count} строк")
    return 0


def cmd_audit(pid: int) -> int:
    """Выполняет глубокий аудит процесса по PID через Windows SDK и выводит сводку."""
    from apps.windows.sdk.modules.process_manager import ProcessAuditor
    auditor = ProcessAuditor()
    sample = auditor.audit_process(pid=pid)

    if not sample:
        logger.console(f"❌ Процесс с PID {pid} не найден или завершился.")
        return 1

    logger.console("=" * 65)
    logger.console(f"       Глубокий аудит процесса PID {sample.pid} ({sample.name})")
    logger.console("=" * 65)
    logger.console(f"Сессия (Instance ID): {sample.instance_id}")
    logger.console(f"Статус:               {sample.status} (Жив: {'Да' if sample.is_alive else 'Нет'})")
    logger.console(f"Время работы (Uptime):{sample.uptime_sec} сек")
    logger.console(f"Исполняемый файл:     {sample.executable or 'N/A'}")
    logger.console(f"Пользователь:         {sample.username or 'N/A'}")
    logger.console(f"Родительский процесс: {sample.parent_name or 'N/A'} (PPID: {sample.ppid})")
    logger.console(f"Тип инициатора:       {sample.initiator_type}")
    logger.console(f"Дескрипторов (handles):{sample.num_handles}")
    logger.console("-" * 65)
    logger.console(" 🔲 CPU (Процессор):")
    logger.console(f"   - Загрузка CPU:     {sample.cpu.cpu_percent}%")
    logger.console(f"   - Время User CPU:   {sample.cpu.user_time_sec} сек")
    logger.console(f"   - Время Kernel CPU: {sample.cpu.kernel_time_sec} сек")
    logger.console(f"   - Всего времени CPU:{sample.cpu.total_cpu_time_sec} сек")
    logger.console(f"   - Потоков:          {sample.cpu.num_threads}")
    logger.console(f"   - Переключений:     {sample.cpu.total_context_switches} (добровольных: {sample.cpu.context_switches_voluntary}, вынужденных: {sample.cpu.context_switches_involuntary})")
    if sample.cpu.cpu_cycles:
        logger.console(f"   - Тактов (cycles):  {sample.cpu.cpu_cycles:,}")
    logger.console("-" * 65)
    logger.console(" 💾 RAM и виртуальная память:")
    logger.console(f"   - Working Set (физ):{sample.memory.working_set_mb} МБ (пик: {sample.memory.peak_working_set_mb} МБ)")
    logger.console(f"   - Private Bytes:    {sample.memory.private_mb} МБ")
    logger.console(f"   - Commit Size:      {sample.memory.commit_size_mb} МБ (пик: {sample.memory.peak_commit_size_mb} МБ)")
    logger.console(f"   - Page Faults:      {sample.memory.page_faults:,}")
    logger.console("-" * 65)
    logger.console(" 💽 Дисковый и файловый ввод-вывод (I/O):")
    logger.console(f"   - Операции:         Чтение: {sample.io.read_operations:,} | Запись: {sample.io.write_operations:,} | Прочие: {sample.io.other_operations:,}")
    logger.console(f"   - Байты:            Чтение: {sample.io.read_bytes / (1024*1024):.2f} МБ | Запись: {sample.io.write_bytes / (1024*1024):.2f} МБ")
    logger.console(f"   - Открытых файлов:  {sample.io.open_files_count}")
    if sample.io.open_files:
        for fpath in sample.io.open_files[:5]:
            logger.console(f"      * {fpath}")
    logger.console("-" * 65)
    logger.console(" 🌐 Сеть (IP Helper API):")
    logger.console(f"   - Соединений всего: {sample.network.total_connections_count} (TCP: {sample.network.tcp_connections_count}, UDP: {sample.network.udp_sockets_count})")
    logger.console(f"   - Установлено TCP:  {sample.network.established_count} | Слушает: {sample.network.listening_count}")
    if sample.network.connections:
        for conn in sample.network.connections[:5]:
            logger.console(f"      * {conn.get('protocol')} {conn.get('local_address')}:{conn.get('local_port')} -> {conn.get('remote_address')}:{conn.get('remote_port')} [{conn.get('state')}]")
    logger.console("=" * 65)
    return 0


def cmd_lifecycle(args: argparse.Namespace) -> int:
    """Выводит журнал сессий процессов с фильтрацией по имени приложения, пользователю и статусу."""
    from apps.windows.telemetry.sqlite import TelemetryStorage
    storage = TelemetryStorage.get_instance(read_only=True)
    sessions = storage.get_process_lifecycle_sessions(
        app_name=args.app,
        username=args.user,
        parent_name=args.parent,
        is_alive=True if args.alive else (False if args.dead else None),
        limit=args.limit,
    )

    logger.console("=" * 75)
    logger.console(f"   Жизненный цикл процессов (найдено {len(sessions)} сессий)")
    logger.console("=" * 75)
    if not sessions:
        logger.console("Нет зарегистрированных сессий с указанными фильтрами.")
        return 0

    for s in sessions:
        status_icon = "🟢" if s.get('is_alive') else "⚫"
        inst = s.get('instance_id')
        name = s.get('name')
        pid = s.get('pid')
        ppid = s.get('ppid')
        parent = s.get('parent_name') or 'N/A'
        user = s.get('username') or 'N/A'
        uptime = s.get('lifetime_sec', 0.0)
        cpu = s.get('cpu_time_total_sec', 0.0)
        ws_mb = s.get('peak_working_set_mb', 0.0)
        read_mb = round(int(s.get('io_read_bytes') or 0) / (1024 * 1024), 2)
        write_mb = round(int(s.get('io_write_bytes') or 0) / (1024 * 1024), 2)

        logger.console(f"{status_icon} [{inst}] {name} (PID: {pid}, PPID: {ppid})")
        logger.console(f"   Пользователь: {user} | Родитель: {parent} ({s.get('initiator_type')})")
        logger.console(f"   Старт: {s.get('created_at')} | Время жизни: {uptime}с | CPU: {cpu}с | RAM: {ws_mb} МБ | I/O: {read_mb} МБ чт / {write_mb} МБ зап")
    logger.console("=" * 75)
    return 0


def cmd_app_summary(args: argparse.Namespace) -> int:
    """Выводит сводный отчет по приложению или пользователю."""
    from apps.windows.telemetry.sqlite import TelemetryStorage
    storage = TelemetryStorage.get_instance(read_only=True)
    rep = storage.get_app_summary_report(app_name=args.app, username=args.user)

    target_title = args.app or args.user or "Все приложения"
    logger.console("=" * 65)
    logger.console(f"       Сводный отчет по активности: {target_title}")
    logger.console("=" * 65)
    logger.console(f"Всего запусков:         {rep.get('total_launches', 0)}")
    logger.console(f"Активно сейчас:         {rep.get('active_now', 0)}")
    logger.console(f"Суммарное время работы: {rep.get('total_lifetime_sec', 0.0)} сек")
    logger.console(f"Суммарное время CPU:    {rep.get('total_cpu_time_sec', 0.0)} сек")
    logger.console(f"Пиковая память (RAM):   {rep.get('peak_memory_mb', 0.0)} МБ")
    logger.console(f"Суммарный ввод/вывод:   Чтение: {rep.get('total_io_read_mb', 0.0)} МБ | Запись: {rep.get('total_io_write_mb', 0.0)} МБ")
    logger.console("-" * 65)
    logger.console(" 👥 Пользователи, запускавшие приложение:")
    for user, cnt in rep.get('users', {}).items():
        logger.console(f"   - {user}: {cnt} запуск(ов)")
    logger.console("-" * 65)
    logger.console(" 🚀 Инициаторы (родительские процессы):")
    for init_p, cnt in rep.get('initiators', {}).items():
        logger.console(f"   - {init_p}: {cnt} запуск(ов)")
    logger.console("=" * 65)
    return 0


def cmd_incident(args: argparse.Namespace) -> int:
    """Восстанавливает и выводит хронологическую цепочку событий инцидента процесса."""
    from apps.windows.telemetry.sqlite import TelemetryStorage
    storage = TelemetryStorage.get_instance(read_only=True)
    timeline = storage.get_process_incident_timeline(pid=args.pid, limit=args.limit)

    if not timeline:
        logger.console(f"❌ Хроника инцидента для процесса PID {args.pid} не найдена (нет замеров аудита).")
        return 1

    pname = timeline.get("process_name", "Unknown")
    inst = timeline.get("instance_id", "N/A")
    initiator = timeline.get("parent_name") or timeline.get("initiator_type", "unknown")
    user = timeline.get("username", "N/A")

    logger.console("=" * 80)
    logger.console(f"       Сквозная хроника инцидента: {pname} (PID: {timeline.get('pid')})")
    logger.console("=" * 80)
    logger.console(f"Сессия:       {inst}")
    logger.console(f"Инициатор:    {initiator} ({timeline.get('initiator_type')}) | Пользователь: {user}")
    logger.console(f"Пиковый CPU:  {timeline.get('max_cpu_percent')}% | Пиковая память: {timeline.get('peak_memory_mb')} МБ | Суммарный I/O: {timeline.get('total_io_mb')} МБ")
    logger.console("-" * 80)
    logger.console(f"{'Время':<10} {'Ресурс':<10} {'Уровень':<10} {'Событие / Описание'}")
    logger.console("-" * 80)

    events = timeline.get("events", [])
    for ev in events:
        sev_icon = "🔴" if ev.get("severity") == "CRITICAL" else ("🟡" if ev.get("severity") == "WARNING" else "🔵")
        logger.console(f"{ev.get('timestamp', ''):<10} {ev.get('resource', ''):<10} {sev_icon} {ev.get('severity', ''):<7} {ev.get('title', '')}")

    touched_files = timeline.get("touched_files", [])
    if touched_files:
        logger.console("-" * 80)
        logger.console(" 💽 Задействованные пути файлов:")
        for f in touched_files[:5]:
            logger.console(f"   * {f}")

    hosts = timeline.get("active_network_hosts", [])
    if hosts:
        logger.console("-" * 80)
        logger.console(" 🌐 Удаленные сетевые подключения:")
        for h in hosts[:5]:
            logger.console(f"   * {h}")

    logger.console("=" * 80)
    return 0



def cmd_live_stream_control(args: argparse.Namespace) -> int:
    """Управление режимом live stream по запросу и просмотр профилей ресурсопотребления."""
    from apps.windows.telemetry.service import TelemetryLoggerService
    from apps.windows.telemetry.sqlite import TelemetryStorage

    action = getattr(args, 'ls_action', 'status')
    service = TelemetryLoggerService.get_instance()
    storage = TelemetryStorage.get_instance()

    if action == 'start':
        sess_id = service.start_live_stream(duration_seconds=args.duration)
        logger.console("=" * 65)
        logger.console(f"🚀 Режим Live Stream активирован по запросу")
        logger.console(f"   ID сессии: {sess_id}")
        if args.duration:
            logger.console(f"   Таймаут:   {args.duration} сек (автоматическая остановка)")
        else:
            logger.console("   Режим:     Непрерывный (до команды stop)")
        logger.console("=" * 65)
        return 0

    elif action == 'stop':
        logger.console("=" * 65)
        logger.console("🛑 Остановка Live Stream и финализация отчета ресурсопотребления...")
        report = service.stop_live_stream()
        if not report:
            logger.console("Режим Live Stream не был активен или нет данных для сессии.")
            logger.console("=" * 65)
            return 0

        logger.console(f"✅ Отчет сессии: {report.get('session_id')}")
        logger.console(f"   Период:      {report.get('started_at')} -> {report.get('ended_at')}")
        logger.console(f"   Длительность:{report.get('duration_seconds')} сек")
        logger.console(f"   Процессор:   {report.get('cpu_model')}")
        logger.console(f"     - Нагрузка:  Avg {report.get('cpu_avg_percent')}% | Max {report.get('cpu_max_percent')}%")
        if report.get('cpu_avg_temp_c') is not None:
            logger.console(f"     - Температура: Avg {report.get('cpu_avg_temp_c')}°C | Max {report.get('cpu_max_temp_c')}°C")
        logger.console(f"   Память RAM:  {report.get('ram_total_gb')} ГБ")
        logger.console(f"     - Занято:    Avg {report.get('ram_avg_used_gb')} ГБ ({report.get('ram_avg_percent')}%) | Max {report.get('ram_max_used_gb')} ГБ")
        if report.get('gpu_name'):
            logger.console(f"   Видеокарта:  {report.get('gpu_name')}")
            logger.console(f"     - Нагрузка:  Avg {report.get('gpu_avg_percent')}% | Max {report.get('gpu_max_percent')}%")
            if report.get('gpu_avg_temp_c') is not None:
                logger.console(f"     - Температура: Avg {report.get('gpu_avg_temp_c')}°C | Max {report.get('gpu_max_temp_c')}°C")
        logger.console(f"   Диски:       {report.get('disk_read_mbs')} МБ/с чт | {report.get('disk_write_mbs')} МБ/с зап")
        logger.console(f"   Сеть:        {report.get('network_recv_kb_sec')} КБ/с приём | {report.get('network_sent_kb_sec')} КБ/с отдача")

        top_cpu = report.get('top_cpu_consumers', [])
        if top_cpu:
            logger.console("   Топ процессы по CPU (чем было загружено железо):")
            for p in top_cpu[:5]:
                logger.console(f"      * {p.get('name')} (PID {p.get('pid')}): Avg {p.get('avg_cpu_percent')}% | Max {p.get('max_cpu_percent')}%")

        logger.console("=" * 65)
        return 0

    elif action == 'sessions':
        sessions = storage.get_live_stream_sessions(limit=args.limit)
        logger.console("=" * 75)
        logger.console(f"   Сохраненные профили сессий Live Stream (всего {len(sessions)})")
        logger.console("=" * 75)
        if not sessions:
            logger.console("Нет завершенных сессий live stream.")
            return 0
        for s in sessions:
            logger.console(f"📦 [{s.get('session_id')}] {s.get('started_at')[:19]} ({s.get('duration_seconds')}с)")
            logger.console(f"   CPU: Avg {s.get('cpu_avg_percent')}% (Max {s.get('cpu_max_percent')}%) | RAM: {s.get('ram_avg_used_gb')}/{s.get('ram_total_gb')} ГБ | I/O: {s.get('disk_read_mbs')} MB/s")
        logger.console("=" * 75)
        return 0

    return 0


def cmd_hardware_changes(args: argparse.Namespace) -> int:
    """Выводит историю всех зафиксированных изменений конфигурации оборудования (как было и как стало)."""
    from apps.windows.telemetry.sqlite import TelemetryStorage
    storage = TelemetryStorage.get_instance(read_only=True)
    changes = storage.get_hardware_config_changes(limit=getattr(args, 'limit', 50))

    logger.console("=" * 75)
    logger.console(f"   История изменений аппаратной конфигурации (всего {len(changes)})")
    logger.console("=" * 75)
    if not changes:
        logger.console("Изменений конфигурации оборудования пока не зафиксировано.")
        logger.console("Таблица hardware_config_changes хранит историю модернизаций ВСЕГДА.")
        logger.console("=" * 75)
        return 0

    for ch in changes:
        logger.console(f"🔧 [#{ch.get('id')}] {ch.get('timestamp')} | {ch.get('component_type')} ({ch.get('change_type')})")
        logger.console(f"   Компонент: {ch.get('component_name')}")
        logger.console(f"   Суть:      {ch.get('summary')}")
        if ch.get('old_config'):
            logger.console(f"   Было:      {ch.get('old_config')}")
        if ch.get('new_config'):
            logger.console(f"   Стало:     {ch.get('new_config')}")
        logger.console("-" * 75)
    return 0


def cmd_hardware_report(args: argparse.Namespace) -> int:
    """Формирует и выводит сравнительный отчет производительности железа «Было / Стало»."""
    from apps.windows.telemetry.sqlite import TelemetryStorage
    storage = TelemetryStorage.get_instance(read_only=True)
    rep = storage.get_hardware_comparison_report(
        change_id=getattr(args, 'change_id', None),
        component_type=getattr(args, 'component_type', None),
    )

    logger.console("=" * 75)
    logger.console("       Сравнительный отчет модернизации оборудования («Было / Стало»)")
    logger.console("=" * 75)
    if not rep:
        logger.console("Недостаточно данных для сравнения. Запустите сессию live stream до и после модернизации.")
        logger.console("=" * 75)
        return 0

    ch = rep.get('change_info')
    if ch:
        logger.console(f"Изменение:    #{ch.get('id')} ({ch.get('component_type')}) - {ch.get('summary')}")
        logger.console(f"Дата замены:  {ch.get('timestamp')}")

    b_sess = rep.get('before_session')
    a_sess = rep.get('after_session')

    if b_sess:
        logger.console("\n📊 Состояние ДО модернизации:")
        logger.console(f"   Сессия:       {b_sess.get('session_id')} ({b_sess.get('started_at')[:19]})")
        logger.console(f"   Процессор:    {b_sess.get('cpu_model')} (Avg {b_sess.get('cpu_avg_percent')}%, Max {b_sess.get('cpu_max_percent')}%)")
        if b_sess.get('cpu_avg_temp_c') is not None:
            logger.console(f"   Температура:  Avg {b_sess.get('cpu_avg_temp_c')}°C | Max {b_sess.get('cpu_max_temp_c')}°C")
        logger.console(f"   Память:       Avg {b_sess.get('ram_avg_used_gb')} ГБ ({b_sess.get('ram_avg_percent')}%)")
        if b_sess.get('gpu_name'):
            logger.console(f"   Видеокарта:   {b_sess.get('gpu_name')} (Avg {b_sess.get('gpu_avg_percent')}%)")

    if a_sess:
        logger.console("\n🚀 Состояние ПОСЛЕ модернизации:")
        logger.console(f"   Сессия:       {a_sess.get('session_id')} ({a_sess.get('started_at')[:19]})")
        logger.console(f"   Процессор:    {a_sess.get('cpu_model')} (Avg {a_sess.get('cpu_avg_percent')}%, Max {a_sess.get('cpu_max_percent')}%)")
        if a_sess.get('cpu_avg_temp_c') is not None:
            logger.console(f"   Температура:  Avg {a_sess.get('cpu_avg_temp_c')}°C | Max {a_sess.get('cpu_max_temp_c')}°C")
        logger.console(f"   Память:       Avg {a_sess.get('ram_avg_used_gb')} ГБ ({a_sess.get('ram_avg_percent')}%)")
        if a_sess.get('gpu_name'):
            logger.console(f"   Видеокарта:   {a_sess.get('gpu_name')} (Avg {a_sess.get('gpu_avg_percent')}%)")

    metrics = rep.get('metrics_comparison', {})
    if metrics:
        logger.console("\n📈 Дельта показателей:")
        for k, v in metrics.items():
            sign = "+" if (isinstance(v, (int, float)) and v > 0) else ""
            logger.console(f"   - {k}: {sign}{v}")

    logger.console(f"\n💡 Вывод: {rep.get('conclusion')}")
    logger.console("=" * 75)
    return 0

def main() -> int:
    """Точка входа утилиты AITelemetryCtl."""
    parser = argparse.ArgumentParser(description='AITelemetry CLI Controller')
    subparsers = parser.add_subparsers(dest='command', help='Команды управления')

    subparsers.add_parser('status', help='Показать статус службы и БД')
    subparsers.add_parser('start', help='Запустить службу')
    subparsers.add_parser('stop', help='Остановить службу')
    subparsers.add_parser('restart', help='Перезапустить службу')
    subparsers.add_parser('database', help='Показать статистику базы данных')
    subparsers.add_parser('diagnose', help='Выполнить экспресс-диагностику')

    mode_p = subparsers.add_parser('mode', help='Управление режимами телеметрии: both, streaming, live_stream, audit, stop_streaming')
    mode_p.add_argument('mode_name', nargs='?', choices=['both', 'streaming', 'live_stream', 'audit', 'live', 'stop_streaming'], default=None, help='Режим работы')
    mode_p.add_argument('--pid', type=int, default=None, help='Целевой PID для режима audit')
    mode_p.add_argument('--interval', type=float, default=None, help='Интервал замеров аудита (сек)')

    audit_p = subparsers.add_parser('audit', help='Глубокий аудит целевого процесса по PID')
    audit_p.add_argument('pid', type=int, help='Идентификатор процесса Windows (PID)')

    sec_parser = subparsers.add_parser('security', help='Управление и аналитика журнала безопасности Security.evtx')
    sec_sub = sec_parser.add_subparsers(dest='sec_action', help='Действия security')

    sec_sub.add_parser('status', help='Статус журнала безопасности и политик аудита')

    tail_p = sec_sub.add_parser('tail', help='Свежие события безопасности в реальном времени')
    tail_p.add_argument('--limit', type=int, default=20, help='Количество событий')
    tail_p.add_argument('--event-id', type=int, default=None, help='Фильтр по Event ID')
    tail_p.add_argument('--search', type=str, default='', help='Поисковая подстрока')

    search_p = sec_sub.add_parser('search', help='Поиск по Event ID в сохраненной базе')
    search_p.add_argument('target', help='Идентификатор события (например 4624, 4688)')
    search_p.add_argument('--limit', type=int, default=50, help='Лимит записей')

    user_p = sec_sub.add_parser('user', help='Поиск событий по пользователю')
    user_p.add_argument('target', help='Имя пользователя (например David, SYSTEM)')
    user_p.add_argument('--limit', type=int, default=50, help='Лимит записей')

    proc_p = sec_sub.add_parser('process', help='История создания процессов (4688)')
    proc_p.add_argument('target', help='Имя процесса (например python.exe, cmd.exe)')
    proc_p.add_argument('--limit', type=int, default=50, help='Лимит записей')

    failed_p = sec_sub.add_parser('failed-logons', help='Неудачные попытки входа (4625)')
    failed_p.add_argument('--hours', type=int, default=24, help='Глубина выборки в часах')

    coll_p = sec_sub.add_parser('collect', help='Запустить инкрементальный сбор из Security.evtx')
    coll_p.add_argument('--batch', type=int, default=500, help='Размер пакета')
    coll_p.add_argument('--max', type=int, default=5000, help='Максимум событий')
    coll_p.add_argument('--raw', action='store_true', help='Сохранять сырой XML')

    corr_p = sec_sub.add_parser('correlate', help='Корреляция событий с метриками телеметрии')
    corr_p.add_argument('--pid', type=int, default=None, help='Фильтр по PID')
    corr_p.add_argument('--user', type=str, default=None, help='Фильтр по пользователю')

    # Команда logs (Каталог 7 доменов, Provenance, Power Lifecycle)
    logs_p = subparsers.add_parser('logs', help='Иерархический каталог Windows Event Logs, 7 доменов и графы происхождения')
    logs_sub = logs_p.add_subparsers(dest='logs_action', help='Действия logs')
    logs_sub.add_parser('domains', help='Сводка по 7 доменам телеметрии Windows Event Logs')
    logs_sub.add_parser('catalog', help='Полный реестр провайдеров и каналов')
    prov_p = logs_sub.add_parser('provenance', help='Граф происхождения процессов (User -> Process -> Parent -> SCM)')
    prov_p.add_argument('--process', type=str, default=None, help='Фильтр по имени процесса')
    prov_p.add_argument('--pid', type=int, default=None, help='Фильтр по PID')
    life_p = logs_sub.add_parser('lifecycle', help='Таймлайн жизненного цикла ОС (Boot/Sleep/Wake/Shutdown/Crash)')
    life_p.add_argument('--hours', type=int, default=72, help='Глубина выборки в часах')
    logs_sub.add_parser('sysmon', help='Проверить статус и возможности Sysmon')

    life_cmd_p = subparsers.add_parser('lifecycle', help='Журнал сессий жизненного цикла процессов (рождение, завершение, ресурсы)')
    life_cmd_p.add_argument('--app', type=str, default=None, help='Фильтр по имени процесса')
    life_cmd_p.add_argument('--user', type=str, default=None, help='Фильтр по имени пользователя')
    life_cmd_p.add_argument('--parent', type=str, default=None, help='Фильтр по имени родителя')
    life_cmd_p.add_argument('--alive', action='store_true', help='Только активные процессы')
    life_cmd_p.add_argument('--dead', action='store_true', help='Только завершенные процессы')
    life_cmd_p.add_argument('--limit', type=int, default=50, help='Максимум строк')

    summary_p = subparsers.add_parser('app-summary', help='Сводный аналитический отчет по приложению или пользователю')
    summary_p.add_argument('--app', type=str, default=None, help='Имя процесса (например python.exe)')
    summary_p.add_argument('--user', type=str, default=None, help='Имя пользователя')

    inc_p = subparsers.add_parser('incident', help='Восстановить сквозную хронику инцидента процесса (CPU, RAM, Диск, Сеть)')
    inc_p.add_argument('pid', type=int, help='Идентификатор процесса Windows (PID)')
    inc_p.add_argument('--limit', type=int, default=100, help='Максимум замеров для анализа')

    subparsers.add_parser('purge-live-stream', help='Очистить таблицы режима live stream (вызывается при переходе в аудит)')

    # Команда live-stream (работа по запросу, отчет ресурсопотребления)
    ls_p = subparsers.add_parser('live-stream', help='Управление live stream по запросу и отчеты ресурсопотребления')
    ls_sub = ls_p.add_subparsers(dest='ls_action', help='Действия live-stream')
    ls_start = ls_sub.add_parser('start', help='Запустить сессию live stream по запросу')
    ls_start.add_argument('--duration', type=float, default=None, help='Таймаут сессии в секундах (автоостановка)')
    ls_sub.add_parser('stop', help='Остановить сессию live stream и сформировать отчет')
    ls_sess = ls_sub.add_parser('sessions', help='Список сохраненных сессий и профилей нагрузки')
    ls_sess.add_argument('--limit', type=int, default=20, help='Лимит записей')

    # Команда hw-changes (история замен оборудования - как было и как стало)
    hwc_p = subparsers.add_parser('hw-changes', help='История изменений оборудования (как было и как стало - хранится всегда)')
    hwc_p.add_argument('--limit', type=int, default=50, help='Лимит записей')

    # Команда hw-report (сравнительный отчет модернизации железа)
    hwr_p = subparsers.add_parser('hw-report', help='Сравнительный отчет производительности железа до и после апгрейда («Было / Стало»)')
    hwr_p.add_argument('--change-id', type=int, default=None, help='Идентификатор изменения оборудования')
    hwr_p.add_argument('--component', type=str, default=None, help='Тип компонента (CPU, RAM, GPU, DISK)')

    args = parser.parse_args()

    if not args.command or args.command == 'status':
        return cmd_status()
    elif args.command in ('start', 'stop', 'restart'):
        return cmd_control(args.command)
    elif args.command == 'database':
        return cmd_database()
    elif args.command == 'diagnose':
        return cmd_diagnose()
    elif args.command == 'security':
        return cmd_security(args)
    elif args.command == 'logs':
        return cmd_logs(args)
    elif args.command == 'mode':
        return cmd_mode(args)
    elif args.command == 'purge-live-stream':
        return cmd_purge_live_stream()
    elif args.command == 'audit':
        return cmd_audit(args.pid)
    elif args.command == 'lifecycle':
        return cmd_lifecycle(args)
    elif args.command == 'app-summary':
        return cmd_app_summary(args)
    elif args.command == 'incident':
        return cmd_incident(args)
    elif args.command == 'live-stream':
        return cmd_live_stream_control(args)
    elif args.command == 'hw-changes':
        return cmd_hardware_changes(args)
    elif args.command == 'hw-report':
        return cmd_hardware_report(args)
    return 0


if __name__ == '__main__':
    sys.exit(main())


