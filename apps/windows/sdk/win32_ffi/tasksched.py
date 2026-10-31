# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry Win32_Ffi - Tasksched
# =============================================================================
# Description:
#   Интерфейс к Task Scheduler 2.0 COM API Windows (реэкспорт из native).
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.win32_ffi.tasksched import TaskSchedulerAPI
#
#     service = TaskSchedulerAPI()
#
# File: tasksched.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.win32_ffi
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-14 23:28:00
# =============================================================================

from __future__ import annotations
"""Интерфейс к Task Scheduler 2.0 COM API Windows (реэкспорт из native)."""

from apps.windows.sdk.native.tasksched import (
    TASK_ACTION_COM_HANDLER,
    TASK_ACTION_EXEC,
    TASK_ACTION_SEND_EMAIL,
    TASK_ACTION_SHOW_MESSAGE,
    TASK_STATE_DISABLED,
    TASK_STATE_MAP,
    TASK_STATE_QUEUED,
    TASK_STATE_READY,
    TASK_STATE_RUNNING,
    TASK_STATE_UNKNOWN,
    TASK_TRIGGER_TYPE_MAP,
    TaskSchedulerAPI,
    TaskSchedulerFFI,
    _format_com_date,
)

__all__ = [
    "TaskSchedulerAPI",
    "TaskSchedulerFFI",
    "TASK_STATE_UNKNOWN",
    "TASK_STATE_DISABLED",
    "TASK_STATE_QUEUED",
    "TASK_STATE_READY",
    "TASK_STATE_RUNNING",
    "TASK_STATE_MAP",
    "TASK_TRIGGER_TYPE_MAP",
    "TASK_ACTION_EXEC",
    "TASK_ACTION_COM_HANDLER",
    "TASK_ACTION_SEND_EMAIL",
    "TASK_ACTION_SHOW_MESSAGE",
    "_format_com_date",
]
