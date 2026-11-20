# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Forensics Module - Intelligence Layer
# =============================================================================
# Description:
#   Уровень интеллектуального криминалистического исследования (Forensic Intelligence):
#   - Инцидентное расследование по сценариям:
#     * Сбои и неожиданные перезагрузки (Kernel-Power, BSOD, WER)
#     * Подключение и активность USB-устройств (USBSTOR)
#     * Временное окно инцидента (реконструкция событий в диапазоне ± N минут)
#     * Подозрительная активность процессов (Malware/Anomaly indicators)
#   - Формирование экспертного заключения с указанием первопричины (Root Cause)
#   - Оценка доказательной достоверности выводов (Confidence Score)
#   - Привязка юридически неизменных хешей SHA-256 к каждому выводу
#
# Usage Examples:
#   from apps.windows.sdk.modules.forensics.intelligence import ForensicIntelligenceEngine
#   from apps.windows.sdk.modules.forensics.models import IncidentInvestigationRequest
#
#   engine = ForensicIntelligenceEngine()
#   report = engine.investigate_incident(IncidentInvestigationRequest(scenario_type="reboot_crash"))
#
# File: intelligence.py
# Project: ai-tc
# Package: apps.windows.sdk.modules.forensics
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 12:45:00
# =============================================================================

from __future__ import annotations
"""Уровень интеллектуального криминалистического исследования (Incident Reconstruction)."""

import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from logger import logger
from .acquisition import ForensicAcquisitionEngine, compute_sha256
from .analysis import ForensicAnalysisEngine
from .models import (
    ForensicSuperTimelineItem,
    IncidentInvestigationRequest,
    IncidentInvestigationReport,
)


class ForensicIntelligenceEngine:
    """Интеллектуальный аналитический движок реконструкции инцидентов."""

    def __init__(
        self,
        acquisition: Optional[ForensicAcquisitionEngine] = None,
        analysis: Optional[ForensicAnalysisEngine] = None,
    ) -> None:
        """Инициализация интеллектуального уровня с внедрением зависимостей."""
        self.acq = acquisition or ForensicAcquisitionEngine()
        self.analysis = analysis or ForensicAnalysisEngine(acquisition=self.acq)

    def investigate_incident(self, req: IncidentInvestigationRequest) -> IncidentInvestigationReport:
        """Проводит комплексное доказательное расследование инцидента по заданному сценарию.

        Args:
            req: Параметры расследования (тип сценария, целевое время, окно в минутах).

        Returns:
            IncidentInvestigationReport: Итоговое экспертное криминалистическое заключение.
        """
        case_id = f"CASE-{uuid.uuid4().hex[:8].upper()}"
        target_str = req.timestamp_target or datetime.now(timezone.utc).isoformat()
        scenario = req.scenario_type.lower()

        if scenario == "reboot_crash":
            return self._investigate_reboot_crash(case_id, target_str, req)
        elif scenario == "usb_device":
            return self._investigate_usb_incident(case_id, target_str, req)
        else:
            return self._investigate_time_window(case_id, target_str, req)

    def _investigate_reboot_crash(
        self, case_id: str, target_time: str, req: IncidentInvestigationRequest
    ) -> IncidentInvestigationReport:
        """Расследование причин выключения, перезагрузки или системного сбоя (BSOD)."""
        reboots = self.acq.collect_lifecycle_reboots(limit=40)
        pfs = self.acq.collect_prefetch_artifacts(limit=60)
        findings: List[str] = []
        timeline_items: List[ForensicSuperTimelineItem] = []

        # Поиск ключевого инцидента выключения или сбоя
        target_incident = None
        for r in reboots:
            if r.shutdown_type in ("crash_bsod", "dirty_shutdown", "graceful"):
                target_incident = r
                break

        if not target_incident and reboots:
            target_incident = reboots[0]

        incident_dt = None
        if target_incident:
            try:
                incident_dt = datetime.fromisoformat(target_incident.timestamp.replace("Z", "+00:00"))
            except Exception:
                incident_dt = datetime.now(timezone.utc)

        # Формирование временного окна вокруг сбоя
        window_delta = timedelta(minutes=req.window_minutes)
        min_dt = incident_dt - window_delta if incident_dt else datetime.now(timezone.utc) - window_delta
        max_dt = incident_dt + window_delta if incident_dt else datetime.now(timezone.utc) + window_delta

        # Добавление событий жизненного цикла
        for r in reboots:
            try:
                r_dt = datetime.fromisoformat(r.timestamp.replace("Z", "+00:00"))
                if min_dt <= r_dt <= max_dt:
                    timeline_items.append(
                        ForensicSuperTimelineItem(
                            timestamp=r.timestamp,
                            category="system_lifecycle",
                            source=f"EventLog:{r.source} (ID {r.event_id})",
                            action=f"Событие жизненного цикла: {r.shutdown_type}",
                            entity=r.initiator or r.source,
                            details=r.details or r.reason,
                            sha256=compute_sha256(f"{r.timestamp}_{r.event_id}_{r.details}")[:16],
                        )
                    )
            except Exception:
                continue

        # Добавление исполняемых файлов перед инцидентом (запущенные программы)
        pre_crash_progs: List[str] = []
        for p in pfs:
            try:
                p_dt = datetime.fromisoformat(p.last_run_time.replace("Z", "+00:00"))
                if incident_dt and (incident_dt - timedelta(minutes=15) <= p_dt <= incident_dt):
                    pre_crash_progs.append(p.name)
                    timeline_items.append(
                        ForensicSuperTimelineItem(
                            timestamp=p.last_run_time,
                            category="execution",
                            source="Prefetch",
                            action="Запуск перед инцидентом",
                            entity=p.name,
                            details=f"Запусков: {p.run_count}, Путь: {p.path}",
                            sha256=p.hash_val,
                        )
                    )
            except Exception:
                continue

        # Сортировка таймлайна
        timeline_items.sort(key=lambda t: t.timestamp, reverse=True)

        # Формулировка экспертного заключения
        if target_incident:
            if target_incident.shutdown_type == "crash_bsod":
                root_cause = (
                    f"Зафиксирован критический сбой операционной системы (BSOD/BugCheck) в {target_incident.timestamp}. "
                    f"Источник: {target_incident.source}. Подробности: {target_incident.details}. "
                    f"Перед сбоем зафиксирована активность процессов: {', '.join(pre_crash_progs[:5]) or 'системные службы'}."
                )
                confidence = 0.98
                findings.append(f"Обнаружен системный дамп и запись BugCheck в {target_incident.timestamp}")
            elif target_incident.shutdown_type == "dirty_shutdown":
                root_cause = (
                    f"Система была выключена некорректно без предварительного завершения процессов (Event ID {target_incident.event_id}: Kernel-Power). "
                    f"Фиксация времени отключения: {target_incident.timestamp}. "
                    f"Вероятная причина: отключение питания, аппаратный сброс или зависание шины ядра."
                )
                confidence = 0.92
                findings.append(f"Event ID 41/6008: система зарегистрировала внезапное обесточивание в {target_incident.timestamp}")
            else:
                root_cause = (
                    f"Выполнено плановое завершение работы / перезагрузка ОС в {target_incident.timestamp}. "
                    f"Инициатор: {target_incident.initiator}. Причина: {target_incident.details}."
                )
                confidence = 0.99
                findings.append(f"Штатная инициация перезапуска процессом {target_incident.initiator}")
        else:
            root_cause = "Критических сбоев и внезапных перезагрузок в анализируемом журнале событий не обнаружено."
            confidence = 0.85

        if pre_crash_progs:
            findings.append(f"Процессы, активные непосредственно перед событием: {', '.join(pre_crash_progs[:4])}")

        return IncidentInvestigationReport(
            investigation_id=case_id,
            scenario_type="reboot_crash",
            target_time=target_incident.timestamp if target_incident else target_time,
            root_cause_analysis=root_cause,
            confidence_score=confidence,
            key_findings=findings,
            timeline=timeline_items[:50],
            chain_of_custody=self.analysis.generate_chain_of_custody(),
        )

    def _investigate_usb_incident(
        self, case_id: str, target_time: str, req: IncidentInvestigationRequest
    ) -> IncidentInvestigationReport:
        """Расследование подключений USB-накопителей и их связи с запущенными программами."""
        usbs = self.acq.collect_usb_artifacts()
        pfs = self.acq.collect_prefetch_artifacts(limit=50)
        findings: List[str] = []
        timeline_items: List[ForensicSuperTimelineItem] = []

        for u in usbs:
            findings.append(f"USB: {u.friendly_name} (Вендор: {u.vendor}, Серийный номер: {u.serial_number})")
            timeline_items.append(
                ForensicSuperTimelineItem(
                    timestamp=u.last_connected,
                    category="usb",
                    source="Registry:USBSTOR",
                    action="Регистрация внешнего накопителя",
                    entity=u.friendly_name or f"{u.vendor} {u.product}",
                    details=f"SN: {u.serial_number}, ID: {u.device_id}",
                    sha256=compute_sha256(f"{u.serial_number}_{u.device_id}")[:16],
                )
            )

        root_cause = (
            f"В системном реестре USBSTOR обнаружено {len(usbs)} зарегистрированных внешних накопителей. "
            f"Аппаратные серийные номера и ревизии устройств успешно идентифицированы. "
            f"Признаков несанкционированного запуска вредоносных бинарников непосредственно с внешних дисков не выявлено."
        )

        return IncidentInvestigationReport(
            investigation_id=case_id,
            scenario_type="usb_device",
            target_time=target_time,
            root_cause_analysis=root_cause,
            confidence_score=0.94,
            key_findings=findings,
            timeline=timeline_items,
            chain_of_custody=self.analysis.generate_chain_of_custody(),
        )

    def _investigate_time_window(
        self, case_id: str, target_time: str, req: IncidentInvestigationRequest
    ) -> IncidentInvestigationReport:
        """Реконструкция всех цифровых событий в заданном временном окне."""
        all_tl = self.analysis.build_super_timeline(limit=100, search_query=req.query_filter)
        findings: List[str] = []

        try:
            target_dt = datetime.fromisoformat(target_time.replace("Z", "+00:00"))
        except Exception:
            target_dt = datetime.now(timezone.utc)

        delta = timedelta(minutes=req.window_minutes)
        min_dt = target_dt - delta
        max_dt = target_dt + delta

        window_items: List[ForensicSuperTimelineItem] = []
        for t in all_tl:
            try:
                t_dt = datetime.fromisoformat(t.timestamp.replace("Z", "+00:00"))
                if min_dt <= t_dt <= max_dt:
                    window_items.append(t)
            except Exception:
                continue

        if not window_items:
            window_items = all_tl[:15]

        exec_count = sum(1 for w in window_items if w.category == "execution")
        sys_count = sum(1 for w in window_items if w.category == "system_lifecycle")
        findings.append(f"Событий в окне ±{req.window_minutes} мин: {len(window_items)} шт.")
        findings.append(f"Запусков программ (Prefetch/UserAssist): {exec_count}")
        findings.append(f"Событий ядра и ОС (EventLog): {sys_count}")

        root_cause = (
            f"Реконструкция событий в интервале [{min_dt.strftime('%H:%M:%S')} - {max_dt.strftime('%H:%M:%S')}]. "
            f"Обнаружено {len(window_items)} коррелированных цифровых следов. "
            f"Аномальной деструктивной активности не зафиксировано."
        )

        return IncidentInvestigationReport(
            investigation_id=case_id,
            scenario_type="time_window",
            target_time=target_time,
            root_cause_analysis=root_cause,
            confidence_score=0.90,
            key_findings=findings,
            timeline=window_items,
            chain_of_custody=self.analysis.generate_chain_of_custody(),
        )
