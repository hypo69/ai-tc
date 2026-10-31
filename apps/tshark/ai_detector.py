# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Tshark - AI Detector
# =============================================================================
# Description:
#   Модуль интеллектуального аудита и классификации сетевых аномалий.
#
# Usage Examples:
#   Python API:
#     from apps.tshark.ai_detector import AIDetector
#
#     detector = AIDetector()
#     report = await detector.diagnose_traffic(packets, stats, heuristics)
#
# File: ai_detector.py
# Project: ai-windows-admin
# Package: apps.tshark
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-20 13:22:00
# =============================================================================

from __future__ import annotations
"""Модуль интеллектуального аудита и классификации сетевых аномалий."""

from typing import List
from .models import AnomalyReport, PacketSummary, TrafficStats


class AIDetector:
    """Детектор аномалий и классификатор сетевых инцидентов."""

    async def diagnose_traffic(
        self,
        packets: List[PacketSummary],
        stats: TrafficStats,
        heuristics: List[str],
    ) -> AnomalyReport:
        """Интеллектуальная оценка профиля сетевого трафика.

        Args:
            packets (List[PacketSummary]): Перехваченные пакеты.
            stats (TrafficStats): Метрики агрегации трафика.
            heuristics (List[str]): Список ранее выявленных эвристических сигнатур.

        Returns:
            AnomalyReport: Сформированный структурированный отчет безопасности.
        """
        health_score = 100
        anomalies: List[str] = list(heuristics)

        if heuristics:
            health_score = max(20, 100 - (len(heuristics) * 25))

        if health_score <= 50:
            threat_level = "CRITICAL"
            summary = f"Обнаружены критические сетевые отклонения: {len(heuristics)} предупреждений."
        elif health_score < 85:
            threat_level = "SUSPICIOUS"
            summary = f"Обнаружена подозрительная сетевая активность ({len(heuristics)} предупреждений)."
        else:
            threat_level = "NORMAL"
            summary = f"Сетевой трафик стабилен ({stats.total_packets} пакетов проверено, угроз не выявлено)."

        return AnomalyReport(
            threat_level=threat_level,
            summary=summary,
            health_score=health_score,
            anomalies=anomalies,
            details={
                "total_inspected_packets": len(packets),
                "total_bytes": stats.total_bytes,
                "protocols_count": len(stats.protocol_distribution),
            },
        )

