# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Apps Windows SDK WinRT - Models
# =============================================================================
# Description:
#   Модели данных Pydantic для подсистем Windows Runtime (WinRT) и Universal
#   Windows Platform (UWP): питание, сеть, захват графики, медиасессии,
#   устройства и изолированные пакеты AppContainer / Phone Link.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.winrt.models import WinRTSnapshot, WinRTPowerTelemetry
#
# File: models.py
# Project: ai-tc
# Package: apps.windows.sdk.winrt
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-16 05:40:00
# =============================================================================

from __future__ import annotations
"""Модели данных Pydantic для телеметрии и диагностики WinRT / UWP."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class WinRTPowerTelemetry(BaseModel):
    """Телеметрия подсистемы Windows.System.Power."""

    battery_status: str = Field(default="NotPresent", description="Статус аккумулятора (NotPresent, Discharging, Idle, Charging)")
    energy_saver_status: str = Field(default="Disabled", description="Режим экономии энергии (Disabled, Off, On)")
    power_supply_status: str = Field(default="Adequate", description="Состояние источника питания (NotPresent, Inadequate, Adequate)")
    remaining_charge_percent: Optional[int] = Field(default=None, description="Остаток заряда в процентах (0-100)")
    remaining_discharge_time_seconds: Optional[int] = Field(default=None, description="Расчётное время разряда в секундах")
    is_battery_present: bool = Field(default=False, description="Признак наличия батареи")


class WinRTNetworkTelemetry(BaseModel):
    """Телеметрия подсистемы Windows.Networking.Connectivity."""

    profile_name: Optional[str] = Field(default=None, description="Имя активного сетевого профиля")
    connectivity_level: str = Field(default="None", description="Уровень подключения (None, LocalAccess, ConstrainedInternetAccess, InternetAccess)")
    domain_connectivity: str = Field(default="None", description="Уровень корпоративного домена (None, Unauthenticated, Authenticated)")
    is_wlan: bool = Field(default=False, description="Подключение через Wi-Fi (WLAN)")
    is_wwan: bool = Field(default=False, description="Подключение через сотовую связь (WWAN)")
    signal_bars: Optional[int] = Field(default=None, description="Уровень сигнала (1-5 делений)")
    iana_interface_type: int = Field(default=0, description="Тип интерфейса IANA (например, 6 - Ethernet, 71 - WiFi)")
    is_metered: bool = Field(default=False, description="Лимитное сетевое подключение")


class WinRTMediaSessionTelemetry(BaseModel):
    """Телеметрия подсистем Windows.Media.Control и Windows.Media.Capture."""

    has_active_session: bool = Field(default=False, description="Наличие активной медиасессии в ОС")
    source_app_user_model_id: Optional[str] = Field(default=None, description="AUMID приложения-источника звука")
    playback_status: Optional[str] = Field(default=None, description="Состояние воспроизведения (Closed, Opened, Changing, Stopped, Playing, Paused)")
    title: Optional[str] = Field(default=None, description="Название текущего трека/медиа")
    artist: Optional[str] = Field(default=None, description="Исполнитель текущего трека")
    album_artist: Optional[str] = Field(default=None, description="Исполнитель альбома")
    album_title: Optional[str] = Field(default=None, description="Название альбома")
    can_pause: bool = Field(default=False, description="Поддержка команды паузы")
    can_play: bool = Field(default=False, description="Поддержка команды воспроизведения")
    media_capture_supported: bool = Field(default=True, description="Поддержка API Windows.Media.Capture")


class WinRTGraphicsTelemetry(BaseModel):
    """Телеметрия подсистем Windows.Graphics.Capture и Windows.Graphics.Imaging."""

    capture_supported: bool = Field(default=True, description="Поддержка современного API захвата Windows.Graphics.Capture")
    supported_imaging_decoders: List[str] = Field(default_factory=list, description="Список поддерживаемых декодеров WIC/WinRT")
    supported_imaging_encoders: List[str] = Field(default_factory=list, description="Список поддерживаемых энкодеров WIC/WinRT")
    gpu_d3d_device_accessible: bool = Field(default=True, description="Доступность прямого Direct3D/DXGI контекста")


class WinRTDeviceTelemetry(BaseModel):
    """Телеметрия подсистемы Windows.Devices.Enumeration."""

    total_devices_count: int = Field(default=0, description="Общее число обнаруженных WinRT устройств")
    cameras_count: int = Field(default=0, description="Количество подключенных камер (VideoDevice)")
    audio_render_count: int = Field(default=0, description="Количество устройств вывода звука")
    audio_capture_count: int = Field(default=0, description="Количество микрофонов и устройств захвата звука")
    bluetooth_devices_count: int = Field(default=0, description="Количество сопряжённых/активных Bluetooth устройств")
    sensors_count: int = Field(default=0, description="Количество аппаратных WinRT сенсоров")
    sample_devices: List[Dict[str, Any]] = Field(default_factory=list, description="Примеры обнаруженных устройств")


class WinRTPackageTelemetry(BaseModel):
    """Телеметрия UWP / MSIX и подсистемы Windows.ApplicationModel."""

    total_uwp_packages: int = Field(default=0, description="Количество зарегистрированных UWP/Appx пакетов пользователя")
    phone_link_installed: bool = Field(default=False, description="Установлено ли системное приложение Phone Link (Связь с телефоном)")
    phone_link_version: Optional[str] = Field(default=None, description="Версия пакета Phone Link")
    phone_link_package_full_name: Optional[str] = Field(default=None, description="Полное имя пакета Microsoft.YourPhone")
    phone_link_appcontainer: bool = Field(default=True, description="Изолированное выполнение в AppContainer")
    phone_link_capabilities: List[str] = Field(default_factory=list, description="Декларированные разрешения Package.appxmanifest")
    sample_packages: List[Dict[str, Any]] = Field(default_factory=list, description="Выборка установленных системных UWP пакетов")


class WinRTProviderStatus(BaseModel):
    """Статус готовности и метаданные адаптера WinRTProvider."""

    is_available: bool = Field(default=False, description="Доступность WinRT в текущей ОС")
    os_version: str = Field(default="", description="Версия Windows")
    runtime_engine: str = Field(default="PowerShell/WinRT Bridge", description="Используемый движок вызова WinRT API")
    supported_namespaces: List[str] = Field(default_factory=list, description="Доступные пространства имён WinRT")
    last_error: Optional[str] = Field(default=None, description="Последняя зафиксированная ошибка")


class WinRTSnapshot(BaseModel):
    """Комплексный моментальный снимок WinRT телеметрии для шины AI-TC."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Метка времени снимка (UTC)")
    status: WinRTProviderStatus = Field(default_factory=WinRTProviderStatus, description="Статус провайдера")
    power: WinRTPowerTelemetry = Field(default_factory=WinRTPowerTelemetry, description="Метрики питания WinRT")
    network: WinRTNetworkTelemetry = Field(default_factory=WinRTNetworkTelemetry, description="Метрики сети WinRT")
    media: WinRTMediaSessionTelemetry = Field(default_factory=WinRTMediaSessionTelemetry, description="Метрики медиа WinRT")
    graphics: WinRTGraphicsTelemetry = Field(default_factory=WinRTGraphicsTelemetry, description="Метрики графики и захвата")
    devices: WinRTDeviceTelemetry = Field(default_factory=WinRTDeviceTelemetry, description="Метрики устройств WinRT")
    appmodel: WinRTPackageTelemetry = Field(default_factory=WinRTPackageTelemetry, description="Метрики UWP приложений и Phone Link")
