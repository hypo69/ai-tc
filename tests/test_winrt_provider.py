# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Tests - WinRT & UWP Provider Tests
# =============================================================================
# Description:
#   Модульные тесты (TDD) для адаптера WinRTProvider, подсистем Windows Runtime,
#   моделей телеметрии, коллектора WinRTCollector и интеграции в WindowsSDK.
#
# Usage Examples:
#   pytest tests/test_winrt_provider.py -v
#
# File: test_winrt_provider.py
# Project: ai-tc
# Package: tests
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-16 05:40:00
# =============================================================================

from __future__ import annotations
"""Модульные тесты для подсистемы Windows Runtime (WinRT) и Universal Windows Platform (UWP)."""

import pytest
from unittest.mock import MagicMock

from apps.windows.sdk import WindowsSDK, windows_sdk
from apps.windows.sdk.winrt import (
    WinRTProvider,
    WinRTSubsystem,
    WinRTExecutor,
    WinRTSnapshot,
    WinRTPowerTelemetry,
    WinRTNetworkTelemetry,
    WinRTMediaSessionTelemetry,
    WinRTGraphicsTelemetry,
    WinRTDeviceTelemetry,
    WinRTPackageTelemetry,
    WinRTProviderStatus,
)
from apps.windows.telemetry.winrt_collector import WinRTCollector


class TestWinRTModels:
    """Тестирование Pydantic моделей данных WinRT."""

    def test_power_telemetry_defaults(self) -> None:
        """Проверка значений по умолчанию для телеметрии питания."""
        p = WinRTPowerTelemetry()
        assert p.battery_status == "NotPresent"
        assert p.energy_saver_status == "Disabled"
        assert p.power_supply_status == "Adequate"
        assert p.remaining_charge_percent is None
        assert not p.is_battery_present

    def test_network_telemetry_defaults(self) -> None:
        """Проверка значений по умолчанию для телеметрии сети."""
        net = WinRTNetworkTelemetry()
        assert net.connectivity_level == "None"
        assert net.domain_connectivity == "None"
        assert not net.is_wlan
        assert not net.is_wwan
        assert net.iana_interface_type == 0

    def test_media_telemetry_defaults(self) -> None:
        """Проверка значений по умолчанию для медиасессий."""
        media = WinRTMediaSessionTelemetry()
        assert not media.has_active_session
        assert media.source_app_user_model_id is None
        assert media.media_capture_supported is True

    def test_appmodel_telemetry_defaults(self) -> None:
        """Проверка значений по умолчанию для UWP / Phone Link."""
        pkg = WinRTPackageTelemetry()
        assert pkg.total_uwp_packages == 0
        assert not pkg.phone_link_installed
        assert pkg.phone_link_appcontainer is True
        assert pkg.phone_link_capabilities == []


class TestWinRTSubsystemsWithMockExecutor:
    """Тестирование парсинга ответов подсистем через имитационный WinRTExecutor."""

    def test_power_subsystem_parsing(self) -> None:
        """Проверка корректности маппинга JSON питания."""
        mock_exec = MagicMock(spec=WinRTExecutor)
        mock_exec.execute_script_sync.return_value = {
            "BatteryStatus": "Discharging",
            "EnergySaverStatus": "Off",
            "PowerSupplyStatus": "NotPresent",
            "RemainingChargePercent": 85,
        }
        provider = WinRTProvider(executor=mock_exec)
        power_info = provider.power.get_power_telemetry_sync()

        assert power_info.battery_status == "Discharging"
        assert power_info.energy_saver_status == "Off"
        assert power_info.remaining_charge_percent == 85
        assert power_info.is_battery_present is True

    def test_network_subsystem_parsing(self) -> None:
        """Проверка корректности маппинга данных сетевого профиля."""
        mock_exec = MagicMock(spec=WinRTExecutor)
        mock_exec.execute_script_sync.return_value = {
            "ProfileName": "Work_WLAN",
            "ConnectivityLevel": "InternetAccess",
            "DomainConnectivity": "Authenticated",
            "IsWlan": True,
            "IsWwan": False,
            "SignalBars": 5,
            "InterfaceType": 71,
        }
        provider = WinRTProvider(executor=mock_exec)
        net_info = provider.network.get_network_telemetry_sync()

        assert net_info.profile_name == "Work_WLAN"
        assert net_info.connectivity_level == "InternetAccess"
        assert net_info.domain_connectivity == "Authenticated"
        assert net_info.is_wlan is True
        assert net_info.signal_bars == 5
        assert net_info.iana_interface_type == 71

    def test_media_subsystem_parsing(self) -> None:
        """Проверка корректности маппинга активной медиасессии."""
        mock_exec = MagicMock(spec=WinRTExecutor)
        mock_exec.execute_script_sync.return_value = {
            "HasActiveSession": True,
            "AppId": "Spotify.Music",
            "PlaybackStatus": "Playing",
            "CanPause": True,
            "CanPlay": False,
        }
        provider = WinRTProvider(executor=mock_exec)
        media_info = provider.media.get_media_telemetry_sync()

        assert media_info.has_active_session is True
        assert media_info.source_app_user_model_id == "Spotify.Music"
        assert media_info.playback_status == "Playing"
        assert media_info.can_pause is True
        assert media_info.can_play is False

    def test_graphics_subsystem_parsing(self) -> None:
        """Проверка корректности маппинга графических возможностей и декодеров."""
        mock_exec = MagicMock(spec=WinRTExecutor)
        mock_exec.execute_script_sync.return_value = {
            "CaptureSupported": True,
            "Decoders": ["JPEG Decoder", "PNG Decoder", "HEIF Decoder"],
            "Encoders": ["JPEG Encoder", "PNG Encoder"],
        }
        provider = WinRTProvider(executor=mock_exec)
        gfx_info = provider.graphics.get_graphics_telemetry_sync()

        assert gfx_info.capture_supported is True
        assert len(gfx_info.supported_imaging_decoders) == 3
        assert "HEIF Decoder" in gfx_info.supported_imaging_decoders

    def test_devices_subsystem_parsing(self) -> None:
        """Проверка подсчета устройств по классам WinRT."""
        mock_exec = MagicMock(spec=WinRTExecutor)
        mock_exec.execute_script_sync.return_value = {
            "AudioCapture": 2,
            "AudioRender": 3,
            "VideoCapture": 1,
        }
        provider = WinRTProvider(executor=mock_exec)
        dev_info = provider.devices.get_devices_telemetry_sync()

        assert dev_info.cameras_count == 1
        assert dev_info.audio_render_count == 3
        assert dev_info.audio_capture_count == 2
        assert dev_info.total_devices_count == 6

    def test_appmodel_subsystem_parsing(self) -> None:
        """Проверка маппинга UWP пакетов и манифеста Phone Link."""
        mock_exec = MagicMock(spec=WinRTExecutor)
        mock_exec.execute_script_sync.return_value = {
            "Total": 142,
            "PhoneInstalled": True,
            "PhoneVersion": "1.26101.115.0",
            "PhoneFullName": "Microsoft.YourPhone_1.26101.115.0_x64__8wekyb3d8bbwe",
            "Capabilities": ["phoneCall", "contacts", "bluetooth"],
            "Samples": [{"Name": "Microsoft.YourPhone", "Version": "1.26101.115.0"}],
        }
        provider = WinRTProvider(executor=mock_exec)
        app_info = provider.appmodel.get_appmodel_telemetry_sync()

        assert app_info.total_uwp_packages == 142
        assert app_info.phone_link_installed is True
        assert app_info.phone_link_version == "1.26101.115.0"
        assert "phoneCall" in app_info.phone_link_capabilities


class TestWinRTProviderAndCollector:
    """Тестирование агрегированного снимка и интеграции с Telemetry Bus."""

    def test_provider_status_and_namespaces(self) -> None:
        """Проверка статуса провайдера и поддерживаемых пространств имён."""
        provider = WinRTProvider()
        status = provider.get_status()
        assert isinstance(status, WinRTProviderStatus)
        assert len(status.supported_namespaces) >= 6
        assert "Windows.System.Power" in status.supported_namespaces
        assert "Windows.ApplicationModel" in status.supported_namespaces

    def test_probe_snapshot_sync(self) -> None:
        """Проверка синхронного формирования комплексного снимка."""
        provider = WinRTProvider()
        snapshot = provider.probe_snapshot_sync()
        assert isinstance(snapshot, WinRTSnapshot)
        assert snapshot.timestamp is not None
        assert isinstance(snapshot.power, WinRTPowerTelemetry)
        assert isinstance(snapshot.network, WinRTNetworkTelemetry)
        assert isinstance(snapshot.media, WinRTMediaSessionTelemetry)
        assert isinstance(snapshot.graphics, WinRTGraphicsTelemetry)
        assert isinstance(snapshot.devices, WinRTDeviceTelemetry)
        assert isinstance(snapshot.appmodel, WinRTPackageTelemetry)

    @pytest.mark.asyncio
    async def test_probe_snapshot_async(self) -> None:
        """Проверка параллельного асинхронного формирования снимка."""
        provider = WinRTProvider()
        snapshot = await provider.probe_snapshot_async()
        assert isinstance(snapshot, WinRTSnapshot)
        assert snapshot.status.is_available is True

    def test_winrt_collector_telemetry_payload(self) -> None:
        """Проверка сериализации снимка в формат шины Telemetry Bus."""
        collector = WinRTCollector()
        payload = collector.to_telemetry_payload()
        assert payload["source"] == "WinRTProvider"
        assert payload["tier"] == "Tier_Modern_WinRT"
        assert "timestamp" in payload
        assert "power" in payload
        assert "network" in payload
        assert "media" in payload
        assert "graphics" in payload
        assert "devices" in payload
        assert "appmodel" in payload


class TestWindowsSDKIntegration:
    """Тестирование включения WinRTSubsystem в состав единого WindowsSDK."""

    def test_sdk_has_winrt(self) -> None:
        """Проверка доступности слоя 6 (winrt) в экземпляре WindowsSDK."""
        sdk = WindowsSDK()
        assert hasattr(sdk, "winrt")
        assert isinstance(sdk.winrt, WinRTSubsystem)
        status = sdk.winrt.get_status()
        assert status.is_available is True

    def test_lazy_singleton_has_winrt(self) -> None:
        """Проверка доступности winrt через ленивый синглтон windows_sdk."""
        assert hasattr(windows_sdk, "winrt")
        power = windows_sdk.winrt.get_power()
        assert isinstance(power, WinRTPowerTelemetry)
