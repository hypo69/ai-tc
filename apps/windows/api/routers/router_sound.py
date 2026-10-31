# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Audio API - Router Sound
# =============================================================================
# Description:
#   API роутер управления звуковой подсистемой Windows:
#   получение состояния громкости, мастер-громкость, громкость системных звуков,
#   аудио-микшер запущенных процессов, звуки запуска и системные утилиты.
#
# Usage Examples:
#   Python API:
#     from apps.windows.api.routers.router_sound import init_router
#     router = init_router()
#
# File: router_sound.py
# Project: ai-windows-admin
# Package: apps.windows.api.routers
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-27 12:05:00
# =============================================================================

from __future__ import annotations
"""API роутер управления звуковой подсистемой и системными звуками Windows."""

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from logger import logger
from apps.windows.sdk.modules.sound.manager import SoundManager
from apps.windows.sdk.modules.sound.models import (
    LaunchToolRequest,
    MuteChangeRequest,
    SessionMuteRequest,
    SessionVolumeRequest,
    SoundSettingsDTO,
    TestSoundRequest,
    VolumeChangeRequest,
)

router = APIRouter(prefix="/api/v1/sound", tags=["Sound & Audio"])
_sound_manager = SoundManager()


@router.get("/state", response_model=SoundSettingsDTO)
async def get_sound_state() -> SoundSettingsDTO:
    """Возвращает текущее состояние звуковой подсистемы Windows.

    Включает мастер-громкость, статус приглушения (Mute), громкость системных звуков,
    активные аудиосессии приложений, списки устройств вывода и ввода, а также звуковую схему.
    """
    try:
        return _sound_manager.get_state()
    except Exception as exc:
        logger.error(f"[RouterSound] Ошибка получения состояния звука: {exc}")
        raise HTTPException(status_code=500, detail=f"Ошибка чтения параметров звука: {exc}")


@router.post("/master-volume")
async def set_master_volume(payload: VolumeChangeRequest) -> Dict[str, Any]:
    """Устанавливает уровень мастер-громкости аудиоустройства по умолчанию (0-100%)."""
    success = _sound_manager.set_master_volume(payload.volume)
    if not success:
        raise HTTPException(status_code=500, detail="Не удалось установить мастер-громкость")
    return {"status": "ok", "volume": payload.volume}


@router.post("/master-mute")
async def set_master_mute(payload: MuteChangeRequest) -> Dict[str, Any]:
    """Включает или выключает общее приглушение звука (Master Mute)."""
    success = _sound_manager.set_master_mute(payload.muted)
    if not success:
        raise HTTPException(status_code=500, detail="Не удалось изменить состояние Master Mute")
    return {"status": "ok", "muted": payload.muted}


@router.post("/system-sounds-volume")
async def set_system_sounds_volume(payload: VolumeChangeRequest) -> Dict[str, Any]:
    """Устанавливает громкость системных звуков Windows (0-100%)."""
    success = _sound_manager.set_system_sounds_volume(payload.volume)
    if not success:
        raise HTTPException(status_code=500, detail="Не удалось настроить громкость системных звуков")
    return {"status": "ok", "volume": payload.volume}


@router.post("/system-sounds-mute")
async def set_system_sounds_mute(payload: MuteChangeRequest) -> Dict[str, Any]:
    """Включает или выключает приглушение системных звуков Windows."""
    success = _sound_manager.set_system_sounds_mute(payload.muted)
    if not success:
        raise HTTPException(status_code=500, detail="Не удалось изменить состояние mute системных звуков")
    return {"status": "ok", "muted": payload.muted}


@router.post("/session-volume")
async def set_session_volume(payload: SessionVolumeRequest) -> Dict[str, Any]:
    """Устанавливает громкость конкретной аудиосессии (процесса или системных звуков)."""
    success = _sound_manager.set_session_volume(payload.target, payload.volume)
    if not success:
        raise HTTPException(status_code=500, detail=f"Не удалось изменить громкость для '{payload.target}'")
    return {"status": "ok", "target": payload.target, "volume": payload.volume}


@router.post("/session-mute")
async def set_session_mute(payload: SessionMuteRequest) -> Dict[str, Any]:
    """Включает или отключает приглушение звука конкретной аудиосессии."""
    success = _sound_manager.set_session_mute(payload.target, payload.muted)
    if not success:
        raise HTTPException(status_code=500, detail=f"Не удалось изменить mute для '{payload.target}'")
    return {"status": "ok", "target": payload.target, "muted": payload.muted}


@router.post("/startup-sound")
async def set_startup_sound(payload: MuteChangeRequest) -> Dict[str, Any]:
    """Включает или отключает звук при запуске Windows (Boot Sound)."""
    success = _sound_manager.set_startup_sound(payload.muted)
    if not success:
        raise HTTPException(status_code=500, detail="Не удалось изменить настройку звука запуска (требуются права администратора)")
    return {"status": "ok", "enabled": payload.muted}


@router.post("/test-sound")
async def play_test_sound(payload: TestSoundRequest) -> Dict[str, Any]:
    """Воспроизводит проверочный системный сигнал Windows."""
    success = _sound_manager.play_test_sound(payload.sound)
    if not success:
        raise HTTPException(status_code=500, detail="Не удалось воспроизвести звуковой сигнал")
    return {"status": "ok", "sound": payload.sound}


@router.post("/launch-tool")
async def launch_sound_tool(payload: LaunchToolRequest) -> Dict[str, Any]:
    """Открывает системное окно настройки звука Windows (settings, sndvol или mmsys)."""
    success = _sound_manager.launch_tool(payload.tool)
    if not success:
        raise HTTPException(status_code=500, detail=f"Не удалось запустить инструмент '{payload.tool}'")
    return {"status": "ok", "tool": payload.tool}


def init_router() -> APIRouter:
    """Фабричная функция инициализации роутера управления звуком."""
    return router

