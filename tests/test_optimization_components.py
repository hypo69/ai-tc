# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Optimization Components Tests
# =============================================================================
# Description:
#   Модульные тесты оптимизационных компонентов (src.utils.common,
#   src.app AppContainer/AppRegistry, WikiLLMClient и AsyncTelemetryBatchClient).
#
# File: test_optimization_components.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-27 23:06:00
# =============================================================================

from __future__ import annotations

import asyncio
import json
import os
import pytest
from pathlib import Path

from src.utils.common import (
    console_log,
    load_json_config,
    save_json_file,
    get_utc_timestamp_iso,
)
from src.app import AppContainer, AppRegistry
from apps.windows.wikillm.client import WikiLLMClient
from src.telemetry.async_client import AsyncTelemetryBatchClient


# -----------------------------------------------------------------------------
# 1. Tests for Common Utils
# -----------------------------------------------------------------------------

def test_common_utils_json_and_timestamp(tmp_path: Path):
    """Проверка функций чтения/записи JSON и ISO временной метки."""
    test_file = tmp_path / "test_cfg.json"
    data = {"app_name": "ai-tc", "version": "2.0"}

    # Сохранение
    assert save_json_file(test_file, data) is True
    assert test_file.is_file()

    # Загрузка
    loaded = load_json_config(test_file)
    assert loaded == data

    # Загрузка несуществующего с default
    missing = load_json_config(tmp_path / "missing.json", default={"fallback": 1})
    assert missing == {"fallback": 1}

    # Временная метка
    ts = get_utc_timestamp_iso()
    assert "Z" in ts or "T" in ts

    # Вывод в консоль
    console_log("Проверка console_log без ошибок")


# -----------------------------------------------------------------------------
# 2. Tests for AppContainer & AppRegistry (DI)
# -----------------------------------------------------------------------------

def test_app_container_di(tmp_path: Path):
    """Проверка работы DI-контейнера и фабрик зависимостей."""
    cfg_file = tmp_path / "config.json"
    save_json_file(cfg_file, {"mode": "test_di"})

    container = AppContainer(config_path=cfg_file)
    assert container.config.get("mode") == "test_di"

    # Регистрация синглтона
    container.register_singleton("db_conn", {"type": "mock_db"})
    assert container.resolve("db_conn") == {"type": "mock_db"}

    # Регистрация фабрики
    counter = {"calls": 0}

    def service_factory():
        counter["calls"] += 1
        return f"instance_{counter['calls']}"

    container.register_factory("my_service", service_factory)
    inst1 = container.resolve("my_service")
    inst2 = container.resolve("my_service")
    assert inst1 == "instance_1"
    assert inst2 == "instance_1"  # закэширован как синглтон

    # Несуществующий сервис
    with pytest.raises(KeyError):
        container.resolve("unknown_service")


def test_app_registry_discovery(tmp_path: Path):
    """Проверка авто-регистрации приложений из каталога /apps."""
    app_dir = tmp_path / "apps" / "my_micro_app"
    app_dir.mkdir(parents=True)
    save_json_file(app_dir / "manifest.json", {"name": "Custom Micro App", "version": "1.0"})

    registry = AppRegistry(apps_root=tmp_path / "apps")
    apps = registry.discover_and_register_apps()
    assert len(apps) == 1
    assert apps[0]["id"] == "my_micro_app"
    assert apps[0]["name"] == "Custom Micro App"


# -----------------------------------------------------------------------------
# 3. Tests for WikiLLMClient (Caching & Batching)
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_wikillm_client_caching_and_batch():
    """Проверка кэширования запросов и пакетного разрешения в WikiLLMClient."""
    client = WikiLLMClient(cache_db_path=":memory:", cache_ttl_seconds=3600)

    # 1. Запрос (вызовет fallback или разрешение)
    res1 = await client.resolve("test_query_code_0x80070005")
    assert res1 is not None
    assert res1.canonical_key is not None

    # 2. Повторный запрос должен браться из кэша
    res2 = await client.resolve("test_query_code_0x80070005")
    assert res2.cached is True
    assert res2.canonical_key == res1.canonical_key

    # 3. Батч-запрос (bulk_query)
    batch_res = await client.bulk_query(["query_a", "query_b"])
    assert len(batch_res) == 2


# -----------------------------------------------------------------------------
# 4. Tests for AsyncTelemetryBatchClient (Delta & Batching)
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_async_telemetry_batch_client_delta():
    """Проверка дельта-сжатия и батч-сброса в AsyncTelemetryBatchClient."""
    sent_batches = []

    def sink(batch):
        sent_batches.append(batch)

    client = AsyncTelemetryBatchClient(
        batch_interval_seconds=60.0,
        max_batch_size=2,
        sink_callback=sink,
    )

    # 1. Первый снимок (все метрики передаются)
    m1 = {"cpu_percent": 12.5, "gpu_percent": 30.0, "unchanged_stat": 100}
    filtered1 = client.filter_delta_metrics(m1)
    assert "cpu_percent" in filtered1
    assert "unchanged_stat" in filtered1

    # 2. Второй снимок с неизменившейся метрикой unchanged_stat
    m2 = {"cpu_percent": 15.0, "gpu_percent": 30.0, "unchanged_stat": 100}
    filtered2 = client.filter_delta_metrics(m2)
    assert "cpu_percent" in filtered2  # ключевая метрика всегда передается
    assert "unchanged_stat" not in filtered2  # неизменившаяся отфильтрована!

    # 3. Батч-отправка по лимиту (max_batch_size = 2)
    await client.enqueue_metrics(m1)
    await client.enqueue_metrics(m2)

    assert len(sent_batches) == 1
    assert len(sent_batches[0]) == 2

