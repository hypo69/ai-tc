# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Telemetry - Test Directory Watcher Configuration
# =============================================================================
# Description:
#   Тесты для проверки интеграции DirectoryWatchEngine с конфигурацией телеметрии,
#   учета watch_directories и корректной работы отслеживания директорий.
#
# File: test_directory_watcher_config.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-13 14:11:00
# =============================================================================

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import pytest

from apps.windows.telemetry.directory_watcher import DirectoryWatchEngine
from apps.windows.telemetry.telemetry_config import TelemetryConfigManager


def test_telemetry_config_watch_directories() -> None:
    """Проверяет методы чтения и сохранения watch_directories в TelemetryConfigManager."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump({
            "collect_file_events": True,
            "watch_directories": [
                "C:\\Users",
                "C:\\Users\\onela\\AppData\\Local\\AI-TC\\data"
            ]
        }, f)
        cfg_path = Path(f.name)

    try:
        cfg_mgr = TelemetryConfigManager(config_path=cfg_path)
        assert cfg_mgr.is_file_events_enabled() is True
        dirs = cfg_mgr.get_watch_directories()
        assert "C:\\Users" in dirs
        assert "C:\\Users\\onela\\AppData\\Local\\AI-TC\\data" in dirs

        # Проверяем сохранение нового списка директорий
        new_dirs = ["C:\\Users", "C:\\Projects"]
        cfg_mgr.set_watch_directories(new_dirs)
        assert cfg_mgr.get_watch_directories() == new_dirs

        # Перечитываем файл с диска
        with open(cfg_path, "r", encoding="utf-8") as rf:
            saved_json = json.load(rf)
            assert saved_json.get("watch_directories") == new_dirs
    finally:
        if cfg_path.exists():
            cfg_path.unlink()


def test_directory_watcher_engine_loads_config() -> None:
    """Проверяет, что DirectoryWatchEngine считывает директории из конфигурации."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        cfg_file = tmp_path / "config.json"
        target_dir = tmp_path / "watched_folder"
        target_dir.mkdir(parents=True, exist_ok=True)

        cfg_file.write_text(
            json.dumps({
                "collect_file_events": True,
                "watch_directories": [str(target_dir)]
            }),
            encoding="utf-8"
        )

        cfg_mgr = TelemetryConfigManager(config_path=cfg_file)
        engine = DirectoryWatchEngine(config_path=cfg_file, config_manager=cfg_mgr)

        tracked = engine.get_tracked_directories()
        norm_target = os.path.normpath(str(target_dir))
        assert norm_target in tracked


def test_directory_watcher_add_and_remove() -> None:
    """Проверяет добавление и удаление отслеживаемых директорий через DirectoryWatchEngine."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        cfg_file = tmp_path / "config.json"
        dir_a = tmp_path / "folder_a"
        dir_b = tmp_path / "folder_b"
        dir_a.mkdir(parents=True, exist_ok=True)
        dir_b.mkdir(parents=True, exist_ok=True)

        cfg_file.write_text(
            json.dumps({
                "collect_file_events": True,
                "watch_directories": [str(dir_a)]
            }),
            encoding="utf-8"
        )

        cfg_mgr = TelemetryConfigManager(config_path=cfg_file)
        engine = DirectoryWatchEngine(config_path=cfg_file, config_manager=cfg_mgr)

        norm_a = os.path.normpath(str(dir_a))
        norm_b = os.path.normpath(str(dir_b))

        assert norm_a in engine.get_tracked_directories()
        assert norm_b not in engine.get_tracked_directories()

        # Добавляем folder_b
        added = engine.add_directory(str(dir_b))
        assert added is True
        assert norm_b in engine.get_tracked_directories()

        # Удаляем folder_a
        removed = engine.remove_directory(str(dir_a))
        assert removed is True
        assert norm_a not in engine.get_tracked_directories()
        assert norm_b in engine.get_tracked_directories()


def test_directory_watcher_process_notifications_unicode_and_bytes() -> None:
    """Проверяет корректность разбора уведомлений с символами вне диапазона ASCII и байтами > 127."""
    import ctypes
    engine = DirectoryWatchEngine()
    captured_events = []
    engine.subscribe(lambda evts: captured_events.extend(evts))

    try:
        # Подготавливаем тестовую структуру FILE_NOTIFY_INFORMATION с UTF-16LE строкой
        test_filename = "Отчет_пользователя.docx"
        filename_bytes = test_filename.encode("utf-16le")
        fn_len = len(filename_bytes)

        # entry: next_offset (4), action (4), file_name_len (4), filename (fn_len)
        entry = (
            (0).to_bytes(4, "little")
            + (3).to_bytes(4, "little")  # FILE_ACTION_MODIFIED
            + fn_len.to_bytes(4, "little")
            + filename_bytes
        )

        # 1. Проверяем разбор с объектом bytes
        engine._process_notifications(entry, len(entry), "C:\\Users")
        assert len(captured_events) == 1
        assert "Отчет_пользователя.docx" in captured_events[0]["file_path"]

        # 2. Проверяем разбор с create_string_buffer
        captured_events.clear()
        buf = ctypes.create_string_buffer(len(entry))
        buf.raw = entry
        engine._process_notifications(buf.raw, len(entry), "C:\\Users")
        assert len(captured_events) == 1
        assert captured_events[0]["operation_type"] == "MODIFY"

        # 3. Проверяем совместимость со знаковым c_byte массивом со значениями >= 128 (отрицательные числа)
        captured_events.clear()
        c_byte_arr = (ctypes.c_byte * len(entry))(*[b if b < 128 else b - 256 for b in entry])
        # Раньше это вызывало ValueError: bytes must be in range(0, 256)
        engine._process_notifications(c_byte_arr, len(entry), "C:\\Users")
        assert len(captured_events) == 1
        assert "Отчет_пользователя.docx" in captured_events[0]["file_path"]
    finally:
        engine.unsubscribe(lambda evts: None)

