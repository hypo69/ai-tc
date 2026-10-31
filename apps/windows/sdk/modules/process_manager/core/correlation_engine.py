# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Modules Process_Manager Core - Correlation Engine
# =============================================================================
# Description:
#   Корреляционный движок построения сквозной хроники инцидентов и аномалий
#   процессов (Correlation Engine): сопоставление всплесков CPU, скачков памяти,
#   интенсивного дискового ввода-вывода (файлы) и сетевой активности.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.process_manager.core.correlation_engine import IncidentTimelineBuilder
#
#     builder = IncidentTimelineBuilder()
#     timeline = builder.build_timeline_from_samples(samples)
#
# File: correlation_engine.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.process_manager.core
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-15 00:58:00
# =============================================================================

from __future__ import annotations
"""Корреляционный движок восстановления хроники инцидентов и ресурсных всплесков процессов."""

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from logger import logger


@dataclass
class IncidentEvent:
    """Единичное событие ресурсного всплеска или активности в таймлайне инцидента."""
    timestamp: str                       # Временная метка (например "12:00:01" или ISO)
    resource: str                        # Ресурс: CPU, RAM, Диск, Сеть, Жизненный цикл
    severity: str = "INFO"               # INFO, WARNING, CRITICAL
    title: str = ""                      # Краткое описание (например "Загрузка CPU выросла до 85%")
    value: float = 0.0                   # Числовое значение метрики
    unit: str = ""                       # Единица измерения (%, МБ, МБ/с, conn)
    details: Dict[str, Any] = field(default_factory=dict)  # Связанные пути файлов, IP:порты, потоки

    def to_dict(self) -> Dict[str, Any]:
        """Преобразование события в словарь."""
        return asdict(self)


@dataclass
class IncidentTimeline:
    """Полная хроника инцидента процесса с корреляцией всех задействованных ресурсов."""
    instance_id: str
    pid: int
    process_name: str
    username: Optional[str] = None
    parent_name: Optional[str] = None
    initiator_type: str = "unknown"
    started_at: str = ""
    total_events: int = 0
    max_cpu_percent: float = 0.0
    peak_memory_mb: float = 0.0
    total_io_mb: float = 0.0
    active_network_hosts: List[str] = field(default_factory=list)
    touched_files: List[str] = field(default_factory=list)
    events: List[IncidentEvent] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Преобразование таймлайна в словарь для API и отчетов."""
        return asdict(self)


class IncidentTimelineBuilder:
    """Построитель хроники инцидента и корреляции событий процессов по замерам телеметрии."""

    # Пороговые значения для детектирования аномалий и всплесков
    CPU_WARNING_THRESHOLD: float = 40.0       # Нагрузка CPU выше 40%
    CPU_CRITICAL_THRESHOLD: float = 75.0      # Нагрузка CPU выше 75%
    RAM_SPIKE_DELTA_MB: float = 30.0          # Скачок памяти более чем на 30 МБ за интервал
    DISK_WRITE_RATE_MB_S: float = 5.0         # Скорость записи выше 5 МБ/сек
    DISK_BURST_OPS: int = 200                 # Более 200 дисковых операций за замер

    def build_timeline_from_samples(
        self, samples: List[Dict[str, Any]]
    ) -> Optional[IncidentTimeline]:
        """Анализирует хронологический ряд замеров процесса и строит таймлайн инцидента.

        Args:
            samples: Список замеров процесса из таблицы process_audit_samples.

        Returns:
            Optional[IncidentTimeline]: Построенный таймлайн инцидента или None.
        """
        if not samples:
            return None

        # Сортировка по времени создания замера (от старых к новым)
        sorted_samples = sorted(samples, key=lambda s: float(s.get('created_at') or 0.0))
        first_sample = sorted_samples[0]

        inst_id = first_sample.get('instance_id') or f"{first_sample.get('pid')}_{first_sample.get('created_at')}"
        pid = int(first_sample.get('pid') or 0)
        pname = str(first_sample.get('name') or "unknown")
        user = first_sample.get('username')
        parent = first_sample.get('parent_name')
        initiator = str(first_sample.get('initiator_type') or "unknown")
        started = str(first_sample.get('timestamp') or "")

        events: List[IncidentEvent] = []
        all_touched_files: set[str] = set()
        all_remote_hosts: set[str] = set()
        max_cpu = 0.0
        peak_ram = 0.0
        total_io_bytes = 0

        # Начальное событие: старт или обнаружение процесса
        start_time_short = self._format_short_time(started)
        events.append(IncidentEvent(
            timestamp=start_time_short,
            resource="Процесс",
            severity="INFO",
            title=f"Процесс {pname} (PID {pid}) инициализирован",
            details={
                "initiator": parent or initiator,
                "user": user or "Unknown",
                "cmdline": first_sample.get('cmdline'),
            }
        ))

        prev_sample: Optional[Dict[str, Any]] = None

        for sample in sorted_samples:
            ts_str = self._format_short_time(sample.get('timestamp') or "")
            cpu_val = float(sample.get('cpu_percent') or 0.0)
            ws_mb = float(sample.get('working_set_mb') or 0.0)
            priv_mb = float(sample.get('private_mb') or 0.0)
            w_bytes_sec = float(sample.get('write_bytes_sec') or 0.0)
            w_mb_sec = round(w_bytes_sec / (1024 * 1024), 2)
            w_ops = int(sample.get('write_operations') or 0)
            r_bytes = int(sample.get('read_bytes') or 0)
            w_bytes = int(sample.get('write_bytes') or 0)

            max_cpu = max(max_cpu, cpu_val)
            peak_ram = max(peak_ram, ws_mb, priv_mb)
            total_io_bytes = max(total_io_bytes, r_bytes + w_bytes)

            # Файлы
            open_files = sample.get('open_files') or []
            if isinstance(open_files, list):
                for fpath in open_files:
                    if fpath:
                        all_touched_files.add(fpath)

            # Сетевые соединения
            conns = sample.get('connections') or []
            if isinstance(conns, list):
                for c in conns:
                    rem_addr = c.get('remote_address') or c.get('remote_ip')
                    rem_port = c.get('remote_port')
                    if rem_addr and rem_addr not in ('0.0.0.0', '::', '127.0.0.1'):
                        all_remote_hosts.add(f"{rem_addr}:{rem_port}")

            # 1. Анализ CPU
            if cpu_val >= self.CPU_CRITICAL_THRESHOLD:
                events.append(IncidentEvent(
                    timestamp=ts_str,
                    resource="CPU",
                    severity="CRITICAL",
                    title=f"Критический всплеск CPU: утилизация выросла до {cpu_val:.1f}%",
                    value=cpu_val,
                    unit="%",
                    details={"threads": sample.get('num_threads', 1)}
                ))
            elif cpu_val >= self.CPU_WARNING_THRESHOLD:
                events.append(IncidentEvent(
                    timestamp=ts_str,
                    resource="CPU",
                    severity="WARNING",
                    title=f"Высокая нагрузка на процессор: {cpu_val:.1f}%",
                    value=cpu_val,
                    unit="%",
                    details={"threads": sample.get('num_threads', 1)}
                ))

            # 2. Анализ памяти (скачки Working Set)
            if prev_sample:
                prev_ws = float(prev_sample.get('working_set_mb') or 0.0)
                delta_ws = round(ws_mb - prev_ws, 2)
                if delta_ws >= self.RAM_SPIKE_DELTA_MB:
                    events.append(IncidentEvent(
                        timestamp=ts_str,
                        resource="RAM",
                        severity="WARNING",
                        title=f"Скачок физической памяти: Working Set увеличился на +{delta_ws} МБ (всего {ws_mb} МБ)",
                        value=delta_ws,
                        unit="МБ",
                        details={"working_set_mb": ws_mb, "private_mb": priv_mb}
                    ))

            # 3. Анализ дискового ввода-вывода (интенсивная запись)
            if w_mb_sec >= self.DISK_WRITE_RATE_MB_S or (prev_sample and (w_ops - int(prev_sample.get('write_operations') or 0)) >= self.DISK_BURST_OPS):
                recent_files = open_files[:3] if isinstance(open_files, list) else []
                events.append(IncidentEvent(
                    timestamp=ts_str,
                    resource="Диск",
                    severity="WARNING",
                    title=f"Интенсивная запись на диск: {w_mb_sec} МБ/сек",
                    value=w_mb_sec,
                    unit="МБ/с",
                    details={"files": recent_files, "write_operations": w_ops}
                ))

            # 4. Анализ сети (активные установленные соединения)
            tcp_cnt = int(sample.get('tcp_connections_count') or 0)
            if prev_sample:
                prev_tcp = int(prev_sample.get('tcp_connections_count') or 0)
                if tcp_cnt > prev_tcp and all_remote_hosts:
                    events.append(IncidentEvent(
                        timestamp=ts_str,
                        resource="Сеть",
                        severity="INFO",
                        title=f"Открыты новые сетевые соединения (+{tcp_cnt - prev_tcp})",
                        value=float(tcp_cnt),
                        unit="conn",
                        details={"endpoints": list(all_remote_hosts)[:5]}
                    ))

            prev_sample = sample

        # Завершающее событие: если процесс умер
        last_sample = sorted_samples[-1]
        if not last_sample.get('is_alive'):
            events.append(IncidentEvent(
                timestamp=self._format_short_time(last_sample.get('timestamp') or ""),
                resource="Процесс",
                severity="INFO",
                title=f"Процесс {pname} завершился",
                details={"lifetime_sec": last_sample.get('exit_time', 0.0)}
            ))

        return IncidentTimeline(
            instance_id=inst_id,
            pid=pid,
            process_name=pname,
            username=user,
            parent_name=parent,
            initiator_type=initiator,
            started_at=started,
            total_events=len(events),
            max_cpu_percent=round(max_cpu, 1),
            peak_memory_mb=round(peak_ram, 1),
            total_io_mb=round(total_io_bytes / (1024 * 1024), 2),
            active_network_hosts=list(all_remote_hosts)[:20],
            touched_files=list(all_touched_files)[:20],
            events=events,
        )

    def _format_short_time(self, iso_ts: str) -> str:
        """Форматирует дату/время в краткий вид ЧЧ:ММ:СС."""
        if not iso_ts:
            return ""
        try:
            # Преобразуем ISO строку в короткое локальное время
            clean_ts = iso_ts.replace('Z', '+00:00')
            dt = datetime.fromisoformat(clean_ts)
            return dt.strftime("%H:%M:%S")
        except Exception:
            return iso_ts[:19]

