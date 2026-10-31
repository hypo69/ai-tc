# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Tshark - Traffic Analyzer
# =============================================================================
# Description:
#   Модуль эвристического анализа сетевого трафика и подсчета статистики пакетов.
#
# Usage Examples:
#   Python API:
#     from apps.tshark.analyzer import TrafficAnalyzer
#
#     analyzer = TrafficAnalyzer()
#     stats = analyzer.compute_stats(packets)
#     heuristics = analyzer.detect_heuristics(packets)
#
# File: analyzer.py
# Project: ai-windows-admin
# Package: apps.tshark
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-20 13:22:00
# =============================================================================

from __future__ import annotations
"""Модуль эвристического анализа сетевого трафика и подсчета статистики пакетов."""

from collections import Counter, defaultdict
from typing import List
from .models import PacketSummary, TrafficStats


class TrafficAnalyzer:
    """Анализатор сетевого трафика и статистический процессор пакетов."""

    def compute_stats(self, packets: List[PacketSummary]) -> TrafficStats:
        """Вычисление суммарной статистики и распределений по буферу пакетов.

        Args:
            packets (List[PacketSummary]): Список пакетов для агрегации.

        Returns:
            TrafficStats: Сформированный объект статистики.
        """
        if not packets:
            return TrafficStats()

        total_bytes = sum(p.length for p in packets)
        proto_counts: Counter[str] = Counter()
        src_counts: Counter[str] = Counter()
        dst_counts: Counter[str] = Counter()

        for p in packets:
            proto_name = (p.protocol or "UNKNOWN").upper()
            proto_counts[proto_name] += 1
            if p.source:
                src_counts[p.source] += 1
            if p.destination:
                dst_counts[p.destination] += 1

        top_sources = dict(src_counts.most_common(10))
        top_destinations = dict(dst_counts.most_common(10))

        return TrafficStats(
            total_packets=len(packets),
            total_bytes=total_bytes,
            protocol_distribution=dict(proto_counts),
            top_sources=top_sources,
            top_destinations=top_destinations,
        )

    def detect_heuristics(self, packets: List[PacketSummary]) -> List[str]:
        """Эвристический поиск потенциальных сетевых угроз и аномалий.

        Args:
            packets (List[PacketSummary]): Пакеты для инспекции.

        Returns:
            List[str]: Список текстовых предупреждений о выявленных аномалиях.
        """
        if not packets:
            return []

        warnings: List[str] = []
        src_to_dst_ports: defaultdict[str, set[int]] = defaultdict(set)
        unencrypted_protos: set[str] = set()
        dns_queries_count = 0

        for p in packets:
            proto = (p.protocol or "").upper()
            dst_port = p.destination_port

            if dst_port in (21, 23, 80) or proto in ("TELNET", "FTP", "HTTP"):
                unencrypted_protos.add(proto or f"Port-{dst_port}")

            if p.source and dst_port:
                src_to_dst_ports[p.source].add(dst_port)

            if proto == "DNS" or dst_port == 53:
                dns_queries_count += 1

        # Проверка на сканирование портов (один хост обращается к множеству разных портов)
        for src_ip, ports in src_to_dst_ports.items():
            if len(ports) >= 15:
                warnings.append(f"Подозрение на сканирование портов с узла {src_ip} ({len(ports)} уникальных портов)")

        # Проверка на незашифрованные протоколы передачи данных
        if unencrypted_protos:
            protos_str = ", ".join(sorted(unencrypted_protos))
            warnings.append(f"Обнаружен незашифрованный трафик открытых протоколов: {protos_str}")

        # Проверка на аномальный всплеск DNS запросов
        if len(packets) >= 20 and (dns_queries_count / len(packets)) > 0.5:
            warnings.append(f"Высокая концентрация DNS-запросов: {dns_queries_count} из {len(packets)} пакетов")

        return warnings

