# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Audio Module - Sound Models
# =============================================================================
# Description:
#   Модели данных Pydantic для управления звуковой подсистемой Windows:
#   мастер-громкость, громкость системных звуков, звуковые сессии процессов,
#   устройства вывода и ввода, звуковые схемы.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.modules.sound.models import SoundSettingsDTO
#
# File: models.py
# Project: ai-windows-admin
# Package: apps.windows.sdk.modules.sound
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-27 12:05:00
# =============================================================================

from __future__ import annotations
"""Модели данных Pydantic для звуковой подсистемы Windows."""

from typing import List, Optional
from pydantic import BaseModel, Field


class AudioDeviceDTO(BaseModel):
    """Модель аудиоустройства Windows (конечная точка MMDevice)."""
    id: str = Field(..., description="Уникальный идентификатор конечной точки MMDevice")
    name: str = Field(..., description="Отображаемое имя аудиоустройства")
    flow: str = Field("render", description="Направление потока: render (вывод) или capture (ввод)")
    is_default: bool = Field(False, description="Флаг устройства по умолчанию для мультимедиа")
    state: str = Field("active", description="Состояние устройства (active, disabled, unplugged)")


class SoundSessionDTO(BaseModel):
    """Модель активной аудиосессии процесса или системных звуков."""
    id: str = Field(..., description="Идентификатор сессии (PID или system_sounds)")
    name: str = Field(..., description="Имя процесса или сервиса")
    pid: int = Field(0, description="Идентификатор процесса (0 для системных звуков)")
    volume: int = Field(100, ge=0, le=100, description="Уровень громкости сессии в процентах (0-100)")
    is_muted: bool = Field(False, description="Флаг отключения звука сессии (Mute)")
    is_system_sounds: bool = Field(False, description="Признак сессии системных звуков Windows")


class SoundSchemeDTO(BaseModel):
    """Модель звуковой схемы Windows."""
    id: str = Field(..., description="Идентификатор схемы реестра (.Default, .None и т.д.)")
    name: str = Field(..., description="Пользовательское наименование схемы")
    is_current: bool = Field(False, description="Флаг текущей активной схемы")


class SoundSettingsDTO(BaseModel):
    """Сводная модель текущего состояния аудиоподсистемы Windows."""
    master_volume: int = Field(50, ge=0, le=100, description="Мастер-громкость устройства по умолчанию (0-100)")
    master_muted: bool = Field(False, description="Флаг общего отключения звука (Master Mute)")
    system_sounds_volume: int = Field(100, ge=0, le=100, description="Громкость системных звуков (0-100)")
    system_sounds_muted: bool = Field(False, description="Флаг отключения системных звуков")
    startup_sound_enabled: bool = Field(True, description="Флаг воспроизведения звука при запуске Windows")
    current_scheme: str = Field(".Default", description="Имя текущей активной звуковой схемы")
    default_output_device: Optional[str] = Field(None, description="Имя устройства вывода звука по умолчанию")
    default_input_device: Optional[str] = Field(None, description="Имя устройства ввода звука по умолчанию")
    output_devices: List[AudioDeviceDTO] = Field(default_factory=list, description="Список устройств вывода")
    input_devices: List[AudioDeviceDTO] = Field(default_factory=list, description="Список устройств ввода")
    active_sessions: List[SoundSessionDTO] = Field(default_factory=list, description="Список активных аудиосессий микшера")
    available_schemes: List[SoundSchemeDTO] = Field(default_factory=list, description="Доступные звуковые схемы")


class VolumeChangeRequest(BaseModel):
    """Запрос изменения уровня громкости."""
    volume: int = Field(..., ge=0, le=100, description="Новый уровень громкости от 0 до 100%")


class MuteChangeRequest(BaseModel):
    """Запрос изменения состояния Mute."""
    muted: bool = Field(..., description="Флаг отключения звука")


class SessionVolumeRequest(BaseModel):
    """Запрос регулировки конкретной аудиосессии."""
    target: str = Field(..., description="PID процесса или 'system_sounds'")
    volume: int = Field(..., ge=0, le=100, description="Новый уровень громкости (0-100)")


class SessionMuteRequest(BaseModel):
    """Запрос отключения звука конкретной аудиосессии."""
    target: str = Field(..., description="PID процесса или 'system_sounds'")
    muted: bool = Field(..., description="Флаг отключения звука")


class TestSoundRequest(BaseModel):
    """Запрос проигрывания тестового звукового сигнала."""
    sound: str = Field("asterisk", description="Тип сигнала: asterisk, exclamation, beep, question")


class LaunchToolRequest(BaseModel):
    """Запрос открытия системного окна настройки звука."""
    tool: str = Field("settings", description="Инструмент: settings, sndvol, mmsys")

