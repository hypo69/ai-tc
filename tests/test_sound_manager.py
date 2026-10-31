# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Tests - Sound Manager & API Tests
# =============================================================================
# Description:
#   Модульные тесты для подсистемы управления звуком Windows:
#   проверка SoundManager, Pydantic моделей, считывания громкости
#   системных звуков, устройств вывода и маршрутов API router_sound.
#
# Usage Examples:
#   pytest tests/test_sound_manager.py -v
#
# File: test_sound_manager.py
# Project: ai-windows-admin
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-27 12:05:00
# =============================================================================

import pytest
from starlette.testclient import TestClient

from apps.windows.api.routers.router_sound import router
from apps.windows.sdk.modules.sound.manager import SoundManager
from apps.windows.sdk.modules.sound.models import (
    AudioDeviceDTO,
    SoundSessionDTO,
    SoundSettingsDTO,
)


def test_sound_settings_dto_validation():
    """Проверяет корректность создания и валидации модели SoundSettingsDTO."""
    dto = SoundSettingsDTO(
        master_volume=75,
        master_muted=False,
        system_sounds_volume=100,
        system_sounds_muted=False,
        startup_sound_enabled=True,
        current_scheme=".Default",
        default_output_device="Динамики (Realtek High Definition Audio)",
        output_devices=[
            AudioDeviceDTO(id="{guid-1}", name="Динамики", flow="render", is_default=True)
        ],
        active_sessions=[
            SoundSessionDTO(id="system_sounds", name="Системные звуки Windows", pid=0, volume=100, is_system_sounds=True)
        ],
    )
    assert dto.master_volume == 75
    assert dto.system_sounds_volume == 100
    assert dto.startup_sound_enabled is True
    assert len(dto.output_devices) == 1
    assert dto.active_sessions[0].is_system_sounds is True


def test_sound_manager_get_state():
    """Проверяет получение реального состояния звука через SoundManager."""
    mgr = SoundManager()
    state = mgr.get_state()

    assert isinstance(state, SoundSettingsDTO)
    assert 0 <= state.master_volume <= 100
    assert 0 <= state.system_sounds_volume <= 100
    assert isinstance(state.master_muted, bool)
    assert isinstance(state.system_sounds_muted, bool)
    assert isinstance(state.output_devices, list)
    assert isinstance(state.active_sessions, list)


def test_router_sound_get_state():
    """Проверяет вызов эндпоинта GET /api/v1/sound/state."""
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.get("/api/v1/sound/state")
    assert response.status_code == 200
    data = response.json()

    assert "master_volume" in data
    assert "system_sounds_volume" in data
    assert "master_muted" in data
    assert "active_sessions" in data
    assert "output_devices" in data


def test_router_sound_test_signal():
    """Проверяет воспроизведение проверочного системного сигнала."""
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.post("/api/v1/sound/test-sound", json={"sound": "asterisk"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["sound"] == "asterisk"

