# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Windows API Registry Test Suite
# =============================================================================
# Description:
#   Модульные и интеграционные тесты для каталога Windows API, 6 подсистем
#   Platform Layer, Smart Dispatcher, привязок Python и REST API.
#
# Usage Examples:
#   pytest tests/test_windows_api_registry.py -v
#
# File: test_windows_api_registry.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-12 03:02:00
# =============================================================================

from __future__ import annotations
"""Тесты каталога Windows API, диспетчера рекомендаций и REST API."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.windows.api_registry import (
    ApiFamily,
    ApiRecommendationQuery,
    PlatformSubsystem,
    PrivilegeLevel,
    get_api_registry_service,
)
from apps.windows.api_registry.catalog import (
    get_all_api_entries,
    get_api_by_id,
    get_apis_by_subsystem,
    get_subsystems_summary,
)
from apps.windows.api.routers.router_windows_api_registry import router


@pytest.fixture
def service():
    """Фикстура получения экземпляра сервиса реестра Windows API."""
    return get_api_registry_service()


def test_catalog_entries_completeness():
    """Проверка полноты и целостности записей в каталоге Windows API."""
    entries = get_all_api_entries()
    assert len(entries) >= 15

    # Проверяем обязательные поля каждой записи
    for entry in entries:
        assert entry.id
        assert entry.name
        assert entry.binary_or_namespace
        assert entry.description
        assert len(entry.functions) > 0
        assert isinstance(entry.family, ApiFamily)
        assert isinstance(entry.subsystem, PlatformSubsystem)
        assert isinstance(entry.privileges, PrivilegeLevel)
        assert "python" in entry.code_examples


def test_subsystems_summary():
    """Проверка структуры 6 платформенных подсистем."""
    summary = get_subsystems_summary()
    assert len(summary) == 6

    expected_subs = [
        "hardware_devices",
        "system_diagnostics",
        "network_intel",
        "graphics_vision",
        "security_intel",
        "storage_intel",
    ]
    for sub in expected_subs:
        assert sub in summary
        sub_info = summary[sub]
        assert sub_info["total_apis"] > 0
        assert "title" in sub_info
        assert "description" in sub_info


def test_bindings_detection(service):
    """Проверка детекции привязок Python (ctypes, psutil и др.)."""
    bindings = service.get_bindings_status()
    assert "ctypes" in bindings
    assert bindings["ctypes"]["installed"] is True
    assert "psutil" in bindings
    assert bindings["psutil"]["installed"] is True


def test_smart_dispatcher_recommendation(service):
    """Проверка работы Smart AI Dispatcher по подбору системного API под задачу."""
    # Задача 1: Сетевые адаптеры
    q_net = ApiRecommendationQuery(
        task_description="получить список сетевых адаптеров и IP адресов",
        prefer_zero_dependency=True,
    )
    res_net = service.recommend(q_net)
    assert res_net.recommended_api.subsystem == PlatformSubsystem.NETWORK_INTELLIGENCE
    assert "Iphlpapi" in res_net.recommended_api.binary_or_namespace
    assert "ctypes" in res_net.python_snippet

    # Задача 2: Экран и графика
    q_gfx = ApiRecommendationQuery(
        task_description="аппаратный захват экрана на GPU через DirectX",
        prefer_zero_dependency=False,
    )
    res_gfx = service.recommend(q_gfx)
    assert res_gfx.recommended_api.subsystem == PlatformSubsystem.GRAPHICS_VISION

    # Задача 3: Диски и SMART
    q_disk = ApiRecommendationQuery(
        task_description="считать SMART телеметрию физических накопителей",
        prefer_zero_dependency=True,
    )
    res_disk = service.recommend(q_disk)
    assert res_disk.recommended_api.subsystem == PlatformSubsystem.STORAGE_INTELLIGENCE


def test_execute_native_probe(service):
    """Проверка выполнения безопасного зонда через ctypes."""
    res = service.execute_probe("kernel32_process_mem")
    assert res["status"] in ("ok", "skipped")
    if res["status"] == "ok":
        assert "TickCount64" in res["result"] or "Аптайм" in res["result"]


def test_windows_api_registry_endpoints():
    """Тестирование REST API эндпоинтов роутера."""
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    # 1. Каталог
    res_cat = client.get("/api/v1/windows-api/catalog")
    assert res_cat.status_code == 200
    assert len(res_cat.json()) >= 15

    # 2. Фильтрация по подсистеме
    res_filter = client.get("/api/v1/windows-api/catalog?subsystem=network_intel")
    assert res_filter.status_code == 200
    for item in res_filter.json():
        assert item["subsystem"] == "network_intel"

    # 3. Карточка конкретного API
    res_entry = client.get("/api/v1/windows-api/entry/setupapi_devices")
    assert res_entry.status_code == 200
    assert res_entry.json()["id"] == "setupapi_devices"

    # 4. Подсистемы
    res_subs = client.get("/api/v1/windows-api/subsystems")
    assert res_subs.status_code == 200
    assert len(res_subs.json()) == 6

    # 5. Bindings
    res_bind = client.get("/api/v1/windows-api/bindings-status")
    assert res_bind.status_code == 200
    assert "ctypes" in res_bind.json()

    # 6. Рекомендация API
    res_rec = client.post(
        "/api/v1/windows-api/recommend",
        json={"task_description": "диагностика процессов и памяти", "prefer_zero_dependency": True},
    )
    assert res_rec.status_code == 200
    rec_data = res_rec.json()
    assert rec_data["recommended_api"]["subsystem"] == "system_diagnostics"

    # 7. Зонд
    res_probe = client.post("/api/v1/windows-api/execute-probe", json={"api_id": "kernel32_process_mem"})
    assert res_probe.status_code == 200

    # 8. Настройки
    res_set = client.get("/api/v1/windows-api/settings")
    assert res_set.status_code == 200
