# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: ai-tc Apps Windows SDK WinRT Subsystems - AppModel & UWP
# =============================================================================
# Description:
#   Адаптер к подсистеме Windows.ApplicationModel и модели разработки UWP.
#   Инспектирует установленные пакеты MSIX/APPX, изоляцию в AppContainer,
#   декларативные манифесты Package.appxmanifest и статус системного
#   приложения «Связь с телефоном» (Phone Link / Microsoft.YourPhone).
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk.winrt.subsystems.appmodel import WinRTAppModelSubsystem
#
#     subsystem = WinRTAppModelSubsystem()
#     app_info = await subsystem.get_appmodel_telemetry_async()
#
# File: appmodel.py
# Project: ai-tc
# Package: apps.windows.sdk.winrt.subsystems
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-11-16 05:40:00
# =============================================================================

from __future__ import annotations
"""Адаптер к пространству имён Windows.ApplicationModel и UWP Package Manifests."""

import asyncio
from typing import Optional
from logger import logger
from apps.windows.sdk.winrt.executor import WinRTExecutor
from apps.windows.sdk.winrt.models import WinRTPackageTelemetry


class WinRTAppModelSubsystem:
    """Подсистема анализа приложений UWP/MSIX и жизненного цикла Windows.ApplicationModel."""

    def __init__(self, executor: Optional[WinRTExecutor] = None) -> None:
        """Инициализация подсистемы AppModel / UWP.

        Args:
            executor: Экземпляр исполнителя WinRT (DI).
        """
        self.executor = executor or WinRTExecutor()

    def get_appmodel_telemetry_sync(self) -> WinRTPackageTelemetry:
        """Синхронный сбор телеметрии UWP приложений и манифеста Phone Link."""
        script = (
            "$pkgs = @(Get-AppxPackage); "
            "$phone = $pkgs | Where-Object { $_.Name -like '*YourPhone*' } | Select-Object -First 1; "
            "$caps = @(); "
            "if ($phone -and (Test-Path (Join-Path $phone.InstallLocation 'AppxManifest.xml'))) { "
            "  try { "
            "    [xml]$xml = Get-Content (Join-Path $phone.InstallLocation 'AppxManifest.xml') -ErrorAction SilentlyContinue; "
            "    $caps = @($xml.Package.Capabilities.ChildNodes | ForEach-Object { $_.Name } | Where-Object { $_ }); "
            "  } catch {} "
            "}; "
            "$samples = @(); "
            "foreach ($p in ($pkgs | Select-Object -First 5)) { "
            "  $samples += @{ Name = $p.Name; Version = $p.Version; Publisher = $p.Publisher } "
            "}; "
            "@{"
            "  Total = $pkgs.Count; "
            "  PhoneInstalled = ($null -ne $phone); "
            "  PhoneVersion = if ($phone) { $phone.Version } else { $null }; "
            "  PhoneFullName = if ($phone) { $phone.PackageFullName } else { $null }; "
            "  Capabilities = $caps; "
            "  Samples = $samples "
            "} | ConvertTo-Json -Compress"
        )

        data = self.executor.execute_script_sync(
            script=script,
            timeout_sec=8.0,
            cache_key="winrt_appmodel",
            cache_ttl_sec=60.0,
        )

        if "error" in data or not data:
            logger.debug(f"[WinRTAppModelSubsystem] Использование fallback значений: {data.get('error')}")
            return WinRTPackageTelemetry()

        caps = data.get("Capabilities", [])
        if isinstance(caps, str):
            caps = [caps]

        samples = data.get("Samples", [])
        if not isinstance(samples, list):
            samples = []

        return WinRTPackageTelemetry(
            total_uwp_packages=int(data.get("Total") or 0),
            phone_link_installed=bool(data.get("PhoneInstalled", False)),
            phone_link_version=data.get("PhoneVersion"),
            phone_link_package_full_name=data.get("PhoneFullName"),
            phone_link_appcontainer=True,
            phone_link_capabilities=caps,
            sample_packages=samples,
        )

    async def get_appmodel_telemetry_async(self) -> WinRTPackageTelemetry:
        """Асинхронный неблокирующий сбор телеметрии UWP приложений."""
        return await asyncio.to_thread(self.get_appmodel_telemetry_sync)
