# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Software Scanner - Tasks Probe
# =============================================================================
# Description:
#   Зонд планировщика заданий Windows Task Scheduler: опрос зарегистрированных
#   задач, извлечение путей запуска исполняемых файлов и поиск сирот.
#
# File: tasks_probe.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.software_scanner.probes
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-10 19:20:00
# =============================================================================

from __future__ import annotations
"""Зонд сканирования задач планировщика Windows."""

import csv
import io
import os
import subprocess
import sys
from typing import List
from logger import logger
from apps.windows.sdk.software_scanner.models import (
    ConfidenceLevel,
    EvidenceItem,
    EvidenceType,
)


class TasksProbe:
    """Зонд аудита задач планировщика заданий Windows Task Scheduler."""

    def scan_tasks(self) -> List[EvidenceItem]:
        """Сбор задач планировщика через schtasks CLI."""
        items: List[EvidenceItem] = []
        if not sys.platform.startswith("win"):
            return items

        try:
            cmd = ["schtasks.exe", "/query", "/fo", "CSV", "/v"]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="mbcs",
                errors="ignore",
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0,
            )
            if result.returncode != 0 or not result.stdout:
                return items

            reader = csv.DictReader(io.StringIO(result.stdout))
            for row in reader:
                task_name = row.get("TaskName") or row.get("Имя задачи") or ""
                task_action = row.get("Task To Run") or row.get("Выполняемое действие") or ""

                if not task_name or not task_action or task_action.lower() in ("n/a", "не применимо", ""):
                    continue

                # Игнорируем стандартные системные задачи Microsoft\Windows
                if task_name.startswith(r"\Microsoft\Windows"):
                    continue

                clean_exec = task_action.strip(' "\'')
                if task_action.startswith('"'):
                    end_idx = task_action.find('"', 1)
                    if end_idx != -1:
                        clean_exec = task_action[1:end_idx]
                else:
                    # Поиск границы расширения исполняемого файла
                    import re
                    m = re.search(r'^(.*?\.(?:exe|dll|bat|cmd|vbs|ps1|scr))(?:\s+.*)?$', task_action, re.IGNORECASE)
                    if m:
                        clean_exec = m.group(1).strip(' "\'')
                    else:
                        clean_exec = clean_exec.split(" ")[0]

                expanded_exec = os.path.expandvars(clean_exec)
                binary_exists = os.path.isfile(expanded_exec) if expanded_exec else False

                items.append(EvidenceItem(
                    evidence_type=EvidenceType.TASK,
                    source="TaskScheduler",
                    path=expanded_exec,
                    product_name=task_name.lstrip("\\"),
                    confidence=ConfidenceLevel.MEDIUM,
                    raw_details={
                        "task_name": task_name,
                        "raw_action": task_action,
                        "binary_exists": binary_exists,
                    }
                ))

        except subprocess.TimeoutExpired:
            logger.debug("[TasksProbe] Таймаут выполнения schtasks")
        except Exception as ex:
            logger.debug(f"[TasksProbe] Ошибка сбора задач: {ex}")

        return items


__all__ = ["TasksProbe"]

