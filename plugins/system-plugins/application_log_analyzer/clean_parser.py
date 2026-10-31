# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Application Log Analyzer - Parser & Diagnostics
# =============================================================================
# Description:
#   Структурированный парсер логов, анализатор паттернов ошибок и синтезатор отчётов.
#
# File: clean_parser.py
# Package: plugins.system-plugins.application_log_analyzer
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-28 18:26:00
# =============================================================================

from __future__ import annotations

"""Парсер и анализатор логов для системного плагина application_log_analyzer."""

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

from logger import logger
from logger.log_analyzer import get_default_log_dir, get_default_reports_dir


@dataclass
class LogEntry:
    """Структура единичной записи лога."""

    timestamp: str = ""
    level: str = "INFO"
    message: str = ""
    logger_name: str = ""
    raw: str = ""


@dataclass
class AnalysisResult:
    """Результат анализа набора записей логов."""

    total_events: int = 0
    level_counts: Dict[str, int] = field(default_factory=dict)
    top_errors: List[Dict[str, Any]] = field(default_factory=list)
    trends: Dict[str, Any] = field(default_factory=dict)


class LogParser:
    """Парсер текстовых и JSON строк логов."""

    LOG_PATTERN = re.compile(
        r"^(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:,\d+)?)\s*-\s*([A-Z]+)\s*-\s*(.*)$"
    )

    def parse_text(self, content: str) -> List[LogEntry]:
        """Парсит текстовые строки лога."""
        entries: List[LogEntry] = []
        if not content:
            return entries

        current_entry: Optional[LogEntry] = None
        for line in content.splitlines():
            line_str = line.strip()
            if not line_str:
                continue

            match = self.LOG_PATTERN.match(line_str)
            if match:
                if current_entry:
                    entries.append(current_entry)
                timestamp, level, message = match.groups()
                current_entry = LogEntry(
                    timestamp=timestamp,
                    level=level.upper(),
                    message=message.strip(),
                    raw=line_str,
                )
            else:
                if current_entry:
                    current_entry.message += f"\n{line_str}"
                    current_entry.raw += f"\n{line_str}"
                else:
                    current_entry = LogEntry(level="INFO", message=line_str, raw=line_str)

        if current_entry:
            entries.append(current_entry)

        return entries

    def parse_json_lines(self, content: str) -> List[LogEntry]:
        """Парсит строки лога в формате JSON."""
        entries: List[LogEntry] = []
        if not content:
            return entries

        for line in content.splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            try:
                data = json.loads(line_str)
                entries.append(
                    LogEntry(
                        timestamp=str(data.get("timestamp") or data.get("time") or ""),
                        level=str(data.get("level") or "INFO").upper(),
                        message=str(data.get("message") or data.get("msg") or ""),
                        logger_name=str(data.get("logger") or ""),
                        raw=line_str,
                    )
                )
            except Exception:
                entries.extend(self.parse_text(line_str))

        return entries


class LogAnalyzer:
    """Анализатор статистических метрик и частых ошибок логов."""

    def __init__(self, parser: Optional[LogParser] = None) -> None:
        """Инициализация анализатора."""
        self.parser = parser or LogParser()

    def analyze_entries(self, entries: List[LogEntry]) -> AnalysisResult:
        """Анализирует список записей и возвращает структурированный отчёт."""
        total = len(entries)
        level_counts: Dict[str, int] = {
            "DEBUG": 0,
            "INFO": 0,
            "WARNING": 0,
            "ERROR": 0,
            "CRITICAL": 0,
        }
        error_map: Dict[str, int] = {}

        for e in entries:
            lvl = e.level.upper()
            level_counts[lvl] = level_counts.get(lvl, 0) + 1

            if lvl in ("ERROR", "CRITICAL"):
                first_line = e.message.splitlines()[0][:120].strip()
                error_map[first_line] = error_map.get(first_line, 0) + 1

        sorted_errors = sorted(error_map.items(), key=lambda x: x[1], reverse=True)[:10]
        top_errors = [{"pattern": err, "count": cnt} for err, cnt in sorted_errors]

        return AnalysisResult(
            total_events=total,
            level_counts=level_counts,
            top_errors=top_errors,
        )


def format_markdown_report(result: AnalysisResult, target_name: str = "Logs") -> str:
    """Форматирует результат анализа в Markdown отчёт."""
    lines = [
        f"## 📊 Отчёт анализа логов: {target_name}",
        "",
        f"- **Всего событий:** {result.total_events}",
        f"- **Ошибок (ERROR):** {result.level_counts.get('ERROR', 0)}",
        f"- **Критических сбоев (CRITICAL):** {result.level_counts.get('CRITICAL', 0)}",
        f"- **Предупреждений (WARNING):** {result.level_counts.get('WARNING', 0)}",
        f"- **Информационных сообщений (INFO):** {result.level_counts.get('INFO', 0)}",
        "",
        "### 🔍 Наиболее частые ошибки",
    ]

    if not result.top_errors:
        lines.append("Критических ошибок и сбоев не обнаружено.")
    else:
        for idx, item in enumerate(result.top_errors, 1):
            lines.append(f"{idx}. `{item['pattern']}` — **{item['count']} раз**")

    return "\n".join(lines)


async def run_ai_synthesis(raw_sample: List[str], res: AnalysisResult) -> str:
    """Формирует ИИ-заключение по собранным логам."""
    try:
        from src.ai import UnifiedChatModel
        chat = UnifiedChatModel()
        prompt = (
            f"Проанализируй сводку системных логов:\n"
            f"Всего событий: {res.total_events}, Ошибок: {res.level_counts.get('ERROR', 0)}\n"
            f"Частые ошибки: {json.dumps(res.top_errors, ensure_ascii=False)}\n"
            f"Кратко укажи возможные первопричины и рекомендации по исправлению на русском языке."
        )
        response = await chat.generate_response(prompt)
        return str(response)
    except Exception as exc:
        logger.debug(f"[run_ai_synthesis] Gemini AI недоступен: {exc}")
        return "Автоматический ИИ-анализ недоступен или API-ключ не настроен."


__all__ = [
    "LogEntry",
    "AnalysisResult",
    "LogParser",
    "LogAnalyzer",
    "format_markdown_report",
    "run_ai_synthesis",
    "get_default_log_dir",
    "get_default_reports_dir",
]

