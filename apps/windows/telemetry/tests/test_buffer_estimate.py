# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows Telemetry Tests - Buffer Estimate
# =============================================================================
# Description:
#   Тесты оптимизации TelemetryBuffer: быстрая оценка размера записи без
#   сериализации и отсутствие обращений к файлу буфера в режиме 'memory'.
#
# File: test_buffer_estimate.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-30 11:50:00
# =============================================================================

import json
import threading
from pathlib import Path
from types import SimpleNamespace

from apps.windows.telemetry.sqlite.buffer import TelemetryBuffer


class _FakeWriter:
    """Заглушка писателя: запоминает сохранённые записи."""

    def __init__(self) -> None:
        self.saved = []

    def batch_insert_records(self, records):
        self.saved.extend(records)
        return len(records)


def _make_buffer(tmp_path: Path, **kwargs) -> tuple:
    cm = SimpleNamespace(db_path=tmp_path / 't.db', read_only=False, lock=threading.RLock())
    writer = _FakeWriter()
    buf = TelemetryBuffer(cm, writer, auto_flush=False, **kwargs)
    return buf, writer


def test_estimate_size_does_not_serialize(tmp_path, monkeypatch):
    """Оценка размера не должна вызывать json.dumps."""
    buf, _ = _make_buffer(tmp_path)

    calls = []
    monkeypatch.setattr(json, 'dumps', lambda *a, **k: calls.append(1) or '{}')
    size = buf._estimate_size({'a': [1, 2, {'b': 'text'}], 'c': 1.5})
    assert size > 0
    assert not calls


def test_estimate_size_grows_with_payload(tmp_path):
    """Большая запись оценивается больше маленькой."""
    buf, _ = _make_buffer(tmp_path)
    small = buf._estimate_size({'a': 1})
    big = buf._estimate_size({'a': ['x' * 100] * 50})
    assert big > small


def test_memory_mode_flush_skips_file_stat(tmp_path, monkeypatch):
    """В режиме memory flush не обращается к файлу буфера, если в нём нет записей."""
    buf, writer = _make_buffer(tmp_path, buffer_size=10)
    calls = []
    real_exists = Path.exists
    monkeypatch.setattr(Path, 'exists', lambda self: calls.append(self) or real_exists(self))

    buf.enqueue({'type': 'event', 'x': 1})
    assert buf.flush() == 1
    assert len(writer.saved) == 1
    assert buf.buffer_file_path not in calls
