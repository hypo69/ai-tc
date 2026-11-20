# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Screen Capture - Visual Intelligence Engine
# =============================================================================
# Description:
#   Движок визуальной аналитики и корреляции экранных снимков с системной
#   ETW-телеметрией, выявление визуальных зависаний и история состояний.
#
# Usage Examples:
#   from apps.windows.vision.screen_capture.visual_intelligence import VisualIntelligenceEngine
#   intel = VisualIntelligenceEngine()
#   event = intel.correlate(frame, window_info)
#
# File: visual_intelligence.py
# Project: ai-windows-admin
# Package: apps.windows.vision.screen_capture
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 02:51:00
# =============================================================================

from __future__ import annotations
"""Аналитический движок визуальной диагностики и связи с ETW телеметрией."""

from collections import deque
from datetime import datetime, timezone
import os
from typing import Any, Deque, Dict, List, Optional
import psutil

from logger import logger
from apps.windows.vision.screen_capture.models import (
    CapturedFrame,
    VisualTelemetryEvent,
    WindowInfo,
)


class VisualIntelligenceEngine:
    """Интеллектуальный анализатор визуальных состояний и телеметрической корреляции."""

    def __init__(self, max_history_events: int = 100) -> None:
        """
        Инициализация хранилища событий визуальной телеметрии.

        Args:
            max_history_events: Максимальное количество хранимых диагностических записей.
        """
        self._events: Deque[VisualTelemetryEvent] = deque(maxlen=max_history_events)
        self._frame_history: Deque[CapturedFrame] = deque(maxlen=50)

    def record_frame(self, frame: CapturedFrame) -> None:
        """Сохраняет снимок в кольцевой буфер истории состояний рабочего стола."""
        self._frame_history.append(frame)

    def get_frame_history(self, limit: int = 20) -> List[CapturedFrame]:
        """Возвращает последние снимки из визуальной истории."""
        items = list(self._frame_history)
        return items[-limit:] if limit > 0 else items

    def get_events_history(self, limit: int = 50) -> List[VisualTelemetryEvent]:
        """Возвращает историю событий корреляции экрана и телеметрии."""
        items = list(self._events)
        return items[-limit:] if limit > 0 else items

    def sample_system_telemetry(self) -> Dict[str, float]:
        """Считывает оперативные числовые показатели системы (CPU, RAM, диск)."""
        try:
            cpu = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory()
            disk = psutil.disk_io_counters()
            disk_active = 0.0
            if disk:
                # Ориентировочный показатель активности диска
                disk_active = min(100.0, (disk.read_bytes + disk.write_bytes) / (1024 * 1024 * 50) * 100.0)

            return {
                "cpu_percent": round(cpu, 1),
                "memory_mb": round(mem.used / (1024 * 1024), 1),
                "memory_percent": round(mem.percent, 1),
                "disk_active_percent": round(disk_active, 1),
            }
        except Exception:
            return {
                "cpu_percent": 0.0,
                "memory_mb": 0.0,
                "memory_percent": 0.0,
                "disk_active_percent": 0.0,
            }

    def correlate(
        self,
        frame: CapturedFrame,
        window_info: Optional[WindowInfo] = None,
        etw_incidents_count: int = 0,
    ) -> VisualTelemetryEvent:
        """
        Связывает визуальный снимок экрана с показателями телеметрии и ETW.

        Args:
            frame: Захваченный кадр.
            window_info: Сведения об исследуемом окне приложения (если цель - окно).
            etw_incidents_count: Число зарегистрированных аномалий ядра Windows / ETW.

        Returns:
            VisualTelemetryEvent: Структурированное диагностическое событие.
        """
        metrics = self.sample_system_telemetry()
        cpu_p = metrics["cpu_percent"]
        mem_mb = metrics["memory_mb"]
        disk_p = metrics["disk_active_percent"]

        # Анализ зависания интерфейса: IsHungAppWindow или отсутствие изменений при высоком CPU
        is_hung = False
        notes = []

        if window_info:
            target_name = f"Window: {window_info.title} [{window_info.process_name or 'PID ' + str(window_info.pid)}]"
            if window_info.is_hung:
                is_hung = True
                notes.append("Обнаружено зависание окна (Windows IsHungAppWindow = True)")
            elif frame.diff_ratio < 0.001 and cpu_p > 85.0:
                notes.append("Предупреждение: Высокая загрузка CPU при статичном интерфейсе")
        else:
            target_name = f"Display: {frame.target_title or frame.target_id}"

        diff_detected = frame.diff_ratio > 0.005
        if not diff_detected:
            notes.append("Интерфейс статичен (без визуальных изменений)")
        else:
            notes.append(f"Визуальная активность: {frame.diff_ratio * 100:.1f}% площади")

        if etw_incidents_count > 0:
            notes.append(f"Зафиксировано {etw_incidents_count} инцидентов ETW ядра Windows")

        event = VisualTelemetryEvent(
            timestamp_utc=frame.timestamp_utc,
            frame_id=frame.frame_id,
            target_name=target_name,
            cpu_percent=cpu_p,
            memory_mb=mem_mb,
            disk_active_percent=disk_p,
            etw_incident_count=etw_incidents_count,
            is_app_hung=is_hung,
            diff_detected=diff_detected,
            diff_ratio=frame.diff_ratio,
            analysis_notes=" | ".join(notes) if notes else "Нормальное рабочее состояние",
        )

        self._events.append(event)
        self.record_frame(frame)
        return event

    def compare_snapshots(
        self,
        before_frame: CapturedFrame,
        after_frame: CapturedFrame,
        action_name: str = "Command Execution",
    ) -> Dict[str, Any]:
        """
        Сравнивает состояние интерфейса до и после выполнения команды (PowerShell, скрипта).

        Returns:
            Dict[str, Any]: Отчет о визуальных и системных сдвигах.
        """
        diff = abs(after_frame.diff_ratio - before_frame.diff_ratio)
        return {
            "action": action_name,
            "before_frame_id": before_frame.frame_id,
            "after_frame_id": after_frame.frame_id,
            "diff_magnitude": round(diff, 4),
            "state_changed": diff > 0.01,
            "summary": (
                f"Действие '{action_name}': интерфейс изменился на {diff * 100:.1f}%"
                if diff > 0.01
                else f"Действие '{action_name}': визуальных изменений интерфейса не зафиксировано"
            ),
        }
