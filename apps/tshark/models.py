# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Tshark - Models
# =============================================================================
# Description:
#   Модели данных для работы с TShark, сетевыми пакетами и анализом трафика.
#
# Usage Examples:
#   Python API:
#     from apps.tshark.models import PacketSummary, TrafficStats
#
#     pkt = PacketSummary(packet_number=1, timestamp="2026-10-20T12:00:00Z", source="192.168.1.2", destination="1.1.1.1", protocol="DNS", length=64)
#
# File: models.py
# Project: ai-windows-admin
# Package: apps.tshark
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-20 13:22:00
# =============================================================================

from __future__ import annotations
"""Модели данных для сетевого анализа и захвата TShark."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class NetworkInterface(BaseModel):
    """Сетевой интерфейс для захвата трафика через TShark."""
    id: str = Field(..., description="Порядковый номер или идентификатор интерфейса")
    name: str = Field(..., description="Системное имя интерфейса (NPF UUID или адаптер)")
    description: str = Field("", description="Человекочитаемое описание интерфейса")


class CaptureFilter(BaseModel):
    """Параметры фильтрации сетевого захвата."""
    interface: str = Field("1", description="Идентификатор или имя интерфейса")
    display_filter: str = Field("", description="Строка фильтра Wireshark / TShark (display filter)")


class PacketSummary(BaseModel):
    """Сводная информация об отдельном перехваченном сетевом пакете."""
    packet_number: int = Field(..., description="Порядковый номер пакета в сессии")
    timestamp: str = Field(..., description="Временная метка захвата пакета в формате ISO или epoch")
    source: str = Field(..., description="IP-адрес или MAC-адрес отправителя")
    destination: str = Field(..., description="IP-адрес или MAC-адрес получателя")
    protocol: str = Field("UNKNOWN", description="Протокол прикладного или транспортного уровня")
    length: int = Field(0, description="Размер пакета в байтах")
    source_port: Optional[int] = Field(None, description="Порт источника для TCP/UDP")
    destination_port: Optional[int] = Field(None, description="Порт назначения для TCP/UDP")
    info: Optional[str] = Field("", description="Краткое описание содержимого пакета")

    @property
    def number(self) -> int:
        """Псевдоним порядкового номера пакета."""
        return self.packet_number

    @property
    def source_ip(self) -> str:
        """Псевдоним адреса источника."""
        return self.source

    @property
    def destination_ip(self) -> str:
        """Псевдоним адреса назначения."""
        return self.destination


class TrafficStats(BaseModel):
    """Агрегированная статистика захваченного трафика."""
    total_packets: int = Field(0, description="Общее число пакетов")
    total_bytes: int = Field(0, description="Общий объем переданных данных в байтах")
    protocol_distribution: Dict[str, int] = Field(default_factory=dict, description="Распределение пакетов по протоколам")
    top_sources: Dict[str, int] = Field(default_factory=dict, description="Наиболее активные источники трафика")
    top_destinations: Dict[str, int] = Field(default_factory=dict, description="Наиболее частые адреса назначения")


class AnomalyReport(BaseModel):
    """Отчет об аномалиях сетевой безопасности и эвристической оценке."""
    threat_level: str = Field("NORMAL", description="Уровень угрозы (NORMAL, SUSPICIOUS, CRITICAL)")
    summary: str = Field("Аномалий в сетевом трафике не обнаружено", description="Текстовое резюме отчета")
    health_score: int = Field(100, description="Оценка безопасности сети (от 0 до 100)")
    anomalies: List[str] = Field(default_factory=list, description="Список обнаруженных подозрительных сигнатур")
    details: Dict[str, Any] = Field(default_factory=dict, description="Дополнительные диагностические метрики")

