# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry - Main
# =============================================================================
# Description:
#   Главная точка входа для автономной службы системной телеметрии Windows.
#   Осуществляет непрерывный и периодический опрос метрик оборудования, ОС,
#   активности процессов, накопителей и безопасности с записью в telemetry.db.
#
# Usage Examples:
#   CLI:
#     python -m apps.windows.telemetry.main --mode hybrid
#     python -m apps.windows.telemetry.main --once
#     ./tlm.ps1 -Foreground
#
# File: main.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-30 12:03:00
# =============================================================================

from __future__ import annotations
"""Главная точка входа для службы системной телеметрии Windows."""

import argparse
import logging
import os
import platform
from typing import Optional
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 1. Настройка кодировки UTF-8 для консоли Windows
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')
os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"

# 2. Определение базовой директории проекта
current_path = Path(__file__).resolve().parent
PROJECT_ROOT = current_path
for candidate in [current_path] + list(current_path.parents):
    if (candidate / 'pyproject.toml').is_file() or (candidate / 'apps').is_dir():
        PROJECT_ROOT = candidate
        break

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if __package__ in (None, ''):
    __package__ = 'apps.windows.telemetry'

try:
    from logger import logger
except ImportError:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    logger = logging.getLogger("telemetry_service")
    if not hasattr(logger, "console"):
        def _console(msg: Any = '', *args: Any, text_color: str = '', **kwargs: Any) -> None:
            logger.info(msg, *args)
        logger.console = _console  # type: ignore

_stop_event = threading.Event()


def parse_arguments() -> argparse.Namespace:
    """Парсит аргументы командной строки службы телеметрии.

    Returns:
        argparse.Namespace: Распарсенные аргументы запуска.
    """
    parser = argparse.ArgumentParser(
        description="AI-Windows-Admin Telemetry Service Entrypoint",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--mode', choices=['minimal', 'hybrid', 'full'], default=None, help='Режим работы: minimal (легковесный), hybrid (минимал + тяжелые периодически), full (полный стек)')
    parser.add_argument('--minimal', action='store_true', help='Запустить в легковесном режиме (эквивалентно --mode minimal)')
    parser.add_argument('--interval', '-i', type=float, default=None, help='Интервал сбора быстрой телеметрии в секундах (по умолчанию из config.json)')
    parser.add_argument('--heavy-interval', type=float, default=None, help='Интервал сбора тяжелых сенсоров для hybrid режима в секундах (по умолчанию из config.json)')
    parser.add_argument('--top-processes', type=int, default=None, help='Количество сохраняемых процессов с наибольшей нагрузкой (по умолчанию 10)')
    parser.add_argument('--log-dir', type=str, default=None, help='Путь к директории для логов и SQLite БД телеметрии')
    parser.add_argument('--verbose', '-v', action='store_true', help='Включить подробный вывод (DEBUG)')
    parser.add_argument('--once', action='store_true', help='Выполнить однократный опрос метрик и завершить работу')
    parser.add_argument('--config', '-C', type=str, default=None, help='Путь к файлу конфигурации config.json / tc.json')
    return parser.parse_args()



def signal_handler(signum: int, frame: Optional[object]) -> None:
    """Обработчик сигналов для корректной остановки сервиса.

    Args:
        signum: Номер сигнала.
        frame: Стек вызовов.
    """
    logger.info(f'Получен сигнал {signum}, остановка телеметрии...')
    _stop_event.set()

def _set_low_priority() -> None:
    """Устанавливает пониженный приоритет процессу для экономии ресурсов CPU."""
    try:
        import psutil
        p = psutil.Process()
        p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        logger.debug('Установлен приоритет процесса: BELOW_NORMAL')
    except Exception as ex:
        logger.debug(f'Не удалось понизить приоритет процесса: {ex}')

def run_telemetry_service(
    mode: str = 'hybrid',
    interval: float = 5.0,
    heavy_interval: float = 60.0,
    top_processes: int = 10,
    heavy_collectors: Optional[Dict[str, bool]] = None,
    log_dir: Optional[str] = None,
    config_path: Optional[str] = None,
    once: bool = False,
) -> int:
    """Запускает универсальный цикл сбора телеметрии (Minimal, Hybrid или Full).

    Args:
        mode: Режим сбора ('minimal', 'hybrid', 'full').
        interval: Быстрый интервал сбора базовых метрик в секундах.
        heavy_interval: Периодический интервал сбора тяжелых сенсоров (для hybrid).
        top_processes: Количество процессов в топе.
        heavy_collectors: Словарь активных тяжелых сенсоров.
        log_dir: Каталог сохранения БД и логов.
        config_path: Путь к файлу конфигурации.

    Returns:
        int: Код завершения.
    """
    import psutil
    from apps.windows.sdk.modules.hardware.gpu_prober import GpuProber
    from .models import CpuMetrics, DiskIoMetrics, DiskPartitionMetrics, GpuMetrics, MemoryMetrics, NetworkInterfaceMetrics, ProcessMetrics, SystemSnapshot
    from .sqlite import TelemetryStorage
    from .telemetry_config import TelemetryConfigManager
    _set_low_priority()
    cfg_mgr = TelemetryConfigManager(config_path=config_path)
    resolved_log_dir = log_dir or str(cfg_mgr.get_data_path())
    os.makedirs(resolved_log_dir, exist_ok=True)
    db_path = os.path.join(resolved_log_dir, 'telemetry.db')
    storage = TelemetryStorage(db_path=db_path)
    gpu_prober = GpuProber()
    hostname = os.environ.get('COMPUTERNAME', 'localhost')
    boot_time = psutil.boot_time()
    psutil.cpu_percent(interval=None)

    custom_mode_set = mode is not None and ('--mode' in sys.argv or '--minimal' in sys.argv)
    custom_interval_set = interval is not None and ('--interval' in sys.argv or '-i' in sys.argv)
    custom_heavy_interval_set = heavy_interval is not None and '--heavy-interval' in sys.argv
    custom_top_processes_set = top_processes is not None and '--top-processes' in sys.argv

    if not custom_mode_set and cfg_mgr:
        mode = cfg_mgr.get_mode()
    if not custom_interval_set and cfg_mgr:
        interval = cfg_mgr.get_interval_seconds()
    if not custom_heavy_interval_set and cfg_mgr:
        heavy_interval = cfg_mgr.get_heavy_interval_seconds()
    if not custom_top_processes_set and cfg_mgr:
        top_processes = cfg_mgr.get_effective_process_limit()

    heavy_disk_interval_sec = cfg_mgr.get_heavy_disk_scan_interval()
    max_heavy_duration_sec = cfg_mgr.get_heavy_mode_max_duration_days() * 24.0 * 3600.0
    auto_switch_enabled = cfg_mgr.is_heavy_auto_switch_enabled()

    h_collectors = heavy_collectors or cfg_mgr.get_heavy_collectors()
    sensor_collector = None
    if mode in ('hybrid', 'full') and h_collectors.get('hardware_sensors', True):
        try:
            from .sensor_collector import SensorCollector
            sensor_collector = SensorCollector(config_manager=cfg_mgr)
            logger.debug('SensorCollector (Hardware/WMI) инициализирован для тяжелых опросов')
        except Exception as sc_err:
            logger.debug(f'SensorCollector не доступен: {sc_err}')

    system_collector = None
    deep_diag = None
    try:
        try:
            from apps.windows.telemetry.deep_diagnostics import DeepDiagnosticsEngine
        except ImportError:
            from apps.windows.analytics.deep_diagnostics import DeepDiagnosticsEngine
        from apps.windows.telemetry.collector import SystemCollector
        system_collector = SystemCollector(storage=storage)
        deep_diag = DeepDiagnosticsEngine()
    except Exception as init_err:
        logger.debug(f"Инициализация системного коллектора: {init_err}")

    # Создание W64/ETW сборщиков системных событий (запуск выполняется асинхронно в фоне)
    w64_collector = None
    w64_etw_collector = None
    w64_cfg = cfg_mgr.get_config().get('w64_collector', {}) if cfg_mgr else {}
    if w64_cfg.get('enabled', False):
        try:
            from .w64_collector import AIW64Collector
            from .w64_etw_collector import AIW64ETWCollector
            w64_collector = AIW64Collector(
                storage=storage,
                enable_file_monitoring=w64_cfg.get('enable_file_monitoring', False),
                enable_process_monitoring=w64_cfg.get('enable_process_monitoring', False),
                enable_registry_monitoring=w64_cfg.get('enable_registry_monitoring', False),
                enable_network_monitoring=w64_cfg.get('enable_network_monitoring', False),
                enable_event_log_monitoring=False,
            )
            w64_etw_collector = AIW64ETWCollector(
                storage=storage,
                enable_process_trace=w64_cfg.get('enable_process_trace', False),
                enable_disk_trace=w64_cfg.get('enable_disk_trace', False),
                enable_network_trace=w64_cfg.get('enable_network_trace', False),
                enable_registry_trace=w64_cfg.get('enable_registry_trace', False),
            )
        except Exception as w64_err:
            logger.debug(f'Не удалось создать W64 сборщики: {w64_err}')

    logger.info('=' * 60)
    logger.info(f'Запущен сервис телеметрии Windows [Режим: {mode.upper()}]')
    logger.info(f'Быстрый интервал: {interval} с | Топ процессов: {top_processes}')
    if mode == 'hybrid':
        logger.info(f'Периодический тяжелый опрос: каждые {heavy_interval} с')
    logger.info(f'База данных: {db_path}')
    logger.info('=' * 60)
    tick = 0
    prev_disk_io = psutil.disk_io_counters()
    prev_net_io = psutil.net_io_counters()
    prev_io_time = time.time()
    last_gpu_probe_time: Optional[float] = None
    cached_gpu_metrics: List[GpuMetrics] = []
    last_partition_check: float = 0.0
    cached_part_list: List[Any] = []
    cached_physical_disks: List[Any] = []
    cached_identity: Dict[str, Any] = {}
    cached_monitors: List[Any] = []
    cached_updates: Optional[Any] = None
    cached_office: Optional[Any] = None
    cached_onedrive: Optional[Any] = None
    cached_ram_sticks: List[Any] = []
    cached_battery: Optional[Any] = None
    last_heavy_time = time.time()
    last_heavy_disk_scan_time = time.time()
    heavy_mode_start_time: Optional[float] = time.time() if mode.lower() in ('full', 'heavy') else None
    heavy_poll_running = False
    heavy_poll_lock = threading.Lock()
    startup_surveys_done = False
    db_cleanup_interval_sec = cfg_mgr.get_db_cleanup_interval_seconds()
    last_db_cleanup_time = time.time()
    aggregation_interval_sec = getattr(cfg_mgr, 'get_aggregation_interval', lambda: 300.0)() if cfg_mgr else 300.0
    last_aggregation_time = time.time()
    known_pids: Dict[int, str] = {}
    last_forensics_window: Optional[Tuple[str, int]] = None
    last_forensics_time: float = 0.0

    def _execute_heavy_poll_job(is_startup: bool = False) -> None:
        nonlocal last_heavy_disk_scan_time, heavy_poll_running, startup_surveys_done, cached_physical_disks, cached_identity, cached_monitors, cached_updates, cached_office, cached_onedrive, cached_ram_sticks, cached_battery
        heavy_start = time.time()
        try:
            # 1. Поочередные стартовые тяжелые опросы (выполняются в фоне один за другим при старте)
            if is_startup and not startup_surveys_done:
                # Этап 1. Идентификация хоста, локали, мониторов и ПО
                if system_collector:
                    try:
                        cached_identity = system_collector.get_system_identity()
                        logger.info(f"💻 Хост: {cached_identity.get('hostname')} | Пользователь: {cached_identity.get('username')} | ОС: Windows {cached_identity.get('os_build')}")
                        logger.info(f"🌐 Язык: {cached_identity.get('system_language')} | Локаль: {cached_identity.get('user_locale')} | Раскладки: {', '.join(cached_identity.get('input_languages', []))}")
                    except Exception as id_err:
                        logger.debug(f"Ошибка сбора идентификации системы: {id_err}")

                    try:
                        cached_monitors = system_collector.get_monitors()
                        logger.info(f"🖥️ Обнаружено активных мониторов: {len(cached_monitors)}")
                    except Exception as mon_err:
                        logger.debug(f"Ошибка сбора мониторов: {mon_err}")

                    try:
                        cached_updates = system_collector.get_updates_info()
                    except Exception as upd_err:
                        logger.debug(f"Ошибка сбора обновлений: {upd_err}")

                    try:
                        cached_office = system_collector.get_ms_office_info()
                        cached_onedrive = system_collector.get_onedrive_info()
                    except Exception as sw_err:
                        logger.debug(f"Ошибка сбора ПО: {sw_err}")

                    try:
                        import asyncio
                        cached_ram_sticks = asyncio.run(system_collector.get_ram_sticks())
                    except Exception as ram_err:
                        logger.debug(f"Ошибка сбора RAM SPD: {ram_err}")

                    try:
                        cached_battery = system_collector.get_battery_metrics()
                    except Exception as batt_err:
                        logger.debug(f"Ошибка сбора батареи: {batt_err}")

                # Этап 2. Опрос физических накопителей и SMART (PowerShell/CIM)
                if system_collector and h_collectors.get('storage_smart', True):
                    try:
                        disks_health = system_collector.get_physical_disks_health(force=True)
                        if disks_health:
                            cached_physical_disks = disks_health
                            d_summary = ", ".join([f"{d.model} ({d.media_type}, {d.size_gb}GB, SMART:{d.health_status})" for d in disks_health])
                            logger.info(f"💾 Накопители SMART (Опрос при запуске): {d_summary}")
                        last_heavy_disk_scan_time = time.time()
                    except Exception as dh_err:
                        logger.debug(f"Ошибка опроса дисков SMART при старте: {dh_err}")

                # Этап 3. Аппаратное дерево и спецификация компонентов
                if system_collector:
                    try:
                        import asyncio
                        hw_tree = asyncio.run(system_collector.get_hardware_tree_async(force=True))
                        if hw_tree:
                            logger.info(f"🖥️ [АППАРАТНАЯ КОНФИГУРАЦИЯ] Спецификация всего железа ПК определена ({len(hw_tree)} компонентов)")
                            if isinstance(storage, TelemetryStorage):
                                storage.sync_hardware_components_lifecycle(hw_tree)
                    except Exception as hw_err:
                        logger.debug(f"Ошибка сбора дерева оборудования: {hw_err}")

                # Этап 4. Проверка критических аудитов при запуске
                try:
                    from apps.windows.analytics.audit_startup_checker import run_startup_audit
                    startup_audit = run_startup_audit(
                        check_integrity=True,
                        check_performance=True,
                        check_drivers=False,
                        check_eventlog=False
                    )
                    if not startup_audit.is_healthy:
                        logger.error(
                            f"🚨 STARTUP AUDIT: Обнаружены критические проблемы! "
                            f"Critical: {startup_audit.critical_count}, Warnings: {startup_audit.warning_count}"
                        )
                        for finding in startup_audit.findings:
                            logger.warning(f"  - [{finding['severity'].upper()}] {finding['domain']}: {finding['title']}")
                    elif startup_audit.warning_count > 0:
                        logger.warning(
                            f"⚠️ STARTUP AUDIT: Предупреждения: {startup_audit.warning_count} ({startup_audit.duration_ms}ms)"
                        )
                        for finding in startup_audit.findings:
                            logger.warning(f"  - [{finding['severity'].upper()}] {finding['domain']}: {finding['title']}")
                    else:
                        logger.info(f"✅ STARTUP AUDIT: Все проверки пройдены ({startup_audit.duration_ms}ms)")

                    # Сохранение выявленных проблем и предупреждений аудита запуска в БД
                    if storage and startup_audit.findings:
                        for finding in startup_audit.findings:
                            storage.save_event(
                                event_type=f"startup_audit_{finding.get('domain', 'system')}",
                                event_details=finding,
                                severity=finding.get('severity', 'warning')
                            )
                        storage.flush()
                except Exception as audit_err:
                    logger.debug(f"Проверка аудитов при запуске: {audit_err}")

                # Этап 5. Аудит точек автозапуска Windows (Autoruns)
                if system_collector:
                    try:
                        startup_entry = system_collector.archive_startup_state(auto_diff=True)
                        if startup_entry and startup_entry.report:
                            rep = startup_entry.report
                            score = getattr(rep.summary, 'health_score', 100) if hasattr(rep, 'summary') else 100
                            total_items = getattr(rep.summary, 'total_entries', len(rep.entries)) if hasattr(rep, 'summary') else len(rep.entries)
                            logger.info(
                                f"🚀 [АВТОЗАПУСК] Снимок автозагрузки зафиксирован в телеметрии: "
                                f"{total_items} элементов (Health Score: {score}/100, изменений: {startup_entry.changes_count})"
                            )
                    except Exception as st_err:
                        logger.debug(f"Ошибка сбора снимка автозапуска при старте телеметрии: {st_err}")

                # Этап 6. Инвентаризация установленного ПО и аудит спящих программ
                try:
                    from apps.windows.sdk.core.software_audit import SoftwareAuditEngine
                    sw_engine = SoftwareAuditEngine()
                    sw_report = sw_engine.generate_audit_report(save_to_db=True)
                    if sw_report:
                        logger.info(
                            f"📦 [ИНВЕНТАРИЗАЦИЯ ПО] Программное обеспечение просканировано и сохранено в телеметрию: "
                            f"всего {sw_report.total_apps} программ (активных: {sw_report.active_apps_count}, спящих: {sw_report.unused_apps_count})"
                        )
                except Exception as sw_scan_err:
                    logger.debug(f"Ошибка инвентаризации ПО при старте телеметрии: {sw_scan_err}")

                # Прогрев быстрого отчета сканера ПО (DeepSoftwareScanner) и сохранение в telemetry.db
                try:
                    from apps.windows.sdk.software_scanner.controller import DeepSoftwareScanner
                    from apps.windows.sdk.software_scanner.models import ScanMode
                    import apps.windows.sdk.software_scanner.router as sw_router_mod
                    from apps.windows.telemetry.sqlite import TelemetryStorage
                    quick_scanner = DeepSoftwareScanner()
                    scanner_report = quick_scanner.run_scan(mode=ScanMode.QUICK)
                    if scanner_report:
                        sw_router_mod._last_report = scanner_report
                        # storage already initialized earlier
                        storage.save_software_scanner_report(scanner_report)
                        logger.info(
                            f"🔍 [СКАНЕР ПО] Отчет сканера ПО сохранен в telemetry.db ({len(scanner_report.inventory)} программ, "
                            f"{scanner_report.stats.dormant_count} спящих, {scanner_report.stats.orphan_count} сирот)"
                        )
                except Exception as sc_err:
                    logger.debug(f"Ошибка прогрева быстрого сканера ПО и сохранения в telemetry.db: {sc_err}")

                # Этап 7. Запуск W64/ETW сборщиков системных событий
                if w64_collector:
                    try:
                        w64_collector.start()
                    except Exception as w_err:
                        logger.debug(f"Не удалось запустить AIW64Collector: {w_err}")
                if w64_etw_collector:
                    try:
                        w64_etw_collector.start()
                    except Exception as we_err:
                        logger.debug(f"Не удалось запустить AIW64ETWCollector: {we_err}")
                if (w64_collector and w64_collector._running) or (w64_etw_collector and w64_etw_collector._running):
                    logger.info('🛰️ Сборщики событий W64 и ETW запущены в составе телеметрии')

                startup_surveys_done = True

            # 2. Периодический опрос системных сенсоров WMI/CIM, SMART, портов, утечек и безопасности
            if mode in ('hybrid', 'full') or is_startup:
                logger.console("🔥 [ТЯЖЕЛЫЙ ОПРОС] Запуск периодического опроса сенсоров WMI/CIM, SMART, портов и утечек...")
                heavy_readings_total = []
                if sensor_collector and h_collectors.get('hardware_sensors', True):
                    heavy_readings = sensor_collector.collect_all_sensors()
                    if heavy_readings:
                        heavy_readings_total.extend(heavy_readings)
                        try:
                            storage.save_sensor_polls(heavy_readings)
                        except Exception as sp_err:
                            logger.debug(f'Ошибка сохранения sensor_polls в БД: {sp_err}')

                        # Разгруппировка и красивый вывод аппаратных сенсоров в консоль
                        hw_temps = [f"{s.get('sensor_name')}: {s.get('value')}{s.get('unit')}" for s in heavy_readings if s.get('sensor_category') in ('Temperatures', 'Temperature')]
                        hw_powers = [f"{s.get('sensor_name')}: {s.get('value')}{s.get('unit')}" for s in heavy_readings if s.get('sensor_category') in ('Powers', 'Power')]
                        hw_fans = [f"{s.get('sensor_name')}: {s.get('value')}{s.get('unit')}" for s in heavy_readings if s.get('sensor_category') in ('Fans', 'Fan')]
                        hw_clocks = [f"{s.get('sensor_name')}: {s.get('value')}{s.get('unit')}" for s in heavy_readings if s.get('sensor_category') in ('Clocks', 'Clock')]

                        logger.console(f"🌡️ [АППАРАТНЫЕ СЕНСОРЫ] Опрошено {len(heavy_readings)} аппаратных датчиков:")
                        if hw_temps:
                            logger.console(f"   ├─ Температуры ({len(hw_temps)}): {', '.join(hw_temps[:8])}")
                        if hw_powers:
                            logger.console(f"   ├─ Энергопотребление ({len(hw_powers)}): {', '.join(hw_powers[:6])}")
                        if hw_fans:
                            logger.console(f"   ├─ Вентиляторы ({len(hw_fans)}): {', '.join(hw_fans)}")
                        if hw_clocks:
                            logger.console(f"   └─ Частоты ({len(hw_clocks)}): {', '.join(hw_clocks[:6])}")

                # Детальный аудит портов, сетевых соединений и утечек дескрипторов
                if system_collector:
                    try:
                        ports = system_collector.get_listening_ports(limit=10)
                        if ports:
                            p_str = ", ".join([f"{p.port}/{p.protocol} ({p.process_name or 'System'})" for p in ports[:5]])
                            logger.console(f"🌐 [ТЯЖЕЛЫЙ ОПРОС] Открытые слушающие порты ({len(ports)}): {p_str}")
                    except Exception:
                        pass
                    try:
                        net_conns = system_collector.get_process_network_activity(limit=50, only_internet=False)
                        if net_conns:
                            if isinstance(storage, TelemetryStorage):
                                storage.save_process_network_snapshot(f"snap_net_{int(time.time())}", net_conns)
                            ext_conns = [c for c in net_conns if getattr(c, 'is_internet', False)]
                            c_str = ", ".join([f"{c.name}->{c.remote_address} ({c.service_type})" for c in ext_conns[:3]])
                            logger.console(f"📡 [ТЯЖЕЛЫЙ ОПРОС] Активные соединения ({len(net_conns)}, Интернет: {len(ext_conns)}): {c_str}")
                    except Exception as net_err:
                        logger.debug(f"Ошибка сбора/сохранения сетевой активности: {net_err}")

                if storage:
                    try:
                        leaks = storage.get_latest_process_leak_report(limit=5)
                        if leaks and leaks.get("top_handle_hogs"):
                            top_h = leaks["top_handle_hogs"][0]
                            logger.console(f"🔍 [ТЯЖЕЛЫЙ ОПРОС] Топ процесса по дескрипторам: {top_h.get('name')} (PID:{top_h.get('pid')}) -> {top_h.get('handles_count')} handles, {top_h.get('gdi_objects')} GDI, {top_h.get('user_objects')} USER")
                    except Exception:
                        pass

                # Периодический тяжелый опрос накопителей SMART и надежности (каждые 12 часов)
                h_now = time.time()
                if not is_startup and system_collector and h_collectors.get('storage_smart', True) and (h_now - last_heavy_disk_scan_time >= heavy_disk_interval_sec):
                    try:
                        heavy_disks = system_collector.get_physical_disks_health(force=True)
                        if heavy_disks:
                            cached_physical_disks = heavy_disks
                            d_summary = ", ".join([f"{d.model} ({d.media_type}, {d.size_gb}GB, SMART:{d.health_status})" for d in heavy_disks])
                            logger.console(f"💾 [ТЯЖЕЛЫЙ ОПРОС (SMART)] Накопители SMART: {d_summary}")
                        last_heavy_disk_scan_time = h_now
                    except Exception as d_err:
                        logger.debug(f"Ошибка тяжелого сканирования накопителей: {d_err}")

                # Сбор журналов событий Windows в SQLite исключен: чтение логов выполняется
                # на лету через веб-интерфейс (WevtAPI), предотвращая неконтролируемый рост БД.

                # Синхронизация паспортов и активности процессов в SQLite (process_definition, process_instance, process_sample)
                try:
                    from apps.windows.sdk.core.process_activity_engine import ProcessActivityEngine
                    proc_engine = ProcessActivityEngine(storage=storage)
                    proc_engine.sync_processes()
                except Exception as proc_sync_err:
                    logger.debug(f"Ошибка синхронизации активности процессов (ProcessActivityEngine): {proc_sync_err}")

                heavy_dur = time.time() - heavy_start
                logger.console(f'✅ [{mode.upper()}] Периодический тяжелый опрос завершен за {heavy_dur:.2f}с (Всего сенсоров: {len(heavy_readings_total)})')
        except Exception as h_err:
            logger.error(f'Ошибка периодического тяжелого опроса: {h_err}')
        finally:
            with heavy_poll_lock:
                heavy_poll_running = False

    last_hw_sensors_time = time.time()
    last_ports_time = time.time()
    last_net_activity_time = time.time()
    last_leaks_time = time.time()
    last_smart_scan_time = time.time()
    last_proc_activity_time = time.time()
    last_internet_speed_time = 0.0
    last_tiered_compaction_time = time.time()

    def _poll_hw_sensors() -> None:
        if sensor_collector and h_collectors.get('hardware_sensors', True):
            try:
                heavy_readings = sensor_collector.collect_all_sensors()
                if heavy_readings:
                    storage.save_sensor_polls(heavy_readings)
                    hw_temps = [f"{s.get('sensor_name')}: {s.get('value')}{s.get('unit')}" for s in heavy_readings if s.get('sensor_category') in ('Temperatures', 'Temperature')]
                    if hw_temps:
                        logger.console(f"🌡️ [АППАРАТНЫЕ СЕНСОРЫ] Опрошено {len(heavy_readings)} датчиков (Температуры: {', '.join(hw_temps[:6])})")
            except Exception as ex:
                logger.debug(f"Ошибка сбора аппаратных сенсоров: {ex}")

    def _poll_listening_ports() -> None:
        if system_collector and (h_collectors.get('listening_ports', True) or h_collectors.get('system_snapshot', True)):
            try:
                ports = system_collector.get_listening_ports(limit=10)
                if ports:
                    p_str = ", ".join([f"{p.port}/{p.protocol} ({p.process_name or 'System'})" for p in ports[:5]])
                    logger.console(f"🌐 [СЕТЬ] Слушающие порты ({len(ports)}): {p_str}")
            except Exception as ex:
                logger.debug(f"Ошибка сбора портов: {ex}")

    def _poll_network_activity() -> None:
        if system_collector and h_collectors.get('network_activity', True):
            try:
                net_conns = system_collector.get_process_network_activity(limit=50, only_internet=False)
                if net_conns:
                    storage.save_process_network_snapshot(f"snap_net_{int(time.time())}", net_conns)
                    ext_conns = [c for c in net_conns if getattr(c, 'is_internet', False)]
                    c_str = ", ".join([f"{c.name}->{c.remote_address} ({c.service_type})" for c in ext_conns[:3]])
                    logger.console(f"📡 [СЕТЬ] Активные соединения ({len(net_conns)}, Интернет: {len(ext_conns)}): {c_str}")
            except Exception as ex:
                logger.debug(f"Ошибка сбора сетевой активности: {ex}")

    def _poll_process_leaks() -> None:
        if h_collectors.get('process_leaks', True):
            try:
                leaks = storage.get_latest_process_leak_report(limit=5)
                if leaks and leaks.get("top_handle_hogs"):
                    top_h = leaks["top_handle_hogs"][0]
                    logger.console(f"🔍 [УТЕЧКИ] Топ по дескрипторам: {top_h.get('name')} (PID:{top_h.get('pid')}) -> {top_h.get('handles_count')} handles, {top_h.get('gdi_objects')} GDI, {top_h.get('user_objects')} USER")
            except Exception as ex:
                logger.debug(f"Ошибка сбора утечек: {ex}")

    def _poll_smart_disks() -> None:
        nonlocal cached_physical_disks, last_heavy_disk_scan_time
        if system_collector and (h_collectors.get('deep_disk_smart', True) or h_collectors.get('storage_smart', True)):
            try:
                heavy_disks = system_collector.get_physical_disks_health(force=True)
                if heavy_disks:
                    cached_physical_disks = heavy_disks
                    d_summary = ", ".join([f"{d.model} ({d.media_type}, {d.size_gb}GB, SMART:{d.health_status})" for d in heavy_disks])
                    logger.console(f"💾 [S.M.A.R.T.] Накопители: {d_summary}")
                last_heavy_disk_scan_time = time.time()
            except Exception as ex:
                logger.debug(f"Ошибка опроса SMART дисков: {ex}")

    def _poll_process_activity() -> None:
        if h_collectors.get('process_activity', True):
            try:
                from apps.windows.sdk.core.process_activity_engine import ProcessActivityEngine
                ProcessActivityEngine(storage=storage).sync_processes()
            except Exception as ex:
                logger.debug(f"Ошибка синхронизации процессов: {ex}")

    def _poll_internet_speed() -> None:
        if h_collectors.get('internet_speed', True) or h_collectors.get('network', True):
            try:
                from apps.windows.telemetry.internet_speed import get_internet_speed_sensor
                sensor = get_internet_speed_sensor()
                res = sensor.check_and_run_hourly(force=False, skip_if_busy=True)
                if res and res.get('download_mbps', 0.0) > 0.0:
                    logger.console(
                        f"🌐 [FAST.COM] Часовой замер скорости: ↓{res.get('download_mbps', 0.0):.1f} Mbps, "
                        f"↑{res.get('upload_mbps', 0.0):.1f} Mbps, пинг: {res.get('ping_ms', 0.0):.1f} мс"
                    )
            except Exception as ex:
                logger.debug(f"Ошибка часового теста скорости интернета FAST.com: {ex}")

    def _trigger_granular_collector(collector_name: str) -> None:
        def _runner():
            with heavy_poll_lock:
                if collector_name == 'hw_sensors':
                    _poll_hw_sensors()
                elif collector_name == 'listening_ports':
                    _poll_listening_ports()
                elif collector_name == 'network_activity':
                    _poll_network_activity()
                elif collector_name == 'process_leaks':
                    _poll_process_leaks()
                elif collector_name == 'smart_disks':
                    _poll_smart_disks()
                elif collector_name == 'process_activity':
                    _poll_process_activity()
                elif collector_name == 'internet_speed':
                    _poll_internet_speed()
        threading.Thread(target=_runner, name=f"Collector-{collector_name}", daemon=True).start()

    def _trigger_heavy_worker(is_startup: bool = False) -> None:
        with heavy_poll_lock:
            nonlocal heavy_poll_running
            if not heavy_poll_running and not _stop_event.is_set():
                heavy_poll_running = True
                worker_thread = threading.Thread(
                    target=lambda: _execute_heavy_poll_job(is_startup=is_startup),
                    name="TelemetryHeavyPollWorker",
                    daemon=True
                )
                worker_thread.start()

    try:
        while not _stop_event.is_set():
            loop_start = time.time()

            # Динамическая перезагрузка параметров из config.json 'на лету'
            cfg_mgr.check_tc_mode_auto_switch()
            if cfg_mgr.check_and_reload():
                if not custom_interval_set:
                    interval = cfg_mgr.get_interval_seconds()
                if not custom_heavy_interval_set:
                    heavy_interval = cfg_mgr.get_heavy_interval_seconds()
                if not custom_top_processes_set:
                    top_processes = cfg_mgr.get_effective_process_limit()
                if not custom_mode_set:
                    mode = cfg_mgr.get_mode()
                heavy_disk_interval_sec = cfg_mgr.get_heavy_disk_scan_interval()
                db_cleanup_interval_sec = cfg_mgr.get_db_cleanup_interval_seconds()
                max_heavy_duration_sec = cfg_mgr.get_heavy_mode_max_duration_days() * 24.0 * 3600.0
                auto_switch_enabled = cfg_mgr.is_heavy_auto_switch_enabled()
                h_collectors = cfg_mgr.get_heavy_collectors()
                logger.info(
                    f"🔄 [Телеметрия CLI] Конфигурация config.json обновлена 'на лету': "
                    f"интервал={interval}с, тяжелый={heavy_interval}с, топ={top_processes}, режим={mode}, tel_mode={cfg_mgr.get_telemetry_mode()}"
                )

            now_dt = datetime.now(timezone.utc)
            now_iso = now_dt.isoformat()
            tick += 1
            cpu_pct = psutil.cpu_percent(interval=None)
            cpu_freq = psutil.cpu_freq()
            freq_mhz = cpu_freq.current if cpu_freq else 0.0
            cpu_model = ''
            try:
                cpu_model = os.environ.get('PROCESSOR_IDENTIFIER', '')
            except Exception:
                pass
            cpu_metrics = CpuMetrics(
                model=cpu_model,
                physical_cores=psutil.cpu_count(logical=False) or 1,
                logical_cores=psutil.cpu_count(logical=True) or 1,
                total_percent=cpu_pct,
                frequency_mhz=freq_mhz,
                temperature_celsius=None,
            )
            mem = psutil.virtual_memory()
            mem_metrics = MemoryMetrics(total_gb=round(mem.total / (1024 ** 3), 2), used_gb=round(mem.used / (1024 ** 3), 2), available_gb=round(mem.available / (1024 ** 3), 2), percent=mem.percent)
            now_sec = time.time()
            gpu_ttl = cfg_mgr.get_cache_ttl('gpu_probe_ttl_sec', 10.0)
            if last_gpu_probe_time is None or now_sec - last_gpu_probe_time >= gpu_ttl:
                try:
                    gpu_data = gpu_prober.probe()
                    cached_gpu_metrics = [
                        GpuMetrics(
                            name=getattr(g, 'name', 'GPU'),
                            vendor=getattr(g, 'vendor', ''),
                            gpu_type=getattr(g, 'gpu_type', 'Discrete'),
                            load_percent=getattr(g, 'load_percent', None) or getattr(g, 'utilization_gpu_pct', None),
                            memory_total_gb=round((getattr(g, 'memory_total_mb', 0.0) or 0.0) / 1024.0, 2),
                            memory_used_gb=round((getattr(g, 'memory_used_mb', 0.0) or 0.0) / 1024.0, 2),
                            dedicated_memory_mb=getattr(g, 'dedicated_memory_mb', 0.0),
                            shared_memory_mb=getattr(g, 'shared_memory_mb', 0.0),
                            memory_type=getattr(g, 'memory_type', 'Dedicated VRAM'),
                            directx_version=getattr(g, 'directx_version', 'DirectX 12'),
                            temperature_celsius=getattr(g, 'temperature_celsius', None) or getattr(g, 'temperature_gpu_c', None),
                            has_cuda=getattr(g, 'has_cuda', False),
                            has_rocm=getattr(g, 'has_rocm', False),
                            has_oneapi=getattr(g, 'has_oneapi', False),
                            has_directml=getattr(g, 'has_directml', True),
                            has_vulkan=getattr(g, 'has_vulkan', True),
                            has_opencl=getattr(g, 'has_opencl', True),
                            compute_apis=getattr(g, 'compute_apis', []),
                            ai_backends=getattr(g, 'ai_backends', []),
                            engines=getattr(g, 'engines', {}),
                        ) for g in gpu_data
                    ]
                except Exception:
                    cached_gpu_metrics = []
                last_gpu_probe_time = now_sec
            gpu_metrics_list = cached_gpu_metrics
            io_elapsed = max(0.001, now_sec - prev_io_time)
            cur_disk_io = psutil.disk_io_counters()
            disk_io_metrics = DiskIoMetrics()
            disk_read_kb = 0.0
            disk_write_kb = 0.0
            if cur_disk_io and prev_disk_io:
                disk_io_metrics.read_bytes_per_sec = max(0.0, (cur_disk_io.read_bytes - prev_disk_io.read_bytes) / io_elapsed)
                disk_io_metrics.write_bytes_per_sec = max(0.0, (cur_disk_io.write_bytes - prev_disk_io.write_bytes) / io_elapsed)
                disk_io_metrics.read_count_per_sec = max(0.0, (cur_disk_io.read_count - prev_disk_io.read_count) / io_elapsed)
                disk_io_metrics.write_count_per_sec = max(0.0, (cur_disk_io.write_count - prev_disk_io.write_count) / io_elapsed)
                disk_read_kb = round(disk_io_metrics.read_bytes_per_sec / 1024.0, 1)
                disk_write_kb = round(disk_io_metrics.write_bytes_per_sec / 1024.0, 1)
            prev_disk_io = cur_disk_io
            part_ttl = cfg_mgr.get_cache_ttl('disk_partitions_ttl_sec', 60.0)
            if not cached_part_list or now_sec - last_partition_check >= part_ttl:
                try:
                    cached_part_list = psutil.disk_partitions(all=False)
                    last_partition_check = now_sec
                except Exception:
                    pass
            disk_partitions: List[DiskPartitionMetrics] = []
            for part in cached_part_list:
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    disk_partitions.append(DiskPartitionMetrics(device=part.device, mountpoint=part.mountpoint, fstype=part.fstype, total_gb=round(usage.total / 1024 ** 3, 2), used_gb=round(usage.used / 1024 ** 3, 2), free_gb=round(usage.free / 1024 ** 3, 2), percent=usage.percent))
                except (PermissionError, OSError):
                    continue
            cur_net_io = psutil.net_io_counters()
            net_recv_kb = 0.0
            net_sent_kb = 0.0
            if cur_net_io and prev_net_io:
                net_recv_kb = round((cur_net_io.bytes_recv - prev_net_io.bytes_recv) / 1024.0 / io_elapsed, 1)
                net_sent_kb = round((cur_net_io.bytes_sent - prev_net_io.bytes_sent) / 1024.0 / io_elapsed, 1)
            prev_net_io = cur_net_io
            prev_io_time = now_sec
            net_metrics_list = [
                NetworkInterfaceMetrics(
                    name='total',
                    is_up=True,
                    speed_mbps=1000,
                    bytes_sent_per_sec=net_sent_kb * 1024.0,
                    bytes_recv_per_sec=net_recv_kb * 1024.0,
                )
            ]
            raw_procs = []
            current_proc_map: Dict[int, Dict[str, Any]] = {}
            for p in psutil.process_iter(['pid', 'name', 'memory_info', 'username']):
                try:
                    info = p.info
                    pid = info.get('pid', 0)
                    name = info.get('name') or 'unknown'
                    if pid:
                        current_proc_map[pid] = {'name': name, 'proc': p, 'info': info}
                    mem_rss = (info.get('memory_info') or getattr(p, 'memory_info', lambda: None)()).rss if info.get('memory_info') else 0
                    raw_procs.append((mem_rss, p, info))
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            # Аккумулирование вспыхивающих / новых процессов в буфер телеметрии
            if tick > 1:
                new_pids = set(current_proc_map.keys()) - set(known_pids.keys())
                if new_pids:
                    flash_events = []
                    for n_pid in new_pids:
                        p_entry = current_proc_map[n_pid]
                        p_obj = p_entry['proc']
                        p_name = p_entry['name']
                        exe_path = None
                        cmdline_str = None
                        ppid = None
                        parent_name = None
                        try:
                            exe_path = p_obj.exe()
                        except Exception:
                            pass
                        try:
                            cmdline_list = p_obj.cmdline()
                            if cmdline_list:
                                cmdline_str = " ".join(cmdline_list)
                        except Exception:
                            pass
                        try:
                            ppid = p_obj.ppid()
                            if ppid:
                                parent_name = psutil.Process(ppid).name()
                        except Exception:
                            pass

                        flash_events.append({
                            'event_type': 'ProcessCreated',
                            'pid': n_pid,
                            'ppid': ppid,
                            'name': p_name,
                            'executable_path': exe_path,
                            'command_line': cmdline_str,
                            'parent_name': parent_name,
                            'source': 'telemetry_detector',
                            'launch_reason': 'FlashProcess',
                            'timestamp': now_iso,
                        })

                    if flash_events and storage:
                        storage.save_process_provenance_batch(flash_events)

            known_pids = {pid: data['name'] for pid, data in current_proc_map.items()}

            # Классификация процессов на Apps, Background и Windows
            from apps.windows.sdk.modules.process_manager.core.classifier import (
                ProcessClassifier,
                WINDOWS_SYSTEM_PROCESS_NAMES,
                KNOWN_APP_FRIENDLY_NAMES,
            )
            classifier = ProcessClassifier()
            windowed_pids, titles_map = classifier.get_windowed_pids_and_titles()

            name_to_windowed = {
                (data['name'] or '').lower(): True
                for p_id, data in current_proc_map.items()
                if p_id in windowed_pids
            }

            # Группировка процессов по категориям
            app_groups: Dict[str, List[Dict[str, Any]]] = {}
            bg_groups: Dict[str, List[Dict[str, Any]]] = {}
            win_groups: Dict[str, List[Dict[str, Any]]] = {}

            for mem_rss, p, info in raw_procs:
                pid = info.get('pid', 0)
                p_name = info.get('name') or 'unknown'
                low_name = p_name.lower()
                has_win = pid in windowed_pids
                is_app = (
                    has_win or
                    (low_name in name_to_windowed and low_name not in WINDOWS_SYSTEM_PROCESS_NAMES) or
                    (low_name in KNOWN_APP_FRIENDLY_NAMES and low_name not in WINDOWS_SYSTEM_PROCESS_NAMES)
                )

                entry = {'pid': pid, 'name': p_name, 'mem_rss': mem_rss, 'proc': p, 'info': info, 'has_win': has_win}
                if is_app:
                    app_groups.setdefault(p_name, []).append(entry)
                elif low_name in WINDOWS_SYSTEM_PROCESS_NAMES:
                    win_groups.setdefault(p_name, []).append(entry)
                else:
                    bg_groups.setdefault(p_name, []).append(entry)

            apps_count = len(app_groups)
            bg_count = len(bg_groups)
            win_count = len(win_groups)

            raw_procs.sort(key=lambda x: x[0], reverse=True)
            top_candidates = raw_procs[:top_processes]
            top_procs: List[ProcessMetrics] = []
            for mem_rss, p, info in top_candidates:
                proc_cpu = 0.0
                try:
                    proc_cpu = p.cpu_percent(interval=None)
                except Exception:
                    pass
                mem_mb = round(mem_rss / (1024 * 1024), 1)
                raw_user = info.get('username')
                clean_user = raw_user if isinstance(raw_user, str) else ''
                p_id = info.get('pid', 0)
                p_name = info.get('name') or 'unknown'
                low_name = p_name.lower()
                has_win = p_id in windowed_pids
                is_app = (
                    has_win or
                    (low_name in name_to_windowed and low_name not in WINDOWS_SYSTEM_PROCESS_NAMES) or
                    (low_name in KNOWN_APP_FRIENDLY_NAMES and low_name not in WINDOWS_SYSTEM_PROCESS_NAMES)
                )
                cat = 'app' if is_app else ('windows' if low_name in WINDOWS_SYSTEM_PROCESS_NAMES else 'background')
                win_titles = titles_map.get(p_id, [])
                friendly = classifier._get_friendly_name(p_name, win_titles)

                top_procs.append(ProcessMetrics(
                    pid=p_id,
                    name=p_name,
                    cpu_percent=proc_cpu,
                    memory_mb=mem_mb,
                    threads_count=1,
                    status='running',
                    username=clean_user,
                    category=cat,
                    is_app=is_app,
                    friendly_name=friendly,
                    window_title=win_titles[0] if win_titles else None,
                ))

            if not cached_physical_disks and system_collector:
                try:
                    cached_physical_disks = system_collector.get_physical_disks_health(force=False)
                except Exception:
                    pass

            snapshot = SystemSnapshot(
                timestamp=now_iso,
                hostname=cached_identity.get('hostname') or hostname,
                workgroup=cached_identity.get('workgroup') or 'WORKGROUP',
                username=clean_user or cached_identity.get('username') or '',
                os_name=cached_identity.get('os_name') or f"{platform.system()} {platform.release()}",
                os_build=cached_identity.get('os_build') or platform.version(),
                system_language=cached_identity.get('system_language') or 'ru-RU',
                os_install_language=cached_identity.get('os_install_language') or 'ru-RU',
                user_locale=cached_identity.get('user_locale') or 'ru-RU',
                system_locale=cached_identity.get('system_locale') or 'ru-RU',
                timezone=cached_identity.get('timezone') or 'UTC+03:00',
                codepage=cached_identity.get('codepage') or 'UTF-8',
                input_languages=cached_identity.get('input_languages') or [],
                os_install_date=cached_identity.get('os_install_date') or '',
                uptime_seconds=round(time.time() - boot_time, 1),
                cpu=cpu_metrics,
                memory=mem_metrics,
                ram_sticks=cached_ram_sticks,
                gpus=gpu_metrics_list,
                monitors=cached_monitors,
                updates=cached_updates,
                office=cached_office,
                onedrive=cached_onedrive,
                disks=disk_partitions,
                disk_io=disk_io_metrics,
                physical_disks=cached_physical_disks,
                network=net_metrics_list,
                battery=cached_battery,
                top_processes=top_procs,
                apps_count=apps_count,
                background_count=bg_count,
                windows_count=win_count,
            )
            if cfg_mgr.is_streaming_enabled():
                try:
                    storage.save_snapshot(snapshot, top_n=top_processes)
                except Exception as db_err:
                    logger.warning(f'Ошибка сохранения снимка в SQLite: {db_err}')

            # Сбор и сохранение среза утечек ресурсов процессов (Handles, GDI, USER, Page Faults) по расписанию из config.json
            leaks_every_n = max(1, int(cfg_mgr.get_threshold('leaks_scan_every_n_ticks', 10.0)))
            if deep_diag and storage and (tick == 1 or tick % leaks_every_n == 0):
                try:
                    leaks_rep = deep_diag.collect_process_leaks(limit=100)
                    snap_leaks_id = f"snap_leaks_{int(time.time())}"
                    storage.save_process_leak_snapshot(snap_leaks_id, leaks_rep)
                except Exception as leak_err:
                    logger.debug(f'Ошибка сбора/сохранения утечек процессов на тике: {leak_err}')

            # Формирование информативного пошагового лога тика и сохранение форензики
            if deep_diag:
                try:
                    win_info, idle_sec = deep_diag.get_foreground_window_fast()
                    forensics_hb_ttl = cfg_mgr.get_cache_ttl('forensics_userassist_ttl_sec', 300.0)
                    cur_win_key = (win_info.get("title", "") if win_info else "", win_info.get("pid", 0) if win_info else 0)
                    if cur_win_key != last_forensics_window or (now_sec - last_forensics_time >= forensics_hb_ttl):
                        forensics = deep_diag.collect_forensics_activity()
                        snap_forensics_id = f"snap_forensics_{int(time.time())}_{win_info.get('pid', 0) if win_info else 0}"
                        storage.save_forensics_snapshot(snap_forensics_id, {
                            "foreground_window_title": win_info.get("title", "") if win_info else "",
                            "foreground_process_name": win_info.get("process_name", "") if win_info else "",
                            "foreground_pid": win_info.get("pid", 0) if win_info else 0,
                            "user_idle_seconds": int(idle_sec),
                            "camera_active_apps": forensics.camera_active_apps,
                            "microphone_active_apps": forensics.microphone_active_apps,
                            "userassist_top_apps": forensics.userassist_top_apps,
                        })
                        last_forensics_window = cur_win_key
                        last_forensics_time = now_sec
                except Exception as f_err:
                    logger.debug(f'Ошибка сбора/сохранения форензики: {f_err}')

            logger.console(f"тик {tick} ", text_color="gray")

            # Асинхронный запуск тяжелых стартовых опросов сразу после завершения первого тика
            if tick == 1 and not once:
                _trigger_heavy_worker(is_startup=True)

            # Автоматическое переключение из тяжелого режима в легкий при непрерывной работе 5 дней (432 000с)
            if auto_switch_enabled and heavy_mode_start_time is not None and mode.lower() in ('full', 'heavy'):
                if now_sec - heavy_mode_start_time >= max_heavy_duration_sec:
                    days_run = round((now_sec - heavy_mode_start_time) / (24 * 3600), 1)
                    logger.warning(
                        f"⏳ [АВТО-ПЕРЕКЛЮЧЕНИЕ] Телеметрия непрерывно работала {days_run} дн. в тяжелом режиме ({mode.upper()}). "
                        f"Для оптимизации ресурсов режим автоматически переключен в легкий (LIGHT)."
                    )
                    mode = 'light'
                    heavy_mode_start_time = None

            # Независимые интервалы опроса тяжелых сенсоров
            heavy_intervals = cfg_mgr.get_heavy_polls_intervals()
            hw_int = heavy_intervals.get('hardware_audit_interval_sec', 60.0)
            ports_int = heavy_intervals.get('network_ports_interval_sec', 30.0)
            net_act_int = heavy_intervals.get('network_activity_interval_sec', 30.0)
            leaks_int = heavy_intervals.get('handles_interval_sec', 30.0)
            smart_int = heavy_intervals.get('disk_scan_interval_sec', 43200.0)
            proc_sync_int = heavy_intervals.get('process_activity_sync_interval_sec', 60.0)
            startup_int = heavy_intervals.get('startup_audit_interval_sec', 0.0)
            software_int = heavy_intervals.get('software_audit_interval_sec', 0.0)
            internet_speed_int = heavy_intervals.get('internet_speed_interval_sec', 3600.0)

            if mode.lower() in ('hybrid', 'full') and tick > 1:
                if hw_int > 0 and h_collectors.get('hardware_sensors', True) and (now_sec - last_hw_sensors_time >= hw_int):
                    last_hw_sensors_time = now_sec
                    _trigger_granular_collector('hw_sensors')

                if ports_int > 0 and (h_collectors.get('listening_ports', True) or h_collectors.get('system_snapshot', True)) and (now_sec - last_ports_time >= ports_int):
                    last_ports_time = now_sec
                    _trigger_granular_collector('listening_ports')

                if net_act_int > 0 and h_collectors.get('network_activity', True) and (now_sec - last_net_activity_time >= net_act_int):
                    last_net_activity_time = now_sec
                    _trigger_granular_collector('network_activity')

                if leaks_int > 0 and h_collectors.get('process_leaks', True) and (now_sec - last_leaks_time >= leaks_int):
                    last_leaks_time = now_sec
                    _trigger_granular_collector('process_leaks')

                if smart_int > 0 and (h_collectors.get('deep_disk_smart', True) or h_collectors.get('storage_smart', True)) and (now_sec - last_smart_scan_time >= smart_int):
                    last_smart_scan_time = now_sec
                    _trigger_granular_collector('smart_disks')

                if proc_sync_int > 0 and h_collectors.get('process_activity', True) and (now_sec - last_proc_activity_time >= proc_sync_int):
                    last_proc_activity_time = now_sec
                    _trigger_granular_collector('process_activity')

                if internet_speed_int > 0 and (h_collectors.get('internet_speed', True) or h_collectors.get('network', True)) and (now_sec - last_internet_speed_time >= internet_speed_int):
                    last_internet_speed_time = now_sec
                    _trigger_granular_collector('internet_speed')

            # Каскадное усреднение снимков (5с -> 30с -> 3м -> 10м -> 36ч)
            if now_sec - last_tiered_compaction_time >= 30.0:
                try:
                    storage.flush()
                    comp_res = storage.run_tiered_compaction(
                        thorough_mode=cfg_mgr.is_thorough_mode(),
                        now_epoch=now_sec,
                    )
                    if not comp_res.get('skipped'):
                        s30 = comp_res.get('step_30s', {})
                        if s30.get('rollups_created', 0) > 0:
                            logger.console(
                                f"🧹 [Усреднение телеметрии] 30с бакеты: +{s30.get('rollups_created')}, "
                                f"очищено сырых: {s30.get('snapshots_deleted')} снимков, "
                                f"{s30.get('procs_deleted')} процессов, {s30.get('sensors_deleted')} сенсоров"
                            )
                    last_tiered_compaction_time = now_sec
                except Exception as comp_err:
                    logger.debug(f"Ошибка каскадного усреднения телеметрии: {comp_err}")

            # Фоновый периодический контроль размера SQLite базы данных telemetry.db
            if now_sec - last_db_cleanup_time >= db_cleanup_interval_sec:
                try:
                    prune_res = storage.enforce_size_limit()
                    if prune_res.get('pruned'):
                        logger.warning(
                            f"🗄️ [КОНТРОЛЬ РАЗМЕРА БД] Усечение базы данных telemetry.db: "
                            f"{prune_res.get('initial_size_mb')} МБ -> {prune_res.get('final_size_mb')} МБ "
                            f"(удалено снимков: {prune_res.get('deleted_snapshots')})"
                        )
                    last_db_cleanup_time = now_sec
                except Exception as db_clean_err:
                    logger.debug(f"Ошибка периодического контроля размера БД: {db_clean_err}")

            # Фоновая периодическая многоуровневая SQL-агрегация (hourly -> daily -> weekly -> monthly -> yearly)
            if now_sec - last_aggregation_time >= aggregation_interval_sec:
                try:
                    storage.flush()
                    agg_res = storage.run_aggregation_pipeline()
                    h_cnt = agg_res.get('hourly', {}).get('buckets_aggregated', 0)
                    sp_cnt = agg_res.get('hourly', {}).get('spikes_recorded', 0)
                    if h_cnt > 0 or sp_cnt > 0:
                        logger.console(f"📈 [SQL АГРЕГАЦИЯ] Обновлены бакеты: hourly={h_cnt}, зафиксировано всплесков={sp_cnt}")
                    last_aggregation_time = now_sec
                except Exception as agg_err:
                    logger.debug(f"Ошибка периодической SQL-агрегации: {agg_err}")

            if once:
                _execute_heavy_poll_job(is_startup=True)
                storage.flush()
                try:
                    storage.run_aggregation_pipeline()
                except Exception:
                    pass
                logger.info('⚡ Однократный опрос системной телеметрии успешно выполнен (--once)')
                break

            elapsed = time.time() - loop_start
            sleep_time = max(0.05, interval - elapsed)
            if _stop_event.wait(timeout=sleep_time):
                logger.info('Получен сигнал остановки (_stop_event установлен)')
                break
    except KeyboardInterrupt:
        logger.info('Прервано пользователем (KeyboardInterrupt)')
    except Exception as ex:
        logger.error(f'Критическая ошибка в цикле телеметрии: {ex}', exc_info=True)
    finally:
        if w64_collector:
            try:
                w64_collector.stop()
            except Exception:
                pass
        if w64_etw_collector:
            try:
                w64_etw_collector.stop()
            except Exception:
                pass
        logger.info('Процесс телеметрии успешно завершен')
    return 0

def run_minimal_telemetry(interval: float=5.0, top_processes: int=10, log_dir: Optional[str]=None) -> int:
    """Обертка для обратной совместимости: запуск в режиме minimal."""
    return run_telemetry_service(mode='minimal', interval=interval, top_processes=top_processes, log_dir=log_dir)

def main() -> int:
    """Главная точка входа службы системной телеметрии Windows.

    Returns:
        int: Код завершения.
    """
    args = parse_arguments()
    if args.verbose:
        logger.setLevel('DEBUG')

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    from .telemetry_config import TelemetryConfigManager
    try:
        config_manager = TelemetryConfigManager(config_path=args.config)
    except Exception as e:
        logger.warning(f'Не удалось загрузить конфигурацию ({e}), используются значения по умолчанию')
        config_manager = None
    if args.minimal:
        mode = 'minimal'
    elif args.mode:
        mode = args.mode
    elif config_manager:
        mode = config_manager.get_mode()
    else:
        mode = 'hybrid'
    interval = args.interval or (config_manager.get_interval_seconds() if config_manager else 5.0)
    heavy_interval = args.heavy_interval or (config_manager.get_heavy_interval_seconds() if config_manager else 60.0)
    top_processes = args.top_processes or (config_manager.get_effective_process_limit() if config_manager else 10)
    heavy_collectors = config_manager.get_heavy_collectors() if config_manager else None
    return run_telemetry_service(
        mode=mode,
        interval=interval,
        heavy_interval=heavy_interval,
        top_processes=top_processes,
        heavy_collectors=heavy_collectors,
        log_dir=args.log_dir,
        config_path=args.config,
        once=args.once,
    )


if __name__ == '__main__':
    sys.exit(main())

