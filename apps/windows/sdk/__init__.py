# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: AI-Windows-Admin Apps Windows SDK - Package Root
# =============================================================================
# Description:
#   Единый Windows SDK для AI-Windows-Admin.
#   Предоставляет централизованный доступ к низкоуровневым C-FFI вызовам,
#   управлению драйверами, системными компонентами Features, ядру SafeOps,
#   27 функциональным модулям администрирования и типизированной системе исключений.
#
# Usage Examples:
#   Python API:
#     from apps.windows.sdk import WindowsSDK, windows_sdk
#     from apps.windows.sdk.exceptions import WindowsSDKError, SafeOpsViolationError
#     from apps.windows.sdk.core import SafeExecutor, WinAPI
#     from apps.windows.sdk.native import Kernel32, Advapi32
#
# File: __init__.py
# Project: ai-windows-admin
# Package: apps.windows.sdk
# Author: hypo69
# Copyright: © 2026 hypo69
# Updated: 2026-10-16 20:35:00
# =============================================================================

from __future__ import annotations
"""Единый комплексный SDK для операционной системы Windows."""

from apps.windows.sdk.client import (
    WindowsSDK,
    windows_sdk,
    NativeSubsystem,
    DriversSubsystem,
    FeaturesSubsystem,
    CoreSubsystem,
    ModulesSubsystem,
)

# Экспорт ключевых подпакетов
from apps.windows.sdk import native
from apps.windows.sdk import win32_ffi
from apps.windows.sdk import core
from apps.windows.sdk import drivers
from apps.windows.sdk import features
from apps.windows.sdk import modules
from apps.windows.sdk.dynamic_runner import DynamicToolRunner
from apps.windows.sdk.modules.network.discovery import NetworkDiscoveryManager, WindowsNetworkDiscovery
from apps.windows.sdk.modules.regional import RegionalManager

# Экспорт ключевых исключений SDK
from apps.windows.sdk.exceptions import (
    WindowsSDKError,
    NativeCallError,
    Win32NativeError,
    AccessDeniedSDKError,
    PrivilegeElevationRequiredError,
    InvalidHandleError,
    SafeOpsViolationError,
    DryRunExecutionError,
    SystemRestorePointError,
    DiagnosticEngineError,
    ParameterValidationError,
    DriverSubsystemError,
    DriverNotFoundError,
    HardwareProbeError,
    DriverDownloadError,
    WindowsFeatureError,
    FeatureNotFoundError,
    FeatureInstallationError,
    ModuleOperationError,
    RegistryAccessError,
    ServiceControlError,
    TaskSchedulerError,
    ProcessOperationError,
    ExplorerManagerError,
    ShellNamespaceError,
    BackupOperationError,
    FirewallConfigurationError,
    DefenderConfigurationError,
)

__all__ = [
    # Фасад
    "WindowsSDK",
    "windows_sdk",
    "NativeSubsystem",
    "DriversSubsystem",
    "FeaturesSubsystem",
    "CoreSubsystem",
    "ModulesSubsystem",
    # Подпакеты
    "native",
    "win32_ffi",
    "core",
    "drivers",
    "features",
    "modules",
    "software_scanner",
    "exceptions",
    "DynamicToolRunner",
    # Исключения
    "WindowsSDKError",
    "NativeCallError",
    "Win32NativeError",
    "AccessDeniedSDKError",
    "PrivilegeElevationRequiredError",
    "InvalidHandleError",
    "SafeOpsViolationError",
    "DryRunExecutionError",
    "SystemRestorePointError",
    "DiagnosticEngineError",
    "ParameterValidationError",
    "DriverSubsystemError",
    "DriverNotFoundError",
    "HardwareProbeError",
    "DriverDownloadError",
    "WindowsFeatureError",
    "FeatureNotFoundError",
    "FeatureInstallationError",
    "ModuleOperationError",
    "RegistryAccessError",
    "ServiceControlError",
    "TaskSchedulerError",
    "ProcessOperationError",
    "ExplorerManagerError",
    "ShellNamespaceError",
    "BackupOperationError",
    "FirewallConfigurationError",
    "DefenderConfigurationError",
    "NetworkDiscoveryManager",
    "WindowsNetworkDiscovery",
    "RegionalManager",
]

