# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry - Telemetry Config
# =============================================================================
# Description:
#   Менеджер конфигурации сбора телеметрии и сенсоров с поддержкой
#   динамического перечитывания config.json на лету.
#
# Usage Examples:
#   Python API:
#     from apps.windows.telemetry.telemetry_config import TelemetryConfigManager
#
#     config_mgr = TelemetryConfigManager()
#     interval = config_mgr.get_interval_seconds()
#     if config_mgr.check_and_reload():
#         print("Конфигурация обновлена!")
#
# File: telemetry_config.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-30 12:55:00
# =============================================================================

from __future__ import annotations
"""Менеджер конфигурации сбора телеметрии и сенсоров."""

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional
try:
    from logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


def get_default_telemetry_config_path() -> Path:
    """Возвращает путь по умолчанию к файлу конфигурации телеметрии в %ProgramData%.

    Проверяет сначала %ProgramData%/AITelemetry/config/config.json,
    затем %ProgramData%/AI-Windows-Admin/apps/windows/telemetry/config.json.
    Если целевой файл отсутствует, выполняется попытка скопировать шаблон из пакета модуля.

    Returns:
        Path: Путь к файлу конфигурации в %ProgramData%.
    """
    programdata = os.environ.get('ProgramData') or os.environ.get('ALLUSERSPROFILE')
    if programdata and os.path.exists(programdata):
        base_dir = Path(programdata)
    else:
        appdata = os.environ.get('APPDATA') or os.environ.get('LOCALAPPDATA')
        if appdata and os.path.exists(appdata):
            base_dir = Path(appdata)
        else:
            base_dir = Path.home() / '.config'

    ai_tel_config = base_dir / 'AITelemetry' / 'config' / 'config.json'
    if ai_tel_config.is_file():
        return ai_tel_config

    app_name = os.environ.get('APP_NAME') or 'ai-tc'
    target_path = base_dir / app_name / 'telemetry' / 'config.json'

    if not target_path.exists():
        bundled_template = Path(__file__).parent / 'config.json'
        if bundled_template.is_file():
            try:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(bundled_template, target_path)
            except Exception:
                return bundled_template
    return target_path


def parse_interval_to_seconds(val: Any, default: float = 5.0, allow_zero: bool = False) -> float:
    """Преобразует строковое или числовое значение интервала в секунды (float).

    Поддерживает:
        - Числа (int, float): 5 -> 5.0, 0 -> 0.0 (при allow_zero=True)
        - Строковые числа: "5", "5.0", "0" -> 5.0 / 0.0
        - Строки с единицами времени:
            - Секунды: "5s", "5 seconds", "5 сек", "5 секунд" -> 5.0
            - Минуты: "1m", "1 minute", "5 minutes", "2 мин" -> 60.0 / 300.0 / 120.0
            - Часы: "1h", "1 hour", "6 hours", "1 час" -> 3600.0 / 21600.0
            - Дни: "1d", "1 day", "7 days", "1 день" -> 86400.0 / 604800.0

    Args:
        val: Значение интервала из конфигурации.
        default: Значение по умолчанию в секундах.
        allow_zero: Разрешить возврат 0.0 для режимов 'только при старте / отключено'.

    Returns:
        float: Интервал в секундах (минимум 0.001 при allow_zero=False).
    """
    if val is None:
        return float(default)
    min_val = 0.0 if allow_zero else 0.001
    if isinstance(val, (int, float)):
        return max(min_val, float(val))
    if isinstance(val, str):
        val_str = val.strip().lower()
        if not val_str:
            return float(default)
        try:
            return max(min_val, float(val_str))
        except ValueError:
            pass
        match = re.match(r"^([\d.]+)\s*([a-zа-я]+)?$", val_str)
        if match:
            try:
                num = float(match.group(1))
                unit = match.group(2) or "s"
                if unit in ("s", "sec", "second", "seconds", "сек", "секунд", "секунды", "секунда"):
                    return max(min_val, num)
                elif unit in ("m", "min", "minute", "minutes", "мин", "минут", "минуты", "минута"):
                    return max(min_val, num * 60.0)
                elif unit in ("h", "hr", "hour", "hours", "ч", "час", "часа", "часов"):
                    return max(min_val, num * 3600.0)
                elif unit in ("d", "day", "days", "д", "день", "дня", "дней"):
                    return max(min_val, num * 86400.0)
            except ValueError:
                pass
    return float(default)


class TelemetryConfigManager:
    """Менеджер конфигурации для централизованного управления сенсорами и интервалами."""

    def __init__(self, config_path: Optional[str] = None) -> None:
        """Инициализирует менеджер конфигурации.

        Args:
            config_path: Путь к файлу конфигурации (по умолчанию: %APPDATA%/AI-Windows-Admin/apps/windows/telemetry/config.json).
        """
        if config_path:
            self._config_path = str(config_path)
        else:
            self._config_path = str(get_default_telemetry_config_path())
        self._config: Dict[str, Any] = {}
        self._sensors_config: Dict[str, Dict[str, Any]] = {}
        self._loggers_config: Dict[str, Dict[str, Any]] = {}
        self._default_interval = 5.0
        self._fast_interval = 30.0
        self._fast_duration_days = 2
        self._aggregation_interval = 3600.0
        self._heavy_interval = 60.0
        self._heavy_disk_scan_interval = 43200.0
        self._heavy_mode_max_duration_days = 5.0
        self._heavy_mode_auto_switch_enabled = True
        self._mode = 'hybrid'
        self._telemetry_mode = 'telemetry'
        self._standard_flush_interval_seconds = 30.0
        self._tc_flush_interval_seconds = 5.0
        self._tc_mode_timeout_seconds = 300.0
        self._tc_mode_activated_at: Optional[float] = None
        self._max_db_size_mb = 100.0
        self._retention_days = 7
        self._db_cleanup_interval_seconds = 300.0
        self._flush_interval_seconds = 30.0
        self._auto_vacuum_enabled = True
        self._enable_foreground_window = True
        self._last_mtime_ns: int = 0
        self._load_config()

    def _load_config(self) -> None:
        """Загружает конфигурацию из JSON файла с фиксацией времени модификации."""
        try:
            cfg_path = Path(self._config_path)
            if cfg_path.is_file():
                self._last_mtime_ns = cfg_path.stat().st_mtime_ns
            with open(self._config_path, 'r', encoding='utf-8') as f:
                new_config = json.load(f)
                
            self._config = new_config
            if 'sensors' in self._config:
                self._sensors_config = self._config.get('sensors', {})
            elif 'telemetry' in self._config and 'sensors' in self._config['telemetry']:
                self._sensors_config = self._config['telemetry'].get('sensors', {})
            else:
                self._sensors_config = {}

            self._loggers_config = self._config.get('loggers', {})

            raw_interval = self._config.get('light_poll_interval_seconds', self._config.get('interval_seconds', self._config.get('interval', self._config.get('telemetry', {}).get('interval_seconds', 5.0))))
            self._default_interval = parse_interval_to_seconds(raw_interval, 5.0)

            raw_heavy = self._config.get('heavy_poll_interval_seconds', self._config.get('heavy_interval_seconds', self._config.get('heavy_interval', self._config.get('telemetry', {}).get('heavy_interval_seconds', 90.0))))
            self._heavy_interval = parse_interval_to_seconds(raw_heavy, 90.0)

            # Детальные интервалы для каждого типа тяжелого опроса
            heavy_polls = self._config.get('heavy_polls_intervals', {})
            if not isinstance(heavy_polls, dict):
                heavy_polls = {}

            self._hardware_audit_interval_sec = parse_interval_to_seconds(
                heavy_polls.get('hardware_audit_interval_sec', self._config.get('hardware_audit_interval_sec', 60.0)),
                60.0
            )
            self._startup_audit_interval_sec = parse_interval_to_seconds(
                heavy_polls.get('startup_audit_interval_sec', self._config.get('startup_audit_interval_sec', 0.0)),
                0.0,
                allow_zero=True
            )
            self._extended_audit_interval_sec = parse_interval_to_seconds(
                heavy_polls.get('extended_audit_interval_sec', self._config.get('extended_audit_interval_sec', 300.0)),
                300.0
            )
            self._defender_audit_interval_sec = parse_interval_to_seconds(
                heavy_polls.get('defender_audit_interval_sec', self._config.get('defender_audit_interval_sec', 120.0)),
                120.0
            )
            self._process_activity_sync_interval_sec = parse_interval_to_seconds(
                heavy_polls.get('process_activity_sync_interval_sec', self._config.get('process_activity_sync_interval_sec', 60.0)),
                60.0
            )
            self._software_audit_interval_sec = parse_interval_to_seconds(
                heavy_polls.get('software_audit_interval_sec', self._config.get('software_audit_interval_sec', 0.0)),
                0.0,
                allow_zero=True
            )
            self._network_activity_interval_sec = parse_interval_to_seconds(
                heavy_polls.get('network_activity_interval_sec', self._config.get('network_activity_interval_sec', 30.0)),
                30.0
            )
            self._network_ports_interval_sec = parse_interval_to_seconds(
                heavy_polls.get('network_ports_interval_sec', self._config.get('network_ports_interval_sec', 30.0)),
                30.0
            )
            self._handles_interval_sec = parse_interval_to_seconds(
                heavy_polls.get('handles_interval_sec', self._config.get('handles_interval_sec', 30.0)),
                30.0
            )

            raw_disk_interval = heavy_polls.get('disk_scan_interval_sec', self._config.get('heavy_disk_scan_interval_seconds'))
            self._heavy_disk_scan_interval = parse_interval_to_seconds(raw_disk_interval, 43200.0)

            raw_fast_interval = self._config.get('fast_interval_seconds')
            self._fast_interval = parse_interval_to_seconds(raw_fast_interval, 30.0)

            self._fast_duration_days = int(self._config.get('fast_duration_days', 2))

            raw_agg = self._config.get('aggregation_interval_seconds', self._config.get('rollup_interval_seconds'))
            self._aggregation_interval = parse_interval_to_seconds(raw_agg, 3600.0)

            raw_max_days = self._config.get('heavy_mode_max_duration_days')
            self._heavy_mode_max_duration_days = float(raw_max_days) if raw_max_days is not None else 5.0

            self._heavy_mode_auto_switch_enabled = bool(self._config.get('heavy_mode_auto_switch_enabled', True))
            self._mode = str(self._config.get('mode', self._config.get('telemetry', {}).get('mode', 'hybrid'))).lower()

            # Audit запускается на старте телеметрии в любом случае
            self._audit_enabled = bool(self._config.get('audit_enabled', True))

            # Стриминг можно отключать отдельно от аудита или запускать оба процесса одновременно
            raw_streaming = self._config.get('streaming_enabled', self._config.get('live_stream_enabled'))
            raw_tel_mode = str(self._config.get('telemetry_mode', self._config.get('profile', 'audit'))).lower()

            if raw_streaming is not None:
                self._streaming_enabled = bool(raw_streaming)
            else:
                self._streaming_enabled = raw_tel_mode in ('live_stream', 'live', 'streaming', 'both', 'all')

            if raw_tel_mode in ('both', 'all', 'streaming_and_audit'):
                self._telemetry_mode = 'both'
                self._streaming_enabled = True
                self._audit_enabled = True
            elif raw_tel_mode in ('live_stream', 'live', 'streaming'):
                self._telemetry_mode = 'both' if self._audit_enabled else 'live_stream'
                self._streaming_enabled = True
            elif raw_tel_mode in ('tc',):
                self._telemetry_mode = 'tc'
                self._streaming_enabled = True
            elif raw_tel_mode in ('audit', 'process_audit', 'telemetry'):
                self._telemetry_mode = 'audit'
                if raw_streaming is None:
                    self._streaming_enabled = False
            else:
                self._telemetry_mode = 'both' if (self._audit_enabled and self._streaming_enabled) else ('live_stream' if self._streaming_enabled else 'audit')

            raw_target_pid = self._config.get('audit_target_pid')
            try:
                self._audit_target_pid = int(raw_target_pid) if raw_target_pid is not None else None
            except (ValueError, TypeError):
                self._audit_target_pid = None

            raw_audit_interval = self._config.get('audit_interval_sec', self._config.get('audit_interval_seconds', 1.0))
            self._audit_interval_sec = parse_interval_to_seconds(raw_audit_interval, 1.0)

            raw_std_flush = self._config.get('standard_flush_interval_seconds', self._config.get('flush_interval_seconds', 30.0))
            self._standard_flush_interval_seconds = parse_interval_to_seconds(raw_std_flush, 30.0)

            raw_tc_flush = self._config.get('tc_flush_interval_seconds', 5.0)
            self._tc_flush_interval_seconds = parse_interval_to_seconds(raw_tc_flush, 5.0)

            raw_tc_timeout = self._config.get('tc_mode_timeout_seconds', self._config.get('tc_timeout_seconds', 300.0))
            self._tc_mode_timeout_seconds = parse_interval_to_seconds(raw_tc_timeout, 300.0)

            raw_tc_act = self._config.get('tc_mode_activated_at')
            try:
                self._tc_mode_activated_at = float(raw_tc_act) if raw_tc_act is not None else None
            except (ValueError, TypeError):
                self._tc_mode_activated_at = None

            raw_max_db = self._config.get('max_db_size_mb', self._config.get('max_file_size_mb', 100.0))
            self._max_db_size_mb = float(raw_max_db) if raw_max_db is not None else 100.0

            raw_retention = self._config.get('retention_days', 7)
            self._retention_days = int(raw_retention) if raw_retention is not None else 7

            raw_cleanup_interval = self._config.get('db_cleanup_interval_seconds')
            self._db_cleanup_interval_seconds = parse_interval_to_seconds(raw_cleanup_interval, 300.0)

            if self._telemetry_mode == 'tc':
                self._flush_interval_seconds = self._tc_flush_interval_seconds
            else:
                self._flush_interval_seconds = self._standard_flush_interval_seconds

            self._auto_vacuum_enabled = bool(self._config.get('auto_vacuum_enabled', True))
            self._enable_foreground_window = bool(self._config.get('enable_foreground_window', True))
            self._thorough_mode = bool(self._config.get('thorough_mode', False))

            # Независимые интервалы опроса коллекторов (03_TELEMETRY.md и heavy_polls_intervals)
            self._wmi_interval_sec = parse_interval_to_seconds(
                heavy_polls.get('wmi_interval_sec', self._config.get('wmi_interval_sec', 120.0)), 120.0
            )
            self._smart_interval_sec = parse_interval_to_seconds(
                heavy_polls.get('smart_interval_sec', self._config.get('smart_interval_sec', 300.0)), 300.0
            )
            self._handles_interval_sec = parse_interval_to_seconds(
                heavy_polls.get('handles_interval_sec', self._config.get('handles_interval_sec', 60.0)), 60.0
            )
            self._network_ports_interval_sec = parse_interval_to_seconds(
                heavy_polls.get('network_ports_interval_sec', self._config.get('network_ports_interval_sec', 30.0)), 30.0
            )
            self._network_activity_interval_sec = parse_interval_to_seconds(
                heavy_polls.get('network_activity_interval_sec', self._config.get('network_activity_interval_sec', 60.0)), 60.0
            )
        except FileNotFoundError:
            if not self._config:
                self._config = {}
                self._sensors_config = {}
                self._loggers_config = {}
                self._default_interval = 5.0
                self._heavy_interval = 60.0
                self._heavy_disk_scan_interval = 43200.0
                self._heavy_mode_max_duration_days = 5.0
                self._heavy_mode_auto_switch_enabled = True
                self._mode = 'audit'
                self._telemetry_mode = 'audit'
                self._audit_enabled = True
                self._streaming_enabled = False
                self._max_db_size_mb = 50.0
                self._retention_days = 7
                self._db_cleanup_interval_seconds = 300.0
                self._flush_interval_seconds = 30.0
                self._auto_vacuum_enabled = True
        except (json.JSONDecodeError, OSError, PermissionError) as e:
            if not self._config:
                raise ValueError(f'Ошибка парсинга {self._config_path}: {e}')
            logger.warning(f'Временная ошибка считывания {self._config_path} на лету: {e}')

    @property
    def config_path(self) -> str:
        """Возвращает путь к активному файлу конфигурации."""
        return self._config_path

    def check_and_reload(self) -> bool:
        """Проверяет модификацию файла config.json на диске и перезагружает параметры 'на лету'.

        Returns:
            bool: True если конфигурация изменилась и успешно перезагружена, иначе False.
        """
        try:
            cfg_path = Path(self._config_path)
            if not cfg_path.is_file():
                return False
            current_mtime_ns = cfg_path.stat().st_mtime_ns
            if current_mtime_ns != self._last_mtime_ns:
                self._load_config()
                return True
        except Exception as e:
            logger.debug(f'Проверка модификации config.json: {e}')
        return False

    def reload(self) -> None:
        """Принудительно перезагружает конфигурацию из файла."""
        self._load_config()

    def get_data_path(self) -> Path:
        """Возвращает настроенный или системный путь к директории хранения данных телеметрии."""
        custom = self._config.get('data_path') or self._config.get('data_dir')
        if not custom and isinstance(self._config.get('storage'), dict):
            custom = self._config['storage'].get('data_path') or self._config['storage'].get('data_dir')
        if custom:
            return Path(os.path.expandvars(str(custom)))
        programdata = os.environ.get('ProgramData') or os.environ.get('ALLUSERSPROFILE')
        if programdata and os.path.exists(programdata):
            base_dir = Path(programdata)
        else:
            appdata = os.environ.get('APPDATA') or os.environ.get('LOCALAPPDATA')
            if appdata and os.path.exists(appdata):
                base_dir = Path(appdata)
            else:
                base_dir = Path.home() / '.config'
        app_name = os.environ.get('APP_NAME') or 'ai-tc'
        return base_dir / app_name / 'telemetry'

    def get_db_path(self) -> Path:
        """Возвращает настроенный или системный путь к файлу SQLite базы данных телеметрии."""
        if isinstance(self._config.get('storage'), dict):
            custom_db = self._config['storage'].get('db_path')
            if custom_db:
                return Path(os.path.expandvars(str(custom_db)))
        custom_db = self._config.get('db_path')
        if custom_db:
            return Path(os.path.expandvars(str(custom_db)))
        return self.get_data_path() / 'telemetry.db'

    def get_fast_interval(self) -> float:
        """Возвращает интервал быстрого режима (сек)."""
        return getattr(self, '_fast_interval', 30.0)

    def get_fast_duration_days(self) -> int:
        """Возвращает длительность быстрого режима в днях."""
        return getattr(self, '_fast_duration_days', 2)

    def get_aggregation_interval(self) -> float:
        """Возвращает интервал агрегации (сек)."""
        return getattr(self, '_aggregation_interval', 3600.0)

    def get_mode(self) -> str:
        """Возвращает режим сбора: minimal, hybrid, full."""
        return self._mode if self._mode in ('minimal', 'hybrid', 'full') else 'hybrid'

    def get_interval_seconds(self) -> float:
        """Возвращает быстрый базовый интервал сбора телеметрии."""
        return self._default_interval

    def get_light_poll_interval_seconds(self) -> float:
        """Возвращает интервал тиков для легких опросов (базовый поток live stream)."""
        return self._default_interval

    def get_heavy_interval_seconds(self) -> float:
        """Возвращает периодический интервал тяжелых сенсоров."""
        return self._heavy_interval

    def get_heavy_poll_interval_seconds(self) -> float:
        """Возвращает общий базовый интервал тиков для тяжелых опросов."""
        return self._heavy_interval

    def get_hardware_audit_interval_seconds(self) -> float:
        """Возвращает интервал аудита аппаратного оборудования (железа)."""
        return getattr(self, '_hardware_audit_interval_sec', 60.0)

    def get_startup_audit_interval_seconds(self) -> float:
        """Возвращает интервал аудита автозапуска Windows (0.0 = только при старте программы)."""
        return getattr(self, '_startup_audit_interval_sec', 0.0)

    def get_extended_audit_interval_seconds(self) -> float:
        """Возвращает интервал расширенного системного аудита."""
        return getattr(self, '_extended_audit_interval_sec', 300.0)

    def get_defender_audit_interval_seconds(self) -> float:
        """Возвращает интервал аудита безопасности и Microsoft Defender."""
        return getattr(self, '_defender_audit_interval_sec', 120.0)

    def get_process_activity_sync_interval_seconds(self) -> float:
        """Возвращает интервал синхронизации активности процессов ProcessActivityEngine."""
        return getattr(self, '_process_activity_sync_interval_sec', 60.0)

    def get_software_audit_interval_seconds(self) -> float:
        """Возвращает интервал периодического аудита установленного ПО (0.0 = только при старте программы)."""
        return getattr(self, '_software_audit_interval_sec', 0.0)

    def get_heavy_polls_intervals(self) -> Dict[str, float]:
        """Возвращает словарь всех индивидуальных интервалов для тяжелых опросов."""
        return {
            'hardware_audit_interval_sec': self.get_hardware_audit_interval_seconds(),
            'startup_audit_interval_sec': self.get_startup_audit_interval_seconds(),
            'extended_audit_interval_sec': self.get_extended_audit_interval_seconds(),
            'defender_audit_interval_sec': self.get_defender_audit_interval_seconds(),
            'process_activity_sync_interval_sec': self.get_process_activity_sync_interval_seconds(),
            'software_audit_interval_sec': self.get_software_audit_interval_seconds(),
            'wmi_interval_sec': self.get_wmi_interval_seconds(),
            'smart_interval_sec': self.get_smart_interval_seconds(),
            'handles_interval_sec': self.get_handles_interval_seconds(),
            'network_ports_interval_sec': self.get_network_ports_interval_seconds(),
            'network_activity_interval_sec': self.get_network_activity_interval_seconds(),
            'disk_scan_interval_sec': self.get_heavy_disk_scan_interval(),
        }

    def is_thorough_mode(self) -> bool:
        """Возвращает флаг режима тщательного сбора (True = сбор всех точек без усреднения)."""
        return getattr(self, '_thorough_mode', False)

    def set_thorough_mode(self, enabled: bool) -> bool:
        """Устанавливает флаг режима тщательного сбора в конфигурации."""
        self._thorough_mode = bool(enabled)
        return self.save_config({'thorough_mode': bool(enabled)})

    def get_network_activity_interval_seconds(self) -> float:
        """Возвращает интервал аудита сетевых соединений процессов (в секундах)."""
        return getattr(self, '_network_activity_interval_sec', 30.0)

    def get_wmi_interval_seconds(self) -> float:
        """Возвращает интервал аудита WMI и оборудования (в секундах)."""
        return getattr(self, '_wmi_interval_sec', 120.0)

    def get_smart_interval_seconds(self) -> float:
        """Возвращает интервал проверки SMART накопителей (в секундах)."""
        return getattr(self, '_smart_interval_sec', 300.0)

    def get_handles_interval_seconds(self) -> float:
        """Возвращает интервал сбора дескрипторов и процессов (в секундах)."""
        return getattr(self, '_handles_interval_sec', 30.0)

    def get_network_ports_interval_seconds(self) -> float:
        """Возвращает интервал сбора сетевых сокетов и портов (в секундах)."""
        return getattr(self, '_network_ports_interval_sec', 30.0)

    def get_heavy_disk_scan_interval(self) -> float:
        """Возвращает интервал тяжелой проверки дисков (в секундах)."""
        return getattr(self, '_heavy_disk_scan_interval', 43200.0)

    def get_heavy_mode_max_duration_days(self) -> float:
        """Возвращает максимальную непрерывную длительность тяжелого режима (в днях)."""
        return getattr(self, '_heavy_mode_max_duration_days', 5.0)

    def is_heavy_auto_switch_enabled(self) -> bool:
        """Возвращает флаг разрешения автопереключения тяжелого режима в легкий."""
        return getattr(self, '_heavy_mode_auto_switch_enabled', True)

    def get_heavy_collectors(self) -> Dict[str, bool]:
        """Возвращает словарь флагов включения тяжелых коллекторов."""
        default_heavy = {
            'hardware_sensors': True,
            'deep_disk_smart': True,
            'system_snapshot': True,
            'hardware_tree': True,
        }
        custom = self._config.get('heavy_collectors', {})
        if isinstance(custom, dict):
            default_heavy.update(custom)
        return default_heavy

    def get_top_processes(self) -> int:
        """Возвращает число сохраняемых процессов с наибольшей нагрузкой."""
        return int(self._config.get('top_processes', 25))

    def get_buffer_mode(self) -> str:
        """Возвращает режим буферизации телеметрии ('memory', 'file', 'direct')."""
        mode = str(self._config.get('buffer_mode', 'memory')).lower()
        return mode if mode in ('memory', 'file', 'direct') else 'memory'

    def get_buffer_size(self) -> int:
        """Возвращает максимальный размер буфера перед принудительным сбросом в БД."""
        try:
            val = int(self._config.get('buffer_size', 50))
            return max(1, val)
        except (ValueError, TypeError):
            return 50

    def is_audit_enabled(self) -> bool:
        """Проверяет, активен ли сбор аудита (Audit запускается на старте телеметрии в любом случае)."""
        return getattr(self, '_audit_enabled', True)

    def is_audit_mode(self) -> bool:
        """Проверяет, активен ли аудит системы или процесса."""
        return self.is_audit_enabled()

    def is_streaming_enabled(self) -> bool:
        """Проверяет, активен ли сбор стриминга метрик (потоковый опрос снимков системы)."""
        return getattr(self, '_streaming_enabled', False)

    def is_live_stream_mode(self) -> bool:
        """Проверяет, активен ли стриминг (live stream)."""
        return self.is_streaming_enabled()

    def get_telemetry_mode(self) -> str:
        """Возвращает текущий режим телеметрии: 'both', 'live_stream', 'audit' или 'tc'."""
        self.check_tc_mode_auto_switch()
        mode = getattr(self, '_telemetry_mode', None)
        if mode in ('tc',):
            return mode
        audit_on = self.is_audit_enabled()
        stream_on = self.is_streaming_enabled()
        if audit_on and stream_on:
            return 'both'
        if stream_on:
            return 'live_stream'
        return 'audit'

    def get_audit_target_pid(self) -> Optional[int]:
        """Возвращает целевой PID процесса для режима аудита."""
        return getattr(self, '_audit_target_pid', None)

    def get_audit_interval_sec(self) -> float:
        """Возвращает интервал сбора аудита процесса в секундах (по умолчанию 1.0с)."""
        return getattr(self, '_audit_interval_sec', 1.0)

    def activate_audit_mode(self, pid: Optional[int] = None, interval_sec: Optional[float] = None) -> bool:
        """Активирует аудит целевого процесса по PID или общий аудит. Стриминг при этом не отключается автоматически.

        Args:
            pid: Идентификатор процесса Windows (PID), опционально.
            interval_sec: Интервал сбора замеров аудита (сек).

        Returns:
            bool: True при успешной активации.
        """
        self._audit_enabled = True
        updates: Dict[str, Any] = {'audit_enabled': True}
        if pid is not None:
            self._audit_target_pid = int(pid)
            updates['audit_target_pid'] = self._audit_target_pid
        if interval_sec is not None:
            self._audit_interval_sec = max(0.1, float(interval_sec))
            updates['audit_interval_sec'] = self._audit_interval_sec
        self._telemetry_mode = self.get_telemetry_mode()
        updates['telemetry_mode'] = self._telemetry_mode
        logger.info(f"🎯 [Телеметрия] Аудит активен (PID={self._audit_target_pid}, интервал: {self.get_audit_interval_sec()}с)")
        return self.save_config(updates)

    def deactivate_audit_mode(self) -> bool:
        """Отключает процесс аудита."""
        self._audit_enabled = False
        self._audit_target_pid = None
        updates: Dict[str, Any] = {
            'audit_enabled': False,
            'audit_target_pid': None,
            'telemetry_mode': self.get_telemetry_mode(),
        }
        logger.info("⏸️ [Телеметрия] Процесс аудита отключен.")
        return self.save_config(updates)

    def activate_streaming_mode(self, interval_sec: Optional[float] = None) -> bool:
        """Активирует стриминг метрик реального времени. Аудит при этом продолжает работу.

        Args:
            interval_sec: Интервал сбора снимков метрик (сек).

        Returns:
            bool: True при успешной активации.
        """
        self._streaming_enabled = True
        updates: Dict[str, Any] = {
            'streaming_enabled': True,
            'live_stream_enabled': True,
        }
        if interval_sec is not None:
            self._interval_seconds = max(0.1, float(interval_sec))
            updates['interval_seconds'] = self._interval_seconds
        self._telemetry_mode = self.get_telemetry_mode()
        updates['telemetry_mode'] = self._telemetry_mode
        logger.info(f"📡 [Телеметрия] Стриминг метрик активирован (интервал: {self.get_interval_seconds()}с)")
        return self.save_config(updates)

    def activate_live_stream_mode(self, interval_sec: Optional[float] = None) -> bool:
        """Алиас для активации стриминга (live stream)."""
        return self.activate_streaming_mode(interval_sec=interval_sec)

    def deactivate_streaming_mode(self) -> bool:
        """Отключает стриминг метрик отдельно от аудита. Аудит продолжает работать.

        Returns:
            bool: True при успешном отключении.
        """
        self._streaming_enabled = False
        updates: Dict[str, Any] = {
            'streaming_enabled': False,
            'live_stream_enabled': False,
            'telemetry_mode': self.get_telemetry_mode(),
        }
        logger.info("⏸️ [Телеметрия] Стриминг отключен отдельно от аудита. Аудит продолжает работу.")
        return self.save_config(updates)

    def deactivate_live_stream_mode(self) -> bool:
        """Алиас для отключения стриминга (live stream)."""
        return self.deactivate_streaming_mode()

    def activate_both_mode(self, pid: Optional[int] = None, interval_sec: Optional[float] = None) -> bool:
        """Активирует оба процесса одновременно: и стриминг, и аудит.

        Args:
            pid: Идентификатор процесса Windows (PID) для аудита, если требуется.
            interval_sec: Интервал сбора замеров (сек).

        Returns:
            bool: True при успешной активации обоих процессов.
        """
        self._audit_enabled = True
        self._streaming_enabled = True
        updates: Dict[str, Any] = {
            'audit_enabled': True,
            'streaming_enabled': True,
            'live_stream_enabled': True,
            'telemetry_mode': 'both',
        }
        if pid is not None:
            self._audit_target_pid = int(pid)
            updates['audit_target_pid'] = self._audit_target_pid
        if interval_sec is not None:
            self._interval_seconds = max(0.1, float(interval_sec))
            updates['interval_seconds'] = self._interval_seconds
        self._telemetry_mode = 'both'
        logger.info("🚀 [Телеметрия] Активированы оба процесса одновременно: Стриминг и Аудит.")
        return self.save_config(updates)

    def set_telemetry_mode(
        self,
        mode: str,
        target_pid: Optional[int] = None,
        interval_sec: Optional[float] = None
    ) -> bool:
        """Устанавливает режим работы телеметрии: 'both', 'live_stream'/'streaming' или 'audit'.

        Args:
            mode: Режим ('both'/'all', 'live_stream'/'streaming', или 'audit'/'process_audit').
            target_pid: Целевой PID процесса (обязателен при режиме audit, если отслеживается процесс).
            interval_sec: Интервал сбора данных в секундах.

        Returns:
            bool: True при успешном сохранении конфигурации.
        """
        clean_mode = str(mode).lower().strip()
        if clean_mode in ('both', 'all', 'streaming_and_audit'):
            return self.activate_both_mode(pid=target_pid, interval_sec=interval_sec)
        elif clean_mode in ('audit', 'process_audit'):
            # В режиме 'audit' стриминг отключается отдельно от аудита
            self.deactivate_streaming_mode()
            return self.activate_audit_mode(pid=target_pid, interval_sec=interval_sec)
        else:
            # clean_mode in ('live_stream', 'streaming', 'live')
            # Стриминг активируется, аудит запускается на старте телеметрии в любом случае!
            self._audit_enabled = True
            return self.activate_streaming_mode(interval_sec=interval_sec)

    def check_tc_mode_auto_switch(self) -> bool:
        """Проверяет таймаут активного режима 'tc' (реальное время) и переключает в 'telemetry'.

        Returns:
            bool: True если произошло автопереключение в 'telemetry', иначе False.
        """
        if getattr(self, '_telemetry_mode', 'telemetry') == 'tc' and getattr(self, '_tc_mode_activated_at', None):
            import time
            elapsed = time.time() - self._tc_mode_activated_at
            timeout = getattr(self, '_tc_mode_timeout_seconds', 300.0)
            if elapsed >= timeout:
                self._telemetry_mode = 'telemetry'
                self._tc_mode_activated_at = None
                self._flush_interval_seconds = getattr(self, '_standard_flush_interval_seconds', 30.0)
                self.save_config({
                    'telemetry_mode': 'telemetry',
                    'tc_mode_activated_at': None
                })
                logger.info(
                    f"⏱️ [Телеметрия] Режим реального времени 'tc' завершен по таймауту ({int(timeout)}с). "
                    f"Автоматически переключен в стандартный режим 'telemetry' (flush: {self._flush_interval_seconds}с, max_db: {self.get_max_db_size_mb()}МБ)"
                )
                return True
        return False

    def activate_tc_mode(self, duration_seconds: Optional[float] = None, flush_interval_seconds: Optional[float] = None) -> bool:
        """Активирует режим отображения телеметрии реального времени ('tc') с задержкой сброса в N сек.

        Args:
            duration_seconds: Длительность режима TC в секундах до автопереключения в telemetry (по умолчанию 300с = 5 мин).
            flush_interval_seconds: Интервал сброса в БД в секундах (по умолчанию 5.0с).

        Returns:
            bool: True при успешной активации.
        """
        import time
        self._telemetry_mode = 'tc'
        self._tc_mode_activated_at = time.time()
        if flush_interval_seconds is not None:
            self._tc_flush_interval_seconds = max(0.1, float(flush_interval_seconds))
        if duration_seconds is not None:
            self._tc_mode_timeout_seconds = max(1.0, float(duration_seconds))
        self._flush_interval_seconds = self._tc_flush_interval_seconds

        updates: Dict[str, Any] = {
            'telemetry_mode': 'tc',
            'tc_mode_activated_at': self._tc_mode_activated_at,
            'tc_flush_interval_seconds': self._tc_flush_interval_seconds,
            'tc_mode_timeout_seconds': self._tc_mode_timeout_seconds,
        }
        logger.info(f"⚡ [Телеметрия] Активирован режим реального времени 'tc' (flush: {self._tc_flush_interval_seconds}с, таймаут: {self._tc_mode_timeout_seconds}с)")
        return self.save_config(updates)

    def deactivate_tc_mode(self) -> bool:
        """Деактивирует режим 'tc' и возвращает телеметрию в стандартный режим 'telemetry'."""
        self._telemetry_mode = 'telemetry'
        self._tc_mode_activated_at = None
        self._flush_interval_seconds = getattr(self, '_standard_flush_interval_seconds', 30.0)
        updates = {
            'telemetry_mode': 'telemetry',
            'tc_mode_activated_at': None,
        }
        logger.info(f"🔄 [Телеметрия] Переключено в стандартный режим 'telemetry' (flush: {self._flush_interval_seconds}с)")
        return self.save_config(updates)

    def get_standard_flush_interval_seconds(self) -> float:
        """Возвращает стандартный интервал сброса буфера в БД (по умолчанию 30с)."""
        return getattr(self, '_standard_flush_interval_seconds', 30.0)

    def get_tc_flush_interval_seconds(self) -> float:
        """Возвращает интервал сброса в режиме реального времени TC (по умолчанию 5с)."""
        return getattr(self, '_tc_flush_interval_seconds', 5.0)

    def get_tc_mode_timeout_seconds(self) -> float:
        """Возвращает таймаут действия режима TC до автопереключения в стандартный (в секундах, по умолчанию 300с)."""
        return getattr(self, '_tc_mode_timeout_seconds', 300.0)

    def get_flush_interval_seconds(self) -> float:
        """Возвращает периодический интервал сброса буфера в БД с учетом активного режима."""
        self.check_tc_mode_auto_switch()
        if getattr(self, '_telemetry_mode', 'telemetry') == 'tc':
            return getattr(self, '_tc_flush_interval_seconds', 5.0)
        return getattr(self, '_standard_flush_interval_seconds', 30.0)

    def get_multi_rate_config(self) -> Dict[str, Any]:
        """Возвращает настройки асинхронного многоскоростного ядра сбора телеметрии."""
        defaults: Dict[str, Any] = {
            'enabled': True,
            'level3_realtime_interval_seconds': 1.0,
            'level2_adaptive_initial_interval_seconds': 2.0,
            'level2_adaptive_min_interval_seconds': 0.5,
            'level2_adaptive_max_interval_seconds': 30.0,
            'level2_cooldown_ticks': 10,
            'level2_backoff_multiplier': 1.5,
            'level1_smart_interval_seconds': 43200.0,
            'level1_battery_interval_seconds': 900.0,
            'level1_security_interval_seconds': 3600.0,
            'level1_scm_interval_seconds': 1800.0,
            'level1_schedule_check_interval_seconds': 60.0,
            'wal_flush_interval_seconds': 5.0,
            'ring_buffer_capacity': 600,
            'ring_buffer_max_mb': 32,
            'deadband': {
                'temperature_c': 1.0,
                'cpu_load_pct': 3.0,
                'freq_mhz': 50.0,
                'power_w': 2.0,
                'fan_rpm': 100.0,
                'network_bytes': 10485760.0,
                'network_packets': 10000.0,
                'disk_space_gb': 0.5,
                'default_threshold': 2.0,
                'heartbeat_interval_seconds': 60.0,
                'ignore_cumulative_network_spikes': True,
            },
        }
        custom = self._config.get('multi_rate_engine', {})
        if isinstance(custom, dict):
            merged = dict(defaults)
            merged.update({k: v for k, v in custom.items() if k != 'deadband'})
            if isinstance(custom.get('deadband'), dict):
                db_merged = dict(defaults['deadband'])
                db_merged.update(custom['deadband'])
                merged['deadband'] = db_merged
            return merged
        return defaults

    def get_deadband_config(self) -> Dict[str, Any]:
        """Возвращает пороги Deadband для сенсоров."""
        mr = self.get_multi_rate_config()
        return mr.get('deadband', {})

    def get_cache_ttls_config(self) -> Dict[str, float]:
        """Возвращает словарь TTL кэширования сенсоров и коллекторов (в секундах)."""
        defaults: Dict[str, float] = {
            'acpi_thermal_ttl_sec': 15.0,
            'storage_smart_ttl_sec': 30.0,
            'cloud_storage_ttl_sec': 120.0,
            'internet_speed_ttl_sec': 1800.0,
            'network_adapter_stats_ttl_sec': 15.0,
            'physical_disks_health_ttl_sec': 43200.0,
            'forensics_consent_store_ttl_sec': 60.0,
            'forensics_userassist_ttl_sec': 300.0,
            'gpu_probe_ttl_sec': 10.0,
            'disk_partitions_ttl_sec': 60.0,
        }
        custom = self._config.get('cache_ttls', {})
        if isinstance(custom, dict):
            for k, v in custom.items():
                try:
                    defaults[k] = float(v)
                except (ValueError, TypeError):
                    pass
        return defaults

    def get_cache_ttl(self, key: str, default: float = 30.0) -> float:
        """Возвращает TTL кэша по ключу из секции cache_ttls."""
        return float(self.get_cache_ttls_config().get(key, default))

    def get_thresholds_config(self) -> Dict[str, float]:
        """Возвращает словарь диагностических порогов аномалий, утечек и нагрузки."""
        defaults: Dict[str, float] = {
            'incident_cpu_pct': 90.0,
            'incident_cpu_critical_pct': 95.0,
            'incident_disk_write_burst_mb_s': 100.0,
            'incident_net_burst_mb_s': 50.0,
            'incident_cooldown_seconds': 60.0,
            'incident_window_before_seconds': 300.0,
            'suspicious_temp_cpu_pct': 15.0,
            'suspicious_temp_critical_cpu_pct': 30.0,
            'individual_process_high_cpu_pct': 50.0,
            'leak_candidate_handles': 250.0,
            'leak_candidate_memory_mb': 80.0,
            'leak_warning_handles': 1500.0,
            'leak_critical_handles': 4000.0,
            'leak_severe_handles': 10000.0,
            'leak_warning_gdi': 800.0,
            'leak_critical_gdi': 2000.0,
            'leak_warning_user_objects': 500.0,
            'leak_high_page_faults': 2000000.0,
            'leak_high_memory_mb': 2048.0,
            'dpc_elevated_pct': 1.5,
            'dpc_severe_pct': 5.0,
            'interrupt_elevated_pct': 1.0,
            'interrupt_severe_pct': 3.0,
            'leaks_scan_every_n_ticks': 10.0,
        }
        custom = self._config.get('thresholds', {})
        if isinstance(custom, dict):
            for k, v in custom.items():
                try:
                    defaults[k] = float(v)
                except (ValueError, TypeError):
                    pass
        return defaults

    def get_threshold(self, key: str, default: float = 0.0) -> float:
        """Возвращает пороговое значение по ключу из секции thresholds."""
        return float(self.get_thresholds_config().get(key, default))

    def get_sampling_controller_config(self) -> Dict[str, float]:
        """Возвращает конфигурацию интервалов адаптивного контроллера режимов сбора."""
        defaults: Dict[str, float] = {
            'forensic_interval_sec': 0.25,
            'forensic_duration_sec': 300.0,
            'incident_interval_sec': 1.0,
            'incident_duration_sec': 1200.0,
            'boot_phase1_max_uptime_sec': 600.0,
            'boot_phase1_interval_sec': 1.0,
            'boot_phase2_max_uptime_sec': 3600.0,
            'boot_phase2_interval_sec': 5.0,
            'boot_phase3_max_uptime_sec': 86400.0,
            'boot_phase3_interval_sec': 30.0,
            'monitoring_interval_sec': 30.0,
            'normal_interval_sec': 60.0,
        }
        custom = self._config.get('sampling_controller', {})
        if isinstance(custom, dict):
            for k, v in custom.items():
                try:
                    defaults[k] = float(v)
                except (ValueError, TypeError):
                    pass
        return defaults

    def get_max_db_size_mb(self) -> float:
        """Возвращает максимальный разрешенный размер SQLite базы данных (в МБ, по умолчанию 100.0)."""
        try:
            val = float(self._config.get('max_db_size_mb', self._config.get('max_file_size_mb', 100.0)))
            return max(1.0, val)
        except (ValueError, TypeError):
            return 100.0

    def get_retention_days(self) -> int:
        """Возвращает срок хранения сырых записей телеметрии (в днях)."""
        try:
            val = int(self._config.get('retention_days', 7))
            return max(1, val)
        except (ValueError, TypeError):
            return 7

    def get_history_retention_days(self) -> int:
        """Возвращает срок хранения истории потребления ресурсов железом и приложениями (в днях).

        Значения history_retention: 1m (30), 3m (90), 6m (180), 1y (365), forever (0).
        Неизвестное или отсутствующее значение трактуется как «вечно», чтобы не терять историю.

        Returns:
            int: Число дней хранения, 0 означает «хранить вечно».
        """
        mapping = {'1m': 30, '3m': 90, '6m': 180, '1y': 365, 'forever': 0}
        return mapping.get(str(self._config.get('history_retention', 'forever')).lower(), 0)

    def get_db_cleanup_interval_seconds(self) -> float:
        """Возвращает интервал периодической проверки и очистки БД (в секундах)."""
        return getattr(self, '_db_cleanup_interval_seconds', 300.0)

    def is_auto_vacuum_enabled(self) -> bool:
        """Возвращает флаг разрешения авто-вакуума (VACUUM) SQLite при усечении."""
        return bool(self._config.get('auto_vacuum_enabled', True))

    def get_enable_foreground_window(self) -> bool:
        """Возвращает флаг разрешения отслеживания заголовков фокусного окна (ForegroundWindow)."""
        return bool(self._config.get('enable_foreground_window', getattr(self, '_enable_foreground_window', True)))

    def get_process_mode(self) -> str:
        """Возвращает режим фильтрации процессов ('top_n' или 'all')."""
        return str(self._config.get('process_mode', 'top_n')).lower()

    def get_top_processes_limit(self) -> int:
        """Возвращает настроенный лимит количества Top-процессов (по умолчанию 10)."""
        try:
            val = int(self._config.get('top_processes', 10))
            return max(1, val)
        except (ValueError, TypeError):
            return 10

    def get_effective_process_limit(self) -> int:
        """Возвращает эффективный лимит процессов для сохранения в БД телеметрии."""
        pm = self.get_process_mode()
        if pm == 'all':
            return 500
        return self.get_top_processes_limit()

    def get_sensor_config(self, sensor_name: str) -> Dict[str, Any]:
        """Возвращает конфигурацию конкретного сенсора."""
        return self._sensors_config.get(sensor_name, {'enabled': False})

    def is_sensor_enabled(self, sensor_name: str) -> bool:
        """Проверяет, включен ли сенсор."""
        config = self.get_sensor_config(sensor_name)
        return bool(config.get('enabled', False))

    def get_sensor_interval(self, sensor_name: str) -> float:
        """Возвращает интервал опроса сенсора в секундах."""
        config = self.get_sensor_config(sensor_name)
        raw = config.get('interval_seconds', config.get('interval', self._default_interval))
        return parse_interval_to_seconds(raw, self._default_interval)

    def get_sensor_metrics(self, sensor_name: str) -> List[str]:
        """Возвращает список метрик для сенсора."""
        config = self.get_sensor_config(sensor_name)
        return config.get('metrics', [])

    def get_all_sensor_names(self) -> List[str]:
        """Возвращает список всех имен сенсоров."""
        return list(self._sensors_config.keys())

    def get_enabled_sensors(self) -> List[str]:
        """Возвращает список включенных сенсоров."""
        return [name for name, config in self._sensors_config.items() if config.get('enabled', False)]

    def get_logger_interval(self, logger_name: str, default: float = 60.0) -> float:
        """Возвращает интервал опроса логгера приложения в секундах."""
        logger_info = self._loggers_config.get(logger_name, {})
        if isinstance(logger_info, dict):
            raw = logger_info.get('interval', self._config.get('default_interval'))
            return parse_interval_to_seconds(raw, default)
        return float(default)

    def is_logger_enabled(self, logger_name: str, default: bool = True) -> bool:
        """Проверяет активность логгера приложения."""
        logger_info = self._loggers_config.get(logger_name, {})
        if isinstance(logger_info, dict):
            return bool(logger_info.get('enabled', default))
        return default

    def get_trigger_mode(self) -> str:
        """Возвращает режим запуска тяжелых коллекторов (ON_STARTUP, ON_DEMAND, ON_STARTUP_OR_DEMAND, INTERVAL_BASED)."""
        return str(self._config.get('trigger_mode', 'INTERVAL_BASED'))

    def is_sequential_heavy_enabled(self) -> bool:
        """Возвращает флаг последовательного запуска тяжелых коллекторов."""
        return bool(self._config.get('sequential_heavy_execution', True))

    def get_all_intervals(self) -> Dict[str, Any]:
        """Возвращает сводный словарь всех настроенных интервалов системы."""
        return {
            'telemetry_mode': self.get_telemetry_mode(),
            'thorough_mode': self.is_thorough_mode(),
            'trigger_mode': self.get_trigger_mode(),
            'sequential_heavy_execution': self.is_sequential_heavy_enabled(),
            'default_interval_seconds': self.get_interval_seconds(),
            'light_poll_interval_seconds': self.get_light_poll_interval_seconds(),
            'heavy_interval_seconds': self.get_heavy_interval_seconds(),
            'heavy_poll_interval_seconds': self.get_heavy_poll_interval_seconds(),
            'heavy_polls_intervals': self.get_heavy_polls_intervals(),
            'fast_interval_seconds': self.get_fast_interval(),
            'aggregation_interval_seconds': self.get_aggregation_interval(),
            'heavy_disk_scan_interval_seconds': self.get_heavy_disk_scan_interval(),
            'db_cleanup_interval_seconds': self.get_db_cleanup_interval_seconds(),
            'flush_interval_seconds': self.get_flush_interval_seconds(),
            'standard_flush_interval_seconds': self.get_standard_flush_interval_seconds(),
            'tc_flush_interval_seconds': self.get_tc_flush_interval_seconds(),
            'tc_mode_timeout_seconds': self.get_tc_mode_timeout_seconds(),
            'sensors': {
                name: self.get_sensor_interval(name)
                for name in self.get_all_sensor_names()
            },
            'loggers': {
                name: self.get_logger_interval(name)
                for name in self._loggers_config.keys()
            }
        }

    def get_general_config(self) -> Dict[str, Any]:
        """Возвращает общую конфигурацию (без сенсоров)."""
        return {k: v for k, v in self._config.items() if k != 'sensors'}

    def get_config(self) -> Dict[str, Any]:
        """Возвращает полную конфигурацию телеметрии."""
        return self._config.copy()

    @property
    def config(self) -> Dict[str, Any]:
        """Свойство для получения полной конфигурации."""
        return self.get_config()

    def save_config(self, new_config: Optional[Dict[str, Any]] = None) -> bool:
        """Сохраняет текущую или переданную конфигурацию в файл.

        Args:
            new_config: Опциональный словарь новых параметров.

        Returns:
            bool: True при успешном сохранении.
        """
        if new_config:
            self._config.update(new_config)
            if 'sensors' in new_config:
                self._sensors_config = new_config['sensors']
            if 'loggers' in new_config:
                self._loggers_config = new_config['loggers']
            if 'interval_seconds' in new_config:
                self._default_interval = parse_interval_to_seconds(new_config['interval_seconds'], 5.0)
            if 'light_poll_interval_seconds' in new_config:
                self._default_interval = parse_interval_to_seconds(new_config['light_poll_interval_seconds'], 5.0)
            if 'heavy_interval_seconds' in new_config:
                self._heavy_interval = parse_interval_to_seconds(new_config['heavy_interval_seconds'], 60.0)
            if 'heavy_poll_interval_seconds' in new_config:
                self._heavy_interval = parse_interval_to_seconds(new_config['heavy_poll_interval_seconds'], 60.0)
            if 'heavy_polls_intervals' in new_config and isinstance(new_config['heavy_polls_intervals'], dict):
                hp = new_config['heavy_polls_intervals']
                if 'hardware_audit_interval_sec' in hp:
                    self._hardware_audit_interval_sec = parse_interval_to_seconds(hp['hardware_audit_interval_sec'], self._heavy_interval)
                if 'startup_audit_interval_sec' in hp:
                    self._startup_audit_interval_sec = parse_interval_to_seconds(hp['startup_audit_interval_sec'], 180.0)
                if 'extended_audit_interval_sec' in hp:
                    self._extended_audit_interval_sec = parse_interval_to_seconds(hp['extended_audit_interval_sec'], 300.0)
                if 'defender_audit_interval_sec' in hp:
                    self._defender_audit_interval_sec = parse_interval_to_seconds(hp['defender_audit_interval_sec'], 120.0)
                if 'process_activity_sync_interval_sec' in hp:
                    self._process_activity_sync_interval_sec = parse_interval_to_seconds(hp['process_activity_sync_interval_sec'], 60.0)
                if 'software_audit_interval_sec' in hp:
                    self._software_audit_interval_sec = parse_interval_to_seconds(hp['software_audit_interval_sec'], 3600.0)
                if 'wmi_interval_sec' in hp:
                    self._wmi_interval_sec = parse_interval_to_seconds(hp['wmi_interval_sec'], 120.0)
                if 'smart_interval_sec' in hp:
                    self._smart_interval_sec = parse_interval_to_seconds(hp['smart_interval_sec'], 300.0)
                if 'handles_interval_sec' in hp:
                    self._handles_interval_sec = parse_interval_to_seconds(hp['handles_interval_sec'], 60.0)
                if 'network_ports_interval_sec' in hp:
                    self._network_ports_interval_sec = parse_interval_to_seconds(hp['network_ports_interval_sec'], 30.0)
                if 'disk_scan_interval_sec' in hp:
                    self._heavy_disk_scan_interval = parse_interval_to_seconds(hp['disk_scan_interval_sec'], 43200.0)
            if 'heavy_disk_scan_interval_seconds' in new_config:
                self._heavy_disk_scan_interval = parse_interval_to_seconds(new_config['heavy_disk_scan_interval_seconds'], 43200.0)
            if 'software_audit_interval_sec' in new_config:
                self._software_audit_interval_sec = parse_interval_to_seconds(new_config['software_audit_interval_sec'], 3600.0)
            if 'fast_interval_seconds' in new_config:
                self._fast_interval = parse_interval_to_seconds(new_config['fast_interval_seconds'], 30.0)
            if 'aggregation_interval_seconds' in new_config:
                self._aggregation_interval = parse_interval_to_seconds(new_config['aggregation_interval_seconds'], 3600.0)
            if 'heavy_mode_max_duration_days' in new_config:
                self._heavy_mode_max_duration_days = float(new_config['heavy_mode_max_duration_days'])
            if 'heavy_mode_auto_switch_enabled' in new_config:
                self._heavy_mode_auto_switch_enabled = bool(new_config['heavy_mode_auto_switch_enabled'])
            if 'mode' in new_config:
                self._mode = str(new_config['mode']).lower()
            if 'telemetry_mode' in new_config:
                self._telemetry_mode = str(new_config['telemetry_mode']).lower()
            if 'audit_enabled' in new_config:
                self._audit_enabled = bool(new_config['audit_enabled'])
            if 'streaming_enabled' in new_config:
                self._streaming_enabled = bool(new_config['streaming_enabled'])
            if 'live_stream_enabled' in new_config:
                self._streaming_enabled = bool(new_config['live_stream_enabled'])
            if 'standard_flush_interval_seconds' in new_config:
                self._standard_flush_interval_seconds = parse_interval_to_seconds(new_config['standard_flush_interval_seconds'], 30.0)
            if 'tc_flush_interval_seconds' in new_config:
                self._tc_flush_interval_seconds = parse_interval_to_seconds(new_config['tc_flush_interval_seconds'], 5.0)
            if 'tc_mode_timeout_seconds' in new_config:
                self._tc_mode_timeout_seconds = parse_interval_to_seconds(new_config['tc_mode_timeout_seconds'], 300.0)
            if 'tc_mode_activated_at' in new_config:
                self._tc_mode_activated_at = float(new_config['tc_mode_activated_at']) if new_config['tc_mode_activated_at'] is not None else None
            if 'max_db_size_mb' in new_config:
                self._max_db_size_mb = float(new_config['max_db_size_mb'])
            if 'retention_days' in new_config:
                self._retention_days = int(new_config['retention_days'])
            if 'db_cleanup_interval_seconds' in new_config:
                self._db_cleanup_interval_seconds = parse_interval_to_seconds(new_config['db_cleanup_interval_seconds'], 300.0)
            if 'flush_interval_seconds' in new_config:
                self._flush_interval_seconds = parse_interval_to_seconds(new_config['flush_interval_seconds'], 30.0)
            if 'auto_vacuum_enabled' in new_config:
                self._auto_vacuum_enabled = bool(new_config['auto_vacuum_enabled'])
        try:
            target_path = Path(self._config_path)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(target_path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            if target_path.is_file():
                self._last_mtime_ns = target_path.stat().st_mtime_ns
            return True
        except Exception:
            return False


_global_telemetry_config_manager: Optional[TelemetryConfigManager] = None


def get_telemetry_config_manager() -> TelemetryConfigManager:
    """Возвращает глобальный экземпляр менеджера конфигурации телеметрии."""
    global _global_telemetry_config_manager
    if _global_telemetry_config_manager is None:
        _global_telemetry_config_manager = TelemetryConfigManager()
    return _global_telemetry_config_manager


def get_trigger_mode() -> str:
    """Возвращает текущий триггерный режим сбора телеметрии."""
    return get_telemetry_config_manager().get_trigger_mode()


def is_sequential_heavy_enabled() -> bool:
    """Возвращает флаг последовательного сбора тяжелой телеметрии."""
    return get_telemetry_config_manager().is_sequential_heavy_enabled()


def get_all_intervals() -> Dict[str, Any]:
    """Возвращает сводный словарь интервалов телеметрии."""
    return get_telemetry_config_manager().get_all_intervals()

