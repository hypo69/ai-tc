# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry - History Mixin
# =============================================================================
# Description:
#   Миксин истории и аудита телеметрии: аппаратный/стартовый аудит, снапшоты, перезагрузки, происхождение процессов.
#   Вынесено из collector.py при декомпозиции SystemCollector (этап 4 ТЗ оптимизации).
#   Методы — тонкие обращения к хранилищу и менеджерам истории, поэтому оформлены миксином
#   (без дублирующих методов-обёрток в SystemCollector).
#
#   Требуемые атрибуты хост-класса: storage, auditor, history_manager, startup_history_manager.
#
# Usage Examples:
#   Python API:
#     from apps.windows.telemetry.history_mixin import TelemetryHistoryMixin
#
#     class SystemCollector(TelemetryHistoryMixin): ...
#
# File: history_mixin.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 08:00:00
# =============================================================================

from __future__ import annotations
"""Миксин истории и аудита телеметрии: аппаратный/стартовый аудит, снапшоты, перезагрузки, происхождение процессов."""

from typing import Any, Dict, List, Optional

from logger import logger
from .models import (
    HardwareArchiveEntry,
    HardwareAuditReport,
    HardwareChangeItem,
    StartupArchiveEntry,
)


class TelemetryHistoryMixin:
    """Миксин истории и аудита телеметрии: аппаратный/стартовый аудит, снапшоты, перезагрузки, происхождение процессов.

    Хост-класс обязан предоставлять атрибуты ``storage``, ``auditor``,
    ``history_manager`` и ``startup_history_manager``.
    """

    def get_hardware_audit(self) -> HardwareAuditReport:
        """Collect deep hardware devices audit with drivers, install dates, and attached sensors.

        Returns:
            HardwareAuditReport: Complete hardware audit report.
        """
        if hasattr(self, 'hardware_collector') and self.hardware_collector is not None:
            return self.hardware_collector.collect_hardware_report()
        return self.auditor.audit_hardware()

    def archive_hardware_state(self, auto_diff: bool=True) -> HardwareArchiveEntry:
        """Capture current hardware audit and save it to historical archive storage.

        Args:
            auto_diff: Automatically compute diff with previous archive.

        Returns:
            HardwareArchiveEntry: Persisted archive entry with detected changes.
        """
        report = self.get_hardware_audit()
        return self.history_manager.archive_report(report, auto_diff=auto_diff)

    def get_hardware_history(self, limit: int=50) -> List[Dict[str, Any]]:
        """Retrieve historical hardware archive snapshots metadata.

        Args:
            limit: Maximum count of archive entries.

        Returns:
            List[Dict[str, Any]]: Chronological list of archive entries.
        """
        return self.history_manager.get_history(limit=limit)

    def get_hardware_changes(self, limit: int=100) -> List[HardwareChangeItem]:
        """Retrieve historical timeline of all hardware configuration changes.

        Args:
            limit: Maximum count of changes to return.

        Returns:
            List[HardwareChangeItem]: Historical changes timeline.
        """
        return self.history_manager.get_change_timeline(limit=limit)

    def get_startup_audit(self) -> Any:
        """Collect deep Windows startup and autoruns audit report.

        Returns:
            AuditReport: Complete startup audit report with risk ratings.
        """
        from apps.windows.sdk.modules.startup.core.auditor import StartupAuditor
        return StartupAuditor().run_audit()

    def archive_startup_state(self, auto_diff: bool = True) -> StartupArchiveEntry:
        """Capture current Windows startup state, compute changes diff, and save snapshot to storage.

        Args:
            auto_diff: Automatically compute diff with previous archive snapshot.

        Returns:
            StartupArchiveEntry: Persisted archive entry with detected changes.
        """
        report = self.get_startup_audit()
        entry = self.startup_history_manager.archive_report(report, auto_diff=auto_diff)
        if self.storage:
            try:
                self.storage.save_startup_archive(entry)
            except Exception as ex:
                logger.debug(f'Не удалось сохранить снимок автозапуска в БД: {ex}')
        return entry

    def get_startup_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve historical startup archive snapshots metadata.

        Args:
            limit: Maximum count of archive entries.

        Returns:
            List[Dict[str, Any]]: Chronological list of startup archive entries.
        """
        if self.storage:
            try:
                db_history = self.storage.get_startup_archives(limit=limit)
                if db_history:
                    return db_history
            except Exception:
                pass
        return self.startup_history_manager.get_history(limit=limit)

    def get_startup_changes(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve historical timeline of all startup configuration changes.

        Args:
            limit: Maximum count of changes to return.

        Returns:
            List[Dict[str, Any]]: Historical changes timeline.
        """
        if self.storage:
            try:
                db_changes = self.storage.get_startup_changes(limit=limit)
                if db_changes:
                    return db_changes
            except Exception:
                pass
        return [c.model_dump(mode='json') for c in self.startup_history_manager.get_change_timeline(limit=limit)]

    def get_latest_startup_audit(self) -> Optional[Dict[str, Any]]:
        """Retrieve latest recorded startup audit snapshot from telemetry storage.

        Returns:
            Optional[Dict[str, Any]]: Startup audit dict or None.
        """
        if self.storage:
            try:
                latest = self.storage.get_latest_startup_archive()
                if latest:
                    return latest
            except Exception:
                pass
        latest_archive = self.startup_history_manager.get_latest_archive()
        return latest_archive.model_dump(mode='json') if latest_archive else None

    def get_snapshots(self, limit: int=60, since_epoch: Optional[float]=None) -> List[Dict[str, Any]]:
        """Retrieve persisted system snapshots from SQLite database.

        Args:
            limit: Maximum number of snapshots.
            since_epoch: Optional starting timestamp.

        Returns:
            List[Dict[str, Any]]: List of system snapshots from database.
        """
        return self.storage.get_snapshots(limit=limit, since_epoch=since_epoch)

    def get_latest_cpu_from_db(self) -> Optional[Dict[str, Any]]:
        """Извлекает последние метрики процессора из базы данных SQLite.

        Returns:
            Optional[Dict[str, Any]]: Метрики процессора из SQLite.
        """
        return self.storage.get_latest_cpu()

    def get_cpu_history_from_db(self, limit: int = 60, since_epoch: Optional[float] = None) -> List[Dict[str, Any]]:
        """Извлекает историю нагрузки процессора из базы данных SQLite.

        Args:
            limit: Количество записей.
            since_epoch: Начальное время UNIX epoch.

        Returns:
            List[Dict[str, Any]]: Исторические срезы нагрузки CPU.
        """
        return self.storage.get_cpu_history(limit=limit, since_epoch=since_epoch)

    def get_process_history(self, name: Optional[str]=None, pid: Optional[int]=None, limit: int=100) -> List[Dict[str, Any]]:
        """Retrieve historical process metrics from SQLite database.

        Args:
            name: Substring of process name.
            pid: Process identifier.
            limit: Record limit.

        Returns:
            List[Dict[str, Any]]: History of process metrics.
        """
        return self.storage.get_process_history(name=name, pid=pid, limit=limit)

    def get_reboot_report(self, limit: int = 20, hours: int = 720) -> Any:
        """Сбор сводного отчета анализа перезагрузок и выключений ОС.

        Args:
            limit: Максимальное количество сессий.
            hours: Глубина выборки журналов в часах.

        Returns:
            RebootAnalysisReport: Сводный аналитический отчет.
        """
        from apps.windows.analytics.reboot_analyzer import WindowsRebootAnalyzer
        analyzer = WindowsRebootAnalyzer(storage=self.storage)
        return analyzer.collect_reboot_history(limit=limit, hours=hours)

    def get_latest_reboot(self) -> Optional[Any]:
        """Получение данных о последней перезагрузке системы.

        Returns:
            Optional[RebootSession]: Информация о последнем перезапуске.
        """
        from apps.windows.analytics.reboot_analyzer import WindowsRebootAnalyzer
        analyzer = WindowsRebootAnalyzer(storage=self.storage)
        return analyzer.analyze_current_boot()

    def get_extended_system_audit(self) -> Any:
        """Сбор расширенного аудита безопасности (Defender), автозагрузки (Startup), VSS и пользователей.

        Returns:
            ExtendedSystemAuditReport: Сводный отчет расширенного аудита.
        """
        from apps.windows.analytics.deep_diagnostics import DeepDiagnosticsEngine
        engine = DeepDiagnosticsEngine()
        report = engine.collect_extended_system_audit()
        try:
            self.storage.save_extended_audit(report)
        except Exception as ex:
            logger.debug(f'Не удалось сохранить расширенный аудит в БД: {ex}')
        return report

    def get_latest_extended_audit(self) -> Optional[Dict[str, Any]]:
        """Получение последнего сохраненного среза расширенного системного аудита.

        Returns:
            Optional[Dict[str, Any]]: Словарь аудита или None.
        """
        return self.storage.get_latest_extended_audit()

    def get_process_provenance_history(
        self,
        guid: Optional[str] = None,
        pid: Optional[int] = None,
        name: Optional[str] = None,
        user: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Получить исторические события жизненного цикла и происхождения процессов из БД.

        Args:
            guid: Фильтр по уникальному идентификатору процесса.
            pid: Фильтр по PID.
            name: Фильтр по имени процесса.
            user: Фильтр по имени пользователя или SID.
            event_type: Фильтр по типу события ('ProcessCreated', 'ProcessTerminated').
            limit: Максимальное количество записей.

        Returns:
            List[Dict[str, Any]]: Список исторических событий происхождения процессов.
        """
        return self.storage.get_process_provenance_history(
            guid=guid,
            pid=pid,
            name=name,
            user=user,
            event_type=event_type,
            limit=limit,
        )

    def get_process_lineage(self, guid_or_pid: str) -> List[Dict[str, Any]]:
        """Построить полную восходящую цепочку предков процесса (дерево запуска).

        Args:
            guid_or_pid: Идентификатор process_guid или числовой PID.

        Returns:
            List[Dict[str, Any]]: Упорядоченный список предков от корневого процесса к целевому.
        """
        return self.storage.get_process_lineage(guid_or_pid=guid_or_pid)

