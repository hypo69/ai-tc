# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Software Scanner - Report Formatter
# =============================================================================
# Description:
#   Форматирование и экспорт результатов глубокого сканирования ПО в JSON,
#   словари и человекочитаемые отчеты.
#
# File: report.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.software_scanner
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 19:20:00
# =============================================================================

from __future__ import annotations
"""Генератор и экспортер отчетов глубокого сканирования ПО."""

from dataclasses import asdict
import json
from typing import Any, Dict
from apps.windows.sdk.software_scanner.models import ScanReport, SoftwareStatus


class ReportFormatter:
    """Форматировщик отчетов сканирования ПО."""

    @staticmethod
    def to_dict(report: ScanReport) -> Dict[str, Any]:
        """Преобразование отчета в сериализуемый словарь Python."""
        return asdict(report)

    @staticmethod
    def to_json(report: ScanReport, pretty: bool = True) -> str:
        """Сериализация отчета в JSON-строку."""
        data = ReportFormatter.to_dict(report)
        return json.dumps(data, indent=2 if pretty else None, ensure_ascii=False)

    @staticmethod
    def format_summary_markdown(report: ScanReport) -> str:
        """Формирование сводного Markdown-отчета для отображения пользователю."""
        lines = [
            f"# Отчет глубокого аудита ПО (Режим: {report.mode.value.upper()})",
            f"- **Идентификатор сканирования:** `{report.scan_id}`",
            f"- **Время выполнения:** {report.stats.duration_ms:.2f} мс",
            f"- **Всего найдено следов:** {report.stats.total_evidence_found}",
            f"- **Идентифицировано программ:** {report.stats.total_software_identified}",
            f"  - 🟢 Активных: **{report.stats.active_count}**",
            f"  - 🟡 Давно не запускавшихся (Dormant): **{report.stats.dormant_count}**",
            f"  - 🔴 Остатков/сирот (Orphans): **{report.stats.orphan_count}**",
            f"  - ⚠️ Ошибок доступа: **{report.stats.errors_count}**",
            "",
            "## 🟡 Программы, которые давно не запускались (Dormant)",
            "| Программа | Издатель | Версия | Дней без запуска | Запусков | Команда деинсталляции |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ]

        dormant_cards = [c for c in report.inventory if c.status in (SoftwareStatus.DORMANT, SoftwareStatus.NEVER_LAUNCHED)]
        if not dormant_cards:
            lines.append("| *Нет программ, подпадающих под критерий спящих* | - | - | - | - | - |")
        else:
            for card in dormant_cards[:30]:
                days_str = f"{card.days_since_last_run} дн." if card.days_since_last_run is not None else "Никогда"
                uninst = f"`{card.uninstall_string[:40]}...`" if card.uninstall_string else "—"
                lines.append(
                    f"| **{card.name}** | {card.publisher or '—'} | {card.version or '—'} | "
                    f"{days_str} | {card.run_count} | {uninst} |"
                )

        if report.orphan_items:
            lines.extend([
                "",
                "## 🔴 Обнаруженные сироты и битые ссылки",
                "| Источник | Путь / Имя | Причина |",
                "| :--- | :--- | :--- |",
            ])
            for orph in report.orphan_items[:20]:
                lines.append(f"| {orph.source} | `{orph.path}` | {orph.product_name} |")

        return "\n".join(lines)


__all__ = ["ReportFormatter"]

