# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry Sqlite - Storage
# =============================================================================
# Description:
#   Главный фасад TelemetryStorage базы данных SQLite телеметрии.
#
# Usage Examples:
#   Python API:
#     from apps.windows.telemetry.sqlite import TelemetryStorage
#
#     storage = TelemetryStorage.get_instance(read_only=True)
#     snapshots = storage.get_snapshots(limit=10)
#
# File: storage.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry.sqlite
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 04:40:00
# =============================================================================

from __future__ import annotations

"""Главный класс TelemetryStorage, объединяющий подсистемы чтения, записи, буферизации и обслуживания."""

import atexit
import os
import sqlite3
import threading
from pathlib import Path
from typing import Optional, Union

from .aggregator import TelemetrySqlAggregator
from .buffer import TelemetryBuffer
from .connection import TelemetryConnectionManager
from .storage_snapshots import TelemetrySnapshotStorageMixin
from .storage_inventory import TelemetryInventoryStorageMixin
from .storage_maintenance import TelemetryMaintenanceStorageMixin
from .storage_audits import TelemetryAuditStorageMixin
from .storage_security import TelemetrySecurityStorageMixin
from .maintenance import TelemetryMaintenance
from .reader import TelemetryReader
from .schema import init_database_schema
from .writer import TelemetryWriter
from ..telemetry_config import TelemetryConfigManager

try:
    from logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class TelemetryStorage(TelemetrySnapshotStorageMixin, TelemetryInventoryStorageMixin, TelemetryMaintenanceStorageMixin, TelemetryAuditStorageMixin, TelemetrySecurityStorageMixin):
    """Универсальный фасад персистентного хранения и выборки телеметрии в SQLite."""

    _instance: Optional[TelemetryStorage] = None
    _ro_instance: Optional[TelemetryStorage] = None
    _lock = threading.RLock()

    def __init__(
        self,
        db_path: Optional[Union[str, Path]] = None,
        buffer_mode: Optional[str] = None,
        buffer_size: Optional[int] = None,
        flush_interval_seconds: Optional[float] = None,
        buffer_file_path: Optional[Union[str, Path]] = None,
        auto_flush: bool = True,
        max_db_size_mb: Optional[float] = None,
        retention_days: Optional[int] = None,
        auto_vacuum: Optional[bool] = None,
        read_only: bool = False,
    ) -> None:
        """Инициализирует подключение к SQLite базе данных телеметрии."""
        self.read_only = bool(read_only)

        # 1. Определение путей базы данных
        if db_path is None:
            programdata = os.environ.get('ProgramData') or os.environ.get('ALLUSERSPROFILE')
            if programdata and os.path.exists(programdata):
                base_dir = Path(programdata)
            else:
                appdata = os.environ.get('APPDATA') or os.environ.get('LOCALAPPDATA')
                base_dir = Path(appdata) if appdata and os.path.exists(appdata) else (Path.home() / '.config')

            ai_tel_dir = base_dir / 'AITelemetry' / 'data'
            if (ai_tel_dir / 'telemetry.db').is_file() or ai_tel_dir.is_dir():
                target_dir = ai_tel_dir
            else:
                target_dir = base_dir / 'ai-tc' / 'telemetry'

            if not self.read_only:
                target_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = target_dir / 'telemetry.db'
        else:
            self.db_path = Path(db_path)
            if not self.read_only:
                self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # 2. Конфигурация
        cfg_manager = None
        try:
            cfg_manager = TelemetryConfigManager()
        except Exception:
            cfg_manager = None

        raw_mode = buffer_mode or (cfg_manager.get_buffer_mode() if cfg_manager else 'memory')
        b_mode = raw_mode.lower() if raw_mode in ('memory', 'file', 'direct') else 'memory'
        b_size = int(buffer_size if buffer_size is not None else (cfg_manager.get_buffer_size() if cfg_manager else 50))
        f_interval = float(flush_interval_seconds if flush_interval_seconds is not None else (cfg_manager.get_flush_interval_seconds() if cfg_manager else 30.0))
        m_size = float(max_db_size_mb if max_db_size_mb is not None else (cfg_manager.get_max_db_size_mb() if cfg_manager else 50.0))
        r_days = int(retention_days if retention_days is not None else (cfg_manager.get_retention_days() if cfg_manager else 7))
        a_vacuum = bool(auto_vacuum if auto_vacuum is not None else (cfg_manager.is_auto_vacuum_enabled() if cfg_manager else True))

        # 3. Инициализация менеджера подключений
        self._cm = TelemetryConnectionManager(db_path=self.db_path, read_only=self.read_only, lock=self._lock)

        # 4. Инициализация схемы (только в режиме записи)
        if not self.read_only:
            try:
                with self._cm.lock, self._cm.get_connection() as conn:
                    init_database_schema(conn)
            except Exception as schema_err:
                logger.warning(f'Ошибка инициализации схемы базы данных: {schema_err}')

        # 5. Инициализация подсистем
        self._reader = TelemetryReader(self._cm)
        self._writer = TelemetryWriter(self._cm)
        self._buffer = TelemetryBuffer(
            connection_manager=self._cm,
            writer=self._writer,
            buffer_mode=b_mode,
            buffer_size=b_size,
            flush_interval_seconds=f_interval,
            buffer_file_path=buffer_file_path,
            auto_flush=auto_flush,
        )
        self._maintenance = TelemetryMaintenance(
            connection_manager=self._cm,
            max_db_size_mb=m_size,
            retention_days=r_days,
            auto_vacuum_enabled=a_vacuum,
            buffer_file_path=self._buffer.buffer_file_path,
        )
        self._aggregator = TelemetrySqlAggregator(self._cm)

        if not self.read_only:
            try:
                atexit.register(self.close)
            except Exception:
                pass

    @classmethod
    def get_instance(
        cls,
        db_path: Optional[Union[str, Path]] = None,
        read_only: bool = False,
    ) -> TelemetryStorage:
        """Возвращает синглтон-экземпляр хранилища телеметрии (для записи или только для чтения)."""
        with cls._lock:
            if read_only:
                if cls._ro_instance is None or (db_path is not None and cls._ro_instance.db_path != Path(db_path)):
                    cls._ro_instance = TelemetryStorage(db_path=db_path, read_only=True, auto_flush=False)
                return cls._ro_instance
            else:
                if cls._instance is None or (db_path is not None and cls._instance.db_path != Path(db_path)):
                    cls._instance = TelemetryStorage(db_path=db_path, read_only=False)
                return cls._instance

    def _get_connection(self) -> sqlite3.Connection:
        """Создает и настраивает соединение с базой данных SQLite."""
        return self._cm.get_connection()

    def get_connection(self) -> sqlite3.Connection:
        """Возвращает активное подключение к SQLite базе данных."""
        return self._cm.get_connection()

    @property
    def connection(self) -> sqlite3.Connection:
        """Свойство прямого доступа к подключению SQLite."""
        return self._cm.get_connection()

    @property
    def reader(self) -> TelemetryReader:
        """Подсистема чтения данных."""
        return self._reader

    @property
    def writer(self) -> TelemetryWriter:
        """Подсистема записи данных."""
        return self._writer

    @property
    def buffer(self) -> TelemetryBuffer:
        """Подсистема буферизации."""
        return self._buffer

    @property
    def maintenance(self) -> TelemetryMaintenance:
        """Подсистема регламентного обслуживания."""
        return self._maintenance

    @property
    def aggregator(self) -> TelemetrySqlAggregator:
        """Подсистема многоуровневой SQL-агрегации."""
        return self._aggregator

    # -------------------------------------------------------------------------
    # Делегирование методов буфера
    # -------------------------------------------------------------------------

    def set_buffer_mode(self, mode: str) -> None:
        self._buffer.set_buffer_mode(mode)

    def get_buffer_mode(self) -> str:
        return self._buffer.buffer_mode

    def set_flush_interval_seconds(self, interval: float) -> None:
        """Обновляет интервал таймера сброса буфера в SQLite."""
        self._buffer.set_flush_interval_seconds(interval)

    def get_buffered_count(self) -> int:
        return self._buffer.get_buffered_count()

    def flush(self) -> int:
        return self._buffer.flush()

    def close(self) -> None:
        self._aggregator.stop_background_scheduler()
        self._buffer.close()

    # -------------------------------------------------------------------------
    # Делегирование методов сохранения (Writer / Buffer)
    # -------------------------------------------------------------------------
























    # -------------------------------------------------------------------------
    # Делегирование методов чтения (Reader)
    # -------------------------------------------------------------------------







































    # -------------------------------------------------------------------------
    # Делегирование методов хранилища накопителей (Storage Subsystem)
    # -------------------------------------------------------------------------











    # -------------------------------------------------------------------------
    # Делегирование методов хранилища процессоров (CPU Subsystem)
    # -------------------------------------------------------------------------





    # -------------------------------------------------------------------------
    # Делегирование методов хранилища памяти (RAM Module / SPD Subsystem)
    # -------------------------------------------------------------------------





    # -------------------------------------------------------------------------
    # Делегирование методов хранилища графики (GPU Subsystem)
    # -------------------------------------------------------------------------





    # -------------------------------------------------------------------------
    # Делегирование методов хранилища сети (Network Adapter Subsystem)
    # -------------------------------------------------------------------------






    # -------------------------------------------------------------------------
    # Делегирование методов обслуживания (Maintenance)
    # -------------------------------------------------------------------------












    # -------------------------------------------------------------------------
    # Делегирование методов SQL-агрегации сенсоров (Aggregator)
    # -------------------------------------------------------------------------










    # -------------------------------------------------------------------------
    # Делегирование методов подсистем рефакторинга: Data-First SQLite
    # -------------------------------------------------------------------------

    # 1. Windows Event Logs





    # 2. Windows Firewall




    # 3. Windows Services





    # 4. Throttling & Power


    # 5. Forensics



    # 6. Process Leaks


    # 7. Defender






    # 8. Process Network & Process Manager


    # 9. Software Transparency




    # 10. Security Events & Audit






















