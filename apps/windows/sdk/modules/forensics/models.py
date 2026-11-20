# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Forensics Module - Models
# =============================================================================
# Description:
#   Модели данных цифровой криминалистики (Digital Forensics):
#   - Артефакты исполнения (Prefetch, UserAssist, Shimcache)
#   - Аппаратные доказательства (USBSTOR, внешние накопители)
#   - Жизненный цикл ОС (перезагрузки, сбои, выключения, BSOD)
#   - События безопасности (вход/выход пользователей)
#   - Единый супер-таймлайн и цепочка сохранности доказательств (Chain of Custody)
#   - Модели интеллектуального расследования инцидентов (Incident Reconstruction)
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.forensics.models import ForensicSuperTimelineItem
#
# File: models.py
# Project: ai-tc
# Package: apps.windows.sdk.modules.forensics
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 12:45:00
# =============================================================================

from __future__ import annotations
"""Модели данных Pydantic для цифровой криминалистики (Forensics) в AI-TC."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ExecutionArtifact(BaseModel):
    """Артефакт выполнения программы (Prefetch, UserAssist, Shimcache)."""
    name: str = Field(..., description="Имя исполняемого файла")
    source: str = Field("Prefetch", description="Источник артефакта: Prefetch, UserAssist, Shimcache")
    path: str = Field("", description="Полный путь или путь к Prefetch-файлу")
    run_count: int = Field(1, description="Количество подтвержденных запусков")
    last_run_time: str = Field("", description="Время последнего запуска (ISO-8601)")
    hash_val: str = Field("", description="Prefetch хэш или вычисленный SHA-256")
    focus_duration: str = Field("", description="Длительность удержания фокуса (для UserAssist)")


class UsbEvidence(BaseModel):
    """Доказательство подключения USB-устройства из реестра USBSTOR."""
    device_id: str = Field(..., description="Идентификатор экземпляра устройства")
    vendor: str = Field("Generic", description="Производитель (Vendor)")
    product: str = Field("", description="Наименование модели/продукта")
    revision: str = Field("", description="Ревизия прошивки")
    serial_number: str = Field("", description="Уникальный серийный номер накопителя")
    friendly_name: str = Field("", description="Отображаемое имя в Windows")
    last_connected: str = Field("", description="Время последнего обнаружения или фиксации")


class RebootIncident(BaseModel):
    """Инцидент жизненного цикла системы (перезагрузка, выключение, BSOD)."""
    timestamp: str = Field(..., description="Время события ISO-8601")
    event_id: int = Field(..., description="Код события EventLog (41, 1074, 6008, 1001, 12, 13)")
    shutdown_type: str = Field("graceful", description="Тип: graceful, dirty_shutdown, crash_bsod, reboot_update")
    source: str = Field("Kernel-Power", description="Источник события")
    reason: str = Field("", description="Расшифрованная причина завершения работы")
    initiator: str = Field("", description="Инициатор (процесс, пользователь или ядро)")
    details: str = Field("", description="Подробности (код BugCheck, параметры)")


class SecurityLogonEvidence(BaseModel):
    """Артефакт аутентификации и входа в систему (Security.evtx)."""
    timestamp: str = Field(..., description="Время попытки входа ISO-8601")
    event_id: int = Field(..., description="4624 (успех), 4625 (отказ), 4634/4647 (выход)")
    username: str = Field(..., description="Имя учетной записи")
    domain: str = Field("", description="Домен или имя рабочей станции")
    logon_type: str = Field("Interactive", description="Тип входа (Interactive, Network, Service, RDP)")
    ip_address: str = Field("", description="IP-адрес источника")
    status: str = Field("Success", description="Статус: Success или Failure")


class ChainOfCustodyRecord(BaseModel):
    """Запись цепочки сохранности доказательства (Chain of Custody)."""
    evidence_id: str = Field(..., description="Уникальный ID доказательства")
    artifact_type: str = Field(..., description="Тип артефакта: prefetch, usbstor, event_log, memory")
    source_location: str = Field(..., description="Физическое или реестровое местоположение")
    sha256_hash: str = Field(..., description="Криптографический хэш SHA-256 исходных данных")
    acquired_at: str = Field(..., description="Точное время фиксации доказательства")
    investigator: str = Field("AI-TC Forensic Engine", description="Модуль фиксации")
    verified: bool = Field(True, description="Подтверждение неизменности артефакта")


class ForensicSuperTimelineItem(BaseModel):
    """Единый элемент супер-таймлайна цифровой криминалистики."""
    timestamp: str = Field(..., description="Время фиксации ISO-8601")
    category: str = Field(..., description="Категория: execution, usb, system_lifecycle, security, audio_media")
    source: str = Field(..., description="Источник: Prefetch, UserAssist, USBSTOR, EventLog, WASAPI")
    action: str = Field(..., description="Действие: Запуск, Подключение, Сбой, Вход, Звук")
    entity: str = Field(..., description="Объект: имя файла, процесса, устройства, пользователя")
    details: str = Field("", description="Дополнительное контекстное описание")
    sha256: str = Field("", description="Контрольный хэш SHA-256 доказательства")


class IncidentInvestigationRequest(BaseModel):
    """Запрос на интеллектуальное расследование инцидента."""
    scenario_type: str = Field("time_window", description="reboot_crash, usb_device, time_window, malware_anomaly")
    timestamp_target: Optional[str] = Field(None, description="Целевое время инцидента ISO-8601 (например, '2026-11-12T14:32:00')")
    window_minutes: int = Field(30, ge=5, le=720, description="Ширина временного окна расследования в минутах")
    query_filter: Optional[str] = Field(None, description="Текстовый фильтр (имя процесса, устройства, пользователя)")


class IncidentInvestigationReport(BaseModel):
    """Итоговый экспертный отчет цифрового криминалистического расследования."""
    investigation_id: str = Field(..., description="Уникальный номер дела / расследования")
    scenario_type: str = Field(..., description="Тип расследованного инцидента")
    target_time: str = Field(..., description="Временной ориентир инцидента")
    root_cause_analysis: str = Field(..., description="Автоматическое экспертное заключение о первопричине")
    confidence_score: float = Field(..., description="Степень доказательной достоверности от 0.0 до 1.0")
    key_findings: List[str] = Field(default_factory=list, description="Ключевые установленные факты")
    timeline: List[ForensicSuperTimelineItem] = Field(default_factory=list, description="Хронологический таймлайн событий инцидента")
    chain_of_custody: List[ChainOfCustodyRecord] = Field(default_factory=list, description="Цепочка сохранности доказательств дела (SHA-256)")
