# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Telemetry Tests - GPU Inventory Dedup
# =============================================================================
# Description:
#   Тестирование дедупликации графических адаптеров (GPU) в хранилище SQLite
#   и в роутере загрузки GPU (/api/v1/panel/gpu-load).
#
# File: test_gpu_dedup.py
# Project: ai-windows-admin
# Package: apps.windows.telemetry.tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-20 20:45:00
# =============================================================================

from __future__ import annotations

import gc
import shutil
import tempfile
from pathlib import Path
import pytest

from apps.windows.telemetry.sqlite import TelemetryStorage
from apps.windows.api.routers.router_gpu_load import _discover_system_gpus


@pytest.fixture
def temp_telemetry_storage():
    """Создает временное хранилище TelemetryStorage в режиме direct для изоляции тестов."""
    tmpdir = tempfile.mkdtemp()
    db_path = Path(tmpdir) / "test_telemetry.db"
    storage = TelemetryStorage(db_path=db_path, buffer_mode="direct")
    yield storage
    try:
        storage.close()
    except Exception:
        pass
    gc.collect()
    shutil.rmtree(tmpdir, ignore_errors=True)


def test_gpu_inventory_deduplication(temp_telemetry_storage: TelemetryStorage):
    """Проверяет, что видеокарты с синонимичными именами и разными индексами не дублируются."""
    storage = temp_telemetry_storage

    # 1. Записываем первую версию NVIDIA (индекс 0) и Intel (индекс 1)
    storage.save_gpu_inventory({
        "gpu_index": 0,
        "name": "GeForce GT 710",
        "vendor": "NVIDIA",
        "vram_total_mb": 2048.0,
    })
    storage.save_gpu_inventory({
        "gpu_index": 1,
        "name": "Intel(R) UHD Graphics 630",
        "vendor": "Intel",
        "vram_total_mb": 1024.0,
    })

    # 2. Записываем вторую версию (в обратном порядке и с добавлением префикса vendor)
    storage.save_gpu_inventory({
        "gpu_index": 0,
        "name": "Intel(R) UHD Graphics 630",
        "vendor": "Intel",
        "vram_total_mb": 1024.0,
    })
    storage.save_gpu_inventory({
        "gpu_index": 1,
        "name": "NVIDIA GeForce GT 710",
        "vendor": "NVIDIA",
        "vram_total_mb": 2048.0,
    })

    # 3. Извлекаем инвентарь GPU
    gpus = storage.get_gpu_inventory()

    # Ожидаем ровно 2 адаптера: NVIDIA (дискретный) и Intel (встроенный)
    assert len(gpus) == 2, f"Ожидалось 2 уникальных GPU, получено: {len(gpus)}"

    names = [g["name"] for g in gpus]
    assert any("GeForce" in n for n in names)
    assert any("Intel" in n for n in names)

    # Проверяем последовательность индексов
    assert gpus[0]["gpu_index"] == 0
    assert gpus[1]["gpu_index"] == 1


def test_discover_system_gpus_deduplication(temp_telemetry_storage: TelemetryStorage):
    """Проверяет дедупликацию в методе _discover_system_gpus роутера GPU Load."""
    storage = temp_telemetry_storage

    storage.save_gpu_inventory({
        "gpu_index": 0,
        "name": "GeForce GT 710",
        "vendor": "NVIDIA",
    })
    storage.save_gpu_inventory({
        "gpu_index": 1,
        "name": "Intel(R) UHD Graphics 630",
        "vendor": "Intel",
    })

    discovered = _discover_system_gpus(storage)
    assert len(discovered) == 2
    assert discovered[0]["index"] == 0
    assert discovered[1]["index"] == 1
    assert discovered[0]["vendor"] == "NVIDIA"
    assert discovered[1]["vendor"] == "Intel"

